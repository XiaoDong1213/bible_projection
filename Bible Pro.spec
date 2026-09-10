# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH)
resources = project_root / "resources"

# Only package files required by the application.
# User configuration (config.ini) is intentionally NOT included.
a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(resources / "和合本.db"), "."),
        (str(resources / "icon.ico"), "."),
        (str(resources / "styles"), "styles"),
        (str(resources / "install.mark"), "."),
    ],
    hiddenimports=[
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        *collect_submodules("app"),
        *collect_submodules("core"),
        *collect_submodules("ui"),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Bible Pro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(resources / "icon.ico"),
    version=str(project_root / "file_version_info.txt"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Bible Pro",
)
