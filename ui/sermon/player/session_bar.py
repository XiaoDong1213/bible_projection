"""放映会话浮条：悬浮在主窗口底部中央的紧凑胶囊，不占布局高度。

样式固定深色（类视频播放器控制条），不随亮暗主题变化；
放映中显示，结束放映后由主窗口统一隐藏（悬浮层用 reposition 定位）。
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QEvent, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class SessionBar(QWidget):
    """讲篇放映进行中悬浮显示在主屏底部，结束后隐藏。

    可按住空白处拖动调整位置；位置由主窗口持久化。"""

    to_scripture = pyqtSignal()
    to_sermon = pyqtSignal()
    prev_page = pyqtSignal()
    next_page = pyqtSignal()
    end_session = pyqtSignal()
    drag_moved = pyqtSignal(int, int)  # 拖动结束后的新位置（主窗坐标系）

    BAR_HEIGHT = 40   # 胶囊总高
    BOTTOM_GAP = 14   # 距主窗口底边

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonSessionBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 5, 10, 5)
        layout.setSpacing(6)

        self.status = QLabel("放映中")
        self.status.setObjectName("sermonSessionStatus")
        layout.addWidget(self.status)
        layout.addStretch(1)

        # 用 U+25C2/U+25B8 小三角：U+25B6 有 emoji 变体（▶️），Windows 上会被
        # 路由到 Segoe UI Emoji 导致字形丢失（按钮显示空白）
        self.prev_btn = QPushButton("◂")
        self.prev_btn.setToolTip("上一页")
        self.next_btn = QPushButton("▸")
        self.next_btn.setToolTip("下一页")
        self.scripture_btn = QPushButton("经文")
        self.sermon_btn = QPushButton("讲篇")
        self.end_btn = QPushButton("结束放映")
        self.end_btn.setObjectName("sermonSessionEnd")
        self.end_btn.setMinimumWidth(88)  # 四字按钮留足渲染余量，防文字被裁
        for b, sig in (
            (self.prev_btn, self.prev_page),
            (self.next_btn, self.next_page),
            (self.scripture_btn, self.to_scripture),
            (self.sermon_btn, self.to_sermon),
            (self.end_btn, self.end_session),
        ):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(30)
            b.clicked.connect(sig.emit)
            layout.addWidget(b)
        for b in (self.prev_btn, self.next_btn):
            b.setFixedWidth(34)
            b.setObjectName("sermonNavBtn")

        self.setFixedHeight(self.BAR_HEIGHT)
        self._fixed_width = 0  # polish 后按最宽状态文案冻结，避免换频道/翻页时宽度跳动
        self.hide()

    def _fix_heights(self):
        """QSS polish 会把按钮 minimumSize 抬到 sizeHint（压过 setFixedHeight），
        在样式应用后把固定高度重新压回，并按最宽状态文案冻结胶囊总宽。"""
        self.setFixedHeight(self.BAR_HEIGHT)
        for b in (
            self.prev_btn,
            self.next_btn,
            self.scripture_btn,
            self.sermon_btn,
            self.end_btn,
        ):
            b.setFixedHeight(30)
        self._apply_fixed_width()

    def _apply_fixed_width(self):
        """冻结胶囊总宽：按最宽状态文案（页码拉满三位）计算一次，之后不再随文字变化。"""
        old = self.status.text()
        self.status.setText("观众：讲篇  999/999")
        self._fixed_width = max(self.sizeHint().width(), 360)
        self.status.setText(old)
        self.setFixedSize(self._fixed_width, self.BAR_HEIGHT)

    def event(self, ev):
        if ev.type() in (
            QEvent.Type.StyleChange,
            QEvent.Type.Polish,
            QEvent.Type.PolishRequest,
        ):
            self._fix_heights()
        return super().event(ev)

    def set_channel(self, channel: str, page_text: str = ""):
        on_sermon = channel == "sermon"
        self.sermon_btn.setEnabled(not on_sermon)
        self.scripture_btn.setEnabled(on_sermon)
        self.prev_btn.setEnabled(on_sermon)
        self.next_btn.setEnabled(on_sermon)
        # 当前观众频道高亮
        self.sermon_btn.setObjectName(
            "sermonChannelActive" if on_sermon else "sermonChannelIdle"
        )
        self.scripture_btn.setObjectName(
            "sermonChannelActive" if not on_sermon else "sermonChannelIdle"
        )
        for b in (self.sermon_btn, self.scripture_btn):
            b.style().unpolish(b)
            b.style().polish(b)
        audience = "讲篇" if on_sermon else "经文"
        extra = f"  {page_text}" if page_text else ""
        self.status.setText(f"观众：{audience}{extra}")

    def reposition(self, host, saved=None):
        """悬浮在 host（主窗口）内。show / resize 后调用。

        saved 为用户拖动后的记忆位置（主窗坐标系），None 时回落到底部居中；
        两种来源都会夹取在主窗可视范围内。"""
        # QSS polish 会抬 minimumSize（见 _fix_heights），此处 setFixedSize 双保险压死尺寸；
        # 宽度用冻结值（_apply_fixed_width），状态文字变化不再改变胶囊长度
        self.setFixedSize(self._fixed_width, self.BAR_HEIGHT)
        w, h = self.width(), self.height()
        if saved is not None:
            x, y = int(saved[0]), int(saved[1])
        else:
            x = (host.width() - w) // 2
            y = host.height() - h - self.BOTTOM_GAP
        self.move(
            max(8, min(x, host.width() - w - 8)),
            max(8, min(y, host.height() - h - 8)),
        )

    # —— 按住非按钮区域拖动调整位置（状态文字也是拖把手） ——
    def mousePressEvent(self, ev):
        child = self.childAt(ev.position().toPoint())
        if ev.button() == Qt.MouseButton.LeftButton and not isinstance(
            child, QPushButton
        ):
            self._drag_from = ev.position().toPoint()
            ev.accept()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if ev.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_from"):
            host = self.parentWidget()
            new_pos = self.pos() + (ev.position().toPoint() - self._drag_from)
            if host is not None:
                new_pos.setX(max(8, min(new_pos.x(), host.width() - self.width() - 8)))
                new_pos.setY(max(8, min(new_pos.y(), host.height() - self.height() - 8)))
            self.move(new_pos)
            ev.accept()
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if hasattr(self, "_drag_from"):
            del self._drag_from
            if ev.button() == Qt.MouseButton.LeftButton:
                self.drag_moved.emit(self.x(), self.y())
            ev.accept()
            return
        super().mouseReleaseEvent(ev)
