# ui/search_widget.py
import re

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent


class SearchWidget(QWidget):
    """圣经搜索框。

    输入规则：
    1. 用户只能输入英文简拼、数字、空格、:：.．。-。
    2. 简拼前缀唯一时立即转换成中文书卷名；有多个候选时继续保留简拼并显示候选。
    3. 当前简拼没有任何前缀候选时，立即尝试把它作为文字搜索；只有唯一结果才自动转中文。
    4. 中文书卷名由简拼自动生成后，不能继续输入字母；数字和范围分隔符仍可输入。
    5. 自动生成的中文书名按一次 Backspace/Delete 直接整体清空。
    6. 章节达到该书卷 ChapterCount 后自动补冒号，例如：CSJ 50 -> CSJ 50:。
    7. 章/节超范围时，确认后定位到数据库中实际存在的最后一章/最后一节。
    """

    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()

    _SEP_TRANSLATION = str.maketrans({"：": ":", "．": ".", "。": "."})
    _ALLOWED_RE = re.compile(r"[A-Za-z0-9 :：.．。\-]")
    _LETTERS_RE = re.compile(r"[A-Za-z]+")
    _BOOK_RE = re.compile(r"^[\u3400-\u9fff]+$")

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._formatting = False
        self._converted_book = False
        self._converted_book_name = ""
        self._last_valid_prefix = ""

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("例如：CSJ 1:2-12")
        self.search_input.textEdited.connect(self._on_text_edited)
        self.search_input.returnPressed.connect(self._on_confirm)
        lay.addWidget(self.search_input)

        self.hint_label = QLabel("输入简拼、数字和分隔符　｜　Enter 确认　｜　Esc 退出")
        lay.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.result_list)

        self.search_input.installEventFilter(self)
        self.result_list.installEventFilter(self)
        self.setFocusProxy(self.search_input)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._converted_book = False
        self._converted_book_name = ""
        self._last_valid_prefix = ""
        self._refresh(self.search_input.text(), False)

    # ------------------------------------------------------------------
    # 书卷匹配
    # ------------------------------------------------------------------
    @staticmethod
    def _norm(value):
        return re.sub(r"[\s._-]+", "", str(value or "").strip().lower())

    def _code(self, book):
        return self._norm(self.db.book_meta.get(book, {}).get("pinyin", ""))

    def _candidates(self, query):
        q = self._norm(query)
        if not q:
            return []
        return [b for b in self.db.book_names if self._code(b).startswith(q)]

    def _exact(self, query):
        q = self._norm(query)
        if not q:
            return None
        for book in self.db.book_names:
            if self._code(book) == q:
                return book
        return None

    def _show_candidates(self, query):
        self.result_list.clear()
        for i, book in enumerate(self._candidates(query)[:12], 1):
            code = self._code(book).upper()
            short = self.db._short_name(book)
            item = QListWidgetItem(f"{i}. {code or short} {book}")
            item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

    def _show_single_book(self, book):
        self._set_text(book, converted_book=True)
        self.result_list.clear()

    # ------------------------------------------------------------------
    # 输入过滤
    # ------------------------------------------------------------------
    def _sanitize(self, text):
        """统一处理键盘、粘贴、输入法提交等产生的非法字符。"""
        return "".join(ch for ch in str(text or "") if self._ALLOWED_RE.fullmatch(ch))

    def _is_letter(self, key):
        return Qt.Key.Key_A <= key <= Qt.Key.Key_Z

    def eventFilter(self, obj, event):
        if obj is self.search_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()

            # Esc：关闭搜索框。
            if key == Qt.Key.Key_Escape:
                self.close_requested.emit()
                return True

            # 自动转换成中文书名后，字母一律无效，不能再拼简拼。
            if self._converted_book and self._is_letter(key):
                return True

            # 中文输入状态下，Backspace/Delete 一次清空自动生成的整本书名。
            if self._converted_book and key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                self._set_text("", converted_book=False)
                self.result_list.clear()
                self._last_valid_prefix = ""
                return True

            # 只允许：A-Z / 0-9 / 空格 / 冒号 / 点 / 短横线。
            # 编辑控制键、Ctrl+A/C/V/X、左右移动等正常放行。
            if not event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                allowed_keys = {
                    Qt.Key.Key_Backspace,
                    Qt.Key.Key_Delete,
                    Qt.Key.Key_Left,
                    Qt.Key.Key_Right,
                    Qt.Key.Key_Home,
                    Qt.Key.Key_End,
                    Qt.Key.Key_Return,
                    Qt.Key.Key_Enter,
                    Qt.Key.Key_Tab,
                }
                if key not in allowed_keys:
                    text = event.text()
                    if text and not all(self._ALLOWED_RE.fullmatch(ch) for ch in text):
                        return True

        if obj is self.result_list and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                if self._select_current_result_by_space() if event.key() == Qt.Key.Key_Space else self._confirm_current_item():
                    return True

        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # 文本状态机
    # ------------------------------------------------------------------
    def _set_text(self, text, converted_book=None):
        text = str(text or "")
        self._formatting = True
        try:
            self.search_input.setText(text)
            self.search_input.setCursorPosition(len(text))
        finally:
            self._formatting = False

        if converted_book is not None:
            self._converted_book = bool(converted_book)
            self._converted_book_name = text if converted_book else ""

    def _clear_result(self):
        self.result_list.clear()

    def _normalize_separators(self, text):
        return str(text or "").translate(self._SEP_TRANSLATION)

    def _auto_format(self, text):
        """只负责格式化，不负责把书卷直接变成中文。"""
        r = str(text or "").strip()
        if not r:
            return r

        # 简拼 + 章 + 节：统一成 CODE 1:2-12。
        m = re.fullmatch(
            r"([A-Za-z]+)[\s]*(\d+)[\s:：.．。]+(\d+)(?:\s*-\s*(\d*))?",
            r,
        )
        if m:
            code, chapter, start, end = m.groups()
            result = f"{code.upper()} {int(chapter)}:{int(start)}"
            if end:
                result += f"-{int(end)}"
            elif "-" in r:
                result += "-"
            return result

        # 简拼 + 数字 + 分隔符 + 数字范围。
        m = re.fullmatch(
            r"([A-Za-z]+)[\s]*(\d+)(?:[\s:：.．。]+(\d+))?(?:\s*-\s*(\d*))?",
            r,
        )
        if not m:
            return r

        code, chapter, start, end = m.groups()
        book = self._exact(code)
        if not book:
            return r

        code = code.upper()
        chapter_i = int(chapter)

        if start is not None:
            result = f"{code} {chapter_i}:{int(start)}"
            if end:
                result += f"-{int(end)}"
            elif "-" in r:
                result += "-"
            return result

        # 只有“章”时：
        # 若继续追加一位数字仍可能形成合法章节，则不急着补冒号；
        # 当 ChapterCount 已经足以确定当前数字就是章节时，自动补冒号。
        count = self._chapter_count(book)
        if count and 1 <= chapter_i <= count:
            possible_longer = any(
                chapter.startswith(str(chapter_i)) and int(chapter) <= count
                for chapter in [str(chapter_i) + str(d) for d in range(10)]
            )
            if not possible_longer:
                return f"{code} {chapter_i}:"

        return f"{code} {chapter_i}"

    def _on_text_edited(self, text):
        if self._formatting:
            return

        # 自动中文书名状态：Qt 文本变化通常来自 Backspace/Delete；
        # 键盘字母已经在 eventFilter 拦截，这里只做兜底。
        if self._converted_book:
            if text == "" or text != self._converted_book_name:
                self._set_text("", converted_book=False)
                self._clear_result()
            return

        clean = self._sanitize(text)
        if clean != text:
            self._set_text(clean, converted_book=False)
            text = clean

        self._refresh(text, True)

    def _refresh(self, text, user=True):
        if self._formatting:
            return

        raw = str(text or "")
        r = raw.strip()
        if not r:
            self._converted_book = False
            self._converted_book_name = ""
            self._last_valid_prefix = ""
            self._clear_result()
            return

        # 简拼输入阶段：每个字符都实时计算前缀候选。
        if re.fullmatch(r"[A-Za-z]+", r):
            candidates = self._candidates(r)

            if candidates:
                self._last_valid_prefix = r
                if len(candidates) == 1:
                    self._show_single_book(candidates[0])
                    return
                self._show_candidates(r)
                return

            # 当前字母已经没有任何“开头匹配”时，不等待数字。
            # 立即尝试文字搜索；只有唯一结果才直接转成中文书名。
            fuzzy = self.db.search_books(r)
            if len(fuzzy) == 1:
                self._show_single_book(fuzzy[0])
                return

            # 没有唯一文字结果，保留用户输入，让用户继续修改。
            self._clear_result()
            return

        # 自动生成的中文书卷名。
        if self._BOOK_RE.fullmatch(r):
            self._converted_book = False
            self._converted_book_name = ""
            self._clear_result()
            return

        # 中文书名 + 章节/节号：中文书名只能来自自动转换。
        if re.fullmatch(r"[\u3400-\u9fff]+[\s]+\d+", r):
            self._clear_result()
            return

        if re.fullmatch(r"[\u3400-\u9fff]+[\s]*\d+(?:[:.][\s]*\d+)?(?:\s*-\s*\d*)?", r):
            p = self._parse(r)
            if p:
                self._show_parse_result(p)
                return

        formatted = self._auto_format(r) if user else r
        if formatted != r:
            self._set_text(formatted, converted_book=False)
            r = formatted

        p = self._parse(r)
        if p:
            self._show_parse_result(p)
            return

        # 越界引用允许继续输入；确认时按实际存在的最后章节/节定位。
        p = self._clamp(r)
        if p:
            self._show_parse_result(p)
            return

        self._show_book_search(r)

    # ------------------------------------------------------------------
    # 解析
    # ------------------------------------------------------------------
    def _chapter_count(self, book):
        try:
            return int(
                self.db.book_meta.get(book, {}).get("chapter_count")
                or self.db.get_chapter_count(book)
                or 0
            )
        except (TypeError, ValueError, AttributeError):
            return 0

    def _verse_count(self, book, chapter):
        try:
            return int(self.db.get_verse_count(book, chapter) or 0)
        except (TypeError, ValueError, AttributeError):
            return 0

    def _valid(self, parsed):
        if not parsed or len(parsed) != 4:
            return None
        book, chapter, start, end = parsed
        if not book:
            return None
        try:
            chapter = int(chapter)
            count = self._chapter_count(book)
            if chapter < 1 or chapter > count:
                return None

            if start is None:
                return book, chapter, None, None

            max_verse = self._verse_count(book, chapter)
            start = int(start)
            end = int(end) if end is not None else start
            if not 1 <= start <= max_verse:
                return None
            if not 1 <= end <= max_verse:
                return None
            if end < start:
                return None
            return book, chapter, start, end
        except (TypeError, ValueError, AttributeError):
            return None

    def _split_digits(self, book, digits):
        """CSJ12 这类输入：按实际 ChapterCount/VerseCount 找到唯一合理拆分。"""
        digits = str(digits)
        if not digits.isdigit() or len(digits) < 2:
            return None

        candidates = []
        for verse_len in range(1, len(digits)):
            chapter_s = digits[:-verse_len]
            verse_s = digits[-verse_len:]
            if chapter_s.startswith("0") or verse_s.startswith("0"):
                continue
            chapter = int(chapter_s)
            verse = int(verse_s)
            if 1 <= chapter <= self._chapter_count(book):
                max_verse = self._verse_count(book, chapter)
                if 1 <= verse <= max_verse:
                    candidates.append((chapter, verse))

        if not candidates:
            # 也允许“纯章节号”，例如 CSJ50。
            try:
                chapter = int(digits)
                if 1 <= chapter <= self._chapter_count(book):
                    return book, chapter, None, None
            except ValueError:
                pass
            return None

        # 优先较短节号；例如 112 -> 1:12 优先于 11:2。
        candidates.sort(key=lambda x: (len(str(x[1])), x[0]))
        chapter, verse = candidates[0]
        return book, chapter, verse, verse

    def _parse(self, text):
        r = self._normalize_separators(text).strip()
        if not r:
            return None

        # CODE 1:2-12 / CODE1.2-12 / CODE 1 2-12。
        m = re.fullmatch(
            r"([A-Za-z]+)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d+))?",
            r,
        )
        if m:
            code, chapter, start, end = m.groups()
            book = self._exact(code)
            if book:
                return self._valid(
                    (book, int(chapter), int(start), int(end) if end else int(start))
                )

        # 中文书名 1:2-12。
        m = re.fullmatch(
            r"([\u3400-\u9fff]+)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d+))?",
            r,
        )
        if m:
            book, chapter, start, end = m.groups()
            book = self.db.find_book(book)
            if book:
                return self._valid(
                    (book, int(chapter), int(start), int(end) if end else int(start))
                )

        # CODE 1 / CODE1。
        m = re.fullmatch(r"([A-Za-z]+)[\s]+(\d+)", r)
        if m:
            book = self._exact(m.group(1))
            return self._valid((book, int(m.group(2)), None, None)) if book else None

        m = re.fullmatch(r"([A-Za-z]+)(\d+)", r)
        if m:
            book = self._exact(m.group(1))
            if book:
                return self._split_digits(book, m.group(2))

        # CODE 1: / 中文书名 1:：输入冒号后等待节号，不在此时确认。
        m = re.fullmatch(r"([A-Za-z]+|[\u3400-\u9fff]+)[\s]*(\d+)[:.]", r)
        if m:
            book = self._exact(m.group(1)) or self.db.find_book(m.group(1))
            if book:
                try:
                    chapter = int(m.group(2))
                    if 1 <= chapter <= self._chapter_count(book):
                        return book, chapter, None, None
                except ValueError:
                    pass

        parsed = self.db.parse_reference(r)
        return self._valid(parsed)

    def _clamp(self, text):
        """越界输入也能定位：章号/节号超过数据库范围时取最后实际存在值。"""
        r = self._normalize_separators(text).strip()
        m = re.fullmatch(
            r"(.+?)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d+))?",
            r,
        )
        if not m:
            return None

        book_query, chapter_s, start_s, end_s = m.groups()
        book = self.db.find_book(book_query.strip())
        if not book:
            return None

        try:
            chapter_count = self._chapter_count(book)
            if not chapter_count:
                return None

            chapter = max(1, min(int(chapter_s), chapter_count))
            max_verse = self._verse_count(book, chapter)
            if not max_verse:
                return None

            start = max(1, min(int(start_s), max_verse))
            end = start if end_s is None else max(start, min(int(end_s), max_verse))
            return book, chapter, start, end
        except (TypeError, ValueError, AttributeError):
            return None

    # ------------------------------------------------------------------
    # 结果显示
    # ------------------------------------------------------------------
    def _display(self, book, chapter, start, end):
        if start is None:
            return f"{book} {chapter}章（整章）"
        if end is None or start == end:
            return f"{book} {chapter}:{start}"
        return f"{book} {chapter}:{start}-{end}"

    def _show_parse_result(self, parsed):
        self._clear_result()
        book, chapter, start, end = parsed
        item = QListWidgetItem("▶ " + self._display(book, chapter, start, end))
        item.setData(Qt.ItemDataRole.UserRole, parsed)
        self.result_list.addItem(item)
        self.result_list.setCurrentRow(0)

    def _show_book_search(self, text):
        self._clear_result()
        q = re.split(r"[0-9:：.．。\-\s]+", text, maxsplit=1)[0].strip()
        if not q:
            return
        for i, book in enumerate(self.db.search_books(q)[:12], 1):
            code = self._code(book).upper()
            short = self.db._short_name(book)
            item = QListWidgetItem(f"{i}. {code or short} {book}")
            item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

    # ------------------------------------------------------------------
    # 确认
    # ------------------------------------------------------------------
    def _confirm_current_item(self):
        item = self.result_list.currentItem()
        if item is None:
            return False
        parsed = item.data(Qt.ItemDataRole.UserRole)
        if not parsed:
            return False
        self.search_triggered.emit(parsed)
        self.close_requested.emit()
        return True

    def _select_current_result_by_space(self):
        """空格只选书卷，不立即关闭搜索框。"""
        item = self.result_list.currentItem()
        if item is None:
            return False
        parsed = item.data(Qt.ItemDataRole.UserRole)
        if not parsed:
            return False
        book = parsed[0]
        self._set_text(book, converted_book=True)
        self._clear_result()
        return True

    def _on_confirm(self):
        text = self.search_input.text().strip()

        # 先按严格解析，再按越界钳制。
        parsed = self._parse(text)
        if parsed is None:
            parsed = self._clamp(text)

        if parsed:
            book, chapter, start, end = parsed
            if start is None:
                display = f"{book} {chapter}"
            elif start == end:
                display = f"{book} {chapter}:{start}"
            else:
                display = f"{book} {chapter}:{start}-{end}"
            self._set_text(display, converted_book=False)
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
            return

        if self._confirm_current_item():
            return

        self.hint_label.setText("无法识别，请输入例如：CSJ 1:2 或 CSJ 1:2-12")

    def _on_item_clicked(self, item):
        parsed = item.data(Qt.ItemDataRole.UserRole)
        if parsed:
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
