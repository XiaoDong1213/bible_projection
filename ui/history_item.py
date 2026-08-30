# ui/history_item.py
# 历史记录项控件：每条记录右侧都有独立“删除”按钮

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal


class HistoryItemWidget(QWidget):
    deleted = pyqtSignal(int)
    clicked = pyqtSignal(int)

    def __init__(self, index, text, parent=None):
        super().__init__(parent)
        self.index = index
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 6, 4)
        layout.setSpacing(6)

        self.label = QLabel(text)
        self.label.setStyleSheet("font-size: 13px;")
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.label, 1)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setFixedSize(42, 26)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setToolTip("删除这条历史记录")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: 1px solid #666;
                border-radius: 4px;
                font-size: 12px;
                padding: 0;
            }
            QPushButton:hover {
                background: #E74C3C;
                border-color: #E74C3C;
                color: white;
            }
        """)
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn)

    def _on_delete(self):
        self.deleted.emit(self.index)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # 点击记录主体打开记录；点击“删除”按钮不会走这里。
            child = self.childAt(event.position().toPoint())
            if child is not self.delete_btn:
                self.clicked.emit(self.index)
        super().mousePressEvent(event)
