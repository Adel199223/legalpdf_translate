from __future__ import annotations

from pathlib import Path


def _read_script(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_create_shortcut_script_uses_ico_and_public_desktop_cleanup() -> None:
    text = _read_script("scripts/create_desktop_shortcut.ps1")
    assert "CommonDesktopDirectory" in text
    assert "^LegalPDF.*\\.lnk$" in text
    assert '$shortcut.IconLocation = "$icoPath,0"' in text
    assert 'Join-Path $desktopPath "LegalPDF Translate.lnk"' in text


def test_build_script_runs_shortcut_then_optional_icon_refresh() -> None:
    text = _read_script("scripts/build_qt.ps1")
    assert "[switch]$SkipIconRefresh" in text
    assert "create_desktop_shortcut.ps1" in text
    assert "refresh_icon_cache.ps1" in text
    assert "& $shortcutScript" in text
    assert "& $refreshScript -Mode Recommended" in text


def test_refresh_icon_cache_script_supports_modes_and_clear_command() -> None:
    text = _read_script("scripts/refresh_icon_cache.ps1")
    assert '[ValidateSet("Recommended", "DeepClean")]' in text
    assert "-ClearIconCache" in text
    assert 'Start-Process "explorer.exe"' in text
    assert '-Filter "iconcache*"' in text
