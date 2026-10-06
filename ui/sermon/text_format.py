"""讲篇文本排版（编辑画布与放映舞台共用，避免循环导入）。"""

from __future__ import annotations

from PyQt6.QtGui import QTextBlockFormat, QTextCursor
from PyQt6.QtWidgets import QGraphicsTextItem

TEXT_PLACEHOLDERS = frozenset({"在此输入", "双击编辑文字"})


def is_text_placeholder(text: str | None) -> bool:
    return (text or "").strip() in TEXT_PLACEHOLDERS


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
