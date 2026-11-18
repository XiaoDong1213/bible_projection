"""单章/跨章/跳节内容联动：模式切换迁移、历史/搜索定位广播、信息行两行结构。"""

import sys

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from core.database import BibleDatabase
from core.selection import ScriptureSelection
from ui.navigation.panel import NavigationPanel

_DB = BibleDatabase()


def _panel():
    p = NavigationPanel(_DB)
    p.resize(320, 600)
    return p


def _goto_genesis(panel):
    panel._set_selected_book("创世记", whole_chapter=False)


def _switch(panel, mode):
    """模拟点击模式按钮（先选中再触发迁移，保持 checkedId 一致）。"""
    panel.mode_group.button(mode).setChecked(True)
    panel._on_mode_changed(mode)


def test_single_to_cross_and_skip():
    """单章 章3 起5 止20 → 切跨章/跳节都带过去。"""
    p = _panel()
    _goto_genesis(p)
    p.chapter_spin.setValue(3)
    p.start_spin.setValue(5)
    p.end_spin.setValue(20)
    _switch(p, NavigationPanel.MODE_CROSS)
    assert p.cross_start_ch.value() == 3
    assert p.cross_start_v.value() == 5
    assert p.cross_end_ch.value() == 3
    assert p.cross_end_v.value() == 20
    _switch(p, NavigationPanel.MODE_SKIP)
    assert p.skip_chapter_spin.value() == 3
    assert p.skip_edit.text() == "5-20"


def test_cross_to_single_keeps_range():
    """跨章 2:3-3:20 → 切单章：章=起章 2，起 3 止 20。"""
    p = _panel()
    _goto_genesis(p)
    _switch(p, NavigationPanel.MODE_CROSS)
    p.cross_start_ch.setValue(2)
    p.cross_start_v.setValue(3)
    p.cross_end_ch.setValue(3)
    p.cross_end_v.setValue(20)
    _switch(p, NavigationPanel.MODE_SINGLE)
    assert p.chapter_spin.value() == 2
    assert p.start_spin.value() == 3
    assert p.end_spin.value() == 20


def test_cross_to_single_clamps_end_to_start_chapter():
    """倒序跨章（起章 2 止章 1 节 31）→ 切单章：止节夹到创 2 的 25 节。"""
    p = _panel()
    _goto_genesis(p)
    _switch(p, NavigationPanel.MODE_CROSS)
    p.cross_start_ch.setValue(2)
    p.cross_start_v.setValue(20)
    p.cross_end_ch.setValue(1)
    p.cross_end_v.setValue(31)
    _switch(p, NavigationPanel.MODE_SINGLE)
    assert p.chapter_spin.value() == 2
    assert p.start_spin.value() == 20
    assert p.end_spin.value() == 25


def test_cross_to_skip_uses_start_chapter():
    """跨章 2:3-3:20 → 切跳节：章=起章 2，文本 3-20。"""
    p = _panel()
    _goto_genesis(p)
    _switch(p, NavigationPanel.MODE_CROSS)
    p.cross_start_ch.setValue(2)
    p.cross_start_v.setValue(3)
    p.cross_end_ch.setValue(3)
    p.cross_end_v.setValue(20)
    _switch(p, NavigationPanel.MODE_SKIP)
    assert p.skip_chapter_spin.value() == 2
    assert p.skip_edit.text() == "3-20"


def test_skip_to_single_and_cross_first_span():
    """跳节多段 "16-18 20 22-25" → 单章/跨章只带第一段 16-18。"""
    p = _panel()
    _goto_genesis(p)
    _switch(p, NavigationPanel.MODE_SKIP)
    p.skip_chapter_spin.setValue(1)
    p.skip_edit.setText("16-18 20 22-25")
    _switch(p, NavigationPanel.MODE_SINGLE)
    assert p.chapter_spin.value() == 1
    assert p.start_spin.value() == 16
    assert p.end_spin.value() == 18
    _switch(p, NavigationPanel.MODE_CROSS)
    assert p.cross_start_ch.value() == 1
    assert p.cross_start_v.value() == 16
    assert p.cross_end_ch.value() == 1
    assert p.cross_end_v.value() == 18


def test_history_cross_selection_fills_all_modes():
    """历史（跨章选区）定位后：单章/跳节同步拿到对应内容。"""
    p = _panel()
    sel = ScriptureSelection.expand_cross_chapter(
        "创世记", 2, 3, 3, 20, _DB.get_verse_count
    )
    p.sync_from_selection(sel)
    # 当前模式=跨章；其余模式被广播
    assert p._current_mode() == NavigationPanel.MODE_CROSS
    assert p.cross_start_ch.value() == 2 and p.cross_start_v.value() == 3
    assert p.cross_end_ch.value() == 3 and p.cross_end_v.value() == 20
    assert p.chapter_spin.value() == 2
    assert p.start_spin.value() == 3
    assert p.end_spin.value() == 20
    assert p.skip_chapter_spin.value() == 2
    assert p.skip_edit.text() == "3-20"
    # 再切到单章，内容不丢
    _switch(p, NavigationPanel.MODE_SINGLE)
    assert p.chapter_spin.value() == 2
    assert p.start_spin.value() == 3 and p.end_spin.value() == 20


def test_sync_selection_broadcasts_to_other_modes():
    """历史（单章选区）定位后：跨章/跳节同步拿到对应内容。"""
    p = _panel()
    _goto_genesis(p)
    p.sync_selection("创世记", 1, 3, 20)
    assert p._current_mode() == NavigationPanel.MODE_SINGLE
    assert p.cross_start_ch.value() == 1
    assert p.cross_start_v.value() == 3
    assert p.cross_end_ch.value() == 1
    assert p.cross_end_v.value() == 20
    assert p.skip_chapter_spin.value() == 1
    assert p.skip_edit.text() == "3-20"


def test_book_info_single_row():
    """信息行单行：全名放得下用全名；长书卷退化简称，永不折行。"""
    p = _panel()
    _goto_genesis(p)
    assert p.book_info_data.text() == "创世记（创） · 本卷共 50 章 · 本章共 31 节"
    _switch(p, NavigationPanel.MODE_CROSS)
    p.cross_start_ch.setValue(2)
    p.cross_end_ch.setValue(3)
    assert "起章 25 节" in p.book_info_data.text()
    assert "止章 24 节" in p.book_info_data.text()
    # 长书卷 + 跨章数据一行放不下 → 退化简称
    p._set_selected_book("帖撒罗尼迦前书", whole_chapter=False)
    p._update_book_info()
    assert p.book_info_data.text().startswith("帖前 · ")
    assert "本卷共 5 章" in p.book_info_data.text()
    # 未选书卷时保留占位
    p2 = _panel()
    assert "—" in p2.book_info_data.text()


def test_skip_hint_only_shown_when_invalid():
    """跳节格式提示平时不占行，输入非法时才出现。"""
    p = _panel()
    _goto_genesis(p)
    _switch(p, NavigationPanel.MODE_SKIP)
    assert not p.skip_hint.isVisibleTo(p)
    p.skip_edit.setText("abc")
    p._current_selection()
    assert p.skip_hint.isVisibleTo(p)
    assert "格式无效" in p.skip_hint.text()
    p.skip_edit.setText("1-5")
    p._current_selection()
    assert not p.skip_hint.isVisibleTo(p)
