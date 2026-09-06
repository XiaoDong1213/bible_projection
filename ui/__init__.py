# ui/__init__.py
# UI组件包，统一导出所有控件

from .themes import THEMES
from .history_item import HistoryItemWidget, HistoryListWidget
from .scripture_display import ScriptureDisplay
from .preview_host import PreviewHost
from .search_widget import SearchWidget
from .scripture_search import ScriptureSearchWidget
from .navigation_panel import NavigationPanel
from .toolbar import ToolBarWidget
from .extension_window import ExtensionWindow

__all__ = [
    "THEMES",
    "HistoryItemWidget",
    "HistoryListWidget",
    "ScriptureDisplay",
    "PreviewHost",
    "SearchWidget",
    "ScriptureSearchWidget",
    "NavigationPanel",
    "ToolBarWidget",
    "ExtensionWindow",
]
