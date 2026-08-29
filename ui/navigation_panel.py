from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QPushButton, QGridLayout, QLabel, QSpinBox, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from .history_item import HistoryItemWidget


class NavigationPanel(QWidget):
    book_selected = pyqtSignal(str, int)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.history = []
        self.setMinimumWidth(300)
        self.setMaximumWidth(360)
        self.setFixedWidth(330)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self.tab_widget = QTabWidget()
        self.old_list = self._create_book_list("old", 2)
        self.tab_widget.addTab(self.old_list, "旧约")
        self.new_list = self._create_book_list("new", 2)
        self.tab_widget.addTab(self.new_list, "新约")
        self.short_list = self._create_book_list("all", 4, short=True)
        self.tab_widget.addTab(self.short_list, "简称")

        history_widget = QWidget()
        hl = QVBoxLayout(history_widget)
        self.history_list = QListWidget()
        self.history_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        hl.addWidget(self.history_list)
        clear_btn = QPushButton("清空历史记录")
        clear_btn.clicked.connect(self._clear_history)
        hl.addWidget(clear_btn)
        self.tab_widget.addTab(history_widget, "历史")
        layout.addWidget(self.tab_widget, 1)

        # 左侧直接选择章、起始节、结束节
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(5)
        grid.addWidget(QLabel("章节"), 0, 0)
        grid.addWidget(QLabel("开始节"), 0, 1)
        grid.addWidget(QLabel("结束节"), 0, 2)
        self.chapter_spin = QSpinBox(); self.chapter_spin.setRange(1, 150)
        self.start_spin = QSpinBox(); self.start_spin.setRange(1, 176)
        self.end_spin = QSpinBox(); self.end_spin.setRange(1, 176)
        grid.addWidget(self.chapter_spin, 1, 0)
        grid.addWidget(self.start_spin, 1, 1)
        grid.addWidget(self.end_spin, 1, 2)
        self.select_btn = QPushButton("显示所选经文")
        self.select_btn.clicked.connect(self._select_range)
        grid.addWidget(self.select_btn, 1, 3)
        layout.addWidget(box)

        self.setLayout(layout)

    def _create_book_list(self, category, columns, short=False):
        w = QListWidget()
        w.setViewMode(QListWidget.ViewMode.IconMode)
        w.setFlow(QListWidget.Flow.LeftToRight)
        w.setWrapping(True)
        w.setResizeMode(QListWidget.ResizeMode.Adjust)
        w.setGridSize(self._grid_size(columns))
        books = self.db.get_books(category)
        for book, short_name in books:
            label = short_name if short else book
            item = QListWidgetItem(label)
            item.setToolTip(book)
            item.setData(Qt.ItemDataRole.UserRole, book)
            w.addItem(item)
        w.itemClicked.connect(self._on_book_clicked)
        return w

    def _grid_size(self, columns):
        return {2: (145, 38), 4: (72, 38)}[columns]

    def _on_book_clicked(self, item):
        book = item.data(Qt.ItemDataRole.UserRole)
        self._set_selected_book(book)
        self.book_selected.emit(book, self.chapter_spin.value())
        self.add_to_history(book, self.chapter_spin.value(), self.start_spin.value(), self.end_spin.value())

    def _set_selected_book(self, book):
        self.selected_book = book
        max_ch = max(1, self.db.get_chapter_count(book))
        self.chapter_spin.setRange(1, max_ch)
        self.chapter_spin.setValue(1)
        max_v = max(1, self.db.get_verse_count(book, 1))
        self.start_spin.setRange(1, max_v)
        self.end_spin.setRange(1, max_v)
        self.start_spin.setValue(1)
        self.end_spin.setValue(min(5, max_v))

    def _select_range(self):
        if not getattr(self, "selected_book", None):
            return
        book = self.selected_book
        chapter = self.chapter_spin.value()
        max_v = max(1, self.db.get_verse_count(book, chapter))
        self.start_spin.setRange(1, max_v)
        self.end_spin.setRange(1, max_v)
        start = min(self.start_spin.value(), max_v)
        end = min(self.end_spin.value(), max_v)
        if end < start:
            start, end = end, start
        self.start_spin.setValue(start)
        self.end_spin.setValue(end)
        self.book_selected.emit(book, chapter)
        # 主窗口目前按书卷点击信号加载整章；范围按钮由主窗口后续接管时可扩展

    def load_history(self, history_list):
        self.history = history_list
        self._update_history_list()

    def add_to_history(self, book, chapter, start, end):
        entry = (book, chapter, start, end)
        if entry in self.history:
            self.history.remove(entry)
        self.history.insert(0, entry)
        self.history = self.history[:30]
        self._update_history_list()

    def _update_history_list(self):
        self.history_list.clear()
        for i, (book, chapter, start, end) in enumerate(self.history):
            if start is None:
                text = f"{book}{chapter}章"
            elif end is None:
                text = f"{book}{chapter}章{start}节-本章末"
            elif start == end:
                text = f"{book}{chapter}章{start}节"
            else:
                text = f"{book}{chapter}章{start}-{end}节"
            item = QListWidgetItem()
            self.history_list.addItem(item)
            widget = HistoryItemWidget(i, text)
            widget.clicked.connect(self._on_history_clicked)
            widget.deleted.connect(self._delete_history)
            item.setSizeHint(widget.sizeHint())
            self.history_list.setItemWidget(item, widget)

    def _on_history_clicked(self, index):
        book, chapter, start, end = self.history[index]
        self.selected_book = book
        self.book_selected.emit(book, chapter)
        self.history.insert(0, self.history.pop(index))
        self._update_history_list()

    def _delete_history(self, index):
        if 0 <= index < len(self.history):
            del self.history[index]
            self._update_history_list()

    def _clear_history(self):
        self.history.clear()
        self._update_history_list()

    def get_history(self):
        return self.history
