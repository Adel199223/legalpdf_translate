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

gui_entry_script = project_root / "src" / "legalpdf_translate" / "qt_main.py"
host_entry_script = project_root / "src" / "legalpdf_translate" / "gmail_focus_host.py"
icon_path = project_root / "resources" / "icons" / "LegalPDFTranslate.ico"
common_pathex = [str(project_root / "src"), str(project_root)]

gui_a = Analysis(
    [str(gui_entry_script)],
    pathex=common_pathex,
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
gui_pyz = PYZ(gui_a.pure)

gui_exe = EXE(
    gui_pyz,
    gui_a.scripts,
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

host_a = Analysis(
    [str(host_entry_script)],
    pathex=common_pathex,
    binaries=[],
    datas=[],
    hiddenimports=[
        "legalpdf_translate.gmail_focus",
        "legalpdf_translate.user_settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PyQt6", "PySide2"],
    noarchive=False,
)
host_pyz = PYZ(host_a.pure)

host_exe = EXE(
    host_pyz,
    host_a.scripts,
    [],
    exclude_binaries=True,
    name="LegalPDFGmailFocusHost",
    icon=str(icon_path),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    gui_exe,
    gui_a.binaries,
    gui_a.datas,
    host_exe,
    host_a.binaries,
    host_a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="legalpdf_translate",
)
