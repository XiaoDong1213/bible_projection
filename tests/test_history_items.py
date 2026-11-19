"""历史列表增量更新与引用定位：删除/改写不再整列重建、删错位根除。"""

from __future__ import annotations

import sys
import unittest

from PyQt6.QtWidgets import QApplication

from ui.history.items import HistoryItemWidget, HistoryListWidget


class HistoryItemsTests(unittest.TestCase):
    def setUp(self):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self.listw = HistoryListWidget()

    def test_signals_emit_row_reference(self):
        """删除信号携带行 widget 本身，定位不依赖易错位的行号。"""
        self.listw.set_entries(["创 1:1-5", "创 1:1-9", "约 3:16"])
        got = []
        self.listw.item_deleted.connect(got.append)
        row = self.listw._rows[1]
        row._on_delete()
        self.assertEqual(got, [row])
        self.assertEqual(self.listw.index_of(row), 1)

    def test_remove_entry_only_drops_one_row(self):
        """remove_entry 只摘一行：其余行保留、选中位随删除平移。"""
        self.listw.set_entries(["a", "b", "c"])
        self.listw.set_selected_index(2)
        self.listw.remove_entry(0)
        self.assertEqual(len(self.listw._rows), 2)
        self.assertEqual(self.listw.selected_index(), 1)
        self.assertEqual(self.listw._rows[0].label.text(), "b")
        self.assertEqual(self.listw._rows[1].label.text(), "c")

    def test_update_entry_text_updates_label_and_tooltip(self):
        """增量改写一行文字，行数与其它行不受影响。"""
        self.listw.set_entries(["创 1:1-5", "约 3:16"])
        self.listw.update_entry_text(0, "创 1:1-9")
        self.assertEqual(self.listw._rows[0].label.text(), "创 1:1-9")
        self.assertEqual(self.listw._rows[0].toolTip(), "创 1:1-9")
        self.assertEqual(self.listw._rows[1].label.text(), "约 3:16")

    def test_index_of_unknown_row_returns_negative(self):
        """行已不在列表（deleteLater 后误触发）时定位为 -1，调用方安全忽略。"""
        self.listw.set_entries(["a"])
        orphan = HistoryItemWidget("x")
        self.assertEqual(self.listw.index_of(orphan), -1)

    def test_buttons_compact_icons_always_visible(self):
        """按钮为 28px 彩色 SVG 图标、常驻显示。"""
        row = HistoryItemWidget("创 1:1-5")
        self.assertTrue(row.copy_btn.isVisibleTo(row))
        self.assertTrue(row.delete_btn.isVisibleTo(row))
        self.assertEqual(row.copy_btn.width(), 28)
        self.assertEqual(row.delete_btn.width(), 28)
        self.assertFalse(row.copy_btn.icon().isNull())
        self.assertFalse(row.delete_btn.icon().isNull())
        self.assertFalse(row.copy_btn.text())
        self.assertFalse(row.delete_btn.text())

    def test_narrow_row_shows_short_not_ellipsis(self):
        """按标签真实宽度降级：全名放得下显示全名，放不下显示简称，极窄才截断。

        setFixedWidth 绕开 QLabel 的 minimumSizeHint（它按当前文本顶住，
        resize 会拒绝变窄）。"""
        full = "创世记 1:1-5（和合本）"
        short = "创 1:1-5"
        row = HistoryItemWidget(full, short)
        fm = row.label.fontMetrics()
        # 宽：全名放得下
        row.label.setFixedWidth(fm.horizontalAdvance(full) + 4)
        row.label._apply_elide()
        self.assertEqual(row.label.text(), full)
        # 窄：全名放不下、简称放得下
        row.label.setFixedWidth(fm.horizontalAdvance(short) + 4)
        row.label._apply_elide()
        self.assertEqual(row.label.text(), short)
        # 极窄：简称也放不下，截断兜底
        row.label.setFixedWidth(20)
        row.label._apply_elide()
        self.assertTrue(row.label.text().endswith("…"))

    def test_delete_middle_keeps_scrollable_order(self):
        """多记录下删除中间行：剩余行顺序与数据一致（30 条模拟）。"""
        texts = [f"创 {i}:1" for i in range(30)]
        self.listw.set_entries(texts)
        self.listw.remove_entry(15)
        remaining = [row.label.text() for row in self.listw._rows]
        self.assertEqual(len(remaining), 29)
        self.assertEqual(remaining[14], "创 14:1")
        self.assertEqual(remaining[15], "创 16:1")
        self.assertNotIn("创 15:1", remaining)


if __name__ == "__main__":
    unittest.main()
