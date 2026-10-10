from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import os

class ProjectSidebar(QWidget):
    project_selected = Signal(str)
    new_project_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(180)
        self.setMaximumWidth(450)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 标题栏
        top_layout = QHBoxLayout()
        title_lbl = QLabel("📁 表情包资产库")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: bold; color: #0F172A;")
        top_layout.addWidget(title_lbl)

        new_btn = QPushButton("+ 新建")
        new_btn.setToolTip("新建一个微信表情包项目文件夹")
        new_btn.clicked.connect(self._on_new_project)
        top_layout.addWidget(new_btn)
        layout.addLayout(top_layout)

        # 项目列表
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

    def set_projects(self, projects: list, current_name: str = None):
        self.list_widget.clear()
        for p in projects:
            status_map = {
                "draft": "🟡 草稿",
                "sliced": "🟢 已切片",
                "submitted": "🔵 已提审",
                "approved": "⭐ 已上架"
            }
            status_text = status_map.get(p.get("status", "draft"), "⚪ 未知")
            upload_date = p.get("upload_date") or "未记录"

            item = QListWidgetItem()
            item.setText(f"{p['name']}\n状态: {status_text} | 上传: {upload_date}")
            item.setData(Qt.UserRole, p["name"])
            self.list_widget.addItem(item)

            if current_name and p["name"] == current_name:
                item.setSelected(True)

    def _on_item_clicked(self, item):
        p_name = item.data(Qt.UserRole)
        self.project_selected.emit(p_name)

    def _on_new_project(self):
        name, ok = QInputDialog.getText(self, "新建表情包项目", "请输入项目名称（如 2026-10-10可爱萌猫）:")
        if ok and name.strip():
            self.new_project_requested.emit(name.strip())
