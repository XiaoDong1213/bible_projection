"""当前页换页过渡（进入本页时的切换效果）。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.sermon.model import (
    TRANSITION_KINDS,
    TRANSITION_LABELS,
    Slide,
    SlideTransition,
)


class TransitionPanel(QWidget):
    """五个切换按钮：无切换 / 平滑 / 淡出 / 切出 / 擦除。"""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonTransitionPanel")
        self._slide: Slide | None = None
        self._block = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)

        tip = QLabel("进入本页时的切换效果（相对上一页）")
        tip.setObjectName("sermonHint")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        row = QHBoxLayout()
        row.setSpacing(6)
        for kind in TRANSITION_KINDS:
            btn = QPushButton(TRANSITION_LABELS.get(kind, kind))
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(40)
            btn.setProperty("transitionKind", kind)
            btn.setObjectName("sermonTransitionBtn")
            self._group.addButton(btn)
            self._buttons[kind] = btn
            row.addWidget(btn)
            btn.clicked.connect(lambda _=False, k=kind: self._on_pick(k))
        layout.addLayout(row)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("时长"))
        self.duration = QSpinBox()
        self.duration.setRange(0, 3000)
        self.duration.setSingleStep(100)
        self.duration.setValue(500)
        self.duration.setSuffix(" 毫秒")
        self.duration.valueChanged.connect(self._on_duration)
        dur_row.addWidget(self.duration, 1)
        layout.addLayout(dur_row)

        layout.addStretch(1)

    def set_slide(self, slide: Slide | None):
        self._slide = slide
        self._block = True
        try:
            if slide is None:
                self._buttons["none"].setChecked(True)
                self.duration.setValue(500)
                self.duration.setEnabled(False)
                return
            tr = slide.transition or SlideTransition()
            kind = tr.kind if tr.kind in self._buttons else "none"
            self._buttons[kind].setChecked(True)
            self.duration.setValue(int(tr.duration_ms))
            self.duration.setEnabled(kind != "none")
        finally:
            self._block = False

    def _on_pick(self, kind: str):
        if self._block or self._slide is None:
            return
        self._slide.transition = SlideTransition(
            kind=kind,
            duration_ms=int(self.duration.value()) if kind != "none" else 0,
        )
        self.duration.setEnabled(kind != "none")
        self.changed.emit()

    def _on_duration(self, value: int):
        if self._block or self._slide is None:
            return
        kind = self._slide.transition.kind if self._slide.transition else "none"
        if kind == "none":
            return
        self._slide.transition = SlideTransition(kind=kind, duration_ms=int(value))
        self.changed.emit()
