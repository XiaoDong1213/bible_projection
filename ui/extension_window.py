# 第二屏幕扩展窗口：完全跟随主屏滚动
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from .scripture_display import ScriptureDisplay

class ExtensionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("圣经投影")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.scripture_display = ScriptureDisplay()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scripture_display)
        self.current_data = None
        self._main_fraction = 0.0

    def update_scripture(self, book_name, chapter, start, end, verses):
        self.current_data = (book_name, chapter, start, end, list(verses or []))
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)
        self.set_scroll_fraction(self._main_fraction)

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        # 扩展屏禁止独立滚动，滚动位置只由主屏决定。
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        self.scripture_display.set_scroll_position(value)

    def set_scroll_fraction(self, fraction):
        try:
            self._main_fraction = max(0.0, min(1.0, float(fraction)))
        except (TypeError, ValueError):
            self._main_fraction = 0.0
        self.scripture_display.set_scroll_fraction(self._main_fraction)

    def sync_from_main(self, main_display):
        # 直接读取主屏当前滚动比例，并立即设置扩展屏滚动条。
        # 主屏和扩展屏使用相同的排版基准，因此同一比例对应同一经文位置。
        fraction = main_display.scroll_fraction()
        self.set_scroll_fraction(fraction)

    def scroll_by(self, delta):
        # 扩展屏不接受独立滚动操作。
        return
