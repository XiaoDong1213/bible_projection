"""副屏窗口：经文层 + 讲篇层。讲篇层不挂透明度特效，避免入场动画被缓存卡住。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QGridLayout,
    QLabel,
    QWidget,
)

from core.sermon.model import SermonDocument, Slide

from .scripture_display import ScriptureDisplay
from ui.sermon.player.stage import SlideStage


class ExtensionWindow(QWidget):
    """负责副屏显示经文 / 讲篇，并与主屏保持同步。"""

    close_requested = pyqtSignal()
    sermon_next_requested = pyqtSignal()
    sermon_prev_requested = pyqtSignal()
    sermon_stop_requested = pyqtSignal()
    scripture_channel_requested = pyqtSignal()

    FADE_MS = 400

    def __init__(self, topmost=True):
        super().__init__()
        self.setWindowTitle("圣经投影")
        self._topmost = bool(topmost)
        self._apply_window_flags()

        self._mode = "scripture"  # scripture | sermon
        self._animating = False
        self._fade_ms = self.FADE_MS

        host = QWidget(self)
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.scripture_display = ScriptureDisplay()
        self.scripture_display.set_follow_only(True)
        self.slide_stage = SlideStage()
        self.slide_stage.set_wheel_pages(False)

        grid.addWidget(self.slide_stage, 0, 0)
        grid.addWidget(self.scripture_display, 0, 0)
        self._cover = QLabel()
        self._cover.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._cover.setScaledContents(True)
        self._cover.hide()
        grid.addWidget(self._cover, 0, 0)
        self.scripture_display.raise_()

        outer = QGridLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(host, 0, 0)

        self.slide_stage.setGraphicsEffect(None)
        self.slide_stage.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.slide_stage.hide()
        self.slide_stage.page_step_requested.connect(self._on_stage_wheel)

        self._cover_fx = QGraphicsOpacityEffect(self._cover)
        self._cover.setGraphicsEffect(self._cover_fx)
        self._cover_fx.setOpacity(0.0)
        self._fade_cover = QPropertyAnimation(self._cover_fx, b"opacity", self)
        self._fade_cover.setDuration(self.FADE_MS)
        self._fade_cover.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.current_data = None
        self._main_scroll_fraction = 0.0

    def _on_stage_wheel(self, delta: int):
        if self._mode != "sermon":
            return
        if delta > 0:
            self.sermon_next_requested.emit()
        elif delta < 0:
            self.sermon_prev_requested.emit()

    def wheelEvent(self, event):
        event.accept()

    def _apply_window_flags(self):
        """设置无边框、工具窗口和置顶属性。"""
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self._topmost:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def apply_topmost(self, on):
        self._topmost = bool(on)
        visible = self.isVisible()
        self._apply_window_flags()
        if visible:
            self.show()

    @property
    def display_mode(self) -> str:
        return self._mode

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            if self._mode == "sermon":
                self.sermon_stop_requested.emit()
            else:
                self.close_requested.emit()
            event.accept()
            return
        if self._mode == "sermon":
            if key in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Space, Qt.Key.Key_PageDown):
                self.sermon_next_requested.emit()
                event.accept()
                return
            if key in (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_PageUp, Qt.Key.Key_Backspace):
                self.sermon_prev_requested.emit()
                event.accept()
                return
        super().keyPressEvent(event)

    def update_scripture(self, book_name, chapter, start, end, verses):
        """更新副屏经文并同步滚动位置。"""
        self.current_data = (book_name, chapter, start, end, list(verses or []))
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)
        self.force_sync_scroll()

    def update_from_selection(self, selection, verses, reset_scroll=True):
        """按多段选择更新副屏。"""
        self.current_data = (
            selection.book,
            selection.primary_chapter,
            selection.primary_start,
            selection.primary_end,
            list(verses or []),
        )
        self.scripture_display.set_from_selection(
            selection, verses, reset_scroll=reset_scroll
        )
        if reset_scroll:
            self.force_sync_scroll()

    def apply_settings(self, settings):
        """应用经文显示设置。"""
        self.scripture_display.apply_settings(settings)
        if settings:
            self.set_channel_fade_ms(settings.get("channel_fade_ms", self.FADE_MS))

    def set_channel_fade_ms(self, ms) -> int:
        try:
            value = int(ms)
        except (TypeError, ValueError):
            value = self.FADE_MS
        self._fade_ms = max(0, min(2000, value))
        self._fade_cover.setDuration(max(1, self._fade_ms))
        return self._fade_ms

    def set_scroll_speed(self, speed):
        # 副屏不独立滚动，只跟随主屏位置
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        """设置副屏滚动位置。"""
        self.scripture_display.force_scroll_to(value)

    def force_sync_scroll(self, main_fraction=None):
        """根据主屏滚动比例更新副屏位置。"""
        if main_fraction is not None:
            try:
                self._main_scroll_fraction = max(0.0, min(1.0, float(main_fraction)))
            except (TypeError, ValueError):
                return
        self.scripture_display.set_scroll_fraction(self._main_scroll_fraction)

    def sync_from_main(self, main_display):
        """从主屏获取滚动比例并同步到副屏。"""
        self.force_sync_scroll(main_display.scroll_fraction())

    def set_scroll_fraction(self, fraction):
        """设置副屏的滚动比例。"""
        self.force_sync_scroll(fraction)

    def show_sermon_slide(
        self,
        doc: SermonDocument,
        slide: Slide,
        assets_root: Path | str | None,
        *,
        prepare_anims: bool = True,
    ):
        """刷新讲篇当前页。prepare_anims 控制是否隐藏待入场元素。"""
        root = Path(assets_root) if assets_root else None
        self.slide_stage.set_assets_root(root)
        self.slide_stage.show_slide(doc, slide, prepare_anims=prepare_anims)
        self.slide_stage.lower()
        self._cover.raise_()

    def showing_sermon_slide_id(self) -> str | None:
        slide = getattr(self.slide_stage, "_slide", None)
        return getattr(slide, "id", None) if slide is not None else None

    def _stop_channel_fade(self):
        self._fade_cover.stop()
        try:
            self._fade_cover.finished.disconnect()
        except TypeError:
            pass
        self._animating = False
        self._cover.hide()
        self._cover.clear()
        self._cover_fx.setOpacity(0.0)

    def _snap_to_mode(self, mode: str):
        self._stop_channel_fade()
        self._mode = mode
        if mode == "sermon":
            self.scripture_display.hide()
            self.slide_stage.show()
            self.slide_stage.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
            )
            self.slide_stage.lower()
        else:
            self.scripture_display.show()
            self.scripture_display.raise_()
            self.slide_stage.hide()
            self.slide_stage.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            self.force_sync_scroll()

    def _grab_layer(self, widget):
        """截当前层；空图则整窗再抓一次，避免淡化被跳过。"""
        pix = None
        if widget is not None and widget.isVisible() and widget.width() >= 8:
            widget.repaint()
            pix = widget.grab()
        if pix is not None and not pix.isNull():
            return pix
        self.repaint()
        return self.grab()

    def _arm_cover(self, pixmap) -> bool:
        if pixmap is None or pixmap.isNull():
            return False
        self._cover.setPixmap(pixmap)
        self._cover.setScaledContents(True)
        self._cover_fx.setOpacity(1.0)
        self._cover.show()
        self._cover.raise_()
        return True

    def _play_cover_fade(self, pixmap, on_done):
        if not self._arm_cover(pixmap):
            on_done()
            return
        self._animating = True
        self._fade_cover.setDuration(max(1, int(self._fade_ms)))
        self._fade_cover.setStartValue(1.0)
        self._fade_cover.setEndValue(0.0)

        def _finished():
            self._animating = False
            self._cover.hide()
            self._cover.clear()
            try:
                self._fade_cover.finished.disconnect(_finished)
            except TypeError:
                pass
            on_done()

        self._fade_cover.finished.connect(_finished)
        self._fade_cover.start()

    def set_display_mode(self, mode: str, animate: bool = True):
        """先盖旧画面，再换层，最后淡出盖布。"""
        if mode not in ("scripture", "sermon"):
            return
        animate = bool(animate) and self._fade_ms >= 40
        if mode == self._mode and not self._animating:
            self._snap_to_mode(mode)
            return

        old = self._mode
        if not animate or old == mode:
            self._snap_to_mode(mode)
            return

        if mode == "sermon":
            pix = self._grab_layer(self.scripture_display)
            self._stop_channel_fade()
            if not self._arm_cover(pix):
                self._snap_to_mode(mode)
                return
            self.slide_stage.setGraphicsEffect(None)
            self.slide_stage.show()
            self.slide_stage.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
            )
            self.slide_stage.lower()
            self.scripture_display.hide()
            self._cover.raise_()
            self._mode = "sermon"
            self._play_cover_fade(pix, lambda: None)
            return

        src = self.slide_stage if self.slide_stage.isVisible() else self.scripture_display
        pix = self._grab_layer(src)
        self._stop_channel_fade()
        if not self._arm_cover(pix):
            self._snap_to_mode(mode)
            return
        self.scripture_display.show()
        self.scripture_display.raise_()
        self._cover.raise_()
        self._mode = "scripture"

        def _after():
            self.slide_stage.hide()
            self.slide_stage.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            self.force_sync_scroll()

        self._play_cover_fade(pix, _after)

    def closeEvent(self, event):
        self.close_requested.emit()
        super().closeEvent(event)
