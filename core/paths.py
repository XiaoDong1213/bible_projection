"""统一资源与数据目录解析。"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    """源码包根目录（bible_projection_v2）。"""
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """只读资源：数据库、图标、QSS/SVG、install.mark。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return project_root() / "resources"


def app_dir() -> Path:
    """程序目录：exe 旁或源码根。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return project_root()


def data_dir() -> Path:
    """可写配置目录：安装版走 APPDATA，源码跑走项目根。"""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", str(Path.home())))
        else:
            base = Path.home()
        return base / "bible_projection"
    return project_root()


def styles_dir() -> Path:
    return resource_dir() / "styles"


def database_path() -> Path:
    return resource_dir() / "和合本.db"


def icon_path() -> Path:
    return resource_dir() / "icon.ico"
