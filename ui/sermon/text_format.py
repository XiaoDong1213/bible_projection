"""讲篇文本排版（编辑画布与放映舞台共用，避免循环导入）。"""

from __future__ import annotations

import json
import re

from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import QGraphicsTextItem

TEXT_PLACEHOLDERS = frozenset({"在此输入", "双击编辑文字"})
# 旧版多色 HTML（仍可读）；新导入用 bp-runs
RICH_HTML_MARK = "<!--bp-html-->"
RICH_RUNS_MARK = "<!--bp-runs-->"

_FALLBACK_FAMILIES = (
    "微软雅黑",
    "Microsoft YaHei",
    "Microsoft YaHei UI",
    "黑体",
    "SimHei",
    "Noto Sans CJK SC",
    "Source Han Sans SC",
    "Arial",
)

# 长 token 在前，避免 ExtraBold 被 Bold 抢先
_WEIGHT_TOKENS: tuple[tuple[str, QFont.Weight], ...] = (
    ("extralight", QFont.Weight.ExtraLight),
    ("ultralight", QFont.Weight.ExtraLight),
    ("semibold", QFont.Weight.DemiBold),
    ("demibold", QFont.Weight.DemiBold),
    ("extrabold", QFont.Weight.ExtraBold),
    ("ultrabold", QFont.Weight.ExtraBold),
    ("light", QFont.Weight.Light),
    ("thin", QFont.Weight.Thin),
    ("medium", QFont.Weight.Medium),
    ("heavy", QFont.Weight.Black),
    ("black", QFont.Weight.Black),
    ("bold", QFont.Weight.Bold),
    ("regular", QFont.Weight.Normal),
)


def is_text_placeholder(text: str | None) -> bool:
    raw = text or ""
    if raw.startswith(RICH_RUNS_MARK):
        try:
            runs = json.loads(raw[len(RICH_RUNS_MARK) :])
            plain = "".join(str(r.get("t", "")) for r in runs if isinstance(r, dict))
        except (json.JSONDecodeError, TypeError):
            plain = ""
        return plain.strip() in TEXT_PLACEHOLDERS
    if raw.startswith(RICH_HTML_MARK):
        from re import sub

        plain = sub(r"<[^>]+>", "", raw[len(RICH_HTML_MARK) :])
        return plain.strip() in TEXT_PLACEHOLDERS
    return raw.strip() in TEXT_PLACEHOLDERS


def is_rich_runs(text: str | None) -> bool:
    return (text or "").startswith(RICH_RUNS_MARK)


def is_rich_html(text: str | None) -> bool:
    return (text or "").startswith(RICH_HTML_MARK)


def parse_rich_runs(text: str | None) -> list[tuple[str, str]]:
    """返回 [(text, #RRGGBB), ...]。"""
    raw = text or ""
    if not raw.startswith(RICH_RUNS_MARK):
        return []
    try:
        data = json.loads(raw[len(RICH_RUNS_MARK) :])
    except (json.JSONDecodeError, TypeError):
        return []
    out: list[tuple[str, str]] = []
    if not isinstance(data, list):
        return out
    for item in data:
        if not isinstance(item, dict):
            continue
        t = str(item.get("t", ""))
        if t == "":
            continue
        c = str(item.get("c") or "#FFFFFF")
        if not c.startswith("#"):
            c = f"#{c}"
        out.append((t, c.upper() if len(c) == 7 else c))
    return out


def encode_rich_runs(runs: list[tuple[str, str]]) -> str:
    payload = [{"t": t, "c": c} for t, c in runs if t != ""]
    return RICH_RUNS_MARK + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def plain_from_content(content: str | None) -> str:
    """讲篇 content 的可见纯文本（含 bp-runs / 旧 bp-html）。"""
    raw = content or ""
    if is_rich_runs(raw):
        return "".join(t for t, _ in parse_rich_runs(raw))
    if is_rich_html(raw):
        return "".join(t for t, _ in _legacy_html_to_plain_runs(raw[len(RICH_HTML_MARK) :], "#FFFFFF"))
    return raw


def weight_from_font_name(name: str | None) -> QFont.Weight | None:
    """从「… 95 ExtraBold / 105 Heavy」族名解析字重。"""
    low = (name or "").lower()
    for token, weight in _WEIGHT_TOKENS:
        if token in low:
            return weight
    return None


def _family_candidates(name: str) -> list[str]:
    raw = (name or "").strip()
    out: list[str] = []
    if raw:
        out.append(raw)
        stripped = raw
        for token, _ in _WEIGHT_TOKENS:
            stripped = re.sub(rf"(?i)[\s\-_]*{re.escape(token)}\b", "", stripped)
        stripped = re.sub(r"\s+\d{2,3}\s*$", "", stripped.strip())
        stripped = re.sub(r"\s+\d+(\.\d+)?\s*$", "", stripped.strip())
        stripped = stripped.strip(" -_")
        if stripped and stripped not in out:
            out.append(stripped)
        parts = raw.split()
        for i in range(len(parts) - 1, 0, -1):
            prefix = " ".join(parts[:i]).strip()
            if prefix and prefix not in out:
                out.append(prefix)
    for fb in _FALLBACK_FAMILIES:
        if fb not in out:
            out.append(fb)
    return out


def _pick_installed_family(candidates: list[str]) -> str:
    """只返回本机已安装族名；未装的 PPT 字体名绝不当真（否则整页变成方框）。"""
    try:
        installed = list(QFontDatabase.families())
    except Exception:
        installed = []
    lower_map = {f.lower(): f for f in installed}
    for cand in candidates:
        hit = lower_map.get((cand or "").lower())
        if hit:
            return hit
    # 模糊：仅当候选足够长，避免「黑」误配
    for cand in candidates:
        cl = (cand or "").lower().replace(" ", "")
        if len(cl) < 4:
            continue
        for fam in installed:
            fl = fam.lower().replace(" ", "")
            if cl in fl or fl in cl:
                return fam
    for fb in _FALLBACK_FAMILIES:
        hit = lower_map.get(fb.lower())
        if hit:
            return hit
    return installed[0] if installed else "微软雅黑"


def apply_text_tab_stops(item: QGraphicsTextItem, distance_px: float | None) -> None:
    """PPT 默认制表位约 1 英寸；保留 \\t 时靠这个拉开栏目间距。"""
    try:
        dist = float(distance_px if distance_px is not None else 192.0)
    except (TypeError, ValueError):
        dist = 192.0
    dist = max(24.0, min(800.0, dist))
    option = item.document().defaultTextOption()
    option.setTabStopDistance(dist)
    item.document().setDefaultTextOption(option)


def resolve_qfont(
    family: str | None,
    *,
    pixel_size: int,
    bold: bool = False,
    italic: bool = False,
) -> QFont:
    """把 PPT 导入的族名解析成本机可用 QFont（含 ExtraBold/Heavy 字重）。"""
    named = weight_from_font_name(family)
    if named is not None:
        weight = named
    elif bold:
        weight = QFont.Weight.Bold
    else:
        weight = QFont.Weight.Normal
    if bold and int(weight) < int(QFont.Weight.Bold):
        weight = QFont.Weight.Bold

    chosen = _pick_installed_family(_family_candidates(family or ""))
    font = QFont(chosen)
    font.setPixelSize(max(8, int(pixel_size)))
    font.setWeight(weight)
    font.setItalic(bool(italic))
    return font


def _apply_runs(item: QGraphicsTextItem, runs: list[tuple[str, str]], style) -> None:
    plain = "".join(t for t, _ in runs)
    item.setPlainText(plain)
    if not plain:
        return
    cursor = QTextCursor(item.document())
    cursor.beginEditBlock()
    pos = 0
    for text, color in runs:
        if not text:
            continue
        end = pos + len(text)
        cursor.setPosition(pos)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        fmt = QTextCharFormat()
        fmt.setFont(item.font())
        qc = QColor(color)
        if not qc.isValid():
            qc = QColor(getattr(style, "color", None) or "#FFFFFF")
        fmt.setForeground(qc)
        cursor.setCharFormat(fmt)
        pos = end
    cursor.endEditBlock()


def _legacy_html_to_plain_runs(html_body: str, fallback: str) -> list[tuple[str, str]]:
    """尽力从旧 bp-html 抽出纯文本（颜色可能不准，重导 PPT 才完整）。"""
    from re import findall, sub

    parts = findall(r'<span style="color:([^"]+)">([^<]*)</span>', html_body)
    if parts:
        runs: list[tuple[str, str]] = []
        for color, text in parts:
            t = (
                text.replace("&nbsp;", " ")
                .replace("&#12288;", "\u3000")
                .replace("&amp;", "&")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replace("&quot;", '"')
            )
            if t:
                runs.append((t, color if color.startswith("#") else f"#{color}"))
        if runs:
            return runs
    plain = sub(r"<[^>]+>", "", html_body)
    plain = (
        plain.replace("&nbsp;", " ")
        .replace("&#12288;", "\u3000")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return [(plain, fallback or "#FFFFFF")] if plain else []


def apply_text_content(item: QGraphicsTextItem, content: str | None, style) -> None:
    """写入纯文本或导入的多色 runs（旧 HTML 兼容只读）。"""
    raw = content or ""
    fallback = getattr(style, "color", None) or "#FFFFFF"
    if is_rich_runs(raw):
        runs = parse_rich_runs(raw)
        if runs:
            _apply_runs(item, runs, style)
            return
        item.setPlainText("")
        return
    if is_rich_html(raw):
        body = raw[len(RICH_HTML_MARK) :]
        runs = _legacy_html_to_plain_runs(body, fallback)
        if runs:
            _apply_runs(item, runs, style)
        return
    text = "" if is_text_placeholder(raw) else raw
    if item.toPlainText() != text:
        item.setPlainText(text)


def fit_text_item_height(item: QGraphicsTextItem, min_h: float) -> float:
    """按文档实际高度抬高显示框，避免字被裁切。返回采用的高度。"""
    doc_h = float(item.document().size().height())
    h = max(float(min_h), doc_h, 8.0)
    return h


def apply_text_line_spacing(item: QGraphicsTextItem, percent: int | None) -> None:
    """按百分比设置讲篇文本行距（100=单倍）。"""
    try:
        pct = int(percent if percent is not None else 120)
    except (TypeError, ValueError):
        pct = 120
    pct = max(80, min(300, pct))
    kind = getattr(QTextBlockFormat.LineHeightTypes, "ProportionalHeight", 1)
    if hasattr(kind, "value"):
        kind = kind.value
    cursor = QTextCursor(item.document())
    cursor.beginEditBlock()
    block = item.document().begin()
    while block.isValid():
        cursor.setPosition(block.position())
        fmt = block.blockFormat()
        fmt.setLineHeight(float(pct), int(kind))
        cursor.setBlockFormat(fmt)
        block = block.next()
    cursor.endEditBlock()
