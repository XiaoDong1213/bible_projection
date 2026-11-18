"""思高本圣咏集：篇标题数据（资源库锁定防回退）与「篇」单位显示。"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from core.database import BibleDatabase
from core.selection import chapter_unit
from ui.display.scripture_display import ScriptureDisplay

_SIGAO_DB = Path(__file__).resolve().parents[1] / "resources" / "思高本.db"


def test_chapter_unit():
    assert chapter_unit("圣咏集") == "篇"
    assert chapter_unit("诗篇") == "篇"
    assert chapter_unit("创世记") == "章"


def test_sigao_psalm_titles_imported():
    """思高本圣咏 1-150 篇每篇都有标题（第 10 篇 = 求主铲除恶霸）。"""
    db = BibleDatabase(str(_SIGAO_DB))
    titles = db.get_chapter_titles("圣咏集", 10)
    assert titles.get(1), "圣咏第 10 篇缺篇标题"
    assert "求主铲除恶霸" in titles[1][0]
    for ch in range(1, 151):
        assert db.get_chapter_titles("圣咏集", ch).get(1), f"第 {ch} 篇缺篇标题"
    db.close()


def test_display_title_uses_psalm_unit():
    """投影大标题：诗篇/圣咏集用「篇」，其余书卷保持「章」。"""
    w = ScriptureDisplay()
    w.resize(800, 600)
    w.set_scripture("圣咏集", 10, None, None, [], title=None)
    assert "圣咏集10篇" in w._title_text, w._title_text
    w.set_scripture("诗篇", 23, 1, 6, [], title=None)
    assert "诗篇23篇1-6节" in w._title_text, w._title_text
    w.set_scripture("创世记", 1, None, None, [], title=None)
    assert "创世记1章" in w._title_text, w._title_text
