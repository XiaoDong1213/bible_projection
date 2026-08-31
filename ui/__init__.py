# ui/__init__.py
# UI组件包，统一导出所有控件

from .themes import THEMES
from .history_item import HistoryItemWidget, HistoryListWidget
from .scripture_display import ScriptureDisplay
from .preview_host import PreviewHost
from .search_widget import SearchWidget
from .navigation_panel import NavigationPanel
from .toolbar import ToolBarWidget
from .extension_window import ExtensionWindow

# 集中加载运行时 UI 修复，避免改动核心显示控件的其它逻辑。
from .runtime_fixes import apply_runtime_fixes
apply_runtime_fixes(ScriptureDisplay, NavigationPanel)

__all__ = [
    "THEMES",
    "HistoryItemWidget",
    "HistoryListWidget",
    "ScriptureDisplay",
    "PreviewHost",
    "SearchWidget",
    "NavigationPanel",
    "ToolBarWidget",
    "ExtensionWindow",
]
