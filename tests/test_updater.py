"""更新检查：版本比较（不访问网络）。"""

from __future__ import annotations

import sys
import unittest

from core.updater import (
    UpdateInfo,
    _candidate_download_urls,
    _parse_release_payload,
    is_newer,
    notes_request_force_update,
    parse_version,
    strip_force_update_marker,
)


class UpdaterVersionTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version("v2.1.0"), (2, 1, 0))
        self.assertEqual(parse_version("1.5"), (1, 5, 0))

    def test_is_newer(self):
        self.assertTrue(is_newer("2.2.0", "2.1.0"))
        self.assertFalse(is_newer("2.1.0", "2.1.0"))
        self.assertFalse(is_newer("2.0.0", "2.1.0"))
        self.assertTrue(is_newer("v2.1.1", "2.1.0"))

    def test_force_update_marker(self):
        from core import updater as updater_mod

        cleaned = strip_force_update_marker("<!-- force_update -->\n## 串珠修复")
        self.assertEqual(cleaned, "## 串珠修复")
        self.assertNotIn("force_update", cleaned)
        # 3.4.0 后总开关关闭：有标记也不强制
        self.assertFalse(updater_mod._FORCE_UPDATE_ENABLED)
        self.assertFalse(notes_request_force_update("<!-- force_update -->\n## 修复"))
        self.assertFalse(notes_request_force_update("## 普通更新\n无强制"))

    def test_parse_release_force_flag(self):
        payload = {
            "tag_name": "v3.4.0",
            "body": "<!-- force_update -->\n### 重要\n串珠修复",
            "assets": [
                {
                    "name": "Bible_Pro_Setup.exe",
                    "browser_download_url": (
                        "https://github.com/XiaoDong1213/bible_projection"
                        "/releases/download/v3.4.0/Bible_Pro_Setup.exe"
                    ),
                    "size": 12,
                }
            ],
        }
        info = _parse_release_payload(payload)
        self.assertIsNotNone(info)
        assert info is not None
        self.assertFalse(info.force)  # 总开关关闭
        self.assertEqual(info.version, "3.4.0")
        self.assertIn("串珠修复", info.notes)
        self.assertNotIn("force_update", info.notes)

        payload["body"] = "### 小改\n无标记"
        info2 = _parse_release_payload(payload)
        self.assertIsNotNone(info2)
        assert info2 is not None
        self.assertFalse(info2.force)

    def test_force_offer_dialog_rejects_stays_open(self):
        from PyQt6.QtWidgets import QApplication, QMainWindow

        from ui.update_prompt import UpdateController, UpdateOfferDialog

        app = QApplication.instance() or QApplication(sys.argv)
        info = UpdateInfo(
            version="3.4.0",
            download_url="https://example.com/x.exe",
            notes="重要",
            asset_name="Bible_Pro_Setup.exe",
            force=True,
        )
        dlg = UpdateOfferDialog(info)
        dlg.show()
        app.processEvents()
        dlg.reject()
        self.assertTrue(dlg.isVisible())
        dlg._force = False
        dlg.close()
        app.processEvents()

        host = QMainWindow()
        ctrl = UpdateController(host)
        ctrl._force = True
        ctrl._busy = True
        self.assertTrue(ctrl.blocks_app_close())
        ctrl._busy = False
        ctrl._offering = True
        self.assertTrue(ctrl.blocks_app_close())
        ctrl._force = False
        self.assertFalse(ctrl.blocks_app_close())
        host.close()

    def test_download_via_gh_proxy(self):
        official = "https://github.com/XiaoDong1213/bible_projection/releases/download/v2.1.0/Bible_Pro_Setup.exe"
        urls = _candidate_download_urls(official, version="2.1.0")
        # 前四个候选走 gh-proxy 双域名加速（官方直链 + 版本直链）
        for url in urls[:4]:
            self.assertTrue(
                url.startswith("https://gh-proxy.org/")
                or url.startswith("https://gh-proxy.com/"),
                url,
            )
        # latest 动态直链兜底在列
        self.assertTrue(any("/releases/latest/download/" in u for u in urls))
        # 直连兜底在列且排在加速候选之后
        self.assertIn(official, urls)
        self.assertGreater(urls.index(official), 3)
        self.assertFalse(any("gitea.cccccjd.cn" in u for u in urls))
        self.assertFalse(any("gh.acmsz.top" in u for u in urls))


if __name__ == "__main__":
    unittest.main()
