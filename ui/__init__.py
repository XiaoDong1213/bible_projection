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


# 经文搜索面板采用延迟导入，避免 ui 包初始化阶段产生循环导入。
def __getattr__(name):
    if name == "ScriptureSearchWidget":
        from .scripture_search import ScriptureSearchWidget
        return ScriptureSearchWidget
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
