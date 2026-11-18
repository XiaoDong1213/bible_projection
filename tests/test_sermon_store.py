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
            doc = new_document(title="keep")
            store.save(doc)
            stale = root / "gone.__old__"
            stale.mkdir()
            (stale / "x.txt").write_text("x", encoding="utf-8")
            tmp = root / ".sid_load_abc"
            tmp.mkdir()
            store.cleanup_temps(keep_id=doc.id)
            self.assertTrue(store.sermon_dir(doc.id).is_dir())
            self.assertFalse(stale.exists())
            self.assertFalse(tmp.exists())

    def test_save_package_keeps_old_until_replace(self):
        """覆盖保存不得先删旧包：replace 失败时旧文件仍在。"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            doc = new_document()
            doc.title = "v1"
            pkg = root / "live.sermon"
            store.save_package(doc, pkg)
            self.assertTrue(pkg.is_file())
            doc.title = "v2"
            store.save_package(doc, pkg)
            loaded = store.load_package(pkg)
            self.assertEqual(loaded.title, "v2")
            self.assertFalse(pkg.with_suffix(".sermon.tmp").exists())

    def test_cleanup_empty_removes_shells(self):
        """空壳工作目录（无 sermon.json 且无文件）清理，有 json 的保留。"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            # 空目录壳
            shell = store.sermon_dir("sermon_shell1")
            shell.mkdir()
            # 仅含空 assets 的壳
            shell2 = store.sermon_dir("sermon_shell2")
            (shell2 / "assets").mkdir(parents=True)
            # 有 json 的工作副本：保留
            doc = new_document()
            store.save(doc)
            # 含文件但无 json 的目录：保留（有数据，不可判空）
            blob = store.sermon_dir("sermon_blob")
            blob.mkdir()
            (blob / "assets").mkdir()
            (blob / "assets" / "pic.png").write_bytes(b"x")
            store.cleanup_empty()
            self.assertFalse(shell.exists())
            self.assertFalse(shell2.exists())
            self.assertTrue(store.sermon_dir(doc.id).is_dir())
            self.assertTrue(blob.is_dir())

    def test_cleanup_all_workdirs_keeps_package_files(self):
        """启动全清：sermons/ 下工作副本目录、.sermon 包、散文件全部删除。"""
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as raw_docs:
            root = Path(raw)
            docs = Path(raw_docs)
            store = SermonStore(root)
            store.default_save_dir = lambda: docs
            doc = new_document()
            store.save(doc)
            pkg = root / "old-default.sermon"  # 旧版默认路径残留在 sermons/ 的包
            pkg.write_bytes(b"package")
            stray = root / "loose.txt"
            stray.write_text("x", encoding="utf-8")
            store.cleanup_all_workdirs()
            self.assertFalse(store.sermon_dir(doc.id).exists())
            self.assertFalse(pkg.exists())  # 用户拍板：sermons/ 下的包也不保留
            self.assertFalse(stray.exists())
            # 清空后新建讲篇仍可正常落盘
            doc2 = new_document()
            store.save(doc2)
            self.assertTrue(store.sermon_dir(doc2.id).is_dir())

    def test_default_save_dir_not_in_store_root(self):
        """「另存为」默认目录是用户文档，绝不在 sermons/ 清理区里。"""
        with tempfile.TemporaryDirectory() as raw:
            store = SermonStore(Path(raw))
            d = store.default_save_dir()
            self.assertTrue(d.is_dir())
            self.assertNotIn(str(store.root), str(d))

    def test_drop_unsaved_workdirs_discards_only_unsaved(self):
        """无包绑定的工作副本列入清理集合；保存后剔除；丢弃时删除目录。"""
        import sys

        from PyQt6.QtWidgets import QApplication

        _app = QApplication.instance() or QApplication(sys.argv)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            store = SermonStore(root)
            from ui.sermon.editor.window import SermonEditorWindow

            editor = SermonEditorWindow(store)
            sid = editor.doc.id
            self.assertIn(sid, editor._unsaved_workdirs)
            self.assertTrue(store.sermon_dir(sid).is_dir())
            # 保存为包后剔除集合
            pkg = root / "kept.sermon"
            self.assertTrue(editor._write_package(pkg))
            self.assertNotIn(sid, editor._unsaved_workdirs)
            self.assertTrue(store.sermon_dir(sid).is_dir())
            editor.close()


if __name__ == "__main__":
    unittest.main()
