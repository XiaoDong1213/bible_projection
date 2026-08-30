# ui/preview_host.py
# 预览舞台：按副屏分辨率排版，再等比缩放到预览区（letterbox）

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, QFrame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter

from .scripture_display import ScriptureDisplay


class PreviewHost(QWidget):
    """右侧预览容器。

    - 无舞台尺寸时：经文区铺满预览（本地编辑）。
    - 有舞台尺寸时：经文区按副屏 W×H 排版，再整体缩放入视口（所见即所得）。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewHost")
        self._stage = None  # (w, h) | None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.view = QGraphicsView()
        self.view.setObjectName("previewView")
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.view.setStyleSheet("QGraphicsView#previewView { background: #0B0D10; border: none; }")

        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(Qt.GlobalColor.black)
        self.view.setScene(self.scene)

        self.display = ScriptureDisplay()
        self.proxy = self.scene.addWidget(self.display)

        layout.addWidget(self.view)

        # 延迟一次 fit，等布局完成
        QTimer.singleShot(0, self._fit_view)

    def set_stage_size(self, width, height):
        """锁定为副屏逻辑分辨率，预览只做等比缩放。"""
        w = max(1, int(width))
        h = max(1, int(height))
        self._stage = (w, h)
        self.display.set_stage_size(w, h)
        self._fit_view()

    def clear_stage(self):
        """退出舞台模式，预览铺满本地区域。"""
        self._stage = None
        self.display.clear_stage_size()
        self._fit_view()

    def stage_size(self):
        return self._stage

    def _fit_view(self):
        vw = max(1, self.view.viewport().width())
        vh = max(1, self.view.viewport().height())

        if self._stage:
            w, h = self._stage
            self.display.setFixedSize(w, h)
            self.proxy.resize(w, h)
            self.scene.setSceneRect(0, 0, w, h)
            scale = min(vw / w, vh / h)
            self.view.resetTransform()
            self.view.scale(scale, scale)
            self.view.centerOn(self.proxy)
        else:
            self.view.resetTransform()
            self.display.setMinimumSize(0, 0)
            self.display.setMaximumSize(16777215, 16777215)
            self.display.setFixedSize(vw, vh)
            self.proxy.resize(vw, vh)
            self.scene.setSceneRect(0, 0, vw, vh)
            self.view.centerOn(self.proxy)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_view()
