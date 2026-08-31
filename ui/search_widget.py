# ui/search_widget.py
import re

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal, QEvent


class SearchWidget(QWidget):
    """搜索框输入状态机：先选书卷，再输入章/节。"""

    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()

    ALLOWED = re.compile(r"[A-Za-z0-9 :：.．。\-]")
    BOOK = re.compile(r"^[\u3400-\u9fff]+$")

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._formatting = False
        self._converted_book = False
        self._converted_book_name = ""

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(4)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("输入简拼，例如：CSJ")
        self.search_input.textEdited.connect(self._on_text_edited)
        self.search_input.returnPressed.connect(self._on_confirm)
        lay.addWidget(self.search_input)

        self.hint_label = QLabel("输入简拼　｜　空格选择高亮书卷　｜　Enter 确认　｜　Esc 退出")
        lay.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.result_list)

        self.search_input.installEventFilter(self)
        self.result_list.installEventFilter(self)
        self.setFocusProxy(self.search_input)

    # ---------------------------------------------------------------
    # 基础
    # ---------------------------------------------------------------
    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._converted_book = False
        self._converted_book_name = ""
        self._refresh(self.search_input.text(), False)

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
        for b in self.db.book_names:
            if self._code(b) == q:
                return b
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
        self._formatting = True
        try:
            self.search_input.setText(str(text or ""))
            self.search_input.setCursorPosition(len(str(text or "")))
        finally:
            self._formatting = False
        if converted is not None:
            self._converted_book = bool(converted)
            self._converted_book_name = str(text or "") if converted else ""

    # ---------------------------------------------------------------
    # 键盘：最重要的是“书卷选完以后数字不能把输入框清空”
    # ---------------------------------------------------------------
    def _is_letter_key(self, key):
        return Qt.Key.Key_A <= key <= Qt.Key.Key_Z

    def eventFilter(self, obj, event):
        if obj is self.search_input and event.type() == QEvent.Type.KeyPress:
            key = event.key()

            if key == Qt.Key.Key_Escape:
                self.close_requested.emit()
                return True

            # 输入框获得焦点时，空格就是“选择当前高亮书卷”。
            # 不再把空格当普通字符，因此不会破坏简拼匹配。
            if key == Qt.Key.Key_Space:
                if self.result_list.currentItem() is not None:
                    if self._select_current_result_by_space():
                        return True
                return True

            # 书卷已经选择后：禁止重新输入字母，允许数字和分隔符。
            if self._converted_book and self._is_letter_key(key):
                return True

            # 书卷已经选择后：一次退格/删除直接清空整个书卷名。
            if self._converted_book and key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                self._set_text("", converted=False)
                self.result_list.clear()
                return True

            # 还没有选择书卷时，不允许直接输入数字。
            # 必须先输入简拼并选择/自动确定书卷。
            if not self._converted_book and not self.search_input.text() and key in (
                Qt.Key.Key_0, Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3,
                Qt.Key.Key_4, Qt.Key.Key_5, Qt.Key.Key_6, Qt.Key.Key_7,
                Qt.Key.Key_8, Qt.Key.Key_9,
            ):
                return True

            # 普通字符白名单；Ctrl+A/C/V/X 等编辑操作保留。
            if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                control = {
                    Qt.Key.Key_Backspace, Qt.Key.Key_Delete,
                    Qt.Key.Key_Left, Qt.Key.Key_Right,
                    Qt.Key.Key_Home, Qt.Key.Key_End,
                    Qt.Key.Key_Return, Qt.Key.Key_Enter,
                }
                if key not in control:
                    typed = event.text()
                    if typed and not all(self.ALLOWED.fullmatch(ch) for ch in typed):
                        return True

        if obj is self.result_list and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                return self._select_current_result_by_space()
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return self._confirm_current_item()

        return super().eventFilter(obj, event)

    # ---------------------------------------------------------------
    # 输入处理
    # ---------------------------------------------------------------
    def _sanitize(self, text):
        return "".join(ch for ch in str(text or "") if self.ALLOWED.fullmatch(ch))

    def _on_text_edited(self, text):
        if self._formatting:
            return

        # ★关键修复：书卷已经选择后，数字是合法的“后半段”。
        # 例如：创世记  -> 输入 1 -> 创世记 1
        # 不再因为 text != _converted_book_name 而把整个输入框清空。
        if self._converted_book:
            book = self._converted_book_name
            if text == book:
                self.result_list.clear()
                return
            if text.startswith(book):
                suffix = text[len(book):]
                if self._suffix_allowed(suffix):
                    self._refresh_selected_book(book, suffix)
                    return

            # 如果用户通过粘贴/鼠标修改破坏了已选书卷状态，则恢复为重新搜索。
            self._set_text("", converted=False)
            self.result_list.clear()
            return

        clean = self._sanitize(text)
        if clean != text:
            self._set_text(clean, converted=False)
            text = clean
        self._refresh(text, True)

    def _suffix_allowed(self, suffix):
        return bool(re.fullmatch(r"[\s0-9:：.．。\-]*", suffix or ""))

    def _refresh(self, text, user=True):
        r = str(text or "").strip()
        self.result_list.clear()
        if not r:
            return

        # 只能用简拼选书卷；不再用数字直接选书卷。
        if re.fullmatch(r"[A-Za-z]+", r):
            candidates = self._candidates(r)
            if len(candidates) == 1:
                # 唯一书卷立即转换；用户随后可以直接输入数字。
                self._set_text(candidates[0], converted=True)
                return
            if candidates:
                self._show_candidates(candidates)
                return

            # 当前字母已经没有简拼前缀时，立即尝试文字匹配。
            matches = self.db.search_books(r)
            if len(matches) == 1:
                self._set_text(matches[0], converted=True)
                return
            return

        # 用户直接输入中文书卷名不作为正常输入路径。
        if self.BOOK.fullmatch(r):
            return

        # 输入尚未选书卷的数字/引用，不继续猜书卷。
        self._show_reference_result(r)

    # ---------------------------------------------------------------
    # 选书卷
    # ---------------------------------------------------------------
    def _show_candidates(self, candidates):
        self.result_list.clear()
        for i, book in enumerate(candidates[:12], 1):
            code = self._code(book).upper()
            short = self.db._short_name(book)
            item = QListWidgetItem(f"{i}. {code or short} {book}")
            item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)  # 高亮第一项
            self.result_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _select_current_result_by_space(self):
        item = self.result_list.currentItem()
        if item is None:
            return False
        parsed = item.data(Qt.ItemDataRole.UserRole)
        if not parsed:
            return False
        book = parsed[0]
        self._set_text(book, converted=True)
        self.result_list.clear()
        self.search_input.setFocus()
        self.search_input.setCursorPosition(len(book))
        return True

    # ---------------------------------------------------------------
    # 已选择书卷后的章/节解析
    # ---------------------------------------------------------------
    def _refresh_selected_book(self, book, suffix):
        s = suffix.strip()
        self.result_list.clear()
        if not s:
            return

        # 允许：1 / 1: / 1:2 / 1:2-12 / 1.2 / 1 2
        m = re.fullmatch(r"(\d+)(?:\s*(?::|[.\s])\s*(\d+)(?:\s*-\s*(\d*)?)?)?", s)
        if not m:
            return

        chapter_s, verse_s, end_s = m.groups()
        try:
            chapter = int(chapter_s)
        except ValueError:
            return

        if verse_s is None:
            count = self._chapter_count(book)
            if 1 <= chapter <= count:
                item = QListWidgetItem(f"▶ {book} {chapter}章（整章）")
                item.setData(Qt.ItemDataRole.UserRole, (book, chapter, None, None))
                self.result_list.addItem(item)
                self.result_list.setCurrentRow(0)
            return

        try:
            verse = int(verse_s)
            end = int(end_s) if end_s else verse
        except ValueError:
            return

        count = self._chapter_count(book)
        max_verse = self._verse_count(book, chapter) if 1 <= chapter <= count else 0
        if not max_verse or verse < 1 or verse > max_verse or end < verse or end > max_verse:
            return

        item = QListWidgetItem(
            f"▶ {book} {chapter}:{verse}" if end == verse else f"▶ {book} {chapter}:{verse}-{end}"
        )
        item.setData(Qt.ItemDataRole.UserRole, (book, chapter, verse, end))
        self.result_list.addItem(item)
        self.result_list.setCurrentRow(0)

    # ---------------------------------------------------------------
    # 兼容原有引用格式
    # ---------------------------------------------------------------
    def _show_reference_result(self, text):
        try:
            parsed = self._parse(text)
        except Exception:
            parsed = None
        if parsed:
            book, chapter, start, end = parsed
            label = f"{book} {chapter}" if start is None else (
                f"{book} {chapter}:{start}" if start == end else f"{book} {chapter}:{start}-{end}"
            )
            item = QListWidgetItem("▶ " + label)
            item.setData(Qt.ItemDataRole.UserRole, parsed)
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)

    def _valid(self, p):
        if not p or len(p) != 4:
            return None
        book, chapter, start, end = p
        try:
            chapter = int(chapter)
            if not book or not 1 <= chapter <= self._chapter_count(book):
                return None
            if start is None:
                return book, chapter, None, None
            start = int(start)
            end = int(end) if end is not None else start
            max_verse = self._verse_count(book, chapter)
            if 1 <= start <= max_verse and start <= end <= max_verse:
                return book, chapter, start, end
        except Exception:
            pass
        return None

    def _parse(self, text):
        r = str(text or "").strip().replace("：", ":").replace("．", ".").replace("。", ".")

        m = re.fullmatch(r"([A-Za-z]+)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d+))?", r)
        if m:
            code, c, s, e = m.groups()
            b = self._exact(code)
            if b:
                return self._valid((b, int(c), int(s), int(e) if e else int(s)))

        m = re.fullmatch(r"([A-Za-z]+)[\s]+(\d+)", r)
        if m:
            b = self._exact(m.group(1))
            return self._valid((b, int(m.group(2)), None, None)) if b else None

        m = re.fullmatch(r"([A-Za-z]+)(\d+)", r)
        if m:
            b = self._exact(m.group(1))
            if b:
                d = m.group(2)
                if len(d) >= 2:
                    for n in range(1, len(d)):
                        c, v = int(d[:-n]), int(d[-n:])
                        p = self._valid((b, c, v, v))
                        if p:
                            return p
                return self._valid((b, int(d), None, None))

        return self._valid(self.db.parse_reference(r))

    # ---------------------------------------------------------------
    # 确认
    # ---------------------------------------------------------------
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

    def _on_confirm(self):
        text = self.search_input.text().strip()
        parsed = self._parse(text)
        if parsed:
            book, chapter, start, end = parsed
            display = f"{book} {chapter}" if start is None else (
                f"{book} {chapter}:{start}" if start == end else f"{book} {chapter}:{start}-{end}"
            )
            self._set_text(display, converted=False)
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
            return

        if self._confirm_current_item():
            return

        self.hint_label.setText("请选择书卷，或输入例如：CSJ 1:2-12")

    def _on_item_clicked(self, item):
        parsed = item.data(Qt.ItemDataRole.UserRole)
        if parsed:
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
