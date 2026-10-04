"""幻灯片缩略图列表。"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.sermon.model import SermonDocument

# PPT 式：图标在上、页码在下；宽度按侧栏内容区留白计算
_THUMB_W = 168
_THUMB_H = 94
_PANEL_W = 208
_GRID_H = 128


class SlideListWidget(QWidget):
    """左侧缩略图 + 增删复制。"""

    slide_selected = pyqtSignal(int)
    add_requested = pyqtSignal()
    delete_requested = pyqtSignal()
    duplicate_requested = pyqtSignal()
    slides_reordered = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonSlideList")
        self.setFixedWidth(_PANEL_W)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAutoFillBackground(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        title = QLabel("幻灯片")
        title.setObjectName("sermonPanelTitle")
        layout.addWidget(title)

        self.list = QListWidget()
        self.list.setObjectName("sermonSlideListView")
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setFlow(QListWidget.Flow.TopToBottom)
        self.list.setWrapping(False)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setMovement(QListWidget.Movement.Static)
        self.list.setUniformItemSizes(True)
        self.list.setIconSize(QSize(_THUMB_W, _THUMB_H))
        self.list.setGridSize(QSize(_THUMB_W + 16, _GRID_H))
        self.list.setSpacing(6)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.list.setDragEnabled(True)
        self.list.setAcceptDrops(True)
        self.list.setDropIndicatorShown(True)
        self.list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.currentRowChanged.connect(self._on_row)
        self.list.installEventFilter(self)
        self.list.viewport().installEventFilter(self)
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.add_btn = QPushButton("＋")
        self.add_btn.setToolTip("新增幻灯片")
        self.add_btn.clicked.connect(self.add_requested.emit)
        self.dup_btn = QPushButton("复制")
        self.dup_btn.setToolTip("复制选中页")
        self.dup_btn.clicked.connect(self.duplicate_requested.emit)
        self.del_btn = QPushButton("删除")
        self.del_btn.setToolTip("删除选中页")
        self.del_btn.clicked.connect(self.delete_requested.emit)
        for b in (self.add_btn, self.dup_btn, self.del_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(30)
            row.addWidget(b)
        layout.addLayout(row)

        self.meta = QLabel("")
        self.meta.setObjectName("sermonSlideListMeta")
        layout.addWidget(self.meta)

        self._doc: SermonDocument | None = None
        self._block = False
        self._order_ids: list[str] = []

    def set_document(self, doc: SermonDocument | None, current: int = 0):
        self._doc = doc
        self.refresh(current)

    def refresh(self, current: int | None = None):
        if current is None:
            current = self.list.currentRow()
        kept: dict[str, QIcon] = {}
        for i in range(self.list.count()):
            old = self.list.item(i)
            if old is None:
                continue
            sid = old.data(Qt.ItemDataRole.UserRole)
            icon = old.icon()
            if sid and not icon.isNull():
                kept[str(sid)] = QIcon(icon)
        self._block = True
        self.list.clear()
        if self._doc is None:
            self.meta.setText("")
            self._order_ids = []
            self._block = False
            return
        placeholder = QPixmap(_THUMB_W, _THUMB_H)
        placeholder.fill(Qt.GlobalColor.darkGray)
        for i, slide in enumerate(self._doc.slides):
            item = QListWidgetItem(f"{i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, slide.id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            icon = kept.get(slide.id)
            item.setIcon(icon if icon is not None else QIcon(placeholder))
            item.setSizeHint(QSize(_THUMB_W + 16, _GRID_H))
            self.list.addItem(item)
        row = max(0, min(current, self.list.count() - 1))
        if self.list.count():
            self.list.setCurrentRow(row)
        n = len(self._doc.slides)
        self.meta.setText(f"共 {n} 页")
        self._order_ids = self.slide_ids()
        self._block = False

    def update_thumbnail(self, index: int, pixmap: QPixmap):
        item = self.list.item(index)
        if item is None or pixmap.isNull():
            return
        fitted = QPixmap(_THUMB_W, _THUMB_H)
        fitted.fill(Qt.GlobalColor.black)
        scaled = pixmap.scaled(
            _THUMB_W,
            _THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (_THUMB_W - scaled.width()) // 2)
        y = max(0, (_THUMB_H - scaled.height()) // 2)
        painter = QPainter(fitted)
        painter.drawPixmap(x, y, scaled)
        painter.end()
        item.setIcon(QIcon(fitted))

    def slide_ids(self) -> list[str]:
        ids: list[str] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None:
                continue
            sid = item.data(Qt.ItemDataRole.UserRole)
            if sid:
                ids.append(str(sid))
        return ids

    def visible_indexes(self) -> list[int]:
        vp = self.list.viewport().rect()
        rows: list[int] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None:
                continue
            if vp.intersects(self.list.visualItemRect(item)):
                rows.append(i)
        return rows

    def current_index(self) -> int:
        return self.list.currentRow()

    def selected_indexes(self) -> list[int]:
        rows = {self.list.row(item) for item in self.list.selectedItems()}
        return sorted(i for i in rows if i >= 0)

    def select_all_slides(self):
        # IconMode 下 QListWidget.selectAll() 经常无效，逐项勾选。
        self.list.setFocus(Qt.FocusReason.ShortcutFocusReason)
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is not None:
                item.setSelected(True)

    def eventFilter(self, obj, event):
        if obj is self.list and event.type() == QEvent.Type.KeyPress:
            if event.matches(QKeySequence.StandardKey.SelectAll):
                self.select_all_slides()
                return True
        if obj in (self.list, self.list.viewport()) and event.type() == QEvent.Type.Drop:
            QTimer.singleShot(0, self._emit_order_if_changed)
        return super().eventFilter(obj, event)

    def _emit_order_if_changed(self):
        if self._block:
            return
        ids = self.slide_ids()
        if ids and ids != self._order_ids:
            self._order_ids = list(ids)
            self.slides_reordered.emit(ids)

    def _on_row(self, row: int):
        if self._block or row < 0:
            return
        self.slide_selected.emit(row)
