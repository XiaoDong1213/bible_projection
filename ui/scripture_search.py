import html

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .themes import theme_tokens


def search_scripture(db, keywords, fuzzy=True, match_all=True, books=None, limit=10, offset=0):
    """使用 SQL 分页查询经文，连续节数据库记录统一显示逻辑节号。"""
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

    total = int(
        db.conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {where}", params
        ).fetchone()[0]
    )
    select_sql = (
        f"SELECT {book_col} AS raw_book, {chapter_col} AS chapter, "
        f"{verse_col} AS verse, {text_col} AS text FROM {table} "
        f"WHERE {where} ORDER BY rowid LIMIT ? OFFSET ?"
    )
    rows = db.conn.execute(
        select_sql, params + [int(limit), int(offset)]
    ).fetchall()
    id_to_name = {
        str(v.get("id")).strip(): k
        for k, v in db.book_meta.items()
        if v.get("id") is not None
    }
    result = []
    for row in rows:
        book = id_to_name.get(
            str(row["raw_book"]).strip(), str(row["raw_book"])
        )
        chapter = int(row["chapter"])
        verse = int(row["verse"])
        label, text = db.get_verse_display_info(book, chapter, verse)
        result.append({
            "book": book,
            "short": db._short_name(book),
            "chapter": chapter,
            "verse": verse,
            "verse_label": label,
            "text": text or str(row["text"]),
        })
    return total, result


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
        # 与经文搜索面板保持一致的宽度。
        self.setFixedSize(400, 560)
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 18)
        root.setSpacing(12)

        heading = QLabel("选择搜索范围")
        heading.setObjectName("scopeDialogTitle")
        root.addWidget(heading)

        hint = QLabel("点击书卷即可选择或取消选择，选中的书卷会整行高亮。")
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
            select_all.setFixedSize(72, 32)
            clear.setFixedSize(72, 32)
            select_all.clicked.connect(lambda _, c=category: self._set_all(c, True))
            clear.clicked.connect(lambda _, c=category: self._set_all(c, False))
            actions.addWidget(select_all)
            actions.addWidget(clear)
            actions.addStretch(1)
            box.addLayout(actions)

            lst = QListWidget()
            lst.setObjectName("scopeBookList")
            lst.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            lst.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            lst.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            lst.itemClicked.connect(self._toggle_book)
            self._lists[category] = lst

            for book, short in self.db.get_books(category):
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, book)
                item.setData(Qt.ItemDataRole.UserRole + 1, short)
                lst.addItem(item)
                self._set_item_checked(item, book in self.selected)

            box.addWidget(lst, 1)
            columns.addLayout(box, 1)

        root.addLayout(columns, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确定")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _set_item_checked(item, checked):
        checked = bool(checked)
        item.setData(Qt.ItemDataRole.UserRole + 2, checked)
        book = str(item.data(Qt.ItemDataRole.UserRole) or "")
        short = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
        item.setText(f"{book}  ·  {short}")
        item.setSelected(checked)

    def _toggle_book(self, item):
        self._set_item_checked(item, item.isSelected())

    def _set_all(self, category, checked):
        for i in range(self._lists[category].count()):
            self._set_item_checked(self._lists[category].item(i), checked)

    def _filter_books(self, text):
        q = text.strip().lower()
        for lst in self._lists.values():
            for i in range(lst.count()):
                item = lst.item(i)
                book = str(item.data(Qt.ItemDataRole.UserRole) or "")
                short = str(item.data(Qt.ItemDataRole.UserRole + 1) or "")
                item.setHidden(bool(q) and q not in book.lower() and q not in short.lower())

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
        QDialog#scriptureScopeDialog {{
            background:{t['surface_raised']}; color:{t['text']};
        }}
        QLabel#scopeDialogTitle {{
            color:{t['text']}; font-size:18px; font-weight:600;
        }}
        QLabel#scopeDialogHint {{
            color:{t['text_muted']}; font-size:12px;
        }}
        QLineEdit#scopeFilter {{
            background:{t['control']}; color:{t['text']};
            border:1px solid {t['border']}; border-radius:9px;
            padding:0 12px; min-height:40px;
        }}
        QLineEdit#scopeFilter:focus {{ border:1px solid {t['focus_ring']}; }}
        QLabel#scopeTitle {{ color:{t['text']}; font-size:14px; font-weight:600; }}
        QPushButton#scopeAction {{
            background:{t['control']}; color:{t['text_muted']};
            border:1px solid {t['border']}; border-radius:7px; padding:0 12px;
        }}
        QPushButton#scopeAction:hover {{
            background:{t['control_hover']}; color:{t['text']};
            border-color:{t['border_strong']};
        }}
        QListWidget#scopeBookList {{
            background:{t['surface_sunken']}; color:{t['text']};
            border:1px solid {t['border']}; border-radius:9px;
            padding:5px; outline:none;
        }}
        QListWidget#scopeBookList::item {{
            background:{t['control']}; min-height:38px;
            padding:6px 10px; margin:2px 0;
            border:1px solid {t['border']}; border-radius:7px;
            color:{t['text']}; font-size:13px;
        }}
        QListWidget#scopeBookList::item:hover {{
            background:{t['control_hover']}; border-color:{t['border_strong']};
        }}
        QListWidget#scopeBookList::item:selected {{
            background:{t['accent']}; color:#FFFFFF;
            border:1px solid {t['accent']};
        }}
        QDialogButtonBox QPushButton {{
            min-width:84px; min-height:34px; border-radius:8px;
            background:{t['control']}; color:{t['text']}; border:1px solid {t['border']};
        }}
        QDialogButtonBox QPushButton:hover {{ background:{t['control_hover']}; }}
        """)


class ScriptureSearchDialog(QDialog):
    """经文搜索弹窗。"""

    def __init__(self, db, on_select, history=None, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self.on_select = on_select
        self.history = list(history or [])
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.scope = None
        self.fuzzy = True
        self.match_all = True
        self.page = 0
        self.page_size = 10
        self.total = 0
        self.results = []
        self._build_ui()
        self._apply_style()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(10)
        title = QLabel("经文搜索")
        title.setObjectName("searchTitle")
        root.addWidget(title)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("输入关键词，可用空格分隔多个关键词")
        self.input.returnPressed.connect(self._search)
        row.addWidget(self.input, 1)
        self.search_button = QPushButton("搜索")
        self.search_button.clicked.connect(self._search)
        row.addWidget(self.search_button)
        root.addLayout(row)
        self.status = QLabel("")
        self.status.setObjectName("searchStatus")
        root.addWidget(self.status)
        self.list = QListWidget()
        self.list.setObjectName("searchResultList")
        self.list.itemDoubleClicked.connect(self._activate_result)
        root.addWidget(self.list, 1)
        page_row = QHBoxLayout()
        self.prev_button = QPushButton("上一页")
        self.next_button = QPushButton("下一页")
        self.prev_button.clicked.connect(self._prev_page)
        self.next_button.clicked.connect(self._next_page)
        page_row.addWidget(self.prev_button)
        page_row.addWidget(self.next_button)
        root.addLayout(page_row)

    def _search(self):
        keywords = [x for x in self.input.text().split() if x]
        if not keywords:
            self.status.setText("请输入搜索关键词")
            return
        self.page = 0
        self._load_results(keywords)

    def _load_results(self, keywords):
        self.total, self.results = search_scripture(
            self.db,
            keywords,
            fuzzy=self.fuzzy,
            match_all=self.match_all,
            books=self.scope,
            limit=self.page_size,
            offset=self.page * self.page_size,
        )
        self.list.clear()
        for result in self.results:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, result)
            item.setText(
                f"{result['book']} {result['chapter']}:{result.get('verse_label', result['verse'])}\n"
                f"{result['text']}"
            )
            self.list.addItem(item)
        if self.total:
            pages = (self.total + self.page_size - 1) // self.page_size
            self.status.setText(f"共 {self.total} 条 · 第 {self.page + 1}/{pages} 页")
        else:
            self.status.setText("没有找到匹配的经文")
        self.prev_button.setEnabled(self.page > 0)
        self.next_button.setEnabled((self.page + 1) * self.page_size < self.total)

    def _activate_result(self, item):
        result = item.data(Qt.ItemDataRole.UserRole)
        if not result:
            return
        self.on_select(result)
        self.accept()

    def _prev_page(self):
        if self.page <= 0:
            return
        keywords = [x for x in self.input.text().split() if x]
        self.page -= 1
        self._load_results(keywords)

    def _next_page(self):
        if (self.page + 1) * self.page_size >= self.total:
            return
        keywords = [x for x in self.input.text().split() if x]
        self.page += 1
        self._load_results(keywords)

    def _apply_style(self):
        t = theme_tokens(self.theme)
        self.setStyleSheet(f"""
        QDialog {{ background:{t['surface_raised']}; color:{t['text']}; }}
        QLabel#searchTitle {{ color:{t['text']}; font-size:18px; font-weight:600; }}
        QLabel#searchStatus {{ color:{t['text_muted']}; font-size:12px; }}
        QLineEdit {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px; padding:0 12px; min-height:40px; }}
        QLineEdit:focus {{ border:1px solid {t['focus_ring']}; }}
        QPushButton {{ background:{t['control']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:8px; padding:0 14px; min-height:34px; }}
        QPushButton:hover {{ background:{t['control_hover']}; }}
        QListWidget#searchResultList {{ background:{t['surface_sunken']}; color:{t['text']}; border:1px solid {t['border']}; border-radius:9px; padding:6px; outline:none; }}
        QListWidget#searchResultList::item {{ color:{t['text']}; padding:10px; border-bottom:1px solid {t['border']}; }}
        QListWidget#searchResultList::item:selected {{ background:{t['accent']}; color:#FFFFFF; }}
        """)
