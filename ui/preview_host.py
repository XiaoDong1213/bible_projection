from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene, QFrame
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush

from .scripture_display import ScriptureDisplay
from .themes import theme_tokens


class PreviewHost(QWidget):
    """右侧预览容器，负责舞台尺寸和缩放显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewHost")
        self._stage = None

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

        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)

        self.display = ScriptureDisplay()
        self.proxy = self.scene.addWidget(self.display)
        layout.addWidget(self.view)
        self.apply_theme(theme_tokens("dark"))
        QTimer.singleShot(0, self._fit_view)

    def apply_theme(self, tokens):
        """预览区背景跟随控制台主题，舞台内容仍由经文设置决定。"""
        if isinstance(tokens, str):
            tokens = theme_tokens(tokens)
        bg = tokens.get("preview_bg", "#07090D")
        canvas = tokens.get("canvas", bg)
        self.setStyleSheet(
            f"#previewHost {{ background: {canvas}; }}"
            f"QGraphicsView#previewView {{ background: {bg}; border: none; }}"
        )
        self.scene.setBackgroundBrush(QBrush(QColor(bg)))

    def set_stage_size(self, width, height):
        """设置预览舞台尺寸。"""
        w = max(1, int(width))
        h = max(1, int(height))
        self._stage = (w, h)
        self.display.set_stage_size(w, h)
        self._fit_view()

    def clear_stage(self):
        """退出舞台模式并恢复自适应尺寸。"""
        self._stage = None
        self.display.clear_stage_size()
        self._fit_view()

    def stage_size(self):
        """返回当前舞台尺寸。"""
        return self._stage

    def _fit_view(self):
        """根据预览区域大小调整舞台缩放比例。"""
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
        """窗口尺寸变化时重新适配预览区域。"""
        super().resizeEvent(event)
        self._fit_view()
