# ui/search_widget.py
import re
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem
from PyQt6.QtCore import Qt,pyqtSignal,QEvent

class SearchWidget(QWidget):
    search_triggered=pyqtSignal(tuple); close_requested=pyqtSignal()
    ALLOWED=re.compile(r"[A-Za-z0-9 :：.．。\-]")
    def __init__(self,db,parent=None):
        super().__init__(parent); self.db=db; self._formatting=False; self._converted_book=False; self._converted_book_name=""; self._selected_book=None; self._stage="book"; self._space_mode=False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.Popup); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay=QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(6)
        self.search_input=QLineEdit(); self.search_input.setObjectName("searchInput"); self.search_input.setPlaceholderText("输入简拼，例如：CSJ"); self.search_input.textEdited.connect(self._on_text_edited); self.search_input.returnPressed.connect(self._on_confirm); lay.addWidget(self.search_input)
        self.hint_label=QLabel("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出")
        self.hint_label.setMinimumHeight(28); self.hint_label.setMaximumHeight(34); self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("QLabel { background: #eeeeee; color: #666666; padding: 3px 8px; border: 1px solid #d2d2d2; border-radius: 4px; }")
        lay.addWidget(self.hint_label)
        self.result_list=QListWidget(); self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.result_list.setSpacing(2); self.result_list.itemClicked.connect(self._on_item_clicked); lay.addWidget(self.result_list)
        self.search_input.installEventFilter(self); self.result_list.installEventFilter(self); self.setFocusProxy(self.search_input)
    def _update_hint(self,text):
        self.hint_label.setText(text); self.hint_label.updateGeometry(); self.adjustSize()
    def _resize_result_area(self):
        count=self.result_list.count()
        if count:
            row_h=max(26,self.result_list.sizeHintForRow(0)); self.result_list.setFixedHeight(min(count,8)*row_h+4)
        else:self.result_list.setFixedHeight(0)
        self.adjustSize()
    def showEvent(self,e):
        super().showEvent(e); self.search_input.setFocus(); self.search_input.selectAll(); self._converted_book=False; self._converted_book_name=""; self._selected_book=None; self._stage="book"; self._space_mode=False; self.result_list.clear(); self._resize_result_area(); self._update_hint("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出")
    @staticmethod
    def _norm(v):return re.sub(r"[\s._-]+","",str(v or "").strip().lower())
    def _code(self,b):return self._norm(self.db.book_meta.get(b,{}).get("pinyin",""))
    def _candidates(self,q):
        q=self._norm(q);return [b for b in self.db.book_names if self._code(b).startswith(q)] if q else []
    def _exact(self,q):
        q=self._norm(q)
        for b in self.db.book_names:
            if self._code(b)==q:return b
        return None
    def _chapter_count(self,b):
        try:return int(self.db.book_meta.get(b,{}).get("chapter_count") or self.db.get_chapter_count(b) or 0)
        except Exception:return 0
    def _verse_count(self,b,c):
        try:return int(self.db.get_verse_count(b,c) or 0)
        except Exception:return 0
    def _set_text(self,t,converted=None):
        t=str(t or ""); self._formatting=True
        try:self.search_input.setText(t);self.search_input.setCursorPosition(len(t))
        finally:self._formatting=False
        if converted is not None:self._converted_book=bool(converted);self._converted_book_name=t if converted else ""
    def _show_candidates(self,cs):
        self.result_list.clear()
        for i,b in enumerate(cs[:30],1):
            code=self._code(b).upper();short=self.db._short_name(b);item=QListWidgetItem(f"{i}. {code or short} {b}");item.setData(Qt.ItemDataRole.UserRole,b);self.result_list.addItem(item)
        if self.result_list.count():self.result_list.setCurrentRow(0);self.result_list.scrollToItem(self.result_list.currentItem())
        self._resize_result_area()
    def _move_highlight(self,d):
        if not self.result_list.count():return True
        row=max(0,min(self.result_list.currentRow()+d,self.result_list.count()-1));self.result_list.setCurrentRow(row);self.result_list.scrollToItem(self.result_list.currentItem());return True
    def _select_current_book(self):
        item=self.result_list.currentItem()
        if item is None:return False
        b=item.data(Qt.ItemDataRole.UserRole)
        if not b:return False
        self._selected_book=b;self._stage="chapter";self._space_mode=False;self._set_text(b,True);self.result_list.clear();self._resize_result_area();self.search_input.setFocus();self.search_input.setCursorPosition(len(b));self._update_hint(f"已选择 {b}　输入章节后按空格进入节号");return True
    def _suffix(self):return self.search_input.text()[len(self._selected_book):] if self._selected_book and self.search_input.text().startswith(self._selected_book) else ""
    def _space_after_chapter(self):
        s=self._suffix().strip()
        if not re.fullmatch(r"\d+",s):return True
        c=int(s);mx=self._chapter_count(self._selected_book)
        if not 1<=c<=mx:self._update_hint(f"章节超出范围，本书最多 {mx} 章");return True
        self._stage="verse";self._set_text(f"{self._selected_book} {c}:");self._update_hint("请输入开始节，按空格自动生成 -");return True
    def _space_after_verse(self):
        s=self._suffix().strip();m=re.fullmatch(r"(\d+)\s*:\s*(\d+)",s)
        if not m:return True
        c,v=map(int,m.groups());mx=self._verse_count(self._selected_book,c)
        if not 1<=v<=mx:self._update_hint(f"本章最多 {mx} 节");return True
        self._space_mode=True;self._set_text(f"{self._selected_book} {c}:{v}-");self._update_hint(f"请输入结束节（{v}-{mx}）");return True
    def _delete_segment(self):
        if not self._selected_book:return False
        text=self.search_input.text();b=self._selected_book;suffix=text[len(b):] if text.startswith(b) else ""
        if re.fullmatch(r"\s*\d+\s*:\s*\d+\s*-\s*\d+\s*",suffix):
            c,v,e=re.fullmatch(r"(\d+)\s*:\s*(\d+)\s*-\s*(\d+)",suffix.strip()).groups();self._set_text(f"{b} {c}:{v}-");self._stage="verse";self._space_mode=True;return True
        if re.fullmatch(r"\s*\d+\s*:\s*\d+\s*-\s*",suffix):
            c,v=re.fullmatch(r"(\d+)\s*:\s*(\d+)\s*-",suffix.strip()).groups();self._set_text(f"{b} {c}:{v}");self._stage="verse";self._space_mode=False;return True
        if re.fullmatch(r"\s*\d+\s*:\s*\d+\s*",suffix):
            c,v=re.fullmatch(r"\s*(\d+)\s*:\s*(\d+)\s*",suffix).groups();self._set_text(f"{b} {c}:");self._stage="verse";return True
        if re.fullmatch(r"\s*\d+\s*:\s*",suffix):
            c=re.fullmatch(r"\s*(\d+)\s*:\s*",suffix).group(1);self._set_text(f"{b} {c}");self._stage="chapter";return True
        if re.fullmatch(r"\s*\d+\s*",suffix):
            self._set_text(b,True);self._stage="chapter";self._space_mode=False;self.result_list.clear();self._resize_result_area();return True
        self._set_text("");self._selected_book=None;self._stage="book";self._space_mode=False;self.result_list.clear();self._resize_result_area();return True
    def eventFilter(self,obj,event):
        if event.type()!=QEvent.Type.KeyPress:return super().eventFilter(obj,event)
        k=event.key()
        if k==Qt.Key.Key_Escape:self.close_requested.emit();return True
        if obj is self.search_input:
            if k==Qt.Key.Key_Up:return self._move_highlight(-1)
            if k==Qt.Key.Key_Down:return self._move_highlight(1)
            if k==Qt.Key.Key_Space:
                if self._stage=="book" and self.result_list.count():return self._select_current_book()
                if self._stage=="chapter" and self._selected_book:return self._space_after_chapter()
                if self._stage=="verse" and self._selected_book:return self._space_after_verse()
                return True
            if k in (Qt.Key.Key_Backspace,Qt.Key.Key_Delete):
                if self._selected_book:return self._delete_segment()
            if self._converted_book and self._is_letter(k):return True
            allowed={Qt.Key.Key_Left,Qt.Key.Key_Right,Qt.Key.Key_Home,Qt.Key.Key_End,Qt.Key.Key_Return,Qt.Key.Key_Enter}
            if not(event.modifiers()&Qt.KeyboardModifier.ControlModifier) and k not in allowed:
                if event.text() and not all(self.ALLOWED.fullmatch(c) for c in event.text()):return True
        return super().eventFilter(obj,event)
    def _is_letter(self,k):return Qt.Key.Key_A<=k<=Qt.Key.Key_Z
    def _on_text_edited(self,text):
        if self._formatting:return
        if self._stage=="book":
            clean="".join(c for c in text if self.ALLOWED.fullmatch(c))
            if clean!=text:self._set_text(clean);text=clean
            self.result_list.clear();q=text.strip()
            if re.fullmatch(r"[A-Za-z]+",q):
                cs=self._candidates(q) or self.db.search_books(q)
                if cs:self._show_candidates(cs)
            self._resize_result_area();return
        if not self._selected_book:return
        b=self._selected_book
        if not text.startswith(b):self._set_text(b,True);return
        suffix=text[len(b):]
        if not re.fullmatch(r"[\s0-9:：.．。\-]*",suffix):
            suffix=re.sub(r"[^0-9 :：.．。\-]","",suffix);self._set_text(b+suffix)
        self._refresh_selected(b,suffix)
    def _refresh_selected(self,b,suffix):
        s=suffix.strip().replace("：",":").replace("．",".").replace("。",".");self.result_list.clear()
        if not s:self._resize_result_area();return
        m=re.fullmatch(r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?",s)
        if not m:self._resize_result_area();return
        c,v,e=m.groups();c=int(c);mx=self._chapter_count(b)
        if not 1<=c<=mx:self._update_hint(f"章节超出范围，本书最多 {mx} 章");self._resize_result_area();return
        if v is None:
            item=QListWidgetItem(f"▶ {b} {c}章（整章）");item.setData(Qt.ItemDataRole.UserRole,(b,c,None,None));self.result_list.addItem(item);self.result_list.setCurrentRow(0);self._resize_result_area();return
        v=int(v);mv=self._verse_count(b,c)
        if not 1<=v<=mv:self._update_hint(f"第 {c} 章最多 {mv} 节");self._resize_result_area();return
        if e is None:
            if "-" in s:self._update_hint(f"请输入结束节（{v}-{mv}）");self._resize_result_area();return
            item=QListWidgetItem(f"▶ {b} {c}:{v}");item.setData(Qt.ItemDataRole.UserRole,(b,c,v,v));self.result_list.addItem(item);self.result_list.setCurrentRow(0);self._resize_result_area();return
        if e=="":self._update_hint(f"请输入结束节（{v}-{mv}）");self._resize_result_area();return
        e=int(e)
        if e<v:self._update_hint(f"结束节不能小于开始节 {v}");self._resize_result_area();return
        if e>mv:self._update_hint(f"本章最多 {mv} 节，不能输入 {e}");self._resize_result_area();return
        item=QListWidgetItem(f"▶ {b} {c}:{v}-{e}");item.setData(Qt.ItemDataRole.UserRole,(b,c,v,e));self.result_list.addItem(item);self.result_list.setCurrentRow(0);self._resize_result_area()
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
        d=item.data(Qt.ItemDataRole.UserRole)
        if not d:return
        if isinstance(d,tuple) and len(d)==4 and d[2] is not None:self.search_triggered.emit(d);self.close_requested.emit();return
        b=d[0] if isinstance(d,tuple) else d;self._selected_book=b;self._stage="chapter";self._set_text(b,True);self.result_list.clear();self._resize_result_area();self.search_input.setFocus();self._update_hint(f"已选择 {b}　输入章节后按空格进入节号")
    def _on_confirm(self):
        p=self._parse(self.search_input.text())
        if p:self.search_triggered.emit(p);self.close_requested.emit();return
        if self._stage=="book" and self.result_list.count():self._select_current_book();return
        self._update_hint("请输入有效的书卷、章节或节范围")
