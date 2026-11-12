"""节号与正文不可分：自绘行布局下任何宽度都不产生「节号悬空」行。

断行/禁则由 ScriptureBody._relayout 自己实现，「节号+正文首字」是同一个
grp 原子。本测试扫描全部布局行，断言：
1) 没有任何行的最后一个绘制单元是节号（节号悬空）
2) 行首不出现收尾标点、行尾不出现开引号（禁则）
3) 不可分簇的正确性（拉丁词、数字组、标点并簇）
"""

import sys

from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ui.display.scripture_display import (
    ScriptureDisplay, _clusters, _is_closing_punct, _is_opening_punct,
)

# 列王纪下 1 章节选（含引号、问号等标点的长句，历史上出过节号悬空）
TEXTS = [
    "亚哈谢在撒马利亚，从楼房的栏杆里掉下来，就病了；于是差遣使者说：你们去问以革伦的神巴力西卜，我这病能好不能好。",
    "但耶和华的使者对提斯比人以利亚说：你起来，去迎着撒马利亚王的使者，对他们说：你们去问以革伦神巴力西卜，岂因以色列中没有神吗？",
    "所以耶和华如此说：你必不下你所上的床，必定要死！",
    "使者就回来见王，王问他们说：你们为什么回来呢？",
    "使者回答说：有一个人迎着我们来，对我们说：你们去见差你们来的王，对他说：耶和华如此说，你差人去问以革伦神巴力西卜，岂因以色列中没有神吗？",
    "王就差遣车马和大军往那里去，黑夜就到了那里。他翻墙就逃走了。",
    "王吩咐他们说：你们来看那个人，他的话是怎样说的。",
    "以利亚回答说：我若是神人，愿火从天上降下来，烧灭你和你那五十人！于是有火从天上降下来，烧灭五十夫长和他那五十人。",
]

CAPTION_VERSES = [
    (3, 1, "〔新娘〕他所爱的对我说：我的佳偶，你甚美丽。", [], ["（细拉）"]),
]


def _make_display():
    w = ScriptureDisplay()
    w.resize(800, 600)
    w.punct_halfwidth = True
    w.verse_num_gap_left = 20
    w.verse_num_gap_right = 15
    return w


def _scan_lines(body):
    """返回 (行尾样式列表, 行首字符列表, 行尾字符列表)。"""
    tails, heads, lasts = [], [], []
    for line in body._lines:
        cells = [c for c in line["cells"] if c["k"] == "t"]
        if not cells:
            tails.append(None); heads.append(None); lasts.append(None)
            continue
        tails.append(cells[-1]["style"])
        heads.append(cells[0]["text"][0])
        lasts.append(cells[-1]["text"][-1])
    return tails, heads, lasts


def test_clusters_basic():
    cs = _clusters("起初神创造天地")
    assert [t for k, t in cs] == list("起初神创造天地")
    # 收尾标点并向前簇（行首禁则）
    cs = _clusters("神说，要有光。")
    assert cs[1][1] == "说，"
    assert cs[-1][1] == "光。"
    # 开括号向后簇（行尾禁则）
    cs = _clusters("（注）他说")
    assert cs[0][1] == "（注）"
    # 拉丁词一簇
    cs = _clusters("In the beginning God created")
    words = [t for k, t in cs if k == "c"]
    assert "beginning" in words and "created" in words
    # 数字组/撇号词一簇
    assert _clusters("1,000人")[0][1] == "1,000"
    assert _clusters("don’t go")[0][1] == "don’t"


def test_number_never_orphans_across_widths():
    w = _make_display()
    verses = [(1, i, t) for i, t in enumerate(TEXTS, start=1)]
    w.set_scripture("列王纪下", 1, 1, len(verses), verses)
    body = w.text_display
    for tw in range(120, 1301, 13):
        body.set_text_width(tw)
        tails, _heads, _lasts = _scan_lines(body)
        for idx, tail in enumerate(tails):
            assert tail != "num", f"宽度 {tw} 第 {idx} 行节号悬空"


def test_number_never_orphans_with_captions():
    w = _make_display()
    w.set_scripture("雅歌", 3, 1, 1, CAPTION_VERSES)
    body = w.text_display
    for tw in range(120, 901, 11):
        body.set_text_width(tw)
        tails, _heads, _lasts = _scan_lines(body)
        for idx, tail in enumerate(tails):
            assert tail != "num", f"宽度 {tw} 第 {idx} 行节号悬空（题注节）"


def test_kinsoku_across_widths():
    w = _make_display()
    verses = [(1, i, t) for i, t in enumerate(TEXTS, start=1)]
    w.set_scripture("列王纪下", 1, 1, len(verses), verses)
    body = w.text_display
    for punct_on in (True, False):
        w.punct_halfwidth = punct_on
        w._render_scripture()
        for tw in range(150, 1301, 17):
            body.set_text_width(tw)
            _tails, heads, lasts = _scan_lines(body)
            for idx, (h, l) in enumerate(zip(heads, lasts)):
                if h is not None:
                    assert not _is_closing_punct(h), f"行首标点：宽度 {tw} 行 {idx}「{h}」"
                    assert not _is_opening_punct(l), f"行尾开引号：宽度 {tw} 行 {idx}「{l}」"


def test_english_left_align_and_binding():
    w = _make_display()
    verses = [(1, i, t) for i, t in enumerate([
        "In the beginning God created the heaven and the earth.",
        "And the earth was without form, and void; and darkness was upon the face of the deep.",
        "And God said, Let there be light: and there was light.",
    ], start=1)]
    w.set_scripture("Genesis", 1, 1, 3, verses)
    assert w._text_justify is False
    body = w.text_display
    for tw in range(150, 901, 11):
        body.set_text_width(tw)
        tails, _heads, _lasts = _scan_lines(body)
        for idx, tail in enumerate(tails):
            assert tail != "num", f"宽度 {tw} 第 {idx} 行节号悬空（英文）"
