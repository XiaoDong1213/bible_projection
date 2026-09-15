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
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


_SPACE_RE = re.compile(r"[\s，,、]+")

# 相近：字序匹配、中间可夹字；一致：整段连续出现
MODE_GAP = "gap"
MODE_CONTIGUOUS = "contiguous"


def split_search_terms(text):
    """空格 / 逗号分隔为多个条件；每段去掉通配符。"""
    parts = _SPACE_RE.split(str(text or "").strip())
    terms = []
    for part in parts:
        term = "".join(ch for ch in part if ch not in "%_")
        if term:
            terms.append(term)
    return terms


def normalize_search_query(text):
    """合并所有条件字（用于空查询判断与高亮）。"""
    return "".join(split_search_terms(text))


def gap_like_pattern(term):
    """爱永不止息 → %爱%永%不%止%息%，中间允许夹字。"""
    chars = list(str(term or ""))
    chars = [ch for ch in chars if ch not in "%_"]
    if not chars:
        return ""
    return "%" + "%".join(chars) + "%"


def contiguous_like_pattern(term):
    """爱永不止息 → %爱永不止息%，必须连着出现。"""
    value = "".join(ch for ch in str(term or "") if ch not in "%_")
    if not value:
        return ""
    return f"%{value}%"


def search_pattern(term, mode=MODE_GAP):
    if mode == MODE_CONTIGUOUS:
        return contiguous_like_pattern(term)
    return gap_like_pattern(term)


def search_scripture(db, query, books=None, limit=10, offset=0, mode=MODE_GAP, **_legacy):
    """经文搜索。mode=gap 相近；mode=contiguous 一致。空格分隔的多段为 AND。"""
    if "fuzzy" in _legacy and not _legacy.get("fuzzy", True):
        mode = MODE_CONTIGUOUS

    terms = split_search_terms(query)
    patterns = [search_pattern(term, mode) for term in terms]
    patterns = [p for p in patterns if p]
    if not patterns:
        return 0, []

    table = db._quote(db.verse_table)
    book_col = db._quote(db.book_col)
    chapter_col = db._quote(db.chapter_col)
    verse_col = db._quote(db.verse_col)
    text_col = db._quote(db.text_col)

    conditions = [f"{text_col} LIKE ?" for _ in patterns]
    params = list(patterns)
    where = f"({' AND '.join(conditions)})"
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
