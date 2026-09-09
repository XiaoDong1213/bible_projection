from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton

from ui.scripture_search import ScriptureSearchDialog
from ui.selection import ScriptureSelection


def install_scripture_search(window):
    """把独立经文搜索接入现有主窗口，不修改原书卷章节搜索。"""
    window._scripture_search_dialog = None

    button = QPushButton("经文搜索")
    button.setObjectName("scriptureSearchToolbarButton")
    button.setCursor(window.cursor().shape())
    button.setToolTip("搜索整本圣经经文  Ctrl+F")
    button.clicked.connect(lambda: _toggle(window))
    window.toolbar.addWidget(button)
    window.scripture_search_button = button

    shortcut = QShortcut(QKeySequence("Ctrl+F"), window)
    shortcut.setContext(QShortcut.Context.WindowShortcut)
    shortcut.activated.connect(lambda: _toggle(window))
    window._scripture_search_shortcut = shortcut


def _toggle(window):
    dialog = window._scripture_search_dialog
    if dialog is not None and dialog.isVisible():
        dialog.activateWindow()
        dialog.raise_()
        dialog.input.setFocus()
        return

    history = []
    if getattr(window, "config", None) is not None:
        try:
            history = window.config.load_scripture_search_history()
        except Exception:
            history = []

    dialog = ScriptureSearchDialog(
        window.db,
        on_select=lambda result: _activate(window, result),
        history=history,
        theme=window.theme,
        parent=window,
    )
    window._scripture_search_dialog = dialog
    dialog.setWindowTitle("经文搜索")
    dialog.setMinimumSize(720, 560)
    dialog.resize(720, max(560, min(window.height() - 80, 760)))
    dialog.setModal(False)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    dialog.input.setFocus()


def _selection_from_result(window, result):
    book = str(result.get("book", ""))
    chapter = int(result.get("chapter", 1))
    verse = int(result.get("verse", 1))
    max_verse = window.db.get_verse_count(book, chapter)
    if not max_verse:
        return None

    # “13~14”这类逻辑节的主节是13，14只是连接标记。
    label = str(result.get("verse_label", ""))
    if "~" in label:
        try:
            verse = int(label.split("~", 1)[0])
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

    dialog = getattr(window, "_scripture_search_dialog", None)
    if dialog is not None:
        dialog.raise_()
        dialog.activateWindow()
