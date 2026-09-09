"""经文小标题兼容层。"""

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFormLayout,
    QFontComboBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QWidget,
    QColorDialog,
)

from .scripture_display import ScriptureDisplay, ScriptureBody
from .toolbar import DisplaySettingsDialog


_ORIGINAL_DISPLAY_INIT = ScriptureDisplay.__init__
_ORIGINAL_APPLY_SETTINGS = ScriptureDisplay.apply_settings
_ORIGINAL_RENDER_SCRIPTURE = ScriptureDisplay._render_scripture
_ORIGINAL_DISPLAY_AUTO_SCROLL = ScriptureDisplay._auto_scroll
_ORIGINAL_DIALOG_BUILD_UI = DisplaySettingsDialog._build_ui
_ORIGINAL_DIALOG_LOAD_SETTINGS = DisplaySettingsDialog._load_settings
_ORIGINAL_DIALOG_GET_SETTINGS = DisplaySettingsDialog.get_settings


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
    self.scripture_title_font_family = str(
        settings.get("scripture_title_font_family", self.scripture_title_font_family)
    )
    try:
        self.scripture_title_size = max(10, min(200, int(settings.get("scripture_title_size", 30))))
    except (TypeError, ValueError):
        self.scripture_title_size = 30

    color = QColor(str(settings.get("scripture_title_color", "#87CEEB")))
    self.scripture_title_color = color if color.isValid() else QColor("#87CEEB")

    try:
        self.scripture_title_spacing = max(0, min(100, int(settings.get("scripture_title_spacing", 8))))
    except (TypeError, ValueError):
        self.scripture_title_spacing = 8

    try:
        self.scripture_title_line_spacing = max(80, min(300, int(settings.get("scripture_title_line_spacing", 120))))
    except (TypeError, ValueError):
        self.scripture_title_line_spacing = 120

    if self.verses:
        old = self.scroll_fraction()
        self._render_scripture()
        self.set_scroll_fraction(old)


def _title_html(self, text):
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fs = self._px(self.scripture_title_size)
    spacing = self._px(self.scripture_title_spacing)
    line_spacing = int(self.scripture_title_line_spacing)
    return (
        f'<p style="margin:0 0 {spacing}px 0;padding:0;line-height:{line_spacing}%;">'
        f'<span style="color:{self.scripture_title_color.name()};font-size:{fs}px;'
        f'font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;">{safe}</span></p>'
    )


def _title_inline_html(self, text):
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    fs = self._px(self.scripture_title_size)
    line_spacing = int(self.scripture_title_line_spacing)
    # 连续经文模式只在小标题处换行，不再额外生成多个空行。
    # 间距用 1px 空白行控制，避免 QTextDocument 将原来的多重 <br> 放大成巨大空白。
    gap = max(1, self._px(self.scripture_title_spacing))
    return (
        f'<br><span style="color:{self.scripture_title_color.name()};font-size:{fs}px;'
        f'font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;'
        f'line-height:{line_spacing}%;">{safe}</span><br>'
        f'<span style="font-size:{gap}px;line-height:100%;">&#8203;</span>'
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


# ---------- 小标题独立设置：文字设置 -> 小标题 ----------

def _ensure_title_settings_widgets(self):
    if hasattr(self, "scripture_title_font_combo"):
        return
    tabs = self.findChild(QTabWidget, "settingsSubTabs")
    if tabs is None:
        return

    page = QWidget()
    form = QFormLayout(page)
    form.setContentsMargins(20, 20, 20, 20)
    form.setHorizontalSpacing(18)
    form.setVerticalSpacing(12)

    self.scripture_title_font_combo = QFontComboBox()
    self.scripture_title_size = QSpinBox()
    self.scripture_title_size.setRange(10, 200)
    self.scripture_title_size.setSuffix(" px")
    self.scripture_title_color_btn = QPushButton("小标题颜色")
    self.scripture_title_spacing = QSpinBox()
    self.scripture_title_spacing.setRange(0, 50)
    self.scripture_title_spacing.setSuffix(" px")
    self.scripture_title_line_spacing = QSpinBox()
    self.scripture_title_line_spacing.setRange(80, 300)
    self.scripture_title_line_spacing.setSuffix("%")

    form.addRow("小标题字体", self.scripture_title_font_combo)
    form.addRow("小标题字号", self.scripture_title_size)
    form.addRow("小标题颜色", self.scripture_title_color_btn)
    form.addRow("小标题间距", self.scripture_title_spacing)
    form.addRow("小标题行距", self.scripture_title_line_spacing)
    tabs.addTab(page, "小标题")
    self.scripture_title_color_btn.clicked.connect(self._choose_scripture_title_color)


def _dialog_build_ui(self):
    _ORIGINAL_DIALOG_BUILD_UI(self)
    _ensure_title_settings_widgets(self)


def _choose_scripture_title_color(self):
    current = str(self.settings.get("scripture_title_color", "#87CEEB"))
    color = QColorDialog.getColor(QColor(current), self, "选择小标题颜色")
    if color.isValid():
        self.settings["scripture_title_color"] = color.name()
        self.scripture_title_color_btn.setStyleSheet(
            f"background:{color.name()};color:{'#000000' if color.lightness() > 160 else '#FFFFFF'};"
        )


def _dialog_load_settings(self):
    _ORIGINAL_DIALOG_LOAD_SETTINGS(self)
    _ensure_title_settings_widgets(self)
    if not hasattr(self, "scripture_title_font_combo"):
        return
    s = self.settings
    self.scripture_title_font_combo.setCurrentFont(QFont(s.get("scripture_title_font_family", "微软雅黑")))
    self.scripture_title_size.setValue(int(s.get("scripture_title_size", 30)))
    self.scripture_title_spacing.setValue(int(s.get("scripture_title_spacing", 8)))
    self.scripture_title_line_spacing.setValue(int(s.get("scripture_title_line_spacing", 120)))
    color = QColor(str(s.get("scripture_title_color", "#87CEEB")))
    if not color.isValid():
        color = QColor("#87CEEB")
    self.scripture_title_color_btn.setStyleSheet(
        f"background:{color.name()};color:{'#000000' if color.lightness() > 160 else '#FFFFFF'};"
    )


def _dialog_get_settings(self):
    s = _ORIGINAL_DIALOG_GET_SETTINGS(self)
    if not hasattr(self, "scripture_title_font_combo"):
        return s
    s.update({
        "scripture_title_font_family": self.scripture_title_font_combo.currentFont().family(),
        "scripture_title_size": self.scripture_title_size.value(),
        "scripture_title_color": str(self.settings.get("scripture_title_color", "#87CEEB")),
        "scripture_title_spacing": self.scripture_title_spacing.value(),
        "scripture_title_line_spacing": self.scripture_title_line_spacing.value(),
    })
    return s


ScriptureDisplay.__init__ = _display_init
ScriptureDisplay.apply_settings = _apply_display_settings
ScriptureDisplay._title_html = _title_html
ScriptureDisplay._title_inline_html = _title_inline_html
ScriptureDisplay._render_scripture = _render_scripture_with_titles
ScriptureDisplay._auto_scroll = _display_auto_scroll

DisplaySettingsDialog._build_ui = _dialog_build_ui
DisplaySettingsDialog._load_settings = _dialog_load_settings
DisplaySettingsDialog.get_settings = _dialog_get_settings
DisplaySettingsDialog._choose_scripture_title_color = _choose_scripture_title_color
