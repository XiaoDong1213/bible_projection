from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath
from PyQt6.QtWidgets import QApplication, QFrame, QWidget

from .stylesheet import build_stylesheet, theme_tokens, THEMES, search_panel_style


def strip_dwm_chrome(widget):
    """压掉 Windows 给顶层窗口叠的系统圆角与描边（黑/白框都来自这一层）。

    DWMWA_NCRENDERING_POLICY=2（DISABLED）：连非客户区渲染一起关掉，
    Win10/Win11 全版本有效；老版 Win11 不支持改边框色（34），但都支持这个。
    再配合 DONOTROUND 与 COLOR_NONE 双保险。"""
    try:
        import ctypes

        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        nc = ctypes.c_int(3)  # DWMWA_NCRENDERING_DISABLED
        dwm.DwmSetWindowAttribute(hwnd, 2, ctypes.byref(nc), 4)
        pref = ctypes.c_int(1)  # DWMWCP_DONOTROUND
        dwm.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(pref), 4)
        no_color = ctypes.c_int(0xFFFFFFFE)  # DWMWA_COLOR_NONE
        dwm.DwmSetWindowAttribute(hwnd, 34, ctypes.byref(no_color), 4)
    except Exception:
        pass


class DwmBorderlessCard(QFrame):
    """透明背景上的圆角浮层卡片（popup 语义）。

    不用 Qt.Popup——Qt6 会给 Popup 类型窗口（含 QMenu）自动套一层
    带直角边框的投影层，圆角外就是那圈框。改用 Frameless|Tool|StaysOnTop
    的干净组合，「点击外部关闭」用全局事件过滤器自己实现。"""

    def __init__(self, parent=None, radius=10):
        super().__init__(
            parent,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._radius = radius
        self._theme = "dark"
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def set_theme(self, theme):
        self._theme = theme if theme in ("dark", "light") else "dark"
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        # show 后窗口已 native 化，DWM 属性此时设置才有效
        strip_dwm_chrome(self)
        QApplication.instance().installEventFilter(self)

    def hideEvent(self, event):
        super().hideEvent(event)
        QApplication.instance().removeEventFilter(self)

    def eventFilter(self, obj, event):
        # popup 语义：点击浮层外任何地方都关闭（事件照常放行给下层控件）
        if event.type() == QEvent.Type.MouseButtonPress and self.isVisible():
            if isinstance(obj, QWidget):
                w = obj
                while w is not None:
                    if w is self:
                        return False
                    w = w.parentWidget()
                self.close()
        return False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        t = theme_tokens(self._theme)
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(0, 0, self.width(), self.height()),
            self._radius,
            self._radius,
        )
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t["surface_raised"]))
        p.drawPath(path)
