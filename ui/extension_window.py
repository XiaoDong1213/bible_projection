from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal
from .scripture_display import ScriptureDisplay


class ExtensionWindow(QWidget):
    """负责副屏显示经文，并与主屏保持同步。"""

    close_requested = pyqtSignal()

    def __init__(self, topmost=True):
        super().__init__()
        self.setWindowTitle("圣经投影")
        self._topmost = bool(topmost)
        self._apply_window_flags()
        self.scripture_display = ScriptureDisplay()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.scripture_display)
        self.current_data = None
        self._main_scroll_fraction = 0.0

    def _apply_window_flags(self):
        """设置无边框、工具窗口和置顶属性。"""
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self._topmost:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    def apply_topmost(self, on):
        """切换窗口置顶状态。"""
        self._topmost = bool(on)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self._topmost)

    def keyPressEvent(self, event):
        # Esc 关闭副屏窗口
        if event.key() == Qt.Key.Key_Escape:
            self.close_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def update_scripture(self, book_name, chapter, start, end, verses):
        """更新副屏经文并同步滚动位置。"""
        self.current_data = (book_name, chapter, start, end, list(verses or []))
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)
        self.force_sync_scroll()

    def update_from_selection(self, selection, verses):
        """按多段选择更新副屏。"""
        self.current_data = (
            selection.book,
            selection.primary_chapter,
            selection.primary_start,
            selection.primary_end,
            list(verses or []),
        )
        self.scripture_display.set_from_selection(selection, verses)
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

    def closeEvent(self, event):
        self.close_requested.emit()
        super().closeEvent(event)
