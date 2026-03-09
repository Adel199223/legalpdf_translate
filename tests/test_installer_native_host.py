from __future__ import annotations

from pathlib import Path


def test_installer_registers_edge_native_host_and_manifest() -> None:
    text = Path("installer/legalpdf_translate.iss").read_text(encoding="utf-8")

    assert 'EdgeNativeHostName "com.legalpdf.gmail_focus"' in text
    assert 'Software\\Microsoft\\Edge\\NativeMessagingHosts\\{#EdgeNativeHostName}' in text
    assert '{app}\\native_messaging\\{#EdgeNativeHostName}.edge.json' in text
    assert "{app}\\LegalPDFGmailFocusHost.exe" in text
    assert "SaveStringToFile(ManifestPath, EdgeNativeHostManifestText(HostExePath), False);" in text
    assert 'chrome-extension://afckgbhjkmojchdlinolkepffchlgpin/' in text
