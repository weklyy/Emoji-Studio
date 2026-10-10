import os
import re
import shutil
import subprocess
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGridLayout, QScrollArea, QFrame, QMessageBox, QApplication, QComboBox,
    QFileDialog, QMenu, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QMovie, QPixmap, QAction
from domain.specs import WeChatSpecs
from domain.path_memory import PathMemory
from domain.project_manager import ProjectManager
from domain.compressor import ImageCompressor
from view.gif_editor_dialog import GifEditorDialog

class ClickableCard(QFrame):
    clicked = Signal(str, str, int) # gif_path, default_text, index
    download_requested = Signal(str, str) # gif_path, default_text
    compress_requested = Signal(str) # gif_path
    selection_changed = Signal(bool)

    def __init__(self, gif_path, default_text, index, parent=None):
        super().__init__(parent)
        self.gif_path = gif_path
        self.default_text = default_text
        self.index = index
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("EmojiCard")
        self._update_style(False)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _update_style(self, checked: bool):
        if checked:
            self.setStyleSheet("""
                QFrame#EmojiCard {
                    background: #F0FDF4;
                    border: 2px solid #07C160;
                    border-radius: 6px;
                    padding: 2px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame#EmojiCard {
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                    padding: 2px;
                }
                QFrame#EmojiCard:hover {
                    border: 1.5px solid #07C160;
                    background: #F0FDF4;
                }
            """)

    def is_checked(self) -> bool:
        return hasattr(self, 'chk') and self.chk.isChecked()

    def set_checked(self, checked: bool):
        if hasattr(self, 'chk'):
            self.chk.blockSignals(True)
            self.chk.setChecked(checked)
            self.chk.blockSignals(False)
            self._update_style(checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.gif_path, self.default_text, self.index)
        super().mousePressEvent(event)

    def _show_context_menu(self, pos: QPoint):
        menu = QMenu(self)
        comp_act = QAction("🗜️ 压缩此表情 (确保 ≤480KB)...", self)
        comp_act.triggered.connect(lambda: self.compress_requested.emit(self.gif_path))
        menu.addAction(comp_act)
        down_act = QAction("💾 单独下载此表情 (另存为)...", self)
        down_act.triggered.connect(lambda: self.download_requested.emit(self.gif_path, self.default_text))
        menu.addAction(down_act)
        menu.exec(self.mapToGlobal(pos))


class WeChatPreviewPanel(QWidget):
    export_requested = Signal(str)
    copy_f12_requested = Signal()
    status_updated = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(320)
        self.setMaximumWidth(600)
        self.current_project = None
        self.movies = []
        self.cards = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        title_box = QFrame()
        title_box.setStyleSheet("background-color: #07C160; border-radius: 6px; padding: 6px;")
        t_layout = QHBoxLayout(title_box)
        t_layout.setContentsMargins(8, 4, 8, 4)
        wechat_logo = QLabel("📱 微信表情开放平台 • 1:1 产物拟真视口")
        wechat_logo.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px; background: transparent;")
        t_layout.addWidget(wechat_logo)
        layout.addWidget(title_box)

        status_card = QFrame()
        status_card.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px;")
        s_layout = QHBoxLayout(status_card)
        s_layout.setContentsMargins(6, 4, 6, 4)
        
        s_layout.addWidget(QLabel("审核状态:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["🟡 草稿", "🟢 已切片", "🔵 已提审", "⭐ 已上架"])
        self.status_combo.currentIndexChanged.connect(self._on_status_changed)
        s_layout.addWidget(self.status_combo)

        self.mark_uploaded_btn = QPushButton("标记今日已提审")
        self.mark_uploaded_btn.setToolTip("记录今天上传微信开放平台")
        self.mark_uploaded_btn.clicked.connect(self._on_mark_today_uploaded)
        s_layout.addWidget(self.mark_uploaded_btn)
        layout.addWidget(status_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: #FFFFFF; border-radius: 8px;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(8, 8, 8, 8)
        c_layout.setSpacing(10)

        banner_box = QFrame()
        banner_box.setStyleSheet("background: #F1F5F9; border: 1px dashed #CBD5E1; border-radius: 6px;")
        b_layout = QVBoxLayout(banner_box)
        b_layout.setContentsMargins(4, 4, 4, 4)
        b_lbl_title = QLabel("详情页横幅 750×400 (严禁文字)")
        b_lbl_title.setStyleSheet("font-size: 11px; color: #64748B; background: transparent;")
        b_layout.addWidget(b_lbl_title)
        
        self.banner_img_lbl = QLabel()
        self.banner_img_lbl.setFixedHeight(120)
        self.banner_img_lbl.setAlignment(Qt.AlignCenter)
        self.banner_img_lbl.setStyleSheet("background: #E2E8F0; border-radius: 4px;")
        b_layout.addWidget(self.banner_img_lbl)
        c_layout.addWidget(banner_box)

        hint_lbl = QLabel("💡 提示：点击表情卡片可【精修与批量同步文字】，勾选可【多选批量下载】！")
        hint_lbl.setStyleSheet("font-size: 11px; color: #D97706; font-weight: bold; background: #FEF3C7; padding: 4px; border-radius: 4px;")
        hint_lbl.setWordWrap(True)
        c_layout.addWidget(hint_lbl)

        # 多选下载控制工具条
        sel_bar = QFrame()
        sel_bar.setStyleSheet("background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 6px;")
        sb_layout = QHBoxLayout(sel_bar)
        sb_layout.setContentsMargins(6, 4, 6, 4)
        sb_layout.setSpacing(6)

        self.sel_all_btn = QPushButton("☑ 全选")
        self.sel_all_btn.setFixedHeight(26)
        self.sel_all_btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        self.sel_all_btn.clicked.connect(self._on_select_all)
        sb_layout.addWidget(self.sel_all_btn)

        self.desel_all_btn = QPushButton("☐ 全不选")
        self.desel_all_btn.setFixedHeight(26)
        self.desel_all_btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        self.desel_all_btn.clicked.connect(self._on_deselect_all)
        sb_layout.addWidget(self.desel_all_btn)

        self.sel_count_lbl = QLabel("已选 0/15")
        self.sel_count_lbl.setStyleSheet("font-size: 11px; color: #475569; font-weight: bold;")
        sb_layout.addWidget(self.sel_count_lbl)

        sb_layout.addStretch(1)

        self.batch_compress_btn = QPushButton("🗜️ 压缩所选 (0)")
        self.batch_compress_btn.setFixedHeight(26)
        self.batch_compress_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                color: #B45309;
                background-color: #FEF3C7;
                border: 1px solid #F59E0B;
                border-radius: 4px;
                padding: 2px 6px;
            }
            QPushButton:hover {
                background-color: #FDE68A;
            }
            QPushButton:disabled {
                background-color: #F1F5F9;
                color: #94A3B8;
                border: 1px solid #CBD5E1;
            }
        """)
        self.batch_compress_btn.setEnabled(False)
        self.batch_compress_btn.clicked.connect(self._on_batch_compress_selected)
        sb_layout.addWidget(self.batch_compress_btn)

        self.batch_down_btn = QPushButton("📥 批量下载所选 (0)")
        self.batch_down_btn.setObjectName("PrimaryBtn")
        self.batch_down_btn.setFixedHeight(26)
        self.batch_down_btn.setStyleSheet("font-size: 11px; padding: 2px 8px;")
        self.batch_down_btn.setEnabled(False)
        self.batch_down_btn.clicked.connect(self._on_batch_download)
        sb_layout.addWidget(self.batch_down_btn)

        c_layout.addWidget(sel_bar)

        title_row = QHBoxLayout()
        grid_title = QLabel("15 个表情 GIF (微缩视口 • 支持自由添加文字)")
        grid_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #334155;")
        title_row.addWidget(grid_title)
        title_row.addStretch(1)

        self.edit_text_all_btn = QPushButton("✏️ 手动添加与排版文字...")
        self.edit_text_all_btn.setFixedHeight(26)
        self.edit_text_all_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                color: #0F172A;
                background-color: #FEF3C7;
                border: 1px solid #F59E0B;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QPushButton:hover {
                background-color: #FDE68A;
            }
        """)
        self.edit_text_all_btn.setToolTip("打开文字工坊：为表情添加或修改艺术字，字体/字号/色彩/描边均可自由定制")
        self.edit_text_all_btn.clicked.connect(self._on_open_text_workshop)
        title_row.addWidget(self.edit_text_all_btn)
        c_layout.addLayout(title_row)

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(6)
        c_layout.addLayout(self.grid_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        action_box = QVBoxLayout()
        action_box.setSpacing(8)

        self.copy_f12_btn = QPushButton("⚡ 一键复制 F12 自动填表脚本 (全页面秒填)")
        self.copy_f12_btn.setObjectName("F12Btn")
        self.copy_f12_btn.setMinimumHeight(38)
        self.copy_f12_btn.clicked.connect(self._on_copy_f12)
        action_box.addWidget(self.copy_f12_btn)

        # 可选打包目标文件夹条 (自选目标文件夹，自动记住)
        target_bar = QHBoxLayout()
        target_bar.setContentsMargins(0, 0, 0, 0)
        target_bar.setSpacing(4)

        target_lbl = QLabel("📁 导出目录:")
        target_lbl.setStyleSheet("font-size: 11px; color: #475569; font-weight: bold;")
        target_bar.addWidget(target_lbl)

        self.target_dir_edit = QLineEdit()
        self.target_dir_edit.setPlaceholderText("选择保存的目标文件夹...")
        self.target_dir_edit.setReadOnly(True)
        self.target_dir_edit.setStyleSheet("""
            QLineEdit {
                font-size: 10px;
                color: #334155;
                background: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px 4px;
            }
        """)
        target_bar.addWidget(self.target_dir_edit, stretch=1)

        self.choose_dir_btn = QPushButton("📂 更改...")
        self.choose_dir_btn.setFixedHeight(24)
        self.choose_dir_btn.setStyleSheet("""
            QPushButton {
                font-size: 10px;
                font-weight: bold;
                padding: 2px 8px;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                background: #FFFFFF;
                color: #334155;
            }
            QPushButton:hover {
                background: #F1F5F9;
                border-color: #07C160;
                color: #07C160;
            }
        """)
        self.choose_dir_btn.setToolTip("选择自定义打包保存的目标文件夹 (下次自动记住)")
        self.choose_dir_btn.clicked.connect(self._on_change_target_dir)
        target_bar.addWidget(self.choose_dir_btn)

        action_box.addLayout(target_bar)

        self.export_pkg_btn = QPushButton("🚀 一键打包微信提审全套物料包")
        self.export_pkg_btn.setObjectName("PrimaryBtn")
        self.export_pkg_btn.setMinimumHeight(40)
        self.export_pkg_btn.clicked.connect(self._on_export_package)
        action_box.addWidget(self.export_pkg_btn)

        layout.addLayout(action_box)

    def _on_open_text_workshop(self):
        """点击顶部按钮打开文字工坊"""
        if not self.cards:
            QMessageBox.information(self, "提示", "尚未切片或加载表情，请先选择视频切片或加载工程！")
            return
        target_idx = 0
        for idx, c in enumerate(self.cards):
            if c.is_checked():
                target_idx = idx
                break
        target_card = self.cards[target_idx]
        self._on_card_clicked(target_card.gif_path, target_card.default_text, target_idx)

    def load_project(self, project: dict):
        self.current_project = project
        status = project.get("status", "draft")
        status_idx_map = {"draft": 0, "sliced": 1, "submitted": 2, "approved": 3}
        self.status_combo.blockSignals(True)
        self.status_combo.setCurrentIndex(status_idx_map.get(status, 0))
        self.status_combo.blockSignals(False)

        if hasattr(self, "target_dir_edit"):
            p_dir = project.get("dir", "")
            d_dir = PathMemory.get_download_dir(fallback=p_dir)
            self.target_dir_edit.setText(d_dir)
            self.target_dir_edit.setToolTip(d_dir)

        self._refresh_banner()
        self._refresh_gifs()

    def release_movies(self):
        for m in self.movies:
            m.stop()
        self.movies.clear()
        self.cards.clear()

        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _refresh_banner(self):
        if not self.current_project:
            return
        p_dir = self.current_project["dir"]
        banner_candidates = [
            os.path.join(p_dir, "横幅.png"), os.path.join(p_dir, "横幅.jpg"),
            os.path.join(p_dir, "banner.png"), os.path.join(p_dir, "banner.jpg")
        ]
        b_src = next((f for f in banner_candidates if os.path.exists(f)), None)
        if b_src:
            pix = QPixmap(b_src)
            scaled = pix.scaled(340, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.banner_img_lbl.setPixmap(scaled)
        else:
            self.banner_img_lbl.setText("暂无横幅 (打包时自动生成规范插画)")

    def _refresh_gifs(self):
        self.release_movies()

        if not self.current_project:
            return

        p_dir = self.current_project["dir"]
        gifs_dir = os.path.join(p_dir, "gifs")

        # 优先在工程目录内递归查找包含 >=8 个表情的目录
        if not os.path.exists(gifs_dir) or not [f for f in os.listdir(gifs_dir) if f.lower().endswith(".gif") and f[:2].isdigit()]:
            found_dir = None
            for root, dirs, files in os.walk(p_dir):
                gifs = [f for f in files if f.lower().endswith(".gif") and f[:2].isdigit()]
                if len(gifs) >= 8:
                    found_dir = root
                    if "01_表情主图" in root or "gifs" in root:
                        break
            if found_dir:
                gifs_dir = found_dir

        if not os.path.exists(gifs_dir):
            tip = QLabel("尚未切片，切片后在此实时动态循环播放")
            tip.setStyleSheet("color: #94A3B8; font-size: 11px;")
            self.grid_layout.addWidget(tip, 0, 0, 1, 3)
            self._update_selection_state()
            return

        gif_files = sorted([f for f in os.listdir(gifs_dir) if f.lower().endswith(".gif") and f[:2].isdigit()])
        if not gif_files:
            tip = QLabel("尚未切片，切片后在此实时动态循环播放")
            tip.setStyleSheet("color: #94A3B8; font-size: 11px;")
            self.grid_layout.addWidget(tip, 0, 0, 1, 3)
            self._update_selection_state()
            return

        meanings = list(self.current_project.get("meanings", []))
        cols = 3
        meanings_changed = False

        for i, gname in enumerate(gif_files):
            g_path = os.path.join(gifs_dir, gname)
            size_kb = os.path.getsize(g_path) / 1024.0

            # 智能提取文件名中的标题
            _, fn_title = ProjectManager.extract_title_and_index_from_filename(gname, fallback_idx=i+1)

            if i < len(meanings) and meanings[i] and not meanings[i].startswith("表情_"):
                meaning_text = meanings[i]
            elif fn_title:
                meaning_text = fn_title
                while len(meanings) <= i:
                    meanings.append(f"表情_{len(meanings)+1:02d}")
                meanings[i] = fn_title
                meanings_changed = True
            else:
                meaning_text = meanings[i] if i < len(meanings) else f"表情_{i+1:02d}"

            card = ClickableCard(g_path, meaning_text, i)
            card.clicked.connect(self._on_card_clicked)
            card.download_requested.connect(self._on_download_requested)
            card.compress_requested.connect(self._on_single_compress)
            self.cards.append(card)

            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(3, 3, 3, 3)
            c_layout.setSpacing(2)

            # 顶部勾选框与序号栏
            top_bar = QHBoxLayout()
            top_bar.setContentsMargins(2, 0, 2, 0)
            
            card.chk = QCheckBox()
            card.chk.setToolTip("勾选此表情以批量下载或定向压缩")
            card.chk.stateChanged.connect(lambda state, c=card: self._on_card_checked_changed(c))
            top_bar.addWidget(card.chk)

            tag_lbl = QLabel(f"#{i+1:02d}")
            tag_lbl.setStyleSheet("font-size: 9px; color: #64748B; font-weight: bold; background: transparent;")
            top_bar.addWidget(tag_lbl)
            top_bar.addStretch(1)
            c_layout.addLayout(top_bar)

            # GIF 动态图
            gif_lbl = QLabel()
            gif_lbl.setFixedSize(100, 100)
            gif_lbl.setAlignment(Qt.AlignCenter)
            gif_lbl.setStyleSheet("background: #FFFFFF; border-radius: 4px;")

            movie = QMovie(g_path)
            movie.setScaledSize(gif_lbl.size())
            gif_lbl.setMovie(movie)
            movie.start()
            self.movies.append(movie)
            c_layout.addWidget(gif_lbl)

            # 可直接原地编辑标题的文本框 (所见即所得，失焦自动保存)
            txt_edit = QLineEdit(meaning_text)
            txt_edit.setAlignment(Qt.AlignCenter)
            txt_edit.setToolTip("点击可直接修改此表情标题 (失焦自动保存)")
            txt_edit.setStyleSheet("""
                QLineEdit {
                    font-size: 10px;
                    font-weight: bold;
                    color: #1E293B;
                    background: transparent;
                    border: 1px solid transparent;
                    border-radius: 3px;
                    padding: 1px;
                }
                QLineEdit:hover {
                    background: #F1F5F9;
                    border: 1px solid #CBD5E1;
                }
                QLineEdit:focus {
                    background: #FFFFFF;
                    border: 1px solid #07C160;
                }
            """)
            txt_edit.editingFinished.connect(lambda c=card, edit=txt_edit, idx=i: self._on_card_title_edited(c, edit.text(), idx))
            card.txt_edit = txt_edit
            c_layout.addWidget(txt_edit)

            # 状态与单独压缩、单独下载按钮行
            bottom_row = QHBoxLayout()
            bottom_row.setContentsMargins(2, 0, 2, 0)
            bottom_row.setSpacing(2)

            badge_color = "#07C160" if size_kb <= WeChatSpecs.MAIN_GIF_MAX_KB else "#EF4444"
            badge = QLabel(f"🟢 {size_kb:.0f}KB" if size_kb <= WeChatSpecs.MAIN_GIF_MAX_KB else f"🔴 {size_kb:.0f}KB")
            badge.setStyleSheet(f"font-size: 9px; color: {badge_color}; background: transparent;")
            bottom_row.addWidget(badge)
            bottom_row.addStretch(1)

            compress_btn = QPushButton("🗜️")
            compress_btn.setFixedSize(22, 18)
            compress_btn.setToolTip("定向压缩此表情 (确保 ≤480KB)")
            compress_btn.setStyleSheet("""
                QPushButton {
                    font-size: 10px;
                    padding: 0px;
                    border: 1px solid #F59E0B;
                    border-radius: 3px;
                    background: #FEF3C7;
                }
                QPushButton:hover {
                    background: #F59E0B;
                    color: #FFFFFF;
                }
            """)
            compress_btn.clicked.connect(lambda checked=False, p=g_path: self._on_single_compress(p))
            bottom_row.addWidget(compress_btn)

            down_btn = QPushButton("💾")
            down_btn.setFixedSize(22, 18)
            down_btn.setToolTip("单独下载此表情另存为...")
            down_btn.setStyleSheet("""
                QPushButton {
                    font-size: 10px;
                    padding: 0px;
                    border: 1px solid #CBD5E1;
                    border-radius: 3px;
                    background: #FFFFFF;
                }
                QPushButton:hover {
                    background: #07C160;
                    color: #FFFFFF;
                }
            """)
            down_btn.clicked.connect(lambda checked=False, p=g_path, t=meaning_text: self._on_download_requested(p, t))
            bottom_row.addWidget(down_btn)

            c_layout.addLayout(bottom_row)

            r = i // cols
            c = i % cols
            self.grid_layout.addWidget(card, r, c)

        if meanings_changed and self.current_project:
            self.current_project["meanings"] = meanings
            self.status_updated.emit({"meanings": meanings})

        self._update_selection_state()

    def _on_single_compress(self, gif_path: str):
        """单独对单张表情执行智能极限压缩"""
        if not os.path.exists(gif_path):
            return
        orig_kb = os.path.getsize(gif_path) / 1024.0
        self.release_movies()
        ok, new_kb, msg = ImageCompressor.compress_gif(gif_path, gif_path, max_kb=480)
        self._refresh_gifs()
        if ok and new_kb <= 480:
            QMessageBox.information(
                self, "压缩成功",
                f"表情已成功压缩至微信合规体积！\n原体积: {orig_kb:.1f} KB ➔ 优化后: {new_kb:.1f} KB (≤480KB 微信安全红线)"
            )
        else:
            QMessageBox.information(
                self, "压缩完成",
                f"压缩处理完成：\n原体积: {orig_kb:.1f} KB ➔ 当前体积: {new_kb:.1f} KB\n({msg})"
            )

    def _on_batch_compress_selected(self):
        """定向批量压缩用户勾选的表情"""
        selected_cards = [c for c in self.cards if c.is_checked()]
        if not selected_cards:
            QMessageBox.information(self, "提示", "请先在上方勾选需要压缩的表情！")
            return

        self.release_movies()
        total = len(selected_cards)
        success = 0
        details = []
        for c in selected_cards:
            if os.path.exists(c.gif_path):
                orig_kb = os.path.getsize(c.gif_path) / 1024.0
                ok, new_kb, _ = ImageCompressor.compress_gif(c.gif_path, c.gif_path, max_kb=480)
                if ok and new_kb <= 480:
                    success += 1
                    details.append(f"#{c.index+1:02d}: {orig_kb:.0f}KB ➔ {new_kb:.0f}KB")

        self._refresh_gifs()
        detail_msg = ("\n\n部分优化明细:\n" + "\n".join(details[:6])) if details else ""
        QMessageBox.information(
            self, "批量压缩完成",
            f"🎉 批量智能压缩完成！\n"
            f"共处理 {total} 个表情，成功压缩至微信安全线 (≤480KB): {success} 个。{detail_msg}"
        )

    def _on_card_checked_changed(self, card: ClickableCard):
        card._update_style(card.is_checked())
        self._update_selection_state()

    def _on_select_all(self):
        for c in self.cards:
            c.set_checked(True)
        self._update_selection_state()

    def _on_deselect_all(self):
        for c in self.cards:
            c.set_checked(False)
        self._update_selection_state()

    def _update_selection_state(self):
        total = len(self.cards)
        count = sum(1 for c in self.cards if c.is_checked())
        self.sel_count_lbl.setText(f"已选 {count}/{total}")
        self.batch_compress_btn.setText(f"🗜️ 压缩所选 ({count})")
        self.batch_compress_btn.setEnabled(count > 0)
        self.batch_down_btn.setText(f"📥 批量下载所选 ({count})")
        self.batch_down_btn.setEnabled(count > 0)

    def _on_batch_download(self):
        """批量多选下载表情"""
        selected_cards = [c for c in self.cards if c.is_checked()]
        if not selected_cards:
            QMessageBox.information(self, "提示", "请先在上方勾选需要下载的表情！")
            return

        default_dir = PathMemory.get_download_dir(fallback=self.current_project.get("dir", "") if self.current_project else "")
        save_dir = QFileDialog.getExistingDirectory(self, "选择保存所选表情的目标文件夹", default_dir)
        if not save_dir:
            return

        PathMemory.set_download_dir(save_dir)

        success_count = 0
        for c in selected_cards:
            if not os.path.exists(c.gif_path):
                continue
            safe_txt = re.sub(r'[\\/*?:"<>|]', "", c.default_text).strip()
            prefix = f"{c.index+1:02d}_"
            fname = f"{prefix}{safe_txt}.gif" if safe_txt else os.path.basename(c.gif_path)
            dst_path = os.path.join(save_dir, fname)
            try:
                shutil.copyfile(c.gif_path, dst_path)
                success_count += 1
            except Exception as e:
                print(f"Error copying {c.gif_path} to {dst_path}: {e}")

        QMessageBox.information(
            self, "批量下载成功",
            f"已成功将选中的 {success_count} 个表情保存至：\n{save_dir}"
        )
        try:
            os.startfile(save_dir)
        except Exception:
            pass

    def _on_card_title_edited(self, card, new_txt, idx):
        new_txt = new_txt.strip()
        card.default_text = new_txt
        if not self.current_project:
            return
        meanings = list(self.current_project.get("meanings", []))
        while len(meanings) <= idx:
            meanings.append(f"表情_{len(meanings)+1:02d}")
        meanings[idx] = new_txt
        self.current_project["meanings"] = meanings
        self.status_updated.emit({"meanings": meanings})

    def _on_titles_updated_from_dialog(self, new_titles):
        if self.current_project:
            self.current_project["meanings"] = new_titles
            self.status_updated.emit({"meanings": new_titles})

    def _on_card_clicked(self, gif_path, default_text, index):
        self.release_movies()
        all_items = [(c.gif_path, c.default_text) for c in self.cards]
        dialog = GifEditorDialog(gif_path, default_text, all_items, current_index=index, parent=self)
        dialog.titles_updated.connect(self._on_titles_updated_from_dialog)
        dialog.applied.connect(lambda p: self._refresh_gifs())
        dialog.exec()
        self._refresh_gifs()

    def _on_download_requested(self, gif_path, default_text):
        """单独下载另存为"""
        fname = f"{default_text}.gif" if default_text else os.path.basename(gif_path)
        default_dir = PathMemory.get_download_dir(fallback=self.current_project.get("dir", "") if self.current_project else "")
        default_target = os.path.join(default_dir, fname)
        save_path, _ = QFileDialog.getSaveFileName(self, "单独下载表情 GIF", default_target, "GIF 动图 (*.gif)")
        if save_path:
            PathMemory.set_download_dir(save_path)
            shutil.copyfile(gif_path, save_path)
            QMessageBox.information(self, "下载成功", f"表情已成功保存至：\n{save_path}")

    def _on_copy_f12(self):
        self.copy_f12_requested.emit()

    def _on_change_target_dir(self):
        """预设打包物料的导出目标文件夹"""
        p_dir = self.current_project.get("dir", "") if self.current_project else ""
        current_target = self.target_dir_edit.text().strip() if hasattr(self, "target_dir_edit") else ""
        default_dir = current_target if (current_target and os.path.isdir(current_target)) else PathMemory.get_download_dir(fallback=p_dir)

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "选择【微信表情提审全套物料包】的目标保存文件夹",
            default_dir
        )
        if not selected_dir:
            return

        PathMemory.set_download_dir(selected_dir)
        if hasattr(self, "target_dir_edit"):
            self.target_dir_edit.setText(selected_dir)
            self.target_dir_edit.setToolTip(selected_dir)

    def _on_export_package(self):
        """一键打包微信提审全套物料包 (支持自选目标文件夹，自动记忆)"""
        if not self.current_project:
            QMessageBox.information(self, "提示", "尚未选择工程，请先打开或创建一个表情工程！")
            return

        p_name = self.current_project.get("name", "微信表情")
        p_dir = self.current_project.get("dir", "")
        current_target = self.target_dir_edit.text().strip() if hasattr(self, "target_dir_edit") else ""
        default_dir = current_target if (current_target and os.path.isdir(current_target)) else PathMemory.get_download_dir(fallback=p_dir)

        # 弹出文件夹选择框，允许用户自由选择或确认目标文件夹
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "选择【微信表情提审全套物料包】的目标保存文件夹",
            default_dir
        )
        if not selected_dir:
            return  # 用户取消选择

        PathMemory.set_download_dir(selected_dir)
        if hasattr(self, "target_dir_edit"):
            self.target_dir_edit.setText(selected_dir)
            self.target_dir_edit.setToolTip(selected_dir)

        # 智能子目录组织：若选择的目录名称未包含提交包或物料包，则建立专属子文件夹，确保干净整洁
        bname = os.path.basename(selected_dir)
        if bname.endswith("微信表情提交包") or bname.endswith("物料包"):
            export_path = selected_dir
        else:
            export_path = os.path.join(selected_dir, f"{p_name}_微信表情提交包")

        self.export_requested.emit(export_path)

    def _on_status_changed(self, idx):
        if not self.current_project:
            return
        status_map = {0: "draft", 1: "sliced", 2: "submitted", 3: "approved"}
        new_status = status_map.get(idx, "draft")
        self.status_updated.emit({"status": new_status})

    def _on_mark_today_uploaded(self):
        if not self.current_project:
            return
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.status_combo.setCurrentIndex(2)
        self.status_updated.emit({
            "status": "submitted",
            "upload_date": today_str
        })
        QMessageBox.information(self, "记录成功", f"已成功将本工程标记为【已提审】，上传日期: {today_str}！")

