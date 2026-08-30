# 第二屏幕扩展窗口
# 扩展屏只负责显示，滚动位置和滚动速度完全由主屏控制。
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from .scripture_display import ScriptureDisplay

class ExtensionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("圣经投影")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.scripture_display = ScriptureDisplay()
        layout = QVBoxLayout(); layout.setContentsMargins(0, 0, 0, 0); layout.addWidget(self.scripture_display); self.setLayout(layout)
        self.current_data = None

    def update_scripture(self, book_name, chapter, start, end, verses):
        self.current_data = (book_name, chapter, start, end, list(verses or []))
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        self.scripture_display.set_scroll_position(value)

    def set_scroll_fraction(self, fraction):
        self.scripture_display.set_scroll_fraction(fraction)

    def scroll_by(self, delta):
        self.scripture_display.scroll_by(delta)
