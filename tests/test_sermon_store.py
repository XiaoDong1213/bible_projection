"""讲篇包加载：正常解压与路径穿越拒绝。"""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from core.sermon.model import new_document
from core.sermon.store import SermonStore, safe_sermon_id
from core.sermon.templates import TemplateStore


class SermonStoreTests(unittest.TestCase):
    def test_save_and_load_package(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            doc = new_document()
            doc.title = "测试讲篇"
            pkg = root / "demo.sermon"
            store.save_package(doc, pkg)
            loaded = store.load_package(pkg)
            self.assertEqual(loaded.title, "测试讲篇")
            self.assertTrue((store.sermon_dir(loaded.id) / "sermon.json").is_file())

    def test_reject_zip_slip(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            pkg = root / "evil.sermon"
            with zipfile.ZipFile(pkg, "w") as zf:
                zf.writestr("sermon.json", json.dumps(new_document().to_dict()))
                zf.writestr("../evil.txt", "nope")
            with self.assertRaises(ValueError):
                store.load_package(pkg)

    def test_safe_sermon_id_blocks_traversal(self):
        self.assertEqual(safe_sermon_id("sermon_abc123"), "sermon_abc123")
        self.assertNotIn("..", safe_sermon_id("../escape"))
        self.assertNotIn("/", safe_sermon_id("a/b"))
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            folder = store.sermon_dir("../escape_me")
            self.assertTrue(str(folder.resolve()).startswith(str(root.resolve())))
            doc = new_document()
            doc.id = "../evil_id"
            pkg = root / "trap.sermon"
            store.save_package(doc, pkg)
            # 包内仍可能写着脏 id；加载时必须洗成安全 id
            data = json.loads(zipfile.ZipFile(pkg).read("sermon.json"))
            data["id"] = "../evil_id"
            with zipfile.ZipFile(pkg, "w") as zf:
                zf.writestr("sermon.json", json.dumps(data))
            loaded = store.load_package(pkg)
            self.assertEqual(loaded.id, safe_sermon_id(loaded.id))
            self.assertTrue(
                str(store.sermon_dir(loaded.id).resolve()).startswith(str(root.resolve()))
            )
            with self.assertRaises(ValueError):
                store.resolve_asset(loaded.id, "assets/../../outside.txt")

    def test_save_normalizes_doc_id(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            doc = new_document()
            doc.id = "../bad"
            doc.title = "x"
            store.save(doc)
            self.assertEqual(doc.id, safe_sermon_id("../bad"))
            data = json.loads(store.json_path(doc.id).read_text(encoding="utf-8"))
            self.assertEqual(data["id"], doc.id)
            self.assertTrue(str(store.sermon_dir(doc.id).resolve()).startswith(str(root.resolve())))

    def test_template_list_and_delete_use_folder_id(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "templates"
            store = TemplateStore(root)
            folder = root / "tpl_safe"
            folder.mkdir(parents=True)
            (folder / "assets").mkdir()
            doc = new_document()
            doc.id = "../../escape_delete"
            doc.title = "evil"
            (folder / "template.json").write_text(json.dumps(doc.to_dict()), encoding="utf-8")
            items = store.list_templates()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["id"], "tpl_safe")
            store.delete(items[0]["id"])
            self.assertFalse(folder.exists())
            # 脏 id 不得删到 templates 外
            victim = Path(raw) / "victim.txt"
            victim.write_text("keep", encoding="utf-8")
            store.delete("../../escape_delete")
            self.assertTrue(victim.is_file())

    def test_cleanup_temps_keeps_active(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            doc = store.create_blank("keep")
            stale = root / "gone.__old__"
            stale.mkdir()
            (stale / "x.txt").write_text("x", encoding="utf-8")
            tmp = root / ".sid_load_abc"
            tmp.mkdir()
            store.cleanup_temps(keep_id=doc.id)
            self.assertTrue(store.sermon_dir(doc.id).is_dir())
            self.assertFalse(stale.exists())
            self.assertFalse(tmp.exists())


if __name__ == "__main__":
    unittest.main()
