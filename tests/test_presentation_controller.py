"""放映状态机：翻页、动画回退与空文档。"""

from __future__ import annotations

import sys
import unittest

from PyQt6.QtWidgets import QApplication

from core.sermon.model import (
    Element,
    Slide,
    new_anim_step,
    new_document,
    new_id,
    new_slide,
    normalize_sermon_title,
)
from ui.sermon.editor.anim_panel import AnimPanel
from ui.sermon.player.controller import PresentationController
from ui.sermon.text_format import encode_rich_runs

_APP = QApplication.instance() or QApplication(sys.argv)


class PresentationControllerTests(unittest.TestCase):
    def test_start_advance_prev_stop(self):
        doc = new_document()
        doc.slides.append(new_slide())
        ctrl = PresentationController()
        self.assertTrue(ctrl.start(doc, 0, None))
        self.assertTrue(ctrl.active)
        self.assertEqual(ctrl.index, 0)
        ctrl.advance()
        self.assertEqual(ctrl.index, 1)
        ctrl.prev_slide()
        self.assertEqual(ctrl.index, 0)
        self.assertEqual(ctrl.anim_cursor, len(ctrl._anims()))
        ctrl.go_to(1)
        self.assertEqual(ctrl.index, 1)
        ctrl.stop()
        self.assertFalse(ctrl.active)

    def test_start_empty_fails(self):
        doc = new_document()
        doc.slides.clear()
        ctrl = PresentationController()
        self.assertFalse(ctrl.start(doc, 0, None))
        self.assertFalse(ctrl.active)

    def test_advance_on_last_slide_stays(self):
        doc = new_document()
        ctrl = PresentationController()
        ctrl.start(doc, 0, None)
        ctrl.advance()
        self.assertEqual(ctrl.index, 0)
        ctrl.stop()

    def test_prev_rewinds_animation_before_page(self):
        doc = new_document()
        slide = doc.slides[0]
        el = "el_a"
        slide.animations = [
            new_anim_step(el, kind="fade", order=0, trigger="on_click"),
            new_anim_step(el, kind="fade", order=1, trigger="on_click"),
        ]
        ctrl = PresentationController()
        self.assertTrue(ctrl.start(doc, 0, None))
        ctrl.advance()
        self.assertEqual(ctrl.anim_cursor, 1)
        ctrl.advance()
        self.assertEqual(ctrl.anim_cursor, 2)
        ctrl.prev()
        self.assertEqual(ctrl.index, 0)
        self.assertEqual(ctrl.anim_cursor, 1)
        ctrl.prev()
        self.assertEqual(ctrl.index, 0)
        self.assertEqual(ctrl.anim_cursor, 0)


class SermonTitleAndAnimLabelTests(unittest.TestCase):
    def test_normalize_presentation_title(self):
        self.assertEqual(normalize_sermon_title("Presentation", "生命价值"), "生命价值")
        self.assertEqual(normalize_sermon_title("演示文稿", "foo"), "foo")
        self.assertEqual(normalize_sermon_title("真正标题", "foo"), "真正标题")

    def test_anim_label_strips_bp_runs(self):
        panel = AnimPanel()
        slide = Slide(id=new_id("slide_"))
        raw = encode_rich_runs([("重拾生命", "#FFFFFF"), ("的价值", "#FFD700")])
        slide.elements.append(
            Element(id="el1", type="text", x=0, y=0, w=100, h=40, content=raw)
        )
        panel.set_slide(slide)
        label = panel._element_label("el1")
        self.assertNotIn("bp-runs", label)
        self.assertIn("重拾生命", label)

    def test_anim_move_updates_order(self):
        panel = AnimPanel()
        slide = Slide(id=new_id("slide_"))
        slide.elements.append(
            Element(id="el1", type="text", x=0, y=0, w=100, h=40, content="甲")
        )
        a = new_anim_step("el1", kind="fade", order=0, trigger="on_click")
        b = new_anim_step("el1", kind="fade", order=1, trigger="on_click")
        slide.animations = [a, b]
        panel.set_slide(slide)
        panel.list.setCurrentRow(1)
        panel._move(-1)
        self.assertEqual([s.id for s in slide.sorted_animations()], [b.id, a.id])
        self.assertEqual(b.order, 0)
        self.assertEqual(a.order, 1)


if __name__ == "__main__":
    unittest.main()
