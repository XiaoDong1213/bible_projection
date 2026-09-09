from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QApplication, QPushButton

from ui.scripture_search import ScriptureSearchWidget
from ui.selection import ScriptureSelection


def install_scripture_search(window):
    """把独立经文搜索接入现有主窗口，不修改原书卷章节搜索。"""
    window._scripture_search_widget = None

    # 置顶、清屏、小标题统一尺寸，保持三个功能按钮视觉一致。
    for attr in ("topmost_btn", "clear_btn", "show_titles_btn"):
        button = getattr(window.toolbar, attr, None)
        if button is not None:
            button.setFixedSize(72, 30)

    # 显示设置 / 亮色之后单独分组，经文搜索作为最后一个独立入口。
    window.toolbar.addSeparator()

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

    widget = ScriptureSearchWidget(
        window.db, window.config, window, theme=window.theme
    )
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
