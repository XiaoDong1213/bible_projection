# 第二屏幕扩展窗口：只跟随主屏滚动
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
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.scripture_display)
        self.current_data = None
        self._main_anchor = 0

    def update_scripture(self, book_name, chapter, start, end, verses):
        self.current_data=(book_name,chapter,start,end,list(verses or []))
        self.scripture_display.set_scripture(book_name,chapter,start,end,verses)
        self.set_scroll_anchor(self._main_anchor)

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        # 扩展屏禁止独立自动滚动，只跟随主屏
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        self.scripture_display.set_scroll_position(value)

    def set_scroll_anchor(self, anchor):
        try:
            self._main_anchor=max(0,int(anchor))
        except (TypeError,ValueError):
            self._main_anchor=0
        self.scripture_display.set_scroll_anchor(self._main_anchor)

    def sync_from_main(self, main_display):
        self.set_scroll_anchor(main_display.get_scroll_anchor())

    def set_scroll_fraction(self, fraction):
        # 兼容旧接口；新的主窗口同步不再依赖百分比
        self.scripture_display.set_scroll_fraction(fraction)

    def scroll_by(self, delta):
        # 扩展屏不作为滚动控制源
        return
