"""投影状态胶囊：五态宽度固定、文本格式、主窗口三态判定与焦点联动。"""

import sys
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QLineEdit

_APP = QApplication.instance() or QApplication(sys.argv)

from ui.toolbar.toolbar import ToolBarWidget
from ui.main_window import MainWindow


def _make_toolbar():
    tb = ToolBarWidget()
    tb.resize(1400, 56)
    return tb


def test_badge_fixed_width_across_states():
    """所有状态同宽：切换不跳长度。"""
    tb = _make_toolbar()
    widths = set()
    for mode, text in (
        ("idle", "未投影"),
        ("scripture", "投影中 · 经文"),
        ("scripture_focus", "投影中 · 经文"),
        ("app_lost", "投影中 · 未激活"),
        ("sermon", "投影中 · 讲篇"),
    ):
        tb.mode_badge.set_state(mode, text)
        widths.add(tb.mode_badge.width())
    assert len(widths) == 1, f"五态宽度应一致: {widths}"


def test_badge_text_uses_spaced_dot():
    tb = _make_toolbar()
    tb.set_mode_badge("投影中 · 经文", mode="scripture")
    assert tb.mode_badge._text == "投影中 · 经文"
    assert " · " in tb.mode_badge._text


def test_badge_theme_follows_toolbar():
    tb = _make_toolbar()
    tb.set_theme("light")
    assert tb.mode_badge.theme == "light"
    tb.set_theme("dark")
    assert tb.mode_badge.theme == "dark"


class _StubCtrl:
    active = False
    generation = 0
    doc = SimpleNamespace(slides=[SimpleNamespace() for _ in range(3)], title="讲篇")
    index = 0


def _make_main_window_stub():
    mw = MainWindow.__new__(MainWindow)
    mw.toolbar = _make_toolbar()
    mw._projection_channel = "scripture"
    mw.sermon_controller = _StubCtrl()
    mw._sermon_editor = None
    mw.extension_window = None
    mw._last_speed = 3
    return mw


def test_badge_idle_when_no_projection():
    mw = _make_main_window_stub()
    mw._update_mode_badge()
    assert mw.toolbar.mode_badge._mode == "idle"


def test_badge_scripture_green_when_hotkey_live(monkeypatch):
    mw = _make_main_window_stub()
    mw.extension_window = SimpleNamespace(isVisible=lambda: True)
    # pytest 环境无激活窗口（activeWindow 为 None 会走红色失活态），
    # patch 成「本软件已激活」以覆盖绿态分支
    monkeypatch.setattr(
        "ui.main_window.QApplication.activeWindow", lambda *a: mw.toolbar
    )
    mw._update_mode_badge()
    # 无输入焦点 → 速度档按键生效 → 绿
    assert mw.toolbar.mode_badge._mode == "scripture_focus"


def test_badge_red_when_app_deactivated(monkeypatch):
    mw = _make_main_window_stub()
    mw.extension_window = SimpleNamespace(isVisible=lambda: True)
    monkeypatch.setattr("ui.main_window.QApplication.activeWindow", lambda *a: None)
    mw._update_mode_badge()
    assert mw.toolbar.mode_badge._mode == "app_lost"


def test_badge_yellow_when_focus_blocks_hotkeys():
    mw = _make_main_window_stub()
    mw.extension_window = SimpleNamespace(isVisible=lambda: True)
    box = QLineEdit()
    box.show()
    box.setFocus()
    _APP.processEvents()
    try:
        mw._update_mode_badge()
        if mw._focus_blocks_nav_shortcuts():
            assert mw.toolbar.mode_badge._mode == "scripture"
    finally:
        box.close()


def test_badge_sermon_green_and_ignores_focus(monkeypatch):
    mw = _make_main_window_stub()
    monkeypatch.setattr(
        "ui.main_window.QApplication.activeWindow", lambda *a: mw.toolbar
    )
    mw.sermon_controller.active = True
    mw._projection_channel = "sermon"
    mw._update_mode_badge()
    assert mw.toolbar.mode_badge._mode == "sermon"
