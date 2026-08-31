from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTabBar, QPushButton, QGridLayout,
    QLabel, QSpinBox, QHBoxLayout, QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from .history_item import HistoryListWidget


class VisibleSpinBox(QSpinBox):
    """数字输入框。

    箭头只交给 QSS 中配置的新 SVG 绘制，避免 Qt 原生箭头与自绘箭头叠加。
    """
    pass


class EqualTabBar(QTabBar):
    """四个页签均分整行宽度；避免 width=0 时把 Tab 算成 1px 塌掉。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(True)
        self.setDrawBase(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setMinimumHeight(36)

    def _available_width(self):
        width = self.width()
        if width <= 0:
            parent = self.parentWidget()
            if parent is not None:
                width = parent.width()
        return max(0, width)

    def tabSizeHint(self, index):
        hint = super().tabSizeHint(index)
        count = max(1, self.count())
        available = self._available_width()
        if available <= 0:
            width = max(hint.width(), 64)
        else:
            width = max(hint.width(), available // count)
        height = max(hint.height(), 36)
        return QSize(width, height)

    def minimumTabSizeHint(self, index):
        hint = super().minimumTabSizeHint(index)
        return QSize(max(hint.width(), 48), max(hint.height(), 36))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGeometry()


class BookGridWidget(QScrollArea):
    """书卷网格：QGridLayout 列均分拉伸，不锁死宽度，完整显示书名。"""

    book_clicked = pyqtSignal(str)

    def __init__(self, columns=2, parent=None):
        super().__init__(parent)
        self._columns = max(1, int(columns))
        self._buttons = []
        self.setObjectName("bookGrid")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._container = QWidget()
        self._container.setObjectName("bookGridInner")
        self._grid = QGridLayout(self._container)
        self._grid.setContentsMargins(10, 10, 10, 10)
        self._grid.setHorizontalSpacing(8)
        self._grid.setVerticalSpacing(8)
        self.setWidget(self._container)

    def set_books(self, books, short=False):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._buttons.clear()

        for index, (book, short_name) in enumerate(books):
            label = short_name if short else book
            btn = QPushButton(label)
            btn.setObjectName("bookBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(book)
            btn.setProperty("bookName", book)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda checked=False, b=book: self._on_btn_clicked(b))
            row, col = divmod(index, self._columns)
            self._grid.addWidget(btn, row, col)
            self._buttons.append(btn)

        for col in range(self._columns):
            self._grid.setColumnStretch(col, 1)
        self._grid.setRowStretch(self._grid.rowCount(), 1)

    def _on_btn_clicked(self, book):
        for btn in self._buttons:
            btn.setChecked(btn.property("bookName") == book)
        self.book_clicked.emit(book)

    def select_book(self, book):
        for btn in self._buttons:
            btn.setChecked(btn.property("bookName") == book)


class NavigationPanel(QWidget):
    book_selected = pyqtSignal(str, int)
    range_selected = pyqtSignal(str, int, int, int)
    # 从历史打开：只投影，不重排历史列表
    history_opened = pyqtSignal(str, int, int, int)
    verse_segmentation_changed = pyqtSignal(bool)
    history_changed = pyqtSignal(list)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.history = []
        self.selected_book = None
        self._history_updating = False
        self.setObjectName("navPanel")
        self.setMinimumWidth(320)
        self.setMaximumWidth(420)
        self.setFixedWidth(360)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setTabBar(EqualTabBar())
        self.old_list = self._create_book_list("old", 2)
        self.tab_widget.addTab(self.old_list, "旧约")
        self.new_list = self._create_book_list("new", 2)
        self.tab_widget.addTab(self.new_list, "新约")
        self.short_list = self._create_book_list("all", 4, short=True)
        self.tab_widget.addTab(self.short_list, "简称")

        history_widget = QWidget()
        hl = QVBoxLayout(history_widget)
        hl.setContentsMargins(8, 8, 8, 8)
        hl.setSpacing(8)
        self.history_list = HistoryListWidget()
        self.history_list.item_clicked.connect(self._on_history_clicked)
        self.history_list.item_deleted.connect(self._delete_history)
        hl.addWidget(self.history_list, 1)
        clear_btn = QPushButton("清空历史")
        clear_btn.setObjectName("clearHistoryBtn")
        clear_btn.clicked.connect(self._clear_history)
        hl.addWidget(clear_btn)
        self.tab_widget.addTab(history_widget, "历史")
        layout.addWidget(self.tab_widget, 1)

        bottom = QFrame()
        bottom.setObjectName("rangeBox")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 10, 12, 12)
        bottom_layout.setSpacing(10)

        options_row = QHBoxLayout()
        options_row.setSpacing(8)
        options_row.addWidget(QLabel("选项"))
        self.segment_btn = QPushButton("按节分段：关")
        self.segment_btn.setObjectName("segmentBtn")
        self.segment_btn.setCheckable(True)
        self.segment_btn.clicked.connect(self._on_segment_clicked)
        options_row.addWidget(self.segment_btn, 1)
        bottom_layout.addLayout(options_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(QLabel("章"), 0, 0)
        grid.addWidget(QLabel("起"), 0, 1)
        grid.addWidget(QLabel("止"), 0, 2)

        self.chapter_spin = VisibleSpinBox()
        self.chapter_spin.setRange(1, 150)
        self.chapter_spin.valueChanged.connect(self._on_chapter_changed)
        self.start_spin = VisibleSpinBox()
        self.start_spin.setRange(1, 176)
        self.end_spin = VisibleSpinBox()
        self.end_spin.setRange(1, 176)
        grid.addWidget(self.chapter_spin, 1, 0)
        grid.addWidget(self.start_spin, 1, 1)
        grid.addWidget(self.end_spin, 1, 2)
        bottom_layout.addLayout(grid)

        self.select_btn = QPushButton("显示所选经文")
        self.select_btn.setObjectName("selectRangeBtn")
        self.select_btn.clicked.connect(self._select_range)
        bottom_layout.addWidget(self.select_btn)

        layout.addWidget(bottom)
        self._update_segment_button(False)

    def _on_segment_clicked(self, checked):
        self._update_segment_button(bool(checked))
        self.verse_segmentation_changed.emit(bool(checked))

    def _update_segment_button(self, enabled):
        self.segment_btn.setChecked(bool(enabled))
        self.segment_btn.setText("按节分段：开" if enabled else "按节分段：关")

    def set_verse_segmentation(self, enabled, emit_signal=False):
        enabled = bool(enabled)
        old = self.segment_btn.blockSignals(True)
        self._update_segment_button(enabled)
        self.segment_btn.blockSignals(old)
        if emit_signal:
            self.verse_segmentation_changed.emit(enabled)

    def _create_book_list(self, category, columns, short=False):
        w = BookGridWidget(columns=columns)
        w.set_books(self.db.get_books(category), short=short)
        w.book_clicked.connect(self._on_book_name_clicked)
        return w

    def _on_book_name_clicked(self, book):
        self._set_selected_book(book, whole_chapter=True)
        # 同步其它页的选中态
        for grid in (self.old_list, self.new_list, self.short_list):
            grid.select_book(book)
        self.book_selected.emit(book, self.chapter_spin.value())

    def _set_selected_book(self, book, whole_chapter=False):
        self.selected_book = book
        max_ch = max(1, self.db.get_chapter_count(book))
        blocked = self.chapter_spin.blockSignals(True)
        self.chapter_spin.setRange(1, max_ch)
        self.chapter_spin.setValue(1)
        self.chapter_spin.blockSignals(blocked)
        self._set_verse_ranges(book, 1, whole_chapter=whole_chapter)

    def _set_verse_ranges(self, book, chapter, whole_chapter=False):
        max_v = max(1, self.db.get_verse_count(book, chapter))
        bs = self.start_spin.blockSignals(True)
        be = self.end_spin.blockSignals(True)
        self.start_spin.setRange(1, max_v)
        self.end_spin.setRange(1, max_v)
        self.start_spin.setValue(1)
        self.end_spin.setValue(max_v if whole_chapter else min(5, max_v))
        self.start_spin.blockSignals(bs)
        self.end_spin.blockSignals(be)

    def _on_chapter_changed(self, chapter):
        if self.selected_book:
            self._set_verse_ranges(self.selected_book, chapter, whole_chapter=False)

    def sync_selection(self, book, chapter, start, end):
        self._history_updating = True
        try:
            self.selected_book = book
            for grid in (self.old_list, self.new_list, self.short_list):
                grid.select_book(book)
            max_ch = max(1, self.db.get_chapter_count(book))
            self.chapter_spin.blockSignals(True)
            self.chapter_spin.setRange(1, max_ch)
            self.chapter_spin.setValue(int(chapter))
            self.chapter_spin.blockSignals(False)
            max_v = max(1, self.db.get_verse_count(book, int(chapter)))
            self.start_spin.blockSignals(True)
            self.end_spin.blockSignals(True)
            self.start_spin.setRange(1, max_v)
            self.end_spin.setRange(1, max_v)
            self.start_spin.setValue(max(1, min(int(start), max_v)))
            self.end_spin.setValue(max(1, min(int(end), max_v)))
            self.start_spin.blockSignals(False)
            self.end_spin.blockSignals(False)
        finally:
            self._history_updating = False

    def _current_selection(self):
        if not self.selected_book:
            return None
        book = self.selected_book
        chapter = int(self.chapter_spin.value())
        start = int(self.start_spin.value())
        end = int(self.end_spin.value())
        if end < start:
            start, end = end, start
        return (book, chapter, start, end)

    def _select_range(self):
        entry = self._current_selection()
        if not entry:
            return
        self.range_selected.emit(*entry)

    def load_history(self, history_list):
        self.history = []
        for entry in history_list or []:
            try:
                if len(entry) == 4:
                    self.history.append((str(entry[0]), int(entry[1]), int(entry[2]), int(entry[3])))
            except (TypeError, ValueError):
                pass
        self.history = self.history[:30]
        self._update_history_list()

    def add_to_history(self, book, chapter, start, end):
        try:
            book = str(book)
            chapter = int(chapter)
            max_v = max(1, self.db.get_verse_count(book, chapter))
            if start is None:
                start = 1
            else:
                start = int(start)
            if end is None:
                end = max_v
            else:
                end = int(end)
            start = max(1, min(start, max_v))
            end = max(1, min(end, max_v))
            if end < start:
                start, end = end, start
            entry = (book, chapter, start, end)
        except (TypeError, ValueError, AttributeError):
            return
        if entry in self.history:
            self.history.remove(entry)
        self.history.insert(0, entry)
        self.history = self.history[:30]
        self._update_history_list(selected_index=0)
        self.history_changed.emit(list(self.history))

    @staticmethod
    def _history_label(book, chapter, start, end):
        if start == end:
            return f"{book} {chapter}章 {start}节"
        return f"{book} {chapter}章 {start}-{end}节"

    def _update_history_list(self, selected_index=-1):
        texts = [self._history_label(*entry) for entry in self.history]
        self.history_list.set_entries(texts, selected_index=selected_index)

    def _on_history_clicked(self, index):
        if not 0 <= index < len(self.history):
            return
        book, chapter, start, end = self.history[index]
        self.sync_selection(book, chapter, start, end)
        # 只改选中态，不重建、不重排
        self.history_list.set_selected_index(index)
        self.history_opened.emit(book, chapter, start, end)

    def _delete_history(self, index):
        if 0 <= index < len(self.history):
            del self.history[index]
            selected = self.history_list.selected_index()
            if selected == index:
                selected = -1
            elif selected > index:
                selected -= 1
            self._update_history_list(selected_index=selected)
            self.history_changed.emit(list(self.history))

    def _clear_history(self):
        self.history.clear()
        self._update_history_list()
        self.history_changed.emit([])

    def get_history(self):
        return list(self.history)
