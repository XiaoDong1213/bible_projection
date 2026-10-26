"""用户可见讲篇格式：主存档 PPTX，旧 .sermon 仍可打开。"""

from __future__ import annotations

from .store import LEGACY_FILTER, PACKAGE_EXT, PACKAGE_FILTER

PPTX_EXT = ".pptx"
PPTX_FILTER = "PowerPoint (*.pptx)"
OPEN_FILTER = f"{PPTX_FILTER};;{PACKAGE_FILTER};;{LEGACY_FILTER};;所有文件 (*.*)"
SAVE_FILTER = f"{PPTX_FILTER};;{PACKAGE_FILTER}"

__all__ = [
    "LEGACY_FILTER",
    "OPEN_FILTER",
    "PACKAGE_EXT",
    "PACKAGE_FILTER",
    "PPTX_EXT",
    "PPTX_FILTER",
    "SAVE_FILTER",
]
