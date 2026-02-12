# -*- mode: python ; coding: utf-8 -*-

from glob import glob
from pathlib import Path

project_root = Path(SPECPATH).resolve().parents[0]


a = Analysis(
    [str(project_root / "src" / "legalpdf_translate" / "qt_main.py")],
    pathex=[str(project_root / "src"), str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "resources"), "resources"),
        *[(path, "resources/ui") for path in glob(str(project_root / "resources" / "ui" / "*.png"))],
    ],
    hiddenimports=[
        "legalpdf_translate.qt_gui.app_window",
        "legalpdf_translate.qt_gui.worker",
        "legalpdf_translate.qt_gui.styles",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LegalPDFTranslateQt",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="legalpdf_translate_qt",
)
