"""方向键导航补丁：按逻辑连续节移动，并保持当前滚动位置。"""

from PyQt6.QtWidgets import QApplication

from .selection import ScriptureSelection


def _logical_range(db, book, chapter, verse):
    """返回物理节所属逻辑单位的起止节号。"""
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


def _next_logical_start(db, book, chapter, verse):
    """取得当前逻辑单位之后的下一个逻辑单位起点。"""
    _start, end = _logical_range(db, book, chapter, verse)
    candidate = end + 1
    max_v = db.get_verse_count(book, chapter)
    if candidate > max_v:
        return None
    start, _end = _logical_range(db, book, chapter, candidate)
    return start


def _previous_logical_range(db, book, chapter, verse):
    """取得当前逻辑单位之前的逻辑单位范围。"""
    start, _end = _logical_range(db, book, chapter, verse)
    candidate = start - 1
    if candidate < 1:
        return None
    return _logical_range(db, book, chapter, candidate)


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


def _replace_history_selection(self, old_selection, new_selection):
    """方向键只修改当前历史项，不新增一条历史记录。"""
    history = getattr(self.nav_panel, "history", None)
    if not history:
        return

    for index, item in enumerate(history):
        if item == old_selection:
            history[index] = new_selection
            self.nav_panel._update_history_list(selected_index=index)
            self.nav_panel.history_changed.emit(
                [entry.to_history_entry() for entry in history]
            )
            return


def _load_and_restore(self, selection, scroll_y):
    old_selection = getattr(self, "current_selection", None)
    self._load_selection(selection)
    # 左右键是“修改当前历史项”，不是“新增历史记录”。
    if old_selection is not None:
        _replace_history_selection(self, old_selection, self.current_selection)
    self.nav_panel.sync_from_selection(self.current_selection)
    _restore_scroll(self, scroll_y)


def _add_verse_end(self):
    """右键：向后移动一个逻辑经文单位。"""
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    next_start = _next_logical_start(self.db, selection.book, span.chapter, span.end)
    if next_start is None:
        return
    _load_and_restore(
        self,
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, span.start, next_start
        ),
        scroll_y,
    )


def _remove_verse_end(self):
    """左键：向前移动一个逻辑经文单位。"""
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    current_start, _current_end = _logical_range(
        self.db, selection.book, span.chapter, span.end
    )

    if current_start > span.start:
        new_end = current_start - 1
        _prev_start, prev_end = _logical_range(
            self.db, selection.book, span.chapter, new_end
        )
        new_end = prev_end
        if new_end < span.start:
            return
        target_start = span.start
    else:
        previous = _previous_logical_range(
            self.db, selection.book, span.chapter, current_start
        )
        if previous is None:
            return
        target_start, new_end = previous

    _load_and_restore(
        self,
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, target_start, new_end
        ),
        scroll_y,
    )


def _add_verse_start(self):
    """Ctrl+右：向前端扩展一个逻辑经文单位。"""
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    previous = _previous_logical_range(
        self.db, selection.book, span.chapter, span.start
    )
    if previous is None:
        return
    prev_start, _prev_end = previous
    _load_and_restore(
        self,
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, prev_start, span.end
        ),
        scroll_y,
    )


def _remove_verse_start(self):
    """Ctrl+左：从前端移除一个逻辑经文单位。"""
    selection = self._simple_selection_or_none()
    if selection is None:
        return
    scroll_y = _current_scroll(self)
    span = selection.spans[0]
    start, end = _logical_range(
        self.db, selection.book, span.chapter, span.start
    )
    if end >= span.end:
        return
    new_start = end + 1
    new_start, _new_end = _logical_range(
        self.db, selection.book, span.chapter, new_start
    )
    if new_start > span.end:
        return
    _load_and_restore(
        self,
        ScriptureSelection.single_chapter(
            selection.book, span.chapter, new_start, span.end
        ),
        scroll_y,
    )


def install(MainWindow):
    MainWindow._add_verse_end = _add_verse_end
    MainWindow._remove_verse_end = _remove_verse_end
    MainWindow._add_verse_start = _add_verse_start
    MainWindow._remove_verse_start = _remove_verse_start
