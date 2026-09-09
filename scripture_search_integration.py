from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton

from ui import scripture_search as _scripture_search
from ui.scripture_result_compat import ScriptureResultWidget

# 当前经文搜索模块已经移除了旧版结果卡片；旧版侧边面板仍需要它。
# 在加载 legacy 面板前提供兼容实现，避免改动当前搜索逻辑。
_scripture_search.ScriptureResultWidget = ScriptureResultWidget

from ui.scripture_search_legacy import ScriptureSearchWidget
from ui.selection import ScriptureSelection


def install_scripture_search(window):
    """恢复旧版独立经文搜索面板，不修改原书卷章节搜索。"""
    window._scripture_search_widget = None

    button = QPushButton("经文搜索")
    button.setObjectName("scriptureSearchToolbarButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setToolTip("搜索整本圣经经文  Ctrl+F")
    button.clicked.connect(lambda: _toggle(window))
    window.toolbar.addWidget(button)
    window.scripture_search_button = button

    shortcut = QShortcut(QKeySequence("Ctrl+F"), window)
    shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
    shortcut.activated.connect(lambda: _toggle(window))
    window._scripture_search_shortcut = shortcut


def _toggle(window):
    widget = window._scripture_search_widget
    if widget is not None and widget.isVisible():
        widget.close()
        return

    widget = ScriptureSearchWidget(window.db, window.config, window, theme=window.theme)
    window._scripture_search_widget = widget
    widget.result_activated.connect(lambda result: _activate(window, result))
    widget.result_project_requested.connect(lambda result: _project(window, result))
    widget.close_requested.connect(widget.close)

    width = widget.width()
    height = max(480, window.height() - window.toolbar.height() - 18)
    widget.resize(width, height)
    global_pos = window.mapToGlobal(
        QPoint(window.width() - width - 8, window.toolbar.height() + 4)
    )
    widget.move(global_pos)
    widget.show()
    widget.raise_()
    widget.search_input.setFocus()


def _selection_from_result(window, result):
    book = str(result.get("book", ""))
    chapter = int(result.get("chapter", 1))
    verse = int(result.get("verse", 1))
    max_verse = window.db.get_verse_count(book, chapter)
    if not max_verse:
        return None

    label = str(result.get("verse_label", ""))
    if "-" in label:
        try:
            verse = int(label.split("-", 1)[0])
        except (TypeError, ValueError):
            pass

    verse = max(1, min(verse, max_verse))
    return ScriptureSelection.single_chapter(
        book, chapter, verse, verse, max_verse=max_verse
    )


def _activate(window, result):
    selection = _selection_from_result(window, result)
    if selection is None:
        return
    window._load_selection(selection)
    window.nav_panel.add_selection_to_history(selection)
    window.nav_panel.sync_from_selection(selection)
    if window._scripture_search_widget is not None:
        window._scripture_search_widget.raise_()


def _project(window, result):
    selection = _selection_from_result(window, result)
    if selection is None:
        return
    window._load_selection(selection)
    window.nav_panel.add_selection_to_history(selection)
    window.nav_panel.sync_from_selection(selection)
    if not window.extension_window or not window.extension_window.isVisible():
        window._show_extension()
    if window._scripture_search_widget is not None:
        window._scripture_search_widget.raise_()
