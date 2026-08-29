# ui/history_item.py
# 历史记录项控件
# 功能：显示单条历史记录，右侧带删除按钮

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal


class HistoryItemWidget(QWidget):
    # 信号：删除按钮点击、条目点击
    deleted = pyqtSignal(int)   # 参数：条目索引
    clicked = pyqtSignal(int)   # 参数：条目索引

    def __init__(self, index, text, parent=None):
        """
        :param index: 条目索引
        :param text: 显示文本
        """
        super().__init__(parent)
        self.index = index

        layout = QHBoxLayout()
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(4)

        # 历史记录文本
        self.label = QLabel(text)
        self.label.setStyleSheet("color: inherit; font-size: 13px;")
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.label, 1)  # 占满剩余空间

        # 删除按钮（×）
        self.delete_btn = QPushButton("×")
        self.delete_btn.setFixedSize(18, 18)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #888;
                border: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 9px;
            }
            QPushButton:hover {
                background: #E74C3C;
                color: white;
            }
        """)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn)

        self.setLayout(layout)

    def _on_delete(self):
        """触发删除信号"""
        self.deleted.emit(self.index)

    def mousePressEvent(self, event):
        """点击整个条目触发选中信号"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)
