from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QListWidget, QListWidgetItem, QPushButton, QGridLayout, QLabel, QSpinBox, QHBoxLayout, QCheckBox
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from .history_item import HistoryItemWidget


class NavigationPanel(QWidget):
    book_selected = pyqtSignal(str, int)
    range_selected = pyqtSignal(str, int, int, int)
    verse_segmentation_changed = pyqtSignal(bool)
    history_changed = pyqtSignal(list)

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.history = []
        self.selected_book = None
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

        options_box = QWidget()
        options_box.setObjectName("displayOptionsBox")
        options_layout = QHBoxLayout(options_box)
        options_layout.setContentsMargins(8, 5, 8, 5)
        options_layout.setSpacing(8)
        options_title = QLabel("显示选项")
        options_title.setStyleSheet("font-weight: bold;")
        options_layout.addWidget(options_title)

        # 明确命名为“按节分段”，默认关闭。该控件只负责切换显示方式，不修改经文范围。
        self.segment_check = QCheckBox("按节分段")
        self.segment_check.setChecked(False)
        self.segment_check.setToolTip("关闭：经文连续显示（默认）；开启：每节单独一段显示")
        self.segment_check.setStyleSheet("QCheckBox { spacing: 6px; } QCheckBox::indicator { width: 16px; height: 16px; }")
        options_layout.addWidget(self.segment_check)
        options_layout.addStretch()
        layout.addWidget(options_box)

        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setHorizontalSpacing(5)
        grid.addWidget(QLabel("章节"), 0, 0)
        grid.addWidget(QLabel("开始节"), 0, 1)
        grid.addWidget(QLabel("结束节"), 0, 2)
        self.chapter_spin = QSpinBox(); self.chapter_spin.setRange(1, 150)
        self.chapter_spin.valueChanged.connect(self._on_chapter_changed)
        self.start_spin = QSpinBox(); self.start_spin.setRange(1, 176)
        self.end_spin = QSpinBox(); self.end_spin.setRange(1, 176)
        grid.addWidget(self.chapter_spin, 1, 0)
        grid.addWidget(self.start_spin, 1, 1)
        grid.addWidget(self.end_spin, 1, 2)
        self.select_btn = QPushButton("显示所选经文")
        self.select_btn.clicked.connect(self._select_range)
        grid.addWidget(self.select_btn, 1, 3)
        layout.addWidget(box)

        self.segment_check.toggled.connect(self._on_segment_toggled)
        self.setLayout(layout)

    def _on_segment_toggled(self, enabled):
        self.verse_segmentation_changed.emit(bool(enabled))

    def set_verse_segmentation(self, enabled, emit_signal=False):
        enabled = bool(enabled)
        old = self.segment_check.blockSignals(True)
        self.segment_check.setChecked(enabled)
        self.segment_check.blockSignals(old)

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
        width, height = {2: (145, 38), 4: (72, 38)}[columns]
        return QSize(width, height)

    def _on_book_clicked(self, item):
        book = item.data(Qt.ItemDataRole.UserRole)
        self._set_selected_book(book)
        self.book_selected.emit(book, self.chapter_spin.value())

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

    def _on_chapter_changed(self, chapter):
        book = getattr(self, "selected_book", None)
        if not book:
            return
        max_v = max(1, self.db.get_verse_count(book, chapter))
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
        self.range_selected.emit(book, chapter, start, end)
        self.add_to_history(book, chapter, start, end)

    def load_history(self, history_list):
        cleaned = []
        for entry in history_list or []:
            try:
                if len(entry) == 4:
                    cleaned.append((entry[0], int(entry[1]), entry[2], entry[3]))
            except (TypeError, ValueError):
                continue
        self.history = cleaned[:30]
        self._update_history_list()

    def add_to_history(self, book, chapter, start, end):
        entry = (book, int(chapter), start, end)
        if entry in self.history:
            self.history.remove(entry)
        self.history.insert(0, entry)
        self.history = self.history[:30]
        self._update_history_list()
        self.history_changed.emit(self.history)

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
        if not (0 <= index < len(self.history)):
            return
        book, chapter, start, end = self.history[index]
        self.selected_book = book
        self.chapter_spin.setRange(1, max(1, self.db.get_chapter_count(book)))
        self.chapter_spin.setValue(chapter)
        max_v = max(1, self.db.get_verse_count(book, chapter))
        self.start_spin.setRange(1, max_v)
        self.end_spin.setRange(1, max_v)
        self.start_spin.setValue(max(1, min(start or 1, max_v)))
        self.end_spin.setValue(max(1, min(end or max_v, max_v)))
        self.range_selected.emit(book, chapter, start or 1, end or max_v)
        self.history.insert(0, self.history.pop(index))
        self._update_history_list()
        self.history_changed.emit(self.history)

    def _delete_history(self, index):
        if 0 <= index < len(self.history):
            del self.history[index]
            self._update_history_list()
            self.history_changed.emit(self.history)

    def _clear_history(self):
        self.history.clear()
        self._update_history_list()
        self.history_changed.emit(self.history)

    def get_history(self):
        return self.history
