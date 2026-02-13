# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

spec_root = Path(SPECPATH).resolve()
candidates = [spec_root, spec_root.parent]
project_root = None
for candidate in candidates:
    entry_candidate = candidate / "src" / "legalpdf_translate" / "qt_main.py"
    icon_candidate = candidate / "resources" / "icons" / "LegalPDFTranslate.ico"
    if entry_candidate.exists() and icon_candidate.exists():
        project_root = candidate
        break
if project_root is None:
    raise RuntimeError(
        f"Could not resolve project root from SPECPATH={SPECPATH}. "
        "Expected src/legalpdf_translate/qt_main.py and resources/icons/LegalPDFTranslate.ico."
    )

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
