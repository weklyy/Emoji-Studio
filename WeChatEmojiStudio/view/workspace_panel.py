from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QGroupBox, QFileDialog, QMessageBox, QProgressBar, QCheckBox,
    QSpinBox, QTabWidget, QScrollArea, QFrame, QProgressDialog, QApplication
)
from PySide6.QtCore import Qt, Signal
import os
import re
import shutil
import subprocess
from domain.path_memory import PathMemory
from domain.project_manager import ProjectManager
from domain.gif_text_editor import GifTextEditor
from view.batch_titles_dialog import BatchTitlesDialog
from view.gif_editor_dialog import GifEditorDialog

class WorkspacePanel(QWidget):
    meta_updated = Signal(dict)
    generate_safe_image_clicked = Signal(str)
    start_slice_clicked = Signal(str, bool, int)
    make_transparent_clicked = Signal(int)
    compress_all_clicked = Signal(int)
    gifs_imported = Signal()
    open_text_workshop_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(380)
        self.current_project = None
        self._init_ui()

    def _init_ui(self):
        panel_layout = QVBoxLayout(self)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        # 内部可自适应滚动区域，确保各分辨率屏幕永不溢出
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        self.project_title_lbl = QLabel("当前工程: 未选择")
        self.project_title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #0F172A;")
        layout.addWidget(self.project_title_lbl)

        # ---------------- 步骤 1: 提审文案 ----------------
        step1_box = QGroupBox("步骤 1: 提审文案规范管理 (失焦即自动保存)")
        s1_layout = QVBoxLayout(step1_box)
        s1_layout.setSpacing(8)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("专辑名称 (≤8字):"))
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(8)
        self.name_edit.editingFinished.connect(self._commit_meta)
        name_row.addWidget(self.name_edit)

        name_row.addWidget(QLabel("赞赏引导语 (≤15字):"))
        self.reward_edit = QLineEdit()
        self.reward_edit.setMaxLength(15)
        self.reward_edit.editingFinished.connect(self._commit_meta)
        name_row.addWidget(self.reward_edit)
        s1_layout.addLayout(name_row)

        s1_layout.addWidget(QLabel("专辑介绍 (≤100字):"))
        self.intro_edit = QTextEdit()
        self.intro_edit.setMaximumHeight(65)
        self.intro_edit.textChanged.connect(self._on_intro_changed)
        s1_layout.addWidget(self.intro_edit)

        layout.addWidget(step1_box)

        # ---------------- 制作模式核心选项卡 (已有GIF上传文字 vs 视频生图切片) ----------------
        self.mode_tabs = QTabWidget()

        # ==================== 选项卡 1: 已有 GIF 上传与文字工坊 (独立专栏) ====================
        tab_gif = QWidget()
        tg_layout = QVBoxLayout(tab_gif)
        tg_layout.setContentsMargins(10, 12, 10, 12)
        tg_layout.setSpacing(10)

        intro_card = QFrame()
        intro_card.setStyleSheet("background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 6px;")
        ic_layout = QVBoxLayout(intro_card)
        ic_layout.setContentsMargins(4, 4, 4, 4)
        intro_lbl = QLabel("💡 独立功能：如果您已有制作好的 GIF 动图（如透明背景或无字动图），直接在此上传即可，无需走视频切片流程！上传后可批量添加开源商用艺术字。")
        intro_lbl.setStyleSheet("color: #065F46; font-size: 12px; font-weight: 500; background: transparent;")
        intro_lbl.setWordWrap(True)
        ic_layout.addWidget(intro_lbl)
        tg_layout.addWidget(intro_card)

        # 子模块 1: 上传已有 GIF
        upload_box = QGroupBox("1. 上传已做好的动态 GIF 素材")
        up_layout = QVBoxLayout(upload_box)
        up_layout.setSpacing(8)

        up_btn_row = QHBoxLayout()
        self.upload_folder_btn = QPushButton("📁 选择并上传 GIF 文件夹...")
        self.upload_folder_btn.setToolTip("选择存放已做好 GIF 动图的文件夹，批量载入到当前工程")
        self.upload_folder_btn.clicked.connect(self._on_upload_gif_folder)
        up_btn_row.addWidget(self.upload_folder_btn)

        self.upload_files_btn = QPushButton("🖼️ 框选上传 GIF 文件 (可多选)...")
        self.upload_files_btn.setToolTip("按住 Ctrl 或 Shift 框选多个已做好的 GIF 文件导入")
        self.upload_files_btn.clicked.connect(self._on_upload_gif_files)
        up_btn_row.addWidget(self.upload_files_btn)

        self.open_gifs_dir_btn = QPushButton("📂 打开 GIF 目录")
        self.open_gifs_dir_btn.clicked.connect(self._open_gifs_folder)
        up_btn_row.addWidget(self.open_gifs_dir_btn)
        up_layout.addLayout(up_btn_row)

        self.gif_upload_status_lbl = QLabel("状态: 等待上传已做好的 GIF 动图")
        self.gif_upload_status_lbl.setStyleSheet("color: #475569; font-size: 12px;")
        up_layout.addWidget(self.gif_upload_status_lbl)
        tg_layout.addWidget(upload_box)

        # 子模块 2: 核对与编辑每一张图片的标题 (共 N 张)
        self.titles_box = QGroupBox("2. 核对与编辑每一张图片的标题 (自动提取文件名或自由修改)")
        tb_layout = QVBoxLayout(self.titles_box)
        tb_layout.setSpacing(6)

        tb_top = QHBoxLayout()
        self.titles_summary_lbl = QLabel("当前工程标题清单 (0 个):")
        self.titles_summary_lbl.setStyleSheet("font-size: 11px; color: #475569; font-weight: bold;")
        tb_top.addWidget(self.titles_summary_lbl)
        tb_top.addStretch(1)

        self.batch_paste_btn = QPushButton("📋 批量粘贴/快速填入所有标题...")
        self.batch_paste_btn.setFixedHeight(26)
        self.batch_paste_btn.setToolTip("多行粘贴所有标题，一秒批量分配给每张图片")
        self.batch_paste_btn.clicked.connect(self._on_batch_paste_titles)
        tb_top.addWidget(self.batch_paste_btn)
        tb_layout.addLayout(tb_top)

        # 标题滚动容器
        self.titles_scroll = QScrollArea()
        self.titles_scroll.setWidgetResizable(True)
        self.titles_scroll.setMaximumHeight(160)
        self.titles_scroll.setStyleSheet("QScrollArea { border: 1px solid #E2E8F0; border-radius: 4px; background: #FFFFFF; }")
        
        self.titles_container = QWidget()
        self.titles_layout = QVBoxLayout(self.titles_container)
        self.titles_layout.setContentsMargins(6, 6, 6, 6)
        self.titles_layout.setSpacing(4)
        self.titles_scroll.setWidget(self.titles_container)
        tb_layout.addWidget(self.titles_scroll)

        tg_layout.addWidget(self.titles_box)

        # 子模块 3: 文字添加与排版工坊
        text_action_box = QGroupBox("3. 批量手动添加艺术文字 (100% 开源商用字库)")
        ta_layout = QVBoxLayout(text_action_box)
        ta_layout.setSpacing(8)

        ta_tip = QLabel("核心流转：只需在文字工坊调好第 1 张图片的字体、字号、色彩、描边和位置，点击【一键为全部表情添加文字】，其余图片秒级全部自动按各自标题渲染！")
        ta_tip.setStyleSheet("color: #065F46; font-size: 11px; font-weight: 500;")
        ta_tip.setWordWrap(True)
        ta_layout.addWidget(ta_tip)

        ta_row1 = QHBoxLayout()
        self.open_workshop_btn = QPushButton("✨ 打开文字工坊 (排版第1张并一键同步全部)...")
        self.open_workshop_btn.setObjectName("PrimaryBtn")
        self.open_workshop_btn.setMinimumHeight(38)
        self.open_workshop_btn.setToolTip("打开全功能文字工坊，为上传的 GIF 逐个或批量添加艺术字")
        self.open_workshop_btn.clicked.connect(self._on_click_open_workshop)
        ta_row1.addWidget(self.open_workshop_btn)

        self.quick_apply_btn = QPushButton("⚡ 一键为全部表情批量添加文字 (按当前排版)")
        self.quick_apply_btn.setMinimumHeight(38)
        self.quick_apply_btn.setToolTip("使用最近一次设定的字体与样式，直接为当前工程所有 GIF 批量添加文字")
        self.quick_apply_btn.clicked.connect(self._on_quick_apply_all_text)
        ta_row1.addWidget(self.quick_apply_btn)
        ta_layout.addLayout(ta_row1)

        ta_row2 = QHBoxLayout()
        self.compress_all_btn = QPushButton("🗜️ 一键批量压缩所有表情 (确保 ≤480KB)")
        self.compress_all_btn.setMinimumHeight(36)
        self.compress_all_btn.setToolTip("使用多通调色板与智能抽帧算法，严格将所有表情体积压缩至 480KB 微信红线之内")
        self.compress_all_btn.clicked.connect(lambda: self.compress_all_clicked.emit(480))
        ta_row2.addWidget(self.compress_all_btn)

        self.tab_trans_btn = QPushButton("🌟 一键去除外围白底 (转为纯透明)")
        self.tab_trans_btn.setMinimumHeight(36)
        self.tab_trans_btn.setToolTip("如果上传的 GIF 还带有白底，一键执行边缘泛洪透明化与安全内缩")
        self.tab_trans_btn.clicked.connect(self._on_make_transparent_clicked)
        ta_row2.addWidget(self.tab_trans_btn)
        ta_layout.addLayout(ta_row2)

        tg_layout.addWidget(text_action_box)
        tg_layout.addStretch(1)

        self.mode_tabs.addTab(tab_gif, "🎨 已有 GIF 上传与文字工坊 (独立专栏)")

        # ==================== 选项卡 2: 视频生图与切片流程 (从零制作) ====================
        tab_video = QWidget()
        tv_layout = QVBoxLayout(tab_video)
        tv_layout.setContentsMargins(10, 10, 10, 10)
        tv_layout.setSpacing(10)

        # 步骤 2: 15宫格 ➔ 16:9 安全图
        step2_box = QGroupBox("步骤 2: 15宫格 ➔ 16:9 安全图 (防截断引擎)")
        s2_layout = QVBoxLayout(step2_box)
        s2_layout.setSpacing(8)

        tip_lbl = QLabel("💡 核心：自动在 15 宫格四周添加 8% 呼吸安全垫。送入可灵/海螺等平台生视频时，绝不会再切掉耳朵和脚！")
        tip_lbl.setStyleSheet("color: #64748B; font-size: 12px;")
        tip_lbl.setWordWrap(True)
        s2_layout.addWidget(tip_lbl)

        s2_btn_row = QHBoxLayout()
        self.sel_grid_img_btn = QPushButton("📁 选择 15 宫格原图...")
        self.sel_grid_img_btn.clicked.connect(self._on_choose_grid_image)
        s2_btn_row.addWidget(self.sel_grid_img_btn)

        self.gen_safe_img_btn = QPushButton("⚡ 生成 16:9 防裁剪视频底图")
        self.gen_safe_img_btn.setObjectName("PrimaryBtn")
        self.gen_safe_img_btn.clicked.connect(self._on_gen_safe_image)
        s2_btn_row.addWidget(self.gen_safe_img_btn)

        self.open_dir_btn = QPushButton("📂 打开工程文件夹")
        self.open_dir_btn.clicked.connect(self._open_project_folder)
        s2_btn_row.addWidget(self.open_dir_btn)
        s2_layout.addLayout(s2_btn_row)

        self.safe_img_status = QLabel("状态: 尚未生成安全图")
        self.safe_img_status.setStyleSheet("color: #475569; font-size: 12px;")
        s2_layout.addWidget(self.safe_img_status)
        tv_layout.addWidget(step2_box)

        # 步骤 3: 视频切片
        step3_box = QGroupBox("步骤 3: 16:9 动态视频一键切片与透明化")
        s3_layout = QVBoxLayout(step3_box)
        s3_layout.setSpacing(8)

        param_row = QHBoxLayout()
        self.trans_check = QCheckBox("去除外围白底为纯透明背景")
        self.trans_check.setChecked(True)
        self.trans_check.setStyleSheet("font-weight: bold; color: #059669;")
        param_row.addWidget(self.trans_check)

        param_row.addWidget(QLabel("防切字内缩比例:"))
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(80, 100)
        self.scale_spin.setValue(94)
        self.scale_spin.setSuffix("%")
        param_row.addWidget(self.scale_spin)

        self.onekey_trans_btn = QPushButton("✨ 一键将已有 GIF 转为透明底")
        self.onekey_trans_btn.clicked.connect(self._on_make_transparent_clicked)
        param_row.addWidget(self.onekey_trans_btn)
        s3_layout.addLayout(param_row)

        s3_btn_row = QHBoxLayout()
        self.sel_video_btn = QPushButton("📁 选择 16:9 动态视频.mp4...")
        self.sel_video_btn.clicked.connect(self._on_choose_video)
        s3_btn_row.addWidget(self.sel_video_btn)

        self.start_slice_btn = QPushButton("⚡ 一键切片为 15 个 GIF")
        self.start_slice_btn.setObjectName("PrimaryBtn")
        self.start_slice_btn.clicked.connect(self._on_start_slice)
        s3_btn_row.addWidget(self.start_slice_btn)
        s3_layout.addLayout(s3_btn_row)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        s3_layout.addWidget(self.progress_bar)

        self.slice_status_lbl = QLabel("状态: 等待视频文件输入")
        self.slice_status_lbl.setStyleSheet("color: #475569; font-size: 12px;")
        s3_layout.addWidget(self.slice_status_lbl)
        tv_layout.addWidget(step3_box)
        tv_layout.addStretch(1)

        self.mode_tabs.addTab(tab_video, "📹 视频生图与切片流程 (从零制作)")

        layout.addWidget(self.mode_tabs)
        layout.addStretch(1)

        scroll.setWidget(container)
        panel_layout.addWidget(scroll)

    def load_project_data(self, project: dict):
        self.current_project = project
        self.project_title_lbl.setText(f"当前工程: {project['name']}")
        self.name_edit.setText(project.get("title", ""))
        self.reward_edit.setText(project.get("reward_text", ""))
        self.intro_edit.setPlainText(project.get("intro", ""))

        p_dir = project["dir"]
        safe_img = os.path.join(p_dir, "待生视频_16x9安全图.png")
        if os.path.exists(safe_img):
            self.safe_img_status.setText(f"✔ 16:9 防裁剪安全图已就绪: {os.path.basename(safe_img)}")
        else:
            self.safe_img_status.setText("状态: 尚未生成安全图")

        vid = os.path.join(p_dir, "15宫格视频.mp4")
        if os.path.exists(vid):
            self.slice_status_lbl.setText(f"✔ 视频就绪: 15宫格视频.mp4")
        else:
            self.slice_status_lbl.setText("状态: 等待视频文件输入")

        # 检查已有的 GIF 状态
        # 检查已有的 GIF 状态与标题清单
        self._refresh_upload_status()
        self._refresh_titles_ui()

    def _refresh_upload_status(self):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        gifs_dir = os.path.join(p_dir, "gifs")

        gif_count = 0
        if os.path.exists(gifs_dir):
            gif_count = len([f for f in os.listdir(gifs_dir) if f.lower().endswith(".gif")])
        else:
            # 检查是否有嵌套目录
            for root, dirs, files in os.walk(p_dir):
                g_list = [f for f in files if f.lower().endswith(".gif") and f[:2].isdigit()]
                if len(g_list) >= 8:
                    gif_count = len(g_list)
                    break

        if gif_count > 0:
            self.gif_upload_status_lbl.setText(f"✔ 当前工程已就绪 {gif_count} 个 GIF 动图，可随时进入文字工坊添加文字！")
            self.gif_upload_status_lbl.setStyleSheet("color: #059669; font-weight: bold; font-size: 12px;")
        else:
            self.gif_upload_status_lbl.setText("状态: 等待上传已做好的 GIF 动图")
            self.gif_upload_status_lbl.setStyleSheet("color: #475569; font-size: 12px;")

    def _refresh_titles_ui(self):
        """刷新并展示当前工程所有表情的标题编辑输入框"""
        while self.titles_layout.count():
            item = self.titles_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        if not self.current_project:
            self.titles_summary_lbl.setText("当前工程标题清单: 未选择工程")
            return

        meanings = self.current_project.get("meanings", [])
        p_dir = self.current_project["dir"]
        gifs_dir = os.path.join(p_dir, "gifs")

        gif_files = []
        if os.path.exists(gifs_dir):
            gif_files = sorted([f for f in os.listdir(gifs_dir) if f.lower().endswith(".gif")])

        count = max(len(gif_files), len(meanings))
        self.titles_summary_lbl.setText(f"当前共 {count} 个表情标题 (支持直接编辑或批量粘贴):")

        for i in range(count):
            row = QHBoxLayout()
            row.setContentsMargins(2, 1, 2, 1)
            row.setSpacing(6)

            tag_lbl = QLabel(f"#{i+1:02d}")
            tag_lbl.setFixedWidth(28)
            tag_lbl.setStyleSheet("font-weight: bold; color: #64748B; font-size: 11px;")
            row.addWidget(tag_lbl)

            cur_t = meanings[i] if i < len(meanings) else f"表情_{i+1:02d}"
            edit = QLineEdit(cur_t)
            edit.setFixedHeight(24)
            edit.setStyleSheet("""
                QLineEdit {
                    font-size: 11px;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    padding: 1px 4px;
                    background: #FFFFFF;
                }
                QLineEdit:focus {
                    border: 1px solid #07C160;
                }
            """)
            edit.editingFinished.connect(lambda e=edit, idx=i: self._on_single_title_edited(idx, e.text()))
            row.addWidget(edit)

            self.titles_layout.addLayout(row)

    def _on_single_title_edited(self, idx, text):
        if not self.current_project:
            return
        text = text.strip()
        meanings = list(self.current_project.get("meanings", []))
        while len(meanings) <= idx:
            meanings.append(f"表情_{len(meanings)+1:02d}")
        meanings[idx] = text
        self.current_project["meanings"] = meanings
        ProjectManager.save_project(self.current_project)
        self.meta_updated.emit({"meanings": meanings})
        self.gifs_imported.emit()

    def _on_batch_paste_titles(self):
        """点击批量填入所有标题"""
        if not self.current_project:
            QMessageBox.warning(self, "提示", "请先在左侧选择一个工程！")
            return
        current_titles = self.current_project.get("meanings", [])
        dlg = BatchTitlesDialog(current_titles, parent=self)
        if dlg.exec():
            new_titles = dlg.result_titles
            self.current_project["meanings"] = new_titles
            ProjectManager.save_project(self.current_project)
            self.meta_updated.emit({"meanings": new_titles})
            self._refresh_titles_ui()
            self.gifs_imported.emit()
            QMessageBox.information(self, "标题填入成功", f"✔ 已成功更新并保存 {len(new_titles)} 个表情的标题！")

    def _on_quick_apply_all_text(self):
        """主界面直接一键为全部表情添加文字 (使用最近调好的排版)"""
        if not self.current_project:
            QMessageBox.warning(self, "提示", "请先在左侧选择一个工程！")
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
            QMessageBox.warning(self, "提示", "当前工程未找到 GIF 动图，请先上传 GIF 素材！")
            return

        gif_files = sorted([f for f in os.listdir(gifs_dir) if f.lower().endswith(".gif") and f[:2].isdigit()])
        if not gif_files:
            QMessageBox.warning(self, "提示", "未找到符合格式的 GIF 动图！")
            return

        meanings = self.current_project.get("meanings", [])
        params = GifEditorDialog.LAST_PARAMS

        preview_lines = []
        for i, gname in enumerate(gif_files[:8]):
            t = meanings[i] if i < len(meanings) else f"表情_{i+1:02d}"
            preview_lines.append(f"  #{i+1:02d}. {t}")
        if len(gif_files) > 8:
            preview_lines.append(f"  ... 等共 {len(gif_files)} 个表情")
        p_str = "\n".join(preview_lines)

        reply = QMessageBox.question(
            self, "一键为全部表情添加文字确认",
            f"确定按当前排版规范：\n\n"
            f"• 字体: {params['font_identifier']}\n"
            f"• 字号: {params['font_size']} pt | 位置 Y: {params['text_y']} px ({params['align']})\n"
            f"• 色彩: 文字 {params['text_color']} | 描边 {params['stroke_color']} ({params['stroke_width']}px)\n\n"
            f"一键为全部 {len(gif_files)} 个表情按照各自标题批量添加文字吗？\n\n"
            f"【即将添加文字的表情清单】：\n{p_str}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply != QMessageBox.Yes:
            return

        progress = QProgressDialog("正在批量添加文字...", "取消", 0, len(gif_files), self)
        progress.setWindowTitle("批量添加文字中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        erase_rect = (0, params["erase_top"], 240, params["erase_h"]) if params["enable_erase"] else None
        success_count = 0

        for idx, gname in enumerate(gif_files):
            if progress.wasCanceled():
                break
            g_path = os.path.join(gifs_dir, gname)
            txt = meanings[idx] if idx < len(meanings) else f"表情_{idx+1:02d}"
            progress.setLabelText(f"正在渲染 ({idx+1}/{len(gif_files)}): {gname} - {txt}")
            QApplication.processEvents()

            ok = GifTextEditor.process_gif(
                gif_path=g_path,
                out_gif_path=g_path,
                text=txt,
                font_identifier=params["font_identifier"],
                font_size=params["font_size"],
                text_color=params["text_color"],
                stroke_color=params["stroke_color"],
                stroke_width=params["stroke_width"],
                text_y=params["text_y"],
                align=params["align"],
                erase_rect=erase_rect
            )
            if ok:
                success_count += 1
            progress.setValue(idx + 1)

        progress.close()
        QMessageBox.information(
            self, "批量添加完成",
            f"🎉 成功为 {success_count}/{len(gif_files)} 个表情添加了艺术文字！\n"
            f"右侧拟真视口已同步实时刷新。"
        )
        self.gifs_imported.emit()

    def _commit_meta(self):
        if not self.current_project:
            return
        data = {
            "title": self.name_edit.text().strip(),
            "reward_text": self.reward_edit.text().strip(),
            "intro": self.intro_edit.toPlainText().strip()
        }
        self.meta_updated.emit(data)

    def _on_intro_changed(self):
        text = self.intro_edit.toPlainText()
        if len(text) > 100:
            self.intro_edit.setPlainText(text[:100])
        self._commit_meta()

    def _on_upload_gif_folder(self):
        """选择并上传已做好的 GIF 文件夹"""
        if not self.current_project:
            QMessageBox.warning(self, "提示", "请先在左侧选择一个工程！")
            return

        folder = QFileDialog.getExistingDirectory(
            self, "选择存放已做好 GIF 动图的文件夹", PathMemory.get_upload_dir()
        )
        if not folder:
            return

        PathMemory.set_upload_dir(folder)

        gif_files = sorted([f for f in os.listdir(folder) if f.lower().endswith(".gif")])
        if not gif_files:
            QMessageBox.warning(self, "未找到 GIF 文件", f"在所选文件夹中未找到任何 .gif 格式动图：\n{folder}")
            return

        p_dir = self.current_project["dir"]
        target_dir = os.path.join(p_dir, "gifs")
        os.makedirs(target_dir, exist_ok=True)

        new_meanings = list(self.current_project.get("meanings", []))
        while len(new_meanings) < len(gif_files):
            new_meanings.append(f"表情_{len(new_meanings)+1:02d}")

        copied_count = 0
        extracted_any = False
        for i, gname in enumerate(gif_files):
            src_p = os.path.join(folder, gname)
            idx, title = ProjectManager.extract_title_and_index_from_filename(gname, fallback_idx=i+1)
            new_name = f"{idx:02d}.gif"
            dst_p = os.path.join(target_dir, new_name)
            try:
                shutil.copyfile(src_p, dst_p)
                copied_count += 1
                if title:
                    while len(new_meanings) < idx:
                        new_meanings.append(f"表情_{len(new_meanings)+1:02d}")
                    new_meanings[idx - 1] = title
                    extracted_any = True
            except Exception as e:
                print(f"Error copying {src_p} to {dst_p}: {e}")

        if extracted_any or len(new_meanings) != len(self.current_project.get("meanings", [])):
            self.current_project["meanings"] = new_meanings
            ProjectManager.save_project(self.current_project)
            self.meta_updated.emit({"meanings": new_meanings})

        self.gif_upload_status_lbl.setText(f"✔ 已成功载入 {copied_count} 个 GIF 动图！(来自: {os.path.basename(folder)})")
        self.gif_upload_status_lbl.setStyleSheet("color: #059669; font-weight: bold; font-size: 12px;")

        self._refresh_titles_ui()
        self.gifs_imported.emit()

        reply = QMessageBox.question(
            self, "上传成功",
            f"🎉 成功上传并导入 {copied_count} 个 GIF 动图！\n\n"
            f"右侧拟真视口已同步实时动态播放。\n"
            f"是否立即打开【文字工坊】为这批表情添加文字？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.open_text_workshop_clicked.emit()

    def _on_upload_gif_files(self):
        """框选多选上传已做好的 GIF 文件"""
        if not self.current_project:
            QMessageBox.warning(self, "提示", "请先在左侧选择一个工程！")
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "多选已做好的 GIF 动图 (按住 Ctrl 或 Shift 可多选)",
            PathMemory.get_upload_dir(), "GIF 动图 (*.gif)"
        )
        if not files:
            return

        PathMemory.set_upload_dir(files[0])

        p_dir = self.current_project["dir"]
        target_dir = os.path.join(p_dir, "gifs")
        os.makedirs(target_dir, exist_ok=True)

        files = sorted(files)
        new_meanings = list(self.current_project.get("meanings", []))
        while len(new_meanings) < len(files):
            new_meanings.append(f"表情_{len(new_meanings)+1:02d}")

        copied_count = 0
        extracted_any = False
        for i, src_p in enumerate(files):
            gname = os.path.basename(src_p)
            idx, title = ProjectManager.extract_title_and_index_from_filename(gname, fallback_idx=i+1)
            new_name = f"{idx:02d}.gif"
            dst_p = os.path.join(target_dir, new_name)
            try:
                shutil.copyfile(src_p, dst_p)
                copied_count += 1
                if title:
                    while len(new_meanings) < idx:
                        new_meanings.append(f"表情_{len(new_meanings)+1:02d}")
                    new_meanings[idx - 1] = title
                    extracted_any = True
            except Exception as e:
                print(f"Error copying {src_p} to {dst_p}: {e}")

        if extracted_any or len(new_meanings) != len(self.current_project.get("meanings", [])):
            self.current_project["meanings"] = new_meanings
            ProjectManager.save_project(self.current_project)
            self.meta_updated.emit({"meanings": new_meanings})

        self.gif_upload_status_lbl.setText(f"✔ 已成功载入 {copied_count} 个 GIF 动图！")
        self.gif_upload_status_lbl.setStyleSheet("color: #059669; font-weight: bold; font-size: 12px;")

        self._refresh_titles_ui()
        self.gifs_imported.emit()

        reply = QMessageBox.question(
            self, "上传成功",
            f"🎉 成功上传并导入 {copied_count} 个 GIF 动图！\n\n"
            f"右侧拟真视口已同步实时动态播放。\n"
            f"是否立即打开【文字工坊】为这批表情添加文字？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            self.open_text_workshop_clicked.emit()

    def _on_click_open_workshop(self):
        """点击打开文字工坊"""
        self.open_text_workshop_clicked.emit()

    def _open_gifs_folder(self):
        """打开当前工程的 gifs 目录"""
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        gifs_dir = os.path.join(p_dir, "gifs")
        os.makedirs(gifs_dir, exist_ok=True)
        subprocess.run(["explorer", gifs_dir])

    def _on_choose_grid_image(self):
        if not self.current_project:
            return
        default_dir = PathMemory.get_upload_dir(fallback=self.current_project.get("dir", ""))
        path, _ = QFileDialog.getOpenFileName(self, "选择 15 宫格原图", default_dir, "图片文件 (*.png *.jpg *.jpeg)")
        if path:
            PathMemory.set_upload_dir(path)
            self.selected_grid_img = path
            self.safe_img_status.setText(f"已选中: {os.path.basename(path)}")

    def _on_gen_safe_image(self):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        img_path = getattr(self, "selected_grid_img", None)
        if not img_path:
            candidates = [os.path.join(p_dir, "15宫格.png"), os.path.join(p_dir, "15宫格.jpg")]
            img_path = next((f for f in candidates if os.path.exists(f)), None)

        if not img_path or not os.path.exists(img_path):
            QMessageBox.warning(self, "提示", "请先选择或在工程目录中放置 15 宫格图片！")
            return

        self.generate_safe_image_clicked.emit(img_path)

    def _on_choose_video(self):
        if not self.current_project:
            return
        default_dir = PathMemory.get_upload_dir(fallback=self.current_project.get("dir", ""))
        path, _ = QFileDialog.getOpenFileName(self, "选择 16:9 动态视频", default_dir, "视频文件 (*.mp4 *.mov *.webm)")
        if path:
            PathMemory.set_upload_dir(path)
            self.selected_video = path
            self.slice_status_lbl.setText(f"已选中: {os.path.basename(path)}")

    def _on_start_slice(self):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        vid_path = getattr(self, "selected_video", None)
        if not vid_path:
            candidates = [os.path.join(p_dir, "15宫格视频.mp4"), os.path.join(p_dir, "视频.mp4")]
            vid_path = next((f for f in candidates if os.path.exists(f)), None)

        if not vid_path or not os.path.exists(vid_path):
            QMessageBox.warning(self, "提示", "请先选择或在工程目录中放置 16:9 动态视频 (如 15宫格视频.mp4)！")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        make_trans = self.trans_check.isChecked()
        scale_pct = self.scale_spin.value()
        self.start_slice_clicked.emit(vid_path, make_trans, scale_pct)

    def _on_make_transparent_clicked(self):
        if not self.current_project:
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.slice_status_lbl.setText("正在执行智能边缘泛洪白底透明化...")
        scale_pct = self.scale_spin.value()
        self.make_transparent_clicked.emit(scale_pct)

    def update_slice_progress(self, cur, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(cur)
        self.slice_status_lbl.setText(f"处理进度: {cur}/{total} 个微信 GIF...")

    def on_slice_finished(self, success, msg):
        self.progress_bar.setVisible(False)
        if success:
            self.slice_status_lbl.setText(f"🎉 {msg}")
            self._refresh_upload_status()
            QMessageBox.information(self, "完成", msg)
        else:
            self.slice_status_lbl.setText(f"❌ 处理失败: {msg}")
            QMessageBox.critical(self, "错误", f"处理失败: {msg}")

    def _open_project_folder(self):
        if self.current_project and os.path.exists(self.current_project["dir"]):
            subprocess.run(["explorer", self.current_project["dir"]])
