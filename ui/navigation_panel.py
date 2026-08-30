from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QPushButton, QGridLayout, QLabel, QSpinBox, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from .history_item import HistoryItemWidget

class NavigationPanel(QWidget):
    book_selected = pyqtSignal(str, int)
    range_selected = pyqtSignal(str, int, int, int)
    verse_segmentation_changed = pyqtSignal(bool)
    history_changed = pyqtSignal(list)
    def __init__(self,db,parent=None):
        super().__init__(parent); self.db=db; self.history=[]; self.selected_book=None; self._history_updating=False; self.setMinimumWidth(300); self.setMaximumWidth(360); self.setFixedWidth(330); self._init_ui()
    def _init_ui(self):
        layout=QVBoxLayout(); layout.setContentsMargins(8,8,8,8); layout.setSpacing(6); self.tab_widget=QTabWidget(); self.old_list=self._create_book_list("old",2); self.tab_widget.addTab(self.old_list,"旧约"); self.new_list=self._create_book_list("new",2); self.tab_widget.addTab(self.new_list,"新约"); self.short_list=self._create_book_list("all",4,short=True); self.tab_widget.addTab(self.short_list,"简称")
        history_widget=QWidget(); hl=QVBoxLayout(history_widget); self.history_list=QListWidget(); self.history_list.setSelectionMode(QListWidget.SelectionMode.NoSelection); hl.addWidget(self.history_list); clear_btn=QPushButton("清空历史记录"); clear_btn.clicked.connect(self._clear_history); hl.addWidget(clear_btn); self.tab_widget.addTab(history_widget,"历史"); layout.addWidget(self.tab_widget,1)
        options_box=QWidget(); options_layout=QHBoxLayout(options_box); options_layout.setContentsMargins(8,5,8,5); options_layout.setSpacing(8); options_layout.addWidget(QLabel("显示选项")); self.segment_btn=QPushButton("按节分段：关"); self.segment_btn.setCheckable(True); self.segment_btn.setChecked(False); self.segment_btn.setMinimumHeight(32); self.segment_btn.clicked.connect(self._on_segment_clicked); options_layout.addWidget(self.segment_btn,1); layout.addWidget(options_box)
        box=QWidget(); grid=QGridLayout(box); grid.setContentsMargins(4,4,4,4); grid.setHorizontalSpacing(5); grid.addWidget(QLabel("章节"),0,0); grid.addWidget(QLabel("开始节"),0,1); grid.addWidget(QLabel("结束节"),0,2); self.chapter_spin=QSpinBox(); self.chapter_spin.setRange(1,150); self.chapter_spin.valueChanged.connect(self._on_chapter_changed); self.start_spin=QSpinBox(); self.start_spin.setRange(1,176); self.start_spin.valueChanged.connect(self._on_range_changed); self.end_spin=QSpinBox(); self.end_spin.setRange(1,176); self.end_spin.valueChanged.connect(self._on_range_changed); grid.addWidget(self.chapter_spin,1,0); grid.addWidget(self.start_spin,1,1); grid.addWidget(self.end_spin,1,2); self.select_btn=QPushButton("显示所选经文"); self.select_btn.clicked.connect(self._select_range); grid.addWidget(self.select_btn,1,3); layout.addWidget(box); self.setLayout(layout); self._update_segment_button(False)
    def _on_segment_clicked(self,checked):
        enabled=bool(checked); self._update_segment_button(enabled); self.verse_segmentation_changed.emit(enabled)
    def _update_segment_button(self,enabled): self.segment_btn.setChecked(bool(enabled)); self.segment_btn.setText("按节分段：开" if enabled else "按节分段：关")
    def set_verse_segmentation(self,enabled,emit_signal=False):
        enabled=bool(enabled); old=self.segment_btn.blockSignals(True); self._update_segment_button(enabled); self.segment_btn.blockSignals(old)
        if emit_signal:self.verse_segmentation_changed.emit(enabled)
    def _create_book_list(self,category,columns,short=False):
        w=QListWidget(); w.setViewMode(QListWidget.ViewMode.IconMode); w.setFlow(QListWidget.Flow.LeftToRight); w.setWrapping(True); w.setResizeMode(QListWidget.ResizeMode.Adjust); w.setGridSize(self._grid_size(columns));
        for book,short_name in self.db.get_books(category):
            item=QListWidgetItem(short_name if short else book); item.setToolTip(book); item.setData(Qt.ItemDataRole.UserRole,book); w.addItem(item)
        w.itemClicked.connect(self._on_book_clicked); return w
    def _grid_size(self,columns): return QSize(*({2:(145,38),4:(72,38)}[columns]))
    def _on_book_clicked(self,item): book=item.data(Qt.ItemDataRole.UserRole); self._set_selected_book(book); self.book_selected.emit(book,self.chapter_spin.value()); self._record_current_selection()
    def _set_selected_book(self,book):
        self.selected_book=book; max_ch=max(1,self.db.get_chapter_count(book)); self.chapter_spin.setRange(1,max_ch); self.chapter_spin.setValue(1); self._set_verse_ranges(book,1)
    def _set_verse_ranges(self,book,chapter):
        max_v=max(1,self.db.get_verse_count(book,chapter)); self.start_spin.setRange(1,max_v); self.end_spin.setRange(1,max_v); self.start_spin.setValue(1); self.end_spin.setValue(min(5,max_v))
    def _on_chapter_changed(self,chapter):
        if self.selected_book:
            self._set_verse_ranges(self.selected_book,chapter); self._record_current_selection()
    def _on_range_changed(self,_value): self._record_current_selection()
    def _current_selection(self):
        if not self.selected_book:return None
        return (self.selected_book,int(self.chapter_spin.value()),int(self.start_spin.value()),int(self.end_spin.value()))
    def _record_current_selection(self):
        if self._history_updating:return
        entry=self._current_selection()
        if entry is None:return
        book,chapter,start,end=entry
        if end<start:start,end=end,start
        self.add_to_history(book,chapter,start,end)
    def _select_range(self):
        if not self.selected_book:return
        book=self.selected_book; chapter=self.chapter_spin.value(); max_v=max(1,self.db.get_verse_count(book,chapter)); start=min(self.start_spin.value(),max_v); end=min(self.end_spin.value(),max_v)
        if end<start:start,end=end,start
        self.start_spin.setValue(start); self.end_spin.setValue(end); self.range_selected.emit(book,chapter,start,end); self.add_to_history(book,chapter,start,end)
    def load_history(self,history_list):
        self.history=[]
        for entry in history_list or []:
            try:
                if len(entry)==4:self.history.append((entry[0],int(entry[1]),int(entry[2]),int(entry[3])))
            except:pass
        self.history=self.history[:30]; self._update_history_list()
    def add_to_history(self,book,chapter,start,end):
        entry=(book,int(chapter),int(start),int(end))
        if entry in self.history:self.history.remove(entry)
        self.history.insert(0,entry); self.history=self.history[:30]; self._update_history_list(); self.history_changed.emit(self.history)
    def _update_history_list(self):
        self._history_updating=True
        try:
            self.history_list.clear()
            for i,(book,chapter,start,end) in enumerate(self.history):
                text=f"{book}{chapter}章{start}节" if start==end else f"{book}{chapter}章{start}-{end}节"; item=QListWidgetItem(); self.history_list.addItem(item); widget=HistoryItemWidget(i,text); widget.clicked.connect(self._on_history_clicked); widget.deleted.connect(self._delete_history); item.setSizeHint(widget.sizeHint()); self.history_list.setItemWidget(item,widget)
        finally:self._history_updating=False
    def _on_history_clicked(self,index):
        if not 0<=index<len(self.history):return
        book,chapter,start,end=self.history[index]; self._history_updating=True
        try:
            self.selected_book=book; self.chapter_spin.setRange(1,max(1,self.db.get_chapter_count(book))); self.chapter_spin.setValue(chapter); max_v=max(1,self.db.get_verse_count(book,chapter)); self.start_spin.setRange(1,max_v); self.end_spin.setRange(1,max_v); self.start_spin.setValue(max(1,min(start,max_v))); self.end_spin.setValue(max(1,min(end,max_v)))
        finally:self._history_updating=False
        self.range_selected.emit(book,chapter,start,end); self.history.insert(0,self.history.pop(index)); self._update_history_list(); self.history_changed.emit(self.history)
    def _delete_history(self,index):
        if 0<=index<len(self.history):del self.history[index]; self._update_history_list(); self.history_changed.emit(self.history)
    def _clear_history(self):self.history.clear(); self._update_history_list(); self.history_changed.emit(self.history)
    def get_history(self):return self.history
