from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton

from ui import scripture_search as _scripture_search
from ui.scripture_result_compat import ScriptureResultWidget
from ui.themes import THEMES

# 旧版搜索面板使用了 text_disabled 令牌，而当前统一主题令牌已改为 text_faint。
# 在兼容层补齐旧字段，避免恢复旧页面时破坏当前主题系统。
for _tokens in THEMES.values():
    _tokens.setdefault("text_disabled", _tokens.get("text_faint", _tokens["text_muted"]))

# 运行时向旧搜索模块注入兼容结果组件；使用 setattr 避免静态类型检查将其视为未知模块属性。
setattr(_scripture_search, "ScriptureResultWidget", ScriptureResultWidget)

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


def _polish_search_panel(widget):
    """只调整旧搜索面板的尺寸与布局，不覆盖主题样式。"""
    # 主题颜色统一由 ScriptureSearchWidget._apply_style() 管理。
    # 这里不要再给子控件设置独立 stylesheet，否则主题切换后会残留旧主题颜色。
    # 单选按钮的高度由面板样式统一控制，不在这里覆盖，避免出现高度不一致。
    search_button = widget.findChild(QPushButton, "scriptureSearchButton")
    if search_button is not None:
        search_button.setFixedSize(82, 34)

    widget.search_input.setFixedHeight(44)

    # 恢复历史版本的结果节奏：容器 0/4/4/0，卡片之间 8px。
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
