"""连续节逻辑范围：把物理选择扩展为逻辑单位。"""

from __future__ import annotations

from .selection import ScriptureSelection, VerseSpan


def normalize_selection(db, selection: ScriptureSelection | None) -> ScriptureSelection | None:
    """将选择中的物理节区间扩展为数据库中的逻辑连续节单位。"""
    if selection is None or not isinstance(selection, ScriptureSelection):
        return selection

    normalized = []
    changed = False
    for span in selection.spans:
        logical = db.get_logical_verses(selection.book, span.chapter, span.start, span.end)
        if not logical:
            normalized.append(span)
            continue
        start = min(int(item[2]) for item in logical)
        end = max(int(item[3]) for item in logical)
        new_span = VerseSpan(span.chapter, start, end)
        normalized.append(new_span)
        if new_span != span:
            changed = True
    if not changed:
        return selection
    return ScriptureSelection(book=selection.book, spans=tuple(normalized))
