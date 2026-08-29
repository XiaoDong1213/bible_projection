# ui/themes.py
# 主题配色常量
# 用于代码中需要动态配色的地方（QSS之外的补充）

THEMES = {
    "dark": {
        "toolbar_bg": "#1E1E2E",      # 工具栏背景
        "panel_bg": "#1A1A28",        # 面板背景
        "item_bg": "#252538",         # 条目背景
        "text_primary": "#DDDDDD",    # 主要文字
        "text_secondary": "#999999",  # 次要文字
        "accent": "#4A90E2",          # 强调色
        "border": "#3A3A5E"           # 边框色
    },
    "light": {
        "toolbar_bg": "#FFFFFF",
        "panel_bg": "#FFFFFF",
        "item_bg": "#F0F2F5",
        "text_primary": "#333333",
        "text_secondary": "#888888",
        "accent": "#2563EB",
        "border": "#E5E7EB"
    }
}
