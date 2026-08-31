# ui/search_widget.py
# 经文快速搜索：支持中文书名、简称、Books.Pinyin简拼、数字快捷输入、小键盘格式、模糊匹配

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal


class SearchWidget(QWidget):
    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._formatting_text = False
        self._rejecting_input = False
        self._last_valid_input = ""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("例如：创世记1:2-12  或  CSJ 1:2-12")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self.search_input)

        self.hint_label = QLabel(
            "书名 / 简称 / 简拼　｜　CSJ12 → CSJ 1:2　｜　Esc 退出"
        )
        self.hint_label.setStyleSheet("color:#9AA3B2;font-size:11px;padding:2px 4px;")
        layout.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background: rgba(255,255,255,0.98);
                max-height: 240px;
                color: #1E293B;
            }
            QListWidget::item { padding: 8px 12px; font-size: 13px; border-radius: 4px; margin: 1px 2px; }
            QListWidget::item:selected { background: #3B82F6; color: white; }
            QListWidget::item:hover:!selected { background: #EEF1F6; }
        """)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.result_list)

        self.search_input.installEventFilter(self)
        self.result_list.installEventFilter(self)
        self.setFocusProxy(self.search_input)

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._on_text_changed(self.search_input.text())

    @staticmethod
    def _normalize(value):
        return re.sub(r"[\s._-]+", "", str(value or "").strip().lower())

    def _find_by_pinyin(self, query):
        q = self._normalize(query)
        if not q:
            return None
        for book, meta in getattr(self.db, "book_meta", {}).items():
            pinyin = self._normalize(meta.get("pinyin", ""))
            if pinyin and pinyin == q:
                return book
        return None

    def _validate_parsed(self, parsed):
        if not parsed or len(parsed) != 4:
            return None
        book, chapter, start, end = parsed
        validator = getattr(self.db, "validate_reference", None)
        if validator is not None:
            try:
                if not validator(book, chapter, start, end):
                    return None
            except (TypeError, ValueError):
                return None
        else:
            try:
                if not book or int(chapter) < 1 or int(chapter) > self.db.get_chapter_count(book):
                    return None
                max_verse = self.db.get_verse_count(book, int(chapter))
                if start is not None and not 1 <= int(start) <= max_verse:
                    return None
                if end is not None and not 1 <= int(end) <= max_verse:
                    return None
                if start is not None and end is not None and int(end) < int(start):
                    return None
            except (TypeError, ValueError, AttributeError):
                return None
        return parsed

    def _best_chapter_verse_split(self, book, digits):
        """对连续数字做经数据库校验的章:节拆分。

        优先较短节号（CSJ12 → 1:2；CSJ1234 → 12:34）。
        若无一合法章:节，则整段视为章节号。
        """
        digits = str(digits or "").strip()
        if not digits or not digits.isdigit() or not book:
            return None
        # 节号长度从 1 增到 len-1，优先「章短、节也合理」的拆法
        candidates = []
        for verse_len in range(1, len(digits)):
            ch_s = digits[:-verse_len]
            v_s = digits[-verse_len:]
            if not ch_s or ch_s.startswith("0") or v_s.startswith("0"):
                continue
            ch, v = int(ch_s), int(v_s)
            parsed = self._validate_parsed((book, ch, v, v))
            if parsed:
                # 评分：优先章号位数合理（1–3）、节号位数合理（1–3）
                score = (0 if len(ch_s) <= 3 else 10) + (0 if len(v_s) <= 3 else 10) + abs(len(ch_s) - len(v_s)) * 0.1
                candidates.append((score, len(v_s), parsed))
        if candidates:
            candidates.sort(key=lambda x: (x[0], x[1]))
            return candidates[0][2]
        # 整段作为章节
        return self._validate_parsed((book, int(digits), None, None))

    def _format_from_parsed(self, label, parsed):
        book, chapter, start, end = parsed
        if start is None:
            return f"{label} {chapter}"
        if end is None or end == start:
            return f"{label} {chapter}:{start}"
        return f"{label} {chapter}:{start}-{end}"

    def _chapter_entry_info(self, text):
        """识别“书卷 + 连续章节数字”，按数据库 ChapterCount 判断是否补冒号。"""
        raw = str(text or "").strip()
        m = re.fullmatch(r"(.+?)[\s]*([0-9]+)", raw)
        if not m:
            return None

        book_part, digits = m.groups()
        book_part = book_part.strip()
        if not book_part or book_part.isdigit():
            return None

        book = self.db.find_book(book_part)
        if not book:
            return None

        try:
            chapter_count = int(
                self.db.book_meta.get(book, {}).get("chapter_count")
                or self.db.get_chapter_count(book)
                or 0
            )
        except (TypeError, ValueError, AttributeError):
            chapter_count = 0

        if chapter_count <= 0:
            return None

        chapter = int(digits)
        if chapter < 1 or chapter > chapter_count:
            return {"invalid": True, "book": book, "book_part": book_part, "digits": digits}

        # 如果再输入任意一位数字，都不可能形成合法章节，
        # 当前数字就是明确的章节号，此时自动补“:”。
        can_extend = any(
            int(digits + str(next_digit)) <= chapter_count
            for next_digit in range(10)
        )
        return {
            "invalid": False,
            "book": book,
            "book_part": book_part,
            "digits": digits,
            "should_split": not can_extend,
            "chapter": chapter,
        }

    def _auto_format_reference(self, text):
        """输入书卷后的连续数字时，根据数据库 ChapterCount 自动补“:”。"""
        raw = str(text or "").strip()
        if not raw:
            return raw

        # 已经存在章:节分隔符，不处理。
        if re.search(r"[0-9][\s:：.]+[0-9]", raw):
            m = re.fullmatch(
                r"(.+?)[\s]*([0-9]+)(?:[\s:：.]+([0-9]+))?(?:[\s-]+([0-9]+))?",
                raw
            )
            if m:
                book_part, n1, n2, n3 = m.groups()
                if n2:
                    book = self.db.find_book(book_part.strip())
                    if book:
                        result = f"{book_part.strip()} {int(n1)}:{int(n2)}"
                        if n3:
                            result += f"-{int(n3)}"
                        return result
            return raw

        # 书卷名/简拼 + 连续章节数字：由数据库章节总数决定是否补冒号。
        chapter_info = self._chapter_entry_info(raw)
        if chapter_info:
            if chapter_info.get("invalid"):
                return raw
            if chapter_info.get("should_split"):
                return f"{chapter_info['book_part']} {chapter_info['chapter']}:"
            return raw

        # 保留原有简拼连续数字的智能章:节拆分（例如 CSJ12）。
        m = re.fullmatch(r"([A-Za-z]+)[\s]*([0-9]+)(?:[\s:：.]+([0-9]+))?(?:[\s-]+([0-9]+))?", raw)
        if not m:
            return raw

        code, n1, n2, n3 = m.groups()
        book = self._find_by_pinyin(code)
        if not book:
            return raw

        label = code.upper()
        if n2:
            result = f"{label} {int(n1)}:{int(n2)}"
            if n3:
                result += f"-{int(n3)}"
            return result

        if len(n1) >= 2:
            parsed = self._best_chapter_verse_split(book, n1)
            if parsed:
                return self._format_from_parsed(label, parsed)

        chapter_info = self._chapter_entry_info(raw)
        if chapter_info and not chapter_info.get("invalid") and chapter_info.get("should_split"):
            return f"{label} {chapter_info['chapter']}:"

        return raw

    def _set_formatted_text(self, text):
        if text == self.search_input.text():
            return
        self._formatting_text = True
        try:
            cursor_pos = self.search_input.cursorPosition()
            self.search_input.setText(text)
            self.search_input.setCursorPosition(min(len(text), max(cursor_pos, len(text))))
        finally:
            self._formatting_text = False

    def _validate_and_parse_formatted(self, text):
        formatted = self._auto_format_reference(text)
        if formatted != text:
            self._set_formatted_text(formatted)
        return self._parse_reference(formatted)

    def _clamp_invalid_reference(self, text):
        """经文输入超出实际章/节范围时，自动定位到该书卷的最后一节并返回规范引用。"""
        raw = str(text or "").strip().replace("：", ":").replace("．", ".").replace("。", ".")
        if not raw:
            return None

        # 支持：中文书名/简称/简拼 + 章:节（含范围）
        m = re.fullmatch(
            r"(.+?)[\\s]*(\\d+)(?::|[.\\s]+)(\\d+)(?:\\s*-\\s*(\\d*))?",
            raw
        )
        if not m:
            return None

        book_query, chapter_s, start_s, end_s = m.groups()
        book = self.db.find_book(book_query.strip())
        if not book:
            return None

        try:
            chapter = int(chapter_s)
            chapter_count = int(
                self.db.book_meta.get(book, {}).get("chapter_count")
                or self.db.get_chapter_count(book)
                or 0
            )
        except (TypeError, ValueError, AttributeError):
            return None

        if chapter_count <= 0:
            return None

        # 章号超出范围：定位到本书最后一章，再取最后一节。
        if chapter < 1 or chapter > chapter_count:
            chapter = chapter_count

        try:
            max_verse = int(self.db.get_verse_count(book, chapter) or 0)
            start = int(start_s)
        except (TypeError, ValueError, AttributeError):
            return None

        if max_verse <= 0:
            return None

        # 起始节超过本章实际节数：直接定位到最后一节。
        if start < 1 or start > max_verse:
            start = max_verse

        # 范围结束节也超出时，同样收敛到最后一节。
        if end_s is not None and end_s != "":
            try:
                end = int(end_s)
            except ValueError:
                end = max_verse
            end = max(1, min(end, max_verse))
            if end < start:
                end = start
            return book, chapter, start, end

        return book, chapter, start, start

    def _parse_reference(self, text):
        raw = str(text).strip().replace("：", ":").replace("．", ".").replace("。", ".")
        if not raw:
            return None

        m = re.fullmatch(r"([A-Za-z]+)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d*))?", raw)
        if m:
            code, chapter, start, end = m.groups()
            book = self._find_by_pinyin(code)
            if book:
                parsed = (
                    book,
                    int(chapter),
                    int(start),
                    int(end) if end else (None if "-" in raw else int(start)),
                )
                return self._validate_parsed(parsed)

        # 简拼 + 纯数字章节：CSJ 12
        m = re.fullmatch(r"([A-Za-z]+)[\s]+(\d+)$", raw)
        if m:
            book = self._find_by_pinyin(m.group(1))
            if book:
                return self._validate_parsed((book, int(m.group(2)), None, None))

        # 简拼连续数字未格式化时再拆一次
        m = re.fullmatch(r"([A-Za-z]+)(\d+)$", raw)
        if m:
            book = self._find_by_pinyin(m.group(1))
            if book:
                return self._best_chapter_verse_split(book, m.group(2))

        book = self._find_by_pinyin(raw)
        if book:
            return book, 1, None, None

        return self._validate_parsed(self.db.parse_reference(raw))

    def _on_text_changed(self, text):
        if self._formatting_text or self._rejecting_input:
            return

        # 超过当前书卷 ChapterCount 的章节直接回退，表现为“输入不上去”。
        chapter_info = self._chapter_entry_info(text.strip())
        if chapter_info and chapter_info.get("invalid"):
            self._rejecting_input = True
            try:
                self.search_input.setText(self._last_valid_input)
                self.search_input.setCursorPosition(len(self._last_valid_input))
            finally:
                self._rejecting_input = False
            return

        self.result_list.clear()
        text = text.strip()
        if not text:
            self._last_valid_input = text
            return

        parsed = self._validate_and_parse_formatted(text)
        if parsed:
            self._last_valid_input = self.search_input.text()
            book, chapter, start, end = parsed
            item = QListWidgetItem("▶ " + self._format_display(book, chapter, start, end))
            item.setData(Qt.ItemDataRole.UserRole, parsed)
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            return

        # 参考经文格式正确但章/节超出数据库范围：自动收敛到最后一节，
        # 并把最终定位结果直接显示在搜索框中。
        clamped = self._clamp_invalid_reference(text)
        if clamped:
            book, chapter, start, end = clamped
            display_ref = f"{book} {chapter}:{start}"
            self._set_formatted_text(display_ref)
            self._last_valid_input = display_ref
            self.result_list.clear()
            item = QListWidgetItem("▶ " + self._format_display(book, chapter, start, end))
            item.setData(Qt.ItemDataRole.UserRole, (book, chapter, start, end))
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            return

        book_query = self._extract_book_query(text)
        if not book_query:
            self._last_valid_input = self.search_input.text()
            return

        books = self.db.search_books(book_query)
        for index, book in enumerate(books[:12], 1):
            pinyin = self.db.book_meta.get(book, {}).get("pinyin", "")
            short = self.db._short_name(book)
            label = f"{pinyin} {book}" if pinyin else f"{short} {book}"
            item = QListWidgetItem(f"{index}. {label}")
            item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)
        self._last_valid_input = self.search_input.text()

    @staticmethod
    def _extract_book_query(text):
        if re.fullmatch(r"\d{1,2}[.\s]+\d+[.\s]+\d+(?:[.\s]+\d+)?", text):
            return ""
        m = re.match(r"^([^0-9:：.\-]+?)(?=\d|$)", text)
        if m:
            return m.group(1).strip()
        return re.split(r"[0-9:：.\-\s]+", text, maxsplit=1)[0].strip()

    def _format_display(self, book, chapter, start, end):
        if start is None:
            return f"{book} {chapter}章（整章）"
        if end is None:
            return f"{book} {chapter}:{start}-末"
        if start == end:
            return f"{book} {chapter}:{start}"
        return f"{book} {chapter}:{start}-{end}"

    def _on_confirm(self):
        text = self.search_input.text().strip()
        parsed = self._validate_and_parse_formatted(text)

        if parsed:
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
            return

        current = self.result_list.currentItem()
        if current:
            data = current.data(Qt.ItemDataRole.UserRole)
            if data:
                self.search_triggered.emit(data)
                self.close_requested.emit()
                return

        self.hint_label.setText("超出实际章节或节号范围，请检查输入")

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.search_triggered.emit(data)
            self.close_requested.emit()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close_requested.emit()
                return True
            if obj in (self.search_input, self.result_list):
                if key == Qt.Key.Key_Down:
                    self._move_selection(1)
                    return True
                if key == Qt.Key.Key_Up:
                    self._move_selection(-1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._on_confirm()
                    return True
        return super().eventFilter(obj, event)

    def _move_selection(self, delta):
        count = self.result_list.count()
        if count == 0:
            return
        row = self.result_list.currentRow()
        if row < 0:
            row = 0
        else:
            row = max(0, min(count - 1, row + delta))
        self.result_list.setCurrentRow(row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        super().keyPressEvent(event)
