"""全文经文搜索面板挂载。"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton

from core.selection import ScriptureSelection
from .panel import ScriptureSearchWidget


def attach_fulltext_search(window):
    """在主窗口工具栏挂载「经文搜索」按钮与 Ctrl+F。"""
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


def _polish_search_panel(widget):
    search_button = widget.findChild(QPushButton, "scriptureSearchButton")
    if search_button is not None:
        search_button.setFixedSize(82, 34)

    widget.search_input.setFixedHeight(44)
    widget.result_layout.setContentsMargins(0, 4, 4, 0)
    widget.result_layout.setSpacing(8)
    widget.history_layout.setContentsMargins(4, 4, 4, 4)
    widget.history_layout.setSpacing(4)


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
    _polish_search_panel(widget)

    panel_width = 480
    widget.setMinimumWidth(0)
    widget.setMaximumWidth(panel_width)
    widget.setFixedWidth(panel_width)

    height = max(480, window.height() - window.toolbar.height() - 18)
    widget.resize(panel_width, height)
    global_pos = window.mapToGlobal(
        QPoint(window.width() - panel_width - 8, window.toolbar.height() + 4)
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
    return ScriptureSelection.single_chapter(book, chapter, verse, verse, max_verse=max_verse)


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
