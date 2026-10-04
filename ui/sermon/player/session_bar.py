"""放映会话底栏：经文/讲篇切换只放这里（不进顶栏）。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class SessionBar(QWidget):
    """讲篇放映进行中显示在主屏底部。"""

    to_scripture = pyqtSignal()
    to_sermon = pyqtSignal()
    prev_page = pyqtSignal()
    next_page = pyqtSignal()
    end_session = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonSessionBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(10)

        self.status = QLabel("放映中")
        self.status.setObjectName("sermonSessionStatus")
        layout.addWidget(self.status)
        layout.addStretch(1)

        self.prev_btn = QPushButton("上一页")
        self.next_btn = QPushButton("下一页")
        self.next_btn.setObjectName("sermonSessionNext")
        self.scripture_btn = QPushButton("显示经文")
        self.sermon_btn = QPushButton("显示讲篇")
        self.end_btn = QPushButton("结束放映")
        self.end_btn.setObjectName("sermonSessionEnd")
        for b, sig in (
            (self.prev_btn, self.prev_page),
            (self.next_btn, self.next_page),
            (self.scripture_btn, self.to_scripture),
            (self.sermon_btn, self.to_sermon),
            (self.end_btn, self.end_session),
        ):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(36)
            b.clicked.connect(sig.emit)
            layout.addWidget(b)

        self.hide()

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
