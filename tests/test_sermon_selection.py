"""画布 Shift 连续选区间。"""

from ui.sermon.editor.canvas import selection_range_ids


def test_selection_range_ids_basic():
    order = ["a", "b", "c", "d"]
    assert selection_range_ids(order, "b", "d") == ["b", "c", "d"]
    assert selection_range_ids(order, "d", "b") == ["b", "c", "d"]


def test_selection_range_ids_no_anchor():
    order = ["a", "b", "c"]
    assert selection_range_ids(order, None, "c") == ["c"]
    assert selection_range_ids(order, "missing", "a") == ["a"]


def test_selection_range_ids_bad_target():
    assert selection_range_ids(["a"], "a", "x") == ["x"]
    assert selection_range_ids(["a"], "a", "") == []
