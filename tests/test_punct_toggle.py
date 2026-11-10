"""标点半角紧凑开关：开 = 半角标点字形，关 = 保留全角原字形。"""

import sys

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ui.display.scripture_display import ScriptureDisplay, _halfwidth

LP = chr(0xFF08)   # 全角左括号
RP = chr(0xFF09)   # 全角右括号
COMMA = chr(0xFF0C)


def _make(**attrs):
    w = ScriptureDisplay()
    w.verse_num_gap_left = 20
    w.verse_num_gap_right = 15
    for key, value in attrs.items():
        setattr(w, key, value)
    return w


def test_halfwidth_map():
    assert _halfwidth(LP + RP + COMMA) == "(),"


def test_on_converts_puncts():
    w = _make(punct_halfwidth=True)
    html = w._verse_html(4, 1, "该隐" + LP + "注" + RP + COMMA)
    assert LP not in html
    assert "(" in html and ")" in html


def test_off_keeps_fullwidth():
    w = _make(punct_halfwidth=False)
    html = w._verse_html(4, 1, "该隐" + LP + "注" + RP + COMMA)
    assert LP in html and RP in html
    assert "(" not in html and ")" not in html


def test_default_is_off():
    w = _make()
    assert w.punct_halfwidth is False
