# ui/extension_window.py
# 第二屏幕扩展窗口
# 功能：全屏显示在第二屏，可置顶，与主界面同步

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt
from .scripture_display import ScriptureDisplay


class ExtensionWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("圣经投影")

        # 窗口标志：无边框 + 置顶 + 工具窗口（任务栏不显示）
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        # 经文显示控件
        self.scripture_display = ScriptureDisplay()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scripture_display)
        self.setLayout(layout)

        self.current_data = None  # 缓存当前经文数据

    def update_scripture(self, book_name, chapter, start, end, verses):
        """更新经文内容"""
        self.current_data = (book_name, chapter, start, end, verses)
        self.scripture_display.set_scripture(book_name, chapter, start, end, verses)

    def apply_settings(self, settings):
        """应用显示设置"""
        self.scripture_display.apply_settings(settings)

    def set_scroll_speed(self, speed):
        """设置滚动速度"""
        self.scripture_display.set_scroll_speed(speed)

    def scroll_by(self, delta):
        """手动滚动"""
        self.scripture_display.scroll_by(delta)
