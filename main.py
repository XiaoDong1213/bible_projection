# main.py
# Bible Pro 程序入口

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon

from config import AppConfig
from bible_database import BibleDatabase
from main_window import MainWindow


def _set_windows_app_id():
    """设置 Windows 应用标识，确保任务栏正确显示程序。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "XiaoDong.BibleProjection"
        )
    except Exception:
        pass


def main():
    _set_windows_app_id()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    icon_path = Path(__file__).resolve().parent / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    config = AppConfig()
    db = BibleDatabase()
    window = MainWindow(db, config)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()