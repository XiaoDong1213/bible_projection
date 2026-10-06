"""扩展屏选择：块数规则与上次屏幕回退（纯函数，便于单测）。"""

from __future__ import annotations


def extension_open_mode(screen_count: int) -> str:
    """1 块不投，2 块直接投，3 块以上先问。"""
    if int(screen_count) <= 1:
        return "none"
    if int(screen_count) == 2:
        return "direct"
    return "ask"


def resolve_saved_output(
    extra_names: list[str], saved_name: str | None
) -> tuple[str | None, bool]:
    """在非主屏名单里解析上次屏幕。返回 (选中的名字, 是否因找不到而回退)。"""
    extras = [str(n) for n in extra_names if str(n or "").strip()]
    if not extras:
        return None, False
    saved = str(saved_name or "").strip()
    if saved and saved in extras:
        return saved, False
    return extras[0], bool(saved)


def screen_choice_label(index: int, width: int, height: int) -> str:
    return f"扩展屏 {int(index)}  {int(width)}×{int(height)}"
