"""统一管理亮色和暗色界面的主题配色。"""

# 深色主题：突出经文内容和主要操作
THEMES = {
    "dark": {
        "window_bg": "#0F1115",
        "toolbar_bg": "#161A22",
        "panel_bg": "#1C212B",
        "item_bg": "#242B38",
        "item_hover": "#2C3545",
        "text_primary": "#E8EAED",
        "text_secondary": "#9AA3B2",
        "accent": "#3B82F6",
        "accent_hover": "#2563EB",
        "border": "#2A3344",
        "danger": "#EF4444",
        "success": "#22C55E",
    },
    # 浅色主题：保持与深色主题相同的控件层级
    "light": {
        "window_bg": "#F3F5F8",
        "toolbar_bg": "#FFFFFF",
        "panel_bg": "#FFFFFF",
        "item_bg": "#EEF1F6",
        "item_hover": "#E2E8F0",
        "text_primary": "#1E293B",
        "text_secondary": "#64748B",
        "accent": "#2563EB",
        "accent_hover": "#1D4ED8",
        "border": "#E2E8F0",
        "danger": "#DC2626",
        "success": "#16A34A",
    },
}
