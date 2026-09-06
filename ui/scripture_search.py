import html
import sqlite3

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QRadioButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)


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

    params = []
    conditions = []
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
        values = []
        for book in books:
            values.append(db.book_meta.get(book, {}).get("id", book))
        placeholders = ",".join("?" for _ in values)
        where += f" AND {book_col} IN ({placeholders})"
        params.extend(values)

    count_sql = f"SELECT COUNT(*) FROM {table} WHERE {where}"
    total = int(db.conn.execute(count_sql, params).fetchone()[0])

    select_sql = (
        f"SELECT {book_col} AS raw_book, {chapter_col} AS chapter, "
        f"{verse_col} AS verse, {text_col} AS text "
        f"FROM {table} WHERE {where} "
        f"ORDER BY rowid LIMIT ? OFFSET ?"
    )
    rows = db.conn.execute(select_sql, params + [int(limit), int(offset)]).fetchall()
    id_to_name = {str(v.get("id")).strip(): k for k, v in db.book_meta.items() if v.get("id") is not None}
    results = []
    for row in rows:
        raw_book = str(row["raw_book"])
        book = id_to_name.get(raw_book.strip(), raw_book)
        results.append({
            "book": book,
            "chapter": int(row["chapter"]),
            "verse": int(row["verse"]),
            "text": str(row["text"]),
        })
    return total, results


class BookScopeDialog(QDialog):
    """选择经文搜索范围。"""

    def __init__(self, db, selected=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected = set(selected or [])
        self.setWindowTitle("选择搜索范围")
        self.setFixedSize(640, 560)
        self._lists = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 14)
        root.setSpacing(10)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("搜索书卷")
        self.filter_input.textChanged.connect(self._filter_books)
        root.addWidget(self.filter_input)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        for title, category in (("旧约", "old"), ("新约", "new")):
            box = QVBoxLayout()
            label = QLabel(title)
            label.setObjectName("scopeTitle")
            box.addWidget(label)
            actions = QHBoxLayout()
            select_all = QPushButton("全选")
            clear = QPushButton("清空")
            select_all.clicked.connect(lambda _, c=category: self._set_all(c, True))
            clear.clicked.connect(lambda _, c=category: self._set_all(c, False))
            actions.addWidget(select_all)
            actions.addWidget(clear)
            box.addLayout(actions)
            lst = QListWidget()
            lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)
            self._lists[category] = lst
            for book, short in self.db.get_books(category):
                item = QListWidgetItem(f"{book}  ({short})")
                item.setData(Qt.ItemDataRole.UserRole, book)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if book in self.selected else Qt.CheckState.Unchecked)
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

    def _set_all(self, category, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._lists[category].count()):
            self._lists[category].item(i).setCheckState(state)

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
                if item.checkState() == Qt.CheckState.Checked:
                    result.add(str(item.data(Qt.ItemDataRole.UserRole)))
        return result


class ScriptureResultWidget(QFrame):
    activated = pyqtSignal(object)
    copy_requested = pyqtSignal(object)
    project_requested = pyqtSignal(object)

    def __init__(self, result, keywords, parent=None):
        super().__init__(parent)
        self.result = result
        self.setObjectName("scriptureSearchResult")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)
        top = QHBoxLayout()
        title = QPushButton(f"{result['book']} {result['chapter']}:{result['verse']}")
        title.setObjectName("scriptureResultTitle")
        title.setFlat(True)
        title.setCursor(Qt.CursorShape.PointingHandCursor)
        title.clicked.connect(lambda: self.activated.emit(self.result))
        top.addWidget(title, 1)
        copy_btn = QPushButton("复制")
        copy_btn.setObjectName("scriptureResultAction")
        copy_btn.clicked.connect(lambda: self.copy_requested.emit(self.result))
        top.addWidget(copy_btn)
        project_btn = QPushButton("投影")
        project_btn.setObjectName("scriptureResultAction")
        project_btn.clicked.connect(lambda: self.project_requested.emit(self.result))
        top.addWidget(project_btn)
        root.addLayout(top)
        text = QLabel(self._highlight(result["text"], keywords))
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setWordWrap(True)
        root.addWidget(text)

    @staticmethod
    def _highlight(text, keywords):
        safe = html.escape(str(text))
        terms = sorted({str(k).strip() for k in keywords if str(k).strip()}, key=len, reverse=True)
        for term in terms:
            safe_term = html.escape(term)
            safe = safe.replace(safe_term, f"<mark>{safe_term}</mark>")
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
        self.theme = theme
        self.page = 0
        self.total = 0
        self.results = []
        self.selected_books = set()
        self.history = config.load_scripture_search_history() if config else []
        self.setObjectName("scriptureSearchPanel")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setFixedWidth(430)
        self._build_ui()
        self._update_scope_text()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("经文搜索")
        title.setObjectName("scriptureSearchTitle")
        header.addWidget(title, 1)
        close = QPushButton("×")
        close.setFixedSize(30, 30)
        close.clicked.connect(self.close_requested.emit)
        header.addWidget(close)
        root.addLayout(header)
        self.condition_toggle = QPushButton("搜索条件  ▲")
        self.condition_toggle.setObjectName("searchConditionToggle")
        self.condition_toggle.setFlat(True)
        self.condition_toggle.clicked.connect(self._toggle_conditions)
        root.addWidget(self.condition_toggle)

        self.condition_box = QWidget()
        condition = QVBoxLayout(self.condition_box)
        condition.setContentsMargins(0, 0, 0, 0)
        condition.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入经文关键词")
        self.search_input.returnPressed.connect(self.search)
        condition.addWidget(self.search_input)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("匹配方式"))
        self.fuzzy_radio = QRadioButton("模糊")
        self.exact_radio = QRadioButton("精确")
        self.fuzzy_radio.setChecked(True)
        mode_row.addWidget(self.fuzzy_radio)
        mode_row.addWidget(self.exact_radio)
        mode_row.addStretch(1)
        condition.addLayout(mode_row)
        keyword_row = QHBoxLayout()
        keyword_row.addWidget(QLabel("多关键词"))
        self.all_radio = QRadioButton("同时包含")
        self.any_radio = QRadioButton("任意包含")
        self.all_radio.setChecked(True)
        keyword_row.addWidget(self.all_radio)
        keyword_row.addWidget(self.any_radio)
        keyword_row.addStretch(1)
        condition.addLayout(keyword_row)
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("搜索范围"))
        self.scope_btn = QPushButton("全部书卷")
        self.scope_btn.clicked.connect(self._choose_scope)
        scope_row.addWidget(self.scope_btn, 1)
        condition.addLayout(scope_row)
        search_btn = QPushButton("搜索")
        search_btn.setObjectName("scriptureSearchButton")
        search_btn.clicked.connect(self.search)
        condition.addWidget(search_btn)
        history_label = QLabel("最近搜索")
        history_label.setObjectName("searchHistoryLabel")
        condition.addWidget(history_label)
        self.history_list = QListWidget()
        self.history_list.setMaximumHeight(92)
        self.history_list.itemClicked.connect(self._use_history)
        condition.addWidget(self.history_list)
        self._refresh_history()
        root.addWidget(self.condition_box)

        self.result_header = QLabel("搜索结果")
        self.result_header.setObjectName("scriptureResultHeader")
        root.addWidget(self.result_header)
        self.result_scroll = QScrollArea()
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.result_container = QWidget()
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setContentsMargins(0, 0, 0, 0)
        self.result_layout.setSpacing(8)
        self.result_scroll.setWidget(self.result_container)
        root.addWidget(self.result_scroll, 1)
        pager = QHBoxLayout()
        self.prev_btn = QPushButton("‹")
        self.next_btn = QPushButton("›")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        pager.addWidget(self.prev_btn)
        self.page_label = QLabel("第 0 / 0 页")
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
        dialog = BookScopeDialog(self.db, self.selected_books, self)
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
            empty = QLabel("没有找到相关经文\n\n请尝试更换关键词或扩大搜索范围")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            self.result_layout.addWidget(empty)
        else:
            for result in self.results:
                card = ScriptureResultWidget(result, keywords)
                card.activated.connect(self._activate_result)
                card.copy_requested.connect(self._copy_result)
                card.project_requested.connect(self.result_project_requested.emit)
                self.result_layout.addWidget(card)
            self.result_layout.addStretch(1)
        self.result_header.setText(f"搜索结果  ·  找到 {self.total} 条")
        self._update_pager()

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
        for text in self.history:
            self.history_list.addItem(text)

    def _use_history(self, item):
        self.search_input.setText(item.text())
        self.search()

    def apply_theme(self, theme):
        self.theme = theme
        self.setProperty("theme", theme)
        self.style().unpolish(self)
        self.style().polish(self)
