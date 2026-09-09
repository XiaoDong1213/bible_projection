import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon, QKeySequence, QShortcut
from PyQt6.QtCore import Qt

from config import AppConfig
from bible_database import BibleDatabase
from main_window import MainWindow
from scripture_search_integration import install_scripture_search
from feature_flags import ENABLE_SCRIPTURE_SEARCH
from ui import scripture_title_render_patch  # noqa: F401 - 安装经文小标题渲染修复
from ui import search_widget_patch  # noqa: F401 - 修复搜索框错误输入后的 Space 行为


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
    # 必须在 QApplication / 主窗口创建前设置，避免 Windows 按默认进程身份生成任务栏图标。
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

    # 应用、主窗口统一使用同一个 icon.ico，避免窗口图标和任务栏图标不一致。
    icon_path = app_root / "icon.ico"
    app_icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    config = AppConfig()
    db = BibleDatabase()
    window = MainWindow(db, config)

    # 独立经文全文搜索：通过发布开关控制，不删除相关代码。
    if ENABLE_SCRIPTURE_SEARCH:
        install_scripture_search(window)

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
