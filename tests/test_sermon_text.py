from __future__ import annotations

import unittest

from core.sermon.model import Background, ElementStyle, new_slide, new_text_element
from ui.sermon.text_format import is_text_placeholder


class SermonTextTests(unittest.TestCase):
    def test_placeholder(self):
        self.assertTrue(is_text_placeholder("在此输入"))
        self.assertTrue(is_text_placeholder("  双击编辑文字  "))
        self.assertFalse(is_text_placeholder("约翰福音"))
        self.assertFalse(is_text_placeholder(""))

    def test_new_text_copies_style(self):
        style = ElementStyle(font_size=36, color="#FFAA00", line_spacing=160)
        el = new_text_element("在此输入", style=style)
        self.assertEqual(el.style.font_size, 36)
        self.assertEqual(el.style.color, "#FFAA00")
        style.font_size = 12
        self.assertEqual(el.style.font_size, 36)

    def test_new_slide_clones_background(self):
        bg = Background(type="color", value="#112233")
        slide = new_slide(background=bg)
        self.assertEqual(slide.background.value, "#112233")
        self.assertIsNot(slide.background, bg)


if __name__ == "__main__":
    unittest.main()
