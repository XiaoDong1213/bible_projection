"""WPS / PowerPoint 探测与打开路径。"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from core.sermon.office_bridge import (
    find_presentation_exes,
    find_wps_presentation_exe,
    open_in_office,
    presentation_app_available,
)


class WpsOfficeTests(unittest.TestCase):
    def test_find_wps_on_this_machine_or_none(self):
        # 本机若已装 WPS，应能解析到 wpp.exe
        exe = find_wps_presentation_exe()
        if exe is not None:
            self.assertEqual(exe.name.lower(), "wpp.exe")
            self.assertTrue(exe.is_file())

    def test_presentation_available_is_bool(self):
        self.assertIsInstance(presentation_app_available(), bool)

    def test_open_prefers_wps_when_present(self):
        fake_wps = Path("C:/fake/office6/wpp.exe")
        fake_ppt = Path("C:/fake/POWERPNT.EXE")
        calls: list[list[str]] = []

        def fake_popen(args, **kwargs):
            calls.append(list(args))

            class _P:
                pass

            return _P()

        with mock.patch(
            "core.sermon.office_bridge.find_wps_presentation_exe",
            return_value=fake_wps,
        ), mock.patch(
            "core.sermon.office_bridge.find_powerpoint_exe",
            return_value=fake_ppt,
        ), mock.patch(
            "core.sermon.office_bridge.subprocess.Popen",
            side_effect=fake_popen,
        ), mock.patch.object(Path, "is_file", return_value=True):
            ok = open_in_office(Path("C:/tmp/demo.pptx"), prefer_wps=True)
        self.assertTrue(ok)
        self.assertTrue(calls)
        self.assertTrue(str(calls[0][0]).lower().endswith("wpp.exe"))

    def test_find_presentation_exes_order(self):
        fake_wps = Path("C:/fake/wpp.exe")
        fake_ppt = Path("C:/fake/POWERPNT.EXE")
        with mock.patch(
            "core.sermon.office_bridge.find_wps_presentation_exe",
            return_value=fake_wps,
        ), mock.patch(
            "core.sermon.office_bridge.find_powerpoint_exe",
            return_value=fake_ppt,
        ):
            ordered = find_presentation_exes(prefer_wps=True)
        self.assertEqual(ordered[0], fake_wps)
        self.assertEqual(ordered[1], fake_ppt)


if __name__ == "__main__":
    unittest.main()
