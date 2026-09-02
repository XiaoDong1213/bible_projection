from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal


class HistoryItemWidget(QWidget):
    """单条历史记录及其操作按钮。"""

    deleted = pyqtSignal(int)
    clicked = pyqtSignal(int)
    copy_requested = pyqtSignal(int)

    def __init__(self, index, text, parent=None):
        super().__init__(parent)
        self.index = index
        self.setObjectName("historyItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(10)

        self.label = QLabel(text)
        self.label.setObjectName("historyText")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.label, 1)

        self.copy_btn = QPushButton("复制")
        self.copy_btn.setObjectName("historyCopyButton")
        self.copy_btn.setMinimumWidth(56)
        self.copy_btn.setFixedHeight(28)
        self.copy_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.copy_btn.setToolTip("复制这条历史记录的简称引用")
        self.copy_btn.clicked.connect(self._on_copy)
        layout.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.delete_btn = QPushButton("删除")
        self.delete_btn.setObjectName("historyDeleteButton")
        self.delete_btn.setMinimumWidth(56)
        self.delete_btn.setFixedHeight(28)
        self.delete_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_btn.setToolTip("删除这条历史记录")
        self.delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_index(self, index):
        """更新记录对应的索引。"""
        self.index = index

    def set_text(self, text):
        """更新历史记录文本。"""
        self.label.setText(text)

    def set_selected(self, selected):
        """更新当前记录的选中状态。"""
        selected = bool(selected)
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def _on_copy(self):
        """发出复制当前记录的信号。"""
        self.copy_requested.emit(self.index)

    def _on_delete(self):
        """发出删除当前记录的信号。"""
        self.deleted.emit(self.index)

    def mousePressEvent(self, event):
        """处理历史记录点击事件。"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.index)
        super().mousePressEvent(event)


class HistoryListWidget(QScrollArea):
    """显示和管理历史记录列表。"""

    item_clicked = pyqtSignal(int)
    item_deleted = pyqtSignal(int)
    item_copy_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("historyList")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._container = QWidget()
        self._container.setObjectName("historyListInner")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch(1)
        self.setWidget(self._container)

        self._rows = []
        self._selected = -1

    def set_entries(self, texts, selected_index=-1):
        """刷新历史记录列表并恢复滚动位置。"""
        bar = self.verticalScrollBar()
        old_value = bar.value()
        while self._rows:
            w = self._rows.pop()
            self._layout.removeWidget(w)
            w.deleteLater()
        self._selected = -1

        for index, text in enumerate(texts):
            row = HistoryItemWidget(index, text)
            row.clicked.connect(self.item_clicked.emit)
            row.deleted.connect(self.item_deleted.emit)
            row.copy_requested.connect(self.item_copy_requested.emit)
            self._layout.insertWidget(index, row)
            self._rows.append(row)

        if 0 <= selected_index < len(self._rows):
            self.set_selected_index(selected_index)

        bar.setValue(old_value)

    def set_selected_index(self, index):
        """设置当前选中的历史记录。"""
        self._selected = index if 0 <= index < len(self._rows) else -1
        for i, row in enumerate(self._rows):
            row.set_selected(i == self._selected)

    def selected_index(self):
        """返回当前选中历史记录的索引。"""
        return self._selected

    def clear(self):
        """清空全部历史记录。"""
        self.set_entries([])
