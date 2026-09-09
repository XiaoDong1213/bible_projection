import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from .themes import theme_tokens


def search_scripture(db, keywords, fuzzy=True, match_all=True, books=None, limit=10, offset=0):
    """使用 SQL 分页查询经文，避免把整本圣经加载到 Python。"""
    terms = [str(k).strip() for k in keywords if str(k).strip()]
    if not terms:
        return 0, []

    table = db._quote(db.verse_table)
    book_col = db._quote(db.book_col)
    chapter_col = db._quote(db.chapter_col)
    verse_col = db._quote(db.verse_col)
    text_col = db._quote(db.text_col)
    conditions = []
    params = []
    for term in terms:
        if fuzzy:
            conditions.append(f"{text_col} LIKE ?")
            params.append(f"%{term}%")
        else:
            conditions.append(f"instr({text_col}, ?) > 0")
            params.append(term)
    joiner = " AND " if match_all else " OR "
    where = f"({joiner.join(conditions)})"
    if books:
        values = [db.book_meta.get(book, {}).get("id", book) for book in books]
        placeholders = ",".join("?" for _ in values)
        where += f" AND {book_col} IN ({placeholders})"
        params.extend(values)
    total = int(db.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0])
    select_sql = (
        f"SELECT {book_col} AS raw_book, {chapter_col} AS chapter, "
        f"{verse_col} AS verse, {text_col} AS text FROM {table} "
        f"WHERE {where} ORDER BY rowid LIMIT ? OFFSET ?"
    )
    rows = db.conn.execute(select_sql, params + [int(limit), int(offset)]).fetchall()
    id_to_name = {str(v.get("id")).strip(): k for k, v in db.book_meta.items() if v.get("id") is not None}
    return total, [{
        "book": id_to_name.get(str(row["raw_book"]).strip(), str(row["raw_book"])),
        "short": db._short_name(id_to_name.get(str(row["raw_book"]).strip(), str(row["raw_book"]))),
        "chapter": int(row["chapter"]), "verse": int(row["verse"]), "text": str(row["text"]),
    } for row in rows]


class BookScopeDialog(QDialog):
    """选择经文搜索范围。"""
    def __init__(self, db, selected=None, parent=None, theme="dark"):
        super().__init__(parent)
        self.db = db
        self.selected = set(selected or [])
        self.theme = theme if theme in ("dark", "light") else "dark"
        self._lists = {}
        self.setObjectName("scriptureScopeDialog")
        self.setWindowTitle("选择搜索范围")
        self.setFixedSize(640, 560)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 18)
        root.setSpacing(12)
        heading = QLabel("选择搜索范围")
        heading.setObjectName("scopeDialogTitle")
        root.addWidget(heading)
        hint = QLabel("点击书卷即可选择或取消选择。")
        hint.setObjectName("scopeDialogHint")
        root.addWidget(hint)
        self.filter_input = QLineEdit()
        self.filter_input.setObjectName("scopeFilter")
        self.filter_input.setPlaceholderText("搜索书卷名称…")
        self.filter_input.textChanged.connect(self._filter_books)
        root.addWidget(self.filter_input)
        columns = QHBoxLayout()
        columns.setSpacing(16)
        for title, category in (("旧约", "old"), ("新约", "new")):
            box = QVBoxLayout()
            label = QLabel(title)
            label.setObjectName("scopeTitle")
            box.addWidget(label)
            actions = QHBoxLayout()
            actions.setSpacing(8)
            select_all = QPushButton("全选")
            clear = QPushButton("清空")
            select_all.setObjectName("scopeAction")
            clear.setObjectName("scopeAction")
            select_all.setFixedHeight(32)
            clear.setFixedHeight(32)
            select_all.setMinimumWidth(72)
            clear.setMinimumWidth(72)
            select_all.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            clear.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            select_all.clicked.connect(lambda _, c=category: self._set_all(c, True))
            clear.clicked.connect(lambda _, c=category: self._set_all(c, False))
            actions.addWidget(select_all)
            actions.addWidget(clear)
            actions.addStretch(1)
            box.addLayout(actions)
            lst = QListWidget()
            lst.setObjectName("scopeBookList")
            lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            lst.itemClicked.connect(self._toggle_book)
            self._lists[category] = lst
            for book, short in self.db.get_books(category):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, book)
                item.setData(Qt.ItemDataRole.UserRole + 1, short)
                self._set_item_checked(item, book in self.selected)
                lst.addItem(item)
            box.addWidget(lst, 1)
            columns.addLayout(box, 1)
        root.addLayout(columns, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _set_item_checked(item, checked):
        item.setData(Qt.ItemDataRole.UserRole + 2, bool(checked))
        book = str(item.data(Qt.ItemDataRole.UserRole) or "")
        short = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
        item.setText(f"{book}  ·  {short}")
        item.setData(Qt.ItemDataRole.UserRole + 3, bool(checked))

    def _toggle_book(self, item):
        checked = not bool(item.data(Qt.ItemDataRole.UserRole + 2))
        self._set_item_checked(item, checked)

    def _set_all(self, category, checked):
        for i in range(self._lists[category].count()):
            self._set_item_checked(self._lists[category].item(i), checked)

    def _filter_books(self, text):
        q = text.strip().lower()
        for lst in self._lists.values():
            for i in range(lst.count()):
                item = lst.item(i)
                book = str(item.data(Qt.ItemDataRole.UserRole) or "")
                item.setHidden(bool(q) and q not in book.lower())

    def selected_books(self):
        result = set()
        for lst in self._lists.values():
            for i in range(lst.count()):
                item = lst.item(i)
                if bool(item.data(Qt.ItemDataRole.UserRole + 2)):
                    result.add(str(item.data(Qt.ItemDataRole.UserRole)))
        return result

    def _apply_style(self):
        t = theme_tokens(self.theme)
        self.setStyleSheet(f"""
        QDialog#scriptureScopeDialog {{ background:{t['surface_raised']}; color:{t['text']}; }}
        QLabel#scopeDialogTitle {{ color:{t['text']}; font-size:18px; font-weight:600; }}
        QLabel#scopeDialogHint {{ color:{t['text_muted']}; font-size:12px; }}
        QLineEdit#scopeFilter {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px; padding:0 12px; min-height:40px; }}
        QLineEdit#scopeFilter:focus {{ border:1px solid {t['focus_ring']}; }}
        QLabel#scopeTitle {{ color:{t['text']}; font-size:14px; font-weight:600; }}
        QPushButton#scopeAction {{ background:{t['control']}; color:{t['text_muted']}; border:1px solid {t['border']}; border-radius:7px; padding:0 12px; min-width:72px; min-height:32px; }}
        QPushButton#scopeAction:hover {{ background:{t['control_hover']}; color:{t['text']}; border-color:{t['border_strong']}; }}
        QListWidget#scopeBookList {{ background:{t['surface_sunken']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px; padding:5px; outline:none; }}
        QListWidget#scopeBookList::item {{ background:{t['control']}; min-height:38px; padding:6px 10px; margin:2px 0; border:1px solid {t['border']}; border-radius:7px; color:{t['text']}; font-size:13px; }}
        QListWidget#scopeBookList::item:hover {{ background:{t['control_hover']}; border-color:{t['border_strong']}; }}
        QListWidget#scopeBookList::item:selected {{ background:{t['accent_soft']}; color:{t['accent_text']}; border:1px solid {t['accent']}; }}
        QDialogButtonBox QPushButton {{ min-width:80px; min-height:34px; border-radius:8px; background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; padding:0 14px; }}
        QDialogButtonBox QPushButton:hover {{ background:{t['control_hover']}; }}
        QDialogButtonBox QPushButton[text="确定"] {{ background:{t['accent']}; color:#FFFFFF; border-color:{t['accent']}; font-weight:600; }}
        QDialogButtonBox QPushButton[text="确定"]:hover {{ background:{t['accent_hover']}; }}
        """)
        self._refresh_selection_style()

    def _refresh_selection_style(self):
        """用整行高亮表达选中状态，不显示圈/对勾。"""
        for lst in self._lists.values():
            for i in range(lst.count()):
                item = lst.item(i)
                item.setSelected(False)
                if bool(item.data(Qt.ItemDataRole.UserRole + 2)):
                    item.setSelected(True)


class ScriptureResultWidget(QFrame):
    activated = pyqtSignal(object)
    copy_requested = pyqtSignal(object)
    project_requested = pyqtSignal(object)

    def __init__(self, result, keywords, theme="dark", parent=None):
        super().__init__(parent)
        self.result = result
        self.keywords = keywords
        self.theme = theme
        self.setObjectName("scriptureSearchResult")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 13, 16, 13)
        root.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        title = QPushButton(f"{result['short']} {result['chapter']}:{result['verse']}")
        title.setObjectName("scriptureResultTitle")
        title.setFlat(True)
        title.setCursor(Qt.CursorShape.PointingHandCursor)
        title.clicked.connect(lambda: self.activated.emit(self.result))
        top.addWidget(title, 1)
        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("scriptureResultAction")
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self.result))
        top.addWidget(copy_btn)
        project_btn = QPushButton("投影")
        project_btn.setObjectName("scriptureResultAction")
        project_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        project_btn.clicked.connect(lambda: self.project_requested.emit(self.result))
        top.addWidget(project_btn)
        root.addLayout(top)
        text = QLabel(self._highlight(result["text"], keywords, theme))
        text.setObjectName("scriptureResultText")
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        root.addWidget(text)

    @staticmethod
    def _highlight(text, keywords, theme):
        t = theme_tokens(theme)
        safe = html.escape(str(text))
        terms = sorted({str(k).strip() for k in keywords if str(k).strip()}, key=len, reverse=True)
        for term in terms:
            safe_term = html.escape(term)
            safe = safe.replace(
                safe_term,
                f'<span style="background-color:{t["accent"]}; color:#FFFFFF; font-weight:700; padding:1px 2px;">{safe_term}</span>'
            )
        return safe


class ScriptureSearchWidget(QWidget):
    """Bible Pro 独立经文全文搜索面板。"""
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
        self.search_input.returnPressed.connect(self.search)
        search_row.addWidget(self.search_input, 1)
        search_btn = QPushButton("搜索")
        search_btn.setObjectName("scriptureSearchButton")
        search_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        search_btn.clicked.connect(self.search)
        search_row.addWidget(search_btn)
        condition.addLayout(search_row)

        options = QHBoxLayout()
        options.setSpacing(10)
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

        self.history_list = QListWidget()
        self.history_list.setObjectName("scriptureHistoryList")
        self.history_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.setFixedHeight(10 * 40 + 6)
        condition.addWidget(self.history_list)
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
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
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
        self.total, self.results = search_scripture(
            self.db, keywords, self.fuzzy_radio.isChecked(), self.all_radio.isChecked(),
            self.selected_books or None, self.PAGE_SIZE, 0,
        )
        self._render_results(keywords)
        self._toggle_conditions_closed()

    def _render_results(self, keywords):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not self.results:
            empty_box = QWidget()
            empty_layout = QVBoxLayout(empty_box)
            empty_layout.setContentsMargins(20, 50, 20, 50)
            empty_icon = QLabel("⌕")
            empty_icon.setObjectName("scriptureEmptyIcon")
            empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_title = QLabel("没有找到相关经文")
            empty_title.setObjectName("scriptureEmptyTitle")
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_hint = QLabel("换一个关键词试试，或扩大搜索范围")
            empty_hint.setObjectName("scriptureEmptyHint")
            empty_layout.addWidget(empty_icon)
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_hint)
            self.result_layout.addWidget(empty_box)
        else:
            for result in self.results:
                card = ScriptureResultWidget(result, keywords, self.theme)
                card.activated.connect(self._activate_result)
                card.copy_requested.connect(self._copy_result)
                card.project_requested.connect(self.result_project_requested.emit)
                self.result_layout.addWidget(card)
            self.result_layout.addStretch(1)
        self.result_header.setText(f"搜索结果  ·  找到 {self.total} 条")
        self.result_hint.setText("点击经文标题可定位")
        self._update_pager()
        self.result_scroll.verticalScrollBar().setValue(0)

    def _toggle_conditions_closed(self):
        self.condition_box.setVisible(False)
        self.condition_toggle.setText("搜索条件  ▼")

    def _activate_result(self, result):
        self.result_activated.emit(result)

    def _copy_result(self, result):
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(f"{result['book']} {result['chapter']}:{result['verse']} {result['text']}")

    def load_page(self, page):
        keywords = self._keywords()
        if not keywords:
            return
        max_page = max(1, (self.total + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self.page = max(0, min(page, max_page - 1))
        _, self.results = search_scripture(
            self.db, keywords, self.fuzzy_radio.isChecked(), self.all_radio.isChecked(),
            self.selected_books or None, self.PAGE_SIZE, self.page * self.PAGE_SIZE,
        )
        self._render_results(keywords)

    def _prev_page(self):
        self.load_page(self.page - 1)

    def _next_page(self):
        self.load_page(self.page + 1)

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
        self.history_list.clear()
        self.clear_history_btn.setEnabled(bool(self.history))
        for text in self.history[:10]:
            item = QListWidgetItem()
            item.setSizeHint(self._history_row_size())
            self.history_list.addItem(item)
            row = QWidget()
            row.setObjectName("scriptureHistoryRow")
            layout = QHBoxLayout(row)
            layout.setContentsMargins(10, 2, 6, 2)
            layout.setSpacing(6)
            use_btn = QPushButton(text)
            use_btn.setObjectName("historyUseButton")
            use_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            use_btn.setToolTip("使用此搜索")
            use_btn.clicked.connect(lambda _, value=text: self._use_history_text(value))
            layout.addWidget(use_btn, 1)
            delete_btn = QPushButton("×")
            delete_btn.setObjectName("historyDeleteButton")
            delete_btn.setFixedSize(26, 26)
            delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_btn.setToolTip("删除此搜索")
            delete_btn.clicked.connect(lambda _, value=text: self._delete_history(value))
            layout.addWidget(delete_btn)
            self.history_list.setItemWidget(item, row)

    @staticmethod
    def _history_row_size():
        from PyQt6.QtCore import QSize
        return QSize(0, 40)

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

    def _use_history(self, item):
        self._use_history_text(item.text())

    def _apply_style(self):
        t = theme_tokens(self.theme)
        self.setStyleSheet(f"""
        QWidget#scriptureSearchPanel {{ background:{t['surface_raised']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:14px; }}
        QLabel#scriptureSearchTitle {{ color:{t['text']}; font-size:19px; font-weight:600; }}
        QLabel#scriptureSearchSubtitle {{ color:{t['text_muted']}; font-size:12px; }}
        QPushButton#scriptureSearchClose {{ background:transparent; color:{t['text_muted']}; border:none; border-radius:9px; font-size:22px; }}
        QPushButton#scriptureSearchClose:hover {{ background:{t['control_hover']}; color:{t['text']}; }}
        QPushButton#searchConditionToggle {{ background:transparent; color:{t['text_muted']}; border:none; padding:2px 4px; text-align:left; font-size:12px; font-weight:600; }}
        QPushButton#searchConditionToggle:hover {{ color:{t['accent']}; }}
        QWidget#scriptureConditionBox {{ background:{t['surface_sunken']}; border:1px solid {t['border']}; border-radius:11px; }}
        QLineEdit#scriptureSearchInput {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px; padding:0 13px; min-height:44px; font-size:14px; selection-background-color:{t['accent']}; selection-color:#FFFFFF; }}
        QLineEdit#scriptureSearchInput:focus {{ border:1px solid {t['focus_ring']}; }}
        QPushButton#scriptureSearchButton {{ background:{t['accent']}; color:#FFFFFF; border:1px solid {t['accent']}; border-radius:9px; min-width:82px; min-height:44px; padding:0 18px; font-size:14px; font-weight:600; }}
        QPushButton#scriptureSearchButton:hover {{ background:{t['accent_hover']}; }}
        QPushButton#scriptureSearchButton:pressed {{ background:{t['accent_pressed']}; }}
        QLabel#conditionLabel {{ color:{t['text_muted']}; font-size:12px; }}
        QRadioButton#searchOption {{ background:{t['control']}; color:{t['text_muted']}; border:1px solid {t['border']}; border-radius:8px; padding:6px 10px; spacing:0; font-size:12px; min-height:18px; }}
        QRadioButton#searchOption:hover {{ background:{t['control_hover']}; color:{t['text']}; border-color:{t['border_strong']}; }}
        QRadioButton#searchOption:checked {{ background:{t['accent_soft']}; color:{t['accent_text']}; border-color:{t['accent']}; font-weight:600; }}
        QRadioButton#searchOption::indicator {{ width:0px; height:0px; margin:0; padding:0; border:none; }}
        QPushButton#scriptureScopeButton {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; min-height:34px; padding:0 12px; text-align:left; }}
        QPushButton#scriptureScopeButton:hover {{ background:{t['control_hover']}; border-color:{t['border_strong']}; }}
        QLabel#searchHistoryLabel {{ color:{t['text_faint']}; font-size:11px; font-weight:600; padding-top:2px; }}
        QPushButton#historyClearButton {{ background:transparent; color:{t['text_muted']}; border:none; padding:2px 4px; font-size:11px; }}
        QPushButton#historyClearButton:hover:enabled {{ color:{t['accent']}; }}
        QPushButton#historyClearButton:disabled {{ color:{t['text_faint']}; }}
        QListWidget#scriptureHistoryList {{ background:{t['surface_sunken']}; border:1px solid {t['border']}; border-radius:9px; color:{t['text']}; outline:none; padding:4px; }}
        QListWidget#scriptureHistoryList::item {{ background:{t['control']}; border:1px solid {t['border']}; border-radius:7px; margin:2px 0; padding:0; }}
        QListWidget#scriptureHistoryList::item:hover {{ background:{t['control_hover']}; border-color:{t['border_strong']}; }}
        QWidget#scriptureHistoryRow {{ background:transparent; }}
        QPushButton#historyUseButton {{ background:transparent; color:{t['text']}; border:none; padding:5px 0; text-align:left; font-size:12px; min-height:30px; }}
        QPushButton#historyUseButton:hover {{ color:{t['accent']}; }}
        QPushButton#historyDeleteButton {{ background:transparent; color:{t['text_faint']}; border:none; border-radius:7px; font-size:15px; padding:0; }}
        QPushButton#historyDeleteButton:hover {{ background:{t['control_hover']}; color:{t['text']}; }}
        QLabel#scriptureResultHeader {{ color:{t['text']}; font-size:13px; font-weight:600; }}
        QLabel#scriptureResultHint {{ color:{t['text_faint']}; font-size:11px; }}
        QScrollArea#scriptureResultScroll {{ background:{t['surface_raised']}; border:none; }}
        QScrollArea#scriptureResultScroll QWidget {{ background:transparent; }}
        QWidget#scriptureResultContainer {{ background:transparent; }}
        QFrame#scriptureSearchResult {{ background:{t['surface']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:10px; }}
        QFrame#scriptureSearchResult:hover {{ background:{t['control']}; border-color:{t['border_strong']}; }}
        QPushButton#scriptureResultTitle {{ background:transparent; color:{t['text']}; border:none; padding:0; text-align:left; font-size:15px; font-weight:600; }}
        QPushButton#scriptureResultTitle:hover {{ color:{t['accent']}; }}
        QLabel#scriptureResultText {{ color:{t['text']}; font-size:14px; }}
        QPushButton#scriptureResultAction {{ background:transparent; color:{t['text_muted']}; border:1px solid {t['border']}; border-radius:7px; min-width:44px; min-height:28px; padding:0 8px; font-size:11px; }}
        QPushButton#scriptureResultAction:hover {{ background:{t['accent_soft']}; color:{t['accent_text']}; border-color:{t['accent']}; }}
        QPushButton#scripturePagerButton {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; font-size:20px; }}
        QPushButton#scripturePagerButton:hover:enabled {{ background:{t['control_hover']}; border-color:{t['border_strong']}; }}
        QPushButton#scripturePagerButton:disabled {{ background:{t['surface_sunken']}; color:{t['text_faint']}; border-color:{t['border']}; }}
        QLabel#scripturePageLabel {{ color:{t['text_muted']}; font-size:12px; }}
        QLabel#scriptureEmptyIcon {{ color:{t['text_faint']}; font-size:38px; }}
        QLabel#scriptureEmptyTitle {{ color:{t['text']}; font-size:16px; font-weight:600; }}
        QLabel#scriptureEmptyHint {{ color:{t['text_muted']}; font-size:12px; }}
        QScrollBar:vertical {{ background:transparent; width:8px; margin:2px; }}
        QScrollBar::handle:vertical {{ background:{t['scroll']}; border-radius:4px; min-height:36px; }}
        QScrollBar::handle:vertical:hover {{ background:{t['scroll_hover']}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)

    def apply_theme(self, theme):
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.setProperty("theme", self.theme)
        self._apply_style()
        self.style().unpolish(self)
        self.style().polish(self)
        if self.results:
            self._render_results(self._keywords())