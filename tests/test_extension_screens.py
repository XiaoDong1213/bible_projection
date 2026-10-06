from ui.display.screens import (
    extension_open_mode,
    resolve_saved_output,
    screen_choice_label,
)


def test_open_mode_one_two_three():
    assert extension_open_mode(0) == "none"
    assert extension_open_mode(1) == "none"
    assert extension_open_mode(2) == "direct"
    assert extension_open_mode(3) == "ask"
    assert extension_open_mode(6) == "ask"


def test_resolve_saved_output_keeps_last():
    name, fallback = resolve_saved_output(["A", "B"], "B")
    assert name == "B"
    assert fallback is False


def test_resolve_saved_output_unplugged_falls_back():
    name, fallback = resolve_saved_output(["A"], "B")
    assert name == "A"
    assert fallback is True


def test_resolve_saved_output_empty():
    name, fallback = resolve_saved_output([], "A")
    assert name is None
    assert fallback is False


def test_screen_choice_label():
    assert "扩展屏 1" in screen_choice_label(1, 1280, 1024)
    assert "1280×1024" in screen_choice_label(1, 1280, 1024)
