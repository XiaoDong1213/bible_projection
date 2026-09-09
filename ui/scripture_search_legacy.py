from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .scripture_search import BookScopeDialog, ScriptureResultWidget, search_scripture


class ScriptureSearchWidget(QWidget):
    """恢复 676fa674 版本的经文搜索侧边面板外观与交互。"""

    result_activated = pyqtSignal(object)
    result_project_requested = pyqtSignal(object)
    close_requested = pyqtSignal()
    PAGE_SIZE = 10

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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedWidth(720)
        self._build_ui()
        self._apply_style()
        self._update_scope_text()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("经文搜索")
        title.setObjectName("scriptureSearchTitle")
        title_box.addWidget(title)
        subtitle = QLabel("搜索整本圣经中的经文，快速定位、复制或投影")
        subtitle.setObjectName("scriptureSearchSubtitle")
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)
        close = QPushButton("×")
        close.setObjectName("scriptureSearchClose")
        close.setFixedSize(34, 34)
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.clicked.connect(self.close_requested.emit)
        header.addWidget(close, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.condition_toggle = QPushButton("搜索条件  ▲")
        self.condition_toggle.setObjectName("searchConditionToggle")
        self.condition_toggle.setFlat(True)
        self.condition_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.condition_toggle.clicked.connect(self._toggle_conditions)
        root.addWidget(self.condition_toggle)

        self.condition_box = QWidget()
        self.condition_box.setObjectName("scriptureConditionBox")
        condition = QVBoxLayout(self.condition_box)
        condition.setContentsMargins(14, 14, 14, 14)
        condition.setSpacing(10)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("scriptureSearchInput")
        self.search_input.setPlaceholderText("输入经文关键词，例如：爱 盼望")
        self.search_input.setFixedHeight(44)
        self.search_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.search_input.returnPressed.connect(self.search)
        search_row.addWidget(self.search_input, 1, Qt.AlignmentFlag.AlignVCenter)
        search_btn = QPushButton("搜索")
        search_btn.setObjectName("scriptureSearchButton")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.setFixedSize(82, 30)
        search_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        search_btn.clicked.connect(self.search)
        search_row.addWidget(search_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        condition.addLayout(search_row)

        options = QHBoxLayout()
        options.setSpacing(8)
        match_label = QLabel("匹配方式")
        match_label.setObjectName("conditionLabel")
        options.addWidget(match_label)
        self.fuzzy_radio = QRadioButton("模糊")
        self.exact_radio = QRadioButton("精确")
        self.fuzzy_radio.setObjectName("searchOption")
        self.exact_radio.setObjectName("searchOption")
        self.fuzzy_radio.setChecked(True)
        self.match_group = QButtonGroup(self)
        self.match_group.addButton(self.fuzzy_radio)
        self.match_group.addButton(self.exact_radio)
        options.addWidget(self.fuzzy_radio)
        options.addWidget(self.exact_radio)
        keyword_label = QLabel("多关键词")
        keyword_label.setObjectName("conditionLabel")
        options.addSpacing(8)
        options.addWidget(keyword_label)
        self.all_radio = QRadioButton("同时包含")
        self.any_radio = QRadioButton("任意包含")
        self.all_radio.setObjectName("searchOption")
        self.any_radio.setObjectName("searchOption")
        self.all_radio.setChecked(True)
        self.keyword_group = QButtonGroup(self)
        self.keyword_group.addButton(self.all_radio)
        self.keyword_group.addButton(self.any_radio)
        options.addWidget(self.all_radio)
        options.addWidget(self.any_radio)
        options.addStretch(1)
        condition.addLayout(options)

        scope_row = QHBoxLayout()
        scope_row.setSpacing(8)
        scope_label = QLabel("搜索范围")
        scope_label.setObjectName("conditionLabel")
        scope_row.addWidget(scope_label)
        self.scope_btn = QPushButton("全部书卷")
        self.scope_btn.setObjectName("scriptureScopeButton")
        self.scope_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.scope_btn.clicked.connect(self._choose_scope)
        scope_row.addWidget(self.scope_btn, 1)
        condition.addLayout(scope_row)

        history_head = QHBoxLayout()
        history_head.setSpacing(8)
        history_label = QLabel("最近搜索")
        history_label.setObjectName("searchHistoryLabel")
        history_head.addWidget(history_label, 1)
        self.clear_history_btn = QPushButton("清空")
        self.clear_history_btn.setObjectName("historyClearButton")
        self.clear_history_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_history_btn.clicked.connect(self._clear_history)
        history_head.addWidget(self.clear_history_btn)
        condition.addLayout(history_head)

        self.history_scroll = QScrollArea()
        self.history_scroll.setObjectName("scriptureHistoryScroll")
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.history_scroll.setFixedHeight(190)

        self.history_container = QWidget()
        self.history_container.setObjectName("scriptureHistoryContainer")
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(4, 4, 4, 4)
        self.history_layout.setSpacing(4)
        self.history_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.history_scroll.setWidget(self.history_container)
        condition.addWidget(self.history_scroll)
        self._refresh_history()

        root.addWidget(self.condition_box)

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

    def _toggle_conditions(self):
        visible = not self.condition_box.isVisible()
        self.condition_box.setVisible(visible)
        self.condition_toggle.setText("搜索条件  ▲" if visible else "搜索条件  ▼")

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
            self.scope_btn.setText(f"已选择 {len(self.selected_books)} 卷")

    def _keywords(self):
        raw = self.search_input.text().strip()
        return [x for x in raw.replace("，", " ").split() if x]

    def search(self):
        keywords = self._keywords()
        if not keywords:
            self.result_header.setText("请输入关键词")
            self.result_hint.setText("")
            return
        self._remember_search(self.search_input.text().strip())
        self.page = 0
        self.total, self.results = search_scripture(self.db, keywords, self.fuzzy_radio.isChecked(), self.all_radio.isChecked(), self.selected_books or None, self.PAGE_SIZE, 0)
        self._render_results(keywords)
        self._toggle_conditions_closed()

    def _toggle_conditions_closed(self):
        self.condition_box.setVisible(False)
        self.condition_toggle.setText("搜索条件  ▼")

    def _render_results(self, keywords):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.results:
            empty = QWidget()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(20, 50, 20, 50)
            icon = QLabel("⌕")
            icon.setObjectName("scriptureEmptyIcon")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title = QLabel("没有找到相关经文")
            title.setObjectName("scriptureEmptyTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint = QLabel("换一个关键词试试，或扩大搜索范围")
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
        self.result_header.setText(f"搜索结果  ·  找到 {self.total} 条")
        self.result_hint.setText("点击经文标题可定位")
        self._update_pager()
        self.result_scroll.verticalScrollBar().setValue(0)

    def _copy_result(self, result):
        from PyQt6.QtWidgets import QApplication
        label = result.get("verse_label", result.get("verse"))
        QApplication.clipboard().setText(f"{result['book']} {result['chapter']}:{label} {result['text']}")

    def load_page(self, page):
        keywords = self._keywords()
        if not keywords:
            return
        pages = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.page = max(0, min(page, pages - 1))
        _, self.results = search_scripture(self.db, keywords, self.fuzzy_radio.isChecked(), self.all_radio.isChecked(), self.selected_books or None, self.PAGE_SIZE, self.page * self.PAGE_SIZE)
        self._render_results(keywords)

    def _update_pager(self):
        pages = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE) if self.total else 0
        self.page_label.setText(f"第 {self.page + 1} / {pages} 页" if pages else "第 0 / 0 页")
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
        for text in self.history[:10]:
            row = QFrame()
            row.setObjectName("scriptureHistoryRow")
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            row.setFixedHeight(36)

            layout = QHBoxLayout(row)
            layout.setContentsMargins(10, 2, 6, 2)
            layout.setSpacing(6)

            use_btn = QPushButton(text)
            use_btn.setObjectName("historyUseButton")
            use_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            use_btn.setToolTip("使用此搜索")
            use_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            use_btn.clicked.connect(lambda _, value=text: self._use_history_text(value))
            layout.addWidget(use_btn, 1)

            delete_btn = QPushButton("×")
            delete_btn.setObjectName("historyDeleteButton")
            delete_btn.setFixedSize(26, 26)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setToolTip("删除此搜索")
            delete_btn.clicked.connect(lambda _, value=text: self._delete_history(value))
            layout.addWidget(delete_btn)
            self.history_layout.addWidget(row)

    def _use_history_text(self, text):
        self.search_input.setText(text)
        self.search()

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
            self._render_results(self._keywords())
        else:
            self._refresh_history()

    def _apply_style(self):
        from .themes import theme_tokens
        t = theme_tokens(self.theme)
        self.setStyleSheet(f"""
        QWidget#scriptureSearchPanel {{ background:{t['surface_raised']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:14px; }}
        QLabel#scriptureSearchTitle {{ color:{t['text']}; font-size:19px; font-weight:600; }}
        QLabel#scriptureSearchSubtitle {{ color:{t['text_muted']}; font-size:12px; }}
        QPushButton#scriptureSearchClose {{ background:transparent; color:{t['text_muted']}; border:none; font-size:22px; }}
        QPushButton#scriptureSearchClose:hover {{ background:{t['control_hover']}; color:{t['text']}; }}
        QPushButton#searchConditionToggle {{ background:transparent; color:{t['text_muted']}; border:none; padding:2px 4px; text-align:left; font-size:12px; font-weight:600; }}
        QPushButton#searchConditionToggle:hover {{ color:{t['accent']}; }}
        QWidget#scriptureConditionBox {{ background:{t['surface_sunken']}; border:1px solid {t['border']}; border-radius:11px; }}
        QLineEdit#scriptureSearchInput {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px; padding:0 13px; height:44px; min-height:44px; max-height:44px; font-size:14px; }}
        QLineEdit#scriptureSearchInput:focus {{ border:1px solid {t['focus_ring']}; }}
        QPushButton#scriptureSearchButton {{ background:{t['accent']}; color:#FFFFFF; border:1px solid {t['accent']}; border-radius:9px; min-width:82px; max-width:82px; height:30px; min-height:30px; max-height:30px; font-size:14px; font-weight:600; }}
        QPushButton#scriptureSearchButton:hover {{ background:{t['accent_hover']}; }}
        QLabel#conditionLabel {{ color:{t['text_muted']}; font-size:12px; }}
        QRadioButton#searchOption {{ background:{t['control']}; color:{t['text_muted']}; border:1px solid {t['border']}; border-radius:8px; padding:7px 12px; spacing:0px; font-size:12px; min-height:18px; }}
        QRadioButton#searchOption::indicator {{ width:0px; height:0px; margin:0px; padding:0px; }}
        QRadioButton#searchOption:checked {{ background:{t['accent_soft']}; color:{t['text']}; border-color:{t['accent']}; }}
        QPushButton#scriptureScopeButton {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; min-height:34px; padding:0 12px; text-align:left; }}
        QPushButton#scriptureScopeButton:hover {{ background:{t['control_hover']}; border-color:{t['border_strong']}; }}
        QLabel#searchHistoryLabel {{ color:{t['text_muted']}; font-size:12px; font-weight:600; }}
        QPushButton#historyClearButton {{ background:transparent; color:{t['text_muted']}; border:none; padding:2px 6px; }}
        QPushButton#historyClearButton:hover {{ color:{t['accent']}; }}
        QScrollArea#scriptureHistoryScroll {{ background:transparent; border:none; }}
        QWidget#scriptureHistoryContainer {{ background:transparent; }}
        QFrame#scriptureHistoryRow {{ background:{t['control']}; border:1px solid {t['border']}; border-radius:8px; }}
        QPushButton#historyUseButton {{ background:transparent; color:{t['text']}; border:none; text-align:left; padding:0; }}
        QPushButton#historyUseButton:hover {{ color:{t['accent']}; }}
        QPushButton#historyDeleteButton {{ background:transparent; color:{t['text_muted']}; border:none; font-size:16px; }}
        QPushButton#historyDeleteButton:hover {{ color:{t['danger']}; }}
        QLabel#scriptureResultHeader {{ color:{t['text']}; font-size:14px; font-weight:600; }}
        QLabel#scriptureResultHint {{ color:{t['text_muted']}; font-size:11px; }}
        QScrollArea#scriptureResultScroll {{ background:transparent; border:none; }}
        QWidget#scriptureResultContainer {{ background:transparent; }}
        QFrame#scriptureSearchResult {{ background:{t['control']}; border:1px solid {t['border']}; border-radius:10px; }}
        QPushButton#scriptureResultTitle {{ background:transparent; color:{t['accent']}; border:none; text-align:left; font-size:14px; font-weight:600; padding:0; }}
        QPushButton#scriptureResultAction {{ background:transparent; color:{t['text_muted']}; border:1px solid {t['border']}; border-radius:7px; padding:4px 10px; }}
        QPushButton#scriptureResultAction:hover {{ background:{t['control_hover']}; color:{t['text']}; }}
        QLabel#scriptureResultText {{ color:{t['text']}; font-size:13px; line-height:1.7; }}
        QLabel#scriptureEmptyIcon {{ color:{t['text_muted']}; font-size:30px; }}
        QLabel#scriptureEmptyTitle {{ color:{t['text']}; font-size:15px; font-weight:600; }}
        QLabel#scriptureEmptyHint {{ color:{t['text_muted']}; font-size:12px; }}
        QLabel#scripturePageLabel {{ color:{t['text_muted']}; font-size:12px; }}
        QPushButton#scripturePagerButton {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; min-width:34px; min-height:32px; font-size:18px; }}
        QPushButton#scripturePagerButton:hover:enabled {{ background:{t['control_hover']}; }}
        QPushButton#scripturePagerButton:disabled {{ color:{t['text_disabled']}; }}
        """)
