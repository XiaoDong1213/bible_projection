"""方向键导航补丁：按逻辑连续节移动，并保持当前滚动位置。"""

from PyQt6.QtWidgets import QApplication

from .selection import ScriptureSelection


def _logical_end(db, book, chapter, verse):
    """返回物理节所属逻辑单位的结束节号。

    get_verse_display_info 当前返回 (label, text)，逻辑起止范围需要
    从 label 解析，兼容普通节号和连续节号。
    """
    label, _text = db.get_verse_display_info(book, chapter, verse)
    text = str(label or "").strip()
    if "-" in text:
        start_text, end_text = text.split("-", 1)
        try:
            return int(start_text), int(end_text)
        except ValueError:
            pass
    try:
        value = int(text)
    except ValueError:
        value = int(verse)
    return value, value


def _logical_start(db, book, chapter, verse):
    """返回物理节所属逻辑单位的起始/结束节号。"""
    return _logical_end(db, book, chapter, verse)


def _restore_scroll(window, scroll_y):
    """恢复方向键操作前的实际滚动位置。"""
    QApplication.processEvents()
    window.scripture_display.text_display.set_scroll_y(scroll_y, emit=False)
    window.scripture_display.update()
    if window.extension_window and window.extension_window.isVisible():
        window._sync_extension_scroll()


def _current_scroll(window):
    try:
        return float(window.scripture_display.text_display.scroll_y())
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _add_verse_end(self):
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    _start, logical_end = _logical_end(self.db, selection.book, span.chapter, span.end)
    max_v = self.db.get_verse_count(selection.book, span.chapter)
    next_verse = logical_end + 1
    if next_verse > max_v:
        return
    self._load_selection(
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, span.start, next_verse
        )
    )
    self.nav_panel.sync_from_selection(self.current_selection)
    _restore_scroll(self, scroll_y)


def _remove_verse_end(self):
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    logical_start, _logical_end_value = _logical_end(
        self.db, selection.book, span.chapter, span.end
    )
    if span.end <= span.start:
        return
    new_end = logical_start
    if new_end < span.start:
        return
    self._load_selection(
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, span.start, new_end
        )
    )
    self.nav_panel.sync_from_selection(self.current_selection)
    _restore_scroll(self, scroll_y)


def _add_verse_start(self):
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    logical_start, _logical_end_value = _logical_start(
        self.db, selection.book, span.chapter, span.start
    )
    previous_verse = logical_start - 1
    if previous_verse < 1:
        return
    _prev_start, _prev_end = _logical_start(
        self.db, selection.book, span.chapter, previous_verse
    )
    self._load_selection(
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, _prev_start, span.end
        )
    )
    self.nav_panel.sync_from_selection(self.current_selection)
    _restore_scroll(self, scroll_y)


def _remove_verse_start(self):
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    logical_start, logical_end = _logical_start(
        self.db, selection.book, span.chapter, span.start
    )
    if logical_start >= span.end:
        return
    new_start = logical_end + 1
    if new_start > span.end:
        return
    self._load_selection(
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, new_start, span.end
        )
    )
    self.nav_panel.sync_from_selection(self.current_selection)
    _restore_scroll(self, scroll_y)


# 安装到 MainWindow，避免改动主窗口的大块业务代码。
def install(MainWindow):
    MainWindow._add_verse_end = _add_verse_end
    MainWindow._remove_verse_end = _remove_verse_end
    MainWindow._add_verse_start = _add_verse_start
    MainWindow._remove_verse_start = _remove_verse_start
