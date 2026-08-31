# ui/search_widget.py
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal, QEvent


class SearchWidget(QWidget):
    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()

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

    def showEvent(self, e):
        super().showEvent(e)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._refresh(self.search_input.text(), False)

    @staticmethod
    def _norm(v):
        return re.sub(r"[\s._-]+", "", str(v or "").strip().lower())

    def _code(self, book):
        return self._norm(self.db.book_meta.get(book, {}).get("pinyin", ""))

    def _candidates(self, q):
        q = self._norm(q)
        return [b for b in self.db.book_names if self._code(b).startswith(q)] if q else []

    def _exact(self, q):
        q = self._norm(q)
        for b in self.db.book_names:
            if self._code(b) == q:
                return b
        return None

    def _show_candidates(self, q):
        self.result_list.clear()
        for i, b in enumerate(self._candidates(q)[:12], 1):
            code = self._code(b).upper()
            short = self.db._short_name(b)
            item = QListWidgetItem(f"{i}. {code or short} {b}")
            item.setData(Qt.ItemDataRole.UserRole, (b, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

    def _valid(self, p):
        if not p or len(p) != 4:
            return None
        b, c, s, e = p
        try:
            c = int(c)
            chapter_count = self.db.get_chapter_count(b)
            if not b or c < 1 or c > chapter_count:
                return None
            max_verse = self.db.get_verse_count(b, c)
            if s is not None and not 1 <= int(s) <= max_verse:
                return None
            if e is not None and not 1 <= int(e) <= max_verse:
                return None
            if s is not None and e is not None and int(e) < int(s):
                return None
            return b, c, s, e
        except (TypeError, ValueError, AttributeError):
            return None

    def _split(self, b, digits):
        digits = str(digits)
        if not digits.isdigit() or len(digits) < 2:
            return None
        opts = []
        for n in range(1, len(digits)):
            cs, vs = digits[:-n], digits[-n:]
            if cs.startswith("0") or vs.startswith("0"):
                continue
            p = self._valid((b, int(cs), int(vs), int(vs)))
            if p:
                opts.append(((len(cs) > 3, len(vs) > 3, abs(len(cs) - len(vs))), p))
        if opts:
            opts.sort(key=lambda x: x[0])
            return opts[0][1]
        return self._valid((b, int(digits), None, None))

    def _fmt(self, label, p):
        b, c, s, e = p
        if s is None:
            return f"{label} {c}"
        return f"{label} {c}:{s}" if e is None or e == s else f"{label} {c}:{s}-{e}"

    def _chapter_info(self, text):
        m = re.fullmatch(r"(.+?)[\s]*([0-9]+)", str(text or "").strip())
        if not m:
            return None
        part, d = m.groups()
        b = self.db.find_book(part.strip())
        if not b:
            return None
        try:
            count = int(self.db.book_meta.get(b, {}).get("chapter_count") or self.db.get_chapter_count(b) or 0)
            c = int(d)
        except (TypeError, ValueError, AttributeError):
            return None
        if not count:
            return None
        if c < 1 or c > count:
            return {"invalid": True}
        return {"book": b, "part": part.strip(), "chapter": c,
                "split": not any(int(d + str(x)) <= count for x in range(10))}

    def _auto(self, text):
        r = str(text or "").strip()
        if not r:
            return r

        m = re.fullmatch(r"([A-Za-z]+)[\s]*(\d+)[\s:：.]+(\d+)(?:\s*-\s*(\d*))?", r)
        if m:
            part, c, s, e = m.groups()
            return f"{part.upper()} {int(c)}:{int(s)}" + (f"-{int(e)}" if e else "")

        m = re.fullmatch(r"([A-Za-z]+)[\s]*([0-9]+)(?:[\s:：.]+([0-9]+))?(?:\s*-\s*([0-9]+))?", r)
        if m:
            code, c, s, e = m.groups()
            b = self._exact(code)
            if b:
                if s:
                    return f"{code.upper()} {int(c)}:{int(s)}" + (f"-{int(e)}" if e else "")
                if len(c) >= 2:
                    p = self._split(b, c)
                    if p and p[2] is not None:
                        return self._fmt(code.upper(), p)
                info = self._chapter_info(f"{b} {c}")
                if info and not info.get("invalid") and info["split"]:
                    return f"{code.upper()} {info['chapter']}:"
        return r

    def _set(self, text, converted_book=None):
        text = str(text or "")
        old = self.search_input.text()
        if text == old:
            if converted_book is not None:
                self._converted_book = converted_book
                self._converted_book_name = text if converted_book else ""
            return
        self._formatting = True
        try:
            self.search_input.setText(text)
            self.search_input.setCursorPosition(len(text))
        finally:
            self._formatting = False
        if converted_book is not None:
            self._converted_book = converted_book
            self._converted_book_name = text if converted_book else ""

    def _parse(self, text):
        r = str(text or "").strip().replace("：", ":").replace("．", ".").replace("。", ".")

        m = re.fullmatch(r"([A-Za-z]+)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d*))?", r)
        if m:
            code, c, s, e = m.groups()
            b = self._exact(code)
            if b:
                return self._valid((b, int(c), int(s), int(e) if e else int(s)))

        m = re.fullmatch(r"([A-Za-z]+)[\s]+(\d+)$", r)
        if m:
            b = self._exact(m.group(1))
            return self._valid((b, int(m.group(2)), None, None)) if b else None

        m = re.fullmatch(r"([A-Za-z]+)(\d+)$", r)
        if m:
            b = self._exact(m.group(1))
            return self._split(b, m.group(2)) if b else None

        return self._valid(self.db.parse_reference(r))

    def _clamp(self, text):
        r = str(text or "").strip().replace("：", ":").replace("．", ".").replace("。", ".")
        m = re.fullmatch(r"(.+?)\s*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d*))?", r)
        if not m:
            return None
        q, cs, ss, es = m.groups()
        b = self.db.find_book(q.strip())
        if not b:
            return None
        try:
            count = int(self.db.book_meta.get(b, {}).get("chapter_count") or self.db.get_chapter_count(b) or 0)
            c = max(1, min(int(cs), count))
            mx = int(self.db.get_verse_count(b, c) or 0)
            s = max(1, min(int(ss), mx))
            e = s
            if es not in (None, ""):
                e = max(s, min(int(es), mx))
            return (b, c, s, e) if mx else None
        except (TypeError, ValueError, AttributeError):
            return None

    def _sanitize_user_text(self, text):
        # 只允许：英文简拼、数字、空格、冒号、点号、短横线。
        return re.sub(r"[^A-Za-z0-9 :：.．。-]", "", str(text or ""))

    def _refresh(self, text, user=True):
        if self._formatting:
            return
        r = str(text or "").strip()

        # 简拼自动变成中文书名后，退格不逐字删除，直接清空整个书名。
        if user and self._converted_book:
            book_name = self._converted_book_name
            if r == "" or (book_name and len(r) < len(book_name) and book_name.startswith(r)):
                self._set("", converted_book=False)
                self.result_list.clear()
                return

        if not r:
            self._converted_book = False
            self._converted_book_name = ""
            self.result_list.clear()
            return

        if user:
            f = self._auto(r)
            if f != r:
                self._set(f)
                r = f

        # 自动转换成中文书名后，继续输入章节时允许中文书名存在。
        if re.fullmatch(r"[\u3400-\u9fff]+", r):
            self.result_list.clear()
            return

        if re.fullmatch(r"([\u3400-\u9fff]+)[\s]+\d+", r):
            self.result_list.clear()
            return

        if re.fullmatch(r"[A-Za-z]+", r):
            cs = self._candidates(r)
            if len(cs) == 1:
                self._set(cs[0], converted_book=True)
                self.result_list.clear()
                return
            if len(cs) > 1:
                self._show_candidates(r)
                return

        p = self._parse(r)
        if p:
            self.result_list.clear()
            b, c, s, e = p
            it = QListWidgetItem("▶ " + self._display(b, c, s, e))
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.result_list.addItem(it)
            self.result_list.setCurrentRow(0)
            return

        p = self._clamp(r)
        if p:
            b, c, s, e = p
            self._set(f"{b} {c}:{s}" if s == e else f"{b} {c}:{s}-{e}", converted_book=False)
            self.result_list.clear()
            it = QListWidgetItem("▶ " + self._display(b, c, s, e))
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.result_list.addItem(it)
            self.result_list.setCurrentRow(0)
            return

        q = re.split(r"[0-9:：.\-\s]+", r, maxsplit=1)[0].strip() if re.search(r"\d", r) else r
        self.result_list.clear()
        for i, b in enumerate(self.db.search_books(q)[:12], 1):
            code = self._code(b).upper()
            short = self.db._short_name(b)
            it = QListWidgetItem(f"{i}. {code or short} {b}")
            it.setData(Qt.ItemDataRole.UserRole, (b, 1, None, None))
            self.result_list.addItem(it)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

    def _on_text_edited(self, text):
        # 粘贴、输入法、键盘输入统一过滤非法字符。
        clean = self._sanitize_user_text(text)
        if clean != text:
            self._set(clean)
            text = clean
        self._refresh(text, True)

    def _display(self, b, c, s, e):
        if s is None:
            return f"{b} {c}章（整章）"
        return f"{b} {c}:{s}" if e is None or e == s else f"{b} {c}:{s}-{e}"

    def _select_current_result_by_space(self):
        """空格确认当前高亮结果：只把书卷名写回输入框，不立即关闭搜索框。"""
        it = self.result_list.currentItem()
        if it is None:
            return False
        p = it.data(Qt.ItemDataRole.UserRole)
        if not p:
            return False
        b, c, s, e = p

        # 空格选择搜索结果时，只显示中文书卷名，保持搜索框继续可输入。
        # 后续再按任意 A-Z 简拼，会从新的简拼搜索开始，而不是继续拼接中文。
        self._set(b, converted_book=True)
        self.result_list.clear()
        return True

    def _on_confirm(self):
        # Enter 必须始终走这里，不依赖全局快捷键。
        text = self.search_input.text().strip()
        p = self._parse(text) or self._clamp(text)
        if p:
            b, c, s, e = p
            if s is None:
                display = f"{b} {c}"
            elif s == e:
                display = f"{b} {c}:{s}"
            else:
                display = f"{b} {c}:{s}-{e}"
            self._set(display, converted_book=False)
            self.search_triggered.emit(p)
            self.close_requested.emit()
            return

        it = self.result_list.currentItem()
        if it is not None:
            p = it.data(Qt.ItemDataRole.UserRole)
            if p:
                self.search_triggered.emit(p)
                self.close_requested.emit()
                return

        self.hint_label.setText("无法识别，请输入例如：CSJ 1:2 或 CSJ 1:2-12")

    def _on_item_clicked(self, item):
        p = item.data(Qt.ItemDataRole.UserRole)
        if p:
            self.search_triggered.emit(p)
            self.close_requested.emit()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            k = event.key()

            if k == Qt.Key.Key_Escape:
                self.close_requested.emit()
                return True

            if obj == self.search_input:
                # 空格：选择当前高亮结果，并把中文书卷名写入搜索框；不关闭搜索框。
                if k == Qt.Key.Key_Space and self.result_list.currentItem() is not None:
                    if self._select_current_result_by_space():
                        return True

                # Backspace/Delete 明确放行给 QLineEdit，保证可以正常删除。
                if k in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                    return super().eventFilter(obj, event)

                if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._on_confirm()
                    return True

                if k == Qt.Key.Key_Down:
                    self._move(1)
                    return True
                if k == Qt.Key.Key_Up:
                    self._move(-1)
                    return True

                txt = event.text()
                if txt and not re.fullmatch(r"[A-Za-z0-9 :：.．。-]", txt):
                    return True

            elif obj == self.result_list:
                if k == Qt.Key.Key_Space:
                    if self._select_current_result_by_space():
                        self.search_input.setFocus()
                        return True
                if k == Qt.Key.Key_Down:
                    self._move(1)
                    return True
                if k == Qt.Key.Key_Up:
                    self._move(-1)
                    return True
                if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._on_confirm()
                    return True

        return super().eventFilter(obj, event)

    def _move(self, d):
        n = self.result_list.count()
        if n:
            row = self.result_list.currentRow()
            if row < 0:
                row = 0
            self.result_list.setCurrentRow(max(0, min(n - 1, row + d)))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_confirm()
            return
        super().keyPressEvent(e)
