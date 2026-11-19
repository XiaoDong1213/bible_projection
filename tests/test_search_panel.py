"""全文搜索面板：历史胶囊全部显示、截断阈值、防抖不记历史、Flow 换行。"""

from __future__ import annotations

import sys
import unittest

from PyQt6.QtWidgets import QApplication, QPushButton

_APP = QApplication.instance() or QApplication(sys.argv)

from core.database import BibleDatabase
from ui.fulltext_search.flow_layout import FlowLayout
from ui.fulltext_search.panel import ScriptureSearchWidget
from ui.fulltext_search.query import BookScopePanel

_DB = BibleDatabase()


class FlowLayoutTests(unittest.TestCase):
    def test_wrap_into_two_lines(self):
        """容器宽度不够时自动换行：heightForWidth 增大、第二行坐标换行。"""
        host = QPushButton()
        flow = FlowLayout(host, spacing=6)
        for _ in range(3):
            btn = QPushButton()
            btn.setFixedSize(100, 30)
            flow.addWidget(btn)
        # 单行宽 100*3+6*2=312：宽容器一行放下
        one_line = flow.heightForWidth(400)
        two_lines = flow.heightForWidth(220)
        self.assertLessEqual(one_line, 34)
        self.assertGreater(two_lines, one_line)


class SearchPanelTests(unittest.TestCase):
    def setUp(self):
        self.panel = ScriptureSearchWidget(_DB, config=None)

    def test_history_packs_single_line(self):
        """历史胶囊单行装箱：宽够全放，宽不够只放放得下的。"""
        while self.panel.history_layout.count():
            self.panel.history_layout.takeAt(0)
        words = [f"搜索词{i}" for i in range(10)]
        placed = self.panel._pack_history_chips(words, 10000)
        self.assertEqual(placed, 10)
        self.assertEqual(self.panel.history_layout.count(), 10)
        while self.panel.history_layout.count():
            self.panel.history_layout.takeAt(0)
        few = self.panel._pack_history_chips(words, 220)
        self.assertLess(few, 10, "窄行放不下 10 条")
        self.assertEqual(self.panel.history_layout.count(), few)

    def test_chip_label_truncates_at_twelve(self):
        """胶囊文字 12 字内原样，超长截到 11 字加省略号。"""
        self.assertEqual(ScriptureSearchWidget._chip_label("爱永不止息感谢主赐下"), "爱永不止息感谢主赐下")
        label = ScriptureSearchWidget._chip_label("爱永不止息感谢主赐下独生爱")
        self.assertEqual(label, "爱永不止息感谢主赐下独" + "…")
        self.assertTrue(label.endswith("…"))

    def test_debounce_search_does_not_touch_history(self):
        """防抖触发的搜索（remember=False）不写入历史。"""
        self.panel.history = ["已有词"]
        self.panel.search_input.setText("耶和华")
        self.panel.search(remember=False)
        self.assertEqual(self.panel.history, ["已有词"])

    def test_empty_query_clears_results(self):
        """输入清空后清掉结果区并提示，而不是留着上次结果。"""
        self.panel.search_input.setText("耶和华")
        self.panel.search(remember=False)
        self.panel.search_input.clear()
        self.panel.search(remember=False)
        self.assertEqual(self.panel.results, [])
        self.assertEqual(self.panel.result_header.text(), "请输入关键词")

    def test_clicking_result_records_history(self):
        """防抖搜索后点中结果/投影：该词补进历史并置顶。"""
        self.panel.history = []
        self.panel.search_input.setText("耶和华")
        got = []
        self.panel.result_activated.connect(got.append)
        self.panel._remember_then_emit({"k": 1})
        self.assertEqual(self.panel.history[0], "耶和华")
        self.assertEqual(got, [{"k": 1}])


class PagerTests(unittest.TestCase):
    """分页条：首页/尾页按钮 + 页码输入框跳页。"""

    def setUp(self):
        self.panel = ScriptureSearchWidget(_DB, config=None)
        self.panel.search_input.setText("耶和华")
        self.panel.search(remember=False)
        self.pages = (self.panel.total + self.panel.PAGE_SIZE - 1) // self.panel.PAGE_SIZE

    def test_first_last_buttons_jump(self):
        """首页按钮回第 1 页，尾页按钮到最后一页，边界处对应按钮禁用。"""
        self.assertGreater(self.pages, 1)
        self.panel.last_btn.click()
        self.assertEqual(self.panel.page, self.pages - 1)
        self.panel._update_pager()
        self.assertFalse(self.panel.last_btn.isEnabled())
        self.assertTrue(self.panel.first_btn.isEnabled())
        self.panel.first_btn.click()
        self.assertEqual(self.panel.page, 0)
        self.panel._update_pager()
        self.assertFalse(self.panel.first_btn.isEnabled())
        self.assertTrue(self.panel.last_btn.isEnabled())

    def test_page_input_jump_and_invalid_recovery(self):
        """输入页码回车跳页；越界夹到边界；非法输入恢复当前页显示。"""
        self.panel.page_input.setText("2")
        self.panel._apply_page_input()
        self.assertEqual(self.panel.page, 1)
        self.panel.page_input.setText("99999")
        self.panel._apply_page_input()
        self.assertEqual(self.panel.page, self.pages - 1)
        self.panel.page_input.setText("abc")
        self.panel._apply_page_input()
        self.assertEqual(self.panel.page_input.text(), str(self.pages))

    def test_page_input_disabled_without_results(self):
        """无结果时输入框禁用、显示 0，按钮全部禁用。"""
        panel = ScriptureSearchWidget(_DB, config=None)
        panel._update_pager()
        self.assertFalse(panel.page_input.isEnabled())
        self.assertEqual(panel.page_input.text(), "0")
        self.assertFalse(panel.first_btn.isEnabled())
        self.assertFalse(panel.last_btn.isEnabled())


class BookScopePanelTests(unittest.TestCase):
    def setUp(self):
        self.panel = ScriptureSearchWidget(_DB, config=None)

    def test_toggle_scope_flips_button_state(self):
        """「全部书卷」按钮切换内嵌范围区：每次 toggle，checked 与隐藏态都翻转。"""
        before_checked = self.panel.scope_btn.isChecked()
        before_hidden = self.panel.scope_panel.isHidden()
        self.panel._toggle_scope()
        self.assertEqual(self.panel.scope_btn.isChecked(), not before_checked)
        self.assertEqual(self.panel.scope_panel.isHidden(), not before_hidden)
        self.panel._toggle_scope()
        self.assertEqual(self.panel.scope_btn.isChecked(), before_checked)
        self.assertEqual(self.panel.scope_panel.isHidden(), before_hidden)

    def test_scope_changed_applies_live(self):
        """勾选 chip 实时广播并重搜；单选时按钮显示卷名。"""
        self.panel._toggle_scope()
        self.panel.search_input.setText("爱")
        self.panel.search(remember=False)
        got = []
        self.panel.scope_panel.scope_changed.connect(got.append)
        chip = self.panel.scope_panel._chips.get("创世记")
        self.assertIsNotNone(chip)
        chip.setChecked(True)
        self.assertEqual(len(got), 1)
        self.assertIn("创世记", got[0])
        self.assertEqual(self.panel.selected_books, {"创世记"})
        self.assertEqual(self.panel.scope_btn.text(), "创世记")

    def test_rebuild_resets_selected(self):
        """换译本重建：书卷列表重挂、已选范围清空。"""
        panel = BookScopePanel(_DB, {"创世记"})
        before = panel.selected_books()
        self.assertTrue(before)
        panel.rebuild(_DB)
        self.assertEqual(panel.selected_books(), set())
        self.assertEqual(panel.selected, set())
        self.assertTrue(len(panel._chips) >= 66)


if __name__ == "__main__":
    unittest.main()
