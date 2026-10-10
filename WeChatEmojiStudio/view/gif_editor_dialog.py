from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSlider, QGroupBox, QMessageBox, QFrame, QFileDialog,
    QComboBox, QProgressDialog, QApplication, QColorDialog, QCheckBox,
    QButtonGroup, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor, QPen
from PIL import Image, ImageDraw, ImageFont
import os
import shutil
from domain.gif_text_editor import GifTextEditor
from domain.compressor import ImageCompressor
from domain.path_memory import PathMemory
from view.batch_titles_dialog import BatchTitlesDialog

class ColorChipButton(QPushButton):
    """
    语义化实体色彩样本卡片 (所见即所得规范)
    未选中时带有 1px 细微灰边，选中时带有 2px 微信绿轮廓光环，内芯色彩 100% 忠于产物
    """
    def __init__(self, color_hex: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setFixedSize(24, 24)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip or color_hex)
        self._update_style(False)

    def _update_style(self, checked: bool):
        border = "2px solid #07C160" if checked else "1px solid #CBD5E1"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.color_hex};
                border: {border};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border: 2px solid #38BDF8;
            }}
        """)

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._update_style(checked)


class GifPreviewCanvas(QLabel):
    """
    240x240 所见即所得交互预览画布
    支持字体、字号、文字颜色、描边粗细与颜色、对齐与位置、以及可选抹除框的 1:1 实时物理渲染
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(240, 240)
        self.setStyleSheet("border: 1px solid #CBD5E1; border-radius: 6px; background-color: #FFFFFF;")
        self.setAlignment(Qt.AlignCenter)
        self.base_pil_frame = None

        self.text = ""
        self.font_identifier = "OPPOSans-H.ttf"
        self.font_size = 24
        self.text_color = (225, 29, 72)
        self.stroke_color = (255, 255, 255)
        self.stroke_width = 3
        self.text_y = 10
        self.align = "center"

        self.enable_erase = False
        self.erase_top = 0
        self.erase_h = 36

    def set_base_frame(self, pil_frame: Image.Image):
        self.base_pil_frame = pil_frame.convert("RGBA")
        self.update_preview()

    def update_params(
        self, text, font_identifier, font_size, text_color,
        stroke_color, stroke_width, text_y, align,
        enable_erase, erase_top, erase_h
    ):
        self.text = text
        self.font_identifier = font_identifier
        self.font_size = font_size
        self.text_color = text_color
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.text_y = text_y
        self.align = align
        self.enable_erase = enable_erase
        self.erase_top = erase_top
        self.erase_h = erase_h
        self.update_preview()

    def update_preview(self):
        if not self.base_pil_frame:
            return

        frame = self.base_pil_frame.copy()
        draw = ImageDraw.Draw(frame)
        w, h = frame.size

        # 1. 可选抹除区域填充
        if self.enable_erase and self.erase_h > 0:
            draw.rectangle((0, self.erase_top, w, self.erase_top + self.erase_h), fill=(240, 240, 240, 255))

        # 2. 绘制新文字 (带描边与对齐)
        if self.text.strip():
            font = GifTextEditor.get_font(self.font_identifier, self.font_size)
            bbox = draw.textbbox((0, 0), self.text, font=font, stroke_width=self.stroke_width)
            tw = bbox[2] - bbox[0]

            if self.align == "left":
                tx = 8
            elif self.align == "right":
                tx = max(4, w - tw - 8)
            else:
                tx = max(4, (w - tw) // 2)

            t_col = GifTextEditor.parse_color(self.text_color)
            s_col = GifTextEditor.parse_color(self.stroke_color)

            if self.stroke_width > 0:
                draw.text(
                    (tx, self.text_y), self.text, font=font,
                    fill=t_col, stroke_width=self.stroke_width, stroke_fill=s_col
                )
            else:
                draw.text((tx, self.text_y), self.text, font=font, fill=t_col)

        data = frame.tobytes("raw", "RGBA")
        qim = QImage(data, w, h, QImage.Format_RGBA8888)
        pix = QPixmap.fromImage(qim)

        # 抹除状态下绘制红色辅助虚线框
        if self.enable_erase and self.erase_h > 0:
            painter = QPainter(pix)
            painter.setPen(QPen(QColor(239, 68, 68, 180), 1, Qt.DashLine))
            painter.drawRect(0, self.erase_top, w - 1, self.erase_h)
            painter.end()

        self.setPixmap(pix)


class GifEditorDialog(QDialog):
    """
    GIF 表情文字工坊：自由手动添加与精修文字
    支持字体、字号、色彩、描边、对齐与位置自由配置，以及一键批量同步与单独下载
    """
    applied = Signal(str)
    titles_updated = Signal(list)

    # 记忆最近一次调整的排版参数 (全局会话同步)
    LAST_PARAMS = {
        "font_identifier": "OPPOSans-H.ttf", # 默认开源特粗黑体
        "font_size": 24,
        "text_color": "#E11D48",    # 默认喜庆红
        "stroke_color": "#FFFFFF",  # 默认纯白描边
        "stroke_width": 3,
        "text_y": 10,
        "align": "center",
        "enable_erase": False,      # 纯净图默认不抹除
        "erase_h": 36,
        "erase_top": 0
    }

    def __init__(self, gif_path: str, default_text: str = "", all_items: list = None, current_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✏️ 表情文字工坊：手动添加与精修文字 (字体/字号/色彩/描边)")
        self.resize(780, 640)
        self.gif_path = gif_path
        self.default_text = default_text
        self.all_items = [[p, txt] for p, txt in (all_items or [])]
        self.current_index = current_index

        self.cur_text_color = self.LAST_PARAMS["text_color"]
        self.cur_stroke_color = self.LAST_PARAMS["stroke_color"]
        self.cur_align = self.LAST_PARAMS["align"]

        self._init_ui()
        self._load_first_frame()

    def _init_ui(self):
        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(16, 12, 16, 12)
        container_layout.setSpacing(10)

        # 顶部表情切换导航条 (若有多个表情)
        if self.all_items and len(self.all_items) > 1:
            nav_frame = QFrame()
            nav_frame.setStyleSheet("background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 6px;")
            nav_bar = QHBoxLayout(nav_frame)
            nav_bar.setContentsMargins(8, 4, 8, 4)
            nav_bar.setSpacing(8)

            nav_lbl = QLabel("🎯 切换表情视口:")
            nav_lbl.setStyleSheet("font-weight: bold; color: #334155; font-size: 12px; background: transparent;")
            nav_bar.addWidget(nav_lbl)

            self.prev_btn = QPushButton("◀ 上一个")
            self.prev_btn.setFixedHeight(26)
            self.prev_btn.clicked.connect(self._on_prev_item)
            nav_bar.addWidget(self.prev_btn)

            self.item_combo = QComboBox()
            self.item_combo.setFixedHeight(26)
            for i, (p, txt) in enumerate(self.all_items):
                self.item_combo.addItem(f"{i+1:02d}. {txt}")
            if 0 <= self.current_index < len(self.all_items):
                self.item_combo.setCurrentIndex(self.current_index)
            self.item_combo.currentIndexChanged.connect(self._on_combo_index_changed)
            nav_bar.addWidget(self.item_combo, stretch=1)

            self.next_btn = QPushButton("下一个 ▶")
            self.next_btn.setFixedHeight(26)
            self.next_btn.clicked.connect(self._on_next_item)
            nav_bar.addWidget(self.next_btn)

            container_layout.addWidget(nav_frame)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(16)

        # ------------------ 左侧：240x240 实时物理视口 ------------------
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("📱 240×240 所见即所得实时视口:"))
        self.canvas = GifPreviewCanvas()
        left_layout.addWidget(self.canvas)

        # 当前表情体积状态与立即压缩
        size_box = QHBoxLayout()
        size_box.setContentsMargins(0, 2, 0, 2)
        size_box.setSpacing(6)
        
        self.size_badge_lbl = QLabel("体积: -- KB")
        self.size_badge_lbl.setStyleSheet("font-size: 11px; font-weight: bold; padding: 2px 6px; border-radius: 4px;")
        size_box.addWidget(self.size_badge_lbl)
        size_box.addStretch(1)

        self.compress_current_btn = QPushButton("🗜️ 压缩当前 (≤480KB)")
        self.compress_current_btn.setFixedHeight(24)
        self.compress_current_btn.setStyleSheet("""
            QPushButton {
                font-size: 11px;
                font-weight: bold;
                color: #B45309;
                background-color: #FEF3C7;
                border: 1px solid #F59E0B;
                border-radius: 4px;
                padding: 1px 8px;
            }
            QPushButton:hover {
                background-color: #FDE68A;
            }
        """)
        self.compress_current_btn.setToolTip("使用智能调色板与自适应算法，将当前表情体积严格压缩至 ≤480KB (微信安全红线)")
        self.compress_current_btn.clicked.connect(self._on_compress_current)
        size_box.addWidget(self.compress_current_btn)
        left_layout.addLayout(size_box)

        # 快捷位置预设胶囊
        pos_quick_lbl = QLabel("极速位置定位:")
        pos_quick_lbl.setStyleSheet("font-size: 11px; color: #64748B; font-weight: bold;")
        left_layout.addWidget(pos_quick_lbl)

        pos_btn_row = QHBoxLayout()
        self.pos_top_btn = QPushButton("⬆ 置顶 (10px)")
        self.pos_top_btn.setFixedHeight(26)
        self.pos_top_btn.clicked.connect(lambda: self.y_slider.setValue(10))
        pos_btn_row.addWidget(self.pos_top_btn)

        self.pos_mid_btn = QPushButton("⏺ 居中 (100px)")
        self.pos_mid_btn.setFixedHeight(26)
        self.pos_mid_btn.clicked.connect(lambda: self.y_slider.setValue(100))
        pos_btn_row.addWidget(self.pos_mid_btn)

        self.pos_bot_btn = QPushButton("⬇ 靠底 (190px)")
        self.pos_bot_btn.setFixedHeight(26)
        self.pos_bot_btn.clicked.connect(lambda: self.y_slider.setValue(190))
        pos_btn_row.addWidget(self.pos_bot_btn)
        left_layout.addLayout(pos_btn_row)

        tip_lbl = QLabel("💡 提示：在此调好满意的字体、色彩与描边，点击下方【一键同步应用到全部】即可秒级为全部 15 张表情自动添加！")
        tip_lbl.setStyleSheet("color: #059669; font-size: 11px; background: #ECFDF5; padding: 6px; border-radius: 4px; border: 1px solid #A7F3D0;")
        tip_lbl.setWordWrap(True)
        left_layout.addWidget(tip_lbl)
        left_layout.addStretch(1)
        main_layout.addLayout(left_layout)

        # ------------------ 右侧：文字排版与样式调配 ------------------
        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)

        # 1. 文字内容与字体选择
        text_box = QGroupBox("1. 文字内容与字体选择")
        t_layout = QVBoxLayout(text_box)
        t_layout.setSpacing(6)

        # 输入文字
        t_row1 = QHBoxLayout()
        t_row1.addWidget(QLabel("表情文字:"))
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("请输入要添加在表情上的文字...")
        self.text_input.setText(self.default_text)
        self.text_input.textChanged.connect(self._on_param_changed)
        t_row1.addWidget(self.text_input)

        self.edit_all_titles_btn = QPushButton("📋 核对/批量粘贴全部标题...")
        self.edit_all_titles_btn.setFixedHeight(26)
        self.edit_all_titles_btn.setToolTip("查看、编辑或多行批量粘贴所有表情的标题")
        self.edit_all_titles_btn.clicked.connect(self._on_open_batch_titles_dialog)
        t_row1.addWidget(self.edit_all_titles_btn)
        t_layout.addLayout(t_row1)

        # 字体下拉与自定义字体
        f_row = QHBoxLayout()
        f_row.addWidget(QLabel("选择字体:"))
        self.font_combo = QComboBox()
        for p in GifTextEditor.FONT_PRESETS:
            self.font_combo.addItem(p["name"], p["file"])
        # 设置当前选中字体
        cur_f = self.LAST_PARAMS["font_identifier"]
        for idx in range(self.font_combo.count()):
            if self.font_combo.itemData(idx) == cur_f or self.font_combo.itemText(idx) == cur_f:
                self.font_combo.setCurrentIndex(idx)
                break
        self.font_combo.currentIndexChanged.connect(self._on_param_changed)
        f_row.addWidget(self.font_combo, stretch=1)

        self.custom_font_btn = QPushButton("📂 本地字体...")
        self.custom_font_btn.setFixedHeight(26)
        self.custom_font_btn.clicked.connect(self._on_choose_custom_font)
        f_row.addWidget(self.custom_font_btn)
        t_layout.addLayout(f_row)

        font_badge = QLabel("🛡️ 100% 开源免费商用字库（OPPO/华为鸿蒙/阿里/思源），微信提审零版权争议风险")
        font_badge.setStyleSheet("font-size: 11px; color: #047857; background: #ECFDF5; border: 1px solid #A7F3D0; padding: 3px 6px; border-radius: 4px;")
        t_layout.addWidget(font_badge)

        # 字号大小与垂直位置
        sz_row = QHBoxLayout()
        sz_row.addWidget(QLabel("字号大小:"))
        self.font_slider = QSlider(Qt.Horizontal)
        self.font_slider.setRange(12, 48)
        self.font_slider.setValue(self.LAST_PARAMS["font_size"])
        self.font_slider.setFixedWidth(110)
        self.font_slider.valueChanged.connect(self._on_param_changed)
        sz_row.addWidget(self.font_slider)
        self.font_val_lbl = QLabel(f"{self.LAST_PARAMS['font_size']} pt")
        sz_row.addWidget(self.font_val_lbl)

        sz_row.addSpacing(10)
        sz_row.addWidget(QLabel("垂直位置:"))
        self.y_slider = QSlider(Qt.Horizontal)
        self.y_slider.setRange(0, 215)
        self.y_slider.setValue(self.LAST_PARAMS["text_y"])
        self.y_slider.setFixedWidth(110)
        self.y_slider.valueChanged.connect(self._on_param_changed)
        sz_row.addWidget(self.y_slider)
        self.y_val_lbl = QLabel(f"{self.LAST_PARAMS['text_y']} px")
        sz_row.addWidget(self.y_val_lbl)
        t_layout.addLayout(sz_row)

        # 水平对齐方式
        align_row = QHBoxLayout()
        align_row.addWidget(QLabel("水平对齐:"))
        self.align_group = QButtonGroup(self)
        for align_val, align_text in [("center", "居中对齐"), ("left", "靠左"), ("right", "靠右")]:
            btn = QPushButton(align_text)
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.setProperty("align_val", align_val)
            if align_val == self.cur_align:
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, val=align_val: self._on_align_changed(val))
            self.align_group.addButton(btn)
            align_row.addWidget(btn)
        align_row.addStretch(1)
        t_layout.addLayout(align_row)

        right_layout.addWidget(text_box)

        # 2. 色彩与描边定制 (所见即所得色卡)
        style_box = QGroupBox("2. 色彩与描边定制 (高对比艺术字)")
        s_layout = QVBoxLayout(style_box)
        s_layout.setSpacing(6)

        # 文字颜色选择
        t_col_row = QHBoxLayout()
        t_col_row.addWidget(QLabel("文字颜色:"))
        self.text_col_group = QButtonGroup(self)
        self.text_col_btns = []
        text_colors = [
            ("#E11D48", "喜庆大红"), ("#141414", "经典黑"), ("#FFFFFF", "纯白"),
            ("#F59E0B", "富贵金"), ("#FACC15", "柠檬黄"), ("#EA580C", "活力橙"),
            ("#10B981", "翡翠绿"), ("#07C160", "微信绿"), ("#2563EB", "宝蓝"), ("#A855F7", "梦幻紫")
        ]
        for hex_code, name in text_colors:
            btn = ColorChipButton(hex_code, name)
            if hex_code.lower() == self.cur_text_color.lower():
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=hex_code: self._on_text_color_selected(c))
            self.text_col_group.addButton(btn)
            self.text_col_btns.append(btn)
            t_col_row.addWidget(btn)

        self.custom_tcol_btn = QPushButton("🎨 选色...")
        self.custom_tcol_btn.setFixedHeight(24)
        self.custom_tcol_btn.clicked.connect(self._on_custom_text_color)
        t_col_row.addWidget(self.custom_tcol_btn)
        t_col_row.addStretch(1)
        s_layout.addLayout(t_col_row)

        # 描边粗细与描边颜色
        st_row = QHBoxLayout()
        st_row.addWidget(QLabel("描边粗细:"))
        self.stroke_slider = QSlider(Qt.Horizontal)
        self.stroke_slider.setRange(0, 8)
        self.stroke_slider.setValue(self.LAST_PARAMS["stroke_width"])
        self.stroke_slider.setFixedWidth(110)
        self.stroke_slider.valueChanged.connect(self._on_param_changed)
        st_row.addWidget(self.stroke_slider)
        self.stroke_val_lbl = QLabel(f"{self.LAST_PARAMS['stroke_width']} px")
        st_row.addWidget(self.stroke_val_lbl)

        st_row.addSpacing(12)
        st_row.addWidget(QLabel("描边颜色:"))
        self.stroke_col_group = QButtonGroup(self)
        self.stroke_col_btns = []
        stroke_colors = [
            ("#FFFFFF", "纯白描边 (推荐)"), ("#000000", "高对比纯黑"),
            ("#FEF08A", "鎏金浅黄"), ("#991B1B", "深红描边")
        ]
        for hex_code, name in stroke_colors:
            btn = ColorChipButton(hex_code, name)
            if hex_code.lower() == self.cur_stroke_color.lower():
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=hex_code: self._on_stroke_color_selected(c))
            self.stroke_col_group.addButton(btn)
            self.stroke_col_btns.append(btn)
            st_row.addWidget(btn)

        self.custom_scol_btn = QPushButton("🎨 自定义...")
        self.custom_scol_btn.setFixedHeight(24)
        self.custom_scol_btn.clicked.connect(self._on_custom_stroke_color)
        st_row.addWidget(self.custom_scol_btn)
        st_row.addStretch(1)
        s_layout.addLayout(st_row)

        right_layout.addWidget(style_box)

        # 3. 原图背景抹除 (可选高级项)
        erase_box = QGroupBox("3. 原图旧字抹除 (若原图自带杂乱错别字时勾选)")
        e_layout = QVBoxLayout(erase_box)
        e_layout.setSpacing(6)

        self.enable_erase_chk = QCheckBox("启用顶部抹除 (纯净原图请勿勾选，保护人物原画)")
        self.enable_erase_chk.setChecked(self.LAST_PARAMS["enable_erase"])
        self.enable_erase_chk.stateChanged.connect(self._on_erase_toggle)
        e_layout.addWidget(self.enable_erase_chk)

        self.erase_controls = QWidget()
        ec_layout = QHBoxLayout(self.erase_controls)
        ec_layout.setContentsMargins(0, 0, 0, 0)
        ec_layout.setSpacing(8)

        ec_layout.addWidget(QLabel("抹除高度:"))
        self.h_slider = QSlider(Qt.Horizontal)
        self.h_slider.setRange(15, 80)
        self.h_slider.setValue(self.LAST_PARAMS["erase_h"])
        self.h_slider.setFixedWidth(100)
        self.h_slider.valueChanged.connect(self._on_param_changed)
        ec_layout.addWidget(self.h_slider)
        self.h_val_lbl = QLabel(f"{self.LAST_PARAMS['erase_h']} px")
        ec_layout.addWidget(self.h_val_lbl)

        ec_layout.addSpacing(8)
        ec_layout.addWidget(QLabel("起始 Y:"))
        self.top_slider = QSlider(Qt.Horizontal)
        self.top_slider.setRange(0, 40)
        self.top_slider.setValue(self.LAST_PARAMS["erase_top"])
        self.top_slider.setFixedWidth(100)
        self.top_slider.valueChanged.connect(self._on_param_changed)
        ec_layout.addWidget(self.top_slider)
        self.top_val_lbl = QLabel(f"{self.LAST_PARAMS['erase_top']} px")
        ec_layout.addWidget(self.top_val_lbl)
        ec_layout.addStretch(1)

        e_layout.addWidget(self.erase_controls)
        self.erase_controls.setVisible(self.LAST_PARAMS["enable_erase"])
        right_layout.addWidget(erase_box)

        # ------------------ 底部应用与单独下载导出按钮 ------------------
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        self.download_btn = QPushButton("💾 单独下载另存为...")
        self.download_btn.setMinimumHeight(38)
        self.download_btn.clicked.connect(self._on_download_single)
        btn_box.addWidget(self.download_btn)

        self.apply_single_btn = QPushButton("⚡ 仅应用到当前表情")
        self.apply_single_btn.setMinimumHeight(38)
        self.apply_single_btn.clicked.connect(self._on_apply_single)
        btn_box.addWidget(self.apply_single_btn)

        all_count = len(self.all_items) if self.all_items else 15
        self.apply_all_btn = QPushButton(f"🌟 一键为全部表情添加文字 (应用此排版到全部 {all_count} 张)")
        self.apply_all_btn.setObjectName("PrimaryBtn")
        self.apply_all_btn.setMinimumHeight(42)
        self.apply_all_btn.setToolTip("以当前第一张图片调好的字体、字号、描边和位置，一键为全部表情按各自标题添加文字！")
        self.apply_all_btn.setStyleSheet("""
            QPushButton#PrimaryBtn {
                font-size: 13px;
                font-weight: bold;
                background-color: #07C160;
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton#PrimaryBtn:hover {
                background-color: #059669;
            }
        """)
        self.apply_all_btn.clicked.connect(self._on_apply_all)
        btn_box.addWidget(self.apply_all_btn)

        right_layout.addLayout(btn_box)
        main_layout.addLayout(right_layout)

        container_layout.addLayout(main_layout)

    def _on_erase_toggle(self, state):
        enabled = (state == Qt.Checked or state == 2)
        self.erase_controls.setVisible(enabled)
        self._on_param_changed()

    def _on_choose_custom_font(self):
        font_dir = PathMemory.get_upload_dir()
        path, _ = QFileDialog.getOpenFileName(self, "选择本地中文字体文件", font_dir, "字体文件 (*.ttf *.ttc *.otf)")
        if path:
            PathMemory.set_upload_dir(path)
            fname = os.path.basename(path)
            self.font_combo.addItem(f"📁 {fname}", path)
            self.font_combo.setCurrentIndex(self.font_combo.count() - 1)
            self._on_param_changed()

    def _on_text_color_selected(self, hex_code: str):
        self.cur_text_color = hex_code
        for b in self.text_col_btns:
            b.setChecked(b.color_hex.lower() == hex_code.lower())
        self._on_param_changed()

    def _on_custom_text_color(self):
        col = QColorDialog.getColor(QColor(self.cur_text_color), self, "选择文字颜色")
        if col.isValid():
            hex_code = col.name().upper()
            self.cur_text_color = hex_code
            for b in self.text_col_btns:
                b.setChecked(False)
            self._on_param_changed()

    def _on_stroke_color_selected(self, hex_code: str):
        self.cur_stroke_color = hex_code
        for b in self.stroke_col_btns:
            b.setChecked(b.color_hex.lower() == hex_code.lower())
        self._on_param_changed()

    def _on_custom_stroke_color(self):
        col = QColorDialog.getColor(QColor(self.cur_stroke_color), self, "选择描边颜色")
        if col.isValid():
            hex_code = col.name().upper()
            self.cur_stroke_color = hex_code
            for b in self.stroke_col_btns:
                b.setChecked(False)
            self._on_param_changed()

    def _on_align_changed(self, val: str):
        self.cur_align = val
        self._on_param_changed()

    def _switch_to_index(self, new_idx: int):
        if not self.all_items or not (0 <= new_idx < len(self.all_items)):
            return
        # 保存当前文字到当前项
        if 0 <= self.current_index < len(self.all_items):
            self.all_items[self.current_index][1] = self.text_input.text().strip()

        self.current_index = new_idx
        self.gif_path, self.default_text = self.all_items[new_idx]

        if hasattr(self, "item_combo"):
            self.item_combo.blockSignals(True)
            self.item_combo.setCurrentIndex(new_idx)
            self.item_combo.blockSignals(False)

        self.text_input.blockSignals(True)
        self.text_input.setText(self.default_text)
        self.text_input.blockSignals(False)

        self._load_first_frame()

    def _on_prev_item(self):
        if not self.all_items:
            return
        new_idx = (self.current_index - 1) % len(self.all_items)
        self._switch_to_index(new_idx)

    def _on_next_item(self):
        if not self.all_items:
            return
        new_idx = (self.current_index + 1) % len(self.all_items)
        self._switch_to_index(new_idx)

    def _on_combo_index_changed(self, idx):
        self._switch_to_index(idx)

    def _on_open_batch_titles_dialog(self):
        """打开批量填入/核对全部标题对话框"""
        current_titles = [item[1] for item in self.all_items]
        dlg = BatchTitlesDialog(current_titles, parent=self)
        if dlg.exec():
            new_titles = dlg.result_titles
            for i, t in enumerate(new_titles):
                if i < len(self.all_items):
                    self.all_items[i][1] = t
                    if hasattr(self, "item_combo"):
                        self.item_combo.setItemText(i, f"{i+1:02d}. {t}")
            if 0 <= self.current_index < len(self.all_items):
                self.default_text = self.all_items[self.current_index][1]
                self.text_input.setText(self.default_text)
            self._on_param_changed()

    def _load_first_frame(self):
        if not os.path.exists(self.gif_path):
            return
        with Image.open(self.gif_path) as im:
            im.seek(0)
            self.canvas.set_base_frame(im)
        self._update_size_badge()
        self._on_param_changed()

    def _update_size_badge(self):
        if not hasattr(self, "size_badge_lbl"):
            return
        if not os.path.exists(self.gif_path):
            self.size_badge_lbl.setText("文件不存在")
            return
        kb = os.path.getsize(self.gif_path) / 1024.0
        if kb <= 480:
            self.size_badge_lbl.setText(f"🟢 体积: {kb:.1f} KB (合规)")
            self.size_badge_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #07C160; background: #F0FDF4; border: 1px solid #BBF7D0; padding: 2px 6px; border-radius: 4px;")
        elif kb <= 500:
            self.size_badge_lbl.setText(f"🟡 体积: {kb:.1f} KB (临界)")
            self.size_badge_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #D97706; background: #FEF3C7; border: 1px solid #FDE68A; padding: 2px 6px; border-radius: 4px;")
        else:
            self.size_badge_lbl.setText(f"🔴 体积: {kb:.1f} KB (超标)")
            self.size_badge_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #EF4444; background: #FEF2F2; border: 1px solid #FECACA; padding: 2px 6px; border-radius: 4px;")

    def _on_compress_current(self):
        if not os.path.exists(self.gif_path):
            return
        orig_kb = os.path.getsize(self.gif_path) / 1024.0
        self.compress_current_btn.setEnabled(False)
        self.compress_current_btn.setText("正在压缩...")
        QApplication.processEvents()

        ok, new_kb, msg = ImageCompressor.compress_gif(self.gif_path, self.gif_path, max_kb=480)
        self._update_size_badge()
        self._load_first_frame()
        self.compress_current_btn.setEnabled(True)
        self.compress_current_btn.setText("🗜️ 压缩当前 (≤480KB)")

        if ok and new_kb <= 480:
            QMessageBox.information(
                self, "压缩成功",
                f"当前表情已成功压缩至微信安全体积！\n原体积: {orig_kb:.1f} KB ➔ 优化后: {new_kb:.1f} KB (≤480KB 微信安全红线)"
            )
        else:
            QMessageBox.information(
                self, "压缩完成",
                f"压缩处理完成：\n原体积: {orig_kb:.1f} KB ➔ 当前体积: {new_kb:.1f} KB\n({msg})"
            )

    def _on_param_changed(self):
        eh = self.h_slider.value()
        etop = self.top_slider.value()
        txt = self.text_input.text()
        fsize = self.font_slider.value()
        ty = self.y_slider.value()
        swidth = self.stroke_slider.value()
        enable_erase = self.enable_erase_chk.isChecked()

        # 实时同步更新到当前项与导航条
        if self.all_items and 0 <= self.current_index < len(self.all_items):
            self.all_items[self.current_index][1] = txt
            if hasattr(self, "item_combo"):
                self.item_combo.blockSignals(True)
                self.item_combo.setItemText(self.current_index, f"{self.current_index+1:02d}. {txt}")
                self.item_combo.blockSignals(False)

        f_data = self.font_combo.currentData()
        font_id = f_data if f_data else self.font_combo.currentText()

        # 实时记忆排版与样式参数
        GifEditorDialog.LAST_PARAMS["font_identifier"] = font_id
        GifEditorDialog.LAST_PARAMS["font_size"] = fsize
        GifEditorDialog.LAST_PARAMS["text_color"] = self.cur_text_color
        GifEditorDialog.LAST_PARAMS["stroke_color"] = self.cur_stroke_color
        GifEditorDialog.LAST_PARAMS["stroke_width"] = swidth
        GifEditorDialog.LAST_PARAMS["text_y"] = ty
        GifEditorDialog.LAST_PARAMS["align"] = self.cur_align
        GifEditorDialog.LAST_PARAMS["enable_erase"] = enable_erase
        GifEditorDialog.LAST_PARAMS["erase_h"] = eh
        GifEditorDialog.LAST_PARAMS["erase_top"] = etop

        self.font_val_lbl.setText(f"{fsize} pt")
        self.y_val_lbl.setText(f"{ty} px")
        self.stroke_val_lbl.setText(f"{swidth} px")
        self.h_val_lbl.setText(f"{eh} px")
        self.top_val_lbl.setText(f"{etop} px")

        self.canvas.update_params(
            text=txt,
            font_identifier=font_id,
            font_size=fsize,
            text_color=self.cur_text_color,
            stroke_color=self.cur_stroke_color,
            stroke_width=swidth,
            text_y=ty,
            align=self.cur_align,
            enable_erase=enable_erase,
            erase_top=etop,
            erase_h=eh
        )

    def _on_apply_single(self):
        """仅应用到当前表情"""
        eh = self.h_slider.value()
        etop = self.top_slider.value()
        txt = self.text_input.text()
        fsize = self.font_slider.value()
        ty = self.y_slider.value()
        swidth = self.stroke_slider.value()
        enable_erase = self.enable_erase_chk.isChecked()
        f_data = self.font_combo.currentData()
        font_id = f_data if f_data else self.font_combo.currentText()

        self.apply_single_btn.setEnabled(False)
        self.apply_single_btn.setText("正在压制文字中...")

        erase_rect = (0, etop, 240, eh) if enable_erase else None
        ok = GifTextEditor.process_gif(
            gif_path=self.gif_path,
            out_gif_path=self.gif_path,
            text=txt,
            font_identifier=font_id,
            font_size=fsize,
            text_color=self.cur_text_color,
            stroke_color=self.cur_stroke_color,
            stroke_width=swidth,
            text_y=ty,
            align=self.cur_align,
            erase_rect=erase_rect
        )

        self.apply_single_btn.setEnabled(True)
        self.apply_single_btn.setText("⚡ 仅应用到当前表情")

        if ok:
            QMessageBox.information(self, "完成", "已成功将文字添加并渲染到该表情的所有帧！")
            self.applied.emit(self.gif_path)
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "GIF 处理失败，请重试！")

    def _on_apply_all(self):
        """一键为全部表情批量添加文字 (应用第1张图调好的排版)"""
        if not self.all_items:
            self._on_apply_single()
            return

        cur_text = self.text_input.text().strip()
        if 0 <= self.current_index < len(self.all_items):
            self.all_items[self.current_index][1] = cur_text

        eh = self.h_slider.value()
        etop = self.top_slider.value()
        fsize = self.font_slider.value()
        ty = self.y_slider.value()
        swidth = self.stroke_slider.value()
        enable_erase = self.enable_erase_chk.isChecked()
        f_data = self.font_combo.currentData()
        font_id = f_data if f_data else self.font_combo.currentText()

        erase_desc = f"开启抹除 ({eh}px)" if enable_erase else "完全保留原画 (不抹除)"

        # 生成清单预览
        items_preview = []
        for i, (gp, t) in enumerate(self.all_items):
            if i < 8:
                items_preview.append(f"  #{i+1:02d}. {t if t else '(无文字)'}")
        if len(self.all_items) > 8:
            items_preview.append(f"  ... 等共 {len(self.all_items)} 个表情")
        preview_str = "\n".join(items_preview)

        ret = QMessageBox.question(
            self, "一键为全部表情添加文字确认",
            f"确定将第 1 张图已做好的艺术字排版：\n\n"
            f"• 字体: {self.font_combo.currentText()}\n"
            f"• 字号: {fsize} pt | 位置 Y: {ty} px ({self.cur_align})\n"
            f"• 色彩: 文字 {self.cur_text_color} | 描边 {self.cur_stroke_color} ({swidth}px)\n"
            f"• 抹除状态: {erase_desc}\n\n"
            f"一键为全部 {len(self.all_items)} 个表情按照各自预设标题批量添加文字吗？\n\n"
            f"【即将添加文字的表情清单】：\n{preview_str}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
        )
        if ret != QMessageBox.Yes:
            return

        progress = QProgressDialog("正在批量为全部表情添加文字...", "取消", 0, len(self.all_items), self)
        progress.setWindowTitle("批量添加文字中")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        erase_rect = (0, etop, 240, eh) if enable_erase else None
        success_count = 0

        for idx, (g_path, txt) in enumerate(self.all_items):
            if progress.wasCanceled():
                break

            progress.setLabelText(f"正在渲染 ({idx+1}/{len(self.all_items)}): {os.path.basename(g_path)} - {txt}")
            QApplication.processEvents()

            ok = GifTextEditor.process_gif(
                gif_path=g_path,
                out_gif_path=g_path,
                text=txt,
                font_identifier=font_id,
                font_size=fsize,
                text_color=self.cur_text_color,
                stroke_color=self.cur_stroke_color,
                stroke_width=swidth,
                text_y=ty,
                align=self.cur_align,
                erase_rect=erase_rect
            )
            if ok:
                success_count += 1
            progress.setValue(idx + 1)

        progress.close()

        QMessageBox.information(
            self, "批量添加完成",
            f"🎉 成功为 {success_count}/{len(self.all_items)} 个表情添加了艺术文字！\n\n"
            f"所有表情已统一应用相同字体、字号、描边、色彩与对齐排版规范。"
        )
        new_titles = [t for _, t in self.all_items]
        self.titles_updated.emit(new_titles)
        self.applied.emit(self.gif_path)
        self.accept()

    def _on_download_single(self):
        """单独下载另存为当前表情"""
        default_name = f"{self.default_text}.gif" if self.default_text else os.path.basename(self.gif_path)
        default_dir = PathMemory.get_download_dir(fallback=os.path.dirname(self.gif_path))
        default_target = os.path.join(default_dir, default_name)
        save_path, _ = QFileDialog.getSaveFileName(self, "单独下载表情 GIF", default_target, "GIF 动图 (*.gif)")
        if save_path:
            PathMemory.set_download_dir(save_path)
            shutil.copyfile(self.gif_path, save_path)
            QMessageBox.information(self, "下载成功", f"表情已成功单独保存至：\n{save_path}")
