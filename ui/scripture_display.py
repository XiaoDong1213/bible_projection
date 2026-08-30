# 经文显示核心控件：主屏滚动，扩展屏同步
import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QFrame
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QColor, QPixmap, QFontMetrics, QPainter

class ScriptureDisplay(QWidget):
    scroll_changed = pyqtSignal(int)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.font_family="微软雅黑"; self.font_size=24; self.font_color=QColor("#FFFFFF"); self.bg_color=QColor("#000000"); self.bg_image=None; self.line_spacing=160; self.margin_left=60; self.margin_right=60
        self.title_font_family="微软雅黑"; self.title_color=QColor("#87CEEB"); self.title_size=36; self.title_min_size=12; self.verse_num_color=QColor("#FFD700"); self.verse_num_size=24; self.verse_num_font_family="微软雅黑"
        self.footer_text=""; self.footer_height=45; self.footer_size=14; self.footer_color=QColor("#AAAAAA"); self.footer_font_family="微软雅黑"; self.scroll_speed=0; self._scroll_anim=None; self._title_text=""; self.verses=[]; self.verse_segmentation=False
        self.scroll_timer=QTimer(self); self.scroll_timer.timeout.connect(self._auto_scroll); self.scroll_timer.setInterval(30); self._init_ui()
    def _init_ui(self):
        layout=QVBoxLayout(self); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0); self.title_bar=QLabel(""); self.title_bar.setAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter); self.title_bar.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); layout.addWidget(self.title_bar)
        self.text_display=QTextEdit(); self.text_display.setReadOnly(True); self.text_display.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.text_display.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.text_display.setFrameShape(QFrame.Shape.NoFrame); self.text_display.setStyleSheet("background:transparent;border:none;padding:0;margin:0;"); self.text_display.viewport().setStyleSheet("background:transparent;"); self.text_display.setContentsMargins(0,0,0,0); self.text_display.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.text_display.document().setDocumentMargin(0); self.text_display.viewport().installEventFilter(self); self.text_display.verticalScrollBar().valueChanged.connect(self._on_scrollbar_changed); layout.addWidget(self.text_display,1)
        self.footer_label=QLabel(self); self.footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground); self.footer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents); self.footer_label.show(); self.footer_label.raise_(); self._update_viewport_margins()
    def _update_viewport_margins(self):
        self.text_display.setViewportMargins(max(0,int(self.margin_left)),0,max(0,int(self.margin_right)),max(0,int(self.footer_height))); self._fit_document_width()
    def _fit_document_width(self):
        if hasattr(self,"text_display"): self.text_display.document().setTextWidth(max(1,self.text_display.viewport().width()))
    def set_scripture(self,book_name,chapter,start_verse,end_verse,verses):
        self.verses=list(verses or []); unit="篇" if book_name=="诗篇" else "章"; title_text=f"{book_name}{chapter}{unit}" if start_verse is None else (f"{book_name}{chapter}{unit}{start_verse}-末节" if end_verse is None else (f"{book_name}{chapter}{unit}{start_verse}节" if start_verse==end_verse else f"{book_name}{chapter}{unit}{start_verse}-{end_verse}节")); self._set_adaptive_title(title_text); self._render_scripture(); self.set_scroll_position(0); self.update()
    def _set_adaptive_title(self,text):
        self._title_text=str(text or "")
        if not self._title_text:self.title_bar.clear(); return
        available_width=max(100,self.title_bar.width()-48); font_size=max(self.title_min_size,int(self.title_size)); font=QFont(self.title_font_family,font_size); font.setBold(True); fm=QFontMetrics(font)
        while fm.horizontalAdvance(self._title_text)>available_width and font_size>self.title_min_size: font_size-=1; font=QFont(self.title_font_family,font_size); font.setBold(True); fm=QFontMetrics(font)
        title_height=max(42,QFontMetrics(font).height()+6); self.title_bar.setMinimumHeight(title_height); self.title_bar.setMaximumHeight(title_height); self.title_bar.setFont(font); self.title_bar.setStyleSheet(f'color:{self.title_color.name()};font-family:"{self.title_font_family}";font-size:{font_size}px;font-weight:bold;background:transparent;padding:0 24px;'); self.title_bar.setText(self._title_text)
    def set_verse_segmentation(self,enabled): self.verse_segmentation=bool(enabled); self._render_scripture() if self.verses else None
    def _verse_html(self,n,t):
        safe=str(t).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"); return f'<span style="color:{self.verse_num_color.name()};font-size:{self.verse_num_size}px;font-family:&quot;{self.verse_num_font_family}&quot;;font-weight:bold;vertical-align:super;">{n}</span>&nbsp;<span style="color:{self.font_color.name()};font-size:{self.font_size}px;font-family:&quot;{self.font_family}&quot;;">{safe}</span>'
    def _render_scripture(self):
        top_pad=max(10,int(self.font_size*.35)); bottom_pad=self.footer_height+max(12,int(self.font_size*.45)); html=f"<div style='padding-top:{top_pad}px;padding-bottom:{bottom_pad}px;margin:0;line-height:{self.line_spacing}%;'>"
        if self.verse_segmentation:
            for n,t in self.verses: html+=f"<p style='margin:0 0 8px 0;padding:0;'>{self._verse_html(n,t)}</p>"
        else: html+="<p style='margin:0;padding:0;'>"+" ".join(self._verse_html(n,t) for n,t in self.verses)+"</p>"
        self.text_display.setHtml(html+"</div>"); self.text_display.document().setDocumentMargin(0); self._fit_document_width(); self.text_display.viewport().update()
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform,True); painter.fillRect(self.rect(),self.bg_color)
        if self.bg_image and os.path.exists(self.bg_image):
            pixmap=QPixmap(self.bg_image)
            if not pixmap.isNull(): scaled=pixmap.scaled(self.size(),Qt.AspectRatioMode.KeepAspectRatioByExpanding,Qt.TransformationMode.SmoothTransformation); painter.drawPixmap((self.width()-scaled.width())//2,(self.height()-scaled.height())//2,scaled)
        super().paintEvent(event); self._update_overlay_geometry()
    def _on_scrollbar_changed(self,value): self.scroll_changed.emit(value)
    def scroll_fraction(self):
        bar=self.text_display.verticalScrollBar(); maximum=bar.maximum(); return 0.0 if maximum<=0 else float(bar.value())/float(maximum)
    def set_scroll_fraction(self,fraction):
        bar=self.text_display.verticalScrollBar(); fraction=max(0.0,min(1.0,float(fraction))); self.set_scroll_position(round(fraction*bar.maximum()))
    def set_scroll_position(self,value):
        bar=self.text_display.verticalScrollBar(); value=max(bar.minimum(),min(int(value),bar.maximum())); bar.blockSignals(True); bar.setValue(value); bar.blockSignals(False)
    def _smooth_to(self,target,duration=120):
        bar=self.text_display.verticalScrollBar(); target=max(bar.minimum(),min(int(target),bar.maximum()));
        if self._scroll_anim:self._scroll_anim.stop()
        self._scroll_anim=QPropertyAnimation(bar,b"value",self); self._scroll_anim.setDuration(duration); self._scroll_anim.setStartValue(bar.value()); self._scroll_anim.setEndValue(target); self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic); self._scroll_anim.start()
    def set_scroll_speed(self,speed):
        self.scroll_speed=max(0,min(6,int(speed))); self.scroll_timer.stop() if self.scroll_speed==0 else self.scroll_timer.start()
    def _auto_scroll(self):
        bar=self.text_display.verticalScrollBar()
        if bar.value()<bar.maximum(): bar.setValue(min(bar.maximum(),bar.value()+self.scroll_speed))
        else:self.scroll_timer.stop()
    def scroll_by(self,delta):
        bar=self.text_display.verticalScrollBar(); self._smooth_to(max(bar.minimum(),min(bar.maximum(),bar.value()+int(delta))))
    def eventFilter(self,obj,event):
        if obj==self.text_display.viewport() and event.type()==event.Type.Wheel: self.scroll_by(-event.angleDelta().y()//6); return True
        return super().eventFilter(obj,event)
    def apply_settings(self,settings):
        for attr,key,conv in [("font_family","font_family",str),("font_size","font_size",int),("line_spacing","line_spacing",int),("title_size","title_size",int),("verse_num_size","verse_num_size",int),("footer_height","footer_height",int),("footer_size","footer_size",int)]:
            if key in settings:
                try:setattr(self,attr,conv(settings[key]))
                except:pass
        for attr,key in [("font_color","font_color"),("verse_num_color","verse_num_color"),("title_color","title_color"),("bg_color","bg_color"),("footer_color","footer_color")]:
            if key in settings:setattr(self,attr,QColor(settings[key]))
        self.bg_image=settings.get("bg_image",self.bg_image) or None; self.margin_left=self.margin_right=int(settings.get("margin",self.margin_left)); self.footer_text=settings.get("footer_text",self.footer_text); self.footer_label.setText(self.footer_text); self.footer_label.setFont(QFont(self.footer_font_family,self.footer_size)); self._update_viewport_margins(); self.set_verse_segmentation(bool(settings.get("verse_segmentation",False))); self.update()
    def _update_overlay_geometry(self): self.footer_label.setGeometry(0,max(0,self.height()-self.footer_height),self.width(),self.footer_height); self.title_bar.raise_(); self.footer_label.raise_()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if self._title_text:self._set_adaptive_title(self._title_text)
        self._update_viewport_margins(); self._fit_document_width(); self._update_overlay_geometry()