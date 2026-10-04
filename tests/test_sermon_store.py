"""讲篇包加载：正常解压与路径穿越拒绝。"""

from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from core.sermon.model import new_document
from core.sermon.store import SermonStore


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


if __name__ == "__main__":
    unittest.main()
