from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import QPushButton

from ui import scripture_search as _scripture_search
from ui.scripture_result_compat import ScriptureResultWidget
from ui.themes import THEMES, theme_tokens

# 旧版搜索面板使用了 text_disabled 令牌，而当前统一主题令牌已改为 text_faint。
# 在兼容层补齐旧字段，避免恢复旧页面时破坏当前主题系统。
for _tokens in THEMES.values():
    _tokens.setdefault("text_disabled", _tokens.get("text_faint", _tokens["text_muted"]))

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


def _polish_search_panel(widget):
    """只调整旧搜索面板的视觉层，不触碰搜索逻辑。"""
    t = theme_tokens(widget.theme)

    # 匹配方式保持旧版的无圆点选择样式，四个选项高度统一。
    radio_style = f"""
        QRadioButton {{
            background:{t['control']}; color:{t['text_muted']};
            border:1px solid {t['border']}; border-radius:8px;
            padding:6px 10px; spacing:0; font-size:12px; min-height:18px;
        }}
        QRadioButton:hover {{
            background:{t['control_hover']}; color:{t['text']};
            border-color:{t['border_strong']};
        }}
        QRadioButton:checked {{
            background:{t['accent_soft']}; color:{t['accent_text']};
            border-color:{t['accent']}; font-weight:600;
        }}
        QRadioButton::indicator {{
            width:0px; height:0px; margin:0; padding:0; border:none;
        }}
    """
    for radio in (
        widget.fuzzy_radio,
        widget.exact_radio,
        widget.all_radio,
        widget.any_radio,
    ):
        radio.setStyleSheet(radio_style)
        radio.setFixedHeight(32)

    # 搜索框和“搜索”按钮强制使用完全相同的高度，避免 Qt 默认 sizeHint
    # 受字体、边框和平台样式影响而出现视觉高低不一致。
    search_button = widget.findChild(QPushButton, "scriptureSearchButton")
    if search_button is not None:
        search_button.setFixedHeight(44)
        search_button.setFixedWidth(82)

    search_input = widget.findChild(type(widget.search_input), "scriptureSearchInput")
    if search_input is not None:
        search_input.setFixedHeight(44)

    # 结果区域统一内边距和卡片间距，避免第一项、最后一项看起来贴边。
    widget.result_layout.setContentsMargins(0, 4, 4, 6)
    widget.result_layout.setSpacing(10)

    # 最近搜索行也统一节奏。
    widget.history_layout.setContentsMargins(4, 4, 4, 4)
    widget.history_layout.setSpacing(5)


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
