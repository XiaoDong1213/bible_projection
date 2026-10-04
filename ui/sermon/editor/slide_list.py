"""幻灯片缩略图列表。"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonSlideList")
        self.setFixedWidth(_PANEL_W)

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
        self.list.currentRowChanged.connect(self._on_row)
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.add_btn = QPushButton("＋")
        self.add_btn.setToolTip("新增幻灯片")
        self.add_btn.clicked.connect(self.add_requested.emit)
        self.dup_btn = QPushButton("复制")
        self.dup_btn.setToolTip("复制当前页")
        self.dup_btn.clicked.connect(self.duplicate_requested.emit)
        self.del_btn = QPushButton("删除")
        self.del_btn.setToolTip("删除当前页")
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

    def set_document(self, doc: SermonDocument | None, current: int = 0):
        self._doc = doc
        self.refresh(current)

    def refresh(self, current: int | None = None):
        if current is None:
            current = self.list.currentRow()
        self._block = True
        self.list.clear()
        if self._doc is None:
            self.meta.setText("")
            self._block = False
            return
        for i, slide in enumerate(self._doc.slides):
            item = QListWidgetItem(f"{i + 1}")
            item.setData(Qt.ItemDataRole.UserRole, slide.id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            pix = QPixmap(_THUMB_W, _THUMB_H)
            pix.fill(Qt.GlobalColor.darkGray)
            item.setIcon(QIcon(pix))
            item.setSizeHint(QSize(_THUMB_W + 16, _GRID_H))
            self.list.addItem(item)
        row = max(0, min(current, self.list.count() - 1))
        if self.list.count():
            self.list.setCurrentRow(row)
        n = len(self._doc.slides)
        self.meta.setText(f"共 {n} 页")
        self._block = False

    def update_thumbnail(self, index: int, pixmap: QPixmap):
        item = self.list.item(index)
        if item is None or pixmap.isNull():
            return
        scaled = pixmap.scaled(
            _THUMB_W,
            _THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        item.setIcon(QIcon(scaled))

    def current_index(self) -> int:
        return self.list.currentRow()

    def _on_row(self, row: int):
        if self._block or row < 0:
            return
        self.slide_selected.emit(row)
