import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal


class SearchLineEdit(QLineEdit):
    special_key = pyqtSignal(int)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape,
                   Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Space,
                   Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.special_key.emit(key)
            event.accept()
            return
        super().keyPressEvent(event)


class SearchWidget(QWidget):
    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()
    ALLOWED = re.compile(r"[A-Za-z0-9 :：.．。\-]")

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._formatting = False
        self._converted_book = False
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self._candidate_cache = {}
        self._confirming = False

        self.setObjectName("searchPanel")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(520)
        self.setMaximumWidth(620)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        self.search_input = SearchLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setMinimumHeight(42)
        self.search_input.setClearButtonEnabled(False)
        self.search_input.setPlaceholderText("输入书卷简拼")
        self.search_input.textEdited.connect(self._on_text_edited)
        self.search_input.special_key.connect(self._on_special_key)
        layout.addWidget(self.search_input)

        self.hint_label = QLabel()
        self.hint_label.setObjectName("searchHint")
        self.hint_label.setMinimumHeight(28)
        self.hint_label.setMaximumHeight(28)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.setObjectName("searchCandidates")
        self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.result_list.setSpacing(1)
        self.result_list.setUniformItemSizes(True)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.result_list)

        self.setFocusProxy(self.search_input)
        self._apply_theme()
        self._reset_view()

    def _apply_theme(self):
        # 只使用 Qt 当前 palette，不写死亮色或暗色背景，也不在 changeEvent 中重复设置。
        self.setStyleSheet("""
            QWidget#searchPanel {
                background: palette(window);
                color: palette(window-text);
                border: 1px solid palette(mid);
                border-radius: 10px;
            }
            QLineEdit#searchInput {
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 7px;
                padding: 0 12px;
                selection-background-color: palette(highlight);
                selection-color: palette(highlighted-text);
            }
            QLineEdit#searchInput:focus {
                border: 1px solid palette(highlight);
            }
            QLabel#searchHint {
                background: palette(window);
                color: palette(mid);
                border: none;
                padding: 0 5px;
            }
            QListWidget#searchCandidates {
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 7px;
                padding: 2px;
                outline: none;
            }
            QListWidget#searchCandidates::item {
                min-height: 30px;
                padding: 0 9px;
                border-radius: 5px;
            }
            QListWidget#searchCandidates::item:hover {
                background: palette(alternate-base);
            }
            QListWidget#searchCandidates::item:selected {
                background: palette(highlight);
                color: palette(highlighted-text);
            }
            QScrollBar:vertical {
                width: 7px;
                background: transparent;
                margin: 3px 1px 3px 0;
            }
            QScrollBar::handle:vertical {
                min-height: 22px;
                background: palette(mid);
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                height: 0px;
                background: transparent;
            }
        """)

    def _reset_view(self):
        self._formatting = False
        self._converted_book = False
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self._confirming = False
        self.result_list.clear()
        self._update_hint("输入简拼　↑↓选择　空格选择　Enter确认　Esc退出")

    def showEvent(self, event):
        super().showEvent(event)
        self._reset_view()
        self._apply_theme()
        self.search_input.setFocus(Qt.FocusReason.PopupFocusReason)
        self.search_input.selectAll()

    def _update_hint(self, text):
        self.hint_label.setText(text)
        self._resize_result_area()

    def _resize_result_area(self):
        count = self.result_list.count()
        if count:
            rows = min(count, 8)
            row_h = max(32, self.result_list.sizeHintForRow(0))
            self.result_list.setFixedHeight(rows * row_h + 6)
        else:
            self.result_list.setFixedHeight(0)
        self.adjustSize()

    @staticmethod
    def _norm(value):
        return re.sub(r"[\s._-]+", "", str(value or "").strip().lower())

    def _code(self, book):
        return self._norm(self.db.book_meta.get(book, {}).get("pinyin", ""))

    def _candidates(self, query):
        query = self._norm(query)
        if query in self._candidate_cache:
            return self._candidate_cache[query]
        result = [b for b in self.db.book_names if self._code(b).startswith(query)] if query else []
        self._candidate_cache[query] = result
        return result

    def _exact(self, query):
        query = self._norm(query)
        for book in self.db.book_names:
            if self._code(book) == query:
                return book
        return None

    def _chapter_count(self, book):
        try:
            return int(self.db.book_meta.get(book, {}).get("chapter_count") or self.db.get_chapter_count(book) or 0)
        except Exception:
            return 0

    def _verse_count(self, book, chapter):
        try:
            return int(self.db.get_verse_count(book, chapter) or 0)
        except Exception:
            return 0

    def _set_text(self, text, converted=None):
        value = str(text or "")
        self._formatting = True
        try:
            self.search_input.setText(value)
            self.search_input.setCursorPosition(len(value))
        finally:
            self._formatting = False
        if converted is not None:
            self._converted_book = bool(converted)

    def _show_candidates(self, books):
        self.result_list.setUpdatesEnabled(False)
        try:
            self.result_list.clear()
            for i, book in enumerate(books[:30], 1):
                code = self._code(book).upper()
                short = self.db._short_name(book)
                item = QListWidgetItem(f"{i}.   {code or short}   {book}")
                item.setData(Qt.ItemDataRole.UserRole, book)
                self.result_list.addItem(item)
        finally:
            self.result_list.setUpdatesEnabled(True)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)
        self._resize_result_area()

    def _move_highlight(self, delta):
        if not self.result_list.count():
            return
        row = max(0, min(self.result_list.currentRow() + delta, self.result_list.count() - 1))
        self.result_list.setCurrentRow(row)
        self.result_list.scrollToItem(self.result_list.currentItem())

    def _select_current_book(self):
        item = self.result_list.currentItem()
        if item is None:
            return
        book = item.data(Qt.ItemDataRole.UserRole)
        if not book:
            return
        self._selected_book = book
        self._stage = "chapter"
        self._space_mode = False
        self._set_text(book, True)
        self.result_list.clear()
        self._resize_result_area()
        self._update_hint(f"已选择 {book}　请输入章节　空格进入节号")
        self.search_input.setFocus()

    def _suffix(self):
        if self._selected_book and self.search_input.text().startswith(self._selected_book):
            return self.search_input.text()[len(self._selected_book):]
        return ""

    def _space_after_chapter(self):
        value = self._suffix().strip()
        if not re.fullmatch(r"\d+", value):
            self._update_hint("请输入有效章节号")
            return
        chapter = int(value)
        maximum = self._chapter_count(self._selected_book)
        if not 1 <= chapter <= maximum:
            self._update_hint(f"章节超出范围，本书最多 {maximum} 章")
            return
        self._stage = "verse"
        self._set_text(f"{self._selected_book} {chapter}:")
        self._update_hint("请输入开始节　空格生成节范围分隔符 -")

    def _space_after_verse(self):
        value = self._suffix().strip()
        match = re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)", value)
        if not match:
            self._update_hint("请输入有效的章节:节")
            return
        chapter, verse = map(int, match.groups())
        maximum = self._verse_count(self._selected_book, chapter)
        if not 1 <= verse <= maximum:
            self._update_hint(f"本章最多 {maximum} 节")
            return
        self._space_mode = True
        self._set_text(f"{self._selected_book} {chapter}:{verse}-")
        self._update_hint(f"请输入结束节　范围 {verse}-{maximum}")

    def _delete_segment(self):
        if not self._selected_book:
            text = self.search_input.text()
            self._set_text(text[:-1] if text else "")
            self._refresh_book_state(self.search_input.text())
            return
        text = self.search_input.text()
        book = self._selected_book
        suffix = text[len(book):] if text.startswith(book) else ""
        patterns = [
            (r"\s*(\d+)\s*:\s*(\d+)\s*-\s*(\d+)\s*$", lambda m: f"{book} {m.group(1)}:{m.group(2)}-", "verse_range"),
            (r"\s*(\d+)\s*:\s*(\d+)\s*-\s*$", lambda m: f"{book} {m.group(1)}:{m.group(2)}", "verse"),
            (r"\s*(\d+)\s*:\s*(\d+)\s*$", lambda m: f"{book} {m.group(1)}:", "verse"),
            (r"\s*(\d+)\s*:\s*$", lambda m: f"{book} {m.group(1)}", "chapter"),
            (r"\s*(\d+)\s*$", lambda m: book, "chapter"),
        ]
        for pattern, maker, stage in patterns:
            match = re.fullmatch(pattern, suffix)
            if match:
                self._set_text(maker(match))
                self._stage = stage
                self._space_mode = stage == "verse_range"
                self._refresh_selected(book, self._suffix())
                self._update_hint_for_stage()
                return
        self._set_text("")
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self._converted_book = False
        self.result_list.clear()
        self._refresh_book_state("")
        self.search_input.setFocus()

    def _refresh_book_state(self, text):
        self._stage = "book"
        self._selected_book = None
        self._converted_book = False
        self._space_mode = False
        self.result_list.clear()
        query = text.strip()
        if re.fullmatch(r"[A-Za-z]+", query):
            candidates = self._candidates(query)
            if candidates:
                self._show_candidates(candidates)
        self._update_hint("输入简拼　↑↓选择　空格选择　Enter确认　Esc退出")

    def _update_hint_for_stage(self):
        if self._stage == "chapter":
            self._update_hint(f"已选择 {self._selected_book}　请输入章节　空格进入节号")
        elif self._stage == "verse":
            self._update_hint("请输入开始节　空格生成节范围分隔符 -")
        elif self._space_mode:
            self._update_hint("请输入结束节")

    def _on_special_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_confirm()
        elif key == Qt.Key.Key_Escape:
            self.close_requested.emit()
        elif key == Qt.Key.Key_Up:
            self._move_highlight(-1)
        elif key == Qt.Key.Key_Down:
            self._move_highlight(1)
        elif key == Qt.Key.Key_Space:
            if self._stage == "book" and self.result_list.count():
                self._select_current_book()
            elif self._stage == "chapter" and self._selected_book:
                self._space_after_chapter()
            elif self._stage == "verse" and self._selected_book:
                self._space_after_verse()
        elif key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self._delete_segment()

    def _on_text_edited(self, text):
        if self._formatting:
            return
        if self._stage == "book":
            clean = "".join(c for c in text if self.ALLOWED.fullmatch(c))
            if clean != text:
                self._set_text(clean)
                text = clean
            self._refresh_book_state(text)
            return
        if not self._selected_book:
            return
        book = self._selected_book
        if not text.startswith(book):
            self._set_text(book, True)
            return
        suffix = text[len(book):]
        if not re.fullmatch(r"[\s0-9:：.．。\-]*", suffix):
            suffix = re.sub(r"[^0-9 :：.．。\-]", "", suffix)
            self._set_text(book + suffix, True)
        self._refresh_selected(book, suffix)

    def _refresh_selected(self, book, suffix):
        value = suffix.strip().replace("：", ":").replace("．", ".").replace("。", ".")
        self.result_list.clear()
        if not value:
            self._resize_result_area()
            self._update_hint_for_stage()
            return
        match = re.fullmatch(r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?", value)
        if not match:
            self._resize_result_area()
            return
        chapter_text, verse_text, end_text = match.groups()
        chapter = int(chapter_text)
        max_chapter = self._chapter_count(book)
        if not 1 <= chapter <= max_chapter:
            self._update_hint(f"章节超出范围，本书最多 {max_chapter} 章")
            return
        if verse_text is None:
            item = QListWidgetItem(f"▶  {book}  {chapter}章（整章）")
            item.setData(Qt.ItemDataRole.UserRole, (book, chapter, None, None))
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            self._resize_result_area()
            return
        verse = int(verse_text)
        max_verse = self._verse_count(book, chapter)
        if not 1 <= verse <= max_verse:
            self._update_hint(f"第 {chapter} 章最多 {max_verse} 节")
            return
        if end_text is None:
            if "-" in value:
                self._update_hint(f"请输入结束节（{verse}-{max_verse}）")
                return
            item = QListWidgetItem(f"▶  {book}  {chapter}:{verse}")
            item.setData(Qt.ItemDataRole.UserRole, (book, chapter, verse, verse))
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            self._resize_result_area()
            return
        if end_text == "":
            self._update_hint(f"请输入结束节（{verse}-{max_verse}）")
            return
        end = int(end_text)
        if end < verse:
            self._update_hint(f"结束节不能小于开始节 {verse}")
            return
        if end > max_verse:
            self._update_hint(f"本章最多 {max_verse} 节，不能输入 {end}")
            return
        item = QListWidgetItem(f"▶  {book}  {chapter}:{verse}-{end}")
        item.setData(Qt.ItemDataRole.UserRole, (book, chapter, verse, end))
        self.result_list.addItem(item)
        self.result_list.setCurrentRow(0)
        self._resize_result_area()

    def _parse(self, text):
        value = text.strip().replace("：", ":").replace("．", ".").replace("。", ".")
        book = self._selected_book
        if not book:
            match = re.match(r"^([A-Za-z]+)", value)
            book = self._exact(match.group(1)) if match else None
        if not book:
            return None
        suffix = value[len(book):].strip() if value.startswith(book) else value
        match = re.fullmatch(r"(\d+)", suffix)
        if match:
            chapter = int(match.group(1))
            return (book, chapter, None, None) if 1 <= chapter <= self._chapter_count(book) else None
        match = re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?", suffix)
        if not match:
            return None
        chapter, verse, end = match.groups()
        chapter, verse = int(chapter), int(verse)
        end = int(end) if end else verse
        max_verse = self._verse_count(book, chapter)
        return (book, chapter, verse, end) if 1 <= chapter <= self._chapter_count(book) and 1 <= verse <= end <= max_verse else None

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        if isinstance(data, tuple) and len(data) == 4 and data[2] is not None:
            self.search_triggered.emit(data)
            self.close_requested.emit()
            return
        book = data[0] if isinstance(data, tuple) else data
        self._selected_book = book
        self._stage = "chapter"
        self._set_text(book, True)
        self.result_list.clear()
        self._resize_result_area()
        self.search_input.setFocus()
        self._update_hint(f"已选择 {book}　请输入章节　空格进入节号")

    def _on_confirm(self):
        if self._confirming:
            return
        self._confirming = True
        try:
            parsed = self._parse(self.search_input.text())
            if parsed:
                self.search_triggered.emit(parsed)
                self.close_requested.emit()
            elif self._stage == "book" and self.result_list.count():
                self._select_current_book()
            else:
                self._update_hint("请输入有效的书卷、章节或节范围")
        finally:
            self._confirming = False
