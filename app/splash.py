"""轻量启动页：仅图标 + 标题，无背景；文字带描边保证浅/深桌面都可读。"""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPen
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


_MIN_VISIBLE_MS = 400


class _OutlinedTitle(QLabel):
    """白字 + 深色描边，浅色壁纸上也能看清。"""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._fill = QColor("#F5F7FA")
        self._stroke = QColor(0, 0, 0, 180)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        font = QFont("Microsoft YaHei UI", 28)
        font.setBold(True)
        self.setFont(font)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        size = fm.size(0, self.text() or "Bible Pro")
        return QSize(size.width() + 8, size.height() + 8)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        text = self.text()
        fm = QFontMetrics(self.font())
        x = (self.width() - fm.horizontalAdvance(text)) // 2
        y = (self.height() + fm.ascent() - fm.descent()) // 2
        painter.setFont(self.font())
        painter.setPen(QPen(self._stroke))
        for dx, dy in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (1, -1),
            (-1, 1),
            (1, 1),
        ):
            painter.drawText(x + dx, y + dy, text)
        painter.setPen(QPen(self._fill))
        painter.drawText(x, y, text)


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
        self._shown_at = 0.0

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

        title = _OutlinedTitle("Bible Pro")
        title.setMinimumHeight(48)
        layout.addWidget(title)

        layout.addStretch(1)
        self._center_on_screen()

    def showEvent(self, event):
        super().showEvent(event)
        self._shown_at = time.monotonic()

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
        """主窗口显示后关闭启动页（保证最短可见时间，避免一闪而过）。"""

        def _close():
            self.close()
            self.deleteLater()
            if main_window is not None:
                main_window.raise_()
                main_window.activateWindow()

        elapsed_ms = int((time.monotonic() - self._shown_at) * 1000) if self._shown_at else 0
        remain = max(0, _MIN_VISIBLE_MS - elapsed_ms)
        if remain <= 0:
            _close()
        else:
            QTimer.singleShot(remain, _close)
