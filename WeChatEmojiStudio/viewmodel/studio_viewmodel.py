import os
import shutil
from PySide6.QtCore import QObject, Signal, QThread
from domain.project_manager import ProjectManager
from domain.padding_engine import SafePaddingEngine
from domain.slicer import VideoGridSlicer
from domain.asset_builder import WeChatAssetPackager
from domain.f12_script_builder import F12ScriptBuilder
from domain.compressor import ImageCompressor

class SliceWorkerThread(QThread):
    progress_signal = Signal(int, int)
    finished_signal = Signal(bool, str)

    def __init__(self, video_path, output_dir, metadata, make_transparent=True, scale_percent=94):
        super().__init__()
        self.video_path = video_path
        self.output_dir = output_dir
        self.metadata = metadata
        self.make_transparent = make_transparent
        self.scale_percent = scale_percent

    def run(self):
        try:
            def on_progress(cur, total):
                self.progress_signal.emit(cur, total)

            VideoGridSlicer.slice_5x3_video(
                video_path=self.video_path,
                output_dir=self.output_dir,
                grid_metadata=self.metadata,
                make_transparent=self.make_transparent,
                scale_percent=self.scale_percent,
                progress_callback=on_progress
            )
            self.finished_signal.emit(True, "切片转码成功完成！")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class TransparentWorkerThread(QThread):
    progress_signal = Signal(int, int)
    finished_signal = Signal(bool, str)

    def __init__(self, gifs_dir, scale_percent=94):
        super().__init__()
        self.gifs_dir = gifs_dir
        self.scale_percent = scale_percent

    def run(self):
        try:
            gif_files = sorted([f for f in os.listdir(self.gifs_dir) if f.lower().endswith(".gif") and f[:2].isdigit()])
            total = len(gif_files)
            for i, fname in enumerate(gif_files, 1):
                p = os.path.join(self.gifs_dir, fname)
                ImageCompressor.make_gif_transparent(p, p, tolerance=30, scale_percent=self.scale_percent)
                self.progress_signal.emit(i, total)
            self.finished_signal.emit(True, "15 个表情已全部转换为纯透明背景 (已智能内缩防切字)！")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class CompressWorkerThread(QThread):
    progress_signal = Signal(int, int, str)
    finished_signal = Signal(bool, str)

    def __init__(self, gifs_dir, max_kb=480):
        super().__init__()
        self.gifs_dir = gifs_dir
        self.max_kb = max_kb

    def run(self):
        try:
            gif_files = sorted([f for f in os.listdir(self.gifs_dir) if f.lower().endswith(".gif") and f[:2].isdigit()])
            total = len(gif_files)
            if total == 0:
                self.finished_signal.emit(False, "未找到任何 GIF 文件！")
                return

            succ_count = 0
            for i, fname in enumerate(gif_files, 1):
                p = os.path.join(self.gifs_dir, fname)
                ok, final_kb, msg = ImageCompressor.compress_gif(p, p, max_kb=self.max_kb)
                if ok:
                    succ_count += 1
                self.progress_signal.emit(i, total, f"{fname} -> {final_kb:.0f}KB")
            self.finished_signal.emit(True, f"已成功将 {succ_count}/{total} 个表情压缩至微信安全红线 (≤{self.max_kb}KB 🟢)！")
        except Exception as e:
            self.finished_signal.emit(False, str(e))

class StudioViewModel(QObject):
    projects_loaded = Signal(list)
    current_project_changed = Signal(dict)
    slice_progress = Signal(int, int)
    slice_completed = Signal(bool, str)
    compress_progress = Signal(int, int, str)
    compress_completed = Signal(bool, str)
    package_completed = Signal(str)

    def __init__(self):
        super().__init__()
        self.projects = []
        self.current_project = None
        self.worker_thread = None

    def load_projects(self):
        self.projects = ProjectManager.list_projects()
        self.projects_loaded.emit(self.projects)
        if self.projects and not self.current_project:
            self.select_project(self.projects[0]["name"])

    def select_project(self, name_or_dir):
        for p in self.projects:
            if p["name"] == name_or_dir or p["dir"] == name_or_dir:
                self.current_project = p
                self.current_project_changed.emit(p)
                return
        if os.path.isdir(name_or_dir):
            p = ProjectManager.load_project(name_or_dir)
            self.current_project = p
            self.projects.append(p)
            self.current_project_changed.emit(p)

    def save_current_project_meta(self, meta_dict):
        if self.current_project:
            self.current_project.update(meta_dict)
            ProjectManager.save_project(self.current_project)

    def generate_safe_16x9_image(self, input_image_path):
        if not self.current_project:
            return None, "未选择工程"
        p_dir = self.current_project["dir"]
        out_path = os.path.join(p_dir, "待生视频_16x9安全图.png")
        meta = SafePaddingEngine.generate_safe_16x9_image(
            input_image_path=input_image_path,
            output_image_path=out_path
        )
        self.current_project["grid_metadata"] = meta
        self.current_project["safe_16x9_image"] = out_path
        ProjectManager.save_project(self.current_project)
        return out_path, "成功生成 16:9 安全防裁剪底图！"

    def start_slice_video(self, video_path, make_transparent=True, scale_percent=94):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        output_dir = os.path.join(p_dir, "gifs")
        meta = self.current_project.get("grid_metadata")

        self.worker_thread = SliceWorkerThread(video_path, output_dir, meta, make_transparent, scale_percent)
        self.worker_thread.progress_signal.connect(self.slice_progress.emit)
        self.worker_thread.finished_signal.connect(self._on_slice_done)
        self.worker_thread.start()

    def make_existing_gifs_transparent(self, scale_percent=94):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        gifs_dir = os.path.join(p_dir, "gifs")
        if not os.path.exists(gifs_dir):
            for sub in os.listdir(p_dir):
                cand = os.path.join(p_dir, sub, "01_表情主图_240x240_GIF")
                if os.path.exists(cand):
                    gifs_dir = cand
                    break

        if not os.path.exists(gifs_dir):
            self.slice_completed.emit(False, "未找到已切片的 GIF 文件夹！")
            return

        self.worker_thread = TransparentWorkerThread(gifs_dir, scale_percent)
        self.worker_thread.progress_signal.connect(self.slice_progress.emit)
        self.worker_thread.finished_signal.connect(self._on_slice_done)
        self.worker_thread.start()

    def _on_slice_done(self, success, msg):
        if success and self.current_project:
            self.current_project["status"] = "sliced"
            ProjectManager.save_project(self.current_project)
            self.current_project_changed.emit(self.current_project)
        self.slice_completed.emit(success, msg)

    def compress_all_gifs(self, max_kb=480):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        gifs_dir = os.path.join(p_dir, "gifs")
        if not os.path.exists(gifs_dir):
            for sub in os.listdir(p_dir):
                cand = os.path.join(p_dir, sub, "01_表情主图_240x240_GIF")
                if os.path.exists(cand):
                    gifs_dir = cand
                    break

        if not os.path.exists(gifs_dir):
            self.compress_completed.emit(False, "未找到已切片的 GIF 文件夹！")
            return

        self.worker_thread = CompressWorkerThread(gifs_dir, max_kb)
        self.worker_thread.progress_signal.connect(self.compress_progress.emit)
        self.worker_thread.finished_signal.connect(self._on_compress_done)
        self.worker_thread.start()

    def _on_compress_done(self, success, msg):
        self.compress_completed.emit(success, msg)

    def export_wechat_package(self, export_dir: str = None):
        if not self.current_project:
            return None
        try:
            p_dir = self.current_project["dir"]
            if not export_dir:
                export_dir = os.path.join(p_dir, f"{self.current_project['name']}_微信表情提交包")
            WeChatAssetPackager.pack_project(
                project_dir=p_dir,
                export_dir=export_dir,
                title=self.current_project.get("title", ""),
                intro=self.current_project.get("intro", ""),
                reward_text=self.current_project.get("reward_text", ""),
                meanings=self.current_project.get("meanings", []),
                tags=self.current_project.get("tags", [])
            )
            self.package_completed.emit(export_dir)
            return export_dir
        except Exception as e:
            self.slice_completed.emit(False, f"打包失败: {str(e)}")
            return None

    def get_f12_script(self):
        if not self.current_project:
            return ""
        return F12ScriptBuilder.build_script(
            title=self.current_project.get("title", ""),
            intro=self.current_project.get("intro", ""),
            reward_text=self.current_project.get("reward_text", ""),
            meanings=self.current_project.get("meanings", []),
            tags=self.current_project.get("tags", [])
        )
