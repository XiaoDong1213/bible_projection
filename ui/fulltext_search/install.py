"""全文经文搜索面板挂载。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton, QSizePolicy

from core.selection import ScriptureSelection


def attach_fulltext_search(window):
    """在主窗口工具栏挂载「经文搜索」按钮与 Ctrl+F（面板首次打开时再创建）。"""
    window._scripture_search_widget = None

    button = QPushButton("经文搜索")
    button.setObjectName("scriptureSearchToolbarButton")
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setFixedHeight(44)
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


def _ensure_panel(window):
    """首次打开时再创建搜索面板，挂到主分割条右侧。"""
    widget = getattr(window, "_scripture_search_widget", None)
    if widget is not None:
        return widget

    from .panel import ScriptureSearchWidget

    splitter = getattr(window, "main_splitter", None)
    parent = splitter if splitter is not None else window.centralWidget()
    widget = ScriptureSearchWidget(window.db, window.config, parent, theme=window.theme)
    widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
    widget.result_activated.connect(lambda result: _activate(window, result))
    widget.result_project_requested.connect(lambda result: _project(window, result))
    widget.close_requested.connect(lambda: _hide_panel(window))
    widget.hide()

    if splitter is not None:
        splitter.addWidget(widget)
        idx = splitter.count() - 1
        splitter.setStretchFactor(idx, 0)
        handle = splitter.handle(idx)
        if handle is not None:
            handle.setEnabled(True)

    window._scripture_search_widget = widget
    return widget


def _hide_panel(window):
    widget = getattr(window, "_scripture_search_widget", None)
    if widget is None:
        return
    widget.hide()
    splitter = getattr(window, "main_splitter", None)
    if splitter is None or splitter.count() < 3:
        return
    sizes = splitter.sizes()
    extra = sizes[2] if len(sizes) > 2 else 0
    if extra <= 0:
        return
    sizes[1] = sizes[1] + extra
    sizes[2] = 0
    splitter.setSizes(sizes)


def _toggle(window):
    widget = _ensure_panel(window)
    if widget.isVisible():
        _hide_panel(window)
        return

    widget.apply_theme(window.theme)
    widget.show()
    splitter = getattr(window, "main_splitter", None)
    if splitter is not None and splitter.count() >= 3:
        sizes = splitter.sizes()
        width = int(getattr(widget, "PANEL_WIDTH", 520))
        if len(sizes) >= 3 and sizes[2] < width // 2:
            take = min(width, max(0, sizes[1] - 200))
            sizes[1] = sizes[1] - take
            sizes[2] = take
            splitter.setSizes(sizes)
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
