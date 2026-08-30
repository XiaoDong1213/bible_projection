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
        """更新经文内容，并从顶部开始显示。"""
        self.current_data = (book_name, chapter, start, end, verses)
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        """扩展屏不独立计时滚动，统一由主屏滚动后同步位置。"""
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        """设置扩展屏滚动条位置，兼容主窗口同步调用。"""
        self.scripture_display.set_scroll_position(value)

    def set_scroll_fraction(self, fraction):
        """按滚动比例同步，避免两块屏幕可滚动范围不同造成错位。"""
        self.scripture_display.set_scroll_fraction(fraction)

    def scroll_by(self, delta):
        """保留手动滚动接口。"""
        self.scripture_display.scroll_by(delta)
