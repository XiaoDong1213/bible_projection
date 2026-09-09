"""经文小标题渲染与独立样式兼容层。"""

from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QFormLayout, QFontComboBox, QPushButton, QSpinBox, QTabWidget, QWidget, QColorDialog

from .scripture_display import ScriptureDisplay
from .toolbar import DisplaySettingsDialog
from config import AppConfig
import ui.themes as _themes

# Qt QSS 的 font-family 使用单一字体名更稳定；原来的 CSS fallback 列表会在部分 Qt 版本触发样式解析警告。
_themes.FONT_FAMILY = '"Microsoft YaHei UI"'


def _color_name(value, fallback="#87CEEB"):
    if isinstance(value, QColor):
        return value.name() if value.isValid() else fallback
    color = QColor(str(value or fallback))
    return color.name() if color.isValid() else fallback


_ORIGINAL_DISPLAY_INIT = ScriptureDisplay.__init__
_ORIGINAL_APPLY_SETTINGS = ScriptureDisplay.apply_settings
_ORIGINAL_RENDER_SCRIPTURE = ScriptureDisplay._render_scripture


def _display_init(self, parent=None):
    _ORIGINAL_DISPLAY_INIT(self, parent)
    self.scripture_title_font_family = "微软雅黑"
    self.scripture_title_size = 30
    self.scripture_title_color = QColor("#87CEEB")
    self.scripture_title_spacing = 8
    self.scripture_title_line_spacing = 120


def _apply_display_settings(self, settings):
    _ORIGINAL_APPLY_SETTINGS(self, settings)
    self.scripture_title_font_family = settings.get("scripture_title_font_family", self.scripture_title_font_family)
    self.scripture_title_size = int(settings.get("scripture_title_size", self.scripture_title_size))
    self.scripture_title_color = QColor(_color_name(settings.get("scripture_title_color", self.scripture_title_color.name())))
    self.scripture_title_spacing = int(settings.get("scripture_title_spacing", self.scripture_title_spacing))
    self.scripture_title_line_spacing = int(settings.get("scripture_title_line_spacing", self.scripture_title_line_spacing))
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
    spacing = self._px(self.scripture_title_spacing)
    line_spacing = int(self.scripture_title_line_spacing)
    return (
        f'<br><span style="color:{self.scripture_title_color.name()};font-size:{fs}px;'
        f'font-family:&quot;{self.scripture_title_font_family}&quot;;font-weight:bold;line-height:{line_spacing}%;">{safe}</span>'
        f'<br><span style="font-size:{max(1, spacing)}px;">&nbsp;</span><br>'
    )


def _render_scripture_with_titles(self):
    if not self.show_scripture_titles:
        _ORIGINAL_RENDER_SCRIPTURE(self)
        return
    fs = self._px(self.font_size)
    top = max(10, int(fs * 0.35))
    bottom = max(12, int(fs * 0.45))
    html = f"<div style='padding-top:{top}px;padding-bottom:{bottom}px;margin:0;line-height:{self.line_spacing}%;text-align:justify;'>"
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


ScriptureDisplay.__init__ = _display_init
ScriptureDisplay.apply_settings = _apply_display_settings
ScriptureDisplay._title_html = _title_html
ScriptureDisplay._title_inline_html = _title_inline_html
ScriptureDisplay._render_scripture = _render_scripture_with_titles


_ORIGINAL_DIALOG_BUILD_UI = DisplaySettingsDialog._build_ui
_ORIGINAL_DIALOG_LOAD_SETTINGS = DisplaySettingsDialog._load_settings
_ORIGINAL_DIALOG_GET_SETTINGS = DisplaySettingsDialog.get_settings


def _add_scripture_title_settings(self):
    tabs = self.findChild(QTabWidget, "settingsSubTabs")
    if tabs is None or hasattr(self, "scripture_title_font_combo"):
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
    self.scripture_title_spacing.setRange(0, 100)
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
    _add_scripture_title_settings(self)


def _choose_scripture_title_color(self):
    current = _color_name(self.settings.get("scripture_title_color", "#87CEEB"))
    color = QColorDialog.getColor(QColor(current), self, "选择小标题颜色")
    if color.isValid():
        self.settings["scripture_title_color"] = color.name()
        self._set_color_button(self.scripture_title_color_btn, color.name())


def _dialog_set_color_button(self, button, color):
    color_name = _color_name(color)
    text_color = "#000000" if QColor(color_name).lightness() > 160 else "#FFFFFF"
    button.setStyleSheet(f"background-color:{color_name};color:{text_color};border:1px solid #6B7280;")


def _dialog_load_settings(self):
    _ORIGINAL_DIALOG_LOAD_SETTINGS(self)
    s = self.settings
    self.scripture_title_font_combo.setCurrentFont(QFont(s.get("scripture_title_font_family", "微软雅黑")))
    self.scripture_title_size.setValue(int(s.get("scripture_title_size", 30)))
    self.scripture_title_spacing.setValue(int(s.get("scripture_title_spacing", 8)))
    self.scripture_title_line_spacing.setValue(int(s.get("scripture_title_line_spacing", 120)))
    color = _color_name(s.get("scripture_title_color", "#87CEEB"))
    self.scripture_title_color_btn.setStyleSheet(f"background-color:{color};color:{'#000000' if QColor(color).lightness() > 160 else '#FFFFFF'};border:1px solid #6B7280;")


def _dialog_get_settings(self):
    s = _ORIGINAL_DIALOG_GET_SETTINGS(self)
    s.update({
        "scripture_title_font_family": self.scripture_title_font_combo.currentFont().family(),
        "scripture_title_size": self.scripture_title_size.value(),
        "scripture_title_color": _color_name(self.settings.get("scripture_title_color", "#87CEEB")),
        "scripture_title_spacing": self.scripture_title_spacing.value(),
        "scripture_title_line_spacing": self.scripture_title_line_spacing.value(),
    })
    return s


DisplaySettingsDialog._build_ui = _dialog_build_ui
DisplaySettingsDialog._set_color_button = _dialog_set_color_button
DisplaySettingsDialog._load_settings = _dialog_load_settings
DisplaySettingsDialog.get_settings = _dialog_get_settings


_ORIGINAL_CONFIG_LOAD = AppConfig.load_display_settings


def _config_load_display_settings(self):
    result = _ORIGINAL_CONFIG_LOAD(self)
    sec = self.parser["Display"] if "Display" in self.parser else {}
    result["scripture_title_font_family"] = sec.get("scripture_title_font_family", "微软雅黑")
    try:
        result["scripture_title_size"] = int(sec.get("scripture_title_size", "30"))
    except ValueError:
        result["scripture_title_size"] = 30
    result["scripture_title_color"] = QColor(sec.get("scripture_title_color", "#87CEEB"))
    try:
        result["scripture_title_spacing"] = int(sec.get("scripture_title_spacing", "8"))
    except ValueError:
        result["scripture_title_spacing"] = 8
    try:
        result["scripture_title_line_spacing"] = int(sec.get("scripture_title_line_spacing", "120"))
    except ValueError:
        result["scripture_title_line_spacing"] = 120
    return result


AppConfig.load_display_settings = _config_load_display_settings
