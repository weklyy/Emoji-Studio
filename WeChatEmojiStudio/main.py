import sys
import os

# 确保项目根目录在 sys.path 中
cur_dir = os.path.dirname(os.path.abspath(__file__))
if cur_dir not in sys.path:
    sys.path.insert(0, cur_dir)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from view.main_window import MainWindow

def main():
    # 启用高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("WeChatEmojiStudio")
    app.setOrganizationName("WeChatStickerTools")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
