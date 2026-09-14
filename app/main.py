"""应用入口。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QLoggingCategory
from PyQt6.QtGui import QFont, QFontDatabase, QIcon, QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication

from app.feature_flags import ENABLE_SCRIPTURE_SEARCH
from core.config import AppConfig
from core.database import BibleDatabase
from core.paths import icon_path, project_root
from ui.main_window import MainWindow
from ui.fulltext_search import attach_fulltext_search


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
    # 默认 UI 字体，减少回退到 MS Sans Serif
    for family in ("Microsoft YaHei UI", "微软雅黑", "Segoe UI"):
        if family in QFontDatabase.families():
            app.setFont(QFont(family, 10))
            break

    icon_file = icon_path()
    app_icon = QIcon(str(icon_file)) if icon_file.exists() else QIcon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    config = AppConfig()
    db = BibleDatabase()
    window = MainWindow(db, config)

    if ENABLE_SCRIPTURE_SEARCH:
        attach_fulltext_search(window)

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
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
