# ui/search_widget.py
# 搜索弹窗控件
# 功能：回车呼出，简拼搜索，实时提示，回车确认

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt, pyqtSignal


class SearchWidget(QWidget):
    # 信号：确认搜索、请求关闭
    search_triggered = pyqtSignal(tuple)   # 参数：(书卷, 章, 起始节, 结束节)
    close_requested = pyqtSignal()

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db

        # 无边框弹窗样式
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Popup)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # 搜索输入框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入: 约 3:16 或 创 1 或 诗篇 23:1-")
        self.search_input.textChanged.connect(self._on_text_changed)
        self.search_input.returnPressed.connect(self._on_confirm)
        layout.addWidget(self.search_input)

        # 格式提示
        self.hint_label = QLabel("格式: 书卷 章:节  |  空格/冒号/点号 均可分隔")
        self.hint_label.setStyleSheet("color: #888; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(self.hint_label)

        # 结果列表
        self.result_list = QListWidget()
        self.result_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #DDD;
                border-radius: 6px;
                background: rgba(255,255,255,0.98);
                max-height: 200px;
            }
            QListWidget::item {
                padding: 7px 12px;
                font-size: 13px;
            }
            QListWidget::item:selected {
                background: #4A90E2;
                color: white;
            }
        """)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.result_list)

        self.setLayout(layout)
        self.search_input.setFocus()

    def _on_text_changed(self, text):
        """输入变化时实时更新搜索建议"""
        self.result_list.clear()
        if not text.strip():
            return

        # 1. 完整解析结果（最优先）
        parsed = self.db.parse_reference(text)
        if parsed:
            book, chapter, start, end = parsed
            display = self._format_display(book, chapter, start, end)
            item = QListWidgetItem(f"▶ {display}")
            item.setData(Qt.ItemDataRole.UserRole, parsed)
            self.result_list.addItem(item)

        # 2. 书卷匹配建议
        parts = text.split()
        if parts:
            books = self.db.search_books(parts[0])
            for book in books[:8]:
                item = QListWidgetItem(f"  {book}")
                item.setData(Qt.ItemDataRole.UserRole, (book, 1, None, None))
                self.result_list.addItem(item)

    def _format_display(self, book, chapter, start, end):
        """格式化显示文本"""
        if start is None:
            return f"{book} {chapter}章（整章）"
        elif end is None:
            return f"{book} {chapter}:{start}-末"
        elif start == end:
            return f"{book} {chapter}:{start}"
        else:
            return f"{book} {chapter}:{start}-{end}"

    def _on_confirm(self):
        """回车确认搜索"""
        if self.result_list.count() > 0:
            current = self.result_list.currentItem()
            if current:
                data = current.data(Qt.ItemDataRole.UserRole)
                self.search_triggered.emit(data)
            else:
                # 没有选中项就解析输入文本
                parsed = self.db.parse_reference(self.search_input.text())
                if parsed:
                    self.search_triggered.emit(parsed)
        else:
            parsed = self.db.parse_reference(self.search_input.text())
            if parsed:
                self.search_triggered.emit(parsed)

        self.close_requested.emit()

    def _on_item_clicked(self, item):
        """点击结果项"""
        data = item.data(Qt.ItemDataRole.UserRole)
        self.search_triggered.emit(data)
        self.close_requested.emit()

    def keyPressEvent(self, event):
        """键盘控制：上下键选结果，ESC关闭"""
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
        elif event.key() == Qt.Key.Key_Down:
            if self.result_list.count() > 0:
                current = self.result_list.currentRow()
                self.result_list.setCurrentRow(min(current + 1, self.result_list.count() - 1))
        elif event.key() == Qt.Key.Key_Up:
            current = self.result_list.currentRow()
            if current > 0:
                self.result_list.setCurrentRow(current - 1)
        else:
            super().keyPressEvent(event)
