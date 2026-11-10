# 经文显示核心控件
# 提词器式滚动：QTextDocument + 浮点偏移绘制，避免滚动条整像素台阶
import os
import re
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import (
    Qt, QTimer, QElapsedTimer, pyqtSignal, QPropertyAnimation, QEasingCurve,
    pyqtProperty, QRectF,
)
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QFontMetrics, QPainter, QTextDocument, QShortcut, QKeySequence,
    QTextCursor, QTextBlockFormat,
)

from app.feature_flags import ENABLE_SCRIPTURE_TITLES

# 收尾标点：不能出现在行首（中文禁则）
_PUNCT_CLOSING = "，。；：？！、）”』》〉…—％·’"
# 节末内联题注文本（细拉/Selah，与转换器写库的字面一致）；其余题注显示在节上方
_SELAH_TEXTS = {"（细拉）", "（細拉）", "Selah"}
# 节中说话人标签独立行（转换器以 \n 分隔写入正文，如「〔新娘〕」），按题注样式渲染
_STANDALONE_CAPTION_RE = re.compile(r"^〔[^〕]*〕$")
# 开引号/开括号：不能出现在行尾
_PUNCT_OPENING = "（“『「《〈‘"
_CJK_RANGES = "\u4e00-\u9fff\u3000-\u303f\uff00-\uffef\u2018\u2019\u201c\u201d（）【】《》〈〉…—％·’‘"

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
# 行首 禁排 (halfwidth closing)
_HALF_CLOSING = ',.;:?!' + chr(8217) + chr(8221) + ')'
_HALF_OPENING = '(' + chr(8220) + chr(8216)


def _inject_break_points(text):
    """禁则感知断点：在相邻可断中文之间注入零宽空格 U+200B。

    作用：给两端对齐提供字间拉伸/断行点（纯中文行无空格，Qt 靠它才能
    把行撑满到右边距）。保持中文禁则：跳过「下一个字是收尾标点」和
    「当前字是开引号/开括号」的边界，行首永不出现标点。
    """
    chars = list(text)
    out = []
    for i, ch in enumerate(chars):
        out.append(ch)
        if i + 1 >= len(chars):
            break
        nxt = chars[i + 1]
        # 只在纯汉字之间注入：标点旁不留拉伸/断行点，
        # 标点簇（说："看 、 人'， ）保持紧凑，不被两端对齐拉开
        if not ("\u4e00" <= ch <= "\u9fff"):
            continue
        if not ("\u4e00" <= nxt <= "\u9fff"):
            continue
        out.append("\u200b")
    return "".join(out)


def _halfwidth(text):
    """全角标点 → 半角字形（仅渲染层转换，不改源文本）。"""
    return "".join(_PUNCT_HALF.get(ch, ch) for ch in str(text))


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
    """经文正文区：用浮点 scroll_y 平移绘制，观感接近网页提词器。"""
    scroll_changed = pyqtSignal(float)
    def __init__(self, parent=None):
        super().__init__(parent); self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False); self.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.setMouseTracking(True); self._doc = QTextDocument(self); self._doc.setDocumentMargin(0); self._scroll_y = 0.0; self._pad_left = 0; self._pad_right = 0; self._pad_bottom = 0; self._wheel_step = 48.0; self._follow_only = False
    def set_html(self, html, justify=True):
        self._doc.setHtml(html); self._doc.setDocumentMargin(0)
        # HTML 里的 text-align:justify 会被 Qt 静默忽略：程序化补对齐。
        # 中文（无空格断行）用两端对齐字间拉伸撑满行尾；
        # 英文等拉丁文本用左对齐（强行两端对齐会拉出巨大词间距）
        cursor = QTextCursor(self._doc)
        cursor.select(QTextCursor.SelectionType.Document)
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(
            Qt.AlignmentFlag.AlignJustify if justify else Qt.AlignmentFlag.AlignLeft
        )
        cursor.mergeBlockFormat(block_fmt)
        self._clamp_scroll(); self.update()
    def set_pads(self,left,right,bottom): self._pad_left=max(0,int(left)); self._pad_right=max(0,int(right)); self._pad_bottom=max(0,int(bottom)); self._fit_text_width(); self._clamp_scroll(); self.update()
    def set_text_width(self,width): self._doc.setTextWidth(max(1.0,float(width))); self._clamp_scroll(); self.update()
    def _fit_text_width(self): self._doc.setTextWidth(float(max(1,self.width()-self._pad_left-self._pad_right)))
    def content_height(self): return float(self._doc.size().height())
    def view_height(self): return max(1.0,float(max(0,self.height()-self._pad_bottom)))
    def max_scroll(self): return max(0.0,self.content_height()-self.view_height())
    def scroll_y(self): return self._scroll_y
    def set_scroll_y(self,value,emit=True):
        try: y=float(value)
        except (TypeError,ValueError): return
        y=max(0.0,min(y,self.max_scroll()))
        if abs(y-self._scroll_y)<1e-4: self._scroll_y=y; return
        self._scroll_y=y; self.update()
        if emit: self.scroll_changed.emit(self._scroll_y)
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
    def scroll_by(self,delta):
        try: delta=float(delta)
        except (TypeError,ValueError): return
        self.set_scroll_y(self._scroll_y+delta)
    def set_follow_only(self, on: bool):
        self._follow_only = bool(on)
    def wheelEvent(self,event):
        if self._follow_only:
            event.accept()
            return
        angle=event.angleDelta().y(); pixel=event.pixelDelta().y()
        if pixel: delta=-float(pixel)
        elif angle: delta=-(float(angle)/120.0)*self._wheel_step
        else: event.ignore(); return
        old=self._scroll_y; self.scroll_by(delta)
        if abs(self._scroll_y-old)>1e-4: event.accept()
        else: event.ignore()
    def resizeEvent(self,event): super().resizeEvent(event); self._fit_text_width(); self._clamp_scroll()
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.TextAntialiasing,True); painter.setRenderHint(QPainter.RenderHint.Antialiasing,True); clip=self.rect()
        if self._pad_bottom: clip.setHeight(max(0,clip.height()-self._pad_bottom))
        painter.setClipRect(clip); painter.translate(float(self._pad_left),-self._scroll_y)
        # 大文档（多章）下 drawContents 全量遍历每帧 35ms+，拖慢整个界面。
        # 文档不大时保持原路径（渲染逐像素一致）；大文档才按可见区裁剪，
        # 每帧只画屏幕上的几行，耗时与经文总量无关
        if float(self._doc.size().height()) <= 30000.0:
            self._doc.drawContents(painter)
        else:
            buf = max(8.0, float(clip.height()) * 0.05)
            vis_h = max(1.0, float(clip.height()) + 2.0 * buf)
            tw = float(self._doc.textWidth())
            if tw <= 0: tw = float(max(1, self.width() - self._pad_left - self._pad_right))
            self._doc.drawContents(painter, QRectF(0.0, self._scroll_y - buf, tw, vis_h))
    def document(self): return self._doc


class ScriptureDisplay(QWidget):
    scroll_changed=pyqtSignal(int); scroll_finished=pyqtSignal(); _TICK_MS_LEGACY=30.0
    def __init__(self,parent=None):
        super().__init__(parent); self.font_family="微软雅黑"; self.font_size=24; self.font_color=QColor("#FFFFFF"); self.bg_color=QColor("#000000"); self.bg_image=None; self._bg_pixmap=None; self._bg_pixmap_path=None; self._bg_scaled=None; self._bg_scaled_size=None; self.line_spacing=160; self.margin_left=60; self.margin_right=60; self.title_font_family="微软雅黑"; self.title_color=QColor("#87CEEB"); self.title_size=36; self.title_min_size=12; self.title_spacing=12; self.show_scripture_titles=False; self.show_captions=True; self.scripture_title_font_family="微软雅黑"; self.scripture_title_size=30; self.scripture_title_color=QColor("#87CEEB"); self.scripture_title_spacing=8; self.scripture_title_line_spacing=120; self.caption_font_family="微软雅黑"; self.caption_size=24; self.caption_color=QColor("#87CEEB"); self.caption_italic=True; self.verse_num_color=QColor("#FFD700"); self.verse_num_size=24; self.verse_num_font_family="微软雅黑"; self.footer_text=""; self.footer_height=45; self.footer_size=14; self.footer_color=QColor("#AAAAAA"); self.footer_font_family="微软雅黑"; self.scroll_speed=0; self._scroll_anim=None; self._scroll_clock=QElapsedTimer(); self._refresh_hz=60.0; self._screen_hooked=False; self._title_text=""; self.verses=[]; self.verse_segmentation=False; self._show_chapter_nums=False; self._reference_size=None; self._design_height=1080; self.scroll_timer=QTimer(self); self.scroll_timer.setTimerType(Qt.TimerType.PreciseTimer); self.scroll_timer.timeout.connect(self._auto_scroll); self._apply_refresh_interval(); self._init_ui(); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self._home_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Home),self); self._home_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); self._home_shortcut.activated.connect(self._scroll_to_top); self._end_shortcut=QShortcut(QKeySequence(Qt.Key.Key_End),self); self._end_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); self._end_shortcut.activated.connect(self._scroll_to_bottom); self.punct_halfwidth=False
    def _init_ui(self):
        # 自己在 paintEvent 里铺底色/背景图，不要让样式表/调色板先盖一层黑
        self.setAutoFillBackground(False)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0); self.title_bar=QLabel(""); self.title_bar.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter); self.title_bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True); layout.addWidget(self.title_bar); self.text_display=ScriptureBody(); self.text_display.scroll_changed.connect(self._on_body_scroll_changed); layout.addWidget(self.text_display,1); self.footer_label=QLabel(self); self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True); self.footer_label.show(); self._update_footer_style(); self._update_viewport_margins()
    def _scroll_to_top(self):
        if self.scroll_speed>0 or self.scroll_timer.isActive(): self.set_scroll_speed(0); self.scroll_finished.emit()
        self.set_scroll_position(0)
    def _scroll_to_bottom(self):
        if self.scroll_speed>0 or self.scroll_timer.isActive(): self.set_scroll_speed(0); self.scroll_finished.emit()
        self.set_scroll_position(self.max_scroll())
    def layout_scale(self): return max(0.55,min(3.0,float(self._reference_size[1])/float(self._design_height))) if self._reference_size else max(0.55,min(3.0,float(max(1,self.height()))/float(self._design_height)))
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
        self.verses=[]; self._show_chapter_nums=False; self._set_adaptive_title(""); self.text_display.set_html(""); self.set_scroll_position(0); self.update()
    def _set_adaptive_title(self,text):
        self._title_text=str(text or ""); shown=self._punct(self._title_text); size=max(self._px(self.title_min_size),self._px(self.title_size)); font=QFont(self.title_font_family,size); font.setBold(True); pad=self._px(24); avail=max(100,self.title_bar.width()-pad*2); min_size=self._px(self.title_min_size)
        while QFontMetrics(font).horizontalAdvance(shown)>avail and size>min_size:
            size-=1; font=QFont(self.title_font_family,size); font.setBold(True)
        h=max(self._px(42),QFontMetrics(font).height()+self._px(6)); self.title_bar.setMinimumHeight(h); self.title_bar.setMaximumHeight(h); self.title_bar.setFont(font); self.title_bar.setStyleSheet(f'color:{self.title_color.name()};font-family:"{self.title_font_family}";'+f"font-size:{size}px;font-weight:bold;background:transparent;padding:0 {pad}px;"); self.title_bar.setText(shown)
    def set_verse_segmentation(self,enabled):
        enabled=bool(enabled)
        if self.verse_segmentation==enabled:return
        old=self.scroll_fraction(); self.verse_segmentation=enabled
        if self.verses:self._render_scripture(); self.set_scroll_fraction(old)
    def set_scripture_titles(self,enabled):
        enabled=bool(enabled) and ENABLE_SCRIPTURE_TITLES
        if self.show_scripture_titles==enabled:return
        old=self.scroll_fraction(); self.show_scripture_titles=enabled
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
                    segs.append(("caption",s))
            else:
                segs.append(("body",s))
        return segs
    def _verse_html(self,chapter,n,t,leading_gap=True,inline_captions=None):
        vn=self._px(self.verse_num_size); fs=self._px(self.font_size)
        label=f"{chapter}:{n}" if getattr(self,"_show_chapter_nums",False) and chapter is not None else str(n)
        # 节号前后间隙用 margin（边距不是两端对齐的拉伸点，恒定不变形）；
        # 节与节的分隔不用空格字符——空格会被对齐拉伸出大空隙
        gl=max(2,self._px(self.verse_num_gap_left)) if self.verse_num_gap_left>0 else max(6,int(vn*1.0))
        gr=max(2,self._px(self.verse_num_gap_right)) if self.verse_num_gap_right>0 else max(6,int(vn*1.0))
        lead = f'<span style="letter-spacing:{gl}px;font-size:{gl}px;">​</span>' if leading_gap else ''
        # 前间隙：零宽字符+正字距（跟随节号字号；段首/行首不 leading）
        # 前后间隙用「零宽字符+正字距」span：Qt 对 letter-spacing 渲染可靠，
        # 且该间隙不是空格字符，不会被两端对齐拉伸出大空隙
        def esc(s): return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        num_span = (f'<span style="color:{self.verse_num_color.name()};font-size:{vn}px;font-family:&quot;{self.verse_num_font_family}&quot;;font-weight:bold;vertical-align:super;">{label}</span>')
        text_style = f'color:{self.font_color.name()};font-size:{fs}px;font-family:&quot;{self.font_family}&quot;;'
        segs=self._verse_segments(t)
        if not segs:
            return num_span + self._inline_captions_html(inline_captions)
        # U+2060 WORD JOINER：节号与正文首字之间禁止断行（不会分离）
        bind = '⁠'
        out=(f'{lead}{num_span}'
             f'<span style="letter-spacing:{gr}px;font-size:{gr}px;">{bind}</span>{bind}')
        first_body=True
        for kind,s in segs:
            if kind=="caption":
                # 节中说话人标签：独立行、题注样式，不并入正文行内
                out+=f'<br><span style="{self._caption_style()}">{self._punct(esc(s))}</span>'
                continue
            h=self._punct(esc(s))
            if first_body:
                first, rest = (h[:1], h[1:]) if h else ("", "")
                rest = _inject_break_points(rest)
                out+=(f'<span style="{text_style}">{first}</span>'
                      f'<span style="{text_style}">{rest}</span>')
                first_body=False
            else:
                h=_inject_break_points(h)
                out+=f'<br><span style="{text_style}">{h}</span>'
        return out + self._inline_captions_html(inline_captions)
    def _title_html(self,text):
        safe=self._punct(str(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")).replace("\n","<br>"); fs=self._px(self.scripture_title_size); return f'<p style="margin:0 0 8px 0;padding:0;line-height:{self.line_spacing}%;"><span style="color:{self.scripture_title_color.name()};font-size:{fs}px;font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;">{safe}</span></p>'
    def _title_inline_html(self,text):
        safe=self._punct(str(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")).replace("\n","<br>"); fs=self._px(self.scripture_title_size); return f'<br><span style="color:{self.scripture_title_color.name()};font-size:{fs}px;font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;">{safe}</span><br>'
    def _caption_style(self):
        # 题注（篇首注/说话人标签/细拉）：独立设置项，斜体可选、不加粗以区别于小标题
        fs=self._px(self.caption_size)
        style=(f'color:{self.caption_color.name()};font-size:{fs}px;'
               f'font-family:&quot;{self.caption_font_family}&quot;;font-weight:normal;')
        if getattr(self,"caption_italic",True): style+="font-style:italic;"
        return style
    def _caption_html(self,text):
        safe=self._punct(str(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")).replace("\n","<br>")
        return f'<p style="margin:0 0 8px 0;padding:0;line-height:{self.line_spacing}%;"><span style="{self._caption_style()}">{safe}</span></p>'
    def _caption_inline_html(self,text):
        safe=self._punct(str(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")).replace("\n","<br>")
        return f'<br><span style="{self._caption_style()}">{safe}</span><br>'
    def _inline_captions_html(self,captions):
        """节末内联题注（细拉/Selah）：跟随经文排版，用 margin 间隙避免两端对齐拉伸。"""
        if not captions: return ""
        gap=max(6,self._px(self.caption_size)//3)
        parts=[]
        for c in captions or []:
            safe=self._punct(str(c or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"))
            parts.append(f'<span style="{self._caption_style()}margin-left:{gap}px;">{safe}</span>')
        return "".join(parts)
    def _split_captions(self,captions):
        """题注分两类：节上方（篇首注/说话人）与节末内联（细拉/Selah）。"""
        above=[]; inline=[]
        for c in captions or []:
            (inline if str(c) in _SELAH_TEXTS else above).append(c)
        return above,inline
    def _verse_block_html(self,chapter,n,t,inline_captions=None): return f"<p style='margin:0;padding:0;line-height:{self.line_spacing}%;'>{self._verse_html(chapter,n,t,leading_gap=False,inline_captions=inline_captions)}</p>"
    def _render_scripture(self):
        # 语种检测：中日韩字符占多数 → 两端对齐；拉丁文（英文译本）→ 左对齐
        sample = "".join(str(self._verse_row(row)[2] or "") for row in self.verses)
        cjk = sum(1 for ch in sample if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
        latin = sum(1 for ch in sample if ch.isascii() and ch.isalpha())
        self._text_justify = cjk >= latin
        fs=self._px(self.font_size); top=max(10,int(fs*0.35)); bottom=max(12,int(fs*0.45)); html=f"<div style='padding-top:{top}px;padding-bottom:{bottom}px;margin:0;line-height:{self.line_spacing}%;'>"; rows=[self._verse_row(row) for row in self.verses]
        show_titles=self.show_scripture_titles; show_captions=self.show_captions
        if self.verse_segmentation:
            blocks=[]
            for ch,n,t,titles,captions in rows:
                if show_titles:
                    for subtitle in titles: blocks.append(self._title_html(subtitle))
                above,inline=self._split_captions(captions)
                if show_captions:
                    for caption in above: blocks.append(self._caption_html(caption))
                else:
                    inline=[]
                blocks.append(self._verse_block_html(ch,n,t,inline_captions=inline))
            html+="".join(blocks)
        elif show_titles or show_captions:
            html+="<p style='margin:0;padding:0;white-space:normal;'>"; has_content=False
            for ch,n,t,titles,captions in rows:
                if show_titles:
                    for subtitle in titles:
                        if has_content: html+="<br>"
                        html+=self._title_inline_html(subtitle); has_content=True
                above,inline=self._split_captions(captions)
                if show_captions:
                    for caption in above:
                        if has_content: html+="<br>"
                        html+=self._caption_inline_html(caption); has_content=True
                else:
                    inline=[]
                html+=self._verse_html(ch,n,t,leading_gap=has_content,inline_captions=inline); has_content=True
            html+="</p>"
        else:
            flow_parts=[]
            for vi,(ch,n,t,_titles,_captions) in enumerate(rows):
                flow_parts.append(self._verse_html(ch,n,t,leading_gap=(vi>0)))
            html+="<p style='margin:0;padding:0;white-space:normal;'>"+"".join(flow_parts)+"</p>"
        self.text_display.set_html(html+"</div>", justify=getattr(self, "_text_justify", True)); self._fit_document_width()
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
        self.title_spacing=int(settings.get("title_spacing",self.title_spacing))
        self.show_scripture_titles=_coerce_bool(settings.get("show_scripture_titles",self.show_scripture_titles),self.show_scripture_titles)
        if not ENABLE_SCRIPTURE_TITLES:
            self.show_scripture_titles=False
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
    def set_title(self,title): self._set_adaptive_title(title)
    def _update_overlay_geometry(self):
        if not self.footer_label:return
        h=self._px(self.footer_height); self.footer_label.setGeometry(0,max(0,self.height()-h),self.width(),h)
