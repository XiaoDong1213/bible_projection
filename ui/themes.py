"""Bible Pro 统一设计令牌与样式表。

风格：极简专业控制台（Minimal Control Console）
- 单一冷蓝强调色，亮/暗共用同一套层级与圆角
- 避免搜索框/历史/工具栏各自一套视觉语言
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

RADIUS = {
    "sm": 6,
    "md": 8,
    "lg": 12,
}

SPACE = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
}

FONT_FAMILY = '"Microsoft YaHei UI", "微软雅黑", "Segoe UI", sans-serif'

THEMES = {
    "dark": {
        "name": "dark",
        "canvas": "#0B0E14",
        "surface": "#12161E",
        "surface_raised": "#181D27",
        "surface_sunken": "#0E1218",
        "control": "#1F2633",
        "control_hover": "#283142",
        "control_pressed": "#171C26",
        "border": "#2A3344",
        "border_strong": "#3A4558",
        "text": "#E8EDF5",
        "text_muted": "#93A0B4",
        "text_faint": "#6B778C",
        "accent": "#3B82F6",
        "accent_hover": "#2563EB",
        "accent_pressed": "#1D4ED8",
        "accent_soft": "#1A2F4A",
        "accent_text": "#DBEAFE",
        "danger": "#EF4444",
        "danger_hover": "#DC2626",
        "danger_soft": "#3F1D1D",
        "danger_text": "#FCA5A5",
        "success": "#22C55E",
        "preview_bg": "#07090D",
        "scroll": "#3A4558",
        "scroll_hover": "#4B5568",
        "focus_ring": "#3B82F6",
        # 兼容旧字段名
        "window_bg": "#0B0E14",
        "toolbar_bg": "#12161E",
        "panel_bg": "#181D27",
        "item_bg": "#1F2633",
        "item_hover": "#283142",
        "text_primary": "#E8EDF5",
        "text_secondary": "#93A0B4",
        "accent_hover_legacy": "#2563EB",
    },
    "light": {
        "name": "light",
        "canvas": "#E8ECF2",
        "surface": "#FFFFFF",
        "surface_raised": "#FFFFFF",
        "surface_sunken": "#F3F5F9",
        "control": "#F1F4F8",
        "control_hover": "#E5EAF1",
        "control_pressed": "#D8DEE8",
        "border": "#D5DCE6",
        "border_strong": "#B8C2D0",
        "text": "#0F172A",
        "text_muted": "#475569",
        "text_faint": "#64748B",
        "accent": "#2563EB",
        "accent_hover": "#1D4ED8",
        "accent_pressed": "#1E40AF",
        "accent_soft": "#DBEAFE",
        "accent_text": "#1E3A8A",
        "danger": "#DC2626",
        "danger_hover": "#B91C1C",
        "danger_soft": "#FEF2F2",
        "danger_text": "#B91C1C",
        "success": "#16A34A",
        "preview_bg": "#0B0D10",
        "scroll": "#C5CDD9",
        "scroll_hover": "#94A3B8",
        "focus_ring": "#2563EB",
        "window_bg": "#E8ECF2",
        "toolbar_bg": "#FFFFFF",
        "panel_bg": "#FFFFFF",
        "item_bg": "#F1F4F8",
        "item_hover": "#E5EAF1",
        "text_primary": "#0F172A",
        "text_secondary": "#475569",
        "accent_hover_legacy": "#1D4ED8",
    },
}


def theme_tokens(name: str = "dark") -> dict:
    """返回主题令牌字典。"""
    return THEMES.get(name, THEMES["dark"])


def search_panel_style(name: str = "dark") -> str:
    """搜索弹层样式：与主界面共用同一套令牌，不再单独走毛玻璃。"""
    t = theme_tokens(name)
    r = RADIUS
    return f"""
    QWidget#searchPanel {{
        background: {t['surface_raised']};
        border: 1px solid {t['border']};
        border-radius: {r['lg']}px;
    }}
    QLineEdit#searchInput {{
        background: {t['control']};
        color: {t['text']};
        border: 1px solid {t['border']};
        border-radius: {r['md']}px;
        padding: 0 16px;
        font-size: 15px;
        min-height: 48px;
        selection-background-color: {t['accent']};
        selection-color: #FFFFFF;
    }}
    QLineEdit#searchInput:focus {{
        border: 2px solid {t['focus_ring']};
        padding: 0 15px;
    }}
    QLabel#searchHint {{
        background: transparent;
        color: {t['text_muted']};
        border: none;
        padding: 6px 4px 2px 4px;
        font-size: 12px;
    }}
    QListWidget#searchCandidates {{
        background: transparent;
        color: {t['text']};
        border: none;
        padding: 6px 0 0 0;
        outline: none;
    }}
    QListWidget#searchCandidates::item {{
        background: {t['control']};
        color: {t['text']};
        border: 1px solid {t['border']};
        border-radius: {r['md']}px;
        padding: 8px 14px;
        min-height: 28px;
        margin: 2px 0;
    }}
    QListWidget#searchCandidates::item:hover {{
        background: {t['control_hover']};
        border-color: {t['border_strong']};
    }}
    QListWidget#searchCandidates::item:selected {{
        background: {t['accent_soft']};
        color: {t['accent_text']};
        border: 1px solid {t['accent']};
    }}
    """


def build_stylesheet(name: str = "dark", styles_dir: str | Path | None = None) -> str:
    """生成完整应用 QSS。"""
    t = theme_tokens(name)
    r = RADIUS
    styles_dir = Path(styles_dir) if styles_dir else Path(__file__).resolve().parent.parent / "styles"
    suffix = "dark" if name == "dark" else "light"
    # 使用正斜杠，避免 QSS url 在 Windows 上转义问题
    arrow_up = (styles_dir / f"arrow-up-{suffix}.svg").as_posix()
    arrow_down_spin = (styles_dir / f"arrow-down-spin-{suffix}.svg").as_posix()
    arrow_down = (styles_dir / f"arrow-down-{suffix}.svg").as_posix()

    return f"""
/* Bible Pro — unified {name} theme */
* {{
    font-family: {FONT_FAMILY};
}}

QMainWindow, QDialog {{
    background: {t['canvas']};
    color: {t['text']};
    font-size: 13px;
}}

QLabel {{
    color: {t['text']};
    background: transparent;
}}

QDialog QLabel {{
    color: {t['text']};
}}

QStatusBar {{
    background: {t['surface']};
    color: {t['text_muted']};
    border-top: 1px solid {t['border']};
    min-height: 28px;
}}
QStatusBar QLabel {{
    color: {t['text_muted']};
    padding-left: 10px;
}}

/* ---------- Toolbar ---------- */
QToolBar {{
    background: {t['surface']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 10px 14px;
    spacing: 8px;
}}
QToolBar QLabel {{
    color: {t['text_muted']};
    font-size: 12px;
    padding: 0 4px;
}}
QToolBar QPushButton {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 7px 12px;
    font-size: 12px;
    min-height: 30px;
}}
QToolBar QPushButton#speedBtn {{
    padding: 6px 10px;
    min-width: 40px;
}}
QToolBar QPushButton:hover {{
    background: {t['control_hover']};
    border-color: {t['accent']};
}}
QToolBar QPushButton:pressed {{
    background: {t['control_pressed']};
}}
QToolBar QPushButton:disabled {{
    background: {t['surface_sunken']};
    color: {t['text_faint']};
    border-color: {t['border']};
}}
QToolBar QPushButton:checked {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}
QToolBar QComboBox {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 6px 10px;
    min-width: 88px;
    min-height: 30px;
}}
QToolBar QComboBox:hover {{
    border-color: {t['accent']};
}}
QToolBar QComboBox::drop-down {{
    border: none;
    width: 32px;
}}
QToolBar QComboBox QAbstractItemView {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    selection-background-color: {t['accent']};
    selection-color: #FFFFFF;
    outline: none;
}}

#extendBtn {{
    background: {t['accent']};
    color: #FFFFFF;
    border: 1px solid {t['accent']};
    font-weight: 600;
    padding: 7px 16px;
}}
#extendBtn:hover {{
    background: {t['accent_hover']};
    border-color: {t['accent_hover']};
}}
#extendBtn:pressed {{
    background: {t['accent_pressed']};
}}
#topmostBtn {{
    min-width: 52px;
}}
#themeBtn, #settingsBtn {{
    background: {t['control']};
}}

/* ---------- Navigation ---------- */
#navPanel {{
    background: {t['surface_raised']};
    border-right: 1px solid {t['border']};
}}
#navPanel QLabel {{
    color: {t['text_muted']};
    font-size: 12px;
}}
#navPanel QLabel#fieldLabel {{
    font-size: 11px;
    color: {t['text_muted']};
}}
#navPanel QLabel#rowTitle {{
    font-size: 12px;
    color: {t['text']};
    font-weight: 600;
}}
#bookGrid, #bookGridInner {{
    background: {t['surface_raised']};
    border: none;
}}
#bookBtn {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 8px 10px;
    font-size: 13px;
    text-align: center;
    min-height: 38px;
}}
#bookBtn:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
}}
#bookBtn:checked {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}

QTabWidget::pane {{
    border: none;
    background: {t['surface_raised']};
    top: -1px;
}}
QTabBar {{
    qproperty-drawBase: false;
    min-height: 42px;
    background: {t['surface']};
}}
QTabBar::tab {{
    background: transparent;
    color: {t['text_muted']};
    padding: 11px 6px;
    font-size: 12px;
    border: none;
    border-bottom: 2px solid transparent;
    margin: 0;
    min-width: 48px;
    min-height: 36px;
}}
QTabBar::tab:hover {{
    color: {t['text']};
    background: transparent;
}}
QTabBar::tab:selected {{
    color: {t['accent']};
    background: transparent;
    border-bottom: 2px solid {t['accent']};
    font-weight: 600;
}}

QListWidget {{
    background: {t['surface_raised']};
    border: none;
    color: {t['text']};
    font-size: 13px;
    outline: none;
}}
QListWidget::item {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid transparent;
    border-radius: {r['sm']}px;
    padding: 6px 8px;
    margin: 2px;
}}
QListWidget::item:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
}}
QListWidget::item:selected {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}

#historyList, #historyListInner {{
    background: transparent;
    border: none;
}}
#historyItem {{
    background: {t['control']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
}}
#historyItem:hover {{
    background: {t['control_hover']};
    border-color: {t['border_strong']};
}}
#historyItem[selected="true"] {{
    background: {t['accent_soft']};
    border: 1px solid {t['accent']};
}}
#historyText {{
    font-size: 13px;
    color: {t['text']};
    background: transparent;
}}
#historyDeleteButton {{
    background: transparent;
    color: {t['text_muted']};
    border: 1px solid {t['border_strong']};
    border-radius: {r['sm']}px;
    font-size: 12px;
    padding: 0;
}}
#historyDeleteButton:hover {{
    background: {t['danger']};
    color: #FFFFFF;
    border: 1px solid {t['danger']};
}}
#historyDeleteButton:pressed {{
    background: {t['danger_hover']};
    color: #FFFFFF;
}}

/* ---------- Forms ---------- */
QSpinBox {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 5px 8px;
    min-height: 28px;
    font-size: 13px;
}}
QSpinBox:hover {{
    border-color: {t['border_strong']};
}}
QSpinBox:focus {{
    border-color: {t['focus_ring']};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background: {t['control_hover']};
    border: none;
    width: 20px;
}}
QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
}}
QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {t['border_strong']};
}}
QSpinBox::up-arrow {{
    image: url({arrow_up});
    width: 10px;
    height: 6px;
}}
QSpinBox::down-arrow {{
    image: url({arrow_down_spin});
    width: 10px;
    height: 6px;
}}

#rangeBox {{
    background: {t['surface']};
    border-top: 1px solid {t['border']};
}}
#modeBar {{
    background: transparent;
    border: none;
    border-bottom: 1px solid {t['border']};
}}
#modeBtn {{
    background: transparent;
    color: {t['text_muted']};
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    padding: 6px 4px 8px 4px;
    font-size: 12px;
    min-height: 28px;
}}
#modeBtn:hover {{
    color: {t['text']};
    background: transparent;
}}
#modeBtn:checked {{
    color: {t['accent']};
    background: transparent;
    border-bottom: 2px solid {t['accent']};
    font-weight: 600;
}}
#modeBtn:focus {{
    border-bottom: 2px solid {t['focus_ring']};
}}
#fieldLabel {{
    color: {t['text_muted']};
    font-size: 12px;
    background: transparent;
    padding: 0;
}}
#rowTitle {{
    color: {t['text_muted']};
    font-size: 12px;
    font-weight: 600;
    background: transparent;
}}
#navHint {{
    color: {t['text_faint']};
    font-size: 11px;
    background: transparent;
    padding: 0;
}}
#rangeBox QSpinBox#rangeSpin {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 2px 4px;
    min-height: 26px;
    max-height: 28px;
    font-size: 13px;
}}
#rangeBox QSpinBox#rangeSpin:focus {{
    border-color: {t['focus_ring']};
}}
#rangeBox QSpinBox#rangeSpin::up-button,
#rangeBox QSpinBox#rangeSpin::down-button {{
    background: transparent;
    border: none;
    width: 14px;
}}
#rangeBox QSpinBox#rangeSpin::up-arrow {{
    image: url({arrow_up});
    width: 8px;
    height: 5px;
}}
#rangeBox QSpinBox#rangeSpin::down-arrow {{
    image: url({arrow_down_spin});
    width: 8px;
    height: 5px;
}}
#skipVerseEdit {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 28px;
}}
#skipVerseEdit:focus {{
    border-color: {t['focus_ring']};
}}
#selectRangeBtn {{
    background: {t['accent']};
    color: #FFFFFF;
    border: none;
    border-radius: {r['sm']}px;
    padding: 8px 12px;
    font-weight: 600;
    font-size: 13px;
    min-height: 34px;
}}
#selectRangeBtn:hover {{
    background: {t['accent_hover']};
}}
#selectRangeBtn:pressed {{
    background: {t['accent_pressed']};
}}
#segmentBtn {{
    background: transparent;
    color: {t['text_muted']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 6px 8px;
    text-align: center;
    font-size: 12px;
    min-height: 34px;
}}
#segmentBtn:hover {{
    border-color: {t['border_strong']};
    color: {t['text']};
}}
#segmentBtn:checked {{
    background: {t['accent_soft']};
    color: {t['accent_text']};
    border-color: {t['accent']};
}}
#clearHistoryBtn {{
    background: transparent;
    color: {t['text_muted']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 8px;
    margin: 4px;
}}
#clearHistoryBtn:hover {{
    background: {t['danger_soft']};
    color: {t['danger_text']};
    border-color: {t['danger']};
}}

QPushButton {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 7px 14px;
    font-size: 12px;
    min-height: 28px;
}}
QPushButton:hover {{
    background: {t['control_hover']};
    border-color: {t['accent']};
}}
QPushButton:pressed {{
    background: {t['control_pressed']};
}}
QPushButton:disabled {{
    color: {t['text_faint']};
    background: {t['surface_sunken']};
}}
QPushButton:focus {{
    border-color: {t['focus_ring']};
}}

QDialogButtonBox QPushButton {{
    min-width: 88px;
    min-height: 32px;
}}

QGroupBox {{
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    margin-top: 12px;
    padding-top: 14px;
    font-weight: 600;
    background: {t['surface_raised']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {t['text_muted']};
}}

QComboBox, QFontComboBox {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 5px 8px;
    min-height: 28px;
}}
QComboBox:hover, QFontComboBox:hover {{
    border-color: {t['border_strong']};
}}
QComboBox:focus, QFontComboBox:focus {{
    border-color: {t['focus_ring']};
}}
QComboBox QAbstractItemView, QFontComboBox QAbstractItemView {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    selection-background-color: {t['accent']};
    selection-color: #FFFFFF;
}}
QComboBox::drop-down, QFontComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 32px;
    border: none;
}}
QComboBox::down-arrow, QFontComboBox::down-arrow {{
    image: url({arrow_down});
    width: 12px;
    height: 8px;
}}

QLineEdit {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['sm']}px;
    padding: 7px 10px;
    font-size: 13px;
    min-width: 0;
}}
QLineEdit:focus {{
    border-color: {t['focus_ring']};
}}

/* 搜索输入框默认跟随主题；弹层自身还会再套一层 search_panel_style */
#searchInput {{
    background: {t['control']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    padding: 10px 14px;
    font-size: 15px;
}}
#searchInput:focus {{
    border-color: {t['focus_ring']};
}}

/* ---------- Preview ---------- */
#previewHost {{
    background: {t['canvas']};
}}
#previewView {{
    background: {t['preview_bg']};
    border: none;
}}

QSplitter::handle {{
    background: {t['border']};
    width: 1px;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['scroll']};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {t['scroll_hover']};
}}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    height: 0;
    background: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {t['scroll']};
    border-radius: 5px;
    min-width: 28px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {t['scroll_hover']};
}}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {{
    width: 0;
    background: none;
}}

QToolTip {{
    background: {t['surface_raised']};
    color: {t['text']};
    border: 1px solid {t['border']};
    padding: 6px 8px;
    border-radius: {r['sm']}px;
}}
"""


def write_qss_files(styles_dir: str | Path | None = None) -> None:
    """把生成结果同步写回 styles/*.qss，便于打包与手工查看。"""
    styles_dir = Path(styles_dir) if styles_dir else Path(__file__).resolve().parent.parent / "styles"
    styles_dir.mkdir(parents=True, exist_ok=True)
    for name in ("dark", "light"):
        (styles_dir / f"{name}.qss").write_text(
            build_stylesheet(name, styles_dir),
            encoding="utf-8",
        )
