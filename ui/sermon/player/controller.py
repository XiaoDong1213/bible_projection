"""讲篇放映状态机（翻页 + 分步入场动画，支持同时/之后）。"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.sermon.model import AnimStep, SermonDocument, Slide


class PresentationController(QObject):
    """管理放映中的文档引用、页码、动画游标。"""

    started = pyqtSignal(object, int, object)  # doc, index, assets_root
    stopped = pyqtSignal()
    slide_changed = pyqtSignal(object, int, object)  # doc, index, assets_root
    steps_requested = pyqtSignal(object)  # list[AnimStep] 同批并行
    resume_requested = pyqtSignal(object, int, object, int)  # doc, index, assets, anim_cursor
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False
        self.doc: SermonDocument | None = None
        self.index = 0
        self.anim_cursor = 0
        self.assets_root: Path | None = None
        self._after_timer = QTimer(self)
        self._after_timer.setSingleShot(True)
        self._after_timer.timeout.connect(self._play_after_batch)
        self._gen = 0  # 翻页/停止时作废待播定时器
        self._hot_refresh = False
        self._pending_reveal = False

    @property
    def slide_count(self) -> int:
        if self.doc is None:
            return 0
        return len(self.doc.slides)

    def current_slide(self) -> Slide | None:
        if self.doc is None or not self.doc.slides:
            return None
        self.index = max(0, min(self.index, len(self.doc.slides) - 1))
        return self.doc.slides[self.index]

    def _anims(self) -> list[AnimStep]:
        slide = self.current_slide()
        if slide is None:
            return []
        return slide.sorted_animations()

    @property
    def generation(self) -> int:
        return self._gen

    def _cancel_after(self):
        self._gen += 1
        self._after_timer.stop()

    def start(self, doc: SermonDocument, index: int, assets_root: Path | str | None):
        if not doc.slides:
            self.status_changed.emit("讲篇没有幻灯片")
            return False
        self._cancel_after()
        self.doc = doc
        self.assets_root = Path(assets_root) if assets_root else None
        self.index = max(0, min(int(index), len(doc.slides) - 1))
        self.anim_cursor = 0
        self.active = True
        self.started.emit(self.doc, self.index, self.assets_root)
        self.status_changed.emit(self._status_text())
        self._auto_start_entrance()
        return True

    def stop(self):
        if not self.active:
            return
        self._cancel_after()
        self.active = False
        self.anim_cursor = 0
        self.stopped.emit()
        self.status_changed.emit("讲篇放映已结束")

    def go_to(self, index: int):
        if not self.active or self.doc is None:
            return
        if not self.doc.slides:
            return
        self._cancel_after()
        new_index = max(0, min(int(index), len(self.doc.slides) - 1))
        self.index = new_index
        self.anim_cursor = 0
        self.slide_changed.emit(self.doc, self.index, self.assets_root)
        self.status_changed.emit(self._status_text())
        # 换页过渡结束后由主窗口调用 maybe_auto_start()

    def maybe_auto_start(self):
        """换页过渡完成后启动本页自动入场。"""
        self._auto_start_entrance()

    def _emit_batch(self, batch: list[AnimStep]):
        if not batch:
            return
        self.steps_requested.emit(batch)
        self.status_changed.emit(self._status_text())
        self._arm_after_chain(batch)

    def _collect_with_following(self, start: int) -> list[AnimStep]:
        """从 start 取一条，并吞掉后续 with_previous。"""
        anims = self._anims()
        if start < 0 or start >= len(anims):
            return []
        batch = [anims[start]]
        i = start + 1
        while i < len(anims) and anims[i].trigger == "with_previous":
            batch.append(anims[i])
            i += 1
        self.anim_cursor = i
        return batch

    def _auto_start_entrance(self):
        """页进入时：若首条是「同时/之后」，自动开播（对应 PPT 换页后自动动画）。"""
        anims = self._anims()
        if not anims or self.anim_cursor != 0:
            return
        first = anims[0].trigger
        if first in ("after_previous", "with_previous"):
            delay = max(0, int(anims[0].delay_ms))
            gen = self._gen

            def _go():
                if not self.active or gen != self._gen or self.anim_cursor != 0:
                    return
                batch = self._collect_with_following(0)
                self._emit_batch(batch)

            if delay <= 0:
                QTimer.singleShot(0, _go)
            else:
                QTimer.singleShot(delay, _go)

    def advance(self):
        """空格/下一页：播下一个单击组（含同时），再翻页。"""
        if not self.active or self.doc is None:
            return
        self._cancel_after()
        anims = self._anims()
        if self.anim_cursor < len(anims):
            # 若卡在 after_previous（定时器被取消），单击也可启动
            batch = self._collect_with_following(self.anim_cursor)
            self._emit_batch(batch)
            return
        if self.index < len(self.doc.slides) - 1:
            self.go_to(self.index + 1)

    def _arm_after_chain(self, batch: list[AnimStep]):
        """本批结束后，若下一条是 after_previous，则自动续播。"""
        anims = self._anims()
        if self.anim_cursor >= len(anims):
            return
        nxt = anims[self.anim_cursor]
        if nxt.trigger != "after_previous":
            return
        wait = max((max(50, int(s.duration_ms)) for s in batch), default=500)
        wait += max(0, int(nxt.delay_ms))
        gen = self._gen
        self._after_timer.stop()
        self._after_timer.setInterval(wait)
        self._pending_after_gen = gen
        self._after_timer.start()

    def _play_after_batch(self):
        if not self.active:
            return
        if getattr(self, "_pending_after_gen", self._gen) != self._gen:
            return
        anims = self._anims()
        if self.anim_cursor >= len(anims):
            return
        if anims[self.anim_cursor].trigger != "after_previous":
            return
        batch = self._collect_with_following(self.anim_cursor)
        self._emit_batch(batch)

    def prev_slide(self):
        """上一页：直接回到上一张并显示终态（不重播本页动画）。"""
        if not self.active or self.doc is None:
            return
        self._cancel_after()
        if self.index <= 0:
            # 已在首页：仅回到未播放准备态，不自动再播
            if self.anim_cursor > 0:
                self.anim_cursor = 0
                self.slide_changed.emit(self.doc, self.index, self.assets_root)
                self.status_changed.emit(self._status_text())
            return
        self.index -= 1
        anims = self._anims()
        self.anim_cursor = len(anims)
        self._pending_reveal = True
        self.slide_changed.emit(self.doc, self.index, self.assets_root)
        self.status_changed.emit(self._status_text())

    def hot_update(self, doc: SermonDocument, index: int | None = None, assets_root=None):
        """放映中文档变更：刷新内容，保留当前动画步进。"""
        if not self.active:
            return
        saved = int(self.anim_cursor)
        self._cancel_after()
        self.doc = doc
        if assets_root is not None:
            self.assets_root = Path(assets_root)
        if not doc.slides:
            self.stop()
            return
        if index is not None:
            self.index = max(0, min(int(index), len(doc.slides) - 1))
        else:
            self.index = max(0, min(self.index, len(doc.slides) - 1))
        anims = self._anims()
        self.anim_cursor = max(0, min(saved, len(anims)))
        self._hot_refresh = True
        self.slide_changed.emit(self.doc, self.index, self.assets_root)
        self.status_changed.emit(self._status_text())

    def resume_display(self) -> bool:
        """切回讲篇频道：不重置页码/动画游标。"""
        if not self.active or self.doc is None:
            return False
        self.resume_requested.emit(self.doc, self.index, self.assets_root, self.anim_cursor)
        self.status_changed.emit(self._status_text())
        return True

    def _status_text(self) -> str:
        n = self.slide_count
        anims = self._anims()
        if anims:
            return f"讲篇放映中 {self.index + 1}/{n} · 动画 {self.anim_cursor}/{len(anims)}"
        return f"讲篇放映中 {self.index + 1}/{n}"
