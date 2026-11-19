"""单章/跨章/跳节内容联动：模式切换迁移、历史/搜索定位广播、信息行两行结构。"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from core.database import BibleDatabase
from core.selection import ScriptureSelection
from ui.navigation.panel import NavigationPanel

_DB = BibleDatabase()


def test_load_history_backfills_bible_file():
    """旧条目缺译本标记：加载时补当前译本并广播固化。"""
    p = _panel()
    got = []
    p.history_changed.connect(lambda entries: got.append(entries))
    p.load_history([
        {"book": "创世记", "spans": [{"c": 1, "s": 1, "e": 3}]},
    ])
    assert len(p.history) == 1
    assert getattr(p.history[0], "bible_file", "") == Path(_DB.db_path).name
    # 广播出去的条目已带标记（连接在 load 之后建立也应收到本轮固化）
    assert len(got) == 1
    assert got[0][0].get("bible_file")


def test_delete_to_single_version_drops_tag():
    """删到只剩一个译本时，剩余行的译本标注去掉（增量改文字不重建）。"""
    p = _panel()
    p.load_history([
        {"book": "创世记", "spans": [{"c": 1, "s": 1, "e": 3}], "bible_file": "思高本.db"},
        {"book": "创世记", "spans": [{"c": 2, "s": 1, "e": 3}], "bible_file": "和合本.db"},
    ])
    # 两个译本：行文字带标注
    assert "（思高本）" in p.history_list._rows[0].label.text()
    p._delete_history(p.history_list._rows[0])
    # 只剩和合本：标注消失、行数减一
    assert len(p.history_list._rows) == 1
    assert "（和合本）" not in p.history_list._rows[0].label.text()
    assert "创世记 2:1-3" in p.history_list._rows[0].label.text()


def test_add_history_incremental_reuses_row():
    """打开经文入历史：新条目插顶、重访复用同一行 widget（不整列重建）。"""
    p = _panel()
    sel1 = ScriptureSelection.single_chapter("创世记", 1, 1, 3)
    sel2 = ScriptureSelection.single_chapter("出埃及记", 2, 1, 5)
    p.add_selection_to_history(sel1)
    p.add_selection_to_history(sel2)
    assert [r.label.text() for r in p.history_list._rows] == [
        "出埃及记 2:1-5",
        "创世记 1:1-3",
    ]
    # 重访创世记：原行 widget 被挪到顶部（同一对象，未销毁重建）
    old_row = p.history_list._rows[1]
    p.add_selection_to_history(sel1)
    assert p.history_list._rows[0] is old_row
    assert p.history_list._rows[0].label.text() == "创世记 1:1-3"
    assert len(p.history_list._rows) == 2


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


def test_cross_chapter_change_resets_verses():
    """跨章改起章→起节归 1；改止章→止节跳到该章末节。"""
    p = _panel()
    _goto_genesis(p)
    _switch(p, NavigationPanel.MODE_CROSS)
    p.cross_start_ch.setValue(2)
    assert p.cross_start_v.value() == 1
    p.cross_end_ch.setValue(3)
    assert p.cross_end_v.value() == 24  # 创 3 共 24 节
    # 历史定位仍能精确回填节号（先归位再显式设值）
    sel = ScriptureSelection.expand_cross_chapter(
        "创世记", 2, 3, 3, 20, _DB.get_verse_count
    )
    p.sync_from_selection(sel)
    assert p.cross_start_v.value() == 3
    assert p.cross_end_v.value() == 20
