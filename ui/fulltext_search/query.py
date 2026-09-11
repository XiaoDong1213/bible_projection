import html
import re

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.themes import theme_tokens


_SPACE_RE = re.compile(r"[\s，,、]+")


def normalize_search_query(text):
    """去掉空白与常见分隔符，得到可夹字匹配用的连续字符。"""
    value = _SPACE_RE.sub("", str(text or "").strip())
    # LIKE 通配符不当作搜索字
    return "".join(ch for ch in value if ch not in "%_")


def gap_like_pattern(text):
    """爱永不止息 → %爱%永%不%止%息%，中间允许夹字。"""
    chars = list(normalize_search_query(text))
    if not chars:
        return ""
    return "%" + "%".join(chars) + "%"


def search_scripture(db, query, books=None, limit=10, offset=0, **_legacy):
    """可夹字模糊搜索：输入「爱永不止息」可命中「爱是永不止息」。"""
    pattern = gap_like_pattern(query)
    if not pattern:
        return 0, []

    table = db._quote(db.verse_table)
    book_col = db._quote(db.book_col)
    chapter_col = db._quote(db.chapter_col)
    verse_col = db._quote(db.verse_col)
    text_col = db._quote(db.text_col)

    where = f"{text_col} LIKE ?"
    params = [pattern]
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
    """选择经文搜索范围（chip 点选，无复选框）。"""

    CHIP_COLS = 2

    def __init__(self, db, selected=None, parent=None, theme="dark"):
        super().__init__(parent)
        self.db = db
        self.selected = set(selected or [])
        self.theme = theme if theme in ("dark", "light") else "dark"
        self._chips = {}
        self._chip_meta = {}
        self.setObjectName("scriptureScopeDialog")
        self.setWindowTitle("选择搜索范围")
        self.setMinimumSize(820, 600)
        self.resize(880, 640)
        self._build_ui()
        self._apply_style()
        self._update_count()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 18)
        root.setSpacing(12)

        heading = QLabel("选择搜索范围")
        heading.setObjectName("scopeDialogTitle")
        root.addWidget(heading)

        self.count_label = QLabel("")
        self.count_label.setObjectName("scopeDialogHint")
        root.addWidget(self.count_label)

        presets = QHBoxLayout()
        presets.setSpacing(8)
        for text, handler in (
            ("全选", self._select_all),
            ("只旧约", lambda: self._select_category("old")),
            ("只新约", lambda: self._select_category("new")),
            ("清空", self._clear_all),
        ):
            btn = QPushButton(text)
            btn.setObjectName("scopeAction")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.clicked.connect(handler)
            presets.addWidget(btn)
        presets.addStretch(1)
        root.addLayout(presets)

        self.filter_input = QLineEdit()
        self.filter_input.setObjectName("scopeFilter")
        self.filter_input.setPlaceholderText("筛选书卷名称…")
        self.filter_input.textChanged.connect(self._filter_books)
        root.addWidget(self.filter_input)

        columns = QHBoxLayout()
        columns.setSpacing(16)
        for title, category in (("旧约", "old"), ("新约", "new")):
            columns.addWidget(self._build_category_column(title, category), 1)
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

    def _build_category_column(self, title, category):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header = QHBoxLayout()
        label = QLabel(title)
        label.setObjectName("scopeTitle")
        header.addWidget(label, 1)
        select_all = QPushButton("全选")
        clear = QPushButton("清空")
        select_all.setObjectName("scopeAction")
        clear.setObjectName("scopeAction")
        select_all.setFixedHeight(28)
        clear.setFixedHeight(28)
        select_all.setCursor(Qt.CursorShape.PointingHandCursor)
        clear.setCursor(Qt.CursorShape.PointingHandCursor)
        select_all.clicked.connect(lambda: self._set_category(category, True))
        clear.clicked.connect(lambda: self._set_category(category, False))
        header.addWidget(select_all)
        header.addWidget(clear)
        layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setObjectName("scopeChipScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        container.setObjectName("scopeChipContainer")
        grid = QGridLayout(container)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(10)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        for i, (book, short) in enumerate(self.db.get_books(category)):
            chip = QPushButton(book)
            chip.setObjectName("scopeBookChip")
            chip.setCheckable(True)
            chip.setChecked(book in self.selected)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setToolTip(f"{book}（{short}）" if short else book)
            chip.setFixedHeight(36)
            chip.setMinimumWidth(140)
            chip.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            chip.toggled.connect(lambda _checked, b=book: self._on_chip_toggled(b))
            self._chips[book] = chip
            self._chip_meta[book] = (category, short or "")
            grid.addWidget(chip, i // self.CHIP_COLS, i % self.CHIP_COLS)

        scroll.setWidget(container)

        panel = QFrame()
        panel.setObjectName("scopeChipPanel")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)
        panel_layout.addWidget(scroll)
        layout.addWidget(panel, 1)
        return box

    def _on_chip_toggled(self, book):
        chip = self._chips.get(book)
        if chip is None:
            return
        if chip.isChecked():
            self.selected.add(book)
        else:
            self.selected.discard(book)
        self._update_count()

    def _set_category(self, category, checked):
        for book, chip in self._chips.items():
            meta = self._chip_meta.get(book)
            if not meta or meta[0] != category:
                continue
            chip.blockSignals(True)
            chip.setChecked(checked)
            chip.blockSignals(False)
            if checked:
                self.selected.add(book)
            else:
                self.selected.discard(book)
        self._update_count()

    def _select_all(self):
        for book, chip in self._chips.items():
            chip.blockSignals(True)
            chip.setChecked(True)
            chip.blockSignals(False)
            self.selected.add(book)
        self._update_count()

    def _clear_all(self):
        for book, chip in self._chips.items():
            chip.blockSignals(True)
            chip.setChecked(False)
            chip.blockSignals(False)
        self.selected.clear()
        self._update_count()

    def _select_category(self, category):
        for book, chip in self._chips.items():
            meta = self._chip_meta.get(book)
            want = bool(meta and meta[0] == category)
            chip.blockSignals(True)
            chip.setChecked(want)
            chip.blockSignals(False)
            if want:
                self.selected.add(book)
            else:
                self.selected.discard(book)
        self._update_count()

    def _filter_books(self, text):
        q = text.strip().lower()
        for book, chip in self._chips.items():
            short = (self._chip_meta.get(book) or ("", ""))[1]
            visible = (not q) or (q in book.lower()) or (q in short.lower())
            chip.setVisible(visible)

    def _update_count(self):
        n = len(self.selected)
        total = len(self._chips)
        if n == 0 or n == total:
            self.count_label.setText(f"当前：全部书卷（共 {total} 卷）· 点选 chip 切换")
        else:
            self.count_label.setText(f"已选 {n} / {total} 卷 · 点选 chip 切换")

    def selected_books(self):
        return {book for book, chip in self._chips.items() if chip.isChecked()}

    def _apply_style(self):
        # 圆角写在全局 stylesheet（QDialog#scriptureScopeDialog …），
        # 这里不再 setStyleSheet，避免冲掉 app 样式。
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)


class ScriptureSearchDialog(QDialog):
    """经文搜索弹窗。"""

    def __init__(self, db, on_select, history=None, theme="dark", parent=None):
        super().__init__(parent)
        self.db = db
        self.on_select = on_select
        self.history = list(history or [])
        self.theme = theme if theme in ("dark", "light") else "dark"
        self.scope = None
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
        query = self.input.text().strip()
        if not normalize_search_query(query):
            self.status.setText("请输入搜索关键词")
            return
        self.page = 0
        self._load_results(query)

    def _load_results(self, query):
        self.total, self.results = search_scripture(
            self.db,
            query,
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
        self.page -= 1
        self._load_results(self.input.text())

    def _next_page(self):
        if (self.page + 1) * self.page_size >= self.total:
            return
        self.page += 1
        self._load_results(self.input.text())

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
