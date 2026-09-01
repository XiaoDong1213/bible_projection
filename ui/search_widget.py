import re

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .search import BookMatcher, SearchParser, SearchState
from .selection import ScriptureSelection
from .themes import search_panel_style


class SearchLineEdit(QLineEdit):
    """转发搜索框需要单独处理的按键。"""

    special_key = pyqtSignal(int)

    def keyPressEvent(self, event):
        key = event.key()
        special_keys = {
            Qt.Key.Key_Escape,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Space,
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        }
        if key in special_keys:
            self.special_key.emit(key)
            event.accept()
            return
        super().keyPressEvent(event)


class SearchWidget(QWidget):
    """提供书卷、章节和节范围搜索。"""

    search_triggered = pyqtSignal(object)
    close_requested = pyqtSignal()
    ALLOWED = re.compile(r"[A-Za-z0-9 :：.．。\-]")
    DEFAULT_HINT = "↑↓ 选择　·　Space 下一段　·　Enter 确认　·　同章如 3:16-18（跨章/跳节请用左侧）"

    def __init__(self, db, parent=None, theme="dark"):
        super().__init__(parent)
        self.db = db
        self.matcher = BookMatcher(db)
        self.parser = SearchParser()
        self.state = SearchState()
        self._scroll_anim = None
        self._theme = theme if theme in ("dark", "light") else "dark"

        self.setObjectName("searchPanel")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(660)
        self.setMaximumWidth(900)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.setSpacing(0)

        self.search_input = SearchLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setMinimumHeight(48)
        self.search_input.setPlaceholderText("输入书卷简拼、章节或同章节号")
        self.search_input.setClearButtonEnabled(False)
        self.search_input.textEdited.connect(self._on_text_edited)
        self.search_input.special_key.connect(self._on_special_key)
        layout.addWidget(self.search_input)

        self.hint_label = QLabel(self.DEFAULT_HINT)
        self.hint_label.setObjectName("searchHint")
        self.hint_label.setMinimumHeight(30)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.setObjectName("searchCandidates")
        self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_list.setFrameShape(QListWidget.Shape.NoFrame)
        self.result_list.setSpacing(4)
        self.result_list.setUniformItemSizes(True)
        self.result_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.result_list)

        self.apply_theme(self._theme)
        self._resize_result_area()

    def apply_theme(self, theme="dark"):
        """与主界面共用同一套设计令牌。"""
        self._theme = theme if theme in ("dark", "light") else "dark"
        self.setStyleSheet(search_panel_style(self._theme))

    def showEvent(self, event):
        super().showEvent(event)
        self.state = SearchState()
        self.result_list.clear()
        self._resize_result_area()
        self._update_hint(self.DEFAULT_HINT)
        self.apply_theme(self._theme)
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _update_hint(self, text):
        self.hint_label.setText(text)
        self._resize_result_area()

    def _resize_result_area(self):
        count = self.result_list.count()
        visible = min(count, 8)
        if visible:
            row_h = max(42, self.result_list.sizeHintForRow(0))
            height = visible * row_h + max(0, visible - 1) * 4 + 8
            self.result_list.setFixedHeight(height)
        else:
            self.result_list.setFixedHeight(0)
        self.adjustSize()

    def _set_text(self, text, converted=None, cursor=None):
        self.state.formatting = True
        try:
            value = str(text or "")
            self.search_input.setText(value)
            if cursor is None:
                self.search_input.setCursorPosition(len(value))
            else:
                self.search_input.setCursorPosition(max(0, min(int(cursor), len(value))))
        finally:
            self.state.formatting = False
        if converted is not None:
            self.state.converted_book = bool(converted)

    def _chapter_count(self, book):
        try:
            return int(
                self.db.book_meta.get(book, {}).get("chapter_count")
                or self.db.get_chapter_count(book)
                or 0
            )
        except Exception:
            return 0

    def _verse_count(self, book, chapter):
        try:
            return int(self.db.get_verse_count(book, chapter) or 0)
        except Exception:
            return 0

    def _convert_book(self, book):
        self.state.selected_book = book
        self.state.stage = "chapter"
        self.state.space_mode = False
        self.state.converted_book = True
        self._set_text(book, True)
        self.result_list.clear()
        self._resize_result_area()
        self._update_hint(f"已识别为 {book}　·　请输入章节　·　Space 进入节号")
        self.search_input.setFocus()

    def _show_candidates(self, books):
        self.result_list.setUpdatesEnabled(False)
        try:
            self.result_list.clear()
            for index, book in enumerate(books, 1):
                code = self.matcher.code(book).upper()
                try:
                    short = self.db._short_name(book)
                except Exception:
                    short = book
                item = QListWidgetItem(f"{index:02d}    {code or short}    {book}")
                item.setData(Qt.ItemDataRole.UserRole, book)
                self.result_list.addItem(item)
        finally:
            self.result_list.setUpdatesEnabled(True)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)
        self._resize_result_area()

    def _move_highlight(self, delta):
        count = self.result_list.count()
        if not count:
            return
        row = max(0, min(self.result_list.currentRow() + delta, count - 1))
        self.result_list.setCurrentRow(row)
        item = self.result_list.item(row)
        if item:
            self._smooth_scroll_to(item)

    def _smooth_scroll_to(self, item):
        bar = self.result_list.verticalScrollBar()
        row_h = max(1, self.result_list.sizeHintForRow(0))
        target = self.result_list.indexFromItem(item).row() * (row_h + 4)
        target = max(bar.minimum(), min(target, bar.maximum()))
        if self._scroll_anim:
            self._scroll_anim.stop()
        self._scroll_anim = QPropertyAnimation(bar, b"value", self)
        self._scroll_anim.setDuration(160)
        self._scroll_anim.setStartValue(bar.value())
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._scroll_anim.start()

    def _select_current_book(self):
        item = self.result_list.currentItem()
        if item:
            book = item.data(Qt.ItemDataRole.UserRole)
            if book:
                self._convert_book(book)

    def _suffix(self):
        book = self.state.selected_book
        text = self.search_input.text()
        if book and text.startswith(book):
            return text[len(book):]
        return ""

    def _space_after_chapter(self):
        value = self._suffix().strip()
        if not re.fullmatch(r"\d+", value):
            return
        chapter = int(value)
        maximum = self._chapter_count(self.state.selected_book)
        if not 1 <= chapter <= maximum:
            self._update_hint(f"章节超出范围　·　本书最多 {maximum} 章")
            return
        self.state.stage = "verse"
        self._set_text(f"{self.state.selected_book} {chapter}:")
        self._update_hint("请输入开始节　·　Space 生成节范围")

    def _space_after_verse(self):
        match = re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)", self._suffix().strip())
        if not match:
            return
        chapter, verse = map(int, match.groups())
        maximum = self._verse_count(self.state.selected_book, chapter)
        if not 1 <= verse <= maximum:
            self._update_hint(f"本章最多 {maximum} 节")
            return
        self.state.space_mode = True
        self._set_text(f"{self.state.selected_book} {chapter}:{verse}-")
        self._update_hint(f"请输入结束节　·　范围 {verse}–{maximum}")

    def _delete_segment(self, key=Qt.Key.Key_Backspace):
        """书卷名整段删除；其后内容逐字删除。"""
        edit = self.search_input
        text = edit.text()
        pos = edit.cursorPosition()
        book = self.state.selected_book

        if not book:
            new_text, new_pos = self._apply_char_delete(text, pos, key, edit)
            self._set_text(new_text, cursor=new_pos)
            self._refresh_book_state(self.search_input.text())
            self.search_input.setFocus()
            return

        if not text.startswith(book):
            self._reset_book_search()
            return

        book_end = len(book)
        suffix = text[book_end:]

        # 书卷后没有实质内容，或光标/选区碰到书卷名 → 整本删除
        if not suffix.strip():
            self._reset_book_search()
            return
        if edit.hasSelectedText() and edit.selectionStart() < book_end:
            self._reset_book_search()
            return
        if key == Qt.Key.Key_Backspace and pos <= book_end and not edit.hasSelectedText():
            self._reset_book_search()
            return
        if key == Qt.Key.Key_Delete and pos < book_end and not edit.hasSelectedText():
            self._reset_book_search()
            return

        new_text, new_pos = self._apply_char_delete(text, pos, key, edit)
        # 保护书卷前缀不被逐字拆掉
        if not new_text.startswith(book):
            self._reset_book_search()
            return
        self._set_text(new_text, converted=True, cursor=new_pos)
        self._refresh_selected(book, new_text[len(book):])
        self.search_input.setFocus()

    @staticmethod
    def _apply_char_delete(text, pos, key, edit):
        if edit.hasSelectedText():
            start = edit.selectionStart()
            end = start + len(edit.selectedText())
            return text[:start] + text[end:], start
        if key == Qt.Key.Key_Backspace:
            if pos <= 0:
                return text, pos
            return text[: pos - 1] + text[pos:], pos - 1
        if key == Qt.Key.Key_Delete:
            if pos >= len(text):
                return text, pos
            return text[:pos] + text[pos + 1 :], pos
        return text, pos

    def _reset_book_search(self):
        self._set_text("")
        self.state = SearchState()
        self.result_list.clear()
        self._resize_result_area()
        self._refresh_book_state("")
        self.search_input.setFocus()

    def _refresh_book_state(self, text):
        self.state.stage = "book"
        self.state.selected_book = None
        self.state.converted_book = False
        self.state.space_mode = False
        self.result_list.clear()
        query = text.strip()
        if not query:
            self._update_hint(self.DEFAULT_HINT)
            return
        if re.fullmatch(r"[A-Za-z]+", query):
            candidates = self.matcher.candidates(query)
            if len(query) == 1 and len(candidates) == 1:
                self._convert_book(candidates[0])
                return
            if len(candidates) == 1 and self.matcher.code(candidates[0]) == self.matcher.normalize(query):
                self._convert_book(candidates[0])
                return
            if candidates:
                self._show_candidates(candidates)
                self._update_hint("↑↓ 选择书卷　·　Space 确认当前项　·　Enter 确认")
                return
            if len(query) == 1:
                first = [b for b in self.db.book_names if self.matcher.code(b)[:1] == query.lower()]
                if len(first) == 1:
                    self._convert_book(first[0])
                    return
            exact = self.matcher.exact(query)
            if exact:
                self._convert_book(exact)
                return
        self._update_hint(self.DEFAULT_HINT)

    def _update_hint_for_stage(self):
        if self.state.stage == "chapter":
            self._update_hint(f"已选择 {self.state.selected_book}　·　请输入章节　·　Space 进入节号")
        elif self.state.stage == "verse":
            self._update_hint("请输入开始节　·　Space 生成节范围")
        elif self.state.space_mode:
            self._update_hint("请输入结束节")

    def _on_special_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
        elif key == Qt.Key.Key_Up:
            self._move_highlight(-1)
        elif key == Qt.Key.Key_Down:
            self._move_highlight(1)
        elif key == Qt.Key.Key_Space:
            if self.state.stage == "book" and self.result_list.count():
                self._select_current_book()
            elif self.state.stage == "chapter" and self.state.selected_book:
                self._space_after_chapter()
            elif self.state.stage == "verse" and self.state.selected_book:
                self._space_after_verse()
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._delete_segment(key)

    def _on_text_edited(self, text):
        if self.state.formatting:
            return
        if self.state.stage == "book":
            clean = "".join(c for c in text if self.ALLOWED.fullmatch(c))
            if clean != text:
                self._set_text(clean)
                text = clean
            self._refresh_book_state(text)
            return
        book = self.state.selected_book
        if not book:
            return
        if not text.startswith(book):
            self._set_text(book, True)
            return
        suffix = text[len(book):]
        if not re.fullmatch(r"[\s0-9:：.．。\-]*", suffix):
            suffix = re.sub(r"[^0-9 :：.．。\-]", "", suffix)
            self._set_text(book + suffix, True)
        self._refresh_selected(book, suffix)

    def _refresh_selected(self, book, suffix):
        value = self.parser.normalize(suffix)
        self.result_list.clear()
        if not value:
            self._resize_result_area()
            self._update_hint_for_stage()
            return

        if re.search(r"-\s*$", value):
            self._update_hint("请输入结束节，例如 3:16-18")
            self._resize_result_area()
            return

        selection = self.parser.parse_suffix(
            book, value, self._chapter_count, self._verse_count
        )
        if selection:
            self._add_selection_item(selection)
            if selection.primary_start == 1 and selection.is_simple:
                span = selection.spans[0]
                # 整章：start=1 且 end=max 时提示整章；单节 1 也是 start==end
                if span.start == span.end:
                    self._update_hint("Enter 确认投影")
                elif ":" not in value and "." not in value:
                    self._update_hint(f"{book} 第 {span.chapter} 章　·　Enter 确认整章")
                else:
                    self._update_hint("Enter 确认投影")
            else:
                self._update_hint("Enter 确认投影")
            return

        match = self.parser.parse_reference(value)
        if not match:
            self._update_hint("同章格式：章　或　章:节　或　章:节-节（跨章/跳节用左侧）")
            self._resize_result_area()
            return

        chapter_text, verse_text, end_text = match
        chapter = int(chapter_text)
        max_chapter = self._chapter_count(book)
        if not 1 <= chapter <= max_chapter:
            self._update_hint(f"章节超出范围　·　本书最多 {max_chapter} 章")
            return
        if verse_text is None:
            max_v = self._verse_count(book, chapter)
            selection = ScriptureSelection.single_chapter(
                book, chapter, 1, max_v, max_verse=max_v
            )
            self._add_selection_item(selection)
            self._update_hint(f"{book} 第 {chapter} 章　·　Enter 确认整章")
            return
        verse = int(verse_text)
        max_verse = self._verse_count(book, chapter)
        if not 1 <= verse <= max_verse:
            self._update_hint(f"第 {chapter} 章最多 {max_verse} 节")
            return
        if end_text is None:
            selection = ScriptureSelection.single_chapter(book, chapter, verse, verse)
            self._add_selection_item(selection)
            self._update_hint("Enter 确认投影")
            return
        end = int(end_text)
        if end < verse:
            self._update_hint(f"结束节不能小于开始节 {verse}")
            return
        if end > max_verse:
            self._update_hint(f"本章最多 {max_verse} 节，不能输入 {end}")
            return
        selection = ScriptureSelection.single_chapter(book, chapter, verse, end)
        self._add_selection_item(selection)
        self._update_hint("Enter 确认投影")

    def _add_selection_item(self, selection: ScriptureSelection):
        item = QListWidgetItem(f"01    {selection.label()}")
        item.setData(Qt.ItemDataRole.UserRole, selection)
        self.result_list.addItem(item)
        self.result_list.setCurrentRow(0)
        self._resize_result_area()

    def _parse(self, text):
        return self.parser.parse(
            text,
            self.state.selected_book,
            self.matcher.exact,
            self._chapter_count,
            self._verse_count,
            book_names=self.db.book_names,
        )

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        if isinstance(data, ScriptureSelection):
            self.search_triggered.emit(data)
            self.close_requested.emit()
            return
        if isinstance(data, tuple) and len(data) == 4 and data[2] is not None:
            selection = ScriptureSelection.from_legacy(*data)
            self.search_triggered.emit(selection)
            self.close_requested.emit()
            return
        book = data[0] if isinstance(data, tuple) else data
        self._convert_book(book)

    def _on_confirm(self):
        if self.state.confirming:
            return
        self.state.confirming = True
        try:
            parsed = self._parse(self.search_input.text())
            if parsed:
                self.search_triggered.emit(parsed)
                self.close_requested.emit()
            elif self.state.stage == "book" and self.result_list.count():
                self._select_current_book()
            else:
                current = self.result_list.currentItem()
                if current and isinstance(current.data(Qt.ItemDataRole.UserRole), ScriptureSelection):
                    self.search_triggered.emit(current.data(Qt.ItemDataRole.UserRole))
                    self.close_requested.emit()
                else:
                    self._update_hint("请输入有效的书卷或同章节范围（跨章/跳节用左侧）")
        finally:
            self.state.confirming = False

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_confirm()
            event.accept()
            return
        super().keyPressEvent(event)
