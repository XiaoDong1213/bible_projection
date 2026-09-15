"""轻量启动页：仅图标 + 标题，无背景。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon, QPixmap
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


_TITLE = "#E8EDF5"


class SplashScreen(QWidget):
    def __init__(self, icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("appSplash")
        self.setWindowTitle("Bible Pro")
        self.setFixedSize(360, 260)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setStyleSheet("background: transparent;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addStretch(1)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        icon_label.setStyleSheet("background: transparent;")
        if icon is not None and not icon.isNull():
            pix = icon.pixmap(96, 96)
            if not pix.isNull():
                icon_label.setPixmap(pix)
        layout.addWidget(icon_label)

        title = QLabel("Bible Pro")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        title.setStyleSheet(f"color: {_TITLE}; background: transparent;")
        font = QFont("Microsoft YaHei UI", 28)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        layout.addStretch(1)
        self._center_on_screen()

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )

    def finish(self, main_window):
        """主窗口显示后关闭启动页。"""
        self.close()
        self.deleteLater()
        if main_window is not None:
            main_window.raise_()
            main_window.activateWindow()
