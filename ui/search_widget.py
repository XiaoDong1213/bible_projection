# ui/search_widget.py
import re
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLineEdit,QLabel,QListWidget,QListWidgetItem
from PyQt6.QtCore import Qt,pyqtSignal

class SearchWidget(QWidget):
    search_triggered=pyqtSignal(tuple)
    close_requested=pyqtSignal()
    def __init__(self,db,parent=None):
        super().__init__(parent); self.db=db; self._formatting=False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay=QVBoxLayout(self); lay.setContentsMargins(10,10,10,10); lay.setSpacing(4)
        self.search_input=QLineEdit(); self.search_input.setObjectName('searchInput')
        self.search_input.setPlaceholderText('例如：创世记1:2-12  或  CSJ 1:2-12')
        # textEdited 只处理用户编辑，因此删除冒号/空格不会被再次强制添加。
        self.search_input.textEdited.connect(self._on_text_edited); self.search_input.returnPressed.connect(self._on_confirm); lay.addWidget(self.search_input)
        self.hint_label=QLabel('书名 / 简称 / 简拼　｜　输入简拼自动识别　｜　Esc 退出'); lay.addWidget(self.hint_label)
        self.result_list=QListWidget(); self.result_list.itemClicked.connect(self._on_item_clicked); lay.addWidget(self.result_list)
        self.search_input.installEventFilter(self); self.result_list.installEventFilter(self); self.setFocusProxy(self.search_input)
    def showEvent(self,e):
        super().showEvent(e); self.search_input.setFocus(); self.search_input.selectAll(); self._refresh(self.search_input.text(),False)
    @staticmethod
    def _norm(v): return re.sub(r'[\s._-]+','',str(v or '').strip().lower())
    def _code(self,b): return self._norm(self.db.book_meta.get(b,{}).get('pinyin',''))
    def _candidates(self,q):
        q=self._norm(q); return [b for b in self.db.book_names if self._code(b).startswith(q)] if q else []
    def _exact(self,q):
        q=self._norm(q)
        for b in self.db.book_names:
            if self._code(b)==q:return b
        return None
    def _show_candidates(self,q):
        self.result_list.clear()
        for i,b in enumerate(self._candidates(q)[:12],1):
            code=self._code(b).upper(); short=self.db._short_name(b); item=QListWidgetItem(f'{i}. {code or short} {b}')
            item.setData(Qt.ItemDataRole.UserRole,(b,1,None,None)); self.result_list.addItem(item)
        if self.result_list.count():self.result_list.setCurrentRow(0)
    def _valid(self,p):
        if not p or len(p)!=4:return None
        b,c,s,e=p
        try:
            c=int(c); mx=self.db.get_verse_count(b,c)
            if not b or c<1 or c>self.db.get_chapter_count(b):return None
            if s is not None and not 1<=int(s)<=mx:return None
            if e is not None and not 1<=int(e)<=mx:return None
            if s is not None and e is not None and int(e)<int(s):return None
            return b,c,s,e
        except (TypeError,ValueError,AttributeError):return None
    def _split(self,b,d):
        d=str(d); opts=[]
        if not d.isdigit() or len(d)<2:return None
        for n in range(1,len(d)):
            cs,vs=d[:-n],d[-n:]
            if cs.startswith('0') or vs.startswith('0'):continue
            p=self._valid((b,int(cs),int(vs),int(vs)))
            if p:opts.append(((len(cs)>3,len(vs)>3,abs(len(cs)-len(vs))),p))
        if opts:opts.sort(key=lambda x:x[0]); return opts[0][1]
        return self._valid((b,int(d),None,None))
    def _chapter_info(self,text):
        m=re.fullmatch(r'(.+?)[\s]*([0-9]+)',str(text or '').strip())
        if not m:return None
        part,d=m.groups(); b=self.db.find_book(part.strip())
        if not b:return None
        try: count=int(self.db.book_meta.get(b,{}).get('chapter_count') or self.db.get_chapter_count(b) or 0); c=int(d)
        except (TypeError,ValueError,AttributeError):return None
        if not count:return None
        if c<1 or c>count:return {'invalid':True}
        return {'book':b,'part':part.strip(),'chapter':c,'split':not any(int(d+str(x))<=count for x in range(10))}
    def _auto(self,text):
        r=str(text or '').strip()
        if not r:return r
        m=re.fullmatch(r'(.+?)[\s]*(\d+)[\s:：.]+(\d+)(?:\s*-\s*(\d*))?',r)
        if m:
            part,c,s,e=m.groups(); return f'{part.strip()} {int(c)}:{int(s)}'+(f'-{int(e)}' if e else '')
        info=self._chapter_info(r)
        if info:
            return r if info.get('invalid') else (f"{info['part']} {info['chapter']}:" if info['split'] else r)
        m=re.fullmatch(r'([A-Za-z]+)[\s]*([0-9]+)(?:[\s:：.]+([0-9]+))?(?:\s*-\s*([0-9]+))?',r)
        if not m:return r
        code,c,s,e=m.groups(); b=self._exact(code)
        if not b:return r
        if s:return f'{code.upper()} {int(c)}:{int(s)}'+(f'-{int(e)}' if e else '')
        if len(c)>=2:
            p=self._split(b,c)
            if p and p[2] is not None:return self._fmt(code.upper(),p)
        info=self._chapter_info(f'{b} {c}')
        return f'{code.upper()} {info["chapter"]}:' if info and info['split'] else r
    def _set(self,text):
        if text==self.search_input.text():return
        self._formatting=True
        try:self.search_input.setText(text); self.search_input.setCursorPosition(len(text))
        finally:self._formatting=False
    def _fmt(self,label,p):
        b,c,s,e=p
        if s is None:return f'{label} {c}'
        return f'{label} {c}:{s}' if e is None or e==s else f'{label} {c}:{s}-{e}'
    def _parse(self,text):
        r=str(text or '').strip().replace('：',':').replace('．','.').replace('。','.')
        m=re.fullmatch(r'([A-Za-z]+)[\s]*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d*))?',r)
        if m:
            code,c,s,e=m.groups(); b=self._exact(code)
            if b:return self._valid((b,int(c),int(s),int(e) if e else int(s)))
        m=re.fullmatch(r'([A-Za-z]+)[\s]+(\d+)$',r)
        if m:
            b=self._exact(m.group(1)); return self._valid((b,int(m.group(2)),None,None)) if b else None
        m=re.fullmatch(r'([A-Za-z]+)(\d+)$',r)
        if m:
            b=self._exact(m.group(1)); return self._split(b,m.group(2)) if b else None
        b=self._exact(r); return (b,1,None,None) if b else self._valid(self.db.parse_reference(r))
    def _clamp(self,text):
        r=str(text or '').strip().replace('：',':').replace('．','.').replace('。','.')
        m=re.fullmatch(r'(.+?)\s*(\d+)(?::|[.\s]+)(\d+)(?:\s*-\s*(\d*))?',r)
        if not m:return None
        q,cs,ss,es=m.groups(); b=self.db.find_book(q.strip())
        if not b:return None
        try:
            count=int(self.db.book_meta.get(b,{}).get('chapter_count') or self.db.get_chapter_count(b) or 0); c=int(cs); c=count if c<1 or c>count else c
            mx=int(self.db.get_verse_count(b,c) or 0); s=int(ss); s=mx if s<1 or s>mx else s
            e=s
            if es not in (None,''):
                try:e=int(es)
                except ValueError:e=mx
                if e<1 or e>mx:e=mx
                if e<s:e=s
            return (b,c,s,e) if mx else None
        except (TypeError,ValueError,AttributeError):return None
    def _refresh(self,text,user=True):
        if self._formatting:return
        r=str(text or '').strip()
        if not r:self.result_list.clear();return
        if user:
            f=self._auto(r)
            if f!=r:self._set(f);r=f
        # 单字母只有一个前缀候选立即转中文；多个候选保留简拼候选。
        if re.fullmatch(r'[A-Za-z]+',r):
            cs=self._candidates(r)
            if len(cs)==1:self._set(cs[0]);r=cs[0];self.result_list.clear()
            elif len(cs)>1:self._show_candidates(r);return
        p=self._parse(r)
        if p:
            self.result_list.clear(); b,c,s,e=p; it=QListWidgetItem('▶ '+self._display(b,c,s,e));it.setData(Qt.ItemDataRole.UserRole,p);self.result_list.addItem(it);self.result_list.setCurrentRow(0);return
        p=self._clamp(r)
        if p:
            b,c,s,e=p; self._set(f'{b} {c}:{s}' if s==e else f'{b} {c}:{s}-{e}');self.result_list.clear();it=QListWidgetItem('▶ '+self._display(b,c,s,e));it.setData(Qt.ItemDataRole.UserRole,p);self.result_list.addItem(it);self.result_list.setCurrentRow(0);return
        q=re.split(r'[0-9:：.\-\s]+',r,maxsplit=1)[0].strip() if re.search(r'\d',r) else r;self.result_list.clear()
        for i,b in enumerate(self.db.search_books(q)[:12],1):
            code=self._code(b).upper();short=self.db._short_name(b);it=QListWidgetItem(f'{i}. {code or short} {b}');it.setData(Qt.ItemDataRole.UserRole,(b,1,None,None));self.result_list.addItem(it)
        if self.result_list.count():self.result_list.setCurrentRow(0)
    def _on_text_edited(self,text):self._refresh(text,True)
    def _display(self,b,c,s,e):
        if s is None:return f'{b} {c}章（整章）'
        return f'{b} {c}:{s}' if e is None or e==s else f'{b} {c}:{s}-{e}'
    def _on_confirm(self):
        text=self.search_input.text().strip();p=self._parse(text)
        if not p:p=self._clamp(text)
        if p:
            b,c,s,e=p;self._set(f'{b} {c}:{s}' if s==e else f'{b} {c}:{s}-{e}');self.search_triggered.emit(p);self.close_requested.emit();return
        it=self.result_list.currentItem()
        if it and it.data(Qt.ItemDataRole.UserRole):self.search_triggered.emit(it.data(Qt.ItemDataRole.UserRole));self.close_requested.emit();return
        self.hint_label.setText('无法识别该经文，请检查书卷、章和节号')
    def _on_item_clicked(self,item):
        p=item.data(Qt.ItemDataRole.UserRole)
        if p:self.search_triggered.emit(p);self.close_requested.emit()
    def eventFilter(self,obj,event):
        if event.type()==event.Type.KeyPress:
            k=event.key()
            if k==Qt.Key.Key_Escape:self.close_requested.emit();return True
            if obj in (self.search_input,self.result_list):
                if k==Qt.Key.Key_Down:self._move(1);return True
                if k==Qt.Key.Key_Up:self._move(-1);return True
                if k in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self._on_confirm();return True
        return super().eventFilter(obj,event)
    def _move(self,d):
        n=self.result_list.count()
        if n:self.result_list.setCurrentRow(max(0,min(n-1,(self.result_list.currentRow() if self.result_list.currentRow()>=0 else 0)+d)))
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Escape:self.close_requested.emit();return
        super().keyPressEvent(e)
