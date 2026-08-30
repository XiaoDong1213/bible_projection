# 第二屏幕扩展窗口：滚动位置由主屏强制驱动
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
        self._main_scroll_value = 0

    def update_scripture(self, book_name, chapter, start, end, verses):
        self.current_data = (book_name, chapter, start, end, list(verses or []))
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)
        self.force_sync_scroll()

    def apply_settings(self, settings):
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        # 扩展屏绝不自己滚动。
        self.scripture_display.set_scroll_speed(0)

    def set_scroll_position(self, value):
        self._main_scroll_value = int(value)
        self.scripture_display.force_scroll_to(self._main_scroll_value)

    def force_sync_scroll(self, main_value=None, main_maximum=None):
        """由主屏强制设置扩展屏滚动条，不使用 QTextCursor/anchor。"""
        if main_value is not None:
            try:self._main_scroll_value = int(main_value)
            except (TypeError, ValueError):return
        bar = self.scripture_display.text_display.verticalScrollBar()
        if main_maximum is None:
            # 兼容旧调用：若未传主屏 maximum，则按保存值直接使用。
            target = self._main_scroll_value
        else:
            try:
                mm = max(0, int(main_maximum)); mv = max(0, int(self._main_scroll_value))
            except (TypeError, ValueError):
                return
            target = 0 if mm <= 0 else round((mv / mm) * bar.maximum())
        self.scripture_display.force_scroll_to(target)

    def sync_from_main(self, main_display):
        main_bar = main_display.text_display.verticalScrollBar()
        self.force_sync_scroll(main_bar.value(), main_bar.maximum())

    def set_scroll_fraction(self, fraction):
        self.scripture_display.set_scroll_fraction(fraction)

    def set_scroll_anchor(self, anchor):
        # 保留兼容接口，但不再用于双屏同步。
        self.scripture_display.set_scroll_anchor(anchor)

    def scroll_by(self, delta):
        return
