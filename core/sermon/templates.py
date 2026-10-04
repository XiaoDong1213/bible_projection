"""讲篇模板库：templates/<id>/template.json + assets/ + thumb.png。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.paths import data_dir

from .model import SermonDocument, new_id


class TemplateStore:
    """模板与讲篇结构相同，另存后改讲篇不影响模板。"""

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else data_dir() / "templates"
        self.root.mkdir(parents=True, exist_ok=True)

    def template_dir(self, template_id: str) -> Path:
        return self.root / template_id

    def json_path(self, template_id: str) -> Path:
        return self.template_dir(template_id) / "template.json"

    def thumb_path(self, template_id: str) -> Path:
        return self.template_dir(template_id) / "thumb.png"

    def assets_dir(self, template_id: str) -> Path:
        path = self.template_dir(template_id) / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_templates(self) -> list[dict]:
        items: list[dict] = []
        if not self.root.exists():
            return items
        for child in sorted(self.root.iterdir()):
            if not child.is_dir():
                continue
            path = child / "template.json"
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            meta = data.get("meta") or {}
            thumb = child / "thumb.png"
            items.append(
                {
                    "id": data.get("id") or child.name,
                    "title": data.get("title") or "未命名模板",
                    "updated": meta.get("updated", ""),
                    "thumb": str(thumb) if thumb.exists() else "",
                }
            )
        items.sort(key=lambda x: x.get("updated") or "", reverse=True)
        return items

    def load(self, template_id: str) -> SermonDocument:
        data = json.loads(self.json_path(template_id).read_text(encoding="utf-8"))
        doc = SermonDocument.from_dict(data)
        doc.id = template_id
        return doc

    def save_from_document(
        self,
        source: SermonDocument,
        *,
        title: str | None = None,
        source_assets: Path | None = None,
        thumb_png: Path | bytes | None = None,
    ) -> str:
        """从当前讲篇深拷贝为新模板，返回 template_id。"""
        tpl_id = new_id("tpl_")
        data = source.to_dict()
        data["id"] = tpl_id
        data["title"] = (title or source.title or "未命名模板").strip() or "未命名模板"
        folder = self.template_dir(tpl_id)
        folder.mkdir(parents=True, exist_ok=True)
        self.assets_dir(tpl_id)

        # 复制资源
        if source_assets and Path(source_assets).exists():
            src = Path(source_assets)
            if src.name != "assets":
                src = src / "assets" if (src / "assets").exists() else src
            if src.is_dir():
                for f in src.iterdir():
                    if f.is_file():
                        shutil.copy2(f, self.assets_dir(tpl_id) / f.name)

        doc = SermonDocument.from_dict(data)
        doc.id = tpl_id
        doc.touch()
        self.json_path(tpl_id).write_text(
            json.dumps(doc.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if thumb_png is not None:
            thumb = self.thumb_path(tpl_id)
            if isinstance(thumb_png, (bytes, bytearray)):
                thumb.write_bytes(thumb_png)
            else:
                p = Path(thumb_png)
                if p.is_file():
                    shutil.copy2(p, thumb)
        return tpl_id

    def instantiate(self, template_id: str) -> SermonDocument:
        """从模板新建讲篇文档（新 id，资源需由调用方复制到 sermon 目录）。"""
        src = self.load(template_id)
        data = src.to_dict()
        data["id"] = new_id("sermon_")
        # 保留标题，加前缀避免混淆
        title = src.title or "未命名讲篇"
        data["title"] = title
        doc = SermonDocument.from_dict(data)
        doc.touch()
        return doc

    def copy_assets_to(self, template_id: str, dest_assets: Path):
        dest_assets = Path(dest_assets)
        dest_assets.mkdir(parents=True, exist_ok=True)
        src = self.assets_dir(template_id)
        if not src.exists():
            return
        for f in src.iterdir():
            if f.is_file():
                shutil.copy2(f, dest_assets / f.name)

    def delete(self, template_id: str) -> None:
        folder = self.template_dir(template_id)
        if folder.exists():
            shutil.rmtree(folder)
