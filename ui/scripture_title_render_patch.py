"""经文小标题渲染兼容修复。

保持原经文显示核心代码不变，只修正 QTextDocument 对连续经文与多个小标题
混合排版时的 HTML 结构，避免多个标题只显示第一个。
"""

from .scripture_display import ScriptureDisplay


_ORIGINAL_RENDER_SCRIPTURE = ScriptureDisplay._render_scripture


def _title_inline_html(self, text):
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fs = self._px(self.title_size)
    spacing = self._px(self.title_spacing)
    return (
        f'<br><span style="color:{self.title_color.name()};font-size:{fs}px;'
        f'font-family:&quot;{self.title_font_family}&quot;;font-weight:bold;">{safe}</span>'
        f'<br><span style="font-size:{max(1, spacing)}px;">&nbsp;</span><br>'
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
        # 分节显示开启：每节独立成行，小标题放在对应节之前。
        for ch, n, t, titles in rows:
            for subtitle in titles:
                html += self._title_html(subtitle)
            html += self._verse_block_html(ch, n, t)
    else:
        # 分节显示关闭：整段经文保持连续，只在小标题锚点处换行。
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


ScriptureDisplay._render_scripture = _render_scripture_with_titles
