from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QTabBar, QPushButton, QGridLayout,
    QLabel, QSpinBox, QHBoxLayout, QFrame, QScrollArea, QSizePolicy,
    QLineEdit, QStackedWidget, QButtonGroup, QApplication,
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from .history_item import HistoryListWidget
from .selection import ScriptureSelection


class VisibleSpinBox(QSpinBox):
    """数字输入框。"""
    pass


class EqualTabBar(QTabBar):
    """均分页签宽度。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setExpanding(True)
        self.setDrawBase(False)
        self.setElideMode(Qt.TextElideMode.ElideNone)
        self.setMinimumHeight(40)

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
        height = max(hint.height(), 40)
        return QSize(width, height)

    def minimumTabSizeHint(self, index):
        hint = super().minimumTabSizeHint(index)
        return QSize(max(hint.width(), 48), max(hint.height(), 40))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateGeometry()


class BookGridWidget(QScrollArea):
    """书卷网格。"""

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
        self._grid.setContentsMargins(12, 12, 12, 12)
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
            btn.setMinimumHeight(40)
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
    range_selected = pyqtSignal(object)
    history_opened = pyqtSignal(object)
    verse_segmentation_changed = pyqtSignal(bool)
    history_changed = pyqtSignal(list)

    MODE_SINGLE = 0
    MODE_CROSS = 1
    MODE_SKIP = 2

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
        hl.setContentsMargins(12, 12, 12, 12)
        hl.setSpacing(10)
        self.history_list = HistoryListWidget()
        self.history_list.item_clicked.connect(self._on_history_clicked)
        self.history_list.item_deleted.connect(self._delete_history)
        self.history_list.item_copy_requested.connect(self._copy_history)
        hl.addWidget(self.history_list, 1)
        clear_btn = QPushButton("清空历史")
        clear_btn.setObjectName("clearHistoryBtn")
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._clear_history)
        hl.addWidget(clear_btn)
        self.tab_widget.addTab(history_widget, "历史")
        layout.addWidget(self.tab_widget, 1)

        bottom = QFrame()
        bottom.setObjectName("rangeBox")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 10)
        bottom_layout.setSpacing(8)

        # 模式：与顶栏页签同语言（下划线，无外框）
        mode_bar = QWidget()
        mode_bar.setObjectName("modeBar")
        mode_row = QHBoxLayout(mode_bar)
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons = []
        for mode, label in (
            (self.MODE_SINGLE, "单章"),
            (self.MODE_CROSS, "跨章"),
            (self.MODE_SKIP, "跳节"),
        ):
            btn = QPushButton(label)
            btn.setObjectName("modeBtn")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setProperty("modeValue", mode)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(30)
            btn.setFlat(True)
            self.mode_group.addButton(btn, mode)
            mode_row.addWidget(btn)
            self.mode_buttons.append(btn)
        self.mode_buttons[0].setChecked(True)
        self.mode_group.idClicked.connect(self._on_mode_changed)
        bottom_layout.addWidget(mode_bar)

        self.range_stack = QStackedWidget()
        self.range_stack.setObjectName("rangeStack")

        # ---- 单章：一行内联 ----
        single_page = QWidget()
        single_page.setObjectName("rangePage")
        single_row = QHBoxLayout(single_page)
        single_row.setContentsMargins(0, 4, 0, 0)
        single_row.setSpacing(6)
        self.chapter_spin = self._make_range_spin(1, 150)
        self.chapter_spin.valueChanged.connect(self._on_chapter_changed)
        self.start_spin = self._make_range_spin(1, 176)
        self.end_spin = self._make_range_spin(1, 176)
        single_row.addLayout(self._inline_field("章", self.chapter_spin))
        single_row.addLayout(self._inline_field("起", self.start_spin))
        single_row.addLayout(self._inline_field("止", self.end_spin))
        self.range_stack.addWidget(single_page)

        # ---- 跨章 ----
        cross_page = QWidget()
        cross_page.setObjectName("rangePage")
        cross_root = QVBoxLayout(cross_page)
        cross_root.setContentsMargins(0, 4, 0, 0)
        cross_root.setSpacing(6)
        self.cross_start_ch = self._make_range_spin(1, 150)
        self.cross_start_v = self._make_range_spin(1, 176)
        self.cross_end_ch = self._make_range_spin(1, 150)
        self.cross_end_v = self._make_range_spin(1, 176)
        self.cross_start_ch.valueChanged.connect(self._on_cross_start_ch_changed)
        self.cross_end_ch.valueChanged.connect(self._on_cross_end_ch_changed)
        cross_root.addLayout(
            self._labeled_spin_row("起", ("章", self.cross_start_ch), ("节", self.cross_start_v))
        )
        cross_root.addLayout(
            self._labeled_spin_row("止", ("章", self.cross_end_ch), ("节", self.cross_end_v))
        )
        self.range_stack.addWidget(cross_page)

        # ---- 跳节 ----
        skip_page = QWidget()
        skip_page.setObjectName("rangePage")
        skip_layout = QVBoxLayout(skip_page)
        skip_layout.setContentsMargins(0, 4, 0, 0)
        skip_layout.setSpacing(6)
        skip_top = QHBoxLayout()
        skip_top.setSpacing(6)
        self.skip_chapter_spin = self._make_range_spin(1, 150)
        self.skip_chapter_spin.setFixedWidth(78)
        self.skip_chapter_spin.valueChanged.connect(self._on_skip_chapter_changed)
        skip_top.addLayout(self._inline_field("章", self.skip_chapter_spin))
        skip_top.addStretch(1)
        skip_layout.addLayout(skip_top)
        self.skip_edit = QLineEdit()
        self.skip_edit.setObjectName("skipVerseEdit")
        self.skip_edit.setPlaceholderText("16-18 20 22-25")
        self.skip_edit.setClearButtonEnabled(True)
        skip_layout.addWidget(self.skip_edit)
        self.skip_hint = QLabel("连续 -　·　多段空格")
        self.skip_hint.setObjectName("navHint")
        skip_layout.addWidget(self.skip_hint)
        self.range_stack.addWidget(skip_page)

        bottom_layout.addWidget(self.range_stack)

        # 次要开关 + 主操作：一行减轻纵向堆叠
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.segment_btn = QPushButton("分节：关")
        self.segment_btn.setObjectName("segmentBtn")
        self.segment_btn.setCheckable(True)
        self.segment_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.segment_btn.setFixedWidth(88)
        self.segment_btn.clicked.connect(self._on_segment_clicked)
        action_row.addWidget(self.segment_btn)
        self.select_btn = QPushButton("显示所选经文")
        self.select_btn.setObjectName("selectRangeBtn")
        self.select_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_btn.clicked.connect(self._select_range)
        action_row.addWidget(self.select_btn, 1)
        bottom_layout.addLayout(action_row)

        layout.addWidget(bottom)
        self._update_segment_button(False)
        self.range_stack.setCurrentIndex(self.MODE_SINGLE)

    def _make_range_spin(self, lo, hi):
        spin = VisibleSpinBox()
        spin.setObjectName("rangeSpin")
        spin.setRange(lo, hi)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        spin.setMinimumHeight(26)
        spin.setMaximumHeight(28)
        return spin

    @staticmethod
    def _inline_field(label_text, spin):
        wrap = QHBoxLayout()
        wrap.setSpacing(4)
        wrap.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(label_text)
        lab.setObjectName("fieldLabel")
        wrap.addWidget(lab)
        wrap.addWidget(spin, 1)
        return wrap

    @staticmethod
    def _labeled_spin_row(title, *fields):
        """跨章一行：起/止 + 章节。"""
        row = QHBoxLayout()
        row.setSpacing(6)
        row.setContentsMargins(0, 0, 0, 0)
        title_lab = QLabel(title)
        title_lab.setObjectName("rowTitle")
        title_lab.setFixedWidth(16)
        row.addWidget(title_lab)
        for label_text, spin in fields:
            lab = QLabel(label_text)
            lab.setObjectName("fieldLabel")
            row.addWidget(lab)
            row.addWidget(spin, 1)
        return row

    def _on_mode_changed(self, mode=None):
        if mode is None:
            mode = self._current_mode()
        mode = int(mode)
        self.range_stack.setCurrentIndex(mode)
        if self.selected_book:
            self._sync_mode_limits()

    def _current_mode(self):
        checked = self.mode_group.checkedId()
        return checked if checked >= 0 else self.MODE_SINGLE

    def _set_mode(self, mode):
        mode = int(mode)
        btn = self.mode_group.button(mode)
        if btn is not None:
            blocked = self.mode_group.blockSignals(True)
            btn.setChecked(True)
            self.mode_group.blockSignals(blocked)
        self.range_stack.setCurrentIndex(mode)

    def _on_segment_clicked(self, checked):
        self._update_segment_button(bool(checked))
        self.verse_segmentation_changed.emit(bool(checked))

    def _update_segment_button(self, enabled):
        self.segment_btn.setChecked(bool(enabled))
        self.segment_btn.setText("分节：开" if enabled else "分节：关")
        self.segment_btn.setToolTip("按节分段显示经文")

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
        for grid in (self.old_list, self.new_list, self.short_list):
            grid.select_book(book)
        self.book_selected.emit(book, self.chapter_spin.value())

    def _set_selected_book(self, book, whole_chapter=False):
        self.selected_book = book
        max_ch = max(1, self.db.get_chapter_count(book))
        for spin in (
            self.chapter_spin,
            self.cross_start_ch,
            self.cross_end_ch,
            self.skip_chapter_spin,
        ):
            blocked = spin.blockSignals(True)
            spin.setRange(1, max_ch)
            spin.setValue(1)
            spin.blockSignals(blocked)
        self._set_verse_ranges(book, 1, whole_chapter=whole_chapter)
        self._sync_mode_limits()

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

        for spin in (self.cross_start_v, self.cross_end_v):
            blocked = spin.blockSignals(True)
            spin.setRange(1, max_v)
            if spin is self.cross_start_v:
                spin.setValue(1)
            else:
                spin.setValue(max_v if whole_chapter else min(5, max_v))
            spin.blockSignals(blocked)

        if whole_chapter:
            self.skip_edit.setText(f"1-{max_v}")
        elif not self.skip_edit.text().strip():
            self.skip_edit.setText("1-5" if max_v >= 5 else f"1-{max_v}")

    def _sync_mode_limits(self):
        if not self.selected_book:
            return
        book = self.selected_book
        max_ch = max(1, self.db.get_chapter_count(book))
        for spin in (
            self.chapter_spin,
            self.cross_start_ch,
            self.cross_end_ch,
            self.skip_chapter_spin,
        ):
            spin.setRange(1, max_ch)

        ch = int(self.chapter_spin.value())
        max_v = max(1, self.db.get_verse_count(book, ch))
        self.start_spin.setRange(1, max_v)
        self.end_spin.setRange(1, max_v)

        sc = int(self.cross_start_ch.value())
        ec = int(self.cross_end_ch.value())
        self.cross_start_v.setRange(1, max(1, self.db.get_verse_count(book, sc)))
        self.cross_end_v.setRange(1, max(1, self.db.get_verse_count(book, ec)))

    def _on_chapter_changed(self, chapter):
        if self.selected_book:
            self._set_verse_ranges(self.selected_book, chapter, whole_chapter=True)
            for spin in (self.cross_start_ch, self.cross_end_ch, self.skip_chapter_spin):
                blocked = spin.blockSignals(True)
                spin.setValue(int(chapter))
                spin.blockSignals(blocked)
            self._sync_mode_limits()

    def _on_cross_start_ch_changed(self, chapter):
        if not self.selected_book:
            return
        max_v = max(1, self.db.get_verse_count(self.selected_book, int(chapter)))
        blocked = self.cross_start_v.blockSignals(True)
        self.cross_start_v.setRange(1, max_v)
        if self.cross_start_v.value() > max_v:
            self.cross_start_v.setValue(max_v)
        self.cross_start_v.blockSignals(blocked)

    def _on_cross_end_ch_changed(self, chapter):
        if not self.selected_book:
            return
        max_v = max(1, self.db.get_verse_count(self.selected_book, int(chapter)))
        blocked = self.cross_end_v.blockSignals(True)
        self.cross_end_v.setRange(1, max_v)
        if self.cross_end_v.value() > max_v:
            self.cross_end_v.setValue(max_v)
        self.cross_end_v.blockSignals(blocked)

    def _on_skip_chapter_changed(self, chapter):
        if self.selected_book and not self._history_updating:
            max_v = max(1, self.db.get_verse_count(self.selected_book, int(chapter)))
            self.skip_hint.setText(f"本章 {max_v} 节　·　例 16-18 20")

    def sync_selection(self, book, chapter, start, end):
        self._history_updating = True
        try:
            self.selected_book = book
            for grid in (self.old_list, self.new_list, self.short_list):
                grid.select_book(book)
            self._set_mode(self.MODE_SINGLE)
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
            self._sync_mode_limits()
        finally:
            self._history_updating = False

    def sync_from_selection(self, selection: ScriptureSelection):
        """按选择同步左侧模式与控件。"""
        self._history_updating = True
        try:
            self.selected_book = selection.book
            for grid in (self.old_list, self.new_list, self.short_list):
                grid.select_book(selection.book)
            max_ch = max(1, self.db.get_chapter_count(selection.book))

            if selection.is_multi_chapter:
                self._set_mode(self.MODE_CROSS)
                first, last = selection.spans[0], selection.spans[-1]
                for spin, value in (
                    (self.cross_start_ch, first.chapter),
                    (self.cross_end_ch, last.chapter),
                ):
                    spin.blockSignals(True)
                    spin.setRange(1, max_ch)
                    spin.setValue(int(value))
                    spin.blockSignals(False)
                self._on_cross_start_ch_changed(first.chapter)
                self._on_cross_end_ch_changed(last.chapter)
                self.cross_start_v.setValue(first.start)
                self.cross_end_v.setValue(last.end)
                self.chapter_spin.blockSignals(True)
                self.chapter_spin.setRange(1, max_ch)
                self.chapter_spin.setValue(first.chapter)
                self.chapter_spin.blockSignals(False)
            elif len(selection.spans) > 1:
                self._set_mode(self.MODE_SKIP)
                chapter = selection.spans[0].chapter
                self.skip_chapter_spin.blockSignals(True)
                self.skip_chapter_spin.setRange(1, max_ch)
                self.skip_chapter_spin.setValue(chapter)
                self.skip_chapter_spin.blockSignals(False)
                self.skip_edit.setText(selection.space_verse_text())
                self.chapter_spin.blockSignals(True)
                self.chapter_spin.setRange(1, max_ch)
                self.chapter_spin.setValue(chapter)
                self.chapter_spin.blockSignals(False)
            else:
                span = selection.spans[0]
                self.sync_selection(selection.book, span.chapter, span.start, span.end)
                return
            self._sync_mode_limits()
        finally:
            self._history_updating = False

    def _current_selection(self):
        if not self.selected_book:
            return None
        book = self.selected_book
        mode = self._current_mode()

        if mode == self.MODE_CROSS:
            try:
                return ScriptureSelection.expand_cross_chapter(
                    book,
                    int(self.cross_start_ch.value()),
                    int(self.cross_start_v.value()),
                    int(self.cross_end_ch.value()),
                    int(self.cross_end_v.value()),
                    self.db.get_verse_count,
                )
            except ValueError:
                return None

        if mode == self.MODE_SKIP:
            chapter = int(self.skip_chapter_spin.value())
            max_v = max(1, self.db.get_verse_count(book, chapter))
            selection = ScriptureSelection.from_space_verses(
                book, chapter, self.skip_edit.text(), max_v
            )
            if selection is None:
                self.skip_hint.setText(f"格式无效　·　可用 1–{max_v}")
            return selection

        chapter = int(self.chapter_spin.value())
        start = int(self.start_spin.value())
        end = int(self.end_spin.value())
        if end < start:
            start, end = end, start
        return ScriptureSelection.single_chapter(book, chapter, start, end)

    def _select_range(self):
        entry = self._current_selection()
        if not entry:
            return
        self.range_selected.emit(entry)

    def load_history(self, history_list):
        self.history = []
        for entry in history_list or []:
            selection = ScriptureSelection.from_history_entry(entry)
            if selection is not None:
                self.history.append(selection)
        self.history = self.history[:30]
        self._update_history_list()

    def add_to_history(self, book, chapter, start, end):
        """兼容旧四元组调用。"""
        try:
            max_v = max(1, self.db.get_verse_count(str(book), int(chapter)))
            selection = ScriptureSelection.single_chapter(
                book, chapter, start, end, max_verse=max_v
            )
        except (TypeError, ValueError, AttributeError):
            return
        self.add_selection_to_history(selection)

    def add_selection_to_history(self, selection: ScriptureSelection):
        if selection is None:
            return
        self.history = [
            item for item in self.history
            if not (
                item.book == selection.book
                and item.spans == selection.spans
            )
        ]
        self.history.insert(0, selection)
        self.history = self.history[:30]
        self._update_history_list(selected_index=0)
        self.history_changed.emit([item.to_history_entry() for item in self.history])

    @staticmethod
    def _history_label(selection: ScriptureSelection):
        return selection.label()

    def _update_history_list(self, selected_index=-1):
        texts = [self._history_label(entry) for entry in self.history]
        self.history_list.set_entries(texts, selected_index=selected_index)

    def _on_history_clicked(self, index):
        if not 0 <= index < len(self.history):
            return
        selection = self.history[index]
        self.sync_from_selection(selection)
        self.history_list.set_selected_index(index)
        self.history_opened.emit(selection)

    def _copy_history(self, index):
        """复制历史记录的简称引用，内容可直接粘贴到搜索框。"""
        if not 0 <= index < len(self.history):
            return
        selection = self.history[index]
        short = self.db._short_name(selection.book)
        QApplication.clipboard().setText(self._history_short_label(selection, short))

    @staticmethod
    def _history_short_label(selection, short):
        if selection.is_simple:
            span = selection.spans[0]
            body = str(span.start) if span.start == span.end else f"{span.start}-{span.end}"
            return f"{short} {span.chapter}:{body}"
        if selection.is_multi_chapter:
            return selection.label()
        return f"{short} {selection.primary_chapter}:{selection.space_verse_text()}"

    def _delete_history(self, index):
        if 0 <= index < len(self.history):
            del self.history[index]
            selected = self.history_list.selected_index()
            if selected == index:
                selected = -1
            elif selected > index:
                selected -= 1
            self._update_history_list(selected_index=selected)
            self.history_changed.emit([item.to_history_entry() for item in self.history])

    def _clear_history(self):
        self.history.clear()
        self._update_history_list()
        self.history_changed.emit([])

    def get_history(self):
        return [item.to_history_entry() for item in self.history]
