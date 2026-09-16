"""Construction and the enumerated bootstrap GETs must not cross live boundaries."""

from __future__ import annotations

from pathlib import Path
import subprocess

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import power_tools_service, translation_service
from legalpdf_translate.shadow_web import app as browser


_GET_ROUTES = (
    "/api/bootstrap",
    "/api/capabilities",
    "/api/bootstrap/shell",
    "/api/bootstrap/shell/ready",
    "/api/settings/admin",
    "/api/power-tools/bootstrap",
    "/api/extension/diagnostics",
    "/api/gmail/bootstrap",
    "/api/translation/bootstrap",
    "/api/interpretation/google-photos/status",
)


def test_injected_offline_bundle_constructs_and_serves_get_payloads_without_live_probes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_root = tmp_path / "isolated-browser-state"
    services = browser.offline_browser_app_services(state_root=state_root)

    def forbidden(*_args, **_kwargs):
        pytest.fail("A global credential, Gmail, Photos, Word, provider, native, or process boundary ran")

    for name in (
        "detect_runtime_build_identity",
        "detect_shadow_runtime_paths",
        "detect_browser_data_paths",
        "classify_shadow_listener",
        "run_browser_automation_preflight",
        "latest_window_trace_status",
        "build_browser_bootstrap",
        "build_power_tools_bootstrap",
        "build_translation_bootstrap",
        "build_google_photos_status",
        "build_extension_lab_summary",
        "build_browser_provider_state",
        "build_browser_capability_snapshot",
        "inspect_edge_native_host",
        "document_runtime_state_payload",
        "load_settings_from_path",
        "GmailBrowserSessionManager",
        "TranslationJobManager",
        "BrowserSourceReviewManager",
        "ArabicDocxReviewManager",
        "BrowserLiveGmailBridgeManager",
    ):
        monkeypatch.setattr(browser, name, forbidden)
    monkeypatch.setattr(translation_service, "resolve_openai_key_with_source", forbidden)
    monkeypatch.setattr(translation_service, "resolve_ocr_api_key", forbidden)
    monkeypatch.setattr(power_tools_service, "resolve_openai_key_with_source", forbidden)
    monkeypatch.setattr(power_tools_service, "_resolve_ocr_api_key_source_for_browser", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)

    app = browser.create_shadow_app(
        repo_root=tmp_path / "empty-repo",
        port=18877,
        enable_live_gmail_bridge=True,
        services=services,
    )
    assert app.state.shadow_context.services is services
    assert app.state.shadow_context.server_runtime_paths.app_data_dir.is_relative_to(state_root)

    with TestClient(app) as client:
        for route in _GET_ROUTES:
            response = client.get(f"{route}?mode=live&workspace=offline-proof")
            assert response.status_code == 200, (route, response.text)
            payload = response.json()
            assert set(payload) == {
                "status",
                "normalized_payload",
                "diagnostics",
                "capability_flags",
            }
            assert payload["status"] == "ok"

        disabled = client.post("/api/translation/source-reviews/prepare?mode=live&workspace=offline-proof",
                               json={"form_values": {}})
        assert disabled.status_code == 409
        assert disabled.json()["diagnostics"] == {"error": "source_review_disabled"}
        assert disabled.json()["normalized_payload"] == {}

        capabilities = client.get(
            "/api/capabilities?mode=live&workspace=offline-proof"
        ).json()["capability_flags"]
        for capability in (
            "translation",
            "ocr",
            "gmail",
            "word_pdf_export",
            "gmail_bridge",
            "native_host",
            "document_runtime",
        ):
            assert capabilities[capability]["status"] == "not_evaluated"
        assert capabilities["translation"]["credentials_configured"] is False

        photos = client.get(
            "/api/interpretation/google-photos/status?mode=live&workspace=offline-proof"
        ).json()
        assert photos["capability_flags"]["google_photos"]["status"] == "not_evaluated"
        assert photos["normalized_payload"]["google_photos"]["connected"] is False

    assert not (state_root / "data" / "live-request" / "settings.json").exists()
