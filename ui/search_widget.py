# ui/search_widget.py
# 经文快速搜索：支持中文书名、简称、拼音码、数字快捷输入、小键盘格式、模糊匹配

import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal


class SearchWidget(QWidget):
    search_triggered = pyqtSignal(tuple)
    close_requested = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        self.search_input = QLineEdit()
        # 界面上只展示文字示例；数字快捷格式仍可直接输入使用。
        self.search_input.setPlaceholderText("例如：创世记1:2-12  或  CSJ 1:2-12")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self.search_input)

        self.hint_label = QLabel(
            "支持模糊匹配：书名 / 简称 / 拼音码　｜　空格、:、. 可作分隔　｜　- 后回车=本章末　｜　ESC退出"
        )
        self.hint_label.setStyleSheet("color:#888;font-size:11px;padding:2px 4px;")
        layout.addWidget(self.hint_label)

        self.result_list = QListWidget()
        self.result_list.setStyleSheet("""
            QListWidget { border:1px solid #DDD; border-radius:6px;
                background:rgba(255,255,255,0.98); max-height:240px; }
            QListWidget::item { padding:7px 12px; font-size:13px; }
            QListWidget::item:selected { background:#4A90E2; color:white; }
        """)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.result_list)

        self.search_input.installEventFilter(self)
        self.result_list.installEventFilter(self)
        self.setFocusProxy(self.search_input)

    def showEvent(self, event):
        super().showEvent(event)
        self.search_input.setFocus()
        self.search_input.selectAll()
        self._on_text_changed(self.search_input.text())

    def _on_text_changed(self, text):
        self.result_list.clear()
        text = text.strip()
        if not text:
            return

        # 完整经文格式优先
        parsed = self.db.parse_reference(text)
        if parsed:
            book, chapter, start, end = parsed
            item = QListWidgetItem("▶ " + self._format_display(book, chapter, start, end))
            item.setData(Qt.ItemDataRole.UserRole, parsed)
            self.result_list.addItem(item)
            self.result_list.setCurrentRow(0)
            return

        # 未形成完整经文地址时，显示书卷文字模糊匹配结果。
        book_query = self._extract_book_query(text)
        if not book_query:
            return

        books = self.db.search_books(book_query)
        for book in books[:12]:
            # 结果只显示文字，不显示数字编号。
            item = QListWidgetItem(f"  {book}  ·  {self.db._short_name(book)}")
            item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
            self.result_list.addItem(item)
        if self.result_list.count():
            self.result_list.setCurrentRow(0)

    @staticmethod
    def _extract_book_query(text):
        # 纯数字小键盘格式由 parse_reference 处理，不显示数字候选。
        if re.fullmatch(r"\d{1,2}[.\s]+\d+[.\s]+\d+(?:[.\s]+\d+)?", text):
            return ""
        m = re.match(r"^([^0-9:：.\-]+?)(?=\d|$)", text)
        if m:
            return m.group(1).strip()
        return re.split(r"[0-9:：.\-\s]+", text, maxsplit=1)[0].strip()

    def _format_display(self, book, chapter, start, end):
        if start is None:
            return f"{book} {chapter}章（整章）"
        if end is None:
            return f"{book} {chapter}:{start}-末"
        if start == end:
            return f"{book} {chapter}:{start}"
        return f"{book} {chapter}:{start}-{end}"

    def _on_confirm(self):
        text = self.search_input.text().strip()
        parsed = self.db.parse_reference(text)

        if parsed:
            self.search_triggered.emit(parsed)
            self.close_requested.emit()
            return

        current = self.result_list.currentItem()
        if current:
            data = current.data(Qt.ItemDataRole.UserRole)
            if data:
                self.search_triggered.emit(data)
                self.close_requested.emit()
                return

        self.hint_label.setText("未找到匹配的书卷或经文格式，请检查输入")

    def _on_item_clicked(self, item):
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.search_triggered.emit(data)
            self.close_requested.emit()

    def eventFilter(self, obj, event):
        if event.type() == event.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.close_requested.emit()
                return True
            if obj in (self.search_input, self.result_list):
                if key == Qt.Key.Key_Down:
                    self._move_selection(1)
                    return True
                if key == Qt.Key.Key_Up:
                    self._move_selection(-1)
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self._on_confirm()
                    return True
        return super().eventFilter(obj, event)

    def _move_selection(self, delta):
        count = self.result_list.count()
        if count == 0:
            return
        row = self.result_list.currentRow()
        if row < 0:
            row = 0
        else:
            row = max(0, min(count - 1, row + delta))
        self.result_list.setCurrentRow(row)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            return
        super().keyPressEvent(event)
