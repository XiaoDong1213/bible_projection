import re
import sys
import ctypes
from ctypes import wintypes
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem
from PyQt6.QtCore import Qt,pyqtSignal

class SearchLineEdit(QLineEdit):
    special_key=pyqtSignal(int)
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Escape,Qt.Key.Key_Up,Qt.Key.Key_Down,Qt.Key.Key_Space,Qt.Key.Key_Backspace,Qt.Key.Key_Delete):
            self.special_key.emit(event.key());event.accept();return
        super().keyPressEvent(event)

class SearchWidget(QWidget):
    search_triggered=pyqtSignal(tuple);close_requested=pyqtSignal()
    ALLOWED=re.compile(r"[A-Za-z0-9 :：.．。\-]")
    def __init__(self,db,parent=None):
        super().__init__(parent);self.db=db;self._formatting=False;self._converted_book=False;self._selected_book=None;self._stage='book';self._space_mode=False;self._candidate_cache={};self._confirming=False
        self.setObjectName('searchPanel');self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.Popup);self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground,True);self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground,True);self.setMinimumWidth(660);self.setMaximumWidth(900)
        l=QVBoxLayout(self);l.setContentsMargins(22,22,22,18);l.setSpacing(0)
        self.search_input=SearchLineEdit();self.search_input.setObjectName('searchInput');self.search_input.setMinimumHeight(58);self.search_input.setPlaceholderText('输入书卷简拼、章节或节号');self.search_input.setClearButtonEnabled(False);self.search_input.textEdited.connect(self._on_text_edited);self.search_input.special_key.connect(self._on_special_key);l.addWidget(self.search_input)
        self.hint_label=QLabel('↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭');self.hint_label.setObjectName('searchHint');self.hint_label.setMinimumHeight(34);self.hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter);l.addWidget(self.hint_label)
        self.result_list=QListWidget();self.result_list.setObjectName('searchCandidates');self.result_list.setFocusPolicy(Qt.FocusPolicy.NoFocus);self.result_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.result_list.setFrameShape(self.result_list.Shape.NoFrame);self.result_list.setSpacing(4);self.result_list.setUniformItemSizes(True);self.result_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel);self.result_list.itemClicked.connect(self._on_item_clicked);l.addWidget(self.result_list)
        self._apply_visual_style();self._resize_result_area()
    def _apply_visual_style(self):
        self.setStyleSheet('''QWidget#searchPanel{background:transparent;border:none}QLineEdit#searchInput{background:rgba(255,255,255,220);color:palette(text);border:1px solid rgba(255,255,255,180);border-radius:17px;padding:0 20px;selection-background-color:palette(highlight);selection-color:palette(highlighted-text)}QLineEdit#searchInput:focus{border:2px solid palette(highlight)}QLabel#searchHint{background:transparent;color:palette(text);border:none;padding:0 7px}QListWidget#searchCandidates{background:transparent;color:palette(text);border:none;padding:4px 0 0 0;outline:none}QListWidget#searchCandidates::item{background:rgba(255,255,255,55);color:palette(text);border:1px solid rgba(255,255,255,70);border-radius:11px;padding:9px 16px;min-height:25px}QListWidget#searchCandidates::item:hover{background:rgba(255,255,255,90)}QListWidget#searchCandidates::item:selected{background:rgba(80,140,255,115);color:palette(text);border:1px solid rgba(255,255,255,120)}''');self._update_native_acrylic()
    def _update_native_acrylic(self):
        if sys.platform!='win32':return
        try:
            hwnd=int(self.winId());u=ctypes.windll.user32
            class A(ctypes.Structure):_fields_=[('AccentState',wintypes.DWORD),('AccentFlags',wintypes.DWORD),('GradientColor',wintypes.DWORD),('AnimationId',wintypes.DWORD)]
            class D(ctypes.Structure):_fields_=[('Attribute',wintypes.DWORD),('Data',ctypes.c_void_p),('SizeOfData',wintypes.SIZE)]
            dark=self.palette().window().color().lightness()<128
            # 更实的玻璃，减少背景干扰；高亮独立使用半透明主题色。
            gradient=0xE61C1712 if dark else 0xE6FFFFFF
            policy=A(4,2,gradient,0);data=D(19,ctypes.addressof(policy),ctypes.sizeof(policy));fn=getattr(u,'SetWindowCompositionAttribute',None)
            if fn:fn.argtypes=[wintypes.HWND,ctypes.POINTER(D)];fn.restype=wintypes.BOOL;fn(hwnd,ctypes.byref(data))
        except Exception:pass
    def showEvent(self,event):
        super().showEvent(event);self._formatting=False;self._converted_book=False;self._selected_book=None;self._stage='book';self._space_mode=False;self._confirming=False;self.result_list.clear();self._resize_result_area();self._update_hint('↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭');self.search_input.setFocus();self.search_input.selectAll();self._update_native_acrylic()
    def _update_hint(self,text):self.hint_label.setText(text);self._resize_result_area()
    def _resize_result_area(self):
        n=min(self.result_list.count(),8)
        if n:
            h=max(42,self.result_list.sizeHintForRow(0));self.result_list.setFixedHeight(n*h+max(0,n-1)*4+8)
        else:self.result_list.setFixedHeight(0)
        self.adjustSize()
    @staticmethod
    def _norm(v):return re.sub(r'[\s._-]+','',str(v or '').strip().lower())
    def _code(self,b):return self._norm(self.db.book_meta.get(b,{}).get('pinyin',''))
    def _candidates(self,q):
        q=self._norm(q)
        if q in self._candidate_cache:return self._candidate_cache[q]
        r=[b for b in self.db.book_names if self._code(b).startswith(q)] if q else [];self._candidate_cache[q]=r;return r
    def _exact(self,q):
        q=self._norm(q)
        for b in self.db.book_names:
            if self._code(b)==q:return b
        return None
    def _chapter_count(self,b):
        try:return int(self.db.book_meta.get(b,{}).get('chapter_count') or self.db.get_chapter_count(b) or 0)
        except:return 0
    def _verse_count(self,b,c):
        try:return int(self.db.get_verse_count(b,c) or 0)
        except:return 0
    def _set_text(self,t,converted=None):
        self._formatting=True
        try:v=str(t or '');self.search_input.setText(v);self.search_input.setCursorPosition(len(v))
        finally:self._formatting=False
        if converted is not None:self._converted_book=bool(converted)
    def _show_candidates(self,books):
        self.result_list.setUpdatesEnabled(False)
        try:
            self.result_list.clear()
            for i,b in enumerate(books,1):
                code=self._code(b).upper();short=self.db._short_name(b);it=QListWidgetItem(f'{i:02d}    {code or short}    {b}');it.setData(Qt.ItemDataRole.UserRole,b);self.result_list.addItem(it)
        finally:self.result_list.setUpdatesEnabled(True)
        if self.result_list.count():self.result_list.setCurrentRow(0)
        self._resize_result_area()
    def _move_highlight(self,d):
        if not self.result_list.count():return
        r=max(0,min(self.result_list.currentRow()+d,self.result_list.count()-1));self.result_list.setCurrentRow(r);self.result_list.scrollToItem(self.result_list.currentItem(),QListWidget.ScrollHint.PositionAtCenter)
    def _select_current_book(self):
        it=self.result_list.currentItem()
        if it is None:return
        b=it.data(Qt.ItemDataRole.UserRole)
        if not b:return
        self._selected_book=b;self._stage='chapter';self._space_mode=False;self._set_text(b,True);self.result_list.clear();self._resize_result_area();self._update_hint(f'已选择 {b}　·　请输入章节　·　Space 进入节号');self.search_input.setFocus()
    def _suffix(self):return self.search_input.text()[len(self._selected_book):] if self._selected_book and self.search_input.text().startswith(self._selected_book) else ''
    def _space_after_chapter(self):
        v=self._suffix().strip()
        if not re.fullmatch(r'\d+',v):return
        c=int(v);m=self._chapter_count(self._selected_book)
        if not 1<=c<=m:self._update_hint(f'章节超出范围　·　本书最多 {m} 章');return
        self._stage='verse';self._set_text(f'{self._selected_book} {c}:');self._update_hint('请输入开始节　·　Space 生成节范围')
    def _space_after_verse(self):
        m=re.fullmatch(r'(\d+)\s*[:.]\s*(\d+)',self._suffix().strip())
        if not m:return
        c,v=map(int,m.groups());mx=self._verse_count(self._selected_book,c)
        if not 1<=v<=mx:self._update_hint(f'本章最多 {mx} 节');return
        self._space_mode=True;self._set_text(f'{self._selected_book} {c}:{v}-');self._update_hint(f'请输入结束节　·　范围 {v}–{mx}')
    def _delete_segment(self):
        if not self._selected_book:
            t=self.search_input.text();self._set_text(t[:-1] if t else '');self._refresh_book_state(self.search_input.text());return
        t=self.search_input.text();b=self._selected_book;s=t[len(b):] if t.startswith(b) else ''
        ps=[(r'\s*(\d+)\s*:\s*(\d+)\s*-\s*(\d+)\s*$',lambda m:f'{b} {m.group(1)}:{m.group(2)}-','verse'),(r'\s*(\d+)\s*:\s*(\d+)\s*-\s*$',lambda m:f'{b} {m.group(1)}:{m.group(2)}','verse'),(r'\s*(\d+)\s*:\s*(\d+)\s*$',lambda m:f'{b} {m.group(1)}:','verse'),(r'\s*(\d+)\s*:\s*$',lambda m:f'{b} {m.group(1)}','chapter'),(r'\s*(\d+)\s*$',lambda m:b,'chapter')]
        for p,maker,stage in ps:
            m=re.fullmatch(p,s)
            if m:self._set_text(maker(m));self._stage=stage;self._space_mode=False;self._refresh_selected(b,self._suffix());self._update_hint_for_stage();return
        self._set_text('');self._selected_book=None;self._stage='book';self._space_mode=False;self._converted_book=False;self.result_list.clear();self._resize_result_area();self._refresh_book_state('');self.search_input.setFocus()
    def _refresh_book_state(self,text):
        self._stage='book';self._selected_book=None;self._converted_book=False;self._space_mode=False;self.result_list.clear();q=text.strip()
        if not q:self._update_hint('↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭');return
        if re.fullmatch(r'[A-Za-z]+',q):
            c=self._candidates(q)
            if c:self._show_candidates(c);self._update_hint('↑↓ 选择书卷　·　Space 确认当前项　·　Enter 确认');return
            if len(q)==1:
                ims=[b for b in self.db.book_names if self._code(b)[:1]==q.lower()]
                if len(ims)==1:self._selected_book=ims[0];self._stage='chapter';self._converted_book=True;self._set_text(ims[0],True);self._update_hint(f'已识别为 {ims[0]}　·　请输入章节');return
            e=self._exact(q)
            if e:self._selected_book=e;self._stage='chapter';self._converted_book=True;self._set_text(e,True);self._update_hint(f'已识别为 {e}　·　请输入章节');return
        self._update_hint('↑↓ 选择　·　Space 选择 / 下一段　·　Enter 确认　·　Esc 关闭')
    def _update_hint_for_stage(self):
        if self._stage=='chapter':self._update_hint(f'已选择 {self._selected_book}　·　请输入章节　·　Space 进入节号')
        elif self._stage=='verse':self._update_hint('请输入开始节　·　Space 生成节范围')
        elif self._space_mode:self._update_hint('请输入结束节')
    def _on_special_key(self,k):
        if k==Qt.Key.Key_Escape:self.close_requested.emit()
        elif k==Qt.Key.Key_Up:self._move_highlight(-1)
        elif k==Qt.Key.Key_Down:self._move_highlight(1)
        elif k==Qt.Key.Key_Space:
            if self._stage=='book' and self.result_list.count():self._select_current_book()
            elif self._stage=='chapter' and self._selected_book:self._space_after_chapter()
            elif self._stage=='verse' and self._selected_book:self._space_after_verse()
        elif k in (Qt.Key.Key_Backspace,Qt.Key.Key_Delete):self._delete_segment()
    def _on_text_edited(self,text):
        if self._formatting:return
        if self._stage=='book':
            clean=''.join(c for c in text if self.ALLOWED.fullmatch(c))
            if clean!=text:self._set_text(clean);text=clean
            self._refresh_book_state(text);return
        if not self._selected_book:return
        b=self._selected_book
        if not text.startswith(b):self._set_text(b,True);return
        s=text[len(b):]
        if not re.fullmatch(r'[\s0-9:：.．。\-]*',s):s=re.sub(r'[^0-9 :：.．。\-]','',s);self._set_text(b+s,True)
        self._refresh_selected(b,s)
    def _refresh_selected(self,b,s):
        v=s.strip().replace('：',':').replace('．','.').replace('。','.');self.result_list.clear()
        if not v:self._resize_result_area();self._update_hint_for_stage();return
        m=re.fullmatch(r'(\d+)(?:\s*[:.]\s*(\d+)(?:\s*-\s*(\d*))?)?',v)
        if not m:return
        ct,vt,et=m.groups();c=int(ct);mc=self._chapter_count(b)
        if not 1<=c<=mc:self._update_hint(f'章节超出范围　·　本书最多 {mc} 章');return
        if vt is None:
            it=QListWidgetItem(f'01    {b}    第 {c} 章');it.setData(Qt.ItemDataRole.UserRole,(b,c,None,None));self.result_list.addItem(it);self.result_list.setCurrentRow(0);self._resize_result_area();return
        verse=int(vt);mv=self._verse_count(b,c)
        if not 1<=verse<=mv:self._update_hint(f'第 {c} 章最多 {mv} 节');return
        if et is None:
            if '-' in v:self._update_hint(f'请输入结束节　·　范围 {verse}–{mv}');return
            it=QListWidgetItem(f'01    {b}    {c}:{verse}');it.setData(Qt.ItemDataRole.UserRole,(b,c,verse,verse));self.result_list.addItem(it);self.result_list.setCurrentRow(0);self._resize_result_area();return
        if et=='':self._update_hint(f'请输入结束节　·　范围 {verse}–{mv}');return
        end=int(et)
        if end<verse:self._update_hint(f'结束节不能小于开始节 {verse}');return
        if end>mv:self._update_hint(f'本章最多 {mv} 节，不能输入 {end}');return
        it=QListWidgetItem(f'01    {b}    {c}:{verse}-{end}');it.setData(Qt.ItemDataRole.UserRole,(b,c,verse,end));self.result_list.addItem(it);self.result_list.setCurrentRow(0);self._resize_result_area()
    def _parse(self,text):
        v=text.strip().replace('：',':').replace('．','.').replace('。','.');b=self._selected_book
        if not b:
            m=re.match(r'^([A-Za-z]+)',v);b=self._exact(m.group(1)) if m else None
        if not b:return None
        s=v[len(b):].strip() if v.startswith(b) else v;m=re.fullmatch(r'(\d+)',s)
        if m:
            c=int(m.group(1));return (b,c,None,None) if 1<=c<=self._chapter_count(b) else None
        m=re.fullmatch(r'(\d+)\s*[:.]\s*(\d+)(?:\s*-\s*(\d+))?',s)
        if not m:return None
        c,vs,e=m.groups();c,vs=int(c),int(vs);e=int(e) if e else vs;mv=self._verse_count(b,c)
        return (b,c,vs,e) if 1<=c<=self._chapter_count(b) and 1<=vs<=e<=mv else None
    def _on_item_clicked(self,it):
        d=it.data(Qt.ItemDataRole.UserRole)
        if not d:return
        if isinstance(d,tuple) and len(d)==4 and d[2] is not None:self.search_triggered.emit(d);self.close_requested.emit();return
        b=d[0] if isinstance(d,tuple) else d;self._selected_book=b;self._stage='chapter';self._set_text(b,True);self.result_list.clear();self._resize_result_area();self.search_input.setFocus();self._update_hint(f'已选择 {b}　·　请输入章节　·　Space 进入节号')
    def _on_confirm(self):
        if self._confirming:return
        self._confirming=True
        try:
            p=self._parse(self.search_input.text())
            if p:self.search_triggered.emit(p);self.close_requested.emit()
            elif self._stage=='book' and self.result_list.count():self._select_current_book()
            else:self._update_hint('请输入有效的书卷、章节或节范围')
        finally:self._confirming=False
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self._on_confirm();event.accept();return
        super().keyPressEvent(event)
