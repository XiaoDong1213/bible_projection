from PyQt6.QtCore import QPointF, QPoint, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFontMetrics, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .flow_layout import FlowLayout
from .query import (
    MODE_CONTIGUOUS,
    MODE_GAP,
    BookScopePanel,
    normalize_search_query,
    search_scripture,
)
from core.paths import styles_dir
from .result_item import ScriptureResultWidget


def _pager_arrow_pixmap(kind, color):
    """程序化画分页箭头（first/prev/next/last），2x 渲染保证高分屏清晰。"""
    pm = QPixmap(40, 40)
    pm.setDevicePixelRatio(2.0)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    if kind in ("first", "prev"):
        x_far, x_tip = (13.4, 9.4) if kind == "first" else (12.2, 8.2)
        painter.drawPolyline([QPointF(x_far, 6.4), QPointF(x_tip, 10), QPointF(x_far, 13.6)])
        if kind == "first":
            painter.drawLine(QPointF(5.6, 6.4), QPointF(5.6, 13.6))
    else:
        x_far, x_tip = (6.6, 10.6) if kind == "last" else (7.8, 11.8)
        painter.drawPolyline([QPointF(x_far, 6.4), QPointF(x_tip, 10), QPointF(x_far, 13.6)])
        if kind == "last":
            painter.drawLine(QPointF(14.4, 6.4), QPointF(14.4, 13.6))
    painter.end()
    return pm


class HistoryChipWidget(QWidget):
    """胶囊形历史词条：点胶囊再搜，右上角小叉单条删除。"""

    activated = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, text, label, parent=None):
        super().__init__(parent)
        self._text = text
        self.setObjectName("historyChip")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedHeight(30)
        self.setMinimumWidth(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(text)

        self._label = QLabel(label)
        self._label.setObjectName("historyChipLabel")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._delete = QPushButton("×")
        self._delete.setObjectName("historyChipDelete")
        self._delete.setFixedSize(18, 18)
        self._delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete.setToolTip("删除这条记录")
        self._delete.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._delete.setFlat(True)
        self._delete.clicked.connect(lambda: self.delete_requested.emit(self._text))

        grid = QGridLayout(self)
        grid.setContentsMargins(12, 0, 2, 0)
        grid.setSpacing(0)
        grid.addWidget(self._label, 0, 0, Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(
            self._delete,
            0,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

    def sizeHint(self):
        fm = QFontMetrics(self._label.font())
        w = fm.horizontalAdvance(self._label.text()) + 30
        return QSize(max(48, w), 30)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._delete.geometry().contains(event.pos()):
                self.activated.emit(self._text)
                event.accept()
                return
        super().mousePressEvent(event)


class ScriptureSearchWidget(QWidget):
    """经文全文搜索侧边面板。"""

    result_activated = pyqtSignal(object)
    result_project_requested = pyqtSignal(object)
    close_requested = pyqtSignal()
    PAGE_SIZE = 10
    PANEL_WIDTH = 520
    INPUT_HEIGHT = 40

    def __init__(self, db, config=None, parent=None, theme="dark"):
        super().__init__(parent)
        self.db = db
        self.config = config
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.page = 0
        self.total = 0
        self.results = []
        self.selected_books = set()
        self.history = (config.load_scripture_search_history() if config else [])[:10]
        self.setObjectName("scriptureSearchPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # 宽度交给主分割条按比例分配（首开 520 由 install 控制），这里只给下限
        self.setMinimumWidth(360)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._build_ui()
        self._apply_style()
        self._update_scope_text()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        # —— 标题 ——
        header = QHBoxLayout()
        header.setSpacing(8)
        title = QLabel("经文搜索")
        title.setObjectName("scriptureSearchTitle")
        header.addWidget(title, 1)
        close = QPushButton("×")
        close.setObjectName("scriptureSearchClose")
        close.setFixedSize(36, 36)
        close.setFlat(True)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        close.clicked.connect(self.close_requested.emit)
        header.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        # —— 搜索条（常驻）——
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("scriptureSearchInput")
        self.search_input.setPlaceholderText("例如：爱永不止息　或　爱 盼望")
        self.search_input.setFixedHeight(self.INPUT_HEIGHT)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_input.returnPressed.connect(self._search_now)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("scriptureSearchButton")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setFixedSize(80, self.INPUT_HEIGHT)
        # clicked 会传 checked，不能直接连到 search(remember=…)
        self.search_btn.clicked.connect(self._search_now)
        search_row.addWidget(self.search_btn)
        root.addLayout(search_row)

        # —— 匹配方式 + 范围 ——
        options = QHBoxLayout()
        options.setSpacing(6)

        self.gap_radio = QRadioButton("相近")
        self.contiguous_radio = QRadioButton("一致")
        self.gap_radio.setObjectName("searchOption")
        self.contiguous_radio.setObjectName("searchOption")
        self.gap_radio.setChecked(True)
        self.gap_radio.setToolTip("按字顺序找，中间可以少几个字；空格表示多个条件都要满足")
        self.contiguous_radio.setToolTip("要跟输入连着一样出现；空格表示多个条件都要满足")
        self.match_group = QButtonGroup(self)
        self.match_group.addButton(self.gap_radio)
        self.match_group.addButton(self.contiguous_radio)
        options.addWidget(self.gap_radio)
        options.addWidget(self.contiguous_radio)
        options.addStretch(1)

        self.scope_btn = QPushButton("全部书卷")
        self.scope_btn.setObjectName("scriptureScopeButton")
        self.scope_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scope_btn.setFixedHeight(30)
        self.scope_btn.setCheckable(True)
        self.scope_btn.clicked.connect(self._toggle_scope)
        options.addWidget(self.scope_btn)
        root.addLayout(options)

        # —— 书卷范围（内嵌展开，点「全部书卷」/「收起」切换）——
        # 高度上限由 BookScopePanel 按「6 行书卷」内容自定，这里不再覆盖
        self.scope_panel = BookScopePanel(self.db, self.selected_books, self.theme)
        self.scope_panel.scope_changed.connect(self._on_scope_changed)
        self.scope_panel.close_requested.connect(self._toggle_scope)
        self.scope_panel.setVisible(False)
        root.addWidget(self.scope_panel)

        # —— 最近搜索（横向 chip，单行；整行给胶囊，溢出入口收进行尾「⋯」）——
        history_row = QHBoxLayout()
        history_row.setSpacing(6)
        history_label = QLabel("最近")
        history_label.setObjectName("searchHistoryLabel")
        history_row.addWidget(history_label)

        self.history_chips = QWidget()
        self.history_chips.setObjectName("scriptureHistoryChips")
        self.history_layout = FlowLayout(self.history_chips, spacing=6)
        # Flow 换行后容器要能变高：sizePolicy 必须开启 heightForWidth
        chips_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        chips_policy.setHeightForWidth(True)
        self.history_chips.setSizePolicy(chips_policy)
        # 装箱保证单行，容器高不会超过一行胶囊
        history_row.addWidget(self.history_chips, 1)

        # 行尾「⋯」三点图标（字符「⋯」在中文字体里太小看不清）
        self.more_history_btn = QPushButton()
        self.more_history_btn.setObjectName("historyMoreButton")
        self.more_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more_history_btn.setFixedSize(34, 30)
        self.more_history_btn.setIcon(QIcon(str(styles_dir() / "history-more.svg")))
        self.more_history_btn.setIconSize(QSize(22, 22))
        self.more_history_btn.setToolTip("更多历史 / 清空历史")
        self.more_history_btn.clicked.connect(self._show_history_menu)
        self.more_history_btn.setVisible(False)
        # 悬停时点变蓝（普通 QIcon 不跟 QSS 走，手动切图）
        self.more_history_btn.enterEvent = lambda _e: self._set_more_icon(True)
        self.more_history_btn.leaveEvent = lambda _e: self._set_more_icon(False)
        history_row.addWidget(self.more_history_btn)
        root.addLayout(history_row)
        self._refresh_history()

        # —— 结果区 ——
        result_top = QHBoxLayout()
        self.result_header = QLabel("搜索结果")
        self.result_header.setObjectName("scriptureResultHeader")
        result_top.addWidget(self.result_header, 1)
        self.result_hint = QLabel("")
        self.result_hint.setObjectName("scriptureResultHint")
        result_top.addWidget(self.result_hint)
        self.clear_results_btn = QPushButton("清空结果")
        self.clear_results_btn.setObjectName("resultClearButton")
        self.clear_results_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_results_btn.setToolTip("清空当前搜索结果，不影响历史")
        self.clear_results_btn.clicked.connect(self._clear_results)
        self.clear_results_btn.setEnabled(False)
        result_top.addWidget(self.clear_results_btn)
        root.addLayout(result_top)

        self.result_scroll = QScrollArea()
        self.result_scroll.setObjectName("scriptureResultScroll")
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.result_container = QWidget()
        self.result_container.setObjectName("scriptureResultContainer")
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setContentsMargins(0, 0, 4, 0)
        self.result_layout.setSpacing(8)
        self.result_scroll.setWidget(self.result_container)
        root.addWidget(self.result_scroll, 1)

        pager = QHBoxLayout()
        pager.setSpacing(4)
        self.first_btn = QPushButton()
        self.prev_btn = QPushButton()
        self.next_btn = QPushButton()
        self.last_btn = QPushButton()
        for btn in (self.first_btn, self.prev_btn, self.next_btn, self.last_btn):
            btn.setObjectName("scripturePagerButton")
            btn.setFixedSize(30, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.first_btn.setToolTip("跳到第一页")
        self.last_btn.setToolTip("跳到最后一页")
        self.first_btn.clicked.connect(lambda: self.load_page(0))
        self.last_btn.clicked.connect(lambda: self.load_page(1 << 30))
        self.prev_btn.clicked.connect(lambda: self.load_page(self.page - 1))
        self.next_btn.clicked.connect(lambda: self.load_page(self.page + 1))
        self.page_input = QLineEdit()
        self.page_input.setObjectName("scripturePageInput")
        self.page_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_input.setFixedSize(40, 30)
        self.page_input.setToolTip("输入页码，回车跳转")
        self.page_input.editingFinished.connect(self._apply_page_input)
        self.page_label = QLabel("/ 0 页")
        self.page_label.setObjectName("scripturePageLabel")
        pager.addStretch(1)
        for w in (self.first_btn, self.prev_btn, self.page_input,
                  self.page_label, self.next_btn, self.last_btn):
            pager.addWidget(w)
        pager.addStretch(1)
        root.addLayout(pager)
        self._update_pager()

        # 输入即搜：300ms 防抖；回车/按钮的显式搜索才计入历史
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._debounced_search)
        self.search_input.textChanged.connect(lambda: self._debounce.start())
        self._last_searched = None

    def _search_now(self):
        """回车 / 搜索按钮：停掉防抖立即搜，并计入历史。"""
        self._debounce.stop()
        self.search()

    def _debounced_search(self):
        """输入停顿后的自动搜索：查询与上次相同时跳过，避免冗余重搜。"""
        if self._query_text() != self._last_searched:
            self.search(remember=False)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 历史胶囊按行宽装箱：面板宽变了要重新装（记录宽度避免 refresh 内 resize 回环）
        w = self.history_chips.width()
        if getattr(self, "_last_hist_width", None) != w:
            self._last_hist_width = w
            self._refresh_history()

    def _toggle_scope(self):
        """展开/收起内嵌的范围选择区（用 isHidden 判断，独立于窗口显示链）。"""
        visible = self.scope_panel.isHidden()
        self.scope_panel.setVisible(visible)
        self.scope_btn.setChecked(visible)

    def _on_scope_changed(self, selected):
        """勾选实时生效：更新按钮文字并按新范围重搜当前查询。"""
        self.selected_books = selected
        self._update_scope_text()
        if self._query_text():
            self.search(remember=False)

    def on_bible_changed(self):
        """译本切换：清空范围、过时结果与展开中的书卷列表（换译本卷数/名称会变）。"""
        self.selected_books = set()
        self._clear_results()
        self.scope_panel.rebuild(self.db)
        self._update_scope_text()

    def _update_scope_text(self):
        all_count = len(self.db.get_books("all"))
        if not self.selected_books or len(self.selected_books) == all_count:
            self.scope_btn.setText("全部书卷")
            return
        old_books = {b for b, _ in self.db.get_books("old")}
        new_books = {b for b, _ in self.db.get_books("new")}
        if self.selected_books == old_books:
            self.scope_btn.setText("只旧约")
            return
        if self.selected_books == new_books:
            self.scope_btn.setText("只新约")
            return
        if len(self.selected_books) == 1:
            self.scope_btn.setText(next(iter(self.selected_books)))
            return
        self.scope_btn.setText(f"已选 {len(self.selected_books)} 卷")

    def _query_text(self):
        return self.search_input.text().strip()

    def _match_mode(self):
        if self.contiguous_radio.isChecked():
            return MODE_CONTIGUOUS
        return MODE_GAP

    def _highlight_terms(self):
        """高亮用：规范化后的每个字。"""
        return list(normalize_search_query(self._query_text()))

    def search(self, remember=True):
        # 防御：误把 clicked(bool) 传到 remember 时仍按「要记住」处理
        if not isinstance(remember, bool):
            remember = True
        query = self._query_text()
        self._last_searched = query
        if not normalize_search_query(query):
            self._clear_results()
            self.result_header.setText("请输入关键词")
            return
        if remember:
            self._remember_search(query)
        self.page = 0
        self.total, self.results = search_scripture(
            self.db,
            query,
            self.selected_books or None,
            self.PAGE_SIZE,
            0,
            mode=self._match_mode(),
        )
        self._render_results(self._highlight_terms())

    def _clear_results(self):
        """只清空结果列表，不动搜索历史。"""
        self.page = 0
        self.total = 0
        self.results = []
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.result_header.setText("搜索结果")
        self.result_hint.setText("")
        self.clear_results_btn.setEnabled(False)
        self._update_pager()

    def _remember_then_emit(self, payload):
        """防抖搜索没进历史；用户点中结果即视为有效搜索，先补记再转发。"""
        self._remember_search(self._query_text())
        self.result_activated.emit(payload)

    def _remember_then_project(self, payload):
        """投影操作同样是有效搜索，先补记历史再转发。"""
        self._remember_search(self._query_text())
        self.result_project_requested.emit(payload)

    def _render_results(self, keywords):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.results:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(20, 40, 20, 40)
            icon = QLabel("⌕")
            icon.setObjectName("scriptureEmptyIcon")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title = QLabel("没有找到相关经文")
            title.setObjectName("scriptureEmptyTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint = QLabel("换个关键词，或扩大搜索范围")
            hint.setObjectName("scriptureEmptyHint")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(icon)
            empty_layout.addWidget(title)
            empty_layout.addWidget(hint)
            self.result_layout.addWidget(empty)
        else:
            for result in self.results:
                card = ScriptureResultWidget(result, keywords, self.theme)
                # 点了结果=这个词确实用上了：转发前先计入搜索历史
                card.activated.connect(self._remember_then_emit)
                card.copy_requested.connect(self._copy_result)
                card.project_requested.connect(self._remember_then_project)
                self.result_layout.addWidget(card)
            self.result_layout.addStretch(1)
        self.result_header.setText(f"搜索结果 · {self.total} 条")
        self.result_hint.setText("点击标题定位" if self.results else "")
        self.clear_results_btn.setEnabled(bool(self.results) or self.total > 0)
        self._update_pager()
        self.result_scroll.verticalScrollBar().setValue(0)

    def _copy_result(self, result):
        from PyQt6.QtWidgets import QApplication

        label = result.get("verse_label", result.get("verse"))
        QApplication.clipboard().setText(
            f"{result['book']} {result['chapter']}:{label} {result['text']}"
        )

    def load_page(self, page):
        # 翻页是明确操作：取消挂起的自动搜索，防止迟到防抖把页码拉回第 1 页
        self._debounce.stop()
        query = self._query_text()
        if not normalize_search_query(query):
            return
        pages = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.page = max(0, min(page, pages - 1))
        _, self.results = search_scripture(
            self.db,
            query,
            self.selected_books or None,
            self.PAGE_SIZE,
            self.page * self.PAGE_SIZE,
            mode=self._match_mode(),
        )
        self._render_results(self._highlight_terms())

    def _update_pager(self):
        pages = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE) if self.total else 0
        self.page_input.setText(str(self.page + 1) if pages else "0")
        self.page_label.setText(f"/ {pages} 页")
        has = bool(pages)
        self.page_input.setEnabled(has)
        self.first_btn.setEnabled(has and self.page > 0)
        self.prev_btn.setEnabled(has and self.page > 0)
        self.next_btn.setEnabled(has and self.page < pages - 1)
        self.last_btn.setEnabled(has and self.page < pages - 1)

    def _apply_page_input(self):
        """页码输入框回车/失焦：跳到输入页（自动夹到合法范围），非法则恢复当前页。"""
        pages = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE) if self.total else 0
        try:
            value = int(self.page_input.text().strip())
        except ValueError:
            self._update_pager()
            return
        if pages:
            self.load_page(value - 1)
        self._update_pager()

    def _remember_search(self, text):
        if not text:
            return
        self.history = [text] + [x for x in self.history if x != text]
        self.history = self.history[:10]
        if self.config:
            self.config.save_scripture_search_history(self.history)
        self._refresh_history()

    def _refresh_history(self):
        """单行装箱：能放下多少放多少；「⋯」入口在有历史时常驻。"""
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.more_history_btn.setVisible(bool(self.history))
        if not self.history:
            empty = QLabel("暂无")
            empty.setObjectName("historyEmptyLabel")
            self.history_layout.addWidget(empty)
            return

        avail = max(60, self.history_chips.width() - 8)
        self._pack_history_chips(self.history, avail)

    def _pack_history_chips(self, words, avail, reserve=0):
        """按可用宽度把历史词装箱成单行胶囊，返回放下的个数；放不下的丢弃。"""
        used = 0
        count = 0
        for word in words:
            chip = HistoryChipWidget(word, self._chip_label(word))
            chip.activated.connect(self._use_history_text)
            chip.delete_requested.connect(self._delete_history)
            w = chip.sizeHint().width()
            gap = 6 if count else 0
            if used + gap + w > avail - reserve:
                chip.deleteLater()
                continue
            self.history_layout.addWidget(chip)
            used += gap + w
            count += 1
        return count

    def _set_more_icon(self, hovered):
        self.more_history_btn.setIcon(
            QIcon(
                str(styles_dir() / ("history-more-hover.svg" if hovered else "history-more.svg"))
            )
        )

    def _show_history_menu(self):
        """自绘历史浮层：不用 QMenu——Qt6 会给 QMenu 画黑色投影层，
        圆角外就是那圈黑框。Popup 语义下点击外部自动关闭。"""
        from ui.themes import DwmBorderlessCard

        overlay = DwmBorderlessCard(self, radius=10)
        overlay.set_theme(self.theme)
        v = QVBoxLayout(overlay)
        v.setContentsMargins(6, 6, 6, 6)
        v.setSpacing(2)
        for word in self.history:
            btn = QPushButton(self._chip_label(word))
            btn.setObjectName("historyMenuItem")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            btn.clicked.connect(
                lambda _checked=False, w=word, o=overlay: (self._use_history_text(w), o.close())
            )
            v.addWidget(btn)
        line = QFrame()
        line.setObjectName("historyMenuSeparator")
        line.setFixedHeight(1)
        v.addWidget(line)
        clear = QPushButton("清空全部历史")
        clear.setObjectName("historyMenuDanger")
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.setFlat(True)
        clear.clicked.connect(lambda: (self._clear_history(), overlay.close()))
        v.addWidget(clear)
        self._history_overlay = overlay

        overlay.adjustSize()
        btn = self.more_history_btn
        pos = btn.mapToGlobal(QPoint(btn.width() - overlay.width(), btn.height() + 6))
        screen = self.window().screen()
        if screen is not None:
            avail = screen.availableGeometry()
            if pos.x() + overlay.width() > avail.right():
                pos.setX(avail.right() - overlay.width())
            if pos.y() + overlay.height() > avail.bottom():
                pos.setY(btn.mapToGlobal(QPoint(0, 0)).y() - overlay.height() - 6)
        overlay.move(pos)
        overlay.show()

    @staticmethod
    def _chip_label(text):
        value = str(text or "").strip()
        if len(value) <= 12:
            return value
        return value[:11] + "…"

    def _use_history_text(self, text):
        self.search_input.setText(text)
        # 点历史只重搜，不把该项挪到最前，避免胶囊乱跳
        self.search(remember=False)

    def _delete_history(self, text):
        self.history = [x for x in self.history if x != text]
        if self.config:
            self.config.save_scripture_search_history(self.history)
        self._refresh_history()

    def _clear_history(self):
        if not self.history:
            return
        self.history = []
        if self.config:
            self.config.save_scripture_search_history(self.history)
        self._refresh_history()

    def apply_theme(self, theme):
        self.theme = theme if theme in ("dark", "light") else "dark"
        self._apply_style()
        if self.results:
            self._render_results(self._highlight_terms())
        else:
            self._refresh_history()

    def _apply_style(self):
        from ui.themes import theme_tokens

        t = theme_tokens(self.theme)
        self.setStyleSheet(
            f"""
        QWidget#scriptureSearchPanel {{
            background:{t['surface_raised']}; color:{t['text']};
            border:none; border-left:1px solid {t['border']}; border-radius:0;
        }}
        QLabel#scriptureSearchTitle {{ color:{t['text']}; font-size:18px; font-weight:600; }}
        QPushButton#scriptureSearchClose {{
            background:transparent; color:{t['text_muted']}; border:none;
            padding:0; margin:0; min-width:36px; max-width:36px;
            min-height:36px; max-height:36px; font-size:22px; font-weight:500;
        }}
        QPushButton#scriptureSearchClose:hover {{
            background:{t['control_hover']}; color:{t['text']}; border-radius:8px;
        }}
        QLineEdit#scriptureSearchInput {{
            background:{t['control']}; color:{t['text']}; border:1px solid {t['border']};
            border-radius:9px; padding:0 12px; font-size:14px;
        }}
        QLineEdit#scriptureSearchInput:focus {{ border:1px solid {t['focus_ring']}; }}
        QPushButton#scriptureSearchButton {{
            background:{t['accent']}; color:#FFFFFF; border:1px solid {t['accent']};
            border-radius:9px; padding:0; font-size:14px; font-weight:600;
        }}
        QPushButton#scriptureSearchButton:hover {{ background:{t['accent_hover']}; }}
        QRadioButton#searchOption {{
            background:{t['control']}; color:{t['text_muted']}; border:1px solid {t['border']};
            border-radius:8px; padding:6px 10px; spacing:0px; font-size:12px;
        }}
        QRadioButton#searchOption::indicator {{ width:0px; height:0px; }}
        QRadioButton#searchOption:checked {{
            background:{t['accent_soft']}; color:{t['accent_text']}; border-color:{t['accent']};
        }}
        QPushButton#scriptureScopeButton {{
            background:{t['control']}; color:{t['text']}; border:1px solid {t['border']};
            border-radius:8px; padding:0 12px; text-align:left; font-size:12px; min-width:100px;
        }}
        QPushButton#scriptureScopeButton:hover {{
            background:{t['control_hover']}; border-color:{t['border_strong']};
        }}
        QLabel#searchHistoryLabel {{ color:{t['text_muted']}; font-size:12px; font-weight:600; }}
        QLabel#historyEmptyLabel {{ color:{t['text_faint']}; font-size:12px; padding-left:8px; }}
        QPushButton#historyMoreButton {{
            background:transparent; color:{t['text']}; border:none; padding:0;
            font-size:16px; font-weight:600;
        }}
        QPushButton#historyMoreButton:hover {{ color:{t['accent']}; }}
        QWidget#historyMenuCard {{
            background:{t['surface_raised']}; border:none; border-radius:10px;
        }}
        QPushButton#historyMenuItem {{
            background:transparent; color:{t['text']}; border:none;
            border-radius:6px; padding:8px 24px 8px 14px;
            text-align:left; font-size:13px;
        }}
        QPushButton#historyMenuItem:hover {{
            background:{t['accent_soft']}; color:{t['accent_text']};
        }}
        QWidget#historyMenuSeparator {{
            background:{t['border']}; max-height:1px; border:none;
        }}
        QPushButton#historyMenuDanger {{
            background:transparent; color:#EF4444; border:none;
            border-radius:6px; padding:8px 24px 8px 14px;
            text-align:left; font-size:13px;
        }}
        QPushButton#historyMenuDanger:hover {{ background:rgba(239,68,68,0.12); }}
        QPushButton#resultClearButton {{
            background:transparent; color:{t['text_muted']}; border:none; padding:2px 6px; font-size:12px;
        }}
        QPushButton#resultClearButton:hover {{ color:{t['accent']}; }}
        QPushButton#resultClearButton:disabled {{ color:{t['text_faint']}; }}
        QPushButton#scripturePagerButton {{
            background:transparent; border:none;
            border-radius:8px; padding:0;
        }}
        QPushButton#scripturePagerButton:hover {{
            background:{t['control_hover']};
        }}
        QLineEdit#scripturePageInput {{
            background:{t['surface_raised']}; color:{t['text']}; border:1px solid {t['border']};
            border-radius:8px; padding:0 4px; font-size:13px;
        }}
        QLineEdit#scripturePageInput:focus {{ border:1px solid {t['focus_ring']}; }}
        QLineEdit#scripturePageInput:disabled {{ color:{t['text_faint']}; }}
        QLabel#scripturePageLabel {{ color:{t['text_muted']}; font-size:13px; }}
        QWidget#historyChip {{
            background:{t['control']}; color:{t['text']}; border:1px solid {t['border']};
            border-radius:15px;
        }}
        QWidget#historyChip:hover {{
            background:{t['accent_soft']}; border-color:{t['accent']};
        }}
        QLabel#historyChipLabel {{
            background:transparent; color:{t['text']}; font-size:12px; border:none;
            padding-right:8px;
        }}
        QWidget#historyChip:hover QLabel#historyChipLabel {{ color:{t['accent_text']}; }}
        QPushButton#historyChipDelete {{
            background:transparent; color:{t['text_faint']}; border:none;
            border-radius:7px; padding:0; margin:0;
            min-width:14px; max-width:14px; min-height:14px; max-height:14px;
            font-size:12px; font-weight:700;
        }}
        QPushButton#historyChipDelete:hover {{
            background:{t['control_hover']}; color:{t['text']};
        }}
        QLabel#scriptureResultHeader {{ color:{t['text']}; font-size:14px; font-weight:600; }}
        QLabel#scriptureResultHint {{ color:{t['text_muted']}; font-size:11px; }}
        QScrollArea#scriptureResultScroll {{ background:transparent; border:none; }}
        QWidget#scriptureResultContainer {{ background:transparent; }}
        QFrame#scriptureSearchResult {{
            background:{t['control']}; border:1px solid {t['border']}; border-radius:10px;
        }}
        QPushButton#scriptureResultTitle {{
            background:transparent; color:{t['accent']}; border:none;
            text-align:left; font-size:14px; font-weight:600; padding:0;
        }}
        QPushButton#scriptureResultAction {{
            background:transparent; color:{t['text_muted']}; border:1px solid {t['border']};
            border-radius:7px; padding:0; font-size:12px;
        }}
        QPushButton#scriptureResultAction:hover {{
            background:{t['control_hover']}; color:{t['text']};
        }}
        QLabel#scriptureResultText {{ color:{t['text']}; font-size:13px; }}
        QLabel#scriptureEmptyIcon {{ color:{t['text_muted']}; font-size:28px; }}
        QLabel#scriptureEmptyTitle {{ color:{t['text']}; font-size:15px; font-weight:600; }}
        QLabel#scriptureEmptyHint {{ color:{t['text_muted']}; font-size:12px; }}
        """
        )
        self._apply_pager_icons()

    def _apply_pager_icons(self):
        """分页箭头用矢量图标：颜色随主题，禁用态换淡色版本。"""
        from ui.themes import theme_tokens

        t = theme_tokens(self.theme)
        for btn, kind in (
            (self.first_btn, "first"),
            (self.prev_btn, "prev"),
            (self.next_btn, "next"),
            (self.last_btn, "last"),
        ):
            icon = QIcon(_pager_arrow_pixmap(kind, QColor(t["text_muted"])))
            icon.addPixmap(
                _pager_arrow_pixmap(kind, QColor(t["text_faint"])), QIcon.Mode.Disabled
            )
            btn.setIcon(icon)
            btn.setIconSize(QSize(18, 18))
