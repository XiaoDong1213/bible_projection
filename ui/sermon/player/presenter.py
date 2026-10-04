"""主屏演讲者视图：当前页 + 下一页预览 + 切换控制。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.sermon.model import SermonDocument

from .stage import SlideStage


class PresenterView(QWidget):
    """控制端演讲者视图（观众画面在扩展屏；切换用底部 SessionBar）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonPresenterView")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.title = QLabel("演讲者视图")
        self.title.setObjectName("sermonPanelTitle")
        root.addWidget(self.title)

        stages = QHBoxLayout()
        stages.setSpacing(12)

        left = QVBoxLayout()
        self.current_caption = QLabel("当前")
        self.current_caption.setObjectName("sermonStageCaption")
        left.addWidget(self.current_caption)
        self.current_stage = SlideStage()
        self.current_stage.setMinimumHeight(280)
        self.current_stage.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        left.addWidget(self.current_stage, 3)
        stages.addLayout(left, 3)

        right = QVBoxLayout()
        self.next_caption = QLabel("下一页")
        self.next_caption.setObjectName("sermonStageCaption")
        right.addWidget(self.next_caption)
        self.next_stage = SlideStage()
        self.next_stage.setMinimumHeight(160)
        self.next_stage.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right.addWidget(self.next_stage, 2)
        stages.addLayout(right, 2)
        root.addLayout(stages, 1)

        self.page_label = QLabel("")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.page_label)

        # 翻页/切换经文·讲篇/结束：统一用主屏最下方 SessionBar，避免两套按钮
        self.hint = QLabel(
            "空格或底栏「下一页」：按 PPT 方式逐步出现元素。"
            "底栏「显示经文 / 显示讲篇」切换观众画面；显示经文时主屏也回到经文预览。"
        )
        self.hint.setWordWrap(True)
        self.hint.setObjectName("sermonHint")
        root.addWidget(self.hint)

        self._doc: SermonDocument | None = None
        self._assets: Path | None = None
        self._index = 0
        self._anim_cursor = 0
        self._channel = "sermon"

    def set_channel(self, channel: str):
        self._channel = channel
        if channel == "sermon":
            self.title.setText("演讲者视图 · 与观众同步")
        else:
            self.title.setText("演讲者视图")

    def update_session(
        self,
        doc: SermonDocument,
        index: int,
        assets_root: Path | str | None,
        anim_cursor: int = 0,
    ):
        self._doc = doc
        self._index = max(0, min(index, len(doc.slides) - 1)) if doc.slides else 0
        self._assets = Path(assets_root) if assets_root else None
        self._anim_cursor = max(0, int(anim_cursor))
        self._refresh()

    def clear_session(self):
        self._doc = None
        self.current_stage.clear_stage()
        self.next_stage.clear_stage()
        self.page_label.setText("")

    def _refresh(self):
        if self._doc is None or not self._doc.slides:
            self.clear_session()
            return
        n = len(self._doc.slides)
        idx = self._index
        slide = self._doc.slides[idx]
        self.current_stage.set_assets_root(self._assets)
        self.next_stage.set_assets_root(self._assets)
        # 与观众同步：未播入场保持隐藏
        self.current_stage.show_slide(self._doc, slide, prepare_anims=True)
        played = slide.sorted_animations()[: self._anim_cursor]
        if played:
            self.current_stage.apply_played_steps(played)
        anims = slide.sorted_animations()
        if idx + 1 < n:
            nxt = self._doc.slides[idx + 1]
            self.next_stage.show_slide(self._doc, nxt, prepare_anims=False)
            self.next_caption.setText(f"下一页（第 {idx + 2} 页）")
        else:
            self.next_stage.clear_stage()
            self.next_caption.setText("下一页（无）")
        anim_txt = ""
        if anims:
            anim_txt = f" · 动画 {self._anim_cursor}/{len(anims)}"
        self.page_label.setText(f"{self._doc.title}  ·  第 {idx + 1}/{n} 页{anim_txt}")
        self.current_caption.setText(f"当前（第 {idx + 1} 页）")

    def play_step(self, step, anim_cursor: int | None = None) -> bool:
        """与观众屏同步播放同一入场步骤（不全页重绘）。"""
        return self.play_steps([step], anim_cursor)

    def play_steps(self, steps, anim_cursor: int | None = None) -> int:
        """同批并行跟播。"""
        n_ok = self.current_stage.play_steps(list(steps or []))
        if self._doc is not None and self._doc.slides:
            if anim_cursor is not None:
                self._anim_cursor = max(0, int(anim_cursor))
            else:
                self._anim_cursor = min(
                    len(self._doc.slides[self._index].sorted_animations()),
                    self._anim_cursor + max(1, len(steps or [])),
                )
            n = len(self._doc.slides)
            anims = self._doc.slides[self._index].sorted_animations()
            anim_txt = f" · 动画 {self._anim_cursor}/{len(anims)}" if anims else ""
            self.page_label.setText(
                f"{self._doc.title}  ·  第 {self._index + 1}/{n} 页{anim_txt}"
            )
        return n_ok
