"""讲篇版式预设（精简母版槽位，非完整 Slide Master）。"""

from __future__ import annotations

from core.sermon.model import (
    ASPECT_SIZE,
    Background,
    Element,
    ElementStyle,
    Slide,
    new_id,
)

# id -> (显示名, 说明)
LAYOUT_PRESETS: list[tuple[str, str, str]] = [
    ("title", "标题页", "大标题 + 副标题"),
    ("scripture", "经文页", "上方出处 + 正文"),
    ("bullets", "要点", "标题 + 条目"),
    ("two_col", "双栏", "左右两栏文字"),
    ("full_image", "全图", "居中提示，可换背景图"),
]


def _text(
    content: str,
    x: float,
    y: float,
    w: float,
    h: float,
    style: ElementStyle,
    z: int,
) -> Element:
    return Element(
        id=new_id("el_"),
        type="text",
        x=x,
        y=y,
        w=w,
        h=h,
        content=content,
        z=z,
        style=style.clone(),
    )


def _shape(
    kind: str,
    x: float,
    y: float,
    w: float,
    h: float,
    style: ElementStyle,
    z: int,
) -> Element:
    return Element(
        id=new_id("el_"),
        type="shape",
        x=x,
        y=y,
        w=w,
        h=h,
        z=z,
        shape=kind if kind in ("rect", "ellipse") else "rect",
        style=style.clone(),
    )


def apply_layout(slide: Slide, layout_id: str, aspect: str = "16:9") -> None:
    """用预设替换当前页元素（保留背景色/图）。"""
    cw, ch = ASPECT_SIZE.get(aspect, ASPECT_SIZE["16:9"])
    bg = slide.background
    slide.animations.clear()
    slide.background = bg if bg is not None else Background()

    title_style = ElementStyle(font_size=44, color="#FFFFFF", align="center", bold=True)
    body_style = ElementStyle(font_size=28, color="#F0F0F0", align="left", line_spacing=140)
    sub_style = ElementStyle(font_size=24, color="#CCCCCC", align="center")

    if layout_id == "title":
        els = [
            _text("讲题标题", cw * 0.1, ch * 0.32, cw * 0.8, ch * 0.18, title_style, 0),
            _text("副标题或讲员", cw * 0.15, ch * 0.55, cw * 0.7, ch * 0.1, sub_style, 1),
        ]
    elif layout_id == "scripture":
        ref = ElementStyle(font_size=22, color="#FFD700", align="center", bold=True)
        verse = ElementStyle(font_size=32, color="#FFFFFF", align="center", line_spacing=150)
        els = [
            _text("约翰福音 3:16", cw * 0.1, ch * 0.12, cw * 0.8, ch * 0.1, ref, 0),
            _text(
                "神爱世人，甚至将他的独生子赐给他们…",
                cw * 0.1,
                ch * 0.28,
                cw * 0.8,
                ch * 0.5,
                verse,
                1,
            ),
        ]
    elif layout_id == "bullets":
        els = [
            _text("要点标题", cw * 0.08, ch * 0.08, cw * 0.84, ch * 0.12, title_style, 0),
            _text(
                "• 第一点\n• 第二点\n• 第三点",
                cw * 0.12,
                ch * 0.28,
                cw * 0.76,
                ch * 0.55,
                body_style,
                1,
            ),
        ]
    elif layout_id == "two_col":
        head = ElementStyle(font_size=36, color="#FFFFFF", align="center", bold=True)
        col = ElementStyle(font_size=24, color="#F0F0F0", align="left", line_spacing=140)
        els = [
            _text("双栏标题", cw * 0.08, ch * 0.06, cw * 0.84, ch * 0.12, head, 0),
            _text("左栏内容", cw * 0.06, ch * 0.24, cw * 0.42, ch * 0.6, col, 1),
            _text("右栏内容", cw * 0.52, ch * 0.24, cw * 0.42, ch * 0.6, col, 2),
        ]
    elif layout_id == "full_image":
        hint = ElementStyle(font_size=22, color="#AAAAAA", align="center")
        mask = ElementStyle(color="#000000", opacity=0.45)
        els = [
            _shape("rect", 0, ch * 0.72, float(cw), ch * 0.28, mask, 0),
            _text("在此输入说明（可换背景图）", cw * 0.1, ch * 0.78, cw * 0.8, ch * 0.14, hint, 1),
        ]
    else:
        els = [
            _text("在此输入", cw * 0.15, ch * 0.35, cw * 0.7, ch * 0.2, title_style, 0),
        ]

    slide.elements = els
