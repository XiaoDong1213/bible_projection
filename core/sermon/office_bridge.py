"""在本机 PowerPoint / WPS 演示中打开讲篇。"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import winreg
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

logger = logging.getLogger(__name__)


def office_apps_hint() -> str:
    return "请安装 WPS 演示或 Microsoft PowerPoint，并用其打开 .pptx。"


def _unique_existing(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        try:
            if not path.is_file():
                continue
            key = str(path.resolve()).lower()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _wps_install_roots() -> list[Path]:
    roots: list[Path] = []
    for hive, sub in (
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Kingsoft\Office\6.0\Common"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Kingsoft\Office\6.0\Common"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Kingsoft\Office\6.0\Common"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as key:
                val, _ = winreg.QueryValueEx(key, "InstallRoot")
        except OSError:
            continue
        if val:
            roots.append(Path(str(val)))
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = Path(local) / "Kingsoft"
        for child in ("WPS Office", "wpsoffice"):
            folder = base / child
            if folder.is_dir():
                roots.append(folder)
                try:
                    for subdir in folder.iterdir():
                        if subdir.is_dir() and (subdir / "office6").is_dir():
                            roots.append(subdir)
                except OSError:
                    pass
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
        base = os.environ.get(env)
        if not base:
            continue
        roots.append(Path(base) / "Kingsoft")
        roots.append(Path(base) / "WPS Office")
    return roots


def find_wps_presentation_exe() -> Path | None:
    """探测本机 WPS 演示（wpp.exe）。"""
    candidates: list[Path] = []
    which = shutil.which("wpp.exe") or shutil.which("wpp")
    if which:
        candidates.append(Path(which))
    for root in _wps_install_roots():
        candidates.append(root / "office6" / "wpp.exe")
        candidates.append(root / "wpp.exe")
    found = _unique_existing(candidates)
    return found[0] if found else None


def find_powerpoint_exe() -> Path | None:
    """探测本机 PowerPoint 可执行文件。"""
    candidates: list[Path] = []
    which = shutil.which("POWERPNT.EXE") or shutil.which("powerpnt")
    if which:
        candidates.append(Path(which))
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
        base = os.environ.get(env)
        if not base:
            continue
        root = Path(base)
        candidates.extend(
            [
                root / "Microsoft Office" / "root" / "Office16" / "POWERPNT.EXE",
                root / "Microsoft Office" / "Office16" / "POWERPNT.EXE",
                root / "Microsoft Office" / "Office15" / "POWERPNT.EXE",
                root / "Microsoft Office" / "Office14" / "POWERPNT.EXE",
            ]
        )
    found = _unique_existing(candidates)
    return found[0] if found else None


def find_presentation_exes(*, prefer_wps: bool = True) -> list[Path]:
    """可用演示程序列表。"""
    wps = find_wps_presentation_exe()
    ppt = find_powerpoint_exe()
    if prefer_wps:
        return [p for p in (wps, ppt) if p is not None]
    return [p for p in (ppt, wps) if p is not None]


def presentation_app_available() -> bool:
    return bool(find_presentation_exes()) or _any_presentation_com()


def _any_presentation_com() -> bool:
    if os.name != "nt":
        return False
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    for prog_id in ("KWPP.Application", "WPP.Application", "PowerPoint.Application"):
        try:
            win32com.client.Dispatch(prog_id)
            return True
        except Exception:
            continue
    return False


def open_in_office(path: Path | str, *, prefer_wps: bool = True) -> bool:
    """打开 PPTX：默认优先 WPS 演示，失败再系统关联 / PowerPoint。"""
    path = Path(path)
    if not path.is_file():
        return False
    resolved = str(path.resolve())

    for exe in find_presentation_exes(prefer_wps=prefer_wps):
        try:
            subprocess.Popen(
                [str(exe), resolved],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except OSError:
            logger.warning("无法用 %s 打开：%s", exe, path)

    url = QUrl.fromLocalFile(resolved)
    if QDesktopServices.openUrl(url):
        return True
    try:
        os.startfile(resolved)  # type: ignore[attr-defined]
        return True
    except OSError:
        logger.warning("无法用系统关联打开：%s", path)
        return False
