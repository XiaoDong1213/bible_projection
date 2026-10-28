"""从 Gitea / GitHub Release 检查 / 下载新版本安装包（优先 Gitea）。"""

from __future__ import annotations

import json
import re
import ssl
import tempfile
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from app.version import (
    APP_VERSION,
    GITHUB_OWNER,
    GITHUB_RELEASES_LATEST_API,
    GITHUB_REPO,
)

_USER_AGENT = f"BiblePro/{APP_VERSION} (+https://github.com/XiaoDong1213/bible_projection)"
# 固定名优先（文章 /releases/latest/download/Bible_Pro_Setup.exe）；兼容带版本号旧附件
_SETUP_FIXED = "Bible_Pro_Setup.exe"
_SETUP_NAME = re.compile(r"^Bible_Pro(_.+)?_Setup\.exe$", re.IGNORECASE)

# 本机测速最快节点（其它慢源一律不用）
_FAST_PROXY = "https://gh.acmsz.top/"
_RANGE_PARTS = 6  # 多连接加速；段数过多易有几段卡死
_RANGE_RETRIES = 4
_RANGE_TIMEOUT = 25  # 单段读超时（秒），卡住就重试该段


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    notes: str
    asset_name: str
    size: int | None = None


class DownloadCancelled(Exception):
    """用户取消下载。"""


def parse_version(raw: str) -> tuple[int, ...]:
    text = str(raw or "").strip().lstrip("vV")
    parts: list[int] = []
    for chunk in text.split("."):
        digits = re.match(r"(\d+)", chunk)
        parts.append(int(digits.group(1)) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return parse_version(remote) > parse_version(local)


def _http_get(url: str, *, timeout: float = 20.0, accept: str | None = None) -> bytes:
    headers = {"User-Agent": _USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers, method="GET")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read()


def _github_asset_urls(version: str, asset_name: str) -> list[str]:
    ver = str(version or "").lstrip("vV")
    name = asset_name or _SETUP_FIXED
    base = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download/v{ver}"
    return [
        f"{base}/{_SETUP_FIXED}",
        f"{base}/{name}",
        f"{base}/Bible_Pro_{ver}_Setup.exe",
    ]


def _via_fast_proxy(url: str) -> str:
    """快节点前缀 + 完整 GitHub URL。"""
    if url.startswith(_FAST_PROXY):
        return url
    return _FAST_PROXY.rstrip("/") + "/" + url


def _candidate_download_urls(official: str, *, version: str = "", asset_name: str = "") -> list[str]:
    """只用本机最快的加速节点，不再回退慢源。"""
    github_seeds: list[str] = []
    if version:
        github_seeds.extend(_github_asset_urls(version, asset_name or _SETUP_FIXED))
    if official and "github.com" in official:
        github_seeds.insert(0, official)
    if not github_seeds and official:
        # 非 GitHub 直链（极少）：仍套同一快节点前缀试试
        return [_via_fast_proxy(official)]

    urls: list[str] = []
    seen: set[str] = set()
    for seed in github_seeds:
        u = _via_fast_proxy(seed)
        if u not in seen:
            seen.add(u)
            urls.append(u)
    return urls


def _parse_release_payload(data: dict) -> UpdateInfo | None:
    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    if not tag:
        return None
    version = tag.lstrip("vV")
    notes = str(data.get("body") or "").strip()
    assets = list(data.get("assets") or [])
    chosen = None
    for asset in assets:
        name = str(asset.get("name") or "")
        if name.casefold() == _SETUP_FIXED.casefold():
            chosen = asset
            break
    if chosen is None:
        for asset in assets:
            name = str(asset.get("name") or "")
            if _SETUP_NAME.match(name):
                chosen = asset
                break
    if chosen is None:
        return None
    name = str(chosen.get("name") or "")
    download_url = str(chosen.get("browser_download_url") or "")
    # Gitea 偶发只有相对路径 / 无 browser_download_url
    if not download_url:
        download_url = str(chosen.get("download_url") or chosen.get("url") or "")
    if not download_url:
        return None
    try:
        size = int(chosen.get("size")) if chosen.get("size") is not None else None
    except (TypeError, ValueError):
        size = None
    return UpdateInfo(
        version=version,
        download_url=download_url,
        notes=notes,
        asset_name=name or _SETUP_FIXED,
        size=size,
    )


def fetch_latest_release() -> UpdateInfo | None:
    """读 GitHub Release 版本信息；安装包下载另走快节点。

    查版本只用 GitHub（API 经 gh-proxy.com，官方文档支持；失败再直连）。
    不用 gh.acmsz.top 查 API（该站对 API 常返回空正文）。
    """
    errors: list[str] = []
    apis = (
        ("https://gh-proxy.com/" + GITHUB_RELEASES_LATEST_API, "application/vnd.github+json"),
        (GITHUB_RELEASES_LATEST_API, "application/vnd.github+json"),
    )
    for api, accept in apis:
        try:
            raw = _http_get(api, accept=accept)
            text = raw.decode("utf-8").strip()
            if not text:
                errors.append(f"{api}: empty body")
                continue
            info = _parse_release_payload(json.loads(text))
            if info is not None:
                # 保证 download_url 是官方 GitHub 附件地址
                if info.version and "github.com" not in (info.download_url or ""):
                    gh = _github_asset_urls(info.version, info.asset_name)[0]
                    info = UpdateInfo(
                        version=info.version,
                        download_url=gh,
                        notes=info.notes,
                        asset_name=info.asset_name or _SETUP_FIXED,
                        size=info.size,
                    )
                return info
            errors.append(f"{api}: no setup asset")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{api}: {exc}")
    if errors:
        raise RuntimeError("；".join(errors))
    return None


def check_for_update() -> UpdateInfo | None:
    """有比当前更新的版本则返回信息，否则 None。"""
    info = fetch_latest_release()
    if info is None or not is_newer(info.version):
        return None
    return info


def _download_one(
    url: str,
    partial: Path,
    *,
    expected_size: int,
    on_progress=None,
    cancel_event: threading.Event | None = None,
) -> None:
    """单连接下载；大文件且支持 Range 时改走多线程分段。"""
    size = expected_size or 0
    if size >= 2 * 1024 * 1024:
        try:
            _download_ranged(
                url,
                partial,
                total_size=size,
                parts=_RANGE_PARTS,
                on_progress=on_progress,
                cancel_event=cancel_event,
            )
            return
        except DownloadCancelled:
            raise
        except Exception:
            if partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass
            # 回退单连接
    _download_single(
        url,
        partial,
        expected_size=expected_size,
        on_progress=on_progress,
        cancel_event=cancel_event,
    )


def _download_single(
    url: str,
    partial: Path,
    *,
    expected_size: int,
    on_progress=None,
    cancel_event: threading.Event | None = None,
) -> None:
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT}, method="GET")
    with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
        total = resp.headers.get("Content-Length")
        try:
            total_n = int(total) if total else expected_size
        except ValueError:
            total_n = expected_size
        done = 0
        with open(partial, "wb") as out:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    out.close()
                    partial.unlink(missing_ok=True)
                    raise DownloadCancelled()
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if on_progress is not None:
                    on_progress(done, total_n)


def _download_ranged(
    url: str,
    partial: Path,
    *,
    total_size: int,
    parts: int = 4,
    on_progress=None,
    cancel_event: threading.Event | None = None,
) -> None:
    """Range 多连接并行下载；单段超时/中断会续传重试，避免卡在某一百分比。"""
    import time

    parts = max(2, min(parts, 8))
    chunk = total_size // parts
    ranges: list[tuple[int, int]] = []
    for i in range(parts):
        start = i * chunk
        end = total_size - 1 if i == parts - 1 else (start + chunk - 1)
        ranges.append((start, end))

    part_paths = [partial.with_suffix(partial.suffix + f".r{i}") for i in range(parts)]
    for p in part_paths:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
    progress = [0] * parts
    lock = threading.Lock()
    ctx = ssl.create_default_context()

    def _report():
        if on_progress is not None:
            on_progress(sum(progress), total_size)

    def _fetch(i: int, start: int, end: int) -> None:
        need = end - start + 1
        last_err: BaseException | None = None
        for attempt in range(_RANGE_RETRIES):
            if cancel_event is not None and cancel_event.is_set():
                raise DownloadCancelled()
            already = 0
            if part_paths[i].exists():
                already = part_paths[i].stat().st_size
            if already > need:
                # 损坏，重来
                try:
                    part_paths[i].unlink()
                except OSError:
                    pass
                already = 0
            with lock:
                progress[i] = already
                _report()
            if already >= need:
                return
            cur = start + already
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 BiblePro",
                    "Range": f"bytes={cur}-{end}",
                    "Accept": "*/*",
                },
                method="GET",
            )
            try:
                with urllib.request.urlopen(
                    req, timeout=_RANGE_TIMEOUT, context=ctx
                ) as resp:
                    status = int(getattr(resp, "status", None) or resp.getcode())
                    if status not in (200, 206):
                        raise RuntimeError(f"range status {status}")
                    mode = "ab" if already else "wb"
                    with open(part_paths[i], mode) as out:
                        while True:
                            if cancel_event is not None and cancel_event.is_set():
                                raise DownloadCancelled()
                            data = resp.read(1024 * 256)
                            if not data:
                                break
                            out.write(data)
                            already += len(data)
                            with lock:
                                progress[i] = min(already, need)
                                _report()
                            if already >= need:
                                break
                if part_paths[i].stat().st_size >= need:
                    with lock:
                        progress[i] = need
                        _report()
                    return
                last_err = RuntimeError(
                    f"段 {i} 不完整 {part_paths[i].stat().st_size}/{need}"
                )
            except DownloadCancelled:
                raise
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(0.4 * (attempt + 1))
                continue
        raise last_err or RuntimeError(f"段 {i} 下载失败")

    try:
        with ThreadPoolExecutor(max_workers=parts) as pool:
            futs = [pool.submit(_fetch, i, s, e) for i, (s, e) in enumerate(ranges)]
            for fut in as_completed(futs):
                if cancel_event is not None and cancel_event.is_set():
                    raise DownloadCancelled()
                fut.result()
        # 拼接
        with open(partial, "wb") as out:
            for p in part_paths:
                with open(p, "rb") as inp:
                    while True:
                        data = inp.read(1024 * 1024)
                        if not data:
                            break
                        out.write(data)
        if partial.stat().st_size != total_size:
            raise RuntimeError("分段合并后大小不匹配")
    finally:
        for p in part_paths:
            try:
                p.unlink(missing_ok=True)
            except OSError:
                pass


def download_installer(
    info: UpdateInfo,
    dest_dir: Path | None = None,
    *,
    on_progress=None,
    cancel_event: threading.Event | None = None,
) -> Path:
    """下载 Setup.exe：官网 gh-proxy 优先 + Range 多线程，失败再回退。"""
    folder = Path(dest_dir) if dest_dir else Path(tempfile.gettempdir()) / "bible_pro_update"
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (info.asset_name or _SETUP_FIXED)
    partial = dest.with_suffix(dest.suffix + ".part")
    last_error: Exception | None = None
    # 不再做多源测速（慢网上测速本身就要几分钟）；直接按文档顺序下
    candidates = _candidate_download_urls(
        info.download_url,
        version=info.version,
        asset_name=info.asset_name,
    )
    expected = int(info.size or 0)

    for url in candidates:
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelled()
        try:
            _download_one(
                url,
                partial,
                expected_size=expected,
                on_progress=on_progress,
                cancel_event=cancel_event,
            )
            partial.replace(dest)
            return dest
        except DownloadCancelled:
            raise
        except Exception as exc:  # noqa: BLE001 — 换镜像再试
            last_error = exc
            if partial.exists():
                try:
                    partial.unlink()
                except OSError:
                    pass
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("下载失败")

def launch_installer_and_exit(setup_path: Path) -> None:
    """拉起安装包；装完后删除临时 Setup，再退出当前进程。"""
    import os
    import subprocess
    import sys

    from PyQt6.QtWidgets import QApplication

    path = Path(setup_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(str(path))

    if os.name == "nt":
        # 独立 cmd：等安装结束 → 删安装包 → 删自身脚本
        helper = path.parent / "_bible_pro_run_update.cmd"
        helper.write_text(
            "\r\n".join(
                [
                    "@echo off",
                    f'start /wait "" "{path}" /SILENT /NORESTART /CLOSEAPPLICATIONS',
                    f'del /f /q "{path}" >nul 2>&1',
                    f'del /f /q "%~f0" >nul 2>&1',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        flags = 0
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        kwargs: dict = {"close_fds": True}
        if flags:
            kwargs["creationflags"] = flags
        subprocess.Popen(["cmd.exe", "/c", str(helper)], **kwargs)
    else:
        subprocess.Popen([str(path)], close_fds=True)

    app = QApplication.instance()
    if app is not None:
        app.quit()
    else:
        sys.exit(0)


def check_for_update_safe() -> tuple[UpdateInfo | None, str | None]:
    """返回 (更新信息, 错误信息)。"""
    try:
        return check_for_update(), None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", None) or exc
        return None, f"无法连接更新服务器：{reason}"
    except Exception as exc:  # noqa: BLE001 — 弹窗给用户看即可
        return None, str(exc) or "检查更新失败"
