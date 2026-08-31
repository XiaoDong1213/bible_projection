# ui/search_widget.py
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal, QEvent


class SearchWidget(QWidget):
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
        self._selected_book = None
        self._stage = "book"
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(4)
        self.search_input = QLineEdit(); self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("输入简拼，例如：CSJ")
        self.search_input.textEdited.connect(self._on_text_edited); self.search_input.returnPressed.connect(self._on_confirm)
        lay.addWidget(self.search_input)
        self.hint_label = QLabel("输入简拼　↑↓选择　空格选择/进入下一段　Enter确认　Esc退出"); lay.addWidget(self.hint_label)
        self.result_list = QListWidget(); self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.result_list.itemClicked.connect(self._on_item_clicked); lay.addWidget(self.result_list)
        self.search_input.installEventFilter(self); self.result_list.installEventFilter(self); self.setFocusProxy(self.search_input)

    def showEvent(self, event):
        super().showEvent(event); self.search_input.setFocus(); self.search_input.selectAll()
        self._converted_book=False; self._converted_book_name=""; self._selected_book=None; self._stage="book"; self.result_list.clear()

    @staticmethod
    def _norm(value): return re.sub(r"[\s._-]+", "", str(value or "").strip().lower())
    def _code(self, book): return self._norm(self.db.book_meta.get(book, {}).get("pinyin", ""))
    def _candidates(self, q):
        q=self._norm(q); return [b for b in self.db.book_names if self._code(b).startswith(q)] if q else []
    def _exact(self, q):
        q=self._norm(q)
        for b in self.db.book_names:
            if self._code(b)==q: return b
        return None
    def _chapter_count(self,b):
        try: return int(self.db.book_meta.get(b,{}).get("chapter_count") or self.db.get_chapter_count(b) or 0)
        except Exception: return 0
    def _verse_count(self,b,c):
        try: return int(self.db.get_verse_count(b,c) or 0)
        except Exception: return 0
    def _set_text(self,t,converted=None):
        t=str(t or ""); self._formatting=True
        try: self.search_input.setText(t); self.search_input.setCursorPosition(len(t))
        finally: self._formatting=False
        if converted is not None:
            self._converted_book=bool(converted); self._converted_book_name=t if converted else ""

    def _show_candidates(self,candidates):
        self.result_list.clear()
        for i,b in enumerate(candidates[:30],1):
            item=QListWidgetItem(f"{self._code(b).upper()}  {b}"); item.setData(Qt.ItemDataRole.UserRole,b); self.result_list.addItem(item)
        if self.result_list.count(): self.result_list.setCurrentRow(0); self.result_list.scrollToItem(self.result_list.currentItem())

    def _move_highlight(self,delta):
        if not self.result_list.count(): return True
        row=self.result_list.currentRow(); row=max(0,min(row+delta,self.result_list.count()-1))
        self.result_list.setCurrentRow(row); self.result_list.scrollToItem(self.result_list.currentItem()); return True

    def _select_current_result_by_space(self):
        item=self.result_list.currentItem()
        if item is None: return False
        book=item.data(Qt.ItemDataRole.UserRole)
        if not book: return False
        self._selected_book=book; self._stage="chapter"; self._set_text(book,converted=True); self.result_list.clear()
        self.search_input.setFocus(); self.search_input.setCursorPosition(len(book)); return True

    def eventFilter(self,obj,event):
        if event.type()!=QEvent.Type.KeyPress: return super().eventFilter(obj,event)
        key=event.key()
        if key==Qt.Key.Key_Escape: self.close_requested.emit(); return True
        if obj is self.search_input:
            if key==Qt.Key.Key_Up: return self._move_highlight(-1)
            if key==Qt.Key.Key_Down: return self._move_highlight(1)
            if key==Qt.Key.Key_Space:
                if self._stage=="book" and self.result_list.count(): return self._select_current_result_by_space()
                if self._stage=="chapter" and self._selected_book:
                    suffix=self.search_input.text()[len(self._selected_book):].strip()
                    if re.fullmatch(r"\d+",suffix):
                        self._stage="verse"; self._set_text(self._selected_book+" "+suffix+" ",converted=False); return True
                    if not suffix:
                        self._stage="verse"; self._set_text(self._selected_book+" ",converted=False); return True
                    return True
                return True
            if self._converted_book and self._is_letter_key(key): return True
            if self._converted_book and key in (Qt.Key.Key_Backspace,Qt.Key.Key_Delete):
                self._set_text("",converted=False); self._selected_book=None; self._stage="book"; self.result_list.clear(); return True
            allowed={Qt.Key.Key_Backspace,Qt.Key.Key_Delete,Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Home,Qt.Key.Key_End,Qt.Key.Key_Return,Qt.Key.Key_Enter}
            if not(event.modifiers() & Qt.KeyboardModifier.ControlModifier) and key not in allowed:
                txt=event.text()
                if txt and not all(self.ALLOWED.fullmatch(ch) for ch in txt): return True
        return super().eventFilter(obj,event)

    def _is_letter_key(self,key): return Qt.Key.Key_A<=key<=Qt.Key.Key_Z
    def _sanitize(self,t): return "".join(ch for ch in str(t or "") if self.ALLOWED.fullmatch(ch))

    def _on_text_edited(self,text):
        if self._formatting:return
        if self._stage=="book":
            clean=self._sanitize(text)
            if clean!=text:self._set_text(clean);text=clean
            q=text.strip();self.result_list.clear()
            if re.fullmatch(r"[A-Za-z]+",q):
                candidates=self._candidates(q)
                if candidates:self._show_candidates(candidates)
                else:
                    matches=self.db.search_books(q)
                    if matches:self._show_candidates(matches)
            return
        if self._selected_book:
            book=self._selected_book
            if not text.startswith(book):
                self._set_text(book,converted=True);return
            suffix=text[len(book):]
            if not re.fullmatch(r"[\s0-9:：.．。\-]*",suffix):
                self._set_text(book+re.sub(r"[^0-9 :：.．。\-]","",suffix),converted=False);return
            self._refresh_selected(book,suffix)

    def _refresh_selected(self,book,suffix):
        s=suffix.strip();self.result_list.clear()
        if not s:return
        m=re.fullmatch(r"(\d+)(?:\s*(?::|[.\s])\s*(\d+)(?:\s*-\s*(\d*)?)?)?",s)
        if not m:return
        c,v,e=m.groups();c=int(c)
        if v is None:
            if 1<=c<=self._chapter_count(book):
                item=QListWidgetItem(f"▶ {book} {c}章（整章）");item.setData(Qt.ItemDataRole.UserRole,(book,c,None,None));self.result_list.addItem(item);self.result_list.setCurrentRow(0)
            return
        v=int(v);e=int(e) if e else v;mv=self._verse_count(book,c)
        if not mv or not(1<=v<=e<=mv):return
        item=QListWidgetItem(f"▶ {book} {c}:{v}" if v==e else f"▶ {book} {c}:{v}-{e}");item.setData(Qt.ItemDataRole.UserRole,(book,c,v,e));self.result_list.addItem(item);self.result_list.setCurrentRow(0)

    def _parse(self,text):
        r=text.strip().replace("：",":").replace("．",".").replace("。",".");b=self._selected_book
        if not b:
            m=re.match(r"^([A-Za-z]+)",r);b=self._exact(m.group(1)) if m else None
        if not b:return None
        s=r[len(b):].strip() if r.startswith(b) else r
        m=re.fullmatch(r"(\d+)",s)
        if m:
            c=int(m.group(1));return (b,c,None,None) if 1<=c<=self._chapter_count(b) else None
        m=re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?",s)
        if not m:return None
        c,v,e=m.groups();c=int(c);v=int(v);e=int(e) if e else v;mv=self._verse_count(b,c)
        return (b,c,v,e) if 1<=c<=self._chapter_count(b) and 1<=v<=e<=mv else None

    def _on_item_clicked(self,item):
        data=item.data(Qt.ItemDataRole.UserRole)
        if not data:return
        if isinstance(data,tuple):
            if len(data)==4 and data[1] is not None and data[2] is not None:
                self.search_triggered.emit(data);self.close_requested.emit();return
            book=data[0]
        else: book=data
        self._selected_book=book;self._stage="chapter";self._set_text(book,converted=True);self.result_list.clear();self.search_input.setFocus()

    def _on_confirm(self):
        p=self._parse(self.search_input.text())
        if p:self.search_triggered.emit(p);self.close_requested.emit();return
        if self._stage=="book" and self.result_list.count(): self._select_current_result_by_space();return
        self.hint_label.setText("请输入有效的章节或节号")

    def _confirm_current_item(self): return False
