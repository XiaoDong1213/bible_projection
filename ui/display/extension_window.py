"""副屏窗口：经文层 + 讲篇层。讲篇层不挂透明度特效，避免入场动画被缓存卡住。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGraphicsOpacityEffect,
    QGridLayout,
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

    FADE_MS = 220

    def __init__(self, topmost=True):
        super().__init__()
        self.setWindowTitle("圣经投影")
        self._topmost = bool(topmost)
        self._apply_window_flags()

        self._mode = "scripture"  # scripture | sermon
        self._animating = False

        host = QWidget(self)
        grid = QGridLayout(host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)

        self.scripture_display = ScriptureDisplay()
        self.slide_stage = SlideStage()

        grid.addWidget(self.scripture_display, 0, 0)
        grid.addWidget(self.slide_stage, 0, 0)
        self.slide_stage.raise_()

        outer = QGridLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(host, 0, 0)

        # 只给经文层做淡入淡出；讲篇舞台挂 OpacityEffect 会导致动画不刷新
        self._scripture_fx = QGraphicsOpacityEffect(self.scripture_display)
        self.scripture_display.setGraphicsEffect(self._scripture_fx)
        self._scripture_fx.setOpacity(1.0)
        self.slide_stage.setGraphicsEffect(None)
        self.slide_stage.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.slide_stage.hide()
        self.slide_stage.page_step_requested.connect(self._on_stage_wheel)

        self._fade_scripture = QPropertyAnimation(self._scripture_fx, b"opacity", self)
        self._fade_scripture.setDuration(self.FADE_MS)

        self.current_data = None
        self._main_scroll_fraction = 0.0

    def _on_stage_wheel(self, delta: int):
        if self._mode != "sermon":
            return
        if delta > 0:
            self.sermon_next_requested.emit()
        elif delta < 0:
            self.sermon_prev_requested.emit()

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
                self.scripture_channel_requested.emit()
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

    def set_display_mode(self, mode: str, animate: bool = True):
        """切换 scripture / sermon。讲篇层直接显隐，不挂透明度特效。"""
        if mode not in ("scripture", "sermon"):
            return
        if mode == self._mode and not self._animating:
            if mode == "sermon":
                self.slide_stage.setGraphicsEffect(None)
                self.slide_stage.show()
                self.slide_stage.raise_()
                self._scripture_fx.setOpacity(0.0)
            return

        target = mode
        self._fade_scripture.stop()

        if target == "sermon":
            self.slide_stage.setGraphicsEffect(None)
            self.slide_stage.show()
            self.slide_stage.raise_()
            self.slide_stage.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self._mode = "sermon"
            if not animate:
                self._scripture_fx.setOpacity(0.0)
                return
            self._animating = True
            self._fade_scripture.setStartValue(self._scripture_fx.opacity())
            self._fade_scripture.setEndValue(0.0)

            def _done_sermon():
                self._animating = False
                try:
                    self._fade_scripture.finished.disconnect(_done_sermon)
                except TypeError:
                    pass

            self._fade_scripture.finished.connect(_done_sermon)
            self._fade_scripture.start()
        else:
            self._mode = "scripture"
            if not animate:
                self._scripture_fx.setOpacity(1.0)
                self.slide_stage.hide()
                self.slide_stage.clear_stage()
                self.slide_stage.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                self.force_sync_scroll()
                return
            self._animating = True
            self.slide_stage.show()
            self._fade_scripture.setStartValue(self._scripture_fx.opacity())
            self._fade_scripture.setEndValue(1.0)

            def _done_scripture():
                self._animating = False
                self.slide_stage.hide()
                self.slide_stage.clear_stage()
                self.slide_stage.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                self.force_sync_scroll()
                try:
                    self._fade_scripture.finished.disconnect(_done_scripture)
                except TypeError:
                    pass

            self._fade_scripture.finished.connect(_done_scripture)
            self._fade_scripture.start()

    def closeEvent(self, event):
        self.close_requested.emit()
        super().closeEvent(event)
