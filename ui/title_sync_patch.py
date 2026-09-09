"""修复逻辑连续节选择变化后，投影顶部标题偶尔未同步的问题。"""


def _logical_title(selection, verses):
    """根据当前实际渲染的逻辑经文行生成标题范围。"""
    if not selection.is_simple or not verses:
        return selection.title()

    span = selection.spans[0]
    starts = []
    ends = []
    for row in verses:
        if row is None or len(row) < 2:
            continue
        label = str(row[1] or "").strip()
        if not label:
            continue
        try:
            if "-" in label:
                left, right = label.split("-", 1)
                start = int(left)
                end = int(right)
            else:
                start = end = int(label)
        except (TypeError, ValueError):
            continue
        starts.append(start)
        ends.append(end)

    if not starts:
        return selection.title()

    logical_start = min(starts)
    logical_end = max(ends)
    unit = "篇" if selection.book == "诗篇" else "章"
    if logical_start == logical_end:
        body = str(logical_start)
    else:
        body = f"{logical_start}-{logical_end}"
    return f"{selection.book}{span.chapter}{unit}{body}节"


def install_title_sync_patch():
    """替换 ScriptureDisplay 的选择标题生成逻辑。"""
    from .scripture_display import ScriptureDisplay

    def set_from_selection(self, selection, verses):
        title = _logical_title(selection, verses)
        self.set_scripture(
            selection.book,
            selection.primary_chapter,
            selection.primary_start,
            selection.primary_end,
            verses,
            title=title,
            show_chapter_nums=selection.is_multi_chapter,
        )

    ScriptureDisplay.set_from_selection = set_from_selection
