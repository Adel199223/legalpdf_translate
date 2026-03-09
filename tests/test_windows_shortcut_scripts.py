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
    assert "register_edge_native_host.ps1" in text
    assert "refresh_icon_cache.ps1" in text
    assert "LegalPDFGmailFocusHost.exe" in text
    assert "& $registerHostScript -HostExePath $focusHostExePath" in text
    assert "& $shortcutScript" in text
    assert "& $refreshScript -Mode Recommended" in text


def test_refresh_icon_cache_script_supports_modes_and_clear_command() -> None:
    text = _read_script("scripts/refresh_icon_cache.ps1")
    assert '[ValidateSet("Recommended", "DeepClean")]' in text
    assert "-ClearIconCache" in text
    assert 'Start-Process "explorer.exe"' in text
    assert '-Filter "iconcache*"' in text


def test_register_edge_native_host_script_uses_python_module_and_dist_host() -> None:
    text = _read_script("scripts/register_edge_native_host.ps1")
    assert ".venv311\\Scripts\\python.exe" in text
    assert "LegalPDFGmailFocusHost.exe" in text
    assert "legalpdf_translate.gmail_focus_host --register --host-executable" in text


def test_install_local_script_registers_native_host_before_shortcut() -> None:
    text = _read_script("scripts/install_local.ps1")
    assert "register_edge_native_host.ps1" in text
    assert "LegalPDFGmailFocusHost.exe" in text
    assert "& $registerHostScript -HostExePath $focusHostPath" in text


def test_sync_loaded_gmail_extension_script_uses_edge_secure_preferences_and_robocopy() -> None:
    text = _read_script("scripts/sync_loaded_gmail_extension.ps1")
    assert "[string[]]$TargetPath = @()" in text
    assert "[switch]$ReportOnly" in text
    assert 'Join-Path $env:SystemRoot "System32\\robocopy.exe"' in text
    assert "Secure Preferences" in text
    assert "extensions/gmail_intake" in text
    assert "legalpdf_translate.gmail_focus_host --edge-extension-report" in text
    assert "Active Gmail intake extension IDs:" in text
    assert "Stale Gmail intake extension IDs:" in text
    assert "& $robocopyExe $sourcePath $targetPath /MIR" in text
    assert "Synced Gmail intake extension to:" in text
