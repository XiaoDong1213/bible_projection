from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, QSize, pyqtSignal

from core.paths import styles_dir


_ACTION_STYLE = """
QPushButton {
    min-width: 28px;
    max-width: 28px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    margin: 0;
    border: none;
    border-radius: 6px;
    background: transparent;
}
"""
_ACTION_HOVER_BLUE = (
    "QPushButton:hover { background: rgba(59,130,246,0.16); }"
    "QPushButton:pressed { background: rgba(59,130,246,0.28); }"
)
_ACTION_HOVER_RED = (
    "QPushButton:hover { background: rgba(239,68,68,0.16); }"
    "QPushButton:pressed { background: rgba(239,68,68,0.3); }"
)


class ElidedLabel(QLabel):
    """单行降级标签：全名放得下显示全名，放不下显示简称，简称也放不下才截断。"""

    def __init__(self, text="", short="", parent=None):
        super().__init__(parent)
        self._full_text = str(text or "")
        self._short_text = str(short or "").strip() or self._full_text
        self.setMinimumWidth(0)
        self._apply_elide()

    def setText(self, text, short=""):
        self._full_text = str(text or "")
        self._short_text = str(short or "").strip() or self._full_text
        self._apply_elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_elide()

    def _apply_elide(self):
        width = max(10, self.width() - 2)
        fm = self.fontMetrics()
        if fm.horizontalAdvance(self._full_text) <= width:
            target = self._full_text
        elif fm.horizontalAdvance(self._short_text) <= width:
            target = self._short_text
        else:
            target = fm.elidedText(
                self._short_text, Qt.TextElideMode.ElideRight, width
            )
        if target != super().text():
            super().setText(target)


class HistoryItemWidget(QWidget):
    """单条历史记录及其操作按钮。"""

    deleted = pyqtSignal(object)
    clicked = pyqtSignal(object)
    copy_requested = pyqtSignal(object)
    pin_toggled = pyqtSignal(object)

    def __init__(self, text, short="", pinned=False, parent=None):
        super().__init__(parent)
        self._full_text = str(text or "")
        self._pinned = bool(pinned)
        self.setObjectName("historyItem")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 10, 8)
        layout.setSpacing(8)

        self.label = ElidedLabel(self._full_text, short)
        self.label.setObjectName("historyText")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.label, 1)

        # 置顶 / 复制 / 删除并排，间距一致
        actions = QWidget(self)
        actions.setObjectName("historyActions")
        actions.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(2)

        self.pin_btn = QPushButton()
        self.pin_btn.setObjectName("historyPinButton")
        self.pin_btn.setFixedSize(28, 26)
        self.pin_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.pin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pin_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pin_btn.setIconSize(QSize(18, 18))
        self.pin_btn.clicked.connect(self._on_pin)
        self.pin_btn.setStyleSheet(_ACTION_STYLE + _ACTION_HOVER_BLUE)
        actions_layout.addWidget(self.pin_btn)
        self._apply_pin_icon()

        self.copy_btn = QPushButton()
        self.copy_btn.setObjectName("historyCopyButton")
        self.copy_btn.setFixedSize(28, 26)
        self.copy_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.copy_btn.setToolTip("复制这条历史记录的简称引用")
        self.copy_btn.setIcon(QIcon(str(styles_dir() / "history-copy.svg")))
        self.copy_btn.setIconSize(QSize(18, 18))
        self.copy_btn.clicked.connect(self._on_copy)
        self.copy_btn.setStyleSheet(_ACTION_STYLE + _ACTION_HOVER_BLUE)
        actions_layout.addWidget(self.copy_btn)

        self.setToolTip(self._full_text)

        self.delete_btn = QPushButton()
        self.delete_btn.setObjectName("historyDeleteButton")
        self.delete_btn.setFixedSize(28, 26)
        self.delete_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.delete_btn.setToolTip("删除这条历史记录")
        self.delete_btn.setIcon(QIcon(str(styles_dir() / "history-delete.svg")))
        self.delete_btn.setIconSize(QSize(18, 18))
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setStyleSheet(_ACTION_STYLE + _ACTION_HOVER_RED)
        actions_layout.addWidget(self.delete_btn)

        layout.addWidget(actions, 0, Qt.AlignmentFlag.AlignVCenter)

    def _apply_pin_icon(self):
        name = "history-pin-on.svg" if self._pinned else "history-pin.svg"
        self.pin_btn.setIcon(QIcon(str(styles_dir() / name)))
        self.pin_btn.setToolTip("取消置顶" if self._pinned else "置顶")

    def set_pinned(self, pinned):
        pinned = bool(pinned)
        if self._pinned == pinned:
            return
        self._pinned = pinned
        self._apply_pin_icon()

    def is_pinned(self):
        return self._pinned

    def set_text(self, text, short=""):
        """更新这一行的全名与简称（增量刷新用），显示形态由标签按真实宽度选。"""
        self._full_text = str(text or "")
        self.setToolTip(self._full_text)
        self.label.setText(self._full_text, short)

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

    def _on_pin(self):
        self.pin_toggled.emit(self)

    def _on_copy(self):
        self.copy_requested.emit(self)

    def _on_delete(self):
        self.deleted.emit(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self)
        super().mousePressEvent(event)


class HistoryListWidget(QScrollArea):
    """显示和管理历史记录列表。"""

    item_clicked = pyqtSignal(object)
    item_deleted = pyqtSignal(object)
    item_copy_requested = pyqtSignal(object)
    item_pin_toggled = pyqtSignal(object)

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
        self._pending_scroll = 0

    def _wire_row(self, row):
        row.clicked.connect(self.item_clicked.emit)
        row.deleted.connect(self.item_deleted.emit)
        row.copy_requested.connect(self.item_copy_requested.emit)
        row.pin_toggled.connect(self.item_pin_toggled.emit)

    def set_entries(self, texts, selected_index=-1, shorts=None, pinned=None):
        """刷新历史记录列表并恢复滚动位置。"""
        bar = self.verticalScrollBar()
        old_value = bar.value()
        while self._rows:
            w = self._rows.pop()
            self._layout.removeWidget(w)
            w.deleteLater()
        self._selected = -1

        shorts = shorts or []
        pinned = pinned or []
        for index, text in enumerate(texts):
            row = HistoryItemWidget(
                text,
                shorts[index] if index < len(shorts) else "",
                pinned=bool(pinned[index]) if index < len(pinned) else False,
            )
            self._wire_row(row)
            self._layout.insertWidget(index, row)
            self._rows.append(row)

        if 0 <= selected_index < len(self._rows):
            self.set_selected_index(selected_index)

        self._pending_scroll = old_value
        QTimer.singleShot(0, self._restore_scroll_value)

    def _restore_scroll_value(self):
        bar = self.verticalScrollBar()
        try:
            bar.setValue(min(self._pending_scroll, bar.maximum()))
        except RuntimeError:
            pass

    def set_selected_index(self, index):
        self._selected = index if 0 <= index < len(self._rows) else -1
        for i, row in enumerate(self._rows):
            row.set_selected(i == self._selected)

    def selected_index(self):
        return self._selected

    def index_of(self, row):
        try:
            return self._rows.index(row)
        except ValueError:
            return -1

    def update_entry_text(self, index, text, short=""):
        if not 0 <= index < len(self._rows):
            return
        self._rows[index].set_text(text, short)

    def set_entry_pinned(self, index, pinned):
        if not 0 <= index < len(self._rows):
            return
        self._rows[index].set_pinned(pinned)

    def remove_entry(self, index):
        if not 0 <= index < len(self._rows):
            return
        row = self._rows.pop(index)
        self._layout.removeWidget(row)
        row.deleteLater()
        if self._selected == index:
            self._selected = -1
        elif self._selected > index:
            self._selected -= 1
        if self._selected >= 0:
            self.set_selected_index(self._selected)

    def insert_entry(self, index, text, short="", pinned=False):
        row = HistoryItemWidget(text, short, pinned=pinned)
        self._wire_row(row)
        self._layout.insertWidget(index, row)
        self._rows.insert(index, row)
        return row

    def move_entry(self, from_idx, to_idx):
        if from_idx == to_idx or not 0 <= from_idx < len(self._rows):
            return
        to_idx = max(0, min(to_idx, len(self._rows) - 1))
        row = self._rows.pop(from_idx)
        self._rows.insert(to_idx, row)
        item = self._layout.takeAt(from_idx)
        if item is not None and item.widget() is not None:
            self._layout.insertWidget(to_idx, item.widget())

    def clear(self):
        self.set_entries([])
