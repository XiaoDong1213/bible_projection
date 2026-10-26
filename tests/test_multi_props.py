"""多选批量改属性（不启窗口，直接测面板写入逻辑）。"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from core.sermon.model import Element, ElementStyle

_APP = QApplication.instance() or QApplication(sys.argv)


def test_write_keys_applies_font_size_to_all_texts():
    from ui.sermon.editor.property_panel import PropertyPanel

    a = Element(
        id="a",
        type="text",
        x=0,
        y=0,
        w=100,
        h=40,
        content="一",
        style=ElementStyle(font_size=40, color="#FFFFFF"),
    )
    b = Element(
        id="b",
        type="text",
        x=10,
        y=10,
        w=120,
        h=40,
        content="二",
        style=ElementStyle(font_size=60, color="#FF0000"),
    )
    panel = PropertyPanel()
    panel._block = True
    panel.font_size.setValue(72)
    panel._font_color = "#00FF00"
    panel._block = False
    panel._selection = [a, b]
    panel._write_keys(a, ("font_size", "font_color"))
    panel._write_keys(b, ("font_size", "font_color"))
    assert a.style.font_size == 72
    assert b.style.font_size == 72
    assert a.style.color == "#00FF00"
    assert b.style.color == "#00FF00"
    assert a.w == 100
    assert b.w == 120


def test_write_keys_size_skips_wrong_type_fields():
    from ui.sermon.editor.property_panel import PropertyPanel

    text = Element(
        id="t",
        type="text",
        x=0,
        y=0,
        w=80,
        h=40,
        content="字",
        style=ElementStyle(font_size=40),
    )
    shape = Element(
        id="s",
        type="shape",
        x=0,
        y=0,
        w=80,
        h=40,
        content="",
        shape="rect",
        style=ElementStyle(color="#111111", opacity=1.0),
    )
    panel = PropertyPanel()
    panel._block = True
    panel.font_size.setValue(90)
    panel.spin_w.setValue(200)
    panel._fill_color = "#ABCDEF"
    panel._block = False
    panel._write_keys(text, ("font_size", "w"))
    panel._write_keys(shape, ("font_size", "w", "fill_color"))
    assert text.style.font_size == 90
    assert text.w == 200
    assert shape.w == 200
    assert shape.style.color == "#ABCDEF"
    assert shape.style.font_size == 48
