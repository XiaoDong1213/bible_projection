# 第二屏幕扩展窗口：按主屏实际阅读位置同步
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
        self._main_anchor = 0

    def update_scripture(self, book_name, chapter, start, end, verses):
        self.current_data = (book_name, chapter, start, end, list(verses or []))
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)
        self.set_scroll_anchor(self._main_anchor)

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        self.scripture_display.set_scroll_position(value)

    def set_scroll_fraction(self, fraction):
        # 保留兼容接口；新的同步不再依赖滚动比例。
        self.scripture_display.set_scroll_fraction(fraction)

    def set_scroll_anchor(self, anchor):
        try:
            self._main_anchor = max(0, int(anchor))
        except (TypeError, ValueError):
            self._main_anchor = 0
        self.scripture_display.set_scroll_anchor(self._main_anchor)

    def sync_from_main(self, main_display):
        # 关键修复：不再比较两个不同窗口的 scrollbar maximum。
        # 直接同步“当前屏幕顶部对应的文档字符位置”，因此主屏滚到哪里，
        # 扩展屏就定位到同一份经文的相同位置。
        anchor = main_display.get_scroll_anchor()
        self.set_scroll_anchor(anchor)

    def scroll_by(self, delta):
        return
