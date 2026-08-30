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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("例如：创世记1:2-12  或  CSJ 1:2-12")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self.search_input)

        self.hint_label = QLabel(
            "支持：书名 / 简称 / Books.Pinyin简拼　｜　自动补全空格、:、-　｜　例如 CSJ12 → CSJ 1:2　｜　ESC退出"
        )
        self.hint_label.setStyleSheet("color:#888;font-size:11px;padding:2px 4px;")
        layout.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.setStyleSheet("""
            QListWidget { border:1px solid #DDD; border-radius:6px;
                background:rgba(255,255,255,0.98); max-height:240px; }
            QListWidget::item { padding:7px 12px; font-size:13px; }
            QListWidget::item:selected { background:#4A90E2; color:white; }
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
        """统一简拼输入：忽略大小写、空格及常见分隔符。"""
        return re.sub(r"[\s._-]+", "", str(value or "").strip().lower())

    def _find_by_pinyin(self, query):
        """直接从 Books.Pinyin 建立的 book_meta 中查找，确保简拼不依赖硬编码。"""
        q = self._normalize(query)
        if not q:
            return None
        for book, meta in getattr(self.db, "book_meta", {}).items():
            pinyin = self._normalize(meta.get("pinyin", ""))
            if pinyin and pinyin == q:
                return book
        return None

    def _validate_parsed(self, parsed):
        """经文地址必须符合数据库实际章节/节号范围，不能让SQL只返回一部分而误显示。"""
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

    def _auto_format_reference(self, text):
        """搜索框输入时自动补充分隔符。

        支持：
        CSJ12       -> CSJ 1:2
        CSJ 12      -> CSJ 1:2
        CSJ1234     -> CSJ 12:34
        CSJ 1 2     -> CSJ 1:2
        CSJ 1 2 12  -> CSJ 1:2-12
        CSJ 1:2-12  -> 保持原样
        """
        raw = str(text or "").strip()
        if not raw:
            return raw

        # 已经包含中文书名时，只把连续的章节/节号数字补成标准格式。
        # 中文书名后面的数字允许没有空格，例如“创世记12”。
        m = re.fullmatch(r"(.+?)[\s]*([0-9]+)(?:[\s:：.]+([0-9]+))?(?:[\s-]+([0-9]+))?", raw)
        if m and not re.fullmatch(r"[A-Za-z]+.*", raw):
            book_part, n1, n2, n3 = m.groups()
            if n2:
                result = f"{book_part.strip()} {int(n1)}:{int(n2)}"
                if n3:
                    result += f"-{int(n3)}"
                return result
            if len(n1) >= 3:
                # 中文书名 + 连续数字：优先按“章节 + 节”拆分。
                # 例如 创世记12 -> 1:2，创世记123 -> 12:3。
                return f"{book_part.strip()} {int(n1[:-1])}:{int(n1[-1])}"
            return raw

        # 简拼 + 数字。先确定书卷，避免把普通英文输入误格式化。
        m = re.fullmatch(r"([A-Za-z]+)[\s]*([0-9]+)(?:[\s:：.]+([0-9]+))?(?:[\s-]+([0-9]+))?", raw)
        if not m:
            return raw
        code, n1, n2, n3 = m.groups()
        if not self._find_by_pinyin(code):
            return raw

        if n2:
            result = f"{code.upper()} {int(n1)}:{int(n2)}"
            if n3:
                result += f"-{int(n3)}"
            return result

        # 连续数字自动按“章节 + 节”拆分。
        if len(n1) >= 3:
            chapter = n1[:-1]
            verse = n1[-1]
            return f"{code.upper()} {int(chapter)}:{int(verse)}"

        # 两位数字无法可靠判断 1:2 还是第12章，因此保持输入，避免误导。
        return raw

    def _set_formatted_text(self, text):
        if text == self.search_input.text():
            return
        self._formatting_text = True
        try:
            cursor_pos = self.search_input.cursorPosition()
            old = self.search_input.text()
            self.search_input.setText(text)
            # 尽量保持光标位于输入末尾，适合键盘连续输入。
            self.search_input.setCursorPosition(min(len(text), max(cursor_pos, len(text))))
        finally:
            self._formatting_text = False

    def _validate_and_parse_formatted(self, text):
        """解析前统一使用自动补全后的标准格式。"""
        formatted = self._auto_format_reference(text)
        if formatted != text:
            self._set_formatted_text(formatted)
        return self._parse_reference(formatted)

    def _parse_reference(self, text):
        """先处理 Books.Pinyin，再交给数据库处理其它格式，并严格限制实际范围。"""
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

        book = self._find_by_pinyin(raw)
        if book:
            return book, 1, None, None

        return self._validate_parsed(self.db.parse_reference(raw))

    def _on_text_changed(self, text):
        if self._formatting_text:
            return
        self.result_list.clear()
        text = text.strip()
        if not text:
            return

        parsed = self._validate_and_parse_formatted(text)
        if parsed:
            book, chapter, start, end = parsed
            item = QListWidgetItem("▶ " + self._format_display(book, chapter, start, end))
            item.setData(Qt.ItemDataRole.UserRole, parsed)
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            return

        book_query = self._extract_book_query(text)
        if not book_query:
            return

        books = self.db.search_books(book_query)
        for index, book in enumerate(books[:12], 1):
            # 候选项自动添加序号分隔符，便于直接按 1/2/3 选择。
            item = QListWidgetItem(f"{index}. {self.db._short_name(book)} {book}")
            item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

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
