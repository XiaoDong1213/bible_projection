"""小标题与正文间距：贴上公式（0 = 负空隙紧贴）、线性步进、全范围不重叠。"""

import sys


from PyQt6.QtWidgets import QApplication

_APP = QApplication.instance() or QApplication(sys.argv)

from ui.display.scripture_display import ScriptureDisplay

_VERSES = [
    (3, 1, "耶和华啊，我的敌人何其加增，有许多人起来攻击我。",
     ["求助的晨祷"], ["大卫逃避他儿子押沙龙的时候作的诗。"]),
]


def _make(gap):
    w = ScriptureDisplay()
    w.resize(1200, 900)
    w.verse_num_gap_left = 0
    w.verse_num_gap_right = 0
    w.show_scripture_titles = True
    w.show_captions = True
    w.verse_segmentation = False
    w.scripture_title_gap = gap
    w.set_scripture("诗篇", 3, 1, 1, _VERSES, title="t")
    return w


def test_gap_zero_is_negative_snug():
    """0 = 贴上：负空隙抵消行盒余量。"""
    w = _make(0)
    assert w._subtitle_vspace() < 0


def test_gap_stepping_is_linear_and_no_mode_jump():
    """0→1 只差约 1px（无模式切换跳变），全程单调。"""
    values = [(_make(g)._subtitle_vspace()) for g in (0, 1, 2, 3)]
    scale = _make(0).layout_scale()
    assert values[1] - values[0] >= 1.0, f"0→1 应可见变化: {values}"
    for v0, v1 in zip(values, values[1:]):
        assert 0 <= v1 - v0 <= 1.01, f"步进应 ≤1px: {values}"
    assert values[-1] - values[0] <= 3 * scale + 1, f"总跨度应线性: {values}"


def test_gap_positive_extends_snug_baseline():
    """gap=30 = 紧贴基准 + 30×scale（统一连续公式）。"""
    w30 = _make(30)
    h30 = w30._subtitle_vspace()
    h0 = _make(0)._subtitle_vspace()
    assert h30 - h0 == int(round(30 * w30.layout_scale()))


def test_snug_layout_no_overlap_and_no_blank_line():
    """贴上布局：无空行，且下一行盒顶 ≈ 小标题基线 + 2px（不重叠不变式）。"""
    w = _make(0)
    lines = w.text_display._lines
    assert not [l for l in lines if not l["cells"]], "不应有空行"
    sub, nxt = lines[0], lines[1]
    assert abs(nxt["y"] - (sub["baseline"] + w._px(2))) < 1.5


def test_snug_safe_under_extreme_line_spacing():
    """正文行距 300% 的极端组合下仍贴上：行盒不变式成立
    （负空隙恰好用尽基线以下余量，数学上保证字形不重叠；
    offscreen fallback 字体的 boundingRect 含 metrics 空隙，不作墨迹断言）。"""
    w = _make(0)
    w.line_spacing = 300
    w.set_scripture("诗篇", 3, 1, 1, _VERSES, title="t")
    lines = w.text_display._lines
    sub, nxt = lines[0], lines[1]
    assert abs(nxt["y"] - (sub["baseline"] + w._px(2))) < 1.5
