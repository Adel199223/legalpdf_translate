from __future__ import annotations

from pathlib import Path


def test_qt_spec_includes_keyring_hiddenimports() -> None:
    spec_path = Path("build/pyinstaller_qt.spec")
    text = spec_path.read_text(encoding="utf-8")
    assert "\"keyring\"" in text
    assert "\"keyring.backends.Windows\"" in text


def test_qt_spec_sets_exe_icon() -> None:
    spec_path = Path("build/pyinstaller_qt.spec")
    text = spec_path.read_text(encoding="utf-8")
    assert "\"LegalPDFTranslate.ico\"" in text
    assert "icon=str(icon_path)" in text


def test_qt_spec_bundles_resources_directory() -> None:
    spec_path = Path("build/pyinstaller_qt.spec")
    text = spec_path.read_text(encoding="utf-8")
    assert "(str(project_root / \"resources\"), \"resources\")" in text
