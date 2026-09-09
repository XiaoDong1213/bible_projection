"""连续节逻辑范围同步补丁。

数据库中的“—”属于前一节，例如 13 + 14(—) => 13-14。
这里把物理选择扩展为逻辑选择，统一供历史记录和左侧范围控件使用。
"""

from .selection import ScriptureSelection, VerseSpan


def normalize_selection(db, selection):
    if selection is None or not isinstance(selection, ScriptureSelection):
        return selection

    normalized = []
    changed = False
    for span in selection.spans:
        logical = db.get_logical_verses(
            selection.book,
            span.chapter,
            span.start,
            span.end,
        )
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


def install_logical_selection_patch():
    from .navigation_panel import NavigationPanel

    if getattr(NavigationPanel, "_logical_selection_patch_installed", False):
        return

    original_load_history = NavigationPanel.load_history
    original_add_history = NavigationPanel.add_selection_to_history
    original_sync = NavigationPanel.sync_from_selection

    def load_history(self, history_list):
        normalized = []
        for entry in history_list or []:
            selection = ScriptureSelection.from_history_entry(entry)
            if selection is not None:
                normalized.append(normalize_selection(self.db, selection).to_history_entry())
        return original_load_history(self, normalized)

    def add_selection_to_history(self, selection):
        selection = normalize_selection(self.db, selection)
        return original_add_history(self, selection)

    def sync_from_selection(self, selection):
        selection = normalize_selection(self.db, selection)
        return original_sync(self, selection)

    NavigationPanel.load_history = load_history
    NavigationPanel.add_selection_to_history = add_selection_to_history
    NavigationPanel.sync_from_selection = sync_from_selection
    NavigationPanel._logical_selection_patch_installed = True
