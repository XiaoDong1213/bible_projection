"""搜索框 Space 行为补丁。"""

import re

from PyQt6.QtCore import Qt

from .search_widget import SearchWidget as _BaseSearchWidget


class SearchWidget(_BaseSearchWidget):
    """修正删除章节分隔符后再次输入章节并按 Space 的行为。"""

    def _on_special_key(self, key):
        if key == Qt.Key.Key_Space and self.state.stage == "verse" and self.state.selected_book:
            suffix = self._suffix().strip()
            # 例如：原来是“创世记 1:” → 删除“:” → 改成“创世记 12”。
            # 此时当前输入实际上又回到了“章节”阶段，Space 应重新生成“创世记 12:”。
            # 正常的节号输入是“1:12”，不会命中这里，因此不影响原有节号 Space。
            if not self.state.space_mode and re.fullmatch(r"\d+", suffix):
                chapter = int(suffix)
                maximum = self._chapter_count(self.state.selected_book)
                if 1 <= chapter <= maximum:
                    self._space_after_chapter()
                    return
        super()._on_special_key(key)
