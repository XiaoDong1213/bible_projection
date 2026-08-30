# 第二屏幕扩展窗口
# 功能：全屏显示在第二屏，可置顶，与主界面严格同步

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from .scripture_display import ScriptureDisplay


class ExtensionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("圣经投影")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.scripture_display = ScriptureDisplay()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scripture_display)
        self.setLayout(layout)
        self.current_data = None

    def update_scripture(self, book_name, chapter, start, end, verses):
        self.current_data = (book_name, chapter, start, end, verses)
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        # 扩展屏不单独滚动，避免与主屏产生速度和位置偏差。
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        self.scripture_display.set_scroll_position(value)

    def scroll_by(self, delta):
        self.scripture_display.scroll_by(delta)
