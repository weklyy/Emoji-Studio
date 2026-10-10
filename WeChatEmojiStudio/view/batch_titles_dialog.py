import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QMessageBox, QFrame
)
from PySide6.QtCore import Qt

class BatchTitlesDialog(QDialog):
    """
    表情标题批量填入与快速核对对话框
    支持直接粘贴多行文本 (纯文字 或 带序号如 01 早上好)，一秒自动解析分配
    """
    def __init__(self, current_titles: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 批量填入与核对表情标题")
        self.resize(500, 440)
        self.result_titles = []
        self._init_ui(current_titles)

    def _init_ui(self, current_titles):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        tip_card = QFrame()
        tip_card.setStyleSheet("background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 6px;")
        tc_layout = QVBoxLayout(tip_card)
        tc_layout.setContentsMargins(4, 4, 4, 4)

        tip_lbl = QLabel(
            "💡 提示：在此直接粘贴所有表情的标题，支持多行文本或带序号格式：\n"
            "• 格式一 (纯标题)：早上好 / 辛苦了 / 收到 / 点赞\n"
            "• 格式二 (带序号)：01 早上好 / 02 辛苦了 / 03 收到"
        )
        tip_lbl.setStyleSheet("color: #166534; font-size: 12px; background: transparent;")
        tip_lbl.setWordWrap(True)
        tc_layout.addWidget(tip_lbl)
        layout.addWidget(tip_card)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("在此粘贴每张图片的标题，一行一个...")
        lines = []
        for i, t in enumerate(current_titles, 1):
            lines.append(f"{i:02d} {t}" if t else f"{i:02d} 表情_{i:02d}")
        self.text_edit.setPlainText("\n".join(lines))
        self.text_edit.setStyleSheet("""
            QTextEdit {
                font-family: 'Consolas', 'Microsoft YaHei', monospace;
                font-size: 13px;
                line-height: 1.5;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 6px;
            }
            QTextEdit:focus {
                border: 1px solid #07C160;
            }
        """)
        layout.addWidget(self.text_edit)

        count_lbl = QLabel(f"当前识别总数: {len(current_titles)} 个表情")
        count_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        layout.addWidget(count_lbl)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch(1)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(32)
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        confirm_btn = QPushButton("✔ 一键解析并填入")
        confirm_btn.setObjectName("PrimaryBtn")
        confirm_btn.setFixedHeight(32)
        confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #07C160;
                color: #FFFFFF;
                font-weight: bold;
                border-radius: 4px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background-color: #059669;
            }
        """)
        confirm_btn.clicked.connect(self._on_confirm)
        btn_box.addWidget(confirm_btn)

        layout.addLayout(btn_box)

    def _on_confirm(self):
        raw_text = self.text_edit.toPlainText().strip()
        lines = raw_text.splitlines()
        parsed = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 移除行首序号如 "01 ", "01. ", "01、", "01\t", "1. "
            m = re.match(r'^(?:\d{1,2})[\s、.\-—\t]*(.*)$', line)
            if m and m.group(1).strip():
                parsed.append(m.group(1).strip())
            else:
                parsed.append(line)

        if not parsed:
            QMessageBox.warning(self, "提示", "未输入任何有效标题！")
            return

        self.result_titles = parsed
        self.accept()
