"""经文小标题渲染兼容层。"""

from PyQt6.QtGui import QColor
from .scripture_display import ScriptureDisplay, ScriptureBody
from .toolbar import DisplaySettingsDialog


_ORIGINAL_DISPLAY_INIT = ScriptureDisplay.__init__
_ORIGINAL_APPLY_SETTINGS = ScriptureDisplay.apply_settings
_ORIGINAL_RENDER_SCRIPTURE = ScriptureDisplay._render_scripture
_ORIGINAL_DISPLAY_AUTO_SCROLL = ScriptureDisplay._auto_scroll
_ORIGINAL_DIALOG_BUILD_UI = DisplaySettingsDialog._build_ui


def _body_clamp_scroll(self):
    self.set_scroll_y(self._scroll_y, emit=False)


def _body_scroll_fraction(self):
    maximum = self.max_scroll()
    return 0.0 if maximum <= 0 else self._scroll_y / maximum


def _body_set_scroll_fraction(self, fraction):
    try:
        value = max(0.0, min(1.0, float(fraction)))
    except (TypeError, ValueError):
        return
    self.set_scroll_y(value * self.max_scroll())


ScriptureBody._clamp_scroll = _body_clamp_scroll
ScriptureBody.scroll_fraction = _body_scroll_fraction
ScriptureBody.set_scroll_fraction = _body_set_scroll_fraction


def _display_init(self, parent=None):
    _ORIGINAL_DISPLAY_INIT(self, parent)
    self.scripture_title_font_family = "微软雅黑"
    self.scripture_title_size = 30
    self.scripture_title_color = QColor("#87CEEB")
    self.scripture_title_spacing = 8
    self.scripture_title_line_spacing = 120


def _apply_display_settings(self, settings):
    _ORIGINAL_APPLY_SETTINGS(self, settings)
    self.scripture_title_font_family = str(settings.get("scripture_title_font_family", self.scripture_title_font_family))
    try:
        self.scripture_title_size = max(10, min(200, int(settings.get("scripture_title_size", 30))))
    except (TypeError, ValueError):
        self.scripture_title_size = 30

    color = QColor(str(settings.get("scripture_title_color", "#87CEEB")))
    self.scripture_title_color = color if color.isValid() else QColor("#87CEEB")

    if self.verses:
        old = self.scroll_fraction()
        self._render_scripture()
        self.set_scroll_fraction(old)


def _title_html(self, text):
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fs = self._px(self.scripture_title_size)
    return (
        '<p style="margin:0 0 8px 0;padding:0;line-height:%s%%;">'
        '<span style="color:%s;font-size:%spx;font-family:&quot;%s&quot;;font-weight:bold;">%s</span></p>'
        % (self.line_spacing, self.scripture_title_color.name(), fs, self.scripture_title_font_family, safe)
    )


def _title_inline_html(self, text):
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fs = self._px(self.scripture_title_size)
    return (
        '<br><span style="color:%s;font-size:%spx;font-family:&quot;%s&quot;;font-weight:bold;">%s</span><br>'
        % (self.scripture_title_color.name(), fs, self.scripture_title_font_family, safe)
    )


def _render_scripture_with_titles(self):
    if not self.show_scripture_titles:
        _ORIGINAL_RENDER_SCRIPTURE(self)
        return

    fs = self._px(self.font_size)
    top = max(10, int(fs * 0.35))
    bottom = max(12, int(fs * 0.45))
    html = (
        f"<div style='padding-top:{top}px;padding-bottom:{bottom}px;margin:0;"
        f"line-height:{self.line_spacing}%;text-align:justify;'>"
    )
    rows = [self._verse_row(row) for row in self.verses]

    if self.verse_segmentation:
        for ch, n, t, titles in rows:
            for subtitle in titles:
                html += self._title_html(subtitle)
            html += self._verse_block_html(ch, n, t)
    else:
        html += "<p style='margin:0;padding:0;white-space:normal;text-align:justify;'>"
        has_content = False
        for ch, n, t, titles in rows:
            for subtitle in titles:
                if has_content:
                    html += "<br>"
                html += self._title_inline_html(subtitle)
                has_content = True
            html += self._verse_html(ch, n, t)
            html += " "
            has_content = True
        html += "</p>"

    self.text_display.set_html(html + "</div>")
    self._fit_document_width()


def _display_auto_scroll(self):
    was_running = self.scroll_timer.isActive()
    _ORIGINAL_DISPLAY_AUTO_SCROLL(self)
    if was_running and self.scroll_speed == 0 and self.max_scroll() > 0:
        if self.scroll_position() >= self.max_scroll() - 0.5:
            self.scroll_finished.emit()


def _dialog_build_ui(self):
    _ORIGINAL_DIALOG_BUILD_UI(self)
    # 标题间距不作为用户设置项，但保留控件实例以兼容旧配置读取。
    spacing = getattr(self, "title_spacing", None)
    if spacing is not None:
        spacing.hide()
        parent = spacing.parentWidget()
        if parent is not None:
            layout = parent.layout()
            if layout is not None and hasattr(layout, "labelForField"):
                label = layout.labelForField(spacing)
                if label is not None:
                    label.hide()


ScriptureDisplay.__init__ = _display_init
ScriptureDisplay.apply_settings = _apply_display_settings
ScriptureDisplay._title_html = _title_html
ScriptureDisplay._title_inline_html = _title_inline_html
ScriptureDisplay._render_scripture = _render_scripture_with_titles
ScriptureDisplay._auto_scroll = _display_auto_scroll

# 不再覆盖 DisplaySettingsDialog 的颜色样式，直接使用 toolbar.py 原有实现。
DisplaySettingsDialog._build_ui = _dialog_build_ui
