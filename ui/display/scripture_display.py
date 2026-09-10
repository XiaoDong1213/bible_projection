# 经文显示核心控件
# 提词器式滚动：QTextDocument + 浮点偏移绘制，避免滚动条整像素台阶
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import (
    Qt, QTimer, QElapsedTimer, pyqtSignal, QPropertyAnimation, QEasingCurve,
    pyqtProperty,
)
from PyQt6.QtGui import (
    QFont, QColor, QPixmap, QFontMetrics, QPainter, QTextDocument, QShortcut, QKeySequence,
)


class ScriptureBody(QWidget):
    """经文正文区：用浮点 scroll_y 平移绘制，观感接近网页提词器。"""
    scroll_changed = pyqtSignal(float)
    def __init__(self, parent=None):
        super().__init__(parent); self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False); self.setFocusPolicy(Qt.FocusPolicy.NoFocus); self.setMouseTracking(True); self._doc = QTextDocument(self); self._doc.setDocumentMargin(0); self._scroll_y = 0.0; self._pad_left = 0; self._pad_right = 0; self._pad_bottom = 0; self._wheel_step = 48.0
    def set_html(self, html): self._doc.setHtml(html); self._doc.setDocumentMargin(0); self._clamp_scroll(); self.update()
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
    def scroll_by(self,delta):
        try: delta=float(delta)
        except (TypeError,ValueError): return
        self.set_scroll_y(self._scroll_y+delta)
    def wheelEvent(self,event):
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
        painter.setClipRect(clip); painter.translate(float(self._pad_left),-self._scroll_y); self._doc.drawContents(painter)
    def document(self): return self._doc


class ScriptureDisplay(QWidget):
    scroll_changed=pyqtSignal(int); scroll_finished=pyqtSignal(); _TICK_MS_LEGACY=30.0
    def __init__(self,parent=None):
        super().__init__(parent); self.font_family="微软雅黑"; self.font_size=24; self.font_color=QColor("#FFFFFF"); self.bg_color=QColor("#000000"); self.bg_image=None; self._bg_pixmap=None; self._bg_pixmap_path=None; self._bg_scaled=None; self._bg_scaled_size=None; self.line_spacing=160; self.margin_left=60; self.margin_right=60; self.title_font_family="微软雅黑"; self.title_color=QColor("#87CEEB"); self.title_size=36; self.title_min_size=12; self.title_spacing=12; self.show_scripture_titles=False; self.verse_num_color=QColor("#FFD700"); self.verse_num_size=24; self.verse_num_font_family="微软雅黑"; self.footer_text=""; self.footer_height=45; self.footer_size=14; self.footer_color=QColor("#AAAAAA"); self.footer_font_family="微软雅黑"; self.scroll_speed=0; self._scroll_anim=None; self._scroll_clock=QElapsedTimer(); self._refresh_hz=60.0; self._screen_hooked=False; self._title_text=""; self.verses=[]; self.verse_segmentation=False; self._show_chapter_nums=False; self._reference_size=None; self._design_height=1080; self.scroll_timer=QTimer(self); self.scroll_timer.setTimerType(Qt.TimerType.PreciseTimer); self.scroll_timer.timeout.connect(self._auto_scroll); self._apply_refresh_interval(); self._init_ui(); self.setFocusPolicy(Qt.FocusPolicy.StrongFocus); self._home_shortcut=QShortcut(QKeySequence(Qt.Key.Key_Home),self); self._home_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); self._home_shortcut.activated.connect(self._scroll_to_top); self._end_shortcut=QShortcut(QKeySequence(Qt.Key.Key_End),self); self._end_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut); self._end_shortcut.activated.connect(self._scroll_to_bottom)
    def _init_ui(self):
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0); self.title_bar=QLabel(""); self.title_bar.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter); layout.addWidget(self.title_bar); self.text_display=ScriptureBody(); self.text_display.scroll_changed.connect(self._on_body_scroll_changed); layout.addWidget(self.text_display,1); self.footer_label=QLabel(self); self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); self.footer_label.show(); self._update_footer_style(); self._update_viewport_margins()
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
    def set_scripture(self,book_name,chapter,start_verse,end_verse,verses,title=None,show_chapter_nums=False):
        self.verses=list(verses or []); self._show_chapter_nums=bool(show_chapter_nums)
        if title: self._set_adaptive_title(title)
        else:
            unit="篇" if book_name=="诗篇" else "章"
            if start_verse is None: title_text=f"{book_name}{chapter}{unit}"
            elif end_verse is None: title_text=f"{book_name}{chapter}{unit}{start_verse}-末节"
            elif start_verse==end_verse: title_text=f"{book_name}{chapter}{unit}{start_verse}节"
            else: title_text=f"{book_name}{chapter}{unit}{start_verse}-{end_verse}节"
            self._set_adaptive_title(title_text)
        self._render_scripture(); self.set_scroll_position(0); self.update()
    def _logical_title_from_verses(self, selection, verses):
        """优先使用数据库解析出的逻辑节号，让投影顶部标题与正文连续节显示一致。"""
        if not selection.is_simple or not verses: return selection.title()
        try:
            first=verses[0]
            label=str(first[1]) if len(first)>=2 else ""
            if not label or "-" not in label: return selection.title()
            span=selection.spans[0]
            # 只有当逻辑节号确实落在当前选择范围内时才替换标题。
            parts=label.split("-",1)
            start=int(parts[0]); end=int(parts[1])
            if start<=span.start<=end:
                unit="篇" if selection.book=="诗篇" else "章"
                return f"{selection.book}{span.chapter}{unit}{label}节"
        except (TypeError,ValueError,IndexError): pass
        return selection.title()
    def set_from_selection(self,selection,verses):
        title=self._logical_title_from_verses(selection,verses)
        self.set_scripture(selection.book,selection.primary_chapter,selection.primary_start,selection.primary_end,verses,title=title,show_chapter_nums=selection.is_multi_chapter)
    def clear_scripture(self):
        self.verses=[]; self._show_chapter_nums=False; self._set_adaptive_title(""); self.text_display.set_html(""); self.set_scroll_position(0); self.update()
    def _set_adaptive_title(self,text):
        self._title_text=str(text or ""); size=max(self._px(self.title_min_size),self._px(self.title_size)); font=QFont(self.title_font_family,size); font.setBold(True); pad=self._px(24); avail=max(100,self.title_bar.width()-pad*2); min_size=self._px(self.title_min_size)
        while QFontMetrics(font).horizontalAdvance(self._title_text)>avail and size>min_size:
            size-=1; font=QFont(self.title_font_family,size); font.setBold(True)
        h=max(self._px(42),QFontMetrics(font).height()+self._px(6)); self.title_bar.setMinimumHeight(h); self.title_bar.setMaximumHeight(h); self.title_bar.setFont(font); self.title_bar.setStyleSheet(f'color:{self.title_color.name()};font-family:"{self.title_font_family}";'+f"font-size:{size}px;font-weight:bold;background:transparent;padding:0 {pad}px;"); self.title_bar.setText(self._title_text)
    def set_verse_segmentation(self,enabled):
        enabled=bool(enabled)
        if self.verse_segmentation==enabled:return
        old=self.scroll_fraction(); self.verse_segmentation=enabled
        if self.verses:self._render_scripture(); self.set_scroll_fraction(old)
    def set_scripture_titles(self,enabled):
        enabled=bool(enabled)
        if self.show_scripture_titles==enabled:return
        old=self.scroll_fraction(); self.show_scripture_titles=enabled
        if self.verses:self._render_scripture(); self.set_scroll_fraction(old)
    def _verse_row(self,row):
        if row is None:return None,None,"",[]
        if len(row)>=4:return row[0],row[1],row[2],list(row[3] or [])
        if len(row)>=3:return row[0],row[1],row[2],[]
        return None,row[0],row[1],[]
    def _verse_html(self,chapter,n,t):
        safe=str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"); vn=self._px(self.verse_num_size); fs=self._px(self.font_size); label=f"{chapter}:{n}" if getattr(self,"_show_chapter_nums",False) and chapter is not None else str(n); return f'<span style="color:{self.verse_num_color.name()};font-size:{vn}px;font-family:&quot;{self.verse_num_font_family}&quot;;font-weight:bold;vertical-align:super;">{label}</span>&nbsp;<span style="color:{self.font_color.name()};font-size:{fs}px;font-family:&quot;{self.font_family}&quot;;">{safe}</span>'
    def _title_html(self,text):
        safe=str(text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"); fs=self._px(self.title_size); spacing=self._px(self.title_spacing); return f'<p style="margin:0 0 {spacing}px 0;padding:0;line-height:{self.line_spacing}%;"><span style="color:{self.title_color.name()};font-size:{fs}px;font-family:&quot;{self.title_font_family}&quot;;font-weight:bold;">{safe}</span></p>'
    def _verse_block_html(self,chapter,n,t): return f"<p style='margin:0;padding:0;text-align:justify;line-height:{self.line_spacing}%;'>{self._verse_html(chapter,n,t)}</p>"
    def _render_scripture(self):
        fs=self._px(self.font_size); top=max(10,int(fs*0.35)); bottom=max(12,int(fs*0.45)); html=f"<div style='padding-top:{top}px;padding-bottom:{bottom}px;margin:0;line-height:{self.line_spacing}%;text-align:justify;'>"; rows=[self._verse_row(row) for row in self.verses]
        if self.verse_segmentation:
            blocks=[]
            for ch,n,t,titles in rows:
                if self.show_scripture_titles:
                    for subtitle in titles: blocks.append(self._title_html(subtitle))
                blocks.append(self._verse_block_html(ch,n,t))
            html+="".join(blocks)
        elif self.show_scripture_titles:
            html+="<p style='margin:0;padding:0;white-space:normal;text-align:justify;'>"; has_content=False
            for ch,n,t,titles in rows:
                for subtitle in titles:
                    if has_content: html+="<br>"
                    html+=self._title_inline_html(subtitle); has_content=True
                html+=self._verse_html(ch,n,t)+" "; has_content=True
            html+="</p>"
        else: html+="<p style='margin:0;padding:0;white-space:normal;text-align:justify;'>"+" ".join(self._verse_html(ch,n,t) for ch,n,t,_titles in rows)+"</p>"
        self.text_display.set_html(html+"</div>"); self._fit_document_width()
    def _update_footer_style(self):
        fs=self._px(self.footer_size); self.footer_label.setText(self.footer_text); self.footer_label.setFont(QFont(self.footer_font_family,fs)); self.footer_label.setStyleSheet(f'color:{self.footer_color.name()};font-family:"{self.footer_font_family}";'+f"font-size:{fs}px;background:transparent;")
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
        if target>=self.max_scroll()-0.5:self.set_scroll_speed(0)
    def apply_settings(self,settings):
        self.font_family=settings.get("font_family",self.font_family); self.font_size=int(settings.get("font_size",self.font_size)); self.font_color=QColor(settings.get("font_color",self.font_color.name())); self.bg_color=QColor(settings.get("bg_color",self.bg_color.name())); self.bg_image=settings.get("bg_image",self.bg_image); self.line_spacing=int(settings.get("line_spacing",self.line_spacing)); self.margin_left=int(settings.get("margin",self.margin_left)); self.margin_right=int(settings.get("margin",self.margin_right)); self.title_font_family=settings.get("title_font_family",self.title_font_family); self.title_color=QColor(settings.get("title_color",self.title_color.name())); self.title_size=int(settings.get("title_size",self.title_size)); self.title_spacing=int(settings.get("title_spacing",self.title_spacing)); self.show_scripture_titles=bool(settings.get("show_scripture_titles",self.show_scripture_titles)); self.verse_num_font_family=settings.get("verse_num_font_family",self.verse_num_font_family); self.verse_num_size=int(settings.get("verse_num_size",self.verse_num_size)); self.verse_num_color=QColor(settings.get("verse_num_color",self.verse_num_color.name())); self.footer_font_family=settings.get("footer_font_family",self.footer_font_family); self.footer_size=int(settings.get("footer_size",self.footer_size)); self.footer_color=QColor(settings.get("footer_color",self.footer_color.name())); self.footer_text=settings.get("footer_text",self.footer_text); self.footer_height=int(settings.get("footer_height",self.footer_height)); self._refresh_layout_metrics(); self._update_footer_style(); self.update()
    def set_title(self,title): self._set_adaptive_title(title)
    def _update_overlay_geometry(self):
        if not self.footer_label:return
        h=self._px(self.footer_height); self.footer_label.setGeometry(0,max(0,self.height()-h),self.width(),h)
