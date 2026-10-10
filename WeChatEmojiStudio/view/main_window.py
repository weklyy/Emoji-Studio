import os
import subprocess
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QMessageBox, QApplication, QSplitter
)
from PySide6.QtCore import Qt
from view.styles import GLOBAL_STYLE
from view.project_sidebar import ProjectSidebar
from view.workspace_panel import WorkspacePanel
from view.wechat_preview_panel import WeChatPreviewPanel
from viewmodel.studio_viewmodel import StudioViewModel

class MainWindow(QMainWindow):
    """
    微信表情包创作与资产全周期管理工坊 主窗体
    严格践行 DDD + MVVM 架构规范，零业务逻辑嵌入
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Emoji-Studio v0.01 • 微信表情创作与提审工坊")
        self.resize(1300, 840)
        self.setStyleSheet(GLOBAL_STYLE)

        self.vm = StudioViewModel()
        self._init_ui()
        self._bind_viewmodel()

        self.vm.load_projects()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        self.sidebar = ProjectSidebar()
        self.workspace = WorkspacePanel()
        self.wechat_sim = WeChatPreviewPanel()

        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.workspace)
        self.splitter.addWidget(self.wechat_sim)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([220, 680, 400])

        main_layout.addWidget(self.splitter)

    def _bind_viewmodel(self):
        self.sidebar.project_selected.connect(self.vm.select_project)
        self.sidebar.new_project_requested.connect(self._on_create_new_project)

        self.workspace.meta_updated.connect(self.vm.save_current_project_meta)
        self.workspace.generate_safe_image_clicked.connect(self._on_gen_safe_image)
        self.workspace.start_slice_clicked.connect(self._on_start_slice)
        self.workspace.make_transparent_clicked.connect(self._on_start_make_transparent)
        self.workspace.compress_all_clicked.connect(self._on_start_compress)
        self.workspace.gifs_imported.connect(self._on_gifs_imported_refresh)
        self.workspace.open_text_workshop_clicked.connect(self.wechat_sim._on_open_text_workshop)

        self.wechat_sim.copy_f12_requested.connect(self._on_copy_f12)
        self.wechat_sim.export_requested.connect(self.vm.export_wechat_package)
        self.wechat_sim.status_updated.connect(self._on_sim_status_updated)

        self.vm.projects_loaded.connect(self._on_projects_loaded)
        self.vm.current_project_changed.connect(self._on_current_project_changed)
        self.vm.slice_progress.connect(self.workspace.update_slice_progress)
        self.vm.slice_completed.connect(self.workspace.on_slice_finished)
        self.vm.slice_completed.connect(self._on_slice_completed_refresh)
        self.vm.compress_completed.connect(self._on_compress_completed)
        self.vm.package_completed.connect(self._on_package_completed)

    def _on_start_slice(self, vid_path, make_transparent, scale_percent):
        self.wechat_sim.release_movies()
        self.vm.start_slice_video(vid_path, make_transparent, scale_percent)

    def _on_start_make_transparent(self, scale_percent):
        self.wechat_sim.release_movies()
        self.vm.make_existing_gifs_transparent(scale_percent)

    def _on_start_compress(self, max_kb=480):
        self.wechat_sim.release_movies()
        self.vm.compress_all_gifs(max_kb)

    def _on_compress_completed(self, success, msg):
        if success and self.vm.current_project:
            self.wechat_sim.load_project(self.vm.current_project)
            QMessageBox.information(self, "批量压缩完成", f"🎉 {msg}")
        else:
            QMessageBox.warning(self, "压缩提示", msg)

    def _on_slice_completed_refresh(self, ok, msg):
        if ok and self.vm.current_project:
            self.wechat_sim.load_project(self.vm.current_project)

    def _on_gifs_imported_refresh(self):
        if self.vm.current_project:
            self.wechat_sim.load_project(self.vm.current_project)
            self.sidebar.set_projects(self.vm.projects, self.vm.current_project["name"])

    def _on_projects_loaded(self, projects):
        cur_name = self.vm.current_project["name"] if self.vm.current_project else None
        self.sidebar.set_projects(projects, cur_name)

    def _on_current_project_changed(self, project):
        self.workspace.load_project_data(project)
        self.wechat_sim.load_project(project)
        self.sidebar.set_projects(self.vm.projects, project["name"])

    def _on_create_new_project(self, name):
        root = self.vm.current_project["dir"] if self.vm.current_project else r"D:\Work\apps\微信表情包"
        parent_dir = os.path.dirname(root)
        new_dir = os.path.join(parent_dir, name)
        os.makedirs(new_dir, exist_ok=True)
        default_scheme = os.path.join(new_dir, "方案.txt")
        if not os.path.exists(default_scheme):
            with open(default_scheme, "w", encoding="utf-8") as f:
                f.write(f"【{name}】\n01\t你好\n02\t谢谢\n03\t收到\n04\t点赞\n05\t加油\n")
        self.vm.load_projects()
        self.vm.select_project(name)
        QMessageBox.information(self, "创建成功", f"项目工程【{name}】已创建完毕！")

    def _on_gen_safe_image(self, img_path):
        out_path, msg = self.vm.generate_safe_16x9_image(img_path)
        if out_path:
            self.workspace.safe_img_status.setText(f"✔ 已生成: {os.path.basename(out_path)}")
            QMessageBox.information(
                self, "防裁剪安全底图已生成",
                f"{msg}\n文件已保存至：\n{out_path}\n\n💡 现在您可以拿着这张图片直接送入可灵、海螺或Runway生成 16:9 视频，再也不会被切掉头顶和脚部了！"
            )
        else:
            QMessageBox.warning(self, "生成失败", msg)

    def _on_copy_f12(self):
        js_code = self.vm.get_f12_script()
        if not js_code:
            QMessageBox.warning(self, "提示", "当前项目暂无可用的提审数据！")
            return

        QApplication.clipboard().setText(js_code)
        QMessageBox.information(
            self, "已复制到剪贴板！",
            "🎉 微信开放平台 F12 万能自动填表脚本已成功复制到剪贴板！\n\n"
            "【使用方式】：\n"
            "1. 浏览器打开微信表情提交审核页面\n"
            "2. 按键盘上的【F12】键打开开发者工具\n"
            "3. 切换到【Console (控制台)】选项卡\n"
            "4. 粘贴 (Ctrl+V) 并按回车 (Enter)\n\n"
            "👉 网页上的【表情名称、专辑介绍、赞赏引导语、15个表情含义】将秒级全部自动填满并勾选原创！"
        )

    def _on_sim_status_updated(self, meta):
        self.vm.save_current_project_meta(meta)
        self.sidebar.set_projects(self.vm.projects, self.vm.current_project["name"])

    def _on_package_completed(self, export_dir):
        QMessageBox.information(
            self, "提审物料打包完成",
            f"🎉 微信表情开放平台全套审核物料已成功打包完毕！\n"
            f"所有主图与伴生图片均已 100% 压缩到微信官方红线之内。\n\n"
            f"保存路径：\n{export_dir}"
        )
        if os.path.exists(export_dir):
            subprocess.run(["explorer", export_dir])
