from __future__ import annotations

from pathlib import Path


def test_qt_spec_includes_keyring_hiddenimports() -> None:
    spec_path = Path("build/pyinstaller_qt.spec")
    text = spec_path.read_text(encoding="utf-8")
    assert "\"keyring\"" in text
    assert "\"keyring.backends.Windows\"" in text
