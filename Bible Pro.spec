# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH)
resources = project_root / "resources"

# Only package files required by the application.
# User configuration (config.ini) is intentionally NOT included.
# All bible translations (*.db in resources/) ship with the installer;
# 和合本.db stays the default until the user picks another version.
a = Analysis(
    ["main.py"],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        *[(str(db), ".") for db in sorted(resources.glob("*.db"))],
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
    # 排除标准库中用不到的大模块：dll/pyd 更少，杀软启动扫描更快
    excludes=["tkinter", "unittest", "pydoc_data", "xmlrpc", "lib2to3"],
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
    # UPX 壳是杀软重点扫描对象（深度扫描拖慢启动、还易误报），禁用
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="Bible Pro",
)
