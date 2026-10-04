"""放映状态机：翻页与空文档。"""

from __future__ import annotations

import sys
import unittest

from PyQt6.QtWidgets import QApplication

from core.sermon.model import new_document, new_slide
from ui.sermon.player.controller import PresentationController

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


if __name__ == "__main__":
    unittest.main()
