"""全文经文搜索面板挂载。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton, QSizePolicy

from core.selection import ScriptureSelection
from .panel import ScriptureSearchWidget


def attach_fulltext_search(window):
    """在主窗口工具栏挂载「经文搜索」按钮与 Ctrl+F。"""
    window._scripture_search_widget = None

    button = QPushButton("经文搜索")
    button.setObjectName("scriptureSearchToolbarButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(48)
    button.setMinimumWidth(64)
    button.setToolTip("搜索整本圣经经文  Ctrl+F")
    button.clicked.connect(lambda: _toggle(window))
    before = getattr(window.toolbar, "_search_anchor_action", None)
    if before is not None:
        window.toolbar.insertWidget(before, button)
    else:
        window.toolbar.addWidget(button)
    window.scripture_search_button = button

    shortcut = QShortcut(QKeySequence("Ctrl+F"), window)
    shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
    shortcut.activated.connect(lambda: _toggle(window))
    window._scripture_search_shortcut = shortcut

    _ensure_panel(window)
    window._scripture_search_widget.hide()


def _ensure_panel(window):
    """把搜索面板嵌进主窗口中央布局，高度随窗口一起变化。"""
    widget = getattr(window, "_scripture_search_widget", None)
    if widget is not None:
        return widget

    central = window.centralWidget()
    widget = ScriptureSearchWidget(window.db, window.config, central, theme=window.theme)
    widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    widget.result_activated.connect(lambda result: _activate(window, result))
    widget.result_project_requested.connect(lambda result: _project(window, result))
    widget.close_requested.connect(widget.hide)

    layout = central.layout()
    if layout is not None:
        layout.addWidget(widget)

    window._scripture_search_widget = widget
    return widget


def _toggle(window):
    widget = _ensure_panel(window)
    if widget.isVisible():
        widget.hide()
        return

    widget.apply_theme(window.theme)
    widget.show()
    widget.raise_()
    widget.search_input.setFocus()
    widget.search_input.selectAll()


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


def _project(window, result):
    selection = _selection_from_result(window, result)
    if selection is None:
        return
    window._load_selection(selection)
    window.nav_panel.add_selection_to_history(selection)
    window.nav_panel.sync_from_selection(selection)
    if not window.extension_window or not window.extension_window.isVisible():
        window._show_extension()
