"""更新检查：版本比较（不访问网络）。"""

from __future__ import annotations

import unittest

from core.updater import _candidate_download_urls, is_newer, parse_version


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

    def test_download_only_fast_proxy(self):
        official = "https://github.com/XiaoDong1213/bible_projection/releases/download/v2.1.0/Bible_Pro_Setup.exe"
        urls = _candidate_download_urls(official, version="2.1.0")
        self.assertTrue(all(u.startswith("https://gh.acmsz.top/") for u in urls))
        self.assertFalse(any("gitea.cccccjd.cn" in u for u in urls))
        self.assertFalse(any(u == official for u in urls))


if __name__ == "__main__":
    unittest.main()
