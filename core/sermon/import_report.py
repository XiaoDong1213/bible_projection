"""PPTX 导入差异说明（给状态栏 / 对话框用）。"""

from __future__ import annotations

from typing import Any


def import_notes_list(doc: Any) -> list[str]:
    notes = list(getattr(doc, "import_notes", None) or [])
    skipped = int(getattr(doc, "import_skip_count", 0) or 0)
    if skipped and not notes:
        return [f"共跳过 {skipped} 处对象"]
    if skipped and notes and not any("共" in n for n in notes):
        notes = list(notes) + [f"……共 {skipped} 处需注意"]
    return notes


def import_status_line(doc: Any, *, max_items: int = 3) -> str:
    notes = import_notes_list(doc)
    if not notes:
        return ""
    return "；".join(notes[:max_items])


def import_dialog_body(doc: Any, *, max_items: int = 12) -> str | None:
    notes = import_notes_list(doc)
    skipped = int(getattr(doc, "import_skip_count", 0) or 0)
    if not notes and not skipped:
        return None
    if skipped < 3 and len(getattr(doc, "import_notes", None) or []) < 3:
        return None
    lines = notes[:max_items]
    return (
        "部分内容已简化或跳过（图表 / SmartArt / 复杂动画等）：\n\n"
        + "\n".join(f"• {n}" for n in lines)
    )
