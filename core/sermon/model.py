"""讲篇数据模型（JSON 可序列化）。"""

from __future__ import annotations

import copy
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


Aspect = Literal["16:9", "4:3"]
BackgroundType = Literal["color", "image"]
ElementType = Literal["text", "image", "shape"]
Align = Literal["left", "center", "right", "justify"]
VAlign = Literal["top", "middle", "bottom", "distribute"]
ALIGN_H: tuple[str, ...] = ("left", "center", "right", "justify")
ALIGN_V: tuple[str, ...] = ("top", "middle", "bottom", "distribute")
AnimKind = Literal[
    "fade",
    "fly-up",
    "fly-down",
    "fly-left",
    "fly-right",
    "zoom",
    "wipe-up",
    "wipe-down",
    "wipe-left",
    "wipe-right",
]
AnimTrigger = Literal["on_click", "with_previous", "after_previous"]

ANIM_KINDS: tuple[str, ...] = (
    "fade",
    "fly-up",
    "fly-down",
    "fly-left",
    "fly-right",
    "zoom",
    "wipe-up",
    "wipe-down",
    "wipe-left",
    "wipe-right",
)

ANIM_KIND_LABELS = {
    "fade": "淡入",
    "fly-up": "飞入·自下",
    "fly-down": "飞入·自上",
    "fly-left": "飞入·自右",
    "fly-right": "飞入·自左",
    "zoom": "缩放",
    "wipe-up": "擦除·自下",
    "wipe-down": "擦除·自上",
    "wipe-left": "擦除·自右",
    "wipe-right": "擦除·自左",
}

ANIM_TRIGGERS: tuple[str, ...] = (
    "on_click",
    "with_previous",
    "after_previous",
)

ANIM_TRIGGER_LABELS = {
    "on_click": "单击时",
    "with_previous": "与上一动画同时",
    "after_previous": "上一动画之后",
}

# 换页过渡（整页切换，不同于元素入场）
TransitionKind = Literal["none", "smooth", "fade", "push", "wipe"]
TRANSITION_KINDS: tuple[str, ...] = ("none", "smooth", "fade", "push", "wipe")
TRANSITION_LABELS = {
    "none": "无切换",
    "smooth": "平滑",
    "fade": "淡出",
    "push": "切出",
    "wipe": "擦除",
}

# 逻辑画布像素（编辑/投影统一坐标系）
ASPECT_SIZE = {
    "16:9": (1920, 1080),
    "4:3": (1600, 1200),
}


def new_id(prefix: str = "") -> str:
    bare = uuid.uuid4().hex[:12]
    return f"{prefix}{bare}" if prefix else bare


# 内部别名，兼容模块内旧调用
_new_id = new_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Background:
    type: BackgroundType = "color"
    value: str = "#1A1A2E"
    fit: str = "cover"  # cover | contain

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "value": self.value, "fit": self.fit}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Background:
        data = data or {}
        bg_type = data.get("type", "color")
        if bg_type not in ("color", "image"):
            bg_type = "color"
        return cls(
            type=bg_type,
            value=str(data.get("value", "#1A1A2E")),
            fit=str(data.get("fit", "cover") or "cover"),
        )


@dataclass
class ElementStyle:
    font_family: str = "微软雅黑"
    font_size: int = 48
    color: str = "#FFFFFF"
    bold: bool = False
    italic: bool = False
    align: Align = "left"
    v_align: VAlign = "top"
    opacity: float = 1.0  # 0~1，形状填充/文字透明度
    wrap: bool = True  # 文本是否在框内自动换行

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ElementStyle:
        data = data or {}
        align = data.get("align", "left")
        if align not in ALIGN_H:
            align = "left"
        v_align = data.get("v_align", "top")
        if v_align not in ALIGN_V:
            v_align = "top"
        try:
            opacity = float(data.get("opacity", 1.0))
        except (TypeError, ValueError):
            opacity = 1.0
        opacity = max(0.0, min(1.0, opacity))
        return cls(
            font_family=str(data.get("font_family", "微软雅黑")),
            font_size=int(data.get("font_size", 48) or 48),
            color=str(data.get("color", "#FFFFFF")),
            bold=bool(data.get("bold", False)),
            italic=bool(data.get("italic", False)),
            align=align,
            v_align=v_align,
            opacity=opacity,
            wrap=bool(data.get("wrap", True)),
        )


@dataclass
class Element:
    id: str
    type: ElementType
    x: float
    y: float
    w: float
    h: float
    content: str = ""
    rotation: float = 0.0
    z: int = 0
    style: ElementStyle = field(default_factory=ElementStyle)
    shape: str = ""  # rect | ellipse

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "content": self.content,
            "rotation": self.rotation,
            "z": self.z,
            "style": self.style.to_dict(),
            "shape": self.shape,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Element:
        el_type = data.get("type", "text")
        if el_type not in ("text", "image", "shape"):
            el_type = "text"
        shape = str(data.get("shape", "") or "")
        if el_type == "shape" and shape not in ("rect", "ellipse"):
            shape = "rect"
        return cls(
            id=str(data.get("id") or _new_id("el_")),
            type=el_type,
            x=float(data.get("x", 0)),
            y=float(data.get("y", 0)),
            w=float(data.get("w", 200)),
            h=float(data.get("h", 80)),
            content=str(data.get("content", "")),
            rotation=float(data.get("rotation", 0) or 0),
            z=int(data.get("z", 0) or 0),
            style=ElementStyle.from_dict(data.get("style")),
            shape=shape,
        )

    def clone(self) -> Element:
        cloned = copy.deepcopy(self)
        cloned.id = _new_id("el_")
        return cloned


@dataclass
class AnimStep:
    id: str
    element_id: str
    kind: str = "fade"
    duration_ms: int = 500
    delay_ms: int = 0
    order: int = 0
    trigger: str = "on_click"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "element_id": self.element_id,
            "kind": self.kind,
            "duration_ms": self.duration_ms,
            "delay_ms": self.delay_ms,
            "order": self.order,
            "trigger": self.trigger,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnimStep:
        kind = str(data.get("kind", "fade") or "fade")
        if kind not in ANIM_KINDS:
            kind = "fade"
        trigger = str(data.get("trigger", "on_click") or "on_click")
        if trigger not in ANIM_TRIGGERS:
            trigger = "on_click"
        return cls(
            id=str(data.get("id") or _new_id("anim_")),
            element_id=str(data.get("element_id") or ""),
            kind=kind,
            duration_ms=max(50, int(data.get("duration_ms", 500) or 500)),
            delay_ms=max(0, int(data.get("delay_ms", 0) or 0)),
            order=int(data.get("order", 0) or 0),
            trigger=trigger,
        )

    def clone(self, element_id: str | None = None) -> AnimStep:
        return AnimStep(
            id=_new_id("anim_"),
            element_id=element_id if element_id is not None else self.element_id,
            kind=self.kind,
            duration_ms=self.duration_ms,
            delay_ms=self.delay_ms,
            order=self.order,
            trigger=self.trigger,
        )


def new_anim_step(
    element_id: str,
    kind: str = "fade",
    order: int = 0,
    *,
    trigger: str = "on_click",
) -> AnimStep:
    if kind not in ANIM_KINDS:
        kind = "fade"
    if trigger not in ANIM_TRIGGERS:
        trigger = "on_click"
    return AnimStep(
        id=_new_id("anim_"),
        element_id=element_id,
        kind=kind,
        duration_ms=500,
        delay_ms=0,
        order=order,
        trigger=trigger,
    )


@dataclass
class SlideTransition:
    """进入本页时的换页过渡（相对上一页）。"""

    kind: str = "none"
    duration_ms: int = 500

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "duration_ms": self.duration_ms}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SlideTransition:
        data = data or {}
        kind = str(data.get("kind", "none") or "none")
        if kind not in TRANSITION_KINDS:
            kind = "none"
        try:
            dur = int(data.get("duration_ms", 500) or 500)
        except (TypeError, ValueError):
            dur = 500
        return cls(kind=kind, duration_ms=max(0, min(3000, dur)))


@dataclass
class Slide:
    id: str
    background: Background = field(default_factory=Background)
    elements: list[Element] = field(default_factory=list)
    animations: list[AnimStep] = field(default_factory=list)
    transition: SlideTransition = field(default_factory=SlideTransition)

    def sorted_animations(self) -> list[AnimStep]:
        return sorted(self.animations, key=lambda a: (a.order, a.id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "background": self.background.to_dict(),
            "elements": [e.to_dict() for e in self.elements],
            "animations": [a.to_dict() for a in self.animations],
            "transition": self.transition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Slide:
        elements = [Element.from_dict(e) for e in (data.get("elements") or [])]
        elements.sort(key=lambda e: e.z)
        anims_raw = data.get("animations") or []
        animations = [
            AnimStep.from_dict(a) if isinstance(a, dict) else a for a in anims_raw
        ]
        return cls(
            id=str(data.get("id") or _new_id("slide_")),
            background=Background.from_dict(data.get("background")),
            elements=elements,
            animations=animations,
            transition=SlideTransition.from_dict(data.get("transition")),
        )

    def clone(self) -> Slide:
        id_map: dict[str, str] = {}
        elements: list[Element] = []
        for el in self.elements:
            cloned = el.clone()
            id_map[el.id] = cloned.id
            elements.append(cloned)
        animations = [
            a.clone(element_id=id_map.get(a.element_id, a.element_id))
            for a in self.animations
        ]
        return Slide(
            id=_new_id("slide_"),
            background=copy.deepcopy(self.background),
            elements=elements,
            animations=animations,
            transition=copy.deepcopy(self.transition),
        )


@dataclass
class SermonDocument:
    id: str
    title: str = "未命名讲篇"
    aspect: Aspect = "16:9"
    slides: list[Slide] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def canvas_size(self) -> tuple[int, int]:
        return ASPECT_SIZE.get(self.aspect, ASPECT_SIZE["16:9"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "id": self.id,
            "title": self.title,
            "aspect": self.aspect,
            "slides": [s.to_dict() for s in self.slides],
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SermonDocument:
        aspect = data.get("aspect", "16:9")
        if aspect not in ASPECT_SIZE:
            aspect = "16:9"
        slides = [Slide.from_dict(s) for s in (data.get("slides") or [])]
        if not slides:
            slides = [new_slide()]
        return cls(
            id=str(data.get("id") or _new_id("sermon_")),
            title=str(data.get("title") or "未命名讲篇"),
            aspect=aspect,
            slides=slides,
            meta=dict(data.get("meta") or {}),
        )

    def touch(self) -> None:
        self.meta["updated"] = _utc_now()
        self.meta.setdefault("created", self.meta["updated"])


def new_slide(background_color: str = "#1A1A2E") -> Slide:
    return Slide(
        id=_new_id("slide_"),
        background=Background(type="color", value=background_color),
        elements=[],
        animations=[],
        transition=SlideTransition(),
    )


def new_text_element(
    text: str = "双击编辑文字",
    *,
    canvas_w: int = 1920,
    canvas_h: int = 1080,
) -> Element:
    w, h = 800.0, 120.0
    return Element(
        id=_new_id("el_"),
        type="text",
        x=(canvas_w - w) / 2,
        y=(canvas_h - h) / 2,
        w=w,
        h=h,
        content=text,
        z=0,
        style=ElementStyle(),
    )


def new_image_element(
    rel_path: str,
    *,
    x: float = 200,
    y: float = 200,
    w: float = 640,
    h: float = 360,
) -> Element:
    return Element(
        id=_new_id("el_"),
        type="image",
        x=x,
        y=y,
        w=w,
        h=h,
        content=rel_path,
        z=0,
        style=ElementStyle(),
    )


def new_shape_element(
    *,
    shape: str = "rect",
    canvas_w: int = 1920,
    canvas_h: int = 1080,
    color: str = "#000000",
    opacity: float = 0.5,
) -> Element:
    if shape not in ("rect", "ellipse"):
        shape = "rect"
    w, h = canvas_w * 0.55, canvas_h * 0.28
    return Element(
        id=_new_id("el_"),
        type="shape",
        x=(canvas_w - w) / 2,
        y=(canvas_h - h) / 2,
        w=w,
        h=h,
        z=0,
        shape=shape,
        style=ElementStyle(color=color, opacity=max(0.0, min(1.0, opacity))),
    )


def new_document(title: str = "未命名讲篇", aspect: Aspect = "16:9") -> SermonDocument:
    now = _utc_now()
    return SermonDocument(
        id=_new_id("sermon_"),
        title=title,
        aspect=aspect,
        slides=[new_slide()],
        meta={"created": now, "updated": now},
    )
