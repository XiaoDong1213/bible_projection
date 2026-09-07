import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtCore import Qt

from config import AppConfig
from bible_database import BibleDatabase
from main_window import MainWindow


# 设置 Windows 应用标识，确保任务栏图标正确关联

def _set_windows_app_id():
    """设置 Windows 应用标识。"""
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
    """初始化应用、数据库和主窗口。"""
    _set_windows_app_id()

    # 统一工作目录，确保打包后的 QSS 相对资源路径仍然有效。
    # styles/*.qss 中的箭头图片使用 styles/xxx.svg 路径，
    # 安装后从快捷方式启动时工作目录可能不是程序目录。
    app_root = Path(__file__).resolve().parent
    try:
        os.chdir(app_root)
    except OSError:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    icon_path = app_root / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    config = AppConfig()
    db = BibleDatabase()
    window = MainWindow(db, config)

    # Home / End 使用应用级快捷键，避免焦点位于搜索框、数字框、列表等子控件时被控件自身截获。
    # 关闭 ScriptureDisplay 内部原有的同键快捷键，统一由主窗口处理。
    if hasattr(window.scripture_display, "_home_shortcut"):
        window.scripture_display._home_shortcut.setEnabled(False)
    if hasattr(window.scripture_display, "_end_shortcut"):
        window.scripture_display._end_shortcut.setEnabled(False)

    home_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Home), window)
    home_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
    home_shortcut.activated.connect(window.scripture_display._scroll_to_top)

    end_shortcut = QShortcut(QKeySequence(Qt.Key.Key_End), window)
    end_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
    end_shortcut.activated.connect(window.scripture_display._scroll_to_bottom)

    # 0：暂停/继续自动滚动。使用窗口快捷键，不改动搜索框的输入逻辑。
    pause_shortcut = QShortcut(QKeySequence(Qt.Key.Key_0), window)
    pause_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
    pause_shortcut.activated.connect(window._toggle_scroll_pause)

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
