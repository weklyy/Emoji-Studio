GLOBAL_STYLE = """
/* 现代 Windows Fluent 极简生态配色体系 (微信灰绿与通透 Slate) */
QWidget {
    font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    color: #1E293B;
    background-color: #F8FAFC;
    font-size: 13px;
}

QScrollBar:vertical {
    border: none;
    background: transparent;
    width: 6px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #CBD5E1;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #94A3B8;
}

/* 按钮通用规范 */
QPushButton {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    color: #334155;
}
QPushButton:hover {
    background-color: #F1F5F9;
    border-color: #CBD5E1;
}
QPushButton:pressed {
    background-color: #E2E8F0;
}

/* 微信主功能按钮 */
QPushButton#PrimaryBtn {
    background-color: #07C160;
    color: #FFFFFF;
    border: 1px solid #06AD56;
    font-weight: bold;
    font-size: 13px;
}
QPushButton#PrimaryBtn:hover {
    background-color: #06AD56;
}
QPushButton#PrimaryBtn:pressed {
    background-color: #059B4C;
}

/* 复制 F12 填表高亮按钮 */
QPushButton#F12Btn {
    background-color: #6366F1;
    color: #FFFFFF;
    border: 1px solid #4F46E5;
    font-weight: bold;
}
QPushButton#F12Btn:hover {
    background-color: #4F46E5;
}

/* 输入框 */
QLineEdit, QTextEdit {
    background-color: #FFFFFF;
    border: 1px solid #CBD5E1;
    border-radius: 6px;
    padding: 6px 8px;
    color: #0F172A;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1.5px solid #07C160;
    background-color: #FFFFFF;
}

/* 列表与卡片 */
QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    outline: none;
}
QListWidget::item {
    border-bottom: 1px solid #F1F5F9;
    padding: 10px;
    border-radius: 6px;
}
QListWidget::item:selected {
    background-color: #ECFDF5;
    border-left: 3px solid #07C160;
    color: #065F46;
}
QListWidget::item:hover:!selected {
    background-color: #F8FAFC;
}

/* 分组面板 */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: bold;
    padding-top: 14px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #475569;
}

/* 三栏可拖拽分割条 (QSplitter) 现代极简风格 */
QSplitter::handle:horizontal {
    width: 6px;
    background-color: #E2E8F0;
    border-radius: 3px;
    margin: 6px 1px;
}
QSplitter::handle:horizontal:hover {
    background-color: #07C160;
}
QSplitter::handle:horizontal:pressed {
    background-color: #059669;
}

/* QTabWidget 现代微信绿风格选项卡 */
QTabWidget::pane {
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    background-color: #FFFFFF;
    top: -1px;
}
QTabBar::tab {
    background-color: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 8px 18px;
    margin-right: 4px;
    font-weight: 600;
    font-size: 13px;
    color: #475569;
}
QTabBar::tab:hover {
    background-color: #E2E8F0;
    color: #0F172A;
}
QTabBar::tab:selected {
    background-color: #FFFFFF;
    border-top: 3px solid #07C160;
    color: #07C160;
    font-weight: bold;
}
"""

