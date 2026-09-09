from PyQt6.QtCore import Qt

from .search_widget import SearchWidget
from . import arrow_navigation_patch


def _on_special_key(self, key):
    if key == Qt.Key.Key_Escape:
        self.close_requested.emit()
        return

    if key == Qt.Key.Key_Up:
        self._move_highlight(-1)
        return

    if key == Qt.Key.Key_Down:
        self._move_highlight(1)
        return

    if key == Qt.Key.Key_Space:
        if self.state.stage == "book":
            # 即使上一次输入过错误内容，只要当前内容已经重新成为合法书卷简拼，
            # Space 仍然必须能够确认当前书卷；不能因为 result_list 为空而吞掉按键。
            item = self.result_list.currentItem()
            if item:
                book = item.data(Qt.ItemDataRole.UserRole)
                if book:
                    self._convert_book(book)
                    return

            query = self.search_input.text().strip()
            if query:
                exact = self.matcher.exact(query)
                if exact:
                    self._convert_book(exact)
                    return
                candidates = self.matcher.candidates(query)
                if len(candidates) == 1:
                    self._convert_book(candidates[0])
                    return

            self._refresh_book_state(self.search_input.text())
            return

        if self.state.stage == "chapter" and self.state.selected_book:
            self._space_after_chapter()
            return

        if self.state.stage == "verse" and self.state.selected_book:
            self._space_after_verse()
            return

    if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
        self._delete_segment(key)


SearchWidget._on_special_key = _on_special_key
arrow_navigation_patch.install(__import__("main_window").MainWindow)
