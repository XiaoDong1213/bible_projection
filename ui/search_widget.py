# ui/search_widget.py
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal, QEvent


class SearchWidget(QWidget):
    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()
    ALLOWED = re.compile(r"[A-Za-z0-9 :：.．。\-]")

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._formatting = False
        self._converted_book = False
        self._converted_book_name = ""
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False

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

        self.hint_label = QLabel("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出")
        lay.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        lay.addWidget(self.result_list)
        self.search_input.installEventFilter(self)
        self.result_list.installEventFilter(self)
        self.setFocusProxy(self.search_input)

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._converted_book = False
        self._converted_book_name = ""
        self._selected_book = None
        self._stage = "book"
        self._space_mode = False
        self.result_list.clear()

    @staticmethod
    def _norm(value):
        return re.sub(r"[\s._-]+", "", str(value or "").strip().lower())

    def _code(self, book):
        return self._norm(self.db.book_meta.get(book, {}).get("pinyin", ""))

    def _candidates(self, query):
        q = self._norm(query)
        return [b for b in self.db.book_names if self._code(b).startswith(q)] if q else []

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
        text = str(text or "")
        self._formatting = True
        try:
            self.search_input.setText(text)
            self.search_input.setCursorPosition(len(text))
        finally:
            self._formatting = False
        if converted is not None:
            self._converted_book = bool(converted)
            self._converted_book_name = text if converted else ""

    def _show_candidates(self, candidates):
        self.result_list.clear()
        for i, book in enumerate(candidates[:30], 1):
            code = self._code(book).upper()
            short = self.db._short_name(book)
            item = QListWidgetItem(f"{i}. {code or short} {book}")
            item.setData(Qt.ItemDataRole.UserRole, book)
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)
            self.result_list.scrollToItem(self.result_list.currentItem())

    def _move_highlight(self, delta):
        if not self.result_list.count():
            return True
        row = self.result_list.currentRow()
        row = max(0, min(row + delta, self.result_list.count() - 1))
        self.result_list.setCurrentRow(row)
        self.result_list.scrollToItem(self.result_list.currentItem())
        return True

    def _select_current_book(self):
        item = self.result_list.currentItem()
        if item is None:
            return False
        book = item.data(Qt.ItemDataRole.UserRole)
        if not book:
            return False
        self._selected_book = book
        self._stage = "chapter"
        self._space_mode = False
        self._set_text(book, converted=True)
        self.result_list.clear()
        self.search_input.setFocus()
        self.search_input.setCursorPosition(len(book))
        self.hint_label.setText(f"已选择 {book}　输入章节后按空格，自动进入节号")
        return True

    def _is_letter(self, key):
        return Qt.Key.Key_A <= key <= Qt.Key.Key_Z

    def _suffix(self):
        if not self._selected_book:
            return ""
        return self.search_input.text()[len(self._selected_book):]

    def _space_after_chapter(self):
        suffix = self._suffix().strip()
        if not re.fullmatch(r"\d+", suffix):
            return False
        chapter = int(suffix)
        max_chapter = self._chapter_count(self._selected_book)
        if chapter < 1 or chapter > max_chapter:
            self.hint_label.setText(f"章节超出范围，本书最多 {max_chapter} 章")
            return True
        self._stage = "verse"
        # 空格只是操作键，不把空格本身作为用户数据；自动显示章/节分隔符。
        self._set_text(f"{self._selected_book} {chapter}:", converted=False)
        self.hint_label.setText(f"请输入第几节；输入节号后按空格自动生成范围分隔符 -")
        return True

    def _space_after_verse(self):
        text = self.search_input.text()
        prefix = self._selected_book
        suffix = text[len(prefix):].strip() if text.startswith(prefix) else ""
        m = re.fullmatch(r"(\d+)\s*:\s*(\d+)", suffix)
        if not m:
            return True
        chapter, verse = int(m.group(1)), int(m.group(2))
        max_chapter = self._chapter_count(prefix)
        max_verse = self._verse_count(prefix, chapter)
        if chapter < 1 or chapter > max_chapter:
            self.hint_label.setText(f"章节超出范围，本书最多 {max_chapter} 章")
            return True
        if verse < 1 or verse > max_verse:
            self.hint_label.setText(f"本章最多 {max_verse} 节")
            return True
        self._space_mode = True
        self._set_text(f"{prefix} {chapter}:{verse}-", converted=False)
        self.hint_label.setText(f"请输入结束节（1-{max_verse}），不能小于 {verse}")
        return True

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(obj, event)
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return True
        if obj is self.search_input:
            if key == Qt.Key.Key_Up:
                return self._move_highlight(-1)
            if key == Qt.Key.Key_Down:
                return self._move_highlight(1)
            if key == Qt.Key.Key_Space:
                if self._stage == "book" and self.result_list.count():
                    return self._select_current_book()
                if self._stage == "chapter" and self._selected_book:
                    return self._space_after_chapter()
                if self._stage == "verse" and self._selected_book:
                    return self._space_after_verse()
                return True
            if self._converted_book:
                if self._is_letter(key):
                    return True
                if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                    self._set_text("", converted=False)
                    self._selected_book = None
                    self._stage = "book"
                    self._space_mode = False
                    self.result_list.clear()
                    return True
            allowed = {Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Home, Qt.Key.Key_End, Qt.Key.Key_Return, Qt.Key.Key_Enter}
            if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and key not in allowed:
                txt = event.text()
                if txt and not all(self.ALLOWED.fullmatch(c) for c in txt):
                    return True
        return super().eventFilter(obj, event)

    def _on_text_edited(self, text):
        if self._formatting:
            return
        if self._stage == "book":
            clean = "".join(c for c in text if self.ALLOWED.fullmatch(c))
            if clean != text:
                self._set_text(clean)
                text = clean
            q = text.strip()
            self.result_list.clear()
            if re.fullmatch(r"[A-Za-z]+", q):
                candidates = self._candidates(q)
                if candidates:
                    self._show_candidates(candidates)
                else:
                    results = self.db.search_books(q)
                    if results:
                        self._show_candidates(results)
            return
        if not self._selected_book:
            return
        book = self._selected_book
        if not text.startswith(book):
            self._set_text(book, converted=True)
            return
        suffix = text[len(book):]
        # 空格是分段符快捷键，但自动生成的 : 和 - 仍然允许存在。
        if not re.fullmatch(r"[\s0-9:：.．。\-]*", suffix):
            clean = re.sub(r"[^0-9 :：.．。\-]", "", suffix)
            self._set_text(book + clean, converted=False)
            suffix = clean
        self._refresh_selected(book, suffix)

    def _refresh_selected(self, book, suffix):
        s = suffix.strip().replace("：", ":").replace("．", ".").replace("。", ".")
        self.result_list.clear()
        if not s:
            return
        # 支持完整范围以及输入中的中间状态：1 / 1: / 1:5 / 1:5- / 1:5-12
        m = re.fullmatch(r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?", s)
        if not m:
            return
        c, v, e = m.groups()
        c = int(c)
        max_c = self._chapter_count(book)
        if c < 1 or c > max_c:
            self.hint_label.setText(f"章节超出范围，本书最多 {max_c} 章")
            return
        if v is None:
            item = QListWidgetItem(f"▶ {book} {c}章（整章）")
            item.setData(Qt.ItemDataRole.UserRole, (book, c, None, None))
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            return
        v = int(v)
        max_v = self._verse_count(book, c)
        if v < 1 or v > max_v:
            self.hint_label.setText(f"第 {c} 章最多 {max_v} 节")
            return
        if e is None:
            # 允许输入到 1:5- 的中间状态
            if "-" in s:
                self.hint_label.setText(f"请输入结束节（{v}-{max_v}）")
                return
            item = QListWidgetItem(f"▶ {book} {c}:{v}")
            item.setData(Qt.ItemDataRole.UserRole, (book, c, v, v))
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            return
        if e == "":
            self.hint_label.setText(f"请输入结束节（{v}-{max_v}）")
            return
        e = int(e)
        if e < v:
            self.hint_label.setText(f"结束节不能小于开始节 {v}")
            return
        if e > max_v:
            self.hint_label.setText(f"本章最多 {max_v} 节，不能输入 {e}")
            return
        item = QListWidgetItem(f"▶ {book} {c}:{v}-{e}")
        item.setData(Qt.ItemDataRole.UserRole, (book, c, v, e))
        self.result_list.addItem(item)
        self.result_list.setCurrentRow(0)

    def _parse(self, text):
        r = text.strip().replace("：", ":").replace("．", ".").replace("。", ".")
        b = self._selected_book
        if not b:
            m = re.match(r"^([A-Za-z]+)", r)
            b = self._exact(m.group(1)) if m else None
        if not b:
            return None
        s = r[len(b):].strip() if r.startswith(b) else r
        m = re.fullmatch(r"(\d+)", s)
        if m:
            c = int(m.group(1))
            return (b, c, None, None) if 1 <= c <= self._chapter_count(b) else None
        m = re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?", s)
        if not m:
            return None
        c, v, e = m.groups(); c=int(c); v=int(v); e=int(e) if e else v
        max_v = self._verse_count(b,c)
        return (b,c,v,e) if 1 <= c <= self._chapter_count(b) and 1 <= v <= e <= max_v else None

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        if isinstance(data, tuple) and len(data) == 4:
            if data[2] is not None:
                self.search_triggered.emit(data)
                self.close_requested.emit()
                return
            book = data[0]
        else:
            book = data
        self._selected_book = book
        self._stage = "chapter"
        self._set_text(book, converted=True)
        self.result_list.clear()
        self.search_input.setFocus()

    def _on_confirm(self):
        parsed = self._parse(self.search_input.text())
        if parsed:
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
            return
        if self._stage == "book" and self.result_list.count():
            self._select_current_book()
            return
        self.hint_label.setText("请输入有效的书卷、章节或节范围")
