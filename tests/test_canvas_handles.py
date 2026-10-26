"""换页后缩放手柄可重建（scene.clear 不会留下已删 C++ 对象）。"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.sermon.model import new_document, new_text_element
from ui.sermon.editor.canvas import SlideCanvas

_APP = QApplication.instance() or QApplication(sys.argv)


def test_load_slide_twice_rebuilds_handles():
    doc = new_document()
    doc.slides[0].elements.append(new_text_element("一"))
    canvas = SlideCanvas()
    canvas.load_slide(doc, doc.slides[0])
    canvas._ensure_handles()
    n1 = len(canvas._handles)
    assert n1 >= 1
    # 第二页
    from core.sermon.model import new_slide

    s2 = new_slide()
    s2.elements.append(new_text_element("二"))
    doc.slides.append(s2)
    canvas.load_slide(doc, s2)
    canvas._ensure_handles()
    assert len(canvas._handles) >= 1
    for h in canvas._handles:
        assert h.scene() is canvas._scene
