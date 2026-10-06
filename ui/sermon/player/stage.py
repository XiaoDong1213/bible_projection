"""放映用只读幻灯片舞台（含入场动画）。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import (
    QDateTime,
    QPointF,
    QRectF,
    QEasingCurve,
    Qt,
    QTimer,
    QVariantAnimation,
    pyqtSignal,
)
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
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
from core.sermon.model import AnimStep, Element, SermonDocument, Slide
from ui.sermon.text_format import apply_text_line_spacing, is_text_placeholder

FLY_OFFSET = 160


class SlideStage(QGraphicsView):
    """副屏讲篇层：无交互，按文档逻辑尺寸等比铺满。"""

    anim_finished = pyqtSignal()
    page_step_requested = pyqtSignal(int)  # +1 下一页/步，-1 上一页
    edit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonSlideStage")
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
        )
        self.setOptimizationFlag(
            QGraphicsView.OptimizationFlag.DontSavePainterState, True
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(self.Shape.NoFrame)
        self.setStyleSheet("background: #000; border: none; border-radius: 0;")
        self.setInteractive(False)

        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._assets_root: Path | None = None
        self._logical_w = 1920
        self._logical_h = 1080
        self._bg_item: QGraphicsRectItem | None = None
        self._bg_image_item: QGraphicsPixmapItem | None = None
        self._items: dict[str, QGraphicsItem] = {}
        self._targets: dict[str, QPointF] = {}
        self._wipe_hosts: dict[str, QGraphicsRectItem] = {}
        self._running: list[QVariantAnimation] = []
        self._slide: Slide | None = None
        self._wheel_guard_ms = 0
        self._wheel_pages = True
        self._page_overlay: QGraphicsPixmapItem | None = None
        self._page_wipe_host: QGraphicsRectItem | None = None
        self._page_anim: QVariantAnimation | None = None
        self._page_done = None
        self._hold_item: QGraphicsPixmapItem | None = None
        self._new_base_item: QGraphicsPixmapItem | None = None
        self._old_snap = QPixmap()
        self._render_cache: dict[tuple, QPixmap] = {}
        self._pending_hot: tuple | None = None
        self._preview_edit = False
        self._hot_flush_timer = QTimer(self)
        self._hot_flush_timer.setSingleShot(True)
        self._hot_flush_timer.setInterval(800)
        self._hot_flush_timer.timeout.connect(self._force_flush_pending_hot)

    def set_assets_root(self, root: Path | None):
        self._assets_root = Path(root) if root else None

    def set_preview_quality(self, light: bool):
        """主屏预览减绘制负担；副屏不要开。"""
        self._preview_edit = bool(light)
        if light:
            self.setRenderHints(QPainter.RenderHint.TextAntialiasing)
            self.setViewportUpdateMode(
                QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
            )
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("放映预览 · 请点工具栏「编辑」再改内容")
        else:
            self.setRenderHints(
                QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
            )
            self.setViewportUpdateMode(
                QGraphicsView.ViewportUpdateMode.SmartViewportUpdate
            )
            self.unsetCursor()
            self.setToolTip("")

    def abort_playback(self):
        """立刻停入场与换页过渡，不回调 on_done。"""
        self.stop_animations(apply_end=False)
        self._stop_page_transition(apply_end=False)
        self.release_hold()

    def clear_stage(self):
        self.abort_playback()
        self._bg_item = None
        self._bg_image_item = None
        self._items.clear()
        self._targets.clear()
        self._wipe_hosts.clear()
        self._slide = None
        self._old_snap = QPixmap()
        self._render_cache.clear()
        self._scene.clear()

    def show_slide(
        self,
        doc: SermonDocument,
        slide: Slide,
        *,
        prepare_anims: bool = True,
    ):
        """渲染一页。prepare_anims=True 时隐藏有入场动画的元素。"""
        self.stop_animations(apply_end=False)
        hold_pix = (
            self._hold_item.pixmap()
            if self._hold_item is not None and not self._hold_item.pixmap().isNull()
            else QPixmap()
        )
        # 清掉过渡层，但不回调 on_done
        anim = self._page_anim
        self._page_anim = None
        self._page_done = None
        if anim is not None:
            anim.stop()
        self._logical_w, self._logical_h = doc.canvas_size()
        self._items.clear()
        self._targets.clear()
        self._wipe_hosts.clear()
        self._bg_item = None
        self._bg_image_item = None
        self._slide = slide
        self._hold_item = None
        self._new_base_item = None
        self._page_overlay = None
        self._page_wipe_host = None
        self._scene.clear()
        self._scene.setSceneRect(0, 0, self._logical_w, self._logical_h)
        self._populate_live_scene(doc, slide, prepare_anims=prepare_anims)
        self._fit_view()
        if not hold_pix.isNull():
            self.hold_pixmap(hold_pix)

    def hot_refresh(self, doc: SermonDocument, slide: Slide, *, anim_cursor: int = 0):
        """放映中改内容：同一页就地更新，避免整页清空闪一下。"""
        if self._page_anim is not None or self._hold_item is not None:
            self._pending_hot = (doc, slide, int(anim_cursor))
            if not self._hot_flush_timer.isActive():
                self._hot_flush_timer.start()
            return
        same = (
            self._slide is not None
            and getattr(self._slide, "id", None) == getattr(slide, "id", None)
            and self._page_anim is None
            and self._hold_item is None
        )
        if not same:
            self.show_slide(doc, slide, prepare_anims=True)
            played = slide.sorted_animations()[: max(0, int(anim_cursor))]
            if played:
                self.apply_played_steps(played)
            return
        self._slide = slide
        self._logical_w, self._logical_h = doc.canvas_size()
        self._scene.setSceneRect(0, 0, self._logical_w, self._logical_h)
        self._apply_background(slide)
        keep = {e.id for e in slide.elements}
        for eid in list(self._items.keys()):
            if eid in keep:
                continue
            item = self._items.pop(eid)
            self._targets.pop(eid, None)
            if item.scene() is not None:
                self._scene.removeItem(item)
        for element in sorted(slide.elements, key=lambda e: e.z):
            item = self._items.get(element.id)
            if item is None or not self._element_item_matches(item, element):
                if item is not None and item.scene() is not None:
                    self._scene.removeItem(item)
                item = self._add_element(element)
                if item is None:
                    self._items.pop(element.id, None)
                    continue
                self._items[element.id] = item
            else:
                self._apply_element_visuals(item, element)
            self._targets[element.id] = QPointF(element.x, element.y)
        self._render_cache = {
            key: pix for key, pix in self._render_cache.items() if key[0] != slide.id
        }
        anims = slide.sorted_animations()
        cursor = max(0, int(anim_cursor))
        played_ids = {a.element_id for a in anims[:cursor]}
        pending_ids = {a.element_id for a in anims[cursor:]}
        for element in slide.elements:
            item = self._items.get(element.id)
            if item is None:
                continue
            if element.id in pending_ids and element.id not in played_ids:
                self._prepare_entrance(item, element, slide)
        played = anims[:cursor]
        if played:
            self.apply_played_steps(played)
        self._fit_view()

    def _element_item_matches(self, item, element: Element) -> bool:
        kind = element.type
        if kind == "text":
            return isinstance(item, QGraphicsTextItem)
        if kind == "image":
            return isinstance(item, QGraphicsPixmapItem)
        if kind == "shape":
            shape = element.shape if element.shape in ("rect", "ellipse") else "rect"
            if shape == "ellipse":
                return isinstance(item, QGraphicsEllipseItem)
            return isinstance(item, QGraphicsRectItem) and not isinstance(
                item, QGraphicsEllipseItem
            )
        return False

    def _apply_element_visuals(self, item, element: Element):
        if element.type == "text" and isinstance(item, QGraphicsTextItem):
            raw = element.content or ""
            text = "" if is_text_placeholder(raw) else raw
            if item.toPlainText() != text:
                item.setPlainText(text)
            style = element.style
            font = QFont(style.font_family or "微软雅黑")
            font.setPixelSize(max(8, int(style.font_size)))
            font.setBold(style.bold)
            font.setItalic(style.italic)
            item.setFont(font)
            color = QColor(style.color)
            if color.isValid():
                color.setAlphaF(max(0.0, min(1.0, float(getattr(style, "opacity", 1.0)))))
            item.setDefaultTextColor(color)
            align = {
                "left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight,
            }.get(style.align, Qt.AlignmentFlag.AlignLeft)
            option = item.document().defaultTextOption()
            option.setAlignment(align)
            item.document().setDefaultTextOption(option)
            if getattr(style, "wrap", True):
                item.setTextWidth(max(40.0, element.w))
            else:
                item.setTextWidth(-1)
            apply_text_line_spacing(item, getattr(style, "line_spacing", 120))
        elif element.type == "image" and isinstance(item, QGraphicsPixmapItem):
            pix = load_pixmap(element.content, self._assets_root)
            if pix is None or pix.isNull():
                pix = QPixmap(max(1, int(element.w)), max(1, int(element.h)))
                pix.fill(QColor("#444444"))
            scaled = scaled_pixmap(
                pix, max(1, int(element.w)), max(1, int(element.h)), smooth=False
            )
            item.setPixmap(scaled)
            item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        elif element.type == "shape":
            if isinstance(item, QGraphicsRectItem):
                item.setRect(0, 0, max(1.0, element.w), max(1.0, element.h))
            color = QColor(element.style.color or "#000000")
            if not color.isValid():
                color = QColor("#000000")
            color.setAlphaF(max(0.0, min(1.0, float(element.style.opacity))))
            item.setBrush(QBrush(color))
            item.setPen(QPen(Qt.PenStyle.NoPen))
        item.setPos(element.x, element.y)
        item.setRotation(element.rotation)
        item.setZValue(element.z)

    def _populate_live_scene(
        self, doc: SermonDocument, slide: Slide, *, prepare_anims: bool
    ):
        self._bg_item = QGraphicsRectItem(0, 0, self._logical_w, self._logical_h)
        self._bg_item.setZValue(-1000)
        self._bg_item.setPen(QPen(Qt.PenStyle.NoPen))
        self._scene.addItem(self._bg_item)
        self._apply_background(slide)
        animated_ids = {a.element_id for a in slide.animations} if prepare_anims else set()
        for element in sorted(slide.elements, key=lambda e: e.z):
            item = self._add_element(element)
            if item is None:
                continue
            self._items[element.id] = item
            self._targets[element.id] = QPointF(element.x, element.y)
            if element.id in animated_ids:
                self._prepare_entrance(item, element, slide)

    def cached_slide_pixmap(
        self,
        doc: SermonDocument,
        slide: Slide,
        *,
        prepare_anims: bool = False,
    ) -> QPixmap:
        w, h = doc.canvas_size()
        key = (slide.id, bool(prepare_anims), int(w), int(h), str(self._assets_root or ""))
        cached = self._render_cache.get(key)
        if cached is not None and not cached.isNull():
            return QPixmap(cached)
        return QPixmap()

    def render_slide_pixmap(
        self,
        doc: SermonDocument,
        slide: Slide,
        *,
        prepare_anims: bool = False,
    ) -> QPixmap:
        """离屏渲染一页（不碰当前舞台），供双图切换与预缓存。"""
        w, h = doc.canvas_size()
        key = (slide.id, bool(prepare_anims), int(w), int(h), str(self._assets_root or ""))
        cached = self._render_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached
        scene = QGraphicsScene()
        scene.setSceneRect(0, 0, w, h)
        bg = QGraphicsRectItem(0, 0, w, h)
        bg.setZValue(-1000)
        bg.setPen(QPen(Qt.PenStyle.NoPen))
        scene.addItem(bg)
        self._paint_background_on(scene, bg, slide, w, h)
        animated_ids = {a.element_id for a in slide.animations} if prepare_anims else set()
        targets: dict[str, QPointF] = {}
        items: dict[str, QGraphicsItem] = {}
        for element in sorted(slide.elements, key=lambda e: e.z):
            item = self._make_element_item(element, scene)
            if item is None:
                continue
            items[element.id] = item
            targets[element.id] = QPointF(element.x, element.y)
            if element.id in animated_ids:
                self._prepare_entrance_item(item, element, slide, targets)
        pix = QPixmap(max(1, int(w)), max(1, int(h)))
        pix.fill(QColor("#000000"))
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        scene.render(painter, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
        painter.end()
        self._render_cache[key] = pix
        while len(self._render_cache) > 12:
            self._render_cache.pop(next(iter(self._render_cache)))
        return pix

    def prefetch_slide(
        self,
        doc: SermonDocument,
        slide: Slide,
        *,
        prepare_anims: bool = True,
    ):
        """预解码资源并缓存整页位图。"""
        w, h = doc.canvas_size()
        bg = slide.background
        if bg.type == "image" and bg.value:
            pix = load_pixmap(bg.value, self._assets_root)
            if pix is not None and not pix.isNull():
                scaled_pixmap(pix, w, h, fit=bg.fit or "cover", smooth=False)
        for element in slide.elements:
            if element.type != "image" or not element.content:
                continue
            pix = load_pixmap(element.content, self._assets_root)
            if pix is not None and not pix.isNull():
                scaled_pixmap(
                    pix,
                    max(1, int(element.w)),
                    max(1, int(element.h)),
                    smooth=False,
                )
        self.render_slide_pixmap(doc, slide, prepare_anims=prepare_anims)

    def snapshot_current(self):
        """空闲时记下当前画面，下次换页当旧图，避免按键时 grab。"""
        if self._hold_item is not None or self._page_anim is not None:
            return
        pix = self.grab_slide_pixmap()
        if pix is not None and not pix.isNull():
            self._old_snap = pix

    def take_old_snapshot(self) -> QPixmap:
        """只返回空闲时记下的图，按键时不再 grab 全屏。"""
        if not self._old_snap.isNull():
            return QPixmap(self._old_snap)
        return QPixmap()

    def set_old_snapshot(self, pix: QPixmap):
        if pix is not None and not pix.isNull():
            self._old_snap = pix

    def hold_pixmap(self, pix: QPixmap):
        """用位图盖住舞台，下面可安全重建。"""
        self.release_hold()
        if pix is None or pix.isNull():
            return
        item = QGraphicsPixmapItem(pix)
        item.setZValue(100010)
        item.setTransformationMode(Qt.TransformationMode.FastTransformation)
        br = item.boundingRect()
        if br.width() > 1 and abs(br.width() - self._logical_w) > 2:
            item.setScale(self._logical_w / br.width())
        self._scene.addItem(item)
        self._hold_item = item

    def release_hold(self):
        if self._hold_item is not None:
            if self._hold_item.scene() is not None:
                self._scene.removeItem(self._hold_item)
            self._hold_item = None
        if self._new_base_item is not None:
            if self._new_base_item.scene() is not None:
                self._scene.removeItem(self._new_base_item)
            self._new_base_item = None
        if self._pending_hot is not None and self._page_anim is None:
            QTimer.singleShot(0, self.flush_pending_hot)

    def flush_pending_hot(self):
        pending = self._pending_hot
        if pending is None:
            return
        if self._page_anim is not None or self._hold_item is not None:
            return
        self._pending_hot = None
        self._hot_flush_timer.stop()
        doc, slide, cursor = pending
        self.hot_refresh(doc, slide, anim_cursor=int(cursor))

    def _force_flush_pending_hot(self):
        if self._pending_hot is None:
            return
        self.stop_animations(apply_end=False)
        self._stop_page_transition(apply_end=False)
        self.release_hold()
        self.flush_pending_hot()

    def _prepare_entrance(self, item: QGraphicsItem, element: Element, slide: Slide):
        self._prepare_entrance_item(item, element, slide, self._targets)

    def _prepare_entrance_item(
        self,
        item: QGraphicsItem,
        element: Element,
        slide: Slide,
        targets: dict[str, QPointF],
    ):
        """PPT 式：有入场的元素先完全不可见，按键后再出现。"""
        step = next((a for a in slide.sorted_animations() if a.element_id == element.id), None)
        if step is None:
            return
        kind = step.kind
        target = targets[element.id]
        item.setOpacity(0.0)
        item.setVisible(False)
        item.setScale(1.0)
        if kind.startswith("wipe-"):
            if targets is self._targets:
                item.setOpacity(1.0)
                item.setVisible(True)
                self._set_wipe_progress(element.id, item, kind, 0.0)
            else:
                # 离屏预渲染：擦除起点先藏住
                item.setOpacity(0.0)
                item.setVisible(False)
                item.setPos(target)
        elif kind == "fade":
            item.setPos(target)
        elif kind == "fly-up":
            item.setPos(target.x(), target.y() + FLY_OFFSET)
        elif kind == "fly-down":
            item.setPos(target.x(), target.y() - FLY_OFFSET)
        elif kind == "fly-left":
            item.setPos(target.x() + FLY_OFFSET, target.y())
        elif kind == "fly-right":
            item.setPos(target.x() - FLY_OFFSET, target.y())
        elif kind == "zoom":
            item.setTransformOriginPoint(item.boundingRect().center())
            item.setScale(0.15)
            item.setPos(target)
        else:
            item.setPos(target)

    def reveal_all(self):
        """立刻显示全部最终态（热更新 / 跳过动画）。"""
        self.stop_animations(apply_end=False)
        for eid, item in list(self._items.items()):
            self._release_wipe_host(eid, item)
            target = self._targets.get(eid)
            if target is not None:
                item.setPos(target)
            item.setVisible(True)
            item.setOpacity(1.0)
            item.setScale(1.0)
            if self._slide:
                for el in self._slide.elements:
                    if el.id == eid:
                        item.setRotation(el.rotation)
                        break

    def stop_animations(self, apply_end: bool = True):
        running = list(self._running)
        self._running.clear()
        for anim in running:
            if apply_end:
                anim.setCurrentTime(anim.duration())
            anim.stop()

    def play_steps(self, steps: list[AnimStep]) -> int:
        """同批并行播放（与上一动画同时）；先结束上一批。"""
        if not steps:
            return 0
        self.stop_animations(apply_end=True)
        n = 0
        for step in steps:
            if self._start_step(step):
                n += 1
        return n

    def _start_step(self, step: AnimStep) -> bool:
        item = self._items.get(step.element_id)
        if item is None:
            return False
        eid = step.element_id
        target = self._targets.get(eid, item.pos())
        duration = max(50, int(step.duration_ms))
        kind = step.kind

        item.setVisible(False)
        item.setOpacity(0.0)
        self._release_wipe_host(eid, item)
        if kind.startswith("fly-"):
            if kind == "fly-up":
                start = QPointF(target.x(), target.y() + FLY_OFFSET)
            elif kind == "fly-down":
                start = QPointF(target.x(), target.y() - FLY_OFFSET)
            elif kind == "fly-left":
                start = QPointF(target.x() + FLY_OFFSET, target.y())
            else:
                start = QPointF(target.x() - FLY_OFFSET, target.y())
            item.setPos(start)
            item.setScale(1.0)
        elif kind == "zoom":
            item.setPos(target)
            item.setTransformOriginPoint(item.boundingRect().center())
            item.setScale(0.15)
        elif kind.startswith("wipe-"):
            item.setScale(1.0)
            item.setOpacity(1.0)
            self._set_wipe_progress(eid, item, kind, 0.0)
        else:
            item.setPos(target)
            item.setScale(1.0)

        item.setVisible(True)

        anims: list[QVariantAnimation] = []

        if kind.startswith("wipe-"):
            wipe = QVariantAnimation(self)
            wipe.setDuration(duration)
            wipe.setEasingCurve(QEasingCurve.Type.InOutQuad)
            wipe.setStartValue(0.0)
            wipe.setEndValue(1.0)
            wipe.valueChanged.connect(
                lambda v, i=item, k=kind, e=eid: self._set_wipe_progress(e, i, k, float(v))
            )
            anims.append(wipe)
        else:
            fade = QVariantAnimation(self)
            fade.setDuration(duration)
            fade.setEasingCurve(QEasingCurve.Type.OutCubic)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.valueChanged.connect(lambda v, it=item: it.setOpacity(float(v)))
            anims.append(fade)

            if kind.startswith("fly-"):
                move = QVariantAnimation(self)
                move.setDuration(duration)
                move.setEasingCurve(QEasingCurve.Type.OutCubic)
                move.setStartValue(item.pos())
                move.setEndValue(target)
                move.valueChanged.connect(lambda v, it=item: it.setPos(v))
                anims.append(move)
            elif kind == "zoom":
                zoom = QVariantAnimation(self)
                zoom.setDuration(duration)
                zoom.setEasingCurve(QEasingCurve.Type.OutBack)
                zoom.setStartValue(0.15)
                zoom.setEndValue(1.0)
                zoom.valueChanged.connect(lambda v, it=item: it.setScale(float(v)))
                anims.append(zoom)

        pending = {"n": len(anims)}

        def _done():
            pending["n"] -= 1
            if pending["n"] > 0:
                return
            for a in anims:
                if a in self._running:
                    self._running.remove(a)
            self._release_wipe_host(eid, item)
            item.setVisible(True)
            item.setOpacity(1.0)
            item.setPos(target)
            item.setScale(1.0)
            self.anim_finished.emit()

        for a in anims:
            self._running.append(a)
            a.finished.connect(_done)
            a.start()
        return True

    def grab_slide_pixmap(self) -> QPixmap:
        vp = self.viewport()
        if vp is None or vp.width() < 8 or vp.height() < 8:
            return QPixmap()
        return vp.grab()

    def play_dual_pixmap_transition(
        self,
        kind: str,
        duration_ms: int,
        old_pix: QPixmap,
        new_pix: QPixmap,
        *,
        forward: bool = True,
        on_done=None,
    ) -> bool:
        """双图切换：不拆场景内容逻辑，只播两张位图。结束后由 on_done 盖住再建场景。"""
        self._stop_page_transition(apply_end=False)
        if old_pix is None or old_pix.isNull() or new_pix is None or new_pix.isNull():
            if on_done:
                on_done()
            return False
        # 先盖新图，再盖旧图做过渡；下方旧场景可暂留
        self.release_hold()
        base = QGraphicsPixmapItem(new_pix)
        base.setZValue(99990)
        base.setTransformationMode(Qt.TransformationMode.FastTransformation)
        br = base.boundingRect()
        if br.width() > 1 and abs(br.width() - self._logical_w) > 2:
            base.setScale(self._logical_w / br.width())
        self._scene.addItem(base)
        self._new_base_item = base

        overlay = QGraphicsPixmapItem(old_pix)
        overlay.setTransformationMode(Qt.TransformationMode.FastTransformation)
        overlay.setZValue(100000)
        overlay.setPos(0, 0)
        overlay.setOpacity(1.0)
        obr = overlay.boundingRect()
        if obr.width() > 1 and abs(obr.width() - self._logical_w) > 2:
            overlay.setScale(self._logical_w / obr.width())

        host = None
        if kind == "wipe":
            host = QGraphicsRectItem(0, 0, self._logical_w, self._logical_h)
            host.setPen(QPen(Qt.PenStyle.NoPen))
            host.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            host.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            host.setZValue(100000)
            self._scene.addItem(host)
            overlay.setParentItem(host)
        else:
            self._scene.addItem(overlay)

        self._page_overlay = overlay
        self._page_wipe_host = host
        self._page_done = on_done
        w, h = float(self._logical_w), float(self._logical_h)

        if not kind or kind in ("", "none") or int(duration_ms) < 40:
            self._stop_page_transition(apply_end=True)
            return False

        dur = max(80, int(duration_ms))
        anim = QVariantAnimation(self)
        anim.setDuration(dur)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        if kind in ("fade", "smooth"):
            anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        else:
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        def _tick(v):
            t = float(v)
            if kind in ("fade", "smooth"):
                overlay.setOpacity(max(0.0, 1.0 - t))
            elif kind == "push":
                overlay.setPos((-w if forward else w) * t, 0)
            elif kind == "wipe":
                if host is None:
                    return
                if forward:
                    host.setRect(0, 0, max(1.0, w * (1.0 - t)), h)
                else:
                    host.setRect(w * t, 0, max(1.0, w * (1.0 - t)), h)
            else:
                overlay.setOpacity(max(0.0, 1.0 - t))

        def _finish():
            self._stop_page_transition(apply_end=True)

        anim.valueChanged.connect(_tick)
        anim.finished.connect(_finish)
        self._page_anim = anim
        anim.start()
        return True

    def _stop_page_transition(self, apply_end: bool = True):
        anim = self._page_anim
        self._page_anim = None
        cb = self._page_done
        self._page_done = None
        if anim is not None:
            anim.stop()
        overlay = self._page_overlay
        host = self._page_wipe_host
        self._page_overlay = None
        self._page_wipe_host = None
        if overlay is not None and overlay.scene() is not None:
            self._scene.removeItem(overlay)
        if host is not None and host.scene() is not None:
            self._scene.removeItem(host)
        # 过渡结束：把新图升为 hold，供下面重建
        if self._new_base_item is not None:
            pix = self._new_base_item.pixmap()
            if self._new_base_item.scene() is not None:
                self._scene.removeItem(self._new_base_item)
            self._new_base_item = None
            if apply_end and not pix.isNull():
                self.hold_pixmap(pix)
        if apply_end and cb:
            cb()

    @staticmethod
    def _item_size(item: QGraphicsItem) -> tuple[float, float]:
        r = item.boundingRect()
        return max(1.0, r.width()), max(1.0, r.height())

    def _ensure_wipe_host(self, eid: str, item: QGraphicsItem) -> QGraphicsRectItem:
        """用会裁剪子项的矩形父节点做擦除（兼容文本/图片，不依赖 setClipPath）。"""
        target = self._targets.get(eid, item.scenePos())
        host = self._wipe_hosts.get(eid)
        if host is None:
            host = QGraphicsRectItem()
            host.setPen(QPen(Qt.PenStyle.NoPen))
            host.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            host.setFlag(QGraphicsItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
            host.setZValue(item.zValue())
            self._scene.addItem(host)
            self._wipe_hosts[eid] = host
        host.setPos(target)
        if item.parentItem() is not host:
            item.setParentItem(host)
            item.setPos(0, 0)
        return host

    def _set_wipe_progress(self, eid: str, item: QGraphicsItem, kind: str, t: float):
        t = max(0.0, min(1.0, float(t)))
        host = self._ensure_wipe_host(eid, item)
        item.setPos(0, 0)
        w, h = self._item_size(item)
        eps = 0.01
        if t <= 0.001:
            host.setRect(0, 0, eps, eps)
        elif kind == "wipe-down":
            # 自上而下揭开
            host.setRect(0, 0, w, max(eps, h * t))
        elif kind == "wipe-up":
            # 自下而上揭开
            host.setRect(0, h * (1.0 - t), w, max(eps, h * t))
        elif kind == "wipe-right":
            # 自左而右揭开
            host.setRect(0, 0, max(eps, w * t), h)
        elif kind == "wipe-left":
            # 自右而左揭开
            host.setRect(w * (1.0 - t), 0, max(eps, w * t), h)
        else:
            host.setRect(0, 0, w, max(eps, h * t))

    def _release_wipe_host(self, eid: str, item: QGraphicsItem):
        host = self._wipe_hosts.pop(eid, None)
        target = self._targets.get(eid)
        if item.parentItem() is not None:
            item.setParentItem(None)
        if target is not None:
            item.setPos(target)
        if host is not None and host.scene() is not None:
            self._scene.removeItem(host)

    def apply_played_steps(self, steps: list[AnimStep]):
        """把已播过的入场动画立刻落到终态（切回讲篇频道时用）。"""
        for step in steps:
            item = self._items.get(step.element_id)
            if item is None:
                continue
            self._release_wipe_host(step.element_id, item)
            target = self._targets.get(step.element_id, item.pos())
            item.setPos(target)
            item.setVisible(True)
            item.setOpacity(1.0)
            item.setScale(1.0)

    def _apply_background(self, slide: Slide):
        if self._bg_item is None:
            return
        if self._bg_image_item is not None:
            self._scene.removeItem(self._bg_image_item)
            self._bg_image_item = None
        img = self._paint_background_on(
            self._scene, self._bg_item, slide, self._logical_w, self._logical_h
        )
        self._bg_image_item = img

    def _paint_background_on(
        self,
        scene: QGraphicsScene,
        bg_item: QGraphicsRectItem,
        slide: Slide,
        w: int,
        h: int,
    ) -> QGraphicsPixmapItem | None:
        bg = slide.background
        if bg.type == "image" and bg.value:
            pix = load_pixmap(bg.value, self._assets_root)
            if pix is not None and not pix.isNull():
                bg_item.setBrush(QBrush(QColor("#000000")))
                item = QGraphicsPixmapItem()
                item.setZValue(-999)
                fit = bg.fit or "cover"
                scaled = scaled_pixmap(pix, w, h, fit=fit, smooth=False)
                item.setPixmap(scaled)
                item.setPos((w - scaled.width()) / 2, (h - scaled.height()) / 2)
                item.setTransformationMode(Qt.TransformationMode.FastTransformation)
                scene.addItem(item)
                return item
        color = QColor(bg.value) if bg.value else QColor("#1A1A2E")
        if not color.isValid():
            color = QColor("#1A1A2E")
        bg_item.setBrush(QBrush(color))
        return None

    def _add_element(self, element: Element) -> QGraphicsItem | None:
        return self._make_element_item(element, self._scene)

    def _make_element_item(
        self, element: Element, scene: QGraphicsScene
    ) -> QGraphicsItem | None:
        if element.type == "text":
            item = QGraphicsTextItem()
            raw = element.content or ""
            item.setPlainText("" if is_text_placeholder(raw) else raw)
            style = element.style
            font = QFont(style.font_family or "微软雅黑")
            font.setPixelSize(max(8, int(style.font_size)))
            font.setBold(style.bold)
            font.setItalic(style.italic)
            item.setFont(font)
            color = QColor(style.color)
            if color.isValid():
                color.setAlphaF(max(0.0, min(1.0, float(getattr(style, "opacity", 1.0)))))
            item.setDefaultTextColor(color)
            align = {
                "left": Qt.AlignmentFlag.AlignLeft,
                "center": Qt.AlignmentFlag.AlignHCenter,
                "right": Qt.AlignmentFlag.AlignRight,
            }.get(style.align, Qt.AlignmentFlag.AlignLeft)
            option = item.document().defaultTextOption()
            option.setAlignment(align)
            item.document().setDefaultTextOption(option)
            if getattr(style, "wrap", True):
                item.setTextWidth(max(40.0, element.w))
            else:
                item.setTextWidth(-1)
            apply_text_line_spacing(item, getattr(style, "line_spacing", 120))
            item.setPos(element.x, element.y)
            item.setRotation(element.rotation)
            item.setZValue(element.z)
            scene.addItem(item)
            return item
        if element.type == "image":
            pix = load_pixmap(element.content, self._assets_root)
            if pix is None or pix.isNull():
                pix = QPixmap(max(1, int(element.w)), max(1, int(element.h)))
                pix.fill(QColor("#444444"))
            scaled = scaled_pixmap(
                pix, max(1, int(element.w)), max(1, int(element.h)), smooth=False
            )
            item = QGraphicsPixmapItem(scaled)
            item.setTransformationMode(Qt.TransformationMode.FastTransformation)
            item.setPos(element.x, element.y)
            item.setRotation(element.rotation)
            item.setZValue(element.z)
            scene.addItem(item)
            return item
        if element.type == "shape":
            kind = element.shape if element.shape in ("rect", "ellipse") else "rect"
            if kind == "ellipse":
                item = QGraphicsEllipseItem(0, 0, max(1.0, element.w), max(1.0, element.h))
            else:
                item = QGraphicsRectItem(0, 0, max(1.0, element.w), max(1.0, element.h))
            color = QColor(element.style.color or "#000000")
            if not color.isValid():
                color = QColor("#000000")
            color.setAlphaF(max(0.0, min(1.0, float(element.style.opacity))))
            item.setBrush(QBrush(color))
            item.setPen(QPen(Qt.PenStyle.NoPen))
            item.setPos(element.x, element.y)
            item.setRotation(element.rotation)
            item.setZValue(element.z)
            scene.addItem(item)
            return item
        return None

    def _fit_view(self):
        if self._logical_w <= 0:
            return
        self.fitInView(
            QRectF(0, 0, self._logical_w, self._logical_h),
            Qt.AspectRatioMode.KeepAspectRatio,
        )

    def set_wheel_pages(self, on: bool):
        """副屏禁止滚轮翻页；主屏预览仍可滚轮控场。"""
        self._wheel_pages = bool(on)

    def mousePressEvent(self, event):
        if self._preview_edit and event.button() == Qt.MouseButton.LeftButton:
            self.edit_requested.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if self._preview_edit:
            self.edit_requested.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def wheelEvent(self, event):
        if not self._wheel_pages:
            event.accept()
            return
        delta = event.angleDelta().y()
        if delta == 0:
            delta = event.pixelDelta().y()
        if delta == 0:
            event.accept()
            return
        now = QDateTime.currentMSecsSinceEpoch()
        if now - self._wheel_guard_ms < 180:
            event.accept()
            return
        self._wheel_guard_ms = now
        self.page_step_requested.emit(-1 if delta > 0 else 1)
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_view()
