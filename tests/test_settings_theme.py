"""设置对话框主题 tab：预览卡片互斥、读写与回显、自绘渲染。"""

import sys

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ui.toolbar.toolbar import DisplaySettingsDialog

_BASE = {
    "theme": "dark",
    "bible_file": "uhe_hb.db",
}


def _dialog():
    return DisplaySettingsDialog(dict(_BASE))


def test_cards_exclusive_and_follow_pick():
    d = _dialog()
    assert d.theme_dark_card.isChecked()
    assert not d.theme_light_card.isChecked()
    d.theme_light_card.click()
    assert d.theme_light_card.isChecked()
    assert not d.theme_dark_card.isChecked()
    assert d.get_settings()["theme"] == "light"
    d.theme_dark_card.click()
    assert d.get_settings()["theme"] == "dark"


def test_reload_restores_theme_selection():
    d = _dialog()
    d.reload({"theme": "light"})
    assert d.theme_light_card.isChecked()
    assert not d.theme_dark_card.isChecked()
    assert d.get_settings()["theme"] == "light"


def test_preview_card_renders_both_states():
    d = _dialog()
    d.show()
    _APP.processEvents()
    d.theme_light_card.setChecked(True)
    d.theme_light_card.grab()
    d.theme_dark_card.setChecked(True)
    d.theme_dark_card.grab()
