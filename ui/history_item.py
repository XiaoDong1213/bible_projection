# ui/history_item.py
# 历史记录项：文字 + 完整删除按钮

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal


class HistoryItemWidget(QWidget):
    deleted = pyqtSignal(int)
    clicked = pyqtSignal(int)

    def __init__(self, index, text, parent=None):
        super().__init__(parent)
        self.index = index
        self.setMinimumHeight(38)
        self.setObjectName("historyItem")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        self.label = QLabel(text)
        self.label.setObjectName("historyText")
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.label, 1)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("historyDeleteButton")
        self.delete_btn.setFixedSize(48, 28)
        self.delete_btn.setMinimumSize(48, 28)
        self.delete_btn.setMaximumSize(48, 28)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_btn.setToolTip("删除这条历史记录")
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet("""
            #historyItem {
                background: transparent;
            }
            #historyText {
                font-size: 13px;
                color: palette(text);
                background: transparent;
                padding: 0;
            }
            #historyDeleteButton {
                background: palette(base);
                color: palette(text);
                border: 1px solid palette(mid);
                border-radius: 4px;
                font-size: 12px;
                font-weight: normal;
                padding: 0;
                margin: 0;
            }
            #historyDeleteButton:hover {
                background: #E74C3C;
                color: white;
                border: 1px solid #E74C3C;
            }
            #historyDeleteButton:pressed {
                background: #C0392B;
                color: white;
            }
        """)

    def _on_delete(self):
        self.deleted.emit(self.index)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)
