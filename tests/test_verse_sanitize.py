"""正文串珠载荷 {{[…]} }：剥机器块与紧随引用，保留校勘注。"""

from pathlib import Path

from core.database import BibleDatabase, sanitize_verse_text

_CUV = Path(__file__).resolve().parents[1] / "resources" / "和合本.db"


def test_sanitize_strips_abbrev_xref():
    raw = (
        "这应验经上所说：“亚伯拉罕信　神，这就算为他的义。”"
        '{{[{"b":1,"c":15,"v":"6"}]}}创15:6'
        "他又得称为　神的朋友。"
    )
    out = sanitize_verse_text(raw)
    assert "{{" not in out
    assert "创15:6" not in out
    assert "这就算为他的义。" in out
    assert "他又得称为" in out


def test_sanitize_keeps_full_book_when_variant_zuo():
    """校勘：只剥载荷，保留「历代志上3章1节作“但以利”」。"""
    raw = (
        "次子基利押（“基利押”"
        '{{[{"b":13,"c":3,"v":"1"}]}}历代志上3章1节'
        "作“但以利”），是作过迦密人拿八的妻亚比该所生的；"
    )
    out = sanitize_verse_text(raw)
    assert "{{" not in out
    assert "历代志上3章1节作“但以利”" in out
    assert out.startswith("次子基利押（“基利押”历代志上")


def test_sanitize_keeps_full_book_pure_xref():
    """见士师记9章1节：只剥载荷，保留书名章节。"""
    raw = (
        "从前打死耶路比设（就是“耶路巴力”。见"
        '{{[{"b":7,"c":9,"v":"1"}]}}士师记9章1节'
        "）儿子亚比米勒的是谁呢？"
    )
    out = sanitize_verse_text(raw)
    assert "{{" not in out
    assert "见士师记9章1节）儿子亚比米勒" in out


def test_sanitize_keeps_jie_tong_and_yuanwen():
    raw = (
        "你们都要受割礼（“受割礼”原文作“割阳皮”。"
        '{{[{"b":1,"c":17,"v":"14,23,24,25"}]}}'
        "14、23、24、25节同），这是我与你们立约的证据。"
    )
    out = sanitize_verse_text(raw)
    assert "{{" not in out
    assert "原文作“割阳皮”" in out
    assert "14、23、24、25节同" in out


def test_sanitize_keeps_book_jie_tong():
    raw = '住在那里{{[{"b":42,"c":4,"v":"26"}]}}路加福音4章26节同），我已吩咐'
    out = sanitize_verse_text(raw)
    assert "{{" not in out
    assert "路加福音4章26节同" in out


def test_sanitize_multi_abbrev_list():
    raw = '又说{{[{"b":2,"c":20,"v":"13"},{"b":5,"c":5,"v":"17"}]}}出20:13;申5:17，又说'
    out = sanitize_verse_text(raw)
    assert "{{" not in out
    assert "出20:13" not in out
    assert "申5:17" not in out
    assert out.endswith("，又说") or "，又说" in out


def test_cuv_genesis_james_samuel_live():
    if not _CUV.is_file():
        return
    db = BibleDatabase(str(_CUV))
    _, gen, *_ = next(r for r in db.get_logical_verses("创世记", 17, 11, 11))
    assert "{{" not in gen
    assert "14、23、24、25节同" in gen
    _, jas, *_ = next(r for r in db.get_logical_verses("雅各书", 2, 23, 23))
    assert "{{" not in jas
    assert "创15:6" not in jas
    _, sam, *_ = next(r for r in db.get_logical_verses("撒母耳记下", 3, 3, 3))
    assert "{{" not in sam
    assert "历代志上3章1节作“但以利”" in sam
    db.close()
