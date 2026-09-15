"""应用入口。"""

from __future__ import annotations

import os
import sys

from PyQt6.QtCore import Qt, QLoggingCategory, QTimer
from PyQt6.QtGui import QFont, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication

from core.paths import icon_path, project_root


def _set_windows_app_id():
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "XiaoDong.BibleProjection"
        )
    except Exception:
        pass


def _set_app_font(app):
    """直接指定界面字体，不做 hasFamily / QFontInfo / families() 探测。

    探测会触发 DirectWrite 字体库初始化，冷启动可多耗数百毫秒到数秒。
    显示设置里的字体下拉仍会在打开对话框时枚举全部系统字体。
    """
    app.setFont(QFont("Microsoft YaHei UI", 10))


def main():
    _set_windows_app_id()

    # QSS 中相对路径 styles/*.svg 依赖工作目录；统一切到项目根。
    root = project_root()
    try:
        os.chdir(root)
    except OSError:
        pass

    # 压掉 DirectWrite 加载旧位图字体时的噪音日志（不影响功能）
    QLoggingCategory.setFilterRules("qt.qpa.fonts=false")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    _set_app_font(app)

    icon_file = icon_path()
    app_icon = QIcon(str(icon_file)) if icon_file.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # 先出启动页，再加载主界面（体感更快）
    from app.splash import SplashScreen

    splash = SplashScreen(app_icon)
    splash.show()
    app.processEvents()

    from app.feature_flags import ENABLE_SCRIPTURE_SEARCH
    from core.config import AppConfig
    from core.database import BibleDatabase
    from ui.main_window import MainWindow

    config = AppConfig()
    db = BibleDatabase()
    window = MainWindow(db, config)

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

    pause_shortcut = QShortcut(QKeySequence(Qt.Key.Key_0), window)
    pause_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
    pause_shortcut.activated.connect(window._toggle_scroll_pause)

    window.show()
    splash.finish(window)
    app.processEvents()

    def _after_show():
        # 挂载全文搜索按钮（面板仍懒创建）；历史等非关键项已在主窗延后
        if ENABLE_SCRIPTURE_SEARCH:
            from ui.fulltext_search import attach_fulltext_search

            attach_fulltext_search(window)

    QTimer.singleShot(0, _after_show)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
