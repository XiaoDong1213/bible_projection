"""PPTX 导入导出（文本 / 图片 / 背景；组合形状递归；主题色回退）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from core.sermon.model import (
    ASPECT_SIZE,
    Background,
    Element,
    ElementStyle,
    SermonDocument,
    Slide,
    SlideTransition,
    new_anim_step,
    new_document,
    new_id,
    new_slide,
)
from core.sermon.store import SermonStore

logger = logging.getLogger(__name__)

EMU_PER_INCH = 914400
EMU_PER_PT = 12700  # 914400 / 72

# OOXML 主题色槽位常见默认（无 theme 解析时的回退）
_THEME_FALLBACK = {
    "dk1": "#000000",
    "lt1": "#FFFFFF",
    "dk2": "#1F497D",
    "lt2": "#EEECE1",
    "tx1": "#000000",
    "tx2": "#1F497D",
    "bg1": "#FFFFFF",
    "bg2": "#EEECE1",
    "accent1": "#4F81BD",
    "accent2": "#C0504D",
    "accent3": "#9BBB59",
    "accent4": "#8064A2",
    "accent5": "#4BACC6",
    "accent6": "#F79646",
    "hlink": "#0000FF",
    "folHlink": "#800080",
}

_SCHEME_ALIGN = {
    "l": "left",
    "ctr": "center",
    "r": "right",
    "just": "left",
    "dist": "left",
}


def _require_pptx():
    try:
        from pptx import Presentation  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("需要安装 python-pptx：pip install python-pptx") from exc


def _hex_rgb(r: int, g: int, b: int) -> str:
    return f"#{int(r) & 0xFF:02X}{int(g) & 0xFF:02X}{int(b) & 0xFF:02X}"


def _parse_hex(value: str) -> tuple[int, int, int]:
    raw = (value or "#1A1A2E").lstrip("#")
    if len(raw) != 6:
        raw = "1A1A2E"
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _aspect_from_size(width_emu: int, height_emu: int) -> str:
    if not width_emu or not height_emu:
        return "16:9"
    ratio = width_emu / height_emu
    return "16:9" if abs(ratio - 16 / 9) < abs(ratio - 4 / 3) else "4:3"


def _color_from_pptx_color(color) -> str | None:
    if color is None:
        return None
    try:
        rgb = getattr(color, "rgb", None)
        if rgb is not None:
            return _hex_rgb(rgb[0], rgb[1], rgb[2])
    except Exception:
        pass
    try:
        theme = getattr(color, "theme_color", None)
        if theme is not None:
            key = str(theme).split(".")[-1].lower()
            # MSO_THEME_COLOR.ACCENT_1 -> accent1
            key = key.replace("_", "")
            for name, hx in _THEME_FALLBACK.items():
                if name.lower() == key or key.endswith(name.lower()):
                    return hx
            # 常见枚举名
            mapping = {
                "dark1": "dk1",
                "light1": "lt1",
                "dark2": "dk2",
                "light2": "lt2",
                "accent1": "accent1",
                "accent2": "accent2",
                "accent3": "accent3",
                "accent4": "accent4",
                "accent5": "accent5",
                "accent6": "accent6",
                "hyperlink": "hlink",
                "followedhyperlink": "folHlink",
            }
            mapped = mapping.get(key)
            if mapped:
                return _THEME_FALLBACK[mapped]
    except Exception:
        pass
    return None


def _bg_blip_from_element(host_el):
    """从 cSld / bg 节点取出背景 blip（不依赖 fill.type）。"""
    if host_el is None:
        return None
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    # 只看背景区，避免误抓形状里的图片
    bg = host_el.find(f"{ns_p}bg")
    if bg is None and host_el.tag.endswith("}bg"):
        bg = host_el
    if bg is None:
        # python-pptx 的 background._element 有时是整个 cSld
        bg = host_el.find(f".//{ns_p}bg")
    if bg is None:
        return None
    return bg.find(f".//{ns_a}blip")


def _save_bg_image(store: SermonStore, sermon_id: str, blob: bytes, ext: str) -> Background:
    ext = (ext or ".png").lstrip(".")
    name = f"bg_{new_id()}.{ext}"
    dest = store.assets_dir(sermon_id) / name
    dest.write_bytes(blob)
    return Background(type="image", value=f"assets/{name}", fit="cover")


def _solid_bg_from_fill(fill) -> Background | None:
    try:
        fill_type = getattr(fill, "type", None)
        type_name = str(fill_type).lower() if fill_type is not None else ""
        if "solid" in type_name or "pattern" in type_name:
            hx = _color_from_pptx_color(getattr(fill, "fore_color", None))
            if hx:
                return Background(type="color", value=hx)
    except Exception:
        pass
    return None


def _slide_bg(slide, store: SermonStore, sermon_id: str) -> Background:
    """背景：XML blipFill 优先（兼容 WPS）；再试版式/母版；最后纯色。"""
    # 1) 本页背景图（不信 fill.type：WPS/部分文件 type 不可靠或 related API 不一致）
    try:
        hosts = []
        try:
            hosts.append(slide._element)  # cSld
        except Exception:
            pass
        try:
            hosts.append(slide.background._element)
        except Exception:
            pass
        for host in hosts:
            blip = _bg_blip_from_element(host)
            if blip is None:
                continue
            blob, ext = _resolve_blip_blob(slide.part, blip)
            if blob:
                return _save_bg_image(store, sermon_id, blob, ext)
    except Exception as exc:
        logger.warning("slide background image failed: %s", exc)

    # 2) 版式 / 母版背景图
    for attr in ("slide_layout",):
        try:
            layout = getattr(slide, attr, None)
            if layout is None:
                continue
            for part_host in (layout, getattr(layout, "slide_master", None)):
                if part_host is None:
                    continue
                try:
                    el = part_host._element
                except Exception:
                    continue
                blip = _bg_blip_from_element(el)
                if blip is None:
                    try:
                        blip = _bg_blip_from_element(part_host.background._element)
                    except Exception:
                        blip = None
                if blip is None:
                    continue
                blob, ext = _resolve_blip_blob(part_host.part, blip)
                if blob:
                    return _save_bg_image(store, sermon_id, blob, ext)
        except Exception as exc:
            logger.warning("layout/master background failed: %s", exc)

    # 3) 本页纯色
    try:
        solid = _solid_bg_from_fill(slide.background.fill)
        if solid is not None:
            return solid
    except Exception as exc:
        logger.warning("slide background color failed: %s", exc)

    return Background(type="color", value="#1A1A2E")


def _is_picture(shape) -> bool:
    try:
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        st = shape.shape_type
        if st == MSO_SHAPE_TYPE.PICTURE:
            return True
        if st == MSO_SHAPE_TYPE.PLACEHOLDER:
            try:
                _ = shape.image
                return True
            except Exception:
                return False
    except Exception:
        pass
    return hasattr(shape, "image") and not getattr(shape, "has_text_frame", False)


def _is_group(shape) -> bool:
    try:
        from pptx.enum.shapes import MSO_SHAPE_TYPE

        return shape.shape_type == MSO_SHAPE_TYPE.GROUP
    except Exception:
        return False


def _save_blob(store: SermonStore, sermon_id: str, blob: bytes, ext: str) -> str:
    ext = (ext or "png").lstrip(".")
    name = f"import_{new_id()}.{ext}"
    dest = store.assets_dir(sermon_id) / name
    dest.write_bytes(blob)
    return f"assets/{name}"


def _save_picture(shape, store: SermonStore, sermon_id: str) -> str | None:
    try:
        image = shape.image
        return _save_blob(store, sermon_id, image.blob, image.ext or "png")
    except Exception as exc:
        logger.warning("save picture failed: %s", exc)
        return None


def _resolve_blip_blob(part_or_slide, blip):
    """解析 r:embed / r:link 得到图片字节。

    part_or_slide: Slide / SlideLayout / SlideMaster，或其 .part。
    """
    from pptx.oxml.ns import qn

    embed = blip.get(qn("r:embed"))
    link = blip.get(qn("r:link"))
    rid = embed or link
    if not rid:
        return None, ".png"

    # 统一拿到 PackagePart
    pkg_part = getattr(part_or_slide, "part", part_or_slide)
    part = None

    # python-pptx 正确 API：related_part(rId)
    try:
        related_part = getattr(pkg_part, "related_part", None)
        if callable(related_part):
            part = related_part(rid)
    except Exception:
        part = None

    if part is None:
        try:
            rels = getattr(pkg_part, "rels", None)
            if rels is not None and rid in rels:
                rel = rels[rid]
                part = getattr(rel, "target_part", None)
                if part is None and link:
                    target = getattr(rel, "target_ref", None) or getattr(rel, "_target", None)
                    if target:
                        path = Path(str(target))
                        if path.is_file():
                            return path.read_bytes(), path.suffix or ".png"
        except Exception as exc:
            logger.warning("blip rel failed %s: %s", rid, exc)
            return None, ".png"

    if part is None:
        return None, ".png"
    try:
        blob = part.blob
        ext = Path(str(getattr(part, "partname", "x.png"))).suffix or ".png"
        return blob, ext
    except Exception as exc:
        logger.warning("blip blob failed: %s", exc)
        return None, ".png"


def _xfrm_box(host_el, ns_a: str, sx: float, sy: float):
    xfrm = host_el.find(f".//{ns_a}xfrm")
    if xfrm is None:
        # 有些在 spPr 下
        xfrm = host_el.find(f".//{ns_a}spPr/{ns_a}xfrm")
    x = y = 0.0
    w = h = 200.0
    if xfrm is None:
        return x, y, w, h
    off = xfrm.find(f"{ns_a}off")
    ext_el = xfrm.find(f"{ns_a}ext")
    if off is not None:
        x = float(off.get("x", 0) or 0) * sx
        y = float(off.get("y", 0) or 0) * sy
    if ext_el is not None:
        w = max(8.0, float(ext_el.get("cx", 0) or 0) * sx)
        h = max(8.0, float(ext_el.get("cy", 0) or 0) * sy)
    return x, y, w, h


def _import_pictures_via_xml(slide, store: SermonStore, sermon_id: str, sx: float, sy: float, z_start: int):
    """兜底：从 slide XML 抽 pic 与形状图片填充（覆盖 WPS/组合）。"""
    elements: list[Element] = []
    z = z_start
    seen_rids: set[str] = set()
    try:
        from pptx.oxml.ns import qn

        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        root = slide._element

        # 1) 标准 p:pic
        hosts = list(root.iter(f"{ns_p}pic"))
        # 2) 带 blipFill 的形状（图片填充）
        for sp in root.iter(f"{ns_p}sp"):
            if sp.find(f".//{ns_a}blipFill/{ns_a}blip") is not None:
                hosts.append(sp)

        for host in hosts:
            blip = host.find(f".//{ns_a}blip")
            if blip is None:
                continue
            rid = blip.get(qn("r:embed")) or blip.get(qn("r:link")) or ""
            # 同一 rid 允许多处使用（不同位置），用 rid+xfrm 去重
            x, y, w, h = _xfrm_box(host, ns_a, sx, sy)
            dedupe = f"{rid}:{round(x)}:{round(y)}:{round(w)}:{round(h)}"
            if dedupe in seen_rids:
                continue
            seen_rids.add(dedupe)

            blob, ext = _resolve_blip_blob(slide, blip)
            if not blob:
                continue
            rel = _save_blob(store, sermon_id, blob, ext)
            elements.append(
                Element(
                    id=new_id("el_"),
                    type="image",
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    content=rel,
                    z=z,
                )
            )
            z += 1
    except Exception as exc:
        logger.warning("xml picture import failed: %s", exc)
    return elements


def _pt_to_canvas_px(pt: float, sx: float) -> int:
    """PPT 磅值 → 逻辑画布像素（与坐标同一套缩放）。"""
    return max(12, int(round(float(pt) * EMU_PER_PT * float(sx))))


def _run_font_pt(run) -> float | None:
    try:
        size = getattr(getattr(run, "font", None), "size", None)
        if size is not None:
            return float(size.pt)
    except Exception:
        pass
    # XML 兜底：sz 为百分之一磅
    try:
        rPr = run._r.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}rPr"
        )
        if rPr is not None and rPr.get("sz"):
            return float(rPr.get("sz")) / 100.0
    except Exception:
        pass
    return None


def _para_default_font_pt(paragraph) -> float | None:
    try:
        pPr = paragraph._p.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}pPr"
        )
        if pPr is None:
            return None
        defRPr = pPr.find(
            "{http://schemas.openxmlformats.org/drawingml/2006/main}defRPr"
        )
        if defRPr is not None and defRPr.get("sz"):
            return float(defRPr.get("sz")) / 100.0
    except Exception:
        pass
    return None


def _scheme_hex(name: str | None) -> str | None:
    if not name:
        return None
    key = str(name).split(".")[-1].lower().replace("_", "")
    if key in _THEME_FALLBACK:
        return _THEME_FALLBACK[key]
    mapping = {
        "dark1": "dk1",
        "light1": "lt1",
        "dark2": "dk2",
        "light2": "lt2",
        "text1": "tx1",
        "text2": "tx2",
        "background1": "bg1",
        "background2": "bg2",
    }
    mapped = mapping.get(key)
    return _THEME_FALLBACK.get(mapped) if mapped else None


def _alpha_from_el(color_el) -> float:
    """OOXML alpha：100000=不透明；缺省 1.0。"""
    if color_el is None:
        return 1.0
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    al = color_el.find(f"{ns_a}alpha")
    if al is None:
        return 1.0
    try:
        return max(0.0, min(1.0, float(al.get("val", "100000")) / 100000.0))
    except ValueError:
        return 1.0


def _fill_from_sp_pr(sp_pr) -> tuple[str | None, float]:
    """从 spPr 读 solidFill → (hex, opacity)。"""
    if sp_pr is None:
        return None, 1.0
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    if sp_pr.find(f"{ns_a}noFill") is not None:
        return None, 1.0
    solid = sp_pr.find(f"{ns_a}solidFill")
    if solid is None:
        return None, 1.0
    srgb = solid.find(f"{ns_a}srgbClr")
    if srgb is not None:
        val = srgb.get("val")
        if val and len(val) == 6:
            return f"#{val.upper()}", _alpha_from_el(srgb)
    scheme = solid.find(f"{ns_a}schemeClr")
    if scheme is not None:
        hx = _scheme_hex(scheme.get("val"))
        if hx:
            return hx, _alpha_from_el(scheme)
    return None, 1.0


def _shape_fill(shape) -> tuple[str | None, float]:
    try:
        sp_pr = shape._element.spPr
        return _fill_from_sp_pr(sp_pr)
    except Exception:
        pass
    try:
        fill = shape.fill
        fill_type = getattr(fill, "type", None)
        type_name = str(fill_type).lower() if fill_type is not None else ""
        if "solid" in type_name:
            hx = _color_from_pptx_color(getattr(fill, "fore_color", None))
            return hx, 1.0
    except Exception:
        pass
    return None, 1.0


def _shape_geom_kind(shape) -> str:
    try:
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        prst = shape._element.spPr.find(f"{ns_a}prstGeom")
        if prst is not None:
            name = (prst.get("prst") or "rect").lower()
            if name in ("ellipse", "circle", "oval"):
                return "ellipse"
            return "rect"
    except Exception:
        pass
    return "rect"


def _text_wrap(shape) -> bool:
    try:
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        body = shape.text_frame._txBody.find(f"{ns_a}bodyPr")
        if body is not None:
            wrap = (body.get("wrap") or "").lower()
            if wrap in ("none", "off"):
                return False
    except Exception:
        pass
    return True


def _text_insets(shape, sx: float, sy: float) -> tuple[float, float, float, float]:
    """文本框内边距（逻辑像素）。"""
    l = t = r = b = 0.0
    try:
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        body = shape.text_frame._txBody.find(f"{ns_a}bodyPr")
        if body is not None:
            l = float(body.get("lIns", 0) or 0) * sx
            t = float(body.get("tIns", 0) or 0) * sy
            r = float(body.get("rIns", 0) or 0) * sx
            b = float(body.get("bIns", 0) or 0) * sy
    except Exception:
        pass
    return l, t, r, b


def _xml_align(shape) -> str | None:
    try:
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        for pPr in shape._element.iter(f"{ns_a}pPr"):
            algn = (pPr.get("algn") or "").lower()
            if algn in ("l", "left"):
                return "left"
            if algn in ("ctr", "center"):
                return "center"
            if algn in ("r", "right"):
                return "right"
            if algn:
                break
    except Exception:
        pass
    return None


def _text_style_from_shape(shape, sx: float = 1.0) -> ElementStyle:
    # PPT 默认制表位约 1 英寸 → 画布像素
    tab_px = max(24, int(round(float(EMU_PER_INCH) * float(sx))))
    style = ElementStyle(align="left", wrap=_text_wrap(shape), tab_stop=tab_px)
    try:
        from pptx.enum.text import PP_ALIGN

        align_map = {
            PP_ALIGN.LEFT: "left",
            PP_ALIGN.CENTER: "center",
            PP_ALIGN.RIGHT: "right",
            PP_ALIGN.JUSTIFY: "left",
        }
    except Exception:
        align_map = {}

    try:
        tf = shape.text_frame
        if not tf.paragraphs:
            return style
        first_p = tf.paragraphs[0]
        # PPT 空 alignment ≈ 左对齐；勿落成默认居中
        if first_p.alignment in align_map:
            style.align = align_map[first_p.alignment]
        else:
            style.align = _xml_align(shape) or "left"
        chosen = None
        chosen_para = first_p
        for p in tf.paragraphs:
            for run in p.runs:
                if (run.text or "").strip():
                    chosen = run
                    chosen_para = p
                    break
            if chosen:
                break
        if chosen is None and first_p.runs:
            chosen = first_p.runs[0]
            chosen_para = first_p
        if chosen is not None:
            font = chosen.font
            pt = _run_font_pt(chosen) or _para_default_font_pt(chosen_para)
            if pt is not None:
                style.font_size = _pt_to_canvas_px(pt, sx)
            fname = str(font.name or "")
            # 字重写在族名里（如 ExtraBold/Heavy）时，PPT 常仍标 b=0
            if _font_name_implies_bold(fname):
                style.bold = True
            elif font.bold is not None:
                style.bold = bool(font.bold)
            if font.italic is not None:
                style.italic = bool(font.italic)
            if fname:
                style.font_family = fname
            hx = (
                _color_from_pptx_color(getattr(font, "color", None))
                or _run_color_hex(chosen)
                or _para_def_color_hex(chosen_para)
            )
            style.color = hx or "#FFFFFF"
        else:
            style.color = "#FFFFFF"
        spacing = _paragraph_line_spacing_pct(chosen_para)
        if spacing is not None:
            style.line_spacing = spacing
    except Exception as exc:
        logger.warning("text style parse failed: %s", exc)
        style.color = "#FFFFFF"
    return style


def _paragraph_line_spacing_pct(paragraph) -> int | None:
    """PPT 行距 → 百分比（100=单倍）。"""
    try:
        ls = paragraph.line_spacing
    except Exception:
        return None
    if ls is None:
        return None
    try:
        # 倍数：1.0 / 1.5
        if isinstance(ls, (int, float)):
            return max(80, min(300, int(round(float(ls) * 100))))
        # Pt 绝对行距：相对默认字号估成倍数
        pt = float(ls.pt)
        base = _para_default_font_pt(paragraph) or 18.0
        if base <= 0:
            return None
        return max(80, min(300, int(round(pt / base * 100))))
    except Exception:
        return None


def _font_name_implies_bold(name: str) -> bool:
    """族名自带字重（阿里巴巴普惠体 … ExtraBold / Heavy 等）。"""
    low = (name or "").lower()
    return any(
        tok in low
        for tok in (
            "extrabold",
            "ultrabold",
            "semibold",
            "demibold",
            "heavy",
            "black",
            "bold",
        )
    )


def _expand_pptx_tabs(text: str) -> str:
    """保留 Tab；显示时靠 ElementStyle.tab_stop + QTextOption 制表位拉开。

    旧逻辑把 \\t 换成全角空格：字体缺失时全角空格也变成方框，栏目空隙消失。
    """
    return text or ""


def _shape_plain_text(shape) -> str:
    try:
        paragraphs = []
        for p in shape.text_frame.paragraphs:
            # 保留软换行：runs + br
            parts: list[str] = []
            try:
                for child in p._p:
                    tag = child.tag.split("}")[-1]
                    if tag == "r":
                        t_el = child.find(
                            "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
                        )
                        parts.append("" if t_el is None or t_el.text is None else t_el.text)
                    elif tag == "br":
                        parts.append("\n")
            except Exception:
                parts.append("".join(run.text or "" for run in p.runs) or (p.text or ""))
            paragraphs.append("".join(parts) if parts else (p.text or ""))
        # 不 strip 整段，避免吃掉有意空行；仅去首尾空白段外层
        text = "\n".join(paragraphs)
        return _expand_pptx_tabs(text.strip("\n"))
    except Exception:
        return ""


def _solid_fill_hex(solid) -> str | None:
    """解析 solidFill；空节点或无色值返回 None（表示继承）。"""
    if solid is None:
        return None
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    srgb = solid.find(f"{ns_a}srgbClr")
    if srgb is not None and srgb.get("val"):
        val = str(srgb.get("val")).strip()
        return val if val.startswith("#") else f"#{val}"
    scheme = solid.find(f"{ns_a}schemeClr")
    if scheme is not None:
        return _scheme_hex(scheme.get("val"))
    return None


def _rpr_color_hex(r_pr) -> str | None:
    if r_pr is None:
        return None
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    return _solid_fill_hex(r_pr.find(f"{ns_a}solidFill"))


def _para_def_color_hex(paragraph) -> str | None:
    """段落 defRPr / endParaRPr 上的默认字色（WPS 常把黄字写在这里）。"""
    try:
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        p = paragraph._p
        p_pr = p.find(f"{ns_a}pPr")
        if p_pr is not None:
            hx = _rpr_color_hex(p_pr.find(f"{ns_a}defRPr"))
            if hx:
                return hx
        return _rpr_color_hex(p.find(f"{ns_a}endParaRPr"))
    except Exception:
        return None


def _run_color_hex(run) -> str | None:
    """单个 run 的颜色；空 solidFill（继承）返回 None。"""
    try:
        hx = _color_from_pptx_color(getattr(run.font, "color", None))
        if hx:
            return hx
    except Exception:
        pass
    try:
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        return _rpr_color_hex(run._r.find(f"{ns_a}rPr"))
    except Exception:
        return None


def _html_escape(text: str) -> str:
    """转义 HTML，并保留空格/Tab/全角空格（默认 HTML 会折叠空白）。"""
    s = (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    s = _expand_pptx_tabs(s)
    s = s.replace("\u3000", "&#12288;")
    s = s.replace(" ", "&nbsp;")
    return s


# 与 ui.sermon.text_format.RICH_RUNS_MARK 一致；避免 core→ui 依赖，本地编码
_RICH_RUNS_MARK = "<!--bp-runs-->"


def _encode_rich_runs(runs: list[tuple[str, str]]) -> str:
    payload = [{"t": t, "c": c} for t, c in runs if t != ""]
    return _RICH_RUNS_MARK + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _shape_text_content(shape, sx: float = 1.0) -> tuple[str, ElementStyle]:
    """导入文字：多色 run 写成 bp-runs JSON；单色仍用纯文本。"""
    style = _text_style_from_shape(shape, sx=sx)
    plain = _shape_plain_text(shape)
    if not plain:
        return "", style

    try:
        runs: list[tuple[str, str]] = []
        colors: set[str] = set()
        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
        paragraphs = list(shape.text_frame.paragraphs)
        for pi, p in enumerate(paragraphs):
            # 段落 defRPr 常有真正字色；run 空 solidFill 时继承它
            para_color = _para_def_color_hex(p) or "#FFFFFF"
            if pi > 0:
                runs.append(("\n", para_color))
            try:
                for child in p._p:
                    tag = child.tag.split("}")[-1]
                    if tag == "r":
                        t_el = child.find(f"{ns_a}t")
                        t = "" if t_el is None or t_el.text is None else t_el.text
                        t = _expand_pptx_tabs(t)
                        if t == "":
                            continue
                        r_pr = child.find(f"{ns_a}rPr")
                        color = _rpr_color_hex(r_pr) or para_color
                        colors.add(color.upper())
                        runs.append((t, color if color.startswith("#") else f"#{color}"))
                    elif tag == "br":
                        runs.append(("\n", para_color))
            except Exception:
                for run in p.runs:
                    t = _expand_pptx_tabs(run.text or "")
                    if not t:
                        continue
                    color = _run_color_hex(run) or para_color
                    colors.add(color.upper())
                    runs.append((t, color if color.startswith("#") else f"#{color}"))
        if len(colors) <= 1:
            if len(colors) == 1:
                only = next(iter(colors))
                style.color = only if only.startswith("#") else f"#{only}"
            elif style.color in (None, "", "#FFFFFF"):
                # 单段无 run 色时仍可能有 defRPr
                hx = _para_def_color_hex(paragraphs[0]) if paragraphs else None
                if hx:
                    style.color = hx
            return plain, style
        if style.color in (None, "", "#FFFFFF"):
            for c in colors:
                if c.upper() not in ("#FFFFFF", "FFFFFF"):
                    style.color = c if c.startswith("#") else f"#{c}"
                    break
        return _encode_rich_runs(runs), style
    except Exception as exc:
        logger.warning("rich text import failed: %s", exc)
        return plain, style


def _group_local_scale(shape) -> tuple[float, float, int, int]:
    """组合 xfrm：child 坐标 → 父坐标的缩放，以及 chOff。

    slide = group_pos + (child - chOff) * (ext / chExt)
    """
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    scale_x = scale_y = 1.0
    ch_x = ch_y = 0
    try:
        xfrm = shape._element.find(f".//{ns_a}xfrm")
        if xfrm is None:
            return scale_x, scale_y, ch_x, ch_y
        ext = xfrm.find(f"{ns_a}ext")
        ch_ext = xfrm.find(f"{ns_a}chExt")
        ch_off = xfrm.find(f"{ns_a}chOff")
        if ch_off is not None:
            ch_x = int(ch_off.get("x", 0) or 0)
            ch_y = int(ch_off.get("y", 0) or 0)
        if ext is not None and ch_ext is not None:
            ecx = float(ext.get("cx", 0) or 0)
            ecy = float(ext.get("cy", 0) or 0)
            ccx = float(ch_ext.get("cx", 0) or 0)
            ccy = float(ch_ext.get("cy", 0) or 0)
            if ccx > 0:
                scale_x = ecx / ccx
            if ccy > 0:
                scale_y = ecy / ccy
    except Exception as exc:
        logger.warning("group xfrm scale failed: %s", exc)
    return scale_x, scale_y, ch_x, ch_y


def _iter_shapes(
    shapes,
    parent_offset=(0, 0),
    group_stack: tuple[int, ...] = (),
    scale: tuple[float, float] = (1.0, 1.0),
    ch_origin: tuple[int, int] = (0, 0),
):
    """递归展开组合。

    产出 (shape, left, top, width, height, scale_x, scale_y, group_stack)，
    坐标/尺寸为幻灯片 EMU（已乘组合缩放）。
    """
    sx, sy = scale
    ox, oy = ch_origin
    for shape in shapes:
        raw_l = int(getattr(shape, "left", 0) or 0)
        raw_t = int(getattr(shape, "top", 0) or 0)
        left = parent_offset[0] + (raw_l - ox) * sx
        top = parent_offset[1] + (raw_t - oy) * sy
        if _is_group(shape):
            try:
                gid = int(shape.shape_id)
            except Exception:
                gid = -1
            try:
                gx, gy, cox, coy = _group_local_scale(shape)
                stack = group_stack + ((gid,) if gid >= 0 else ())
                # 子坐标在本组 child 空间；组的 left/top 已是幻灯片 EMU
                yield from _iter_shapes(
                    shape.shapes,
                    (left, top),
                    stack,
                    (gx, gy),
                    (cox, coy),
                )
            except Exception as exc:
                logger.warning("group expand failed: %s", exc)
            continue
        raw_w = int(getattr(shape, "width", 0) or 0)
        raw_h = int(getattr(shape, "height", 0) or 0)
        yield shape, left, top, raw_w * sx, raw_h * sy, sx, sy, group_stack


# PPT presetSubtype 方向位（常见于飞入/擦除等）
_PPT_SUBTYPE_DIR = {
    1: "from-top",
    2: "from-right",
    4: "from-bottom",
    8: "from-left",
}

_PPT_FILTER_DIR = {
    "up": "from-top",
    "down": "from-bottom",
    "left": "from-left",
    "right": "from-right",
}

_FLY_FROM = {
    "from-top": "fly-down",
    "from-right": "fly-left",
    "from-bottom": "fly-up",
    "from-left": "fly-right",
}

_WIPE_FROM = {
    "from-top": "wipe-down",
    "from-right": "wipe-left",
    "from-bottom": "wipe-up",
    "from-left": "wipe-right",
}

_PPT_NODE_TRIGGER = {
    "clickeffect": "on_click",
    "witheffect": "with_previous",
    "aftereffect": "after_previous",
}


def _ppt_ms(value: str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or text in ("indefinite", "nil"):
        return None
    try:
        return max(0, int(float(text)))
    except ValueError:
        return None


def _direction_from_subtype(subtype: str | None) -> str | None:
    try:
        code = int(subtype or "0")
    except ValueError:
        return None
    # 组合方向取最低有效位
    for bit, kind in _PPT_SUBTYPE_DIR.items():
        if code & bit:
            return kind
    return None


def _direction_from_filter(filter_attr: str | None) -> str | None:
    if not filter_attr:
        return None
    text = filter_attr.lower()
    for token, kind in _PPT_FILTER_DIR.items():
        if f"({token})" in text or text.endswith(token):
            return kind
    return None


def _kind_from_entrance_ctn(ctn) -> str:
    """从单条入场 cTn 推断效果（不再扫整页 XML）。"""
    ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    preset_id = str(ctn.get("presetID") or "")
    subtype = ctn.get("presetSubtype")
    filter_attr = None
    for ae in ctn.iter(f"{ns_p}animEffect"):
        filter_attr = ae.get("filter")
        if filter_attr:
            break

    # 淡入 / 出现
    if preset_id in {"1", "10"}:  # appear / fade
        return "fade"
    if filter_attr and "fade" in filter_attr.lower() and "wipe" not in (filter_attr or "").lower():
        return "fade"

    # 缩放
    if preset_id in {"6", "53"} or any(
        True for _ in ctn.iter(f"{ns_p}animScale")
    ):
        if preset_id in {"6", "53"}:
            return "zoom"

    origin = _direction_from_filter(filter_attr) or _direction_from_subtype(subtype)
    filter_l = (filter_attr or "").lower()

    # 擦除（PPT wipe）保留擦除，不要映射成飞入
    if preset_id in {"7", "22"} or "wipe" in filter_l:
        return _WIPE_FROM.get(origin or "", "wipe-down")

    # 飞入 / 切入 / 覆盖
    if preset_id in {"2", "12", "14"} or any(
        k in filter_l for k in ("fly", "cover", "strip")
    ):
        return _FLY_FROM.get(origin or "", "fly-up")

    if origin:
        return _FLY_FROM.get(origin, "fly-up")
    if any(True for _ in ctn.iter(f"{ns_p}animMotion")):
        return _FLY_FROM.get(origin or "", "fly-up")
    return "fade"


def _duration_from_ctn(ctn) -> int:
    ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    best = None
    for node in ctn.iter(f"{ns_p}cTn"):
        ms = _ppt_ms(node.get("dur"))
        if ms is not None and ms >= 50:
            best = ms if best is None else max(best, ms)
    return best or 500


def _delay_from_ctn(ctn) -> int:
    ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    # 只看本节点直接 stCondLst，避免吃到子动画 delay
    st = ctn.find(f"{ns_p}stCondLst")
    if st is None:
        return 0
    for cond in st.findall(f"{ns_p}cond"):
        ms = _ppt_ms(cond.get("delay"))
        if ms is not None:
            return ms
    return 0


def _spid_from_ctn(ctn) -> int | None:
    ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
    for sp in ctn.iter(f"{ns_p}spTgt"):
        raw = sp.get("spid")
        if raw is None:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None


def _import_slide_anims(
    slide,
    id_by_shape: dict[int, str],
    group_els: dict[int, list[str]] | None = None,
) -> list:
    """按每条入场动画节点解析方向与开始方式。

    PPT 常把动画挂在「组合」上；导入时组合已拆成子元素，需把组 id 映射到子元素。
    """
    steps = []
    group_els = group_els or {}
    try:
        ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        timing = slide._element.find(f".//{ns_p}timing")
        if timing is None:
            return steps
        order = 0
        seen_ids: set[str] = set()
        for ctn in timing.iter(f"{ns_p}cTn"):
            if ctn.get("presetClass") != "entr":
                continue
            ctn_id = ctn.get("id") or ""
            # 同一入场节点勿重复
            if ctn_id and ctn_id in seen_ids:
                continue
            if ctn_id:
                seen_ids.add(ctn_id)

            spid = _spid_from_ctn(ctn)
            if spid is None:
                continue
            targets: list[str] = []
            el_id = id_by_shape.get(spid)
            if el_id:
                targets = [el_id]
            elif spid in group_els:
                # 组合动画 → 组内每个子元素同一步（同时出现）
                targets = list(group_els[spid])
            if not targets:
                continue

            node = str(ctn.get("nodeType") or "").lower()
            trigger = _PPT_NODE_TRIGGER.get(node, "on_click")
            kind = _kind_from_entrance_ctn(ctn)
            duration = _duration_from_ctn(ctn)
            delay = _delay_from_ctn(ctn)
            for i, tid in enumerate(targets):
                step = new_anim_step(tid, kind=kind, order=order, trigger=trigger)
                step.duration_ms = duration
                step.delay_ms = delay
                # 同一组合内：第一个保持原 trigger，其余 with_previous
                if i > 0:
                    step.trigger = "with_previous"
                steps.append(step)
            order += 1
    except Exception as exc:
        logger.warning("anim import failed: %s", exc)
        return []
    return steps


def _import_slide_transition(slide) -> SlideTransition:
    """读取 PPT 换页过渡，映射到无切换/平滑/淡出/切出/擦除。"""
    try:
        ns_p = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        tr = slide._element.find(f".//{ns_p}transition")
        if tr is None:
            return SlideTransition()
        spd = (tr.get("spd") or "med").lower()
        dur_map = {"slow": 800, "med": 500, "fast": 280}
        duration = dur_map.get(spd, 500)
        raw_dur = tr.get("dur")
        if raw_dur:
            ms = _ppt_ms(raw_dur)
            if ms is not None and ms >= 40:
                duration = min(3000, ms)

        children = [child.tag.split("}")[-1].lower() for child in list(tr)]
        kind = "none"
        for name in children:
            if name in ("fade", "fadethroughblack"):
                kind = "fade"
                break
            if name in ("push", "cover", "pull", "uncover"):
                kind = "push"
                break
            if name in ("wipe", "strips", "wheel"):
                kind = "wipe"
                break
            if name in ("cut",):
                kind = "none"
                break
            if name in ("morph", "flash", "dissolve"):
                kind = "smooth"
                break
        if kind == "none" and children:
            # 其它效果用平滑近似
            if any(n not in ("sndacst", "extlst") for n in children):
                kind = "smooth"
        if kind == "none":
            duration = 0
        return SlideTransition(kind=kind, duration_ms=duration)
    except Exception as exc:
        logger.warning("transition import failed: %s", exc)
        return SlideTransition()


def import_pptx(
    path: Path | str,
    store: SermonStore,
    title: str | None = None,
    *,
    reuse_id: str | None = None,
) -> SermonDocument:
    """把 PPTX 转成讲篇文档并写入 store（含图片资源）。

    reuse_id：Office 外编重载时复用工作目录，避免换 id。
    """
    _require_pptx()
    from pptx import Presentation

    from .store import safe_sermon_id

    path = Path(path)
    prs = Presentation(str(path))
    aspect = _aspect_from_size(int(prs.slide_width), int(prs.slide_height))
    canvas_w, canvas_h = ASPECT_SIZE[aspect]
    sx = canvas_w / float(prs.slide_width)
    sy = canvas_h / float(prs.slide_height)

    if not title:
        try:
            title = (prs.core_properties.title or "").strip() or None
        except Exception:
            title = None

    doc = new_document(title=title or path.stem or "导入讲篇", aspect=aspect)
    created_new = not reuse_id
    if reuse_id:
        doc.id = safe_sermon_id(str(reuse_id), path.stem)
    try:
        store.save(doc)
        doc.slides.clear()
        return _import_pptx_body(prs, doc, store, sx, sy)
    except Exception:
        if created_new:
            try:
                store.delete(doc.id)
            except Exception:
                pass
        raise


def _import_pptx_body(prs, doc, store, sx: float, sy: float):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    skipped = {"n": 0}
    notes: list[str] = []

    def _skip(reason: str) -> None:
        skipped["n"] += 1
        if len(notes) < 40:
            notes.append(reason)

    for slide_i, slide in enumerate(prs.slides, start=1):
        out = Slide(
            id=new_id("slide_"),
            background=_slide_bg(slide, store, doc.id),
            elements=[],
            animations=[],
        )
        id_by_shape: dict[int, str] = {}
        group_els: dict[int, list[str]] = {}
        z = 0
        for shape, abs_left, abs_top, abs_w, abs_h, gsx, gsy, group_stack in _iter_shapes(
            slide.shapes
        ):
            x = float(abs_left) * sx
            y = float(abs_top) * sy
            w = max(8.0, float(abs_w) * sx)
            h = max(8.0, float(abs_h) * sy)
            try:
                shape_id = int(shape.shape_id)
            except Exception:
                shape_id = z

            def _register(el_id: str) -> None:
                id_by_shape[shape_id] = el_id
                for gid in group_stack:
                    group_els.setdefault(int(gid), []).append(el_id)

            # 图表/表格/媒体等：内置舞台不支持，记入说明（枚举名因 pptx 版本而异）
            try:
                st = shape.shape_type
            except Exception:
                st = None
            skip_kinds = {
                getattr(MSO_SHAPE_TYPE, "CHART", None): "图表",
                getattr(MSO_SHAPE_TYPE, "TABLE", None): "表格（请用 Office 编辑）",
                getattr(MSO_SHAPE_TYPE, "MEDIA", None): "视频/音频",
                getattr(MSO_SHAPE_TYPE, "SMART_ART", None): "SmartArt",
                getattr(MSO_SHAPE_TYPE, "DIAGRAM", None): "SmartArt",
            }
            label = skip_kinds.get(st)
            if label:
                _skip(f"第{slide_i}页：跳过{label}")
                continue

            if _is_picture(shape):
                rel = _save_picture(shape, store, doc.id)
                if not rel:
                    _skip(f"第{slide_i}页：图片无法读取")
                    continue
                el = Element(
                    id=new_id("el_"),
                    type="image",
                    x=x,
                    y=y,
                    w=w,
                    h=h,
                    content=rel,
                    z=z,
                )
                out.elements.append(el)
                _register(el.id)
                z += 1
                continue

            fill_hex, fill_op = _shape_fill(shape)
            text = ""
            style = ElementStyle()
            if getattr(shape, "has_text_frame", False):
                text, style = _shape_text_content(shape, sx=sx)

            if text:
                # 组内边距 EMU 在 child 坐标系，需乘组合缩放
                inset_l, inset_t, inset_r, inset_b = _text_insets(
                    shape, sx * float(gsx), sy * float(gsy)
                )
                el = Element(
                    id=new_id("el_"),
                    type="text",
                    x=x + inset_l,
                    y=y + inset_t,
                    w=max(8.0, w - inset_l - inset_r),
                    h=max(8.0, h - inset_t - inset_b),
                    content=text,
                    z=z,
                    style=style,
                )
                out.elements.append(el)
                _register(el.id)
                z += 1
                continue

            # 无文字：导入纯色/半透明形状（如遮罩矩形）
            if fill_hex is None:
                name = getattr(shape, "name", "") or "形状"
                _skip(f"第{slide_i}页：跳过无填充{name}")
                continue
            el = Element(
                id=new_id("el_"),
                type="shape",
                x=x,
                y=y,
                w=w,
                h=h,
                z=z,
                shape=_shape_geom_kind(shape),
                style=ElementStyle(color=fill_hex, opacity=fill_op),
            )
            out.elements.append(el)
            _register(el.id)
            z += 1

        # 若形状遍历几乎没图，用 XML blip 兜底（避免重复：仅当当前无图时）
        if not any(e.type == "image" for e in out.elements):
            extras = _import_pictures_via_xml(slide, store, doc.id, sx, sy, z)
            out.elements.extend(extras)
            z += len(extras)
        else:
            # 有图也可能漏了组合内的：补充位置不重叠的
            existing = {
                (round(e.x), round(e.y), round(e.w), round(e.h))
                for e in out.elements
                if e.type == "image"
            }
            for el in _import_pictures_via_xml(slide, store, doc.id, sx, sy, z):
                key = (round(el.x), round(el.y), round(el.w), round(el.h))
                if key in existing:
                    continue
                el.z = z
                out.elements.append(el)
                existing.add(key)
                z += 1

        out.animations = _import_slide_anims(slide, id_by_shape, group_els)
        # 若有 timing 但没解析到步骤：给每个元素默认淡入（更接近「点一下出一个」）
        if not out.animations and out.elements:
            try:
                timing = slide._element.find(
                    ".//{http://schemas.openxmlformats.org/presentationml/2006/main}timing"
                )
                if timing is not None:
                    for i, el in enumerate(out.elements):
                        out.animations.append(new_anim_step(el.id, kind="fade", order=i))
                    notes.append(f"第{slide_i}页：复杂动画已降级为逐项淡入")
            except Exception:
                pass

        out.transition = _import_slide_transition(slide)
        doc.slides.append(out)
        logger.info(
            "imported slide %s: %d elements, %d images",
            len(doc.slides),
            len(out.elements),
            sum(1 for e in out.elements if e.type == "image"),
        )

    if not doc.slides:
        doc.slides.append(new_slide())
    store.save(doc)
    setattr(doc, "import_skip_count", skipped["n"])
    setattr(doc, "import_notes", notes)
    return doc


def export_pptx(doc: SermonDocument, dest: Path | str, store: SermonStore) -> Path:
    """把讲篇写成可被 WPS/Office 打开的 PPTX。"""
    _require_pptx()
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
    from pptx.util import Emu, Pt

    dest = Path(dest)
    canvas_w, canvas_h = doc.canvas_size()
    prs = Presentation()
    if doc.aspect == "4:3":
        prs.slide_width = Emu(int(10 * EMU_PER_INCH))
        prs.slide_height = Emu(int(7.5 * EMU_PER_INCH))
    else:
        prs.slide_width = Emu(int(13.333333 * EMU_PER_INCH))
        prs.slide_height = Emu(int(7.5 * EMU_PER_INCH))
    sx = float(prs.slide_width) / canvas_w
    sy = float(prs.slide_height) / canvas_h
    blank = prs.slide_layouts[6]

    align_map = {
        "left": PP_ALIGN.LEFT,
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
    }

    for slide in doc.slides:
        s = prs.slides.add_slide(blank)
        try:
            s.follow_master_background = False
            fill = s.background.fill
            fill.solid()
            bg_val = slide.background.value if slide.background.type == "color" else "#000000"
            r, g, b = _parse_hex(bg_val)
            fill.fore_color.rgb = RGBColor(r, g, b)
        except Exception:
            pass

        if slide.background.type == "image" and slide.background.value:
            img = store.resolve_asset(doc.id, slide.background.value)
            if img.is_file():
                s.shapes.add_picture(str(img), Emu(0), Emu(0), width=prs.slide_width, height=prs.slide_height)

        for el in sorted(slide.elements, key=lambda e: e.z):
            left = Emu(int(el.x * sx))
            top = Emu(int(el.y * sy))
            width = Emu(int(max(8, el.w) * sx))
            height = Emu(int(max(8, el.h) * sy))
            if el.type == "image":
                img = store.resolve_asset(doc.id, el.content)
                if img.is_file():
                    s.shapes.add_picture(str(img), left, top, width=width, height=height)
                continue
            if el.type == "shape":
                from pptx.enum.shapes import MSO_SHAPE

                kind = MSO_SHAPE.OVAL if el.shape == "ellipse" else MSO_SHAPE.RECTANGLE
                shp = s.shapes.add_shape(kind, left, top, width, height)
                try:
                    shp.fill.solid()
                    r, g, b = _parse_hex(el.style.color or "#000000")
                    shp.fill.fore_color.rgb = RGBColor(r, g, b)
                    # python-pptx 透明度：0=不透明，1=全透明
                    shp.fill.fore_color.brightness = 0
                    try:
                        from pptx.oxml.ns import qn

                        srgb = shp.fill._fill.foreColor._color._xClr
                        # 写 alpha（OOXML 百分之一百分比）
                        alpha_val = int(round(max(0.0, min(1.0, float(el.style.opacity))) * 100000))
                        # 清旧 alpha
                        for child in list(srgb):
                            if child.tag.endswith("}alpha"):
                                srgb.remove(child)
                        from lxml import etree

                        ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
                        etree.SubElement(srgb, f"{ns_a}alpha").set("val", str(alpha_val))
                    except Exception:
                        pass
                    shp.line.fill.background()
                except Exception as exc:
                    logger.warning("export shape fill failed: %s", exc)
                continue
            if el.type != "text":
                continue
            box = s.shapes.add_textbox(left, top, width, height)
            tf = box.text_frame
            tf.word_wrap = bool(getattr(el.style, "wrap", True))
            lines = (el.content or "").split("\n") or [""]
            for i, line in enumerate(lines):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                p.alignment = align_map.get(el.style.align, PP_ALIGN.LEFT)
                run = p.add_run()
                run.text = line
                # font_size 存的是画布像素 → 磅
                pt = max(12.0, float(el.style.font_size) * float(sx) / EMU_PER_PT)
                run.font.size = Pt(pt)
                run.font.bold = bool(el.style.bold)
                run.font.italic = bool(el.style.italic)
                run.font.name = el.style.font_family or "微软雅黑"
                r, g, b = _parse_hex(el.style.color)
                try:
                    run.font.color.rgb = RGBColor(r, g, b)
                except Exception:
                    pass
            try:
                tf._txBody.bodyPr.set("anchor", "ctr")
            except Exception:
                _ = MSO_ANCHOR

    try:
        prs.core_properties.title = doc.title or dest.stem
    except Exception:
        pass
    dest.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(dest))
    return dest
