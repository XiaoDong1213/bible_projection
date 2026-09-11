from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .query import BookScopeDialog, normalize_search_query, search_scripture
from .result_item import ScriptureResultWidget


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
        self._delete.setFixedSize(14, 14)
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
        self.setFixedWidth(self.PANEL_WIDTH)
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
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("经文搜索")
        title.setObjectName("scriptureSearchTitle")
        title_box.addWidget(title)
        subtitle = QLabel("Ctrl + F · 定位 / 复制 / 投影")
        subtitle.setObjectName("scriptureSearchSubtitle")
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
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
        self.search_input.setPlaceholderText("例如：爱永不止息（可漏字）")
        self.search_input.setFixedHeight(self.INPUT_HEIGHT)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_input.returnPressed.connect(self.search)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("搜索")
        self.search_btn.setObjectName("scriptureSearchButton")
        self.search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_btn.setFixedSize(80, self.INPUT_HEIGHT)
        self.search_btn.clicked.connect(self.search)
        search_row.addWidget(self.search_btn)
        root.addLayout(search_row)

        # —— 范围 ——
        options = QHBoxLayout()
        options.setSpacing(6)
        hint = QLabel("按字顺序匹配，中间可漏字")
        hint.setObjectName("searchMatchHint")
        options.addWidget(hint, 1)

        self.scope_btn = QPushButton("全部书卷")
        self.scope_btn.setObjectName("scriptureScopeButton")
        self.scope_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scope_btn.setFixedHeight(30)
        self.scope_btn.clicked.connect(self._choose_scope)
        options.addWidget(self.scope_btn)
        root.addLayout(options)

        # —— 最近搜索（横向 chip）——
        history_row = QHBoxLayout()
        history_row.setSpacing(6)
        history_label = QLabel("最近")
        history_label.setObjectName("searchHistoryLabel")
        history_row.addWidget(history_label)

        self.history_chips = QWidget()
        self.history_chips.setObjectName("scriptureHistoryChips")
        self.history_layout = QHBoxLayout(self.history_chips)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(6)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        history_row.addWidget(self.history_chips, 1)

        self.clear_history_btn = QPushButton("清空")
        self.clear_history_btn.setObjectName("historyClearButton")
        self.clear_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_history_btn.clicked.connect(self._clear_history)
        history_row.addWidget(self.clear_history_btn)
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
        pager.setSpacing(8)
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        self.prev_btn.setObjectName("scripturePagerButton")
        self.next_btn.setObjectName("scripturePagerButton")
        self.prev_btn.setFixedSize(34, 32)
        self.next_btn.setFixedSize(34, 32)
        self.prev_btn.clicked.connect(lambda: self.load_page(self.page - 1))
        self.next_btn.clicked.connect(lambda: self.load_page(self.page + 1))
        pager.addWidget(self.prev_btn)
        self.page_label = QLabel("第 0 / 0 页")
        self.page_label.setObjectName("scripturePageLabel")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pager.addWidget(self.page_label, 1)
        pager.addWidget(self.next_btn)
        root.addLayout(pager)
        self._update_pager()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _choose_scope(self):
        dialog = BookScopeDialog(self.db, self.selected_books, self, self.theme)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.selected_books = dialog.selected_books()
            self._update_scope_text()

    def _update_scope_text(self):
        all_count = len(self.db.get_books("all"))
        if not self.selected_books or len(self.selected_books) == all_count:
            self.scope_btn.setText("全部书卷")
        elif len(self.selected_books) == 1:
            self.scope_btn.setText(next(iter(self.selected_books)))
        else:
            self.scope_btn.setText(f"已选 {len(self.selected_books)} 卷")

    def _query_text(self):
        return self.search_input.text().strip()

    def _highlight_terms(self):
        """高亮用：规范化后的每个字。"""
        return list(normalize_search_query(self._query_text()))

    def search(self, remember=True):
        query = self._query_text()
        if not normalize_search_query(query):
            self.result_header.setText("请输入关键词")
            self.result_hint.setText("")
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
        )
        self._render_results(self._highlight_terms())

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
                card.activated.connect(self.result_activated.emit)
                card.copy_requested.connect(self._copy_result)
                card.project_requested.connect(self.result_project_requested.emit)
                self.result_layout.addWidget(card)
            self.result_layout.addStretch(1)
        self.result_header.setText(f"搜索结果 · {self.total} 条")
        self.result_hint.setText("点击标题定位")
        self._update_pager()
        self.result_scroll.verticalScrollBar().setValue(0)

    def _copy_result(self, result):
        from PyQt6.QtWidgets import QApplication

        label = result.get("verse_label", result.get("verse"))
        QApplication.clipboard().setText(
            f"{result['book']} {result['chapter']}:{label} {result['text']}"
        )

    def load_page(self, page):
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
        )
        self._render_results(self._highlight_terms())

    def _update_pager(self):
        pages = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE) if self.total else 0
        self.page_label.setText(
            f"第 {self.page + 1} / {pages} 页" if pages else "第 0 / 0 页"
        )
        self.prev_btn.setEnabled(self.page > 0)
        self.next_btn.setEnabled(bool(pages) and self.page < pages - 1)

    def _remember_search(self, text):
        if not text:
            return
        self.history = [text] + [x for x in self.history if x != text]
        self.history = self.history[:10]
        if self.config:
            self.config.save_scripture_search_history(self.history)
        self._refresh_history()

    def _refresh_history(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.clear_history_btn.setEnabled(bool(self.history))
        if not self.history:
            empty = QLabel("暂无")
            empty.setObjectName("historyEmptyLabel")
            self.history_layout.addWidget(empty)
            self.history_layout.addStretch(1)
            return

        # 横向胶囊，最多显示 6 条；右上角小叉可单条删除
        for text in self.history[:6]:
            chip = HistoryChipWidget(text, self._chip_label(text))
            chip.activated.connect(self._use_history_text)
            chip.delete_requested.connect(self._delete_history)
            self.history_layout.addWidget(chip)
        self.history_layout.addStretch(1)

    @staticmethod
    def _chip_label(text):
        value = str(text or "").strip()
        if len(value) <= 8:
            return value
        return value[:7] + "…"

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
        QLabel#scriptureSearchSubtitle {{ color:{t['text_muted']}; font-size:12px; }}
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
            border-radius:9px; font-size:14px; font-weight:600;
        }}
        QPushButton#scriptureSearchButton:hover {{ background:{t['accent_hover']}; }}
        QLabel#searchMatchHint {{ color:{t['text_muted']}; font-size:12px; }}
        QPushButton#scriptureScopeButton {{
            background:{t['control']}; color:{t['text']}; border:1px solid {t['border']};
            border-radius:8px; padding:0 12px; text-align:left; font-size:12px; min-width:100px;
        }}
        QPushButton#scriptureScopeButton:hover {{
            background:{t['control_hover']}; border-color:{t['border_strong']};
        }}
        QLabel#searchHistoryLabel {{ color:{t['text_muted']}; font-size:12px; font-weight:600; }}
        QLabel#historyEmptyLabel {{ color:{t['text_faint']}; font-size:12px; }}
        QPushButton#historyClearButton {{
            background:transparent; color:{t['text_muted']}; border:none; padding:2px 6px; font-size:12px;
        }}
        QPushButton#historyClearButton:hover {{ color:{t['accent']}; }}
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
        QLabel#scripturePageLabel {{ color:{t['text_muted']}; font-size:12px; }}
        QPushButton#scripturePagerButton {{
            background:{t['control']}; color:{t['text']}; border:1px solid {t['border']};
            border-radius:8px; font-size:18px;
        }}
        QPushButton#scripturePagerButton:hover:enabled {{ background:{t['control_hover']}; }}
        QPushButton#scripturePagerButton:disabled {{ color:{t['text_faint']}; }}
        """
        )
