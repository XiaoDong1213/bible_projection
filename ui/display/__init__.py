from .scripture_display import ScriptureDisplay
from . import scripture_title_render_patch  # noqa: F401 — v1 小标题/滚动 fraction 补丁
from .title_sync_patch import install_title_sync_patch

install_title_sync_patch()

from .preview_host import PreviewHost
from .extension_window import ExtensionWindow

__all__ = [
    "ScriptureDisplay",
    "PreviewHost",
    "ExtensionWindow",
]
