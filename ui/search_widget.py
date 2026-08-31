import re
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem,QSizePolicy
from PyQt6.QtGui import QPalette
from PyQt6.QtCore import Qt,pyqtSignal,QEvent

class SearchWidget(QWidget):
    search_triggered=pyqtSignal(tuple); close_requested=pyqtSignal()
    ALLOWED=re.compile(r"[A-Za-z0-9 :：.．。\-]")
    def __init__(self,db,parent=None):
        super().__init__(parent)
        self.db=db; self._formatting=False; self._converted_book=False; self._converted_book_name=""; self._selected_book=None; self._stage="book"; self._space_mode=False
        self._book_cache={}
        self.setObjectName("searchPanel")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.setMinimumWidth(520); self.setMaximumWidth(560)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Maximum)
        lay=QVBoxLayout(self); lay.setContentsMargins(14,14,14,14); lay.setSpacing(8)
        self.search_input=QLineEdit(); self.search_input.setObjectName("searchInput"); self.search_input.setMinimumHeight(44); self.search_input.setPlaceholderText("输入简拼，例如：CSJ"); self.search_input.textEdited.connect(self._on_text_edited); self.search_input.returnPressed.connect(self._on_confirm); lay.addWidget(self.search_input)
        self.hint_label=QLabel(); self.hint_label.setObjectName("searchHint"); self.hint_label.setMinimumHeight(28); self.hint_label.setMaximumHeight(32); self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.hint_label.setWordWrap(False); lay.addWidget(self.hint_label)
        self.result_list=QListWidget(); self.result_list.setObjectName("searchCandidates"); self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.result_list.setSpacing(2); self.result_list.setMinimumWidth(492); self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded); self.result_list.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed); self.result_list.itemClicked.connect(self._on_item_clicked); lay.addWidget(self.result_list)
        self.search_input.installEventFilter(self); self.result_list.installEventFilter(self); self.setFocusProxy(self.search_input); self._apply_theme(); self._set_hint("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出")
    @staticmethod
    def _palette_color(p,role):
        try:
            return p.color(role)
        except TypeError:
            return p.color(QPalette.ColorGroup.Active,role)
    def _apply_theme(self):
        if not all(hasattr(self,x) for x in ("search_input","hint_label","result_list")): return
        p=self.search_input.palette(); base=self._palette_color(p,QPalette.ColorRole.Base); text=self._palette_color(p,QPalette.ColorRole.Text); mid=self._palette_color(p,QPalette.ColorRole.Mid); highlight=self._palette_color(p,QPalette.ColorRole.Highlight); htext=self._palette_color(p,QPalette.ColorRole.HighlightedText)
        panel=self._palette_color(p,QPalette.ColorRole.Window)
        self.setStyleSheet(f"QWidget#searchPanel{{background:{panel.name()};border:1px solid {mid.name()};border-radius:12px;}} QLineEdit#searchInput{{background:{base.name()};color:{text.name()};border:1px solid {mid.name()};border-radius:9px;padding:0 12px;selection-background-color:{highlight.name()};selection-color:{htext.name()};}} QLabel#searchHint{{background:{base.name()};color:{text.name()};border:1px solid {mid.name()};border-radius:9px;padding:2px 10px;}} QListWidget#searchCandidates{{background:{base.name()};color:{text.name()};border:1px solid {mid.name()};border-radius:9px;padding:3px;outline:0;}} QListWidget#searchCandidates::item{{padding:6px 10px;border-radius:6px;min-height:20px;}} QListWidget#searchCandidates::item:selected{{background:{highlight.name()};color:{htext.name()};}}")
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange,QEvent.Type.StyleChange): self._apply_theme()
    def _set_hint(self,text,resize=False):
        self.hint_label.setText(text)
        if resize:self._resize_result_area()
    def _update_hint(self,text): self._set_hint(text,False)
    def _resize_result_area(self,force=True):
        count=self.result_list.count()
        if count:
            rows=min(count,8); row_h=max(32,self.result_list.sizeHintForRow(0)); new_h=rows*row_h+8
            if self.result_list.height()!=new_h:self.result_list.setFixedHeight(new_h)
        else:
            if self.result_list.height()!=0:self.result_list.setFixedHeight(0)
        if force:self.adjustSize()
    def showEvent(self,e):
        super().showEvent(e); self._apply_theme(); self.search_input.setFocus(); self.search_input.selectAll(); self._converted_book=False; self._converted_book_name=""; self._selected_book=None; self._stage="book"; self._space_mode=False; self.result_list.clear(); self._set_hint("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出",True)
    @staticmethod
    def _norm(v): return re.sub(r"[\s._-]+","",str(v or "").strip().lower())
    def _code(self,b): return self._norm(self.db.book_meta.get(b,{}).get("pinyin",""))
    def _candidates(self,q):
        q=self._norm(q)
        if not q:return []
        if q in self._book_cache:return self._book_cache[q]
        result=[b for b in self.db.book_names if self._code(b).startswith(q)]
        self._book_cache[q]=result
        return result
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
        try:self.search_input.setText(t); self.search_input.setCursorPosition(len(t))
        finally:self._formatting=False
        if converted is not None:self._converted_book=bool(converted); self._converted_book_name=t if converted else ""
    def _show_candidates(self,cs):
        self.result_list.setUpdatesEnabled(False); self.result_list.clear()
        for i,b in enumerate(cs[:30],1):
            code=self._code(b).upper(); short=self.db._short_name(b); item=QListWidgetItem(f"{i}.  {code or short}  {b}"); item.setData(Qt.ItemDataRole.UserRole,b); self.result_list.addItem(item)
        self.result_list.setUpdatesEnabled(True)
        if self.result_list.count():self.result_list.setCurrentRow(0)
        self._resize_result_area(True)
    def _move_highlight(self,d):
        if not self.result_list.count():return True
        row=max(0,min(self.result_list.currentRow()+d,self.result_list.count()-1)); self.result_list.setCurrentRow(row); self.result_list.scrollToItem(self.result_list.currentItem()); return True
    def _select_current_book(self):
        item=self.result_list.currentItem()
        if item is None:return False
        b=item.data(Qt.ItemDataRole.UserRole)
        if not b:return False
        self._selected_book=b; self._stage="chapter"; self._space_mode=False; self._set_text(b,True); self.result_list.clear(); self._resize_result_area(True); self._update_hint(f"已选择 {b}　输入章节后按空格进入节号"); self.search_input.setFocus(); self.search_input.setCursorPosition(len(b)); return True
    def _suffix(self): return self.search_input.text()[len(self._selected_book):] if self._selected_book and self.search_input.text().startswith(self._selected_book) else ""
    def _space_after_chapter(self):
        s=self._suffix().strip()
        if not re.fullmatch(r"\d+",s):return True
        c=int(s); mx=self._chapter_count(self._selected_book)
        if not 1<=c<=mx:self._update_hint(f"章节超出范围，本书最多 {mx} 章"); return True
        self._stage="verse"; self._set_text(f"{self._selected_book} {c}:"); self._update_hint("请输入开始节　按空格自动生成 -"); return True
    def _space_after_verse(self):
        s=self._suffix().strip(); m=re.fullmatch(r"(\d+)\s*:\s*(\d+)",s)
        if not m:return True
        c,v=map(int,m.groups()); mx=self._verse_count(self._selected_book,c)
        if not 1<=v<=mx:self._update_hint(f"本章最多 {mx} 节"); return True
        self._space_mode=True; self._set_text(f"{self._selected_book} {c}:{v}-"); self._update_hint(f"请输入结束节（{v}-{mx}）"); return True
    def _delete_segment(self):
        if not self._selected_book:
            text=self.search_input.text(); new_text=text[:-1] if text else ""
            self._set_text(new_text); self._refresh_book_state(new_text); self.search_input.setFocus(); self.search_input.setCursorPosition(len(new_text)); return True
        text=self.search_input.text(); b=self._selected_book; suffix=text[len(b):] if text.startswith(b) else ""
        patterns=[(r"\s*(\d+)\s*:\s*(\d+)\s*-\s*(\d+)\s*$",lambda m:f"{b} {m.group(1)}:{m.group(2)}-", "verse_range"),(r"\s*(\d+)\s*:\s*(\d+)\s*-\s*$",lambda m:f"{b} {m.group(1)}:{m.group(2)}", "verse"),(r"\s*(\d+)\s*:\s*(\d+)\s*$",lambda m:f"{b} {m.group(1)}:", "verse"),(r"\s*(\d+)\s*:\s*$",lambda m:f"{b} {m.group(1)}", "chapter"),(r"\s*(\d+)\s*$",lambda m:b, "chapter")]
        for pat,make,stage in patterns:
            m=re.fullmatch(pat,suffix)
            if m:
                self._set_text(make(m)); self._stage=stage; self._space_mode=(stage=="verse_range"); self._refresh_selected(b,self._suffix()); self._update_hint_for_stage(); self.search_input.setFocus(); return True
        self._set_text(""); self._selected_book=None; self._stage="book"; self._space_mode=False; self._converted_book=False; self._converted_book_name=""; self.result_list.clear(); self._resize_result_area(True); self._update_hint("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出"); self.search_input.setFocus(); self.search_input.setCursorPosition(0); return True
    def _refresh_book_state(self,text):
        self._stage="book"; self._selected_book=None; self._converted_book=False; self._converted_book_name=""; self._space_mode=False
        q=text.strip()
        if not q:
            self.result_list.clear(); self.result_list.setFixedHeight(0); self._update_hint("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出"); return
        if re.fullmatch(r"[A-Za-z]+",q):
            cs=self._candidates(q)
            if not cs:cs=self.db.search_books(q) or []
            self._show_candidates(cs)
        else:
            self.result_list.clear(); self.result_list.setFixedHeight(0)
        self._update_hint("输入简拼　↑↓选择　空格选择/下一段　Enter确认　Esc退出")
    def _update_hint_for_stage(self):
        if not self._selected_book:return
        if self._stage=="chapter":self._update_hint(f"已选择 {self._selected_book}　输入章节后按空格进入节号")
        elif self._stage=="verse":self._update_hint("请输入开始节　按空格自动生成 -")
        elif self._space_mode:self._update_hint("请输入结束节")
    def eventFilter(self,obj,event):
        if event.type()!=QEvent.Type.KeyPress:return super().eventFilter(obj,event)
        k=event.key()
        if k==Qt.Key.Key_Escape:self.close_requested.emit(); return True
        if obj is self.search_input:
            if k==Qt.Key.Key_Up:return self._move_highlight(-1)
            if k==Qt.Key.Key_Down:return self._move_highlight(1)
            if k==Qt.Key.Key_Space:
                if self._stage=="book" and self.result_list.count():return self._select_current_book()
                if self._stage=="chapter" and self._selected_book:return self._space_after_chapter()
                if self._stage=="verse" and self._selected_book:return self._space_after_verse()
                return True
            if k in (Qt.Key.Key_Backspace,Qt.Key.Key_Delete):return self._delete_segment()
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
            if clean!=text:self._set_text(clean); text=clean
            self._refresh_book_state(text); return
        if not self._selected_book:return
        b=self._selected_book
        if not text.startswith(b):self._set_text(b,True);return
        suffix=text[len(b):]
        if not re.fullmatch(r"[\s0-9:：.．。\-]*",suffix):suffix=re.sub(r"[^0-9 :：.．。\-]","",suffix);self._set_text(b+suffix)
        self._refresh_selected(b,suffix)
    def _refresh_selected(self,b,suffix):
        s=suffix.strip().replace("：",":").replace("．",".").replace("。","."); self.result_list.clear()
        if not s:self.result_list.setFixedHeight(0); self._update_hint_for_stage(); return
        m=re.fullmatch(r"(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?",s)
        if not m:self.result_list.setFixedHeight(0); return
        c,v,e=m.groups(); c=int(c); mx=self._chapter_count(b)
        if not 1<=c<=mx:self._update_hint(f"章节超出范围，本书最多 {mx} 章"); self.result_list.setFixedHeight(0); return
        if v is None:
            item=QListWidgetItem(f"▶  {b}  {c}章（整章）"); item.setData(Qt.ItemDataRole.UserRole,(b,c,None,None)); self.result_list.addItem(item); self.result_list.setCurrentRow(0); self._resize_result_area(True); return
        v=int(v); mv=self._verse_count(b,c)
        if not 1<=v<=mv:self._update_hint(f"第 {c} 章最多 {mv} 节"); self.result_list.setFixedHeight(0); return
        if e is None:
            if "-" in s:self._update_hint(f"请输入结束节（{v}-{mv}）"); self.result_list.setFixedHeight(0); return
            item=QListWidgetItem(f"▶  {b}  {c}:{v}"); item.setData(Qt.ItemDataRole.UserRole,(b,c,v,v)); self.result_list.addItem(item); self.result_list.setCurrentRow(0); self._resize_result_area(True); return
        if e=="":self._update_hint(f"请输入结束节（{v}-{mv}）"); self.result_list.setFixedHeight(0); return
        e=int(e)
        if e<v:self._update_hint(f"结束节不能小于开始节 {v}"); self.result_list.setFixedHeight(0); return
        if e>mv:self._update_hint(f"本章最多 {mv} 节，不能输入 {e}"); self.result_list.setFixedHeight(0); return
        item=QListWidgetItem(f"▶  {b}  {c}:{v}-{e}"); item.setData(Qt.ItemDataRole.UserRole,(b,c,v,e)); self.result_list.addItem(item); self.result_list.setCurrentRow(0); self._resize_result_area(True)
    def _parse(self,text):
        r=text.strip().replace("：",":").replace("．",".").replace("。","."); b=self._selected_book
        if not b:
            m=re.match(r"^([A-Za-z]+)",r); b=self._exact(m.group(1)) if m else None
        if not b:return None
        s=r[len(b):].strip() if r.startswith(b) else r
        m=re.fullmatch(r"(\d+)",s)
        if m:
            c=int(m.group(1)); return (b,c,None,None) if 1<=c<=self._chapter_count(b) else None
        m=re.fullmatch(r"(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?",s)
        if not m:return None
        c,v,e=m.groups(); c=int(c); v=int(v); e=int(e) if e else v; mv=self._verse_count(b,c)
        return (b,c,v,e) if 1<=c<=self._chapter_count(b) and 1<=v<=e<=mv else None
    def _on_item_clicked(self,item):
        d=item.data(Qt.ItemDataRole.UserRole)
        if not d:return
        if isinstance(d,tuple) and len(d)==4 and d[2] is not None:self.search_triggered.emit(d); self.close_requested.emit(); return
        b=d[0] if isinstance(d,tuple) else d; self._selected_book=b; self._stage="chapter"; self._set_text(b,True); self.result_list.clear(); self._resize_result_area(True); self.search_input.setFocus(); self._update_hint(f"已选择 {b}　输入章节后按空格进入节号")
    def _on_confirm(self):
        p=self._parse(self.search_input.text())
        if p:self.search_triggered.emit(p); self.close_requested.emit(); return
        if self._stage=="book" and self.result_list.count():self._select_current_book(); return
        self._update_hint("请输入有效的书卷、章节或节范围")