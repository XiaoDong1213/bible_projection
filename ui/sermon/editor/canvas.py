"""幻灯片画布：QGraphicsView，逻辑坐标与文档一致。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QMouseEvent,
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
from ui.sermon.text_format import (
    apply_text_content,
    apply_text_line_spacing,
    apply_text_tab_stops,
    fit_text_item_height,
    is_text_placeholder,
    plain_from_content,
    resolve_qfont,
)

_HANDLE_ROLES = ("nw", "n", "ne", "e", "se", "s", "sw", "w")
_HANDLE_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,
    "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor,
    "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor,
    "w": Qt.CursorShape.SizeHorCursor,
}


def selection_range_ids(order: list[str], anchor: str | None, target: str) -> list[str]:
    """Shift 连续选：图层顺序上从锚点到目标（含两端）。"""
    if not target or target not in order:
        return [target] if target else []
    if not anchor or anchor not in order:
        return [target]
    i0, i1 = order.index(anchor), order.index(target)
    lo, hi = min(i0, i1), max(i0, i1)
    return order[lo : hi + 1]


def _render_scene_thumb(scene: QGraphicsScene, logical_w: int, logical_h: int, size: int) -> QPixmap:
    source = QRectF(0, 0, logical_w, logical_h)
    aspect = logical_h / max(1, logical_w)
    w = size
    h = max(1, int(size * aspect))
    pix = QPixmap(w, h)
    pix.fill(QColor("#000000"))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    scene.render(painter, QRectF(0, 0, w, h), source)
    painter.end()
    return pix


def render_slide_thumbnail(
    doc: SermonDocument,
    slide: Slide,
    size: int = 168,
    assets_root: Path | None = None,
) -> QPixmap:
    """用临时场景渲一页预览，不碰编辑画布。"""
    lw, lh = doc.canvas_size()
    scene = QGraphicsScene()
    scene.setSceneRect(0, 0, lw, lh)
    bg = QGraphicsRectItem(0, 0, lw, lh)
    bg.setZValue(-1000)
    bg.setPen(QPen(Qt.PenStyle.NoPen))
    scene.addItem(bg)
    background = slide.background
    if background.type == "image" and background.value:
        pix = load_pixmap(background.value, assets_root)
        if pix is not None and not pix.isNull():
            bg.setBrush(QBrush(QColor("#000000")))
            item = QGraphicsPixmapItem()
            item.setZValue(-999)
            item.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
            scaled = scaled_pixmap(
                pix, lw, lh, fit=background.fit or "contain", smooth=True
            )
            item.setPixmap(scaled)
            item.setPos((lw - scaled.width()) / 2, (lh - scaled.height()) / 2)
            scene.addItem(item)
        else:
            color = QColor("#1A1A2E")
            bg.setBrush(QBrush(color))
    else:
        color = QColor(background.value) if background.value else QColor("#1A1A2E")
        if not color.isValid():
            color = QColor("#1A1A2E")
        bg.setBrush(QBrush(color))
    for element in sorted(slide.elements, key=lambda e: e.z):
        if element.type == "text":
            scene.addItem(TextElementItem(element))
        elif element.type == "image":
            pix = load_pixmap(element.content, assets_root) or QPixmap(
                max(1, int(element.w)), max(1, int(element.h))
            )
            if pix.isNull():
                pix = QPixmap(max(1, int(element.w)), max(1, int(element.h)))
                pix.fill(QColor("#444444"))
            scene.addItem(ImageElementItem(element, pix))
        elif element.type == "shape":
            scene.addItem(ShapeElementItem(element))
    return _render_scene_thumb(scene, lw, lh, size)


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
        style = element.style
        font = resolve_qfont(
            style.font_family,
            pixel_size=max(8, int(style.font_size)),
            bold=bool(style.bold),
            italic=bool(style.italic),
        )
        self.setFont(font)
        color = QColor(style.color)
        if color.isValid():
            color.setAlphaF(max(0.0, min(1.0, float(getattr(style, "opacity", 1.0)))))
        self.setDefaultTextColor(color)
        apply_text_tab_stops(self, getattr(style, "tab_stop", 192))
        apply_text_content(self, element.content, style)
        align = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignHCenter,
            "right": Qt.AlignmentFlag.AlignRight,
        }.get(style.align, Qt.AlignmentFlag.AlignLeft)
        option = self.document().defaultTextOption()
        option.setAlignment(align)
        # setAlignment 会换新 option，制表位再写一次
        try:
            option.setTabStopDistance(
                max(24.0, float(getattr(style, "tab_stop", 192) or 192))
            )
        except (TypeError, ValueError):
            option.setTabStopDistance(192.0)
        self.document().setDefaultTextOption(option)
        if getattr(style, "wrap", True):
            self.setTextWidth(max(40.0, element.w))
        else:
            self.setTextWidth(-1)
        self._line_spacing = int(getattr(style, "line_spacing", 120) or 120)
        apply_text_line_spacing(self, self._line_spacing)
        self.setPos(element.x, element.y)
        self.setRotation(element.rotation)
        self.setZValue(element.z)

    def _is_placeholder(self) -> bool:
        return is_text_placeholder(self.toPlainText())

    def _consume_placeholder(self) -> None:
        if not self._is_placeholder():
            return
        self.setPlainText("")
        apply_text_line_spacing(self, getattr(self, "_line_spacing", 120))
        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self.setTextCursor(cursor)
        scene = self.scene()
        if scene is None:
            return
        for view in scene.views():
            if hasattr(view, "commit_geometry"):
                view.commit_geometry()
                break

    def _place_cursor_for_edit(self) -> None:
        cursor = self.textCursor()
        if self._is_placeholder():
            cursor.clearSelection()
            cursor.movePosition(cursor.MoveOperation.Start)
        self.setTextCursor(cursor)

    def mouseDoubleClickEvent(self, event):
        scene = self.scene()
        if scene is not None:
            for view in scene.views():
                if hasattr(view, "edit_started"):
                    view.edit_started.emit()
                if hasattr(view, "_place_resize_handles"):
                    view._place_resize_handles()
                break
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mouseDoubleClickEvent(event)
        self._place_cursor_for_edit()

    def keyPressEvent(self, event):
        if (
            self.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
            and self._is_placeholder()
        ):
            key = event.key()
            if key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
                self._consume_placeholder()
                event.accept()
                return
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if key == Qt.Key.Key_V:
                    self._consume_placeholder()
            elif event.text():
                self._consume_placeholder()
        super().keyPressEvent(event)

    def inputMethodEvent(self, event):
        if event.commitString() or event.preeditString():
            self._consume_placeholder()
        super().inputMethodEvent(event)

    def focusOutEvent(self, event):
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)
        scene = self.scene()
        if scene is None:
            return
        for view in scene.views():
            if hasattr(view, "commit_geometry"):
                view.commit_geometry()
            if hasattr(view, "edit_finished"):
                view.edit_finished.emit()
            if hasattr(view, "_place_resize_handles"):
                view._place_resize_handles()
            break


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


class _ResizeHandle(QGraphicsRectItem):
    """单选时的边角缩放点（屏幕固定大小，像 PPT）。"""

    def __init__(self, role: str, canvas: "SlideCanvas"):
        hs = 9.0
        super().__init__(-hs / 2, -hs / 2, hs, hs)
        self.role = role
        self._canvas = canvas
        self.setZValue(1_000_000)
        self.setBrush(QBrush(QColor("#2196F3")))
        self.setPen(QPen(QColor("#FFFFFF"), 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.setCursor(QCursor(_HANDLE_CURSORS[role]))
        self._start_box: tuple[float, float, float, float] | None = None
        self._origin: QPointF | None = None

    def mousePressEvent(self, event):
        self._canvas.history_checkpoint.emit()
        box = self._canvas._selected_item_box()
        if box is None:
            event.accept()
            return
        self._start_box = box
        self._origin = event.scenePos()
        event.accept()

    def mouseMoveEvent(self, event):
        if self._start_box is None or self._origin is None:
            event.accept()
            return
        delta = event.scenePos() - self._origin
        self._canvas._resize_from_handle(self.role, self._start_box, delta.x(), delta.y())
        event.accept()

    def mouseReleaseEvent(self, event):
        self._start_box = None
        self._origin = None
        self._canvas.commit_geometry()
        self._canvas._place_resize_handles()
        event.accept()


class SlideCanvas(QGraphicsView):
    """单页编辑画布。"""

    selection_changed = pyqtSignal(object)  # Element | None
    slide_modified = pyqtSignal()
    status_message = pyqtSignal(str)
    rect_drawn = pyqtSignal(str, float, float, float, float)  # kind, x, y, w, h
    format_paint_target = pyqtSignal(object)  # Element | None
    edit_finished = pyqtSignal()
    edit_started = pyqtSignal()
    history_checkpoint = pyqtSignal()

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
        self._drag_history_armed = False
        self._stage_matte = QColor("#12161E")
        self.setBackgroundBrush(QBrush(self._stage_matte))
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
        self._format_paint = False
        # PPT 式选区：Shift 连续选锚点；Ctrl+框选时保留原选中
        self._sel_anchor_id: str | None = None
        self._rubber_keep_ids: set[str] | None = None
        self._handles: list[_ResizeHandle] = []

    def set_assets_root(self, root: Path | None):
        self._assets_root = Path(root) if root else None

    def _ensure_handles(self):
        # scene.clear 后 C++ 对象已删，不能再调 h.scene()
        need = not self._handles
        if not need:
            for h in self._handles:
                try:
                    if h.scene() is not self._scene:
                        need = True
                        break
                except RuntimeError:
                    need = True
                    break
        if need:
            self._handles = []
            for role in _HANDLE_ROLES:
                h = _ResizeHandle(role, self)
                h.hide()
                self._scene.addItem(h)
                self._handles.append(h)
        self._place_resize_handles()

    def _editing_text(self) -> bool:
        focus = self._scene.focusItem()
        return isinstance(focus, TextElementItem) and (
            focus.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
        )

    def _selected_item_box(self) -> tuple[float, float, float, float] | None:
        el = self.selected_element()
        if el is None or len(self.selected_elements()) != 1:
            return None
        item = self._items.get(el.id)
        if item is None:
            return None
        x, y = float(item.pos().x()), float(item.pos().y())
        if isinstance(item, TextElementItem):
            tw = float(item.textWidth()) if item.textWidth() > 0 else float(item.boundingRect().width())
            th = float(item.boundingRect().height())
            return x, y, max(20.0, tw), max(16.0, th)
        if isinstance(item, ShapeElementItem):
            r = item.rect()
            return x, y, max(20.0, float(r.width())), max(16.0, float(r.height()))
        if isinstance(item, ImageElementItem):
            pm = item.pixmap()
            return x, y, max(20.0, float(pm.width())), max(16.0, float(pm.height()))
        return None

    def _place_resize_handles(self):
        if not self._handles:
            return
        box = self._selected_item_box()
        if box is None or self._editing_text():
            for h in self._handles:
                h.hide()
            return
        x, y, w, h = box
        pts = {
            "nw": (x, y),
            "n": (x + w / 2, y),
            "ne": (x + w, y),
            "e": (x + w, y + h / 2),
            "se": (x + w, y + h),
            "s": (x + w / 2, y + h),
            "sw": (x, y + h),
            "w": (x, y + h / 2),
        }
        for handle in self._handles:
            px, py = pts[handle.role]
            handle.setPos(px, py)
            handle.show()

    def _resize_from_handle(
        self,
        role: str,
        start: tuple[float, float, float, float],
        dx: float,
        dy: float,
    ):
        el = self.selected_element()
        item = self._items.get(el.id) if el else None
        if el is None or item is None:
            return
        x, y, w, h = start
        left, top, right, bottom = x, y, x + w, y + h
        min_s = 24.0
        if role in ("nw", "w", "sw"):
            left = min(right - min_s, x + dx)
        if role in ("ne", "e", "se"):
            right = max(left + min_s, x + w + dx)
        if role in ("nw", "n", "ne"):
            top = min(bottom - min_s, y + dy)
        if role in ("sw", "s", "se"):
            bottom = max(top + min_s, y + h + dy)
        el.x, el.y = float(left), float(top)
        el.w, el.h = float(right - left), float(bottom - top)
        self._syncing = True
        if isinstance(item, TextElementItem):
            item.setPos(el.x, el.y)
            item.setTextWidth(el.w)
        elif isinstance(item, ShapeElementItem):
            item.apply_element(el)
        elif isinstance(item, ImageElementItem):
            pix = load_pixmap(el.content, self._assets_root)
            item.apply_element(el, pix)
        self._syncing = False
        self._place_resize_handles()
        self.slide_modified.emit()

    def _top_element_item_at(self, view_pos) -> QGraphicsItem | None:
        """点到的最上层可选元素（忽略背景）。"""
        for item in self.items(view_pos):
            if item is self._bg_item or item is self._bg_image_item:
                continue
            if item is self._draw_rubber:
                continue
            if getattr(item, "element_id", None):
                return item
        return None

    def _element_order_ids(self) -> list[str]:
        if self._slide is None:
            return list(self._items.keys())
        return [e.id for e in self._slide.elements if e.id in self._items]

    def _apply_shift_range(self, target: QGraphicsItem, *, additive: bool = False) -> None:
        """Shift+单击：从锚点到目标按图层顺序连续选。"""
        tid = getattr(target, "element_id", None)
        if not tid:
            return
        order = self._element_order_ids()
        if tid not in order:
            return
        aid = self._sel_anchor_id if self._sel_anchor_id in order else None
        if aid is None:
            self._sel_anchor_id = tid
        ids = selection_range_ids(order, self._sel_anchor_id, tid)
        if not additive:
            self._scene.clearSelection()
        for eid in ids:
            item = self._items.get(eid)
            if item is not None:
                item.setSelected(True)

    def nudge_selected(self, dx: float, dy: float) -> bool:
        """方向键微移选中图层。"""
        els = self.selected_elements()
        if not els:
            return False
        for el in els:
            item = self._items.get(el.id)
            if item is None:
                continue
            item.setPos(item.pos() + QPointF(dx, dy))
        self.commit_geometry()
        return True

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
        self._handles = []
        self._scene.clear()

    def _rebuild(self):
        if self._slide is None:
            self.clear_canvas()
            return
        self._syncing = True
        self._handles = []  # scene.clear 会销毁手柄，先丢掉 Python 引用
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

        # 仅编辑画布：导入框常偏矮，按排版后高度抬高（缩略图路径不走这里）
        for el in self._slide.elements:
            if el.type != "text":
                continue
            item = self._items.get(el.id)
            if isinstance(item, TextElementItem):
                el.h = fit_text_item_height(item, el.h)

        self._syncing = False
        self._ensure_handles()
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
                # 留白用主题垫底（监视器外框），不跟死黑/页色
                self.setBackgroundBrush(QBrush(self._stage_matte))
                return
        color = QColor(bg.value) if bg.value else QColor("#1A1A2E")
        if not color.isValid():
            color = QColor("#1A1A2E")
        self._bg_item.setBrush(QBrush(color))
        self.setBackgroundBrush(QBrush(self._stage_matte))

    def set_stage_matte(self, color):
        c = QColor(color) if not isinstance(color, QColor) else QColor(color)
        if c.isValid():
            self._stage_matte = c
            self.setBackgroundBrush(QBrush(self._stage_matte))
            self.viewport().update()

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
        self._place_resize_handles()
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
                plain = item.toPlainText()
                stored_plain = plain_from_content(el.content)
                # 富文本未改可见字时保留 bp-runs；改过则降级为纯文本
                if plain != stored_plain:
                    el.content = plain
                    changed = True
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
        self._place_resize_handles()

    def begin_draw(self, kind: str):
        """进入拖拽画框：text | shape。"""
        if kind not in ("text", "shape"):
            return
        self.cancel_draw()
        self._draw_kind = kind
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        tip = (
            "拖出文本框，打完字后点空白或 Esc 确认"
            if kind == "text"
            else "拖拽画出形状，Esc 取消"
        )
        self.status_message.emit(tip)

    def cancel_draw(self):
        self._clear_draw_rubber()
        self._draw_kind = None
        self._draw_origin = None
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.unsetCursor()

    def is_drawing(self) -> bool:
        return self._draw_kind is not None

    def set_format_paint(self, on: bool):
        self._format_paint = bool(on)
        if self._format_paint:
            self.cancel_draw()
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.viewport().setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.unsetCursor()
            self.viewport().unsetCursor()

    def is_format_painting(self) -> bool:
        return self._format_paint

    def _clear_draw_rubber(self):
        if self._draw_rubber is not None:
            if self._draw_rubber.scene() is not None:
                self._scene.removeItem(self._draw_rubber)
            self._draw_rubber = None

    def mousePressEvent(self, event):
        if self._format_paint and event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            el = self._element_from_item(item) if item is not None else None
            self.format_paint_target.emit(el if el is not None and el.type == "text" else None)
            event.accept()
            return
        if self._format_paint and event.button() == Qt.MouseButton.RightButton:
            self.format_paint_target.emit(False)
            event.accept()
            return
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

        self._drag_history_armed = False
        self._rubber_keep_ids = None
        if (
            event.button() == Qt.MouseButton.LeftButton
            and not self._draw_kind
            and not self._format_paint
        ):
            mods = event.modifiers()
            ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            hit = self._top_element_item_at(event.position().toPoint())

            # 空白处框选：Ctrl 保留原选中再并上框内
            if hit is None:
                if ctrl:
                    self._rubber_keep_ids = {
                        getattr(it, "element_id", "")
                        for it in self._scene.selectedItems()
                        if getattr(it, "element_id", None)
                    }
                super().mousePressEvent(event)
                return

            # Ctrl+单击：切换选中；Shift+单击：连续范围选
            if ctrl or shift:
                if shift and not ctrl:
                    self._apply_shift_range(hit, additive=False)
                elif shift and ctrl:
                    self._apply_shift_range(hit, additive=True)
                else:
                    hit.setSelected(not hit.isSelected())
                    if hit.isSelected():
                        self._sel_anchor_id = getattr(hit, "element_id", None)
                if hit.isSelected():
                    self.history_checkpoint.emit()
                    self._drag_history_armed = True
                    # 去掉修饰键再交给基类，才能拖动且不再改选区
                    plain = QMouseEvent(
                        event.type(),
                        event.position(),
                        event.globalPosition(),
                        event.button(),
                        event.buttons(),
                        Qt.KeyboardModifier.NoModifier,
                    )
                    super().mousePressEvent(plain)
                else:
                    event.accept()
                return

            # 普通单击：单选并记下 Shift 锚点
            self._sel_anchor_id = getattr(hit, "element_id", None)
            self.history_checkpoint.emit()
            self._drag_history_armed = True
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._format_paint:
            event.accept()
            return
        if self._draw_kind and self._draw_origin is not None and self._draw_rubber is not None:
            pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._draw_origin, pos).normalized()
            self._draw_rubber.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)
        if self._handles and any(h.isVisible() for h in self._handles):
            self._place_resize_handles()

    def mouseReleaseEvent(self, event):
        if self._format_paint:
            event.accept()
            return
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
        # Ctrl+框选：把框选前保留的选中并回来
        keep = self._rubber_keep_ids
        self._rubber_keep_ids = None
        if keep:
            for eid in keep:
                item = self._items.get(eid)
                if item is not None:
                    item.setSelected(True)
        self.commit_geometry()
        self._drag_history_armed = False

    def refresh_background(self):
        self._apply_background()
        self.slide_modified.emit()

    def update_selected_from_element(self, element: Element):
        """属性面板改完后刷新选中项外观。"""
        self.update_elements_from_model([element])

    def update_elements_from_model(self, elements: list[Element]):
        """属性面板批量改完后刷新多项外观。"""
        if not elements:
            return
        self._syncing = True
        for element in elements:
            item = self._items.get(element.id)
            if item is None:
                continue
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
        if event.key() == Qt.Key.Key_Escape and self._format_paint:
            self.format_paint_target.emit(False)
            event.accept()
            return
        if self._draw_kind and event.key() == Qt.Key.Key_Escape:
            self.cancel_draw()
            self.status_message.emit("已取消画框")
            event.accept()
            return
        # 改字中：方向键留给光标，不微移图层
        focus = self._scene.focusItem()
        editing_text = isinstance(focus, TextElementItem) and (
            focus.textInteractionFlags() != Qt.TextInteractionFlag.NoTextInteraction
        )
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            if editing_text:
                super().keyPressEvent(event)
                return
            self.remove_selected()
            event.accept()
            return
        arrows = {
            Qt.Key.Key_Left: (-1.0, 0.0),
            Qt.Key.Key_Right: (1.0, 0.0),
            Qt.Key.Key_Up: (0.0, -1.0),
            Qt.Key.Key_Down: (0.0, 1.0),
        }
        if event.key() in arrows and not editing_text:
            dx, dy = arrows[event.key()]
            step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            if self.nudge_selected(dx * step, dy * step):
                event.accept()
                return
        super().keyPressEvent(event)

    def render_thumbnail(self, size: int = 160) -> QPixmap:
        """当前页缩略图。"""
        if self._slide is None:
            pix = QPixmap(size, int(size * 9 / 16))
            pix.fill(QColor("#333333"))
            return pix
        return _render_scene_thumb(
            self._scene, self._logical_w, self._logical_h, size
        )

    def render_slide_thumbnail(
        self, doc: SermonDocument, slide: Slide, size: int = 168
    ) -> QPixmap:
        """离屏渲染任意页，不拆当前画布。"""
        return render_slide_thumbnail(doc, slide, size, self._assets_root)
