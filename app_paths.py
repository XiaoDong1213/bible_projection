# app_paths.py
# 源码运行与 PyInstaller 打包后的路径统一入口

import sys
from pathlib import Path


def resource_dir() -> Path:
    """只读资源目录（db、qss、icon）。打包后为 _MEIPASS。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def app_dir() -> Path:
    """程序根目录（exe 旁 / 源码根）。用于 install.mark 与便携配置。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent
