from __future__ import annotations

import http.client
import json
import socket
import time
from pathlib import Path

import pytest

from legalpdf_translate.gmail_intake import InboundMailContext, LocalGmailIntakeBridge


def _reserve_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _request(
    *,
    method: str,
    port: int,
    token: str,
    body: object | None = None,
    content_type: str = "application/json",
) -> tuple[int, dict[str, object]]:
    encoded_body = b"" if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": content_type,
    }
    if encoded_body:
        headers["Content-Length"] = str(len(encoded_body))

    deadline = time.time() + 1.0
    while True:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2.0)
        try:
            connection.request(method, "/gmail-intake", body=encoded_body or None, headers=headers)
            response = connection.getresponse()
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
        except ConnectionRefusedError:
            if time.time() >= deadline:
                raise
            time.sleep(0.02)
        finally:
            connection.close()


def test_local_gmail_intake_bridge_accepts_valid_context() -> None:
    accepted: list[InboundMailContext] = []
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=accepted.append,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="shared-token",
            body={
                "message_id": "18f43f6f2f8c0a11",
                "thread_id": "18f43f6f2f8c0a10",
                "subject": "Urgent filing",
                "account_email": "lawyer@example.com",
            },
        )
        assert bridge.url == f"http://127.0.0.1:{bridge.port}/gmail-intake"
        assert status == 200
        assert payload["status"] == "accepted"
        assert accepted == [
            InboundMailContext(
                message_id="18f43f6f2f8c0a11",
                thread_id="18f43f6f2f8c0a10",
                subject="Urgent filing",
                account_email="lawyer@example.com",
            )
        ]
    finally:
        bridge.stop()
    assert bridge.is_running is False


def test_local_gmail_intake_bridge_rejects_invalid_token() -> None:
    accepted: list[InboundMailContext] = []
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=accepted.append,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="wrong-token",
            body={
                "message_id": "msg-1",
                "thread_id": "thread-1",
                "subject": "",
            },
        )
        assert status == 401
        assert payload["code"] == "invalid_token"
        assert accepted == []
    finally:
        bridge.stop()


def test_local_gmail_intake_bridge_rejects_unknown_payload_fields() -> None:
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=lambda _context: None,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="shared-token",
            body={
                "message_id": "msg-1",
                "thread_id": "thread-1",
                "subject": "Subject",
                "extra": "not-allowed",
            },
        )
        assert status == 400
        assert payload["code"] == "invalid_payload"
        assert "Unknown keys" in str(payload["message"])
    finally:
        bridge.stop()


def test_local_gmail_intake_bridge_rejects_blank_message_identity() -> None:
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=lambda _context: None,
    )
    bridge.start()
    try:
        status, payload = _request(
            method="POST",
            port=bridge.port,
            token="shared-token",
            body={
                "message_id": "   ",
                "thread_id": "thread-1",
                "subject": "Subject",
            },
        )
        assert status == 400
        assert payload["code"] == "invalid_payload"
        assert payload["message"] == "message_id must be non-empty."
    finally:
        bridge.stop()


def test_local_gmail_intake_bridge_requires_localhost_binding() -> None:
    bridge = LocalGmailIntakeBridge(
        port=_reserve_port(),
        token="shared-token",
        on_context=lambda _context: None,
        host="0.0.0.0",
    )
    with pytest.raises(ValueError, match="127.0.0.1"):
        bridge.start()


def test_gmail_extension_manifest_is_gmail_only_and_localhost_only() -> None:
    extension_dir = Path(__file__).resolve().parents[1] / "extensions" / "gmail_intake"
    manifest = json.loads((extension_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 3
    assert manifest["permissions"] == ["activeTab", "nativeMessaging", "scripting", "storage", "tabs"]
    assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
    assert manifest["key"].startswith("MIIBIjAN")
    assert manifest["options_page"] == "options.html"
    assert manifest["background"]["service_worker"] == "background.js"
    assert manifest["content_scripts"] == [
        {
            "matches": ["https://mail.google.com/*"],
            "js": ["content.js"],
            "run_at": "document_idle",
        }
    ]


def test_gmail_extension_scripts_keep_stage_one_contract_markers() -> None:
    extension_dir = Path(__file__).resolve().parents[1] / "extensions" / "gmail_intake"
    background_js = (extension_dir / "background.js").read_text(encoding="utf-8")
    content_js = (extension_dir / "content.js").read_text(encoding="utf-8")

    assert "Authorization" in background_js
    assert "http://127.0.0.1:" in background_js
    assert "/gmail-intake" in background_js
    assert "chrome.scripting.executeScript" in background_js
    assert 'type: "gmail-intake-ping"' in background_js
    assert 'files: ["content.js"]' in background_js
    assert "showFallbackBanner" in background_js
    assert "chrome.runtime.sendNativeMessage" in background_js
    assert "com.legalpdf.gmail_focus" in background_js
    assert 'action: "prepare_gmail_intake"' in background_js
    assert "chrome.storage.local.get" in background_js
    assert "includeToken" in background_js
    assert "requestFocus" in background_js
    assert "launch_timeout" in background_js
    assert "auto-launch is not available from this checkout" in background_js
    assert "Gmail bridge is not configured in LegalPDF Translate." in background_js
    assert "LegalPDF Translate native host is unavailable. Reload the extension or open the options page." in background_js
    assert "chrome.tabs.reload" not in background_js
    assert "bypassCache: true" not in background_js
    assert "waitForLaunchedBrowserAppTab" in background_js
    assert "nativeResponse.launched === true" in background_js
    assert "The browser app may still need manual focus." in background_js
    assert "candidates.find((tab) => Number.isInteger(tab.id))" in background_js
    assert "chrome.tabs.update(existing.id, { active: true, url: targetUrl })" in background_js
    assert "Bridge token is missing in extension options." not in background_js
    assert background_js.index("chrome.runtime.sendNativeMessage") < background_js.index("await postContext")
    assert background_js.index("browserAppOpened = await openOrFocusBrowserApp") < background_js.index("await postContext")
    assert "[data-message-id][data-legacy-message-id]" in content_js
    assert "data-legacy-thread-id" in content_js
    assert "h2.hP" in content_js
    assert "__legalPdfGmailIntakeLoaded" in content_js
    assert 'message.type === "gmail-intake-ping"' in content_js


def test_gmail_extension_options_page_is_diagnostics_first() -> None:
    extension_dir = Path(__file__).resolve().parents[1] / "extensions" / "gmail_intake"
    options_js = (extension_dir / "options.js").read_text(encoding="utf-8")
    options_html = (extension_dir / "options.html").read_text(encoding="utf-8")

    assert 'action: "prepare_gmail_intake"' in options_js
    assert "requestFocus: false" in options_js
    assert "includeToken: false" in options_js
    assert "Auto-configured from LegalPDF Translate" in options_js
    assert "Native host unavailable" in options_js
    assert "formatNativeHostError" in options_js
    assert "toolbar clicks can auto-start the app" in options_js
    assert "Launch Target" in options_html
    assert "Auto-launch" in options_html
    assert "Native Host Error" in options_html
    assert "Refresh Diagnostics" in options_html
    assert "Raw bridge tokens stay hidden here." in options_html
    assert "Legacy fallback" in options_html
    assert "bridgeToken" not in options_html
