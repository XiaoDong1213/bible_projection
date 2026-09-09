"""经文小标题渲染兼容层。

只负责小标题显示和滚动接口兼容，不再动态改写显示设置对话框。
显示设置对话框保持 toolbar.py 的原始实现，避免运行时 monkey patch 引发崩溃。
"""

from PyQt6.QtGui import QColor

from .scripture_display import ScriptureDisplay, ScriptureBody


_ORIGINAL_DISPLAY_INIT = ScriptureDisplay.__init__
_ORIGINAL_APPLY_SETTINGS = ScriptureDisplay.apply_settings
_ORIGINAL_RENDER_SCRIPTURE = ScriptureDisplay._render_scripture
_ORIGINAL_DISPLAY_AUTO_SCROLL = ScriptureDisplay._auto_scroll


def _body_clamp_scroll(self):
    """兼容正文区边距更新时使用的滚动边界校正接口。"""
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


# 保留 ScriptureBody 原有调用链所需要的三个接口。
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

    # 这些设置没有时使用稳定默认值；即使旧 config.ini 没有对应字段也不会报错。
    self.scripture_title_font_family = str(
        settings.get("scripture_title_font_family", self.scripture_title_font_family)
    )
    try:
        self.scripture_title_size = max(
            10, min(200, int(settings.get("scripture_title_size", self.scripture_title_size)))
        )
    except (TypeError, ValueError):
        self.scripture_title_size = 30

    self.scripture_title_color = QColor(
        str(settings.get("scripture_title_color", self.scripture_title_color.name()))
    )
    if not self.scripture_title_color.isValid():
        self.scripture_title_color = QColor("#87CEEB")

    try:
        self.scripture_title_spacing = max(
            0, min(100, int(settings.get("scripture_title_spacing", self.scripture_title_spacing)))
        )
    except (TypeError, ValueError):
        self.scripture_title_spacing = 8

    try:
        self.scripture_title_line_spacing = max(
            80, min(300, int(settings.get("scripture_title_line_spacing", self.scripture_title_line_spacing)))
        )
    except (TypeError, ValueError):
        self.scripture_title_line_spacing = 120

    if self.verses:
        old = self.scroll_fraction()
        self._render_scripture()
        self.set_scroll_fraction(old)


def _title_html(self, text):
    safe = (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    fs = self._px(self.scripture_title_size)
    spacing = self._px(self.scripture_title_spacing)
    line_spacing = int(self.scripture_title_line_spacing)
    return (
        f'<p style="margin:0 0 {spacing}px 0;padding:0;line-height:{line_spacing}%;">'
        f'<span style="color:{self.scripture_title_color.name()};font-size:{fs}px;'
        f'font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;">'
        f'{safe}</span></p>'
    )


def _title_inline_html(self, text):
    safe = (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    fs = self._px(self.scripture_title_size)
    spacing = self._px(self.scripture_title_spacing)
    line_spacing = int(self.scripture_title_line_spacing)
    return (
        f'<br><span style="color:{self.scripture_title_color.name()};font-size:{fs}px;'
        f'font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;'
        f'line-height:{line_spacing}%;">{safe}</span>'
        f'<br><span style="font-size:{max(1, spacing)}px;">&nbsp;</span><br>'
    )


def _render_scripture_with_titles(self):
    # 开关关闭：完全走原来的渲染逻辑，不改变原有分节/连续显示行为。
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
        # 分节显示开启：每节独立显示，小标题出现在对应节之前。
        for ch, n, t, titles in rows:
            for subtitle in titles:
                html += self._title_html(subtitle)
            html += self._verse_block_html(ch, n, t)
    else:
        # 分节显示关闭：正文继续连续排版，只有遇到小标题时才换行。
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


ScriptureDisplay.__init__ = _display_init
ScriptureDisplay.apply_settings = _apply_display_settings
ScriptureDisplay._title_html = _title_html
ScriptureDisplay._title_inline_html = _title_inline_html
ScriptureDisplay._render_scripture = _render_scripture_with_titles
ScriptureDisplay._auto_scroll = _display_auto_scroll
