# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

project_root = Path(SPECPATH).resolve().parents[0]
entry_script = project_root / "src" / "legalpdf_translate" / "qt_main.py"
icon_path = project_root / "resources" / "icons" / "LegalPDFTranslate.ico"


a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src"), str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "resources"), "resources"),
    ],
    hiddenimports=[
        "legalpdf_translate.qt_app",
        "legalpdf_translate.qt_gui.app_window",
        "legalpdf_translate.qt_gui.dialogs",
        "legalpdf_translate.qt_gui.worker",
        "legalpdf_translate.qt_gui.styles",
        "keyring",
        "keyring.backends.Windows",
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
    name="LegalPDFTranslate",
    icon=str(icon_path),
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
    name="legalpdf_translate",
)
