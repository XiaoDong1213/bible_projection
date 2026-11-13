# 经文显示核心控件
# 行布局完全自绘：断行/禁则/两端对齐由本模块自己计算，不经过 Qt 文本引擎。
# 「节号+正文首字」是同一个不可分原子（grp），任何字体/宽度/缩放下
# 都不可能出现「节号悬在行尾、正文另起一行」。
import math
import os
import re

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import (
    Qt, QTimer, QElapsedTimer, pyqtSignal, QPointF,
)
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QFontMetrics, QFontMetricsF, QPainter, QShortcut, QKeySequence,
)


# 收尾标点：不能出现在行首（中文禁则）
_PUNCT_CLOSING = "，。；：？！、）”』》〉〕…—％·’"
# 开引号/开括号：不能出现在行尾
_PUNCT_OPENING = "（“『「《〈〔‘"
# 节末内联题注文本（细拉/Selah，与转换器写库的字面一致）；其余题注显示在节上方
_SELAH_TEXTS = {"（细拉）", "（細拉）", "Selah"}
# 节中说话人标签独立行（转换器以 \n 分隔写入正文，如「〔新娘〕〕」），按题注样式渲染
_STANDALONE_CAPTION_RE = re.compile(r"^〔[^〕]*〕$")

# 渲染用半角标点映射：全角标点字格一半以上是空白，多字连续时
# 叠加出大空隙；半角字形无此问题（视觉等同专业排版的标点压缩）
_PUNCT_HALF = {
    u'\uff0c': ',',
    u'\u3002': '.',
    u'\uff1b': ';',
    u'\uff1a': ':',
    u'\uff1f': '?',
    u'\uff01': '!',
    u'\u3001': ',',
    u'\u201c': chr(34),
    u'\u201d': chr(34),
    u'\u2018': chr(39),
    u'\u2019': chr(39),
    u'\uff08': '(',
    u'\uff09': ')',
}
# 半角形式的行首禁排/行尾禁排字符
_HALF_CLOSING = ',.;:?!' + chr(8217) + chr(8221) + ')'
_HALF_OPENING = '(' + chr(8220) + chr(8216)


def _halfwidth(text):
    """全角标点 → 半角字形（仅渲染层转换，不改源文本）。"""
    return "".join(_PUNCT_HALF.get(ch, ch) for ch in str(text))


# 可见空白统一折叠为半角空格。旧 QTextDocument/HTML 渲染本来就会折叠它们
# （U+3000 神版记号、连续空格、其他 Unicode 空白在旧版里都显示为窄空格），
# 自绘布局必须显式对齐该行为，否则 U+3000 会按字面渲染成整字宽。
_WS_RUN_RE = re.compile(r"\s+")


def _norm_ws(text):
    return _WS_RUN_RE.sub(" ", str(text))


def _is_closing_punct(ch):
    """收尾标点：不能出现在行首。"""
    return ch in _PUNCT_CLOSING or ch in _HALF_CLOSING


def _is_opening_punct(ch):
    """开引号/开括号：不能出现在行尾。"""
    return ch in _PUNCT_OPENING or ch in _HALF_OPENING


def _tokens(text):
    """词元切分：拉丁字母/数字连续串为一个词元（含 don't / 1,000 / well-known），
    其余字符逐个成词元，空格单独成词元。返回 [(kind, text)]，kind: 'w'|'sp'。"""
    text = str(text)
    toks = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == " ":
            toks.append(("sp", ch)); i += 1
            continue
        if ch.isascii() and ch.isalnum():
            j = i
            word = ""
            while j < n:
                c = text[j]
                if c.isascii() and c.isalnum():
                    word += c; j += 1
                elif c in "-'" or c == chr(8217):
                    # 词内连字符/撇号：仅当两侧都是字母数字时并入（don't / well-known / 1,000）
                    if word and j + 1 < n and text[j + 1].isascii() and text[j + 1].isalnum() and word[-1].isascii() and word[-1].isalnum():
                        word += c; j += 1
                    else:
                        break
                elif c in ",." and word and j + 1 < n and text[j + 1].isdigit() and word[-1].isdigit():
                    word += c; j += 1
                else:
                    break
            toks.append(("w", word)); i = j
            continue
        toks.append(("w", ch)); i += 1
    return toks


def _clusters(text):
    """把文本切成「不可分簇」：断行只允许发生在簇与簇之间。

    - 拉丁词整体一簇（词内不断行）
    - 收尾标点并向前簇（禁则：行首不出现标点）
    - 开引号/开括号向后簇合并（禁则：行尾不出现标点）
    返回 [(kind, text)]，kind: 'c'=簇 | 'sp'=空格（断行点/拉伸点）。
    """
    out = []
    open_pending = False
    for kind, s in _tokens(text):
        if kind == "sp":
            out.append(["sp", s]); open_pending = False
            continue
        if len(s) == 1 and _is_opening_punct(s):
            if open_pending and out:
                out[-1][1] += s
            else:
                out.append(["c", s])
            open_pending = True
            continue
        if open_pending and out:
            out[-1][1] += s; open_pending = False
            continue
        open_pending = False
        if len(s) == 1 and _is_closing_punct(s) and out:
            if out[-1][0] == "c":
                out[-1][1] += s
                continue
            if out[-1][0] == "sp":
                # 空格后的收尾标点：连同空格并入前簇，标点不得落到行首
                k = len(out)
                while k > 0 and out[k - 1][0] == "sp":
                    k -= 1
                if k > 0 and out[k - 1][0] == "c":
                    out[k - 1][1] += " " * (len(out) - k) + s
                    del out[k:]
                    continue
        out.append(["c", s])
    return out


# 字形宽度缓存：{(family, px, bold, italic) -> {text: 逻辑宽}}。
# CJK 无 kerning，可按字符缓存累加；拉丁词整词缓存（保留词内 shaping）。
# 命中后量宽近零成本，跨章节/重排复用。
_ADV_CACHE = {}


def _coerce_color(value, fallback="#87CEEB"):
    if isinstance(value, QColor):
        return value if value.isValid() else QColor(fallback)
    color = QColor(str(value) if value is not None else fallback)
    return color if color.isValid() else QColor(fallback)


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"true", "1", "yes", "on"}


class ScriptureBody(QWidget):
    """经文正文区：自绘行布局 + 浮点 scroll_y 平移绘制，观感接近网页提词器。

    断行/禁则/两端对齐全部由 _relayout 自己实现（不经过 Qt 断行器）：
    - 「节号+正文首字」在同一个 grp 原子里，物理上不可能分行悬空
    - 拉丁词内不断行；行首不出现收尾标点；行尾不出现开引号
    - 两端对齐把剩余空间均分到「纯汉字之间的边界与空格」上，标点簇保持紧凑
    """
    scroll_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        self._content = []        # 原子列表（ScriptureDisplay._build_content 生成）
        self._styles = {}         # 样式名 -> (QFont, QColor)
        self._justify = True      # 两端对齐（中文译本开，英文译本关）
        self._line_factor = 1.6   # line_spacing% / 100
        self._pad_top = 0.0
        self._doc_pad_bottom = 0.0
        self._text_width = 1.0
        self._lines = []          # 布局结果：[{y, advance, baseline, cells}]
        self._content_h = 0.0
        self._scroll_y = 0.0
        self._pad_left = 0; self._pad_right = 0; self._pad_bottom = 0
        self._wheel_step = 48.0
        self._follow_only = False
        self._fms = {}
        self._adv_cache = {}   # 样式名 -> 该字体配置的全局宽度缓存（set_content 时刷新）

    # ---------- 内容与样式 ----------

    def set_content(self, atoms, styles, justify, pad_top, pad_bottom, line_spacing_pct):
        """接收原子序列与样式表，重建行布局。原子结构见 _build_content。"""
        self._content = list(atoms or [])
        self._styles = dict(styles or {})
        self._justify = bool(justify)
        self._line_factor = max(0.5, float(line_spacing_pct) / 100.0)
        self._pad_top = max(0.0, float(pad_top))
        self._doc_pad_bottom = max(0.0, float(pad_bottom))
        self._fms = {}
        self._adv_cache = {}
        self._relayout(); self._clamp_scroll(); self.update()

    def _style(self, name):
        st = self._styles.get(name)
        if st is None:
            font = QFont()
            font.setPixelSize(16)
            return (font, QColor("#FFFFFF"))
        return st

    def _fm(self, name):
        fm = self._fms.get(name)
        if fm is None:
            fm = QFontMetricsF(self._style(name)[0])
            self._fms[name] = fm
        return fm

    def _advance(self, style, text):
        """文本逻辑宽度（带缓存）。纯 CJK/标点簇按字符累加（无 kerning），
        其余（拉丁词/混合）整串量宽并缓存。"""
        cache = self._adv_cache.get(style)
        if cache is None:
            font, _color = self._style(style)
            key = (font.family(), font.pixelSize(), font.bold(), font.italic())
            cache = _ADV_CACHE.setdefault(key, {})
            self._adv_cache[style] = cache
        w = cache.get(text)
        if w is not None:
            return w
        fm = self._fm(style)
        if len(text) > 1 and not any(ch.isascii() and ch.isalnum() for ch in text):
            w = 0.0
            for ch in text:
                cw = cache.get(ch)
                if cw is None:
                    cw = fm.horizontalAdvance(ch)
                    cache[ch] = cw
                w += cw
        else:
            w = fm.horizontalAdvance(text)
        cache[text] = w
        return w

    def _atom_width(self, atom):
        w = atom.get("w")
        if w is not None:
            return w
        kind = atom["kind"]
        if kind == "w":
            w = self._advance(atom["style"], atom["text"])
        elif kind == "grp":
            w = 0.0
            for piece in atom["pieces"]:
                if piece["k"] == "text":
                    piece["w"] = self._advance(piece["style"], piece["text"])
                    w += piece["w"]
                else:
                    w += float(piece["w"])
        elif kind == "sp":
            w = self._advance("body", " ")
        elif kind == "gap":
            w = float(atom["gap"])
        else:
            w = 0.0
        atom["w"] = w
        return w

    # ---------- 断行与布局 ----------

    def _relayout(self):
        for atom in self._content:
            self._atom_width(atom)
        width = max(1.0, float(self._text_width))
        raw = []   # [(行内原子列表, 是否允许两端对齐)]
        chunk = []
        for atom in self._content:
            kind = atom["kind"]
            if kind == "vspace":
                # 纯垂直空隙：自带断行，不占水平宽度，不参与绘制
                if chunk:
                    self._wrap_chunk(chunk, width, raw)
                    chunk = []
                raw.append(([atom], False))
            elif kind == "br":
                if chunk:
                    self._wrap_chunk(chunk, width, raw)
                    chunk = []
                elif raw:
                    raw.append(([], False))   # 连续换行的空行
            else:
                chunk.append(atom)
        if chunk:
            self._wrap_chunk(chunk, width, raw)

        # 垂直排布：行高 = 行内最大字体高 × line_spacing%，基线居中于行距增量
        lines = []
        y = self._pad_top
        factor = self._line_factor
        body_fm = self._fm("body")
        for atoms, just in raw:
            if len(atoms) == 1 and atoms[0]["kind"] == "vspace":
                y += atoms[0]["h"]
                continue
            cells, nat_h, max_asc = self._layout_line(atoms, width, just and self._justify)
            if nat_h <= 0.0:
                nat_h = body_fm.height(); max_asc = body_fm.ascent()
            # 与旧 QTextDocument 渲染一致：行高先取整再乘 line-height%，
            # 额外行距放在行下方（文字贴行盒顶部），首行基线 = ascent
            advance = math.ceil(nat_h) * factor
            baseline = y + max_asc
            lines.append({"y": y, "advance": advance, "baseline": baseline, "cells": cells})
            y += advance
        self._lines = lines
        self._content_h = y + self._doc_pad_bottom

    def _wrap_chunk(self, atoms, width, raw):
        """一个强制换行块内的贪心断行。atoms 为非 br 原子。

        在溢出点直接断行：拉丁词本身是不可分原子，溢出时整体下移；
        行尾空格由 _push_line 剥离。不回退到行中空格——中文里最近的
        空格可能在十几个原子之外（如「起初　神创造天地」的 U+3000），
        回退会丢弃大半行内容，再被两端对齐拉出巨洞。
        """
        line = []
        line_w = 0.0
        for atom in atoms:
            kind = atom["kind"]
            w = atom["w"]
            if kind == "sp":
                if not line:
                    continue   # 行首空格丢弃
                line.append(atom); line_w += w
                continue
            if line and line_w + w > width:
                self._push_line(raw, line, True)
                line = []; line_w = 0.0
            line.append(atom); line_w += w
        self._push_line(raw, line, False)   # 块末行（自然段末行）不拉伸

    @staticmethod
    def _push_line(raw, atoms, justify):
        while atoms and atoms[-1]["kind"] == "sp":
            atoms.pop()   # 行尾空格不占宽
        if atoms:
            raw.append((atoms, justify))

    def _layout_line(self, atoms, width, justify):
        """把一行原子平铺成绘制单元并做两端对齐。返回 (cells, nat_h, max_asc)。

        cell 结构：{"k": "t"/"sp", "x", "text", "style", "raise", "w"}
        拉伸点 = 相邻两个纯汉字单元之间的边界 + 空格；标点簇旁不拉伸（保持密排）。
        """
        cells = []
        x = 0.0

        def push_text(text, style, raise_, w):
            nonlocal x
            cells.append({"k": "t", "x": x, "text": text, "style": style,
                          "raise": raise_, "w": w})
            x += w

        for a in atoms:
            if a["kind"] == "sp":
                cells.append({"k": "sp", "x": x, "text": "", "style": "body",
                              "raise": 0.0, "w": a["w"]})
                x += a["w"]
                continue
            if a["kind"] == "grp":
                for piece in a["pieces"]:
                    if piece["k"] == "gap":
                        x += float(piece["w"])
                        prev_cjk = False
                    else:
                        push_text(piece["text"], piece["style"], piece["raise"],
                                  piece["w"])
                continue
            push_text(a["text"], a["style"], 0.0, a["w"])

        natural = x
        # 两端对齐：剩余空间均匀分布到所有字间边界。按「平移原始坐标」实现——
        # 原始 x 已包含 grp 原子内部的节号间隙，直接重排会把它抹掉。
        # 不用「拉伸点均分」：行内汉字边界太少时（如「号,定节令,日子,年岁,」
        # 只有 2 个）整行富余会拉成巨洞；均匀化后每处只多零点几个字宽。
        # 节号与它正文首字之间不参与，节号不漂离正文。
        if justify and cells and natural < width:
            extra = width - natural
            if extra > 0 and len(cells) > 1:
                weights = [0.0]
                prev_style = cells[0]["style"]
                for c in cells[1:]:
                    weights.append(0.0 if prev_style == "num" else 1.0)
                    prev_style = c["style"]
                total_w = sum(weights)
                if total_w > 0:
                    acc = 0.0
                    for idx, c in enumerate(cells):
                        if idx:
                            acc += extra * weights[idx] / total_w
                            c["x"] += acc

        # 合并相邻同样式且紧贴的单元（减少 drawText 调用；拉丁词本身已是一格）
        merged = []
        for c in cells:
            if c["k"] != "t":
                continue
            if merged:
                last = merged[-1]
                if (last["style"] == c["style"] and last["raise"] == c["raise"]
                        and abs(last["x"] + last["w"] - c["x"]) < 0.01):
                    last["text"] += c["text"]
                    last["w"] += c["w"]
                    continue
            merged.append(dict(c))
        nat_h = 0.0; max_asc = 0.0
        for c in merged:
            fm = self._fm(c["style"])
            if fm.height() > nat_h: nat_h = fm.height()
            if fm.ascent() > max_asc: max_asc = fm.ascent()
        return merged, nat_h, max_asc

    # ---------- 视口/滚动 ----------

    def set_pads(self, left, right, bottom):
        self._pad_left = max(0, int(left)); self._pad_right = max(0, int(right)); self._pad_bottom = max(0, int(bottom))
        self._fit_text_width(); self._clamp_scroll(); self.update()

    def set_text_width(self, width):
        w = max(1.0, float(width))
        if abs(w - self._text_width) < 0.5:
            return
        self._text_width = w
        self._relayout(); self._clamp_scroll(); self.update()

    def _fit_text_width(self):
        self.set_text_width(max(1, self.width() - self._pad_left - self._pad_right))

    def content_height(self):
        return max(1.0, self._content_h)

    def view_height(self):
        return max(1.0, float(max(0, self.height() - self._pad_bottom)))

    def max_scroll(self):
        return max(0.0, self.content_height() - self.view_height())

    def scroll_y(self):
        return self._scroll_y

    def set_scroll_y(self, value, emit=True):
        try:
            y = float(value)
        except (TypeError, ValueError):
            return
        y = max(0.0, min(y, self.max_scroll()))
        if abs(y - self._scroll_y) < 1e-4:
            self._scroll_y = y; return
        self._scroll_y = y; self.update()
        if emit:
            self.scroll_changed.emit(self._scroll_y)

    def _clamp_scroll(self):
        self.set_scroll_y(self._scroll_y, emit=False)

    def scroll_fraction(self):
        maximum = self.max_scroll()
        return 0.0 if maximum <= 0 else self._scroll_y / maximum

    def set_scroll_fraction(self, fraction):
        try:
            value = max(0.0, min(1.0, float(fraction)))
        except (TypeError, ValueError):
            return
        self.set_scroll_y(value * self.max_scroll())

    def scroll_by(self, delta):
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            return
        self.set_scroll_y(self._scroll_y + delta)

    def set_follow_only(self, on: bool):
        self._follow_only = bool(on)

    def wheelEvent(self, event):
        if self._follow_only:
            event.accept()
            return
        angle = event.angleDelta().y(); pixel = event.pixelDelta().y()
        if pixel:
            delta = -float(pixel)
        elif angle:
            delta = -(float(angle) / 120.0) * self._wheel_step
        else:
            event.ignore(); return
        old = self._scroll_y; self.scroll_by(delta)
        if abs(self._scroll_y - old) > 1e-4:
            event.accept()
        else:
            event.ignore()

    def resizeEvent(self, event):
        super().resizeEvent(event); self._fit_text_width(); self._clamp_scroll()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        clip = self.rect()
        if self._pad_bottom:
            clip.setHeight(max(0, clip.height() - self._pad_bottom))
        painter.setClipRect(clip)
        painter.translate(float(self._pad_left), -self._scroll_y)
        # 只画可见区附近的行（滚动耗时与文档总行数基本无关）
        top = self._scroll_y - 40.0
        bottom = self._scroll_y + clip.height() + 40.0
        for line in self._lines:
            if line["y"] + line["advance"] < top:
                continue
            if line["y"] > bottom:
                break
            base = line["baseline"]
            for cell in line["cells"]:
                font, color = self._style(cell["style"])
                painter.setFont(font)
                painter.setPen(color)
                painter.drawText(QPointF(cell["x"], base - cell["raise"]), cell["text"])


class ScriptureDisplay(QWidget):
    scroll_changed=pyqtSignal(int); scroll_finished=pyqtSignal(); content_changed=pyqtSignal(); _TICK_MS_LEGACY=30.0
    def __init__(self,parent=None):
        super().__init__(parent); self.font_family="微软雅黑"; self.font_size=24; self.font_color=QColor("#FFFFFF"); self.bg_color=QColor("#000000"); self.bg_image=None; self._bg_pixmap=None; self._bg_pixmap_path=None; self._bg_scaled=None; self._bg_scaled_size=None; self.line_spacing=160; self.margin_left=60; self.margin_right=60; self.title_font_family="微软雅黑"; self.title_color=QColor("#87CEEB"); self.title_size=36; self.title_min_size=12; self.title_gap=30; self.scripture_title_gap=30; self.show_scripture_titles=False; self.show_captions=True; self.scripture_title_font_family="微软雅黑"; self.scripture_title_size=30; self.scripture_title_color=QColor("#87CEEB"); self.caption_font_family="微软雅黑"; self.caption_size=24; self.caption_color=QColor("#87CEEB"); self.caption_italic=True; self.verse_num_color=QColor("#FFD700"); self.verse_num_size=24; self.verse_num_font_family="微软雅黑"; self.footer_text=""; self.footer_height=45; self.footer_size=14; self.footer_color=QColor("#AAAAAA"); self.footer_font_family="微软雅黑"; self.scroll_speed=0; self._scroll_anim=None; self._scroll_clock=QElapsedTimer(); self._refresh_hz=60.0; self._screen_hooked=False; self._title_text=""; self.verses=[]; self.verse_segmentation=False; self._show_chapter_nums=False; self._reference_size=None; self._design_height=1080; self.scroll_timer=QTimer(self); self.scroll_timer.setTimerType(Qt.TimerType.PreciseTimer); self.scroll_timer.timeout.connect(self._auto_scroll); self._apply_refresh_interval(); self._fill_scale=None; self._init_ui(); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self._home_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Home),self); self._home_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); self._home_shortcut.activated.connect(self._scroll_to_top); self._end_shortcut=QShortcut(QKeySequence(Qt.Key.Key_End),self); self._end_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); self._end_shortcut.activated.connect(self._scroll_to_bottom); self.punct_halfwidth=False; self._text_justify=True
    def _init_ui(self):
        # 自己在 paintEvent 里铺底色/背景图，不要让样式表/调色板先盖一层黑
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0); self.title_bar=QLabel(""); self.title_bar.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop); self.title_bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True); layout.addWidget(self.title_bar); self.text_display=ScriptureBody(); self.text_display.scroll_changed.connect(self._on_body_scroll_changed); layout.addWidget(self.text_display,1); self.footer_label=QLabel(self); self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True); self.footer_label.show(); self._update_footer_style(); self._update_viewport_margins()
    def _scroll_to_top(self):
        if self.scroll_speed>0 or self.scroll_timer.isActive(): self.set_scroll_speed(0); self.scroll_finished.emit()
        self.set_scroll_position(0)
    def _scroll_to_bottom(self):
        if self.scroll_speed>0 or self.scroll_timer.isActive(): self.set_scroll_speed(0); self.scroll_finished.emit()
        self.set_scroll_position(self.max_scroll())
    def layout_scale(self):
        if self._reference_size:
            return max(0.55,min(3.0,float(self._reference_size[1])/float(self._design_height)))
        if self._fill_scale is not None:
            return self._fill_scale
        return max(0.55,min(3.0,float(max(1,self.height()))/float(self._design_height)))
    def recalibrate_fill_scale(self):
        """显示面突变（进入/退出全屏）后重估冻结的 fill 缩放并重排。"""
        if self._reference_size is not None:
            return
        self._fill_scale=None
        self._refresh_layout_metrics()
    def _px(self,value): return max(1,int(round(float(value)*self.layout_scale())))
    def set_stage_size(self,width,height): self.set_reference_size(width,height)
    def clear_stage_size(self): self.clear_reference_size()
    def set_reference_size(self,width,height):
        try: self._reference_size=(max(1,int(width)),max(1,int(height)))
        except (TypeError,ValueError): self._reference_size=None
        self._refresh_layout_metrics()
    def clear_reference_size(self): self._reference_size=None; self._refresh_layout_metrics()
    def _refresh_layout_metrics(self):
        self._update_viewport_margins()
        if self._title_text: self._set_adaptive_title(self._title_text)
        if self.verses:
            old=self.scroll_fraction(); self._render_scripture(); self.set_scroll_fraction(old)
        self._update_footer_style(); self.update()
    def _update_viewport_margins(self): self.text_display.set_pads(self._px(self.margin_left),self._px(self.margin_right),self._px(self.footer_height)); self._fit_document_width()
    def _fit_document_width(self):
        if self._reference_size: self.text_display.set_text_width(max(1,self._reference_size[0]-self._px(self.margin_left)-self._px(self.margin_right)))
        else: self.text_display._fit_text_width(); self.text_display.update()
    def set_scripture(self,book_name,chapter,start_verse,end_verse,verses,title=None,show_chapter_nums=False,reset_scroll=True):
        self.verses=list(verses or []); self._show_chapter_nums=bool(show_chapter_nums)
        if title: self._set_adaptive_title(title)
        else:
            book_ascii = all(ord(c) < 128 for c in str(book_name))
            if book_ascii:
                # 英文等拉丁译本：标准英文引用格式（Genesis 1 / Genesis 1:1-31）
                if start_verse is None: title_text=f"{book_name} {chapter}"
                elif start_verse==end_verse: title_text=f"{book_name} {chapter}:{start_verse}"
                else: title_text=f"{book_name} {chapter}:{start_verse}-{end_verse}"
            else:
                unit="篇" if book_name=="诗篇" else "章"
                if start_verse is None: title_text=f"{book_name}{chapter}{unit}"
                elif end_verse is None: title_text=f"{book_name}{chapter}{unit}{start_verse}-末节"
                elif start_verse==end_verse: title_text=f"{book_name}{chapter}{unit}{start_verse}节"
                else: title_text=f"{book_name}{chapter}{unit}{start_verse}-{end_verse}节"
            self._set_adaptive_title(title_text)
        self._render_scripture()
        if reset_scroll: self.set_scroll_position(0)
        else: self.text_display._clamp_scroll()
        self.update()
    def _logical_title_from_verses(self, selection, verses):
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
        book_ascii = all(ord(c) < 128 for c in str(selection.book))
        if book_ascii:
            if logical_start == logical_end:
                return f"{selection.book} {span.chapter}:{logical_start}"
            return f"{selection.book} {span.chapter}:{logical_start}-{logical_end}"
        unit = "篇" if selection.book == "诗篇" else "章"
        if logical_start == logical_end:
            body = str(logical_start)
        else:
            body = f"{logical_start}-{logical_end}"
        return f"{selection.book}{span.chapter}{unit}{body}节"
    def set_from_selection(self,selection,verses,reset_scroll=True):
        title=self._logical_title_from_verses(selection,verses)
        self.set_scripture(selection.book,selection.primary_chapter,selection.primary_start,selection.primary_end,verses,title=title,show_chapter_nums=selection.is_multi_chapter,reset_scroll=reset_scroll)
    def clear_scripture(self):
        self.verses=[]; self._show_chapter_nums=False; self._set_adaptive_title(""); self.text_display.set_content([], self._body_styles(), True, 0, 0, self.line_spacing); self.set_scroll_position(0); self.update()
    def _set_adaptive_title(self,text):
        self._title_text=str(text or ""); shown=self._punct(self._title_text); size=max(self._px(self.title_min_size),self._px(self.title_size)); font=QFont(self.title_font_family,size); font.setBold(True); pad=self._px(24); avail=max(100,self.title_bar.width()-pad*2); min_size=self._px(self.title_min_size)
        while QFontMetrics(font).horizontalAdvance(shown)>avail and size>min_size:
            size-=1; font=QFont(self.title_font_family,size); font.setBold(True)
        # 标题栏高度 = 字体上缘 + 收尾 2px + 「标题与正文间距」设置；
        # 旧公式 height+6 且垂直居中，大字号时 descent 空隙+居中余白
        # 让标题与正文之间隔出一大截；配 AlignTop 后字贴栏顶、底部只留可调间距
        h=max(self._px(42),QFontMetrics(font).ascent()+self._px(2)+self._px(self.title_gap)); self.title_bar.setMinimumHeight(h); self.title_bar.setMaximumHeight(h); self.title_bar.setFont(font); self.title_bar.setStyleSheet(f'color:{self.title_color.name()};font-family:"{self.title_font_family}";'+f"font-size:{size}px;font-weight:bold;background:transparent;padding:0 {pad}px;"); self.title_bar.setText(shown)
    def set_verse_segmentation(self,enabled):
        enabled=bool(enabled)
        if self.verse_segmentation==enabled:return
        old=self.scroll_fraction(); self.verse_segmentation=enabled
        if self.verses:self._render_scripture(); self.set_scroll_fraction(old)
    def _verse_row(self,row):
        if row is None:return None,None,"",[],[]
        if len(row)>=5:return row[0],row[1],row[2],list(row[3] or []),list(row[4] or [])
        if len(row)>=4:return row[0],row[1],row[2],list(row[3] or []),[]
        if len(row)>=3:return row[0],row[1],row[2],[],[]
        return None,row[0],row[1],[],[]
    def _punct(self,html):
        """标点紧凑开关统一出口：开 = 全角标点转半角字形；关 = 原样恢复。
        正文/题注/小标题/标题栏/底注全部走这里，保证开关全量生效、全量还原。"""
        if getattr(self,"punct_halfwidth",True):
            return _halfwidth(html)
        return html
    def _verse_segments(self,text):
        """按 \\n 拆段；〔…〕独立行是节中说话人标签，按题注渲染（受题注开关控制）。"""
        segs=[]
        for raw in str(text or "").split("\n"):
            s=raw.strip()
            if not s: continue
            if _STANDALONE_CAPTION_RE.match(s):
                if self.show_captions:
                    segs.append(("caption",_norm_ws(s).strip()))
            else:
                segs.append(("body",_norm_ws(s).strip()))
        return segs
    def _body_styles(self):
        """正文区四种样式的字体/颜色（QFont 以像素字号构建，与绘制一致）。"""
        vn=self._px(self.verse_num_size)
        def mk(family,px,bold=False,italic=False):
            font=QFont(str(family)); font.setPixelSize(max(1,int(round(px)))); font.setBold(bold); font.setItalic(italic); return font
        return {
            "body": (mk(self.font_family,self._px(self.font_size)), self.font_color),
            "caption": (mk(self.caption_font_family,self._px(self.caption_size),italic=self.caption_italic), self.caption_color),
            "title": (mk(self.scripture_title_font_family,self._px(self.scripture_title_size),bold=True), self.scripture_title_color),
            "num": (mk(self.verse_num_font_family,vn*0.66,bold=True), self.verse_num_color),
        }
    def _verse_atoms(self,chapter,n,t,leading_gap,inline_captions):
        """一节的原子序列。核心保证：节号与正文（或首段题注）的第一簇
        在同一个 grp 原子里——断行以原子为单位，节号永远不可能单独悬在行尾。"""
        vn=self._px(self.verse_num_size)
        label=f"{chapter}:{n}" if getattr(self,"_show_chapter_nums",False) and chapter is not None else str(n)
        gl=max(2,self._px(self.verse_num_gap_left)) if self.verse_num_gap_left>0 else max(6,int(vn*1.0))
        gr=max(2,self._px(self.verse_num_gap_right)) if self.verse_num_gap_right>0 else max(6,int(vn*1.0))
        # 节号顶对齐正文顶部（真上标，永远在所在行的左上角）：
        # 抬升 = 正文上缘 - 节号上缘；旧实现按节号字号的 30% 抬升，
        # 正文字号大时节号贴着基线，落在行中就跑到「右下角」了
        try:
            _st = self._body_styles()
            _fm_b = QFontMetricsF(_st["body"][0])
            _fm_n = QFontMetricsF(_st["num"][0])
            raise_px = max(0, int(round(_fm_b.ascent() - _fm_n.ascent())))
        except Exception:
            raise_px = int(round(vn * 0.30))
        def cluster_atoms(text,style):
            out=[]
            for ck,cs in _clusters(self._punct(str(text))):
                if ck=="sp":
                    out.append({"kind":"sp"})
                else:
                    out.append({"kind":"w","text":cs,"style":style})
            return out
        pieces=[]
        if leading_gap:
            pieces.append({"k":"gap","w":float(gl)})
        pieces.append({"k":"text","text":label,"style":"num","raise":raise_px})
        segs=self._verse_segments(t)
        seg_atom_lists=[("body" if kind=="body" else "caption", cluster_atoms(s,"body" if kind=="body" else "caption")) for kind,s in segs]
        # 节末内联题注（细拉/Selah）
        inline_gap=max(6,self._px(self.caption_size)//3)
        inline_atoms=[]
        for i,cap in enumerate(inline_captions or []):
            if i: inline_atoms.append({"kind":"gap","gap":inline_gap})
            inline_atoms.extend(cluster_atoms(cap,"caption"))
        # 首段首簇并入节号原子（节号+间距+首字 物理一体）
        if seg_atom_lists and seg_atom_lists[0][1]:
            pieces.append({"k":"gap","w":float(gr)})
            first=seg_atom_lists[0][1].pop(0)
            pieces.append({"k":"text","text":first["text"],"style":first["style"],"raise":0.0})
        elif inline_atoms and inline_atoms[0]["kind"]=="w":
            # 无正文段的节：首个内联题注簇并入，节号同样不悬空
            pieces.append({"k":"gap","w":float(gr)})
            first=inline_atoms.pop(0)
            pieces.append({"k":"text","text":first["text"],"style":first["style"],"raise":0.0})
        while pieces and pieces[-1]["k"]=="gap":
            pieces.pop()
        atoms=[{"kind":"grp","pieces":pieces}]
        for si,(style,seg) in enumerate(seg_atom_lists):
            if si: atoms.append({"kind":"br"})
            atoms.extend(seg)
        atoms.extend(inline_atoms)
        return atoms
    def _build_content(self):
        """把 self.verses 组装成原子序列（三种排版模式，结构与旧 HTML 版一致）。"""
        rows=[self._verse_row(row) for row in self.verses]
        show_titles=self.show_scripture_titles; show_captions=self.show_captions
        atoms=[]
        def br():
            # vspace 自带断行语义，其后不需要再跟 br
            if atoms and atoms[-1]["kind"] not in ("br","vspace"):
                atoms.append({"kind":"br"})
        def flow(text,style):
            parts=str(text or "").split("\n")
            for i,part in enumerate(parts):
                if i: br()
                for ck,cs in _clusters(self._punct(_norm_ws(part).strip())):
                    if ck=="sp":
                        atoms.append({"kind":"sp"})
                    else:
                        atoms.append({"kind":"w","text":cs,"style":style})
        # 小标题与后续内容的垂直间距（「小标题与正文间距」设置）
        subtitle_gap=self._subtitle_vspace()
        if self.verse_segmentation:
            for ch,n,t,titles,captions in rows:
                if show_titles:
                    for subtitle in titles:
                        br(); flow(subtitle,"title")
                        # vspace 自带断行：替代小标题后的尾 br，不再叠加
                        atoms.append({"kind":"vspace","h":subtitle_gap})
                above,inline=self._split_captions(captions)
                if show_captions:
                    for caption in above: br(); flow(caption,"caption"); br()
                else:
                    inline=[]
                br()
                atoms.extend(self._verse_atoms(ch,n,t,leading_gap=False,inline_captions=inline))
        elif show_titles or show_captions:
            has_content=False
            for ch,n,t,titles,captions in rows:
                # 与分节模式一样用 br() helper：直接 append 会在
                # 小标题尾 br + 题注头 br 处叠出连续两个 br，
                # _relayout 把它当成一个正文行高的空行 → 巨大垂直空白。
                # 每段前 br()：小标题/题注各自独立成行，正文仍连排
                if show_titles:
                    for subtitle in titles:
                        br(); flow(subtitle,"title")
                        atoms.append({"kind":"vspace","h":subtitle_gap})
                        has_content=True
                above,inline=self._split_captions(captions)
                if show_captions:
                    for caption in above:
                        br(); flow(caption,"caption"); br(); has_content=True
                else:
                    inline=[]
                atoms.extend(self._verse_atoms(ch,n,t,leading_gap=has_content,inline_captions=inline)); has_content=True
        else:
            for vi,(ch,n,t,_titles,_captions) in enumerate(rows):
                atoms.extend(self._verse_atoms(ch,n,t,leading_gap=(vi>0),inline_captions=[]))
        while atoms and atoms[-1]["kind"]=="br":
            atoms.pop()
        return atoms
    def _subtitle_vspace(self):
        """小标题后的垂直空隙（像素，允许负值）。

        统一连续公式：贴上偏移 + 设置值。贴上偏移为负空隙，恰好抵消
        小标题行的 descent 与额外行距，把下一行的行盒顶吸到小标题基线
        +2px（观感与大标题 0 间距一致）；设置值在其上线性叠加，
        0→1px 只差 1px，不再有模式切换的跳变。
        不重叠性：下一行行盒顶 = 小标题基线 + 2px + 设置值，任何
        字号/行距/间距组合都不会与小标题墨迹重叠。"""
        gap = max(0, int(getattr(self, "scripture_title_gap", 30)))
        st = self._body_styles()
        fm_t = QFontMetricsF(st["title"][0])
        # 行盒 advance = ceil(行内最大字高) × 行距%，行距因子全局统一（正文行距，
        # 见 set_content/_line_factor）
        factor = max(0.5, float(getattr(self, "line_spacing", 160)) / 100.0)
        extra = math.ceil(fm_t.height()) * (factor - 1.0)
        # 保留浮点步进，且不能用 _px()：它有 max(1,…) 下限，会把 0px 抬成 1px，
        # 导致 0→1 无差别（用户反馈的跳变/无变化问题）
        scale = self.layout_scale()
        return int(round(2.0 * scale)) - fm_t.descent() - extra + int(round(gap * scale))
    def _split_captions(self,captions):
        """题注分两类：节上方（篇首注/说话人）与节末内联（细拉/Selah）。"""
        above=[]; inline=[]
        for c in captions or []:
            (inline if str(c) in _SELAH_TEXTS else above).append(c)
        return above,inline
    def _render_scripture(self):
        # fill 模式缩放冻结：首次真实渲染时按当时窗口高定格，此后缩放窗口
        # 不再改变字号（否则每节经文加载都按新窗口高重算，字号跟着漂移）；
        # 全屏等显示面突变走 recalibrate_fill_scale 重估
        if self._reference_size is None and self._fill_scale is None and self.height()>=200:
            self._fill_scale=max(0.55,min(3.0,float(self.height())/float(self._design_height)))
            self._update_viewport_margins()   # 边距/底注与冻结后的字号同刻度
        # 语种检测：中日韩字符占多数 → 两端对齐；拉丁文（英文译本）→ 左对齐
        sample = "".join(str(self._verse_row(row)[2] or "") for row in self.verses)
        cjk = sum(1 for ch in sample if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
        latin = sum(1 for ch in sample if ch.isascii() and ch.isalpha())
        self._text_justify = cjk >= latin
        # 旧 QTextDocument 渲染里 div 的 padding-top/bottom 实测不生效（文档高=行进之和），
        # 自绘布局同样不加首尾衬距，保持观感与滚动量一致
        self._fit_document_width()   # 先把行宽就位，避免 set_content 在过期宽度上白排一遍
        atoms=self._build_content()
        self.text_display.set_content(
            atoms, self._body_styles(), justify=getattr(self,"_text_justify",True),
            pad_top=0, pad_bottom=0, line_spacing_pct=self.line_spacing,
        )
    def _update_footer_style(self):
        fs=self._px(self.footer_size); self.footer_label.setText(self._punct(self.footer_text)); self.footer_label.setFont(QFont(self.footer_font_family,fs)); self.footer_label.setStyleSheet(f'color:{self.footer_color.name()};font-family:"{self.footer_font_family}";'+f"font-size:{fs}px;background:transparent;")
    def _ensure_bg_pixmap(self):
        path=self.bg_image
        if not path or not os.path.exists(path): self._bg_pixmap=None; self._bg_pixmap_path=None; self._bg_scaled=None; self._bg_scaled_size=None; return None
        if self._bg_pixmap is None or self._bg_pixmap_path!=path:
            pix=QPixmap(path); self._bg_pixmap=pix if not pix.isNull() else None; self._bg_pixmap_path=path; self._bg_scaled=None; self._bg_scaled_size=None
        return self._bg_pixmap
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True); painter.fillRect(self.rect(),self.bg_color); pix=self._ensure_bg_pixmap()
        if pix is not None:
            size=self.size()
            if self._bg_scaled is None or self._bg_scaled_size!=size: self._bg_scaled=pix.scaled(size,Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation); self._bg_scaled_size=size
            scaled=self._bg_scaled; painter.drawPixmap((self.width()-scaled.width())//2,(self.height()-scaled.height())//2,scaled)
        super().paintEvent(event); self._update_overlay_geometry()
    def _on_body_scroll_changed(self,value): self.scroll_changed.emit(int(round(value)))
    def set_follow_only(self, on: bool):
        """副屏：只跟主屏位置，忽略滚轮和 Home/End。"""
        self.text_display.set_follow_only(on)
        enabled = not bool(on)
        self._home_shortcut.setEnabled(enabled)
        self._end_shortcut.setEnabled(enabled)
    def scroll_position(self): return self.text_display.scroll_y()
    def max_scroll(self): return self.text_display.max_scroll()
    def scroll_fraction(self): return self.text_display.scroll_fraction()
    def set_scroll_position(self,value): self.text_display.set_scroll_y(value)
    def set_scroll_fraction(self,fraction): self.text_display.set_scroll_fraction(fraction)
    def scroll_by(self,delta): self.text_display.scroll_by(delta)
    def force_scroll_to(self,value): self.set_scroll_position(value)
    def set_scroll_speed(self,speed):
        try:speed=max(0,min(9,int(speed)))
        except (TypeError,ValueError):speed=0
        self.scroll_speed=speed
        if speed<=0:self.scroll_timer.stop(); self._scroll_clock.invalidate(); return
        self._apply_refresh_interval(); self._scroll_clock.restart()
        if not self.scroll_timer.isActive():self.scroll_timer.start()
    def _apply_refresh_interval(self): self.scroll_timer.setInterval(max(8,int(round(1000.0/self._refresh_hz))))
    def _auto_scroll(self):
        if self.scroll_speed<=0:return
        if not self._scroll_clock.isValid():self._scroll_clock.start();return
        elapsed_ms=max(0,self._scroll_clock.restart()); delta=elapsed_ms*self.scroll_speed/self._TICK_MS_LEGACY; current=self.scroll_position(); target=min(self.max_scroll(),current+delta); self.set_scroll_position(target)
        if target>=self.max_scroll()-0.5:
            self.set_scroll_speed(0)
            if self.max_scroll()>0: self.scroll_finished.emit()
    def apply_settings(self,settings):
        self.font_family=settings.get("font_family",self.font_family)
        self.font_size=int(settings.get("font_size",self.font_size))
        self.font_color=_coerce_color(settings.get("font_color",self.font_color),"#FFFFFF")
        self.bg_color=_coerce_color(settings.get("bg_color",self.bg_color),"#000000")
        new_bg_image=settings.get("bg_image",self.bg_image)
        if new_bg_image!=self.bg_image:
            self._bg_pixmap=None; self._bg_pixmap_path=None; self._bg_scaled=None; self._bg_scaled_size=None
        self.bg_image=new_bg_image
        self.line_spacing=int(settings.get("line_spacing",self.line_spacing))
        self.margin_left=int(settings.get("margin",self.margin_left))
        self.margin_right=int(settings.get("margin",self.margin_right))
        self.title_font_family=settings.get("title_font_family",self.title_font_family)
        self.title_color=_coerce_color(settings.get("title_color",self.title_color),"#87CEEB")
        self.title_size=int(settings.get("title_size",self.title_size))
        self.title_gap=max(0,int(settings.get("title_gap",getattr(self,"title_gap",0))or 0))
        self.scripture_title_gap=max(0,int(settings.get("scripture_title_gap",getattr(self,"scripture_title_gap",30))or 0))
        self.show_scripture_titles=_coerce_bool(settings.get("show_scripture_titles",self.show_scripture_titles),self.show_scripture_titles)
        self.show_captions=_coerce_bool(settings.get("show_captions",getattr(self,"show_captions",True)),True)
        self.scripture_title_font_family=str(settings.get("scripture_title_font_family",self.scripture_title_font_family))
        try: self.scripture_title_size=max(10,min(200,int(settings.get("scripture_title_size",self.scripture_title_size))))
        except (TypeError,ValueError): self.scripture_title_size=30
        self.scripture_title_color=_coerce_color(settings.get("scripture_title_color",self.scripture_title_color),"#87CEEB")
        self.caption_font_family=str(settings.get("caption_font_family",self.caption_font_family))
        try: self.caption_size=max(10,min(200,int(settings.get("caption_size",self.caption_size))))
        except (TypeError,ValueError): self.caption_size=24
        self.caption_color=_coerce_color(settings.get("caption_color",self.caption_color),"#87CEEB")
        self.caption_italic=_coerce_bool(settings.get("caption_italic",getattr(self,"caption_italic",True)),True)
        self.verse_num_font_family=settings.get("verse_num_font_family",self.verse_num_font_family)
        self.verse_num_gap_left=max(0,int(settings.get("verse_num_gap_left",getattr(self,"verse_num_gap_left",0))or 0))
        self.verse_num_gap_right=max(0,int(settings.get("verse_num_gap_right",getattr(self,"verse_num_gap_right",0))or 0))
        self.punct_halfwidth=_coerce_bool(settings.get("punct_halfwidth",getattr(self,"punct_halfwidth",True)),True)
        self.verse_num_size=int(settings.get("verse_num_size",self.verse_num_size))
        self.verse_num_color=_coerce_color(settings.get("verse_num_color",self.verse_num_color),"#FFD700")
        self.footer_font_family=settings.get("footer_font_family",self.footer_font_family)
        self.footer_size=int(settings.get("footer_size",self.footer_size))
        self.footer_color=_coerce_color(settings.get("footer_color",self.footer_color),"#AAAAAA")
        self.footer_text=settings.get("footer_text",self.footer_text)
        self.footer_height=int(settings.get("footer_height",self.footer_height))
        self._refresh_layout_metrics(); self._update_footer_style(); self.update()
    def _update_overlay_geometry(self):
        if not self.footer_label:return
        h=self._px(self.footer_height); self.footer_label.setGeometry(0,max(0,self.height()-h),self.width(),h)
