from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGraphicsView,
    QGraphicsScene,
    QFrame,
    QLabel,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QBrush, QPalette

from .scripture_display import ScriptureDisplay
from ui.themes import theme_tokens


class PreviewHost(QWidget):
    """右侧预览容器，负责舞台尺寸和缩放显示。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("previewHost")
        self._stage = None
        self._has_content = False
        self._content_bg = QColor("#000000")
        self._stage_matte = QColor("#12161E")
        self._ui_canvas = "#0B0E14"
        # 上次 _fit_view 的视口/舞台指纹；相同则跳过 resetTransform，避免主屏经文快滚时抖
        self._fit_key = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.view = QGraphicsView()
        self.view.setObjectName("previewView")
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 不要开 SmoothPixmapTransform：经文在缩放代理里快滚时会被整帧重采样，主屏发颤；
        # 副屏是 1:1 直绘所以不受影响。文字抗锯齿仍由 ScriptureBody 自己开。
        self.view.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
        )
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.view.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # FullViewportUpdate 会在每次滚动时重绘整块（含黑边），放大抖动感
        self.view.setViewportUpdateMode(
            QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate
        )
        # 避免全局 QSS 把 viewport 盖成死黑，挡住经文舞台上的背景图
        self.view.setStyleSheet("background: transparent; border: none;")
        self.view.viewport().setAutoFillBackground(True)

        self.scene = QGraphicsScene(self)
        self.view.setScene(self.scene)

        self.display = ScriptureDisplay()
        # proxy 默认会打开 autoFillBackground，易用调色板黑盖住 paintEvent 里的背景图
        self.display.setAutoFillBackground(False)
        self.proxy = self.scene.addWidget(self.display)
        self.display.setAutoFillBackground(False)

        root.addWidget(self.view)

        # 叠在预览之上的引导字：不进 Stack，避免挡住 / 盖住舞台背景
        self.empty_hint = QLabel(self)
        self.empty_hint.setObjectName("previewEmptyHint")
        self.empty_hint.setText(
            "输入卷章或点左侧书卷\n按 Enter 快速定位 · Ctrl+F 全文搜索"
        )
        self.empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_hint.setWordWrap(True)
        self.empty_hint.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.empty_hint.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.empty_hint.show()
        self.empty_hint.raise_()

        self.apply_theme(theme_tokens("dark"))
        QTimer.singleShot(0, self._fit_view)

    def set_empty(self, empty: bool):
        """无经文时叠引导字；背景始终走经文舞台（含背景图）。"""
        self._has_content = not bool(empty)
        self.empty_hint.setVisible(not self._has_content)
        if not self._has_content:
            self.empty_hint.raise_()

    def set_content_background(self, color):
        """预览四周边框与经文背景色一致；舞台本体仍由 ScriptureDisplay 画色/图。"""
        c = QColor(color) if not isinstance(color, QColor) else QColor(color)
        if not c.isValid():
            c = QColor("#000000")
        self._content_bg = c
        self._apply_chrome_colors()
        self.display.update()

    def apply_theme(self, tokens):
        """外壳跟控制台主题；扩展等比留白用 stage_matte。"""
        if isinstance(tokens, str):
            tokens = theme_tokens(tokens)
        self._ui_canvas = tokens.get("canvas", "#0B0E14")
        matte = QColor(tokens.get("stage_matte", tokens.get("surface_sunken", "#12161E")))
        if matte.isValid():
            self._stage_matte = matte
        self._apply_chrome_colors()

    def _letterbox_color(self) -> QColor:
        """有舞台比例时用主题垫底；铺满预览时跟经文底色。"""
        return QColor(self._stage_matte) if self._stage else QColor(self._content_bg)

    def _apply_chrome_colors(self):
        letter = self._letterbox_color()
        hint_ref = self._content_bg if self._content_bg.isValid() else letter
        fg = QColor("#E8EDF5") if hint_ref.lightness() < 140 else QColor("#334155")
        fg.setAlpha(220)
        self.setStyleSheet(
            f"#previewHost {{ background: {self._ui_canvas}; }}"
            f"QLabel#previewEmptyHint {{"
            f" background: transparent; color: {fg.name()}; font-size: 15px;"
            f" padding: 24px; }}"
        )
        self.view.setBackgroundBrush(QBrush(letter))
        self.scene.setBackgroundBrush(QBrush(letter))
        pal = self.view.viewport().palette()
        pal.setColor(QPalette.ColorRole.Window, letter)
        pal.setColor(QPalette.ColorRole.Base, letter)
        self.view.viewport().setPalette(pal)
        self.view.viewport().update()

    def set_stage_size(self, width, height):
        """设置预览舞台尺寸。"""
        w = max(1, int(width))
        h = max(1, int(height))
        if self._stage == (w, h):
            self.display.set_stage_size(w, h)
            self._apply_chrome_colors()
            return
        self._stage = (w, h)
        self._fit_key = None
        self.display.set_stage_size(w, h)
        self._apply_chrome_colors()
        self._fit_view()

    def clear_stage(self):
        """退出舞台模式并恢复自适应尺寸。"""
        if self._stage is None:
            self.display.clear_stage_size()
            self._apply_chrome_colors()
            return
        self._stage = None
        self._fit_key = None
        self.display.clear_stage_size()
        self._apply_chrome_colors()
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
            scale = min(vw / w, vh / h) if w > 0 and h > 0 else 0.0
            # 尽量落到整像素宽度，减轻缩放后亚像素抖动
            if scale > 0:
                snapped = max(1, int(round(w * scale))) / float(w)
                if snapped <= scale + 1e-9:
                    scale = snapped
            fit_key = ("stage", w, h, vw, vh, round(scale, 6))
        else:
            w = vw
            h = vh
            scale = 1.0
            fit_key = ("fill", vw, vh)

        if fit_key == self._fit_key:
            hint = self.rect()
            if self.empty_hint.geometry() != hint:
                self.empty_hint.setGeometry(hint)
            if not self._has_content:
                self.empty_hint.raise_()
            return
        self._fit_key = fit_key

        if self.display.width() != w or self.display.height() != h:
            if not self._stage:
                self.display.setMinimumSize(0, 0)
                self.display.setMaximumSize(16777215, 16777215)
            self.display.setFixedSize(w, h)
        self.proxy.resize(w, h)
        self.scene.setSceneRect(0, 0, w, h)
        self.view.resetTransform()
        if self._stage and scale > 0:
            self.view.scale(scale, scale)
        self.view.centerOn(self.proxy)

        self.empty_hint.setGeometry(self.rect())
        if not self._has_content:
            self.empty_hint.raise_()

    def resizeEvent(self, event):
        """窗口尺寸变化时重新适配预览区域。"""
        super().resizeEvent(event)
        # 尺寸未变时 _fit_view 内部会短路，避免无意义 resetTransform
        self._fit_view()
