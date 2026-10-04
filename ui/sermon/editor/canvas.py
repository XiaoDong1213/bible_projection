"""幻灯片画布：QGraphicsView，逻辑坐标与文档一致。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from core.sermon.image_cache import load_pixmap, scaled_pixmap
from core.sermon.model import Element, SermonDocument, Slide


class ElementItemMixin:
    """图形项与 Element.id 绑定。"""

    element_id: str = ""


class TextElementItem(QGraphicsTextItem, ElementItemMixin):
    def __init__(self, element: Element, parent=None):
        super().__init__(parent)
        self.element_id = element.id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.apply_element(element)

    def apply_element(self, element: Element):
        self.element_id = element.id
        self.setPlainText(element.content or "")
        style = element.style
        font = QFont(style.font_family or "微软雅黑")
        font.setPixelSize(max(8, int(style.font_size)))
        font.setBold(style.bold)
        font.setItalic(style.italic)
        self.setFont(font)
        color = QColor(style.color)
        if color.isValid():
            color.setAlphaF(max(0.0, min(1.0, float(getattr(style, "opacity", 1.0)))))
        self.setDefaultTextColor(color)
        align = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(style.align, Qt.AlignmentFlag.AlignLeft)
        option = self.document().defaultTextOption()
        option.setAlignment(align)
        self.document().setDefaultTextOption(option)
        if getattr(style, "wrap", True):
            self.setTextWidth(max(40.0, element.w))
        else:
            self.setTextWidth(-1)
        self.setPos(element.x, element.y)
        self.setRotation(element.rotation)
        self.setZValue(element.z)

    def mouseDoubleClickEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        cursor = self.textCursor()
        cursor.select(cursor.SelectionType.Document)
        self.setTextCursor(cursor)
        super().mouseDoubleClickEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)


class ShapeElementItem(QGraphicsRectItem, ElementItemMixin):
    """矩形 / 椭圆填充形状（透明度在 brush alpha）。"""

    def __init__(self, element: Element, parent=None):
        super().__init__(parent)
        self.element_id = element.id
        self._kind = element.shape or "rect"
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.apply_element(element)

    def apply_element(self, element: Element):
        self.element_id = element.id
        self._kind = element.shape if element.shape in ("rect", "ellipse") else "rect"
        self.setRect(0, 0, max(1.0, element.w), max(1.0, element.h))
        color = QColor(element.style.color or "#000000")
        if not color.isValid():
            color = QColor("#000000")
        color.setAlphaF(max(0.0, min(1.0, float(element.style.opacity))))
        self.setBrush(QBrush(color))
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setPos(element.x, element.y)
        self.setRotation(element.rotation)
        self.setZValue(element.z)

    def paint(self, painter, option, widget=None):
        if self._kind == "ellipse":
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setBrush(self.brush())
            painter.setPen(self.pen())
            painter.drawEllipse(self.rect())
        else:
            super().paint(painter, option, widget)


class ImageElementItem(QGraphicsPixmapItem, ElementItemMixin):
    def __init__(self, element: Element, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.element_id = element.id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.apply_element(element, pixmap)

    def apply_element(self, element: Element, pixmap: QPixmap | None = None):
        self.element_id = element.id
        if pixmap is not None and not pixmap.isNull():
            scaled = scaled_pixmap(
                pixmap,
                max(1, int(element.w)),
                max(1, int(element.h)),
                smooth=True,
            )
            self.setPixmap(scaled)
        self.setPos(element.x, element.y)
        self.setRotation(element.rotation)
        self.setZValue(element.z)


class SlideCanvas(QGraphicsView):
    """单页编辑画布。"""

    selection_changed = pyqtSignal(object)  # Element | None
    slide_modified = pyqtSignal()
    status_message = pyqtSignal(str)
    rect_drawn = pyqtSignal(str, float, float, float, float)  # kind, x, y, w, h

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonCanvas")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor("#2B2B2B")))
        self.setFrameShape(self.Shape.NoFrame)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._scene.selectionChanged.connect(self._on_selection_changed)

        self._doc: SermonDocument | None = None
        self._slide: Slide | None = None
        self._assets_root: Path | None = None
        self._bg_item: QGraphicsRectItem | None = None
        self._bg_image_item: QGraphicsPixmapItem | None = None
        self._items: dict[str, QGraphicsItem] = {}
        self._syncing = False
        self._logical_w = 1920
        self._logical_h = 1080
        self._wheel_guard_ms = 0
        self._draw_kind: str | None = None  # "text" | "shape"
        self._draw_origin: QPointF | None = None
        self._draw_rubber: QGraphicsRectItem | None = None

    def set_assets_root(self, root: Path | None):
        self._assets_root = Path(root) if root else None

    def wheelEvent(self, event):
        """滚轮翻页（放映跟控制器；编辑跟侧栏）。编辑文字时不抢。"""
        host = self.parent()
        while host is not None and not hasattr(host, "_presenting"):
            host = host.parent()
        if host is None:
            super().wheelEvent(event)
            return
        if hasattr(host, "_focus_is_text_field") and host._focus_is_text_field():
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return
        from PyQt6.QtCore import QDateTime

        now = QDateTime.currentMSecsSinceEpoch()
        if now - self._wheel_guard_ms < 180:
            event.accept()
            return
        self._wheel_guard_ms = now
        if hasattr(host, "_wheel_change_slide"):
            host._wheel_change_slide(delta)
        elif getattr(host, "_presenting", False):
            if delta < 0:
                host._present_next()
            else:
                host._present_prev()
        event.accept()

    def load_slide(self, doc: SermonDocument, slide: Slide):
        self._doc = doc
        self._slide = slide
        self._logical_w, self._logical_h = doc.canvas_size()
        self._rebuild()

    def current_slide(self) -> Slide | None:
        return self._slide

    def clear_canvas(self):
        self._doc = None
        self._slide = None
        self._items.clear()
        self._bg_item = None
        self._bg_image_item = None
        self._scene.clear()

    def _rebuild(self):
        if self._slide is None:
            self.clear_canvas()
            return
        self._syncing = True
        self._scene.clear()
        self._items.clear()
        self._bg_item = None
        self._bg_image_item = None

        self._scene.setSceneRect(0, 0, self._logical_w, self._logical_h)

        self._bg_item = QGraphicsRectItem(0, 0, self._logical_w, self._logical_h)
        self._bg_item.setZValue(-1000)
        self._bg_item.setPen(QPen(Qt.PenStyle.NoPen))
        self._apply_background()
        self._scene.addItem(self._bg_item)

        for element in sorted(self._slide.elements, key=lambda e: e.z):
            self._add_item_for_element(element)

        self._syncing = False
        self._fit_view()
        self.selection_changed.emit(None)

    def _apply_background(self):
        if self._bg_item is None or self._slide is None:
            return
        bg = self._slide.background
        if self._bg_image_item is not None:
            self._scene.removeItem(self._bg_image_item)
            self._bg_image_item = None

        if bg.type == "image" and bg.value:
            pix = load_pixmap(bg.value, self._assets_root)
            if pix is not None and not pix.isNull():
                self._bg_item.setBrush(QBrush(QColor("#000000")))
                item = QGraphicsPixmapItem()
                item.setZValue(-999)
                item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
                scaled = scaled_pixmap(
                    pix,
                    self._logical_w,
                    self._logical_h,
                    fit=bg.fit or "contain",
                    smooth=True,
                )
                item.setPixmap(scaled)
                # 居中
                item.setPos(
                    (self._logical_w - scaled.width()) / 2,
                    (self._logical_h - scaled.height()) / 2,
                )
                self._scene.addItem(item)
                self._bg_image_item = item
                return
        color = QColor(bg.value) if bg.value else QColor("#1A1A2E")
        if not color.isValid():
            color = QColor("#1A1A2E")
        self._bg_item.setBrush(QBrush(color))

    def _add_item_for_element(self, element: Element):
        if element.type == "text":
            item = TextElementItem(element)
            self._scene.addItem(item)
            self._items[element.id] = item
        elif element.type == "image":
            pix = load_pixmap(element.content, self._assets_root) or QPixmap(
                int(element.w), int(element.h)
            )
            if pix.isNull():
                pix = QPixmap(max(1, int(element.w)), max(1, int(element.h)))
                pix.fill(QColor("#444444"))
            item = ImageElementItem(element, pix)
            self._scene.addItem(item)
            self._items[element.id] = item
        elif element.type == "shape":
            item = ShapeElementItem(element)
            self._scene.addItem(item)
            self._items[element.id] = item

    def _fit_view(self):
        if self._logical_w <= 0:
            return
        margin = 24
        self.fitInView(
            QRectF(-margin, -margin, self._logical_w + margin * 2, self._logical_h + margin * 2),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_view()

    def _on_selection_changed(self):
        if self._syncing:
            return
        selected = self._scene.selectedItems()
        if not selected:
            self.selection_changed.emit(None)
            return
        item = selected[0]
        element = self._element_from_item(item)
        self.selection_changed.emit(element)

    def _element_from_item(self, item: QGraphicsItem) -> Element | None:
        if self._slide is None:
            return None
        eid = getattr(item, "element_id", None)
        if not eid:
            return None
        for el in self._slide.elements:
            if el.id == eid:
                return el
        return None

    def selected_element(self) -> Element | None:
        items = self._scene.selectedItems()
        if not items:
            return None
        return self._element_from_item(items[0])

    def selected_elements(self) -> list[Element]:
        out: list[Element] = []
        seen: set[str] = set()
        for item in self._scene.selectedItems():
            el = self._element_from_item(item)
            if el is None or el.id in seen:
                continue
            seen.add(el.id)
            out.append(el)
        return out

    def select_all(self):
        """选中当前页全部图层。"""
        for item in self._items.values():
            item.setSelected(True)
        els = self.selected_elements()
        self.selection_changed.emit(els[0] if len(els) == 1 else None)

    def align_selected(self, mode: str, relative: str = "slide"):
        """图层对齐：left|hcenter|right|top|vcenter|bottom。

        relative:
          - slide：相对幻灯片（单个也可）
          - selection：相对选中对象包围盒（≥2）
        """
        self.commit_geometry()
        els = self.selected_elements()
        if not els:
            return
        if relative == "selection":
            if len(els) < 2:
                return
            left = min(e.x for e in els)
            top = min(e.y for e in els)
            right = max(e.x + e.w for e in els)
            bottom = max(e.y + e.h for e in els)
        else:
            left = 0.0
            top = 0.0
            right = float(self._logical_w)
            bottom = float(self._logical_h)
        mid_x = (left + right) / 2
        mid_y = (top + bottom) / 2
        for e in els:
            if mode == "left":
                e.x = left
            elif mode == "hcenter":
                e.x = mid_x - e.w / 2
            elif mode == "right":
                e.x = right - e.w
            elif mode == "top":
                e.y = top
            elif mode == "vcenter":
                e.y = mid_y - e.h / 2
            elif mode == "bottom":
                e.y = bottom - e.h
            item = self._items.get(e.id)
            if item is not None:
                item.setPos(e.x, e.y)
        self.slide_modified.emit()

    def distribute_selected(self, axis: str):
        """多选图层等距分布：h | v。"""
        self.commit_geometry()
        els = self.selected_elements()
        if len(els) < 3:
            return
        if axis == "h":
            ordered = sorted(els, key=lambda e: e.x)
            left = ordered[0].x
            right = ordered[-1].x + ordered[-1].w
            total = sum(e.w for e in ordered)
            gap = (right - left - total) / (len(ordered) - 1)
            cursor = left
            for e in ordered:
                e.x = cursor
                cursor += e.w + gap
                item = self._items.get(e.id)
                if item is not None:
                    item.setPos(e.x, e.y)
        else:
            ordered = sorted(els, key=lambda e: e.y)
            top = ordered[0].y
            bottom = ordered[-1].y + ordered[-1].h
            total = sum(e.h for e in ordered)
            gap = (bottom - top - total) / (len(ordered) - 1)
            cursor = top
            for e in ordered:
                e.y = cursor
                cursor += e.h + gap
                item = self._items.get(e.id)
                if item is not None:
                    item.setPos(e.x, e.y)
        self.slide_modified.emit()

    def commit_geometry(self):
        """把图形项位置写回文档。"""
        if self._slide is None or self._syncing:
            return
        changed = False
        for el in self._slide.elements:
            item = self._items.get(el.id)
            if item is None:
                continue
            pos = item.pos()
            if abs(el.x - pos.x()) > 0.5 or abs(el.y - pos.y()) > 0.5:
                el.x = float(pos.x())
                el.y = float(pos.y())
                changed = True
            if isinstance(item, TextElementItem):
                text = item.toPlainText()
                if text != el.content:
                    el.content = text
                    changed = True
                # 文本宽
                tw = item.textWidth()
                if tw > 0 and abs(el.w - tw) > 0.5:
                    el.w = float(tw)
                    changed = True
                br = item.boundingRect()
                if br.height() > 0 and abs(el.h - br.height()) > 0.5:
                    el.h = float(br.height())
                    changed = True
            elif isinstance(item, ShapeElementItem):
                rect = item.rect()
                if abs(el.w - rect.width()) > 0.5 or abs(el.h - rect.height()) > 0.5:
                    el.w = float(rect.width())
                    el.h = float(rect.height())
                    changed = True
        if changed:
            self.slide_modified.emit()

    def begin_draw(self, kind: str):
        """进入拖拽画框：text | shape。"""
        if kind not in ("text", "shape"):
            return
        self.cancel_draw()
        self._draw_kind = kind
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        tip = "拖拽画出文本框，Esc 取消" if kind == "text" else "拖拽画出形状，Esc 取消"
        self.status_message.emit(tip)

    def cancel_draw(self):
        self._clear_draw_rubber()
        self._draw_kind = None
        self._draw_origin = None
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.unsetCursor()

    def is_drawing(self) -> bool:
        return self._draw_kind is not None

    def _clear_draw_rubber(self):
        if self._draw_rubber is not None:
            if self._draw_rubber.scene() is not None:
                self._scene.removeItem(self._draw_rubber)
            self._draw_rubber = None

    def mousePressEvent(self, event):
        if (
            self._draw_kind
            and event.button() == Qt.MouseButton.LeftButton
            and self._slide is not None
        ):
            pos = self.mapToScene(event.position().toPoint())
            self._draw_origin = pos
            self._clear_draw_rubber()
            rubber = QGraphicsRectItem(QRectF(pos, pos))
            rubber.setZValue(100000)
            rubber.setPen(QPen(QColor("#4FC3F7"), 6, Qt.PenStyle.DashLine))
            rubber.setBrush(QBrush(QColor(79, 195, 247, 40)))
            self._scene.addItem(rubber)
            self._draw_rubber = rubber
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self._draw_kind:
            self.cancel_draw()
            self.status_message.emit("已取消画框")
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._draw_kind and self._draw_origin is not None and self._draw_rubber is not None:
            pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._draw_origin, pos).normalized()
            self._draw_rubber.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if (
            self._draw_kind
            and event.button() == Qt.MouseButton.LeftButton
            and self._draw_origin is not None
        ):
            pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._draw_origin, pos).normalized()
            kind = self._draw_kind
            self.cancel_draw()
            # 单击未拖：给默认小框
            if rect.width() < 20 or rect.height() < 16:
                cx, cy = pos.x(), pos.y()
                if kind == "text":
                    rect = QRectF(cx - 200, cy - 40, 400, 80)
                else:
                    rect = QRectF(cx - 160, cy - 80, 320, 160)
            self.rect_drawn.emit(
                kind,
                float(rect.x()),
                float(rect.y()),
                float(max(40.0, rect.width())),
                float(max(24.0, rect.height())),
            )
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self.commit_geometry()

    def refresh_background(self):
        self._apply_background()
        self.slide_modified.emit()

    def update_selected_from_element(self, element: Element):
        """属性面板改完后刷新选中项外观。"""
        item = self._items.get(element.id)
        if item is None:
            return
        self._syncing = True
        if isinstance(item, TextElementItem):
            item.apply_element(element)
        elif isinstance(item, ImageElementItem):
            pix = load_pixmap(element.content, self._assets_root)
            item.apply_element(element, pix)
        elif isinstance(item, ShapeElementItem):
            item.apply_element(element)
        self._syncing = False
        self.slide_modified.emit()

    def add_element(self, element: Element):
        if self._slide is None:
            return
        max_z = max((e.z for e in self._slide.elements), default=-1)
        element.z = max_z + 1
        self._slide.elements.append(element)
        self._add_item_for_element(element)
        item = self._items.get(element.id)
        if item is not None:
            self._scene.clearSelection()
            item.setSelected(True)
        self.slide_modified.emit()

    def reorder_selected(self, action: str):
        """调整选中元素图层：front|back|up|down。"""
        if self._slide is None:
            return
        el = self.selected_element()
        if el is None:
            return
        ordered = sorted(self._slide.elements, key=lambda e: (e.z, e.id))
        idx = next((i for i, e in enumerate(ordered) if e.id == el.id), -1)
        if idx < 0:
            return
        if action == "up":
            if idx >= len(ordered) - 1:
                return
            ordered[idx], ordered[idx + 1] = ordered[idx + 1], ordered[idx]
        elif action == "down":
            if idx <= 0:
                return
            ordered[idx], ordered[idx - 1] = ordered[idx - 1], ordered[idx]
        elif action == "front":
            ordered.append(ordered.pop(idx))
        elif action == "back":
            ordered.insert(0, ordered.pop(idx))
        else:
            return
        for i, e in enumerate(ordered):
            e.z = i
            item = self._items.get(e.id)
            if item is not None:
                item.setZValue(i)
        self.slide_modified.emit()

    def remove_selected(self):
        if self._slide is None:
            return
        selected = list(self._scene.selectedItems())
        if not selected:
            return
        ids = {getattr(i, "element_id", None) for i in selected}
        ids.discard(None)
        if not ids:
            return
        self._slide.elements = [e for e in self._slide.elements if e.id not in ids]
        for eid in ids:
            item = self._items.pop(eid, None)
            if item is not None:
                self._scene.removeItem(item)
        self.slide_modified.emit()
        self.selection_changed.emit(None)

    def keyPressEvent(self, event):
        if self._draw_kind and event.key() == Qt.Key.Key_Escape:
            self.cancel_draw()
            self.status_message.emit("已取消画框")
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            # 文本编辑中不删元素
            focus = self._scene.focusItem()
            if isinstance(focus, TextElementItem) and (
                focus.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
            ):
                super().keyPressEvent(event)
                return
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def render_thumbnail(self, size: int = 160) -> QPixmap:
        """当前页缩略图。"""
        if self._slide is None:
            pix = QPixmap(size, int(size * 9 / 16))
            pix.fill(QColor("#333333"))
            return pix
        source = QRectF(0, 0, self._logical_w, self._logical_h)
        aspect = self._logical_h / max(1, self._logical_w)
        w = size
        h = max(1, int(size * aspect))
        pix = QPixmap(w, h)
        pix.fill(QColor("#000000"))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._scene.render(painter, QRectF(0, 0, w, h), source)
        painter.end()
        return pix

    def render_slide_thumbnail(
        self, doc: SermonDocument, slide: Slide, size: int = 168
    ) -> QPixmap:
        """渲染任意页缩略图，结束后恢复当前页。"""
        old_doc, old_slide = self._doc, self._slide
        self.load_slide(doc, slide)
        pix = self.render_thumbnail(size)
        if old_doc is not None and old_slide is not None:
            self.load_slide(old_doc, old_slide)
        return pix
