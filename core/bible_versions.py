"""圣经版本（多译本数据库）扫描与切换辅助。

一个版本 = 一个 SQLite 数据库文件。内置版本在 resources/，用户版本放在
数据目录 bibles/ 子文件夹（安装版 %APPDATA%\\bible_projection\\bibles）。
显示名优先读库内 metadata 表的 name，缺省用文件名。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .paths import data_dir, resource_dir

USER_BIBLES_DIRNAME = "bibles"
_DEFAULT_FILE = "和合本.db"

_METADATA_NAMES = ("name", "version", "版本", "名称", "shortname")


def user_bibles_dir() -> Path:
    return data_dir() / USER_BIBLES_DIRNAME


def ensure_user_bibles_dir() -> Path:
    path = user_bibles_dir()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path


def open_user_bibles_dir() -> bool:
    """在资源管理器中打开版本文件夹；成功返回 True。"""
    import subprocess
    import sys

    path = ensure_user_bibles_dir()
    try:
        if sys.platform == "win32":
            os.startfile(str(path))
            return True
        subprocess.Popen(["xdg-open", str(path)])
        return True
    except Exception:
        return False


def resolve_bible_path(filename: str) -> Path | None:
    """按文件名解析版本路径：用户目录优先，其次内置 resources。"""
    name = str(filename or "").strip()
    if not name:
        return None
    for base in (user_bibles_dir(), resource_dir()):
        candidate = base / name
        if candidate.is_file():
            return candidate
    return None


def _probe_bible_name(path: Path) -> str:
    """读 metadata 表里的版本名；失败则退回文件名。"""
    stem = path.stem
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        try:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(metadata)")]
            if "name" in {c.lower() for c in columns} and "value" in {
                c.lower() for c in columns
            }:
                for key in _METADATA_NAMES:
                    row = conn.execute(
                        "SELECT value FROM metadata WHERE lower(name)=lower(?) LIMIT 1",
                        (key,),
                    ).fetchone()
                    if row and str(row[0] or "").strip():
                        return str(row[0]).strip()
        finally:
            conn.close()
    except sqlite3.Error:
        pass
    return stem


def available_bible_versions() -> list[dict]:
    """扫描可用版本：[{name, file, path, builtin}]，和合本排最前。

    内置目录（resources/）与用户目录（数据目录 bibles/）下的 .db 都是版本。
    """
    versions: list[dict] = []
    seen: set[str] = set()

    for path in sorted(resource_dir().glob("*.db")):
        if not path.is_file() or path.name in seen:
            continue
        seen.add(path.name)
        versions.append(
            {
                "name": _probe_bible_name(path),
                "file": path.name,
                "path": path,
                "builtin": True,
            }
        )
    # 和合本排最前
    versions.sort(key=lambda v: (v["file"] != _DEFAULT_FILE, v["file"]))

    user_dir = user_bibles_dir()
    if user_dir.is_dir():
        for path in sorted(user_dir.glob("*.db")):
            if path.name in seen or not path.is_file():
                continue
            seen.add(path.name)
            versions.append(
                {
                    "name": _probe_bible_name(path),
                    "file": path.name,
                    "path": path,
                    "builtin": False,
                }
            )
    return versions
