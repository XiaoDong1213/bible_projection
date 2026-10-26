"""讲篇本地存储：工作目录 + .sermon 单文件包（zip：sermon.json + assets/）。"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from core.paths import data_dir

from .model import SermonDocument, new_document

PACKAGE_EXT = ".sermon"
PACKAGE_FILTER = "讲篇 (*.sermon)"
LEGACY_FILTER = "旧版讲篇 (sermon.json)"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def suggest_package_name(title: str) -> str:
    """从标题生成安全文件名（不含扩展名）。"""
    raw = (title or "未命名讲篇").strip() or "未命名讲篇"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw)
    cleaned = cleaned.strip(" .") or "未命名讲篇"
    return cleaned[:80]


def safe_sermon_id(raw: str, fallback: str = "sermon") -> str:
    """拒绝路径穿越用的 id（只留字母数字 _ -）。"""
    sid = (raw or "").strip()
    if _SAFE_ID.match(sid):
        return sid
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (fallback or "sermon").strip()).strip("_")
    cleaned = cleaned[:64] or "sermon"
    if not _SAFE_ID.match(cleaned):
        from .model import new_id

        return new_id("sermon_")
    return cleaned


class SermonStore:
    """工作副本在 sermons/<id>/；用户可见存档为 *.sermon 包。"""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else data_dir() / "sermons"
        self.root.mkdir(parents=True, exist_ok=True)

    def sermon_dir(self, sermon_id: str) -> Path:
        sid = safe_sermon_id(sermon_id)
        root = self.root.resolve()
        path = (root / sid).resolve()
        path.relative_to(root)
        return path

    def assets_dir(self, sermon_id: str) -> Path:
        path = self.sermon_dir(sermon_id) / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def json_path(self, sermon_id: str) -> Path:
        return self.sermon_dir(sermon_id) / "sermon.json"

    def list_sermons(self) -> list[dict]:
        """返回简要列表：优先 *.sermon，其次旧版目录。"""
        items: list[dict] = []
        seen_ids: set[str] = set()
        if not self.root.exists():
            return items

        for path in sorted(self.root.glob(f"*{PACKAGE_EXT}")):
            if not path.is_file():
                continue
            meta = self._peek_package(path)
            if not meta:
                continue
            sid = meta.get("id") or path.stem
            seen_ids.add(sid)
            items.append(
                {
                    "id": sid,
                    "title": meta.get("title") or path.stem,
                    "updated": meta.get("updated", ""),
                    "path": str(path),
                    "kind": "package",
                }
            )

        for child in sorted(self.root.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if child.name.endswith(".__old__"):
                continue
            path = child / "sermon.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            sid = data.get("id") or child.name
            if sid in seen_ids:
                continue
            meta = data.get("meta") or {}
            items.append(
                {
                    "id": sid,
                    "title": data.get("title") or "未命名讲篇",
                    "updated": meta.get("updated", ""),
                    "path": str(path),
                    "kind": "legacy",
                }
            )

        items.sort(key=lambda x: x.get("updated") or "", reverse=True)
        return items

    def _peek_package(self, package_path: Path) -> dict | None:
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                raw = zf.read("sermon.json")
            data = json.loads(raw.decode("utf-8"))
        except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        meta = data.get("meta") or {}
        return {
            "id": data.get("id"),
            "title": data.get("title"),
            "updated": meta.get("updated", ""),
        }

    def load(self, sermon_id: str) -> SermonDocument:
        sid = safe_sermon_id(sermon_id)
        path = self.json_path(sid)
        data = json.loads(path.read_text(encoding="utf-8"))
        doc = SermonDocument.from_dict(data)
        doc.id = sid
        return doc

    def load_path(self, path: Path | str) -> SermonDocument:
        path = Path(path)
        if path.suffix.lower() == PACKAGE_EXT:
            return self.load_package(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        doc = SermonDocument.from_dict(data)
        if path.parent.name and path.parent.parent == self.root:
            doc.id = path.parent.name
        return doc

    def load_package(self, package_path: Path | str) -> SermonDocument:
        """解压 .sermon 到临时目录，成功后再替换工作副本。"""
        package_path = Path(package_path)
        if not package_path.is_file():
            raise FileNotFoundError(str(package_path))
        with zipfile.ZipFile(package_path, "r") as zf:
            self._validate_zip(zf)
            try:
                data = json.loads(zf.read("sermon.json").decode("utf-8"))
            except KeyError as exc:
                raise ValueError("不是有效的讲篇包（缺少 sermon.json）") from exc
            doc = SermonDocument.from_dict(data)
            sid = safe_sermon_id((doc.id or "").strip() or package_path.stem, package_path.stem)
            doc.id = sid
            folder = self.sermon_dir(doc.id)
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = Path(tempfile.mkdtemp(prefix=f".{sid}_load_", dir=str(self.root.resolve())))
            old = folder.with_name(folder.name + ".__old__")
            try:
                self._extract_package(zf, tmp)
                if old.exists():
                    shutil.rmtree(old)
                if folder.exists():
                    folder.rename(old)
                tmp.rename(folder)
                if old.exists():
                    shutil.rmtree(old)
            except Exception:
                if not folder.exists() and old.exists():
                    old.rename(folder)
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)
                raise
        return doc

    @staticmethod
    def _validate_zip(zf: zipfile.ZipFile) -> None:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/").lstrip("/")
            if not name or name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
                raise ValueError(f"讲篇包含非法路径：{info.filename}")
            if ".." in name.split("/"):
                raise ValueError(f"讲篇包含非法路径：{info.filename}")

    @staticmethod
    def _extract_package(zf: zipfile.ZipFile, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        root = dest.resolve()
        written = 0
        max_bytes = 500 * 1024 * 1024  # 解压上限，防压缩炸弹
        for info in zf.infolist():
            name = info.filename.replace("\\", "/").lstrip("/")
            if not name or name.endswith("/"):
                continue
            if name != "sermon.json" and not name.startswith("assets/"):
                continue
            if ".." in name.split("/"):
                raise ValueError(f"讲篇包含非法路径：{info.filename}")
            target = (dest / name).resolve()
            try:
                target.relative_to(root)
            except ValueError as exc:
                raise ValueError(f"讲篇包含非法路径：{info.filename}") from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info, "r") as src, open(target, "wb") as out:
                while True:
                    chunk = src.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_bytes:
                        raise ValueError("讲篇包解压过大（超过 500MB）")
                    out.write(chunk)

    def save(self, doc: SermonDocument) -> Path:
        """写入工作目录（编辑/放映用），不写用户 .sermon 包。"""
        doc.id = safe_sermon_id(doc.id)
        doc.touch()
        folder = self.sermon_dir(doc.id)
        folder.mkdir(parents=True, exist_ok=True)
        self.assets_dir(doc.id)
        path = self.json_path(doc.id)
        # 先写临时文件再替换，避免写到一半崩溃留下空/半截 JSON
        tmp = path.with_name(path.name + ".tmp")
        payload = json.dumps(doc.to_dict(), ensure_ascii=False, indent=2)
        try:
            tmp.write_text(payload, encoding="utf-8")
            tmp.replace(path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return path

    def save_package(self, doc: SermonDocument, package_path: Path | str) -> Path:
        """保存工作副本并打包为 .sermon。"""
        package_path = Path(package_path)
        if package_path.suffix.lower() != PACKAGE_EXT:
            package_path = package_path.with_suffix(PACKAGE_EXT)
        package_path.parent.mkdir(parents=True, exist_ok=True)
        self.save(doc)
        work = self.sermon_dir(doc.id)
        tmp = package_path.with_suffix(package_path.suffix + ".tmp")
        try:
            with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                json_file = self.json_path(doc.id)
                zf.write(json_file, "sermon.json")
                assets = work / "assets"
                if assets.is_dir():
                    for file in assets.rglob("*"):
                        if file.is_file():
                            arc = file.relative_to(work).as_posix()
                            zf.write(file, arc)
            # 原子替换：不要先 unlink 旧包（失败会丢唯一副本）
            tmp.replace(package_path)
        except Exception:
            if tmp.exists():
                tmp.unlink(missing_ok=True)
            raise
        return package_path

    def delete(self, sermon_id: str) -> None:
        folder = self.sermon_dir(sermon_id)
        if folder.exists():
            shutil.rmtree(folder)

    def import_asset(self, sermon_id: str, source: Path | str) -> str:
        """复制图片到 assets/，返回相对路径（assets/xxx）。"""
        source = Path(source)
        if not source.is_file():
            raise FileNotFoundError(str(source))
        dest_dir = self.assets_dir(sermon_id)
        name = source.name
        dest = dest_dir / name
        if dest.exists():
            stem, suffix = source.stem, source.suffix
            n = 1
            while dest.exists():
                dest = dest_dir / f"{stem}_{n}{suffix}"
                n += 1
        shutil.copy2(source, dest)
        return f"assets/{dest.name}"

    def resolve_asset(self, sermon_id: str, rel: str) -> Path:
        rel = (rel or "").replace("\\", "/").lstrip("/")
        base = self.sermon_dir(sermon_id).resolve()
        target = (base / rel).resolve()
        target.relative_to(base)
        return target

    def cleanup_temps(self, keep_id: str | None = None) -> None:
        """清掉加载残留的临时目录，不碰正在编辑的工作副本。"""
        if not self.root.exists():
            return
        keep = str(keep_id or "").strip()
        for child in list(self.root.iterdir()):
            name = child.name
            if not child.is_dir():
                continue
            if keep and name == keep:
                continue
            if name.endswith(".__old__") or name.startswith("."):
                shutil.rmtree(child, ignore_errors=True)

    def create_blank(self, title: str = "未命名讲篇") -> SermonDocument:
        doc = new_document(title=title)
        self.save(doc)
        return doc

    def default_save_dir(self) -> Path:
        return self.root
