"""PPTX 主格式与版式预设。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from core.sermon.formats import OPEN_FILTER, PPTX_EXT, SAVE_FILTER
from core.sermon.model import new_document, new_text_element
from core.sermon.store import PACKAGE_EXT, SermonStore
from ui.sermon.editor.layouts import LAYOUT_PRESETS, apply_layout

_APP = QApplication.instance() or QApplication(sys.argv)


class FormatsTests(unittest.TestCase):
    def test_filters_prefer_sermon_package(self):
        self.assertTrue(OPEN_FILTER.startswith("讲篇"))
        self.assertIn(PACKAGE_EXT, OPEN_FILTER)
        self.assertIn(PPTX_EXT, SAVE_FILTER)
        self.assertIn(PACKAGE_EXT, SAVE_FILTER)


class LayoutTests(unittest.TestCase):
    def test_all_presets_replace_elements(self):
        for lid, _name, _tip in LAYOUT_PRESETS:
            slide = new_document().slides[0]
            slide.elements.append(new_text_element("旧内容"))
            apply_layout(slide, lid, aspect="16:9")
            self.assertGreaterEqual(len(slide.elements), 1)
            self.assertEqual(slide.animations, [])


class PptxRoundtripTests(unittest.TestCase):
    def test_export_import_reuse_id(self):
        try:
            from core.sermon.pptx_io import export_pptx, import_pptx
        except Exception:
            self.skipTest("python-pptx unavailable")
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            doc = new_document(title="往返")
            doc.slides[0].elements.append(new_text_element("你好"))
            store.save(doc)
            pptx = root / "round.pptx"
            export_pptx(doc, pptx, store)
            loaded = import_pptx(pptx, store, reuse_id=doc.id)
            self.assertEqual(loaded.id, doc.id)
            self.assertEqual(loaded.title, "往返")
            self.assertTrue(
                any("你好" in (el.content or "") for s in loaded.slides for el in s.elements)
            )
            self.assertTrue(hasattr(loaded, "import_notes"))


if __name__ == "__main__":
    unittest.main()
