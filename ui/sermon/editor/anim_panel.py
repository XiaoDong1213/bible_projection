"""当前页入场动画列表。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.sermon.model import (
    ANIM_KIND_LABELS,
    ANIM_KINDS,
    ANIM_TRIGGER_LABELS,
    ANIM_TRIGGERS,
    AnimStep,
    Element,
    Slide,
    new_anim_step,
)
from ui.sermon.styles import SermonComboBox


class AnimPanel(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sermonAnimPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        self.list = QListWidget()
        self.list.setMinimumHeight(120)
        self.list.currentRowChanged.connect(self._on_row)
        layout.addWidget(self.list)

        kind_row = QHBoxLayout()
        self.kind_combo = SermonComboBox()
        self.kind_combo.setMaxVisibleItems(8)
        for k in ANIM_KINDS:
            self.kind_combo.addItem(ANIM_KIND_LABELS.get(k, k), k)
        kind_row.addWidget(QLabel("效果"))
        kind_row.addWidget(self.kind_combo, 1)
        layout.addLayout(kind_row)

        trigger_row = QHBoxLayout()
        self.trigger_combo = SermonComboBox()
        self.trigger_combo.setMaxVisibleItems(8)
        for t in ANIM_TRIGGERS:
            self.trigger_combo.addItem(ANIM_TRIGGER_LABELS.get(t, t), t)
        trigger_row.addWidget(QLabel("开始"))
        trigger_row.addWidget(self.trigger_combo, 1)
        layout.addLayout(trigger_row)

        dur_row = QHBoxLayout()
        self.duration = QSpinBox()
        self.duration.setRange(100, 5000)
        self.duration.setSingleStep(100)
        self.duration.setValue(500)
        self.duration.setSuffix(" 毫秒")
        dur_row.addWidget(QLabel("时长"))
        dur_row.addWidget(self.duration, 1)
        layout.addLayout(dur_row)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("添加")
        self.add_btn.setToolTip("为当前选中元素添加入场动画")
        self.add_btn.clicked.connect(self._add)
        self.del_btn = QPushButton("删除")
        self.del_btn.clicked.connect(self._delete)
        self.up_btn = QPushButton("↑")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton("↓")
        self.down_btn.clicked.connect(lambda: self._move(1))
        for b in (self.add_btn, self.del_btn, self.up_btn, self.down_btn):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFixedHeight(28)
            btn_row.addWidget(b)
        layout.addLayout(btn_row)

        self.apply_btn = QPushButton("应用效果/开始/时长")
        self.apply_btn.clicked.connect(self._apply_fields)
        layout.addWidget(self.apply_btn)

        hint = QLabel(
            "选中元素后点「添加」。放映时空格播「单击」组；"
            "「同时」会一起出现，「之后」会自动接下一批。"
        )
        hint.setWordWrap(True)
        hint.setObjectName("sermonHint")
        layout.addWidget(hint)

        self._slide: Slide | None = None
        self._selected: Element | None = None
        self._block = False
        self._play_cursor = -1

    def set_slide(self, slide: Slide | None):
        self._slide = slide
        self.refresh()

    def set_play_cursor(self, cursor: int):
        """放映步进：已播条目高亮，下一条待播。"""
        self._play_cursor = int(cursor)
        self._apply_play_cursor()

    def set_selected_element(self, element: Element | None):
        self._selected = element

    def refresh(self):
        self._block = True
        self.list.clear()
        if self._slide is None:
            self._block = False
            return
        for i, step in enumerate(self._slide.sorted_animations()):
            label = ANIM_KIND_LABELS.get(step.kind, step.kind)
            trig = ANIM_TRIGGER_LABELS.get(step.trigger, step.trigger)
            el_name = self._element_label(step.element_id)
            item = QListWidgetItem(f"{i + 1}. [{trig}] {label} · {el_name}")
            item.setData(Qt.ItemDataRole.UserRole, step.id)
            self.list.addItem(item)
        self._block = False
        self._apply_play_cursor()

    def _apply_play_cursor(self):
        from PyQt6.QtGui import QBrush, QColor

        for i in range(self.list.count()):
            item = self.list.item(i)
            if item is None:
                continue
            if self._play_cursor < 0:
                item.setForeground(QBrush(QColor("#E8EEF6")))
            elif i < self._play_cursor:
                item.setForeground(QBrush(QColor("#8BC34A")))
            elif i == self._play_cursor:
                item.setForeground(QBrush(QColor("#FFD54F")))
            else:
                item.setForeground(QBrush(QColor("#9AA4B2")))
        if 0 <= self._play_cursor < self.list.count():
            self.list.setCurrentRow(self._play_cursor)

    def _element_label(self, element_id: str) -> str:
        if self._slide is None:
            return element_id[:8]
        for el in self._slide.elements:
            if el.id == element_id:
                if el.type == "text":
                    text = (el.content or "文本").replace("\n", " ")
                    return text[:12] + ("…" if len(text) > 12 else "")
                if el.type == "shape":
                    return "形状"
                return "图片"
        return "（已删）"

    def _current_step(self) -> AnimStep | None:
        if self._slide is None:
            return None
        row = self.list.currentRow()
        anims = self._slide.sorted_animations()
        if row < 0 or row >= len(anims):
            return None
        return anims[row]

    def _on_row(self, row: int):
        if self._block or self._slide is None or row < 0:
            return
        step = self._current_step()
        if step is None:
            return
        idx = self.kind_combo.findData(step.kind)
        if idx >= 0:
            self.kind_combo.setCurrentIndex(idx)
        tidx = self.trigger_combo.findData(step.trigger)
        if tidx >= 0:
            self.trigger_combo.setCurrentIndex(tidx)
        self.duration.setValue(step.duration_ms)

    def _add(self):
        if self._slide is None:
            return
        if self._selected is None:
            win = self.window()
            if win is not None and hasattr(win, "statusBar"):
                win.statusBar().showMessage("请先选中一个元素再添动画", 3000)
            return
        order = len(self._slide.animations)
        kind = str(self.kind_combo.currentData() or "fade")
        trigger = str(self.trigger_combo.currentData() or "on_click")
        step = new_anim_step(self._selected.id, kind=kind, order=order, trigger=trigger)
        step.duration_ms = int(self.duration.value())
        self._slide.animations.append(step)
        self._reindex()
        self.refresh()
        self.list.setCurrentRow(len(self._slide.animations) - 1)
        self.changed.emit()

    def _delete(self):
        step = self._current_step()
        if step is None or self._slide is None:
            return
        self._slide.animations = [a for a in self._slide.animations if a.id != step.id]
        self._reindex()
        self.refresh()
        self.changed.emit()

    def _move(self, delta: int):
        if self._slide is None:
            return
        anims = self._slide.sorted_animations()
        row = self.list.currentRow()
        new_row = row + delta
        if row < 0 or new_row < 0 or new_row >= len(anims):
            return
        anims[row], anims[new_row] = anims[new_row], anims[row]
        self._slide.animations = anims
        self._reindex()
        self.refresh()
        self.list.setCurrentRow(new_row)
        self.changed.emit()

    def _apply_fields(self):
        step = self._current_step()
        if step is None:
            return
        step.kind = str(self.kind_combo.currentData() or "fade")
        step.trigger = str(self.trigger_combo.currentData() or "on_click")
        step.duration_ms = int(self.duration.value())
        self.refresh()
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == step.id:
                self.list.setCurrentRow(i)
                break
        self.changed.emit()

    def _reindex(self):
        if self._slide is None:
            return
        ordered = self._slide.sorted_animations()
        for i, a in enumerate(ordered):
            a.order = i
        self._slide.animations = ordered
