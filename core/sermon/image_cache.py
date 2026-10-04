"""讲篇图片解码缓存：编辑器与放映舞台共用，避免同一张大图反复读盘。"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

_MAX_RAW = 48
_MAX_SCALED = 64
_raw: OrderedDict[tuple, QPixmap] = OrderedDict()
_scaled: OrderedDict[tuple, QPixmap] = OrderedDict()


def _remember(store: OrderedDict, key: tuple, value: QPixmap, limit: int) -> QPixmap:
    store[key] = value
    store.move_to_end(key)
    while len(store) > limit:
        store.popitem(last=False)
    return value


def resolve_asset(rel_or_abs: str, assets_root: Path | None) -> Path | None:
    path = Path(rel_or_abs)
    if path.is_file():
        return path
    if assets_root is None:
        return None
    rel = rel_or_abs.replace("\\", "/")
    candidate = assets_root / rel
    if candidate.is_file():
        return candidate
    sermon_dir = assets_root.parent if assets_root.name == "assets" else assets_root
    candidate = sermon_dir / rel
    if candidate.is_file():
        return candidate
    return None


def load_pixmap(rel_or_abs: str, assets_root: Path | None) -> QPixmap | None:
    path = resolve_asset(rel_or_abs, assets_root)
    if path is None or not path.is_file():
        return None
    key = ("raw", str(path.resolve()), path.stat().st_mtime_ns)
    cached = _raw.get(key)
    if cached is not None and not cached.isNull():
        _raw.move_to_end(key)
        return cached
    pix = QPixmap(str(path))
    if pix.isNull():
        return None
    return _remember(_raw, key, pix, _MAX_RAW)


def scaled_pixmap(
    pix: QPixmap,
    w: int,
    h: int,
    *,
    fit: str | None = None,
    smooth: bool = False,
) -> QPixmap:
    if pix is None or pix.isNull():
        return QPixmap()
    if fit == "cover":
        mode = Qt.AspectRatioMode.KeepAspectRatioByExpanding
    elif fit == "contain":
        mode = Qt.AspectRatioMode.KeepAspectRatio
    else:
        mode = Qt.AspectRatioMode.IgnoreAspectRatio
    xform = (
        Qt.TransformationMode.SmoothTransformation
        if smooth
        else Qt.TransformationMode.FastTransformation
    )
    key = ("scaled", pix.cacheKey(), int(w), int(h), fit or "", mode.name, xform.name)
    cached = _scaled.get(key)
    if cached is not None and not cached.isNull():
        _scaled.move_to_end(key)
        return cached
    scaled = pix.scaled(max(1, int(w)), max(1, int(h)), mode, xform)
    return _remember(_scaled, key, scaled, _MAX_SCALED)
