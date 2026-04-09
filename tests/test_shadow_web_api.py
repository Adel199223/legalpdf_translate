from __future__ import annotations

import io
import json
from pathlib import Path
import re

from fastapi.testclient import TestClient
from PIL import Image

import legalpdf_translate.browser_arabic_review as browser_arabic_review
import legalpdf_translate.browser_app_service as browser_app_service
from legalpdf_translate.browser_gmail_bridge import BrowserLiveBridgeSyncResult
from legalpdf_translate.power_tools_service import generate_browser_run_report
import legalpdf_translate.shadow_web.app as shadow_app_module
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.interpretation_service import InterpretationValidationError
from legalpdf_translate.shadow_runtime import BrowserDataPaths, ShadowListenerOwnership, ShadowRuntimePaths
from legalpdf_translate.word_automation import WordAutomationResult


_ORIGINAL_BUILD_BROWSER_PROVIDER_STATE = shadow_app_module.build_browser_provider_state


def _identity() -> RuntimeBuildIdentity:
    return RuntimeBuildIdentity(
        worktree_path="C:/Users/FA507/.codex/legalpdf_translate_beginner_first_ux",
        branch="codex/beginner-first-primary-flow-ux",
        head_sha="5c9842e",
        labels=("shadow-web",),
        is_canonical=False,
        is_lineage_valid=True,
        canonical_worktree_path="C:/Users/FA507/.codex/legalpdf_translate",
        canonical_branch="main",
        approved_base_branch="main",
        approved_base_head_floor="506dee6",
        canonical_head_floor="506dee6",
        reasons=("noncanonical",),
    )


def _canonical_identity() -> RuntimeBuildIdentity:
    return RuntimeBuildIdentity(
        worktree_path="C:/Users/FA507/.codex/legalpdf_translate",
        branch="main",
        head_sha="5c9842e",
        labels=("shadow-web",),
        is_canonical=True,
        is_lineage_valid=True,
        canonical_worktree_path="C:/Users/FA507/.codex/legalpdf_translate",
        canonical_branch="main",
        approved_base_branch="main",
        approved_base_head_floor="506dee6",
        canonical_head_floor="506dee6",
        reasons=(),
    )


def _runtime_paths(tmp_path: Path) -> ShadowRuntimePaths:
    app_data_dir = tmp_path / "shadow"
    return ShadowRuntimePaths(
        app_data_dir=app_data_dir,
        settings_path=app_data_dir / "settings.json",
        job_log_db_path=app_data_dir / "job_log.sqlite3",
        outputs_dir=app_data_dir / "outputs",
        uploads_dir=app_data_dir / "uploads",
        runtime_metadata_path=app_data_dir / "shadow_runtime.json",
    )


def _browser_data_paths(tmp_path: Path, mode: str) -> BrowserDataPaths:
    root = tmp_path / ("live" if mode == "live" else "shadow")
    return BrowserDataPaths(
        mode=mode,
        label="Live App Data" if mode == "live" else "Isolated Test Data",
        app_data_dir=root,
        settings_path=root / "settings.json",
        job_log_db_path=root / "job_log.sqlite3",
        outputs_dir=root / "outputs",
        live_data=mode == "live",
        banner_text="LIVE APP DATA" if mode == "live" else "",
    )


def _native_host_state(*, ready: bool = True, repairable: bool = True) -> dict[str, object]:
    return {
        "configured": True,
        "ready": ready,
        "reason": "native_host_ready" if ready else "native_host_manifest_drift",
        "message": "Edge native host is registered and passed self-test." if ready else "Edge native host needs repair.",
        "registry_key_path": r"HKCU\Software\Microsoft\Edge\NativeMessagingHosts\com.legalpdf.gmail_focus",
        "registered_manifest_path": "C:/tmp/native_host.edge.json",
        "expected_manifest_path": "C:/tmp/native_host.edge.json",
        "manifest_exists": True,
        "manifest_matches_expected": ready,
        "registered_host_path": "C:/tmp/LegalPDFGmailFocusHost.cmd",
        "host_exists": True,
        "wrapper_path": "C:/tmp/LegalPDFGmailFocusHost.cmd",
        "wrapper_exists": True,
        "wrapper_target_python": "C:/tmp/python.exe",
        "self_test_ok": ready,
        "self_test_status": "ok" if ready else "failed",
        "self_test_reason": "native_host_self_test_ok" if ready else "native_host_self_test_failed",
        "self_test_payload": {"ok": ready},
        "repair_supported": True,
        "repairable": repairable,
        "repair_reason": "packaged_host_ready" if repairable else "launch_runtime_broken",
        "repair_target_kind": "checkout_wrapper",
        "repair_target_python": "C:/tmp/python.exe",
        "repair_recommended": not ready and repairable,
        "current_runtime_python": "C:/tmp/python.exe",
    }


def _build_app(tmp_path: Path, monkeypatch, *, build_identity: RuntimeBuildIdentity | None = None) -> TestClient:
    identity = build_identity or _identity()
    monkeypatch.setattr(shadow_app_module, "detect_runtime_build_identity", lambda **kwargs: identity)
    monkeypatch.setattr(
        shadow_app_module,
        "detect_shadow_runtime_paths",
        lambda **kwargs: _runtime_paths(tmp_path),
    )
    monkeypatch.setattr(
        shadow_app_module,
        "run_browser_automation_preflight",
        lambda **kwargs: {
            "preferred_host_status": "unavailable",
            "toolchain": {
                "playwright_available": False,
            },
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "detect_browser_data_paths",
        lambda mode, **kwargs: _browser_data_paths(tmp_path, mode),
    )
    if shadow_app_module.build_browser_provider_state is _ORIGINAL_BUILD_BROWSER_PROVIDER_STATE:
        monkeypatch.setattr(
            shadow_app_module,
            "build_browser_provider_state",
            lambda **kwargs: {"native_host": _native_host_state()},
        )
    app = shadow_app_module.create_shadow_app(repo_root=tmp_path, port=8877, enable_live_gmail_bridge=False)
    return TestClient(app)


def _completed_ar_job(docx_path: Path, *, job_id: str = "tx-ar-001") -> dict[str, object]:
    return {
        "job_id": job_id,
        "job_kind": "translate",
        "status": "completed",
        "config": {
            "source_path": str(docx_path.with_name("source.pdf")),
            "target_lang": "AR",
            "start_page": 1,
        },
        "result": {
            "save_seed": {
                "translation_date": "2026-04-02",
                "case_number": "305/23.2GCBJA",
                "case_entity": "Juizo Local Criminal de Beja",
                "case_city": "Beja",
                "court_email": "beja.judicial@tribunais.org.pt",
                "run_id": "20260402_164400",
                "target_lang": "AR",
                "pages": 5,
                "word_count": 980,
                "rate_per_word": 0.08,
                "expected_total": 78.4,
                "amount_paid": 0,
                "api_cost": 3.2,
                "profit": 75.2,
                "output_docx": str(docx_path),
            },
            "run_dir": str(docx_path.parent / "run"),
        },
        "artifacts": {
            "output_docx": str(docx_path),
            "run_dir": str(docx_path.parent / "run"),
        },
    }


def test_compute_browser_asset_version_changes_for_dirty_static_edits(tmp_path: Path) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    target = static_dir / "browser_pdf.js"
    target.write_text("console.log('one');\n", encoding="utf-8")
    version_one = shadow_app_module.compute_browser_asset_version(static_dir)
    target.write_text("console.log('two');\n", encoding="utf-8")
    version_two = shadow_app_module.compute_browser_asset_version(static_dir)
    assert version_one != version_two


def test_shadow_web_bootstrap_and_save_row_flow(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        bootstrap = client.get("/api/bootstrap")
        assert bootstrap.status_code == 200
        assert bootstrap.headers["cache-control"] == "no-store"
        bootstrap_payload = bootstrap.json()
        assert bootstrap_payload["status"] == "ok"
        assert bootstrap_payload["normalized_payload"]["runtime"]["port"] == 8877
        assert bootstrap_payload["normalized_payload"]["runtime"]["runtime_mode"] == "live"
        assert bootstrap_payload["normalized_payload"]["runtime"]["build_identity"]["is_canonical"] is True
        assert bootstrap_payload["normalized_payload"]["runtime"]["build_identity"]["reasons"] == []
        assert bootstrap_payload["normalized_payload"]["blank_seed"]["service_date"] == ""
        assert any(item["id"] == "gmail-intake" for item in bootstrap_payload["normalized_payload"]["navigation"])
        assert any(item["id"] == "extension-lab" for item in bootstrap_payload["normalized_payload"]["navigation"])
        assert any(item["id"] == "power-tools" for item in bootstrap_payload["normalized_payload"]["navigation"])
        assert "settings_admin" in bootstrap_payload["normalized_payload"]
        assert "power_tools" in bootstrap_payload["normalized_payload"]
        assert bootstrap_payload["normalized_payload"]["parity_audit"]["promotion_recommendation"]["status"] == "ready_for_daily_use"
        assert "interpretation_reference" in bootstrap_payload["normalized_payload"]
        assert "Vidigueira" in bootstrap_payload["normalized_payload"]["interpretation_reference"]["available_cities"]
        assert bootstrap_payload["normalized_payload"]["interpretation_reference"]["travel_origin_label"] == "Marmelar"

        save = client.post(
            "/api/interpretation/save-row",
            json={
                "form_values": {
                    "case_number": "1095/25.0T8BJA",
                    "court_email": "beja.trabalho.ministeriopublico@tribunais.org.pt",
                    "case_entity": "Tribunal do Trabalho",
                    "case_city": "Beja",
                    "service_entity": "Tribunal do Trabalho",
                    "service_city": "Beja",
                    "service_date": "2026-02-26",
                    "travel_km_outbound": "39",
                    "pages": "0",
                    "word_count": "0",
                    "rate_per_word": "0",
                    "expected_total": "0",
                    "amount_paid": "0",
                    "api_cost": "0",
                    "profit": "0",
                },
                "service_same_checked": True,
                "use_service_location_in_honorarios_checked": False,
                "include_transport_sentence_in_honorarios_checked": True,
            },
        )
        save_payload = save.json()
        assert save.status_code == 200
        assert save_payload["status"] == "ok"
        assert save_payload["saved_result"]["row_id"] > 0

        history = client.get("/api/interpretation/history")
        history_payload = history.json()
        assert history.status_code == 200
        assert len(history_payload["normalized_payload"]["history"]) == 1


def test_shadow_web_index_contains_beginner_first_shell_sections(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        text = response.text
        match = re.search(r'assetVersion: "([^"]+)"', text)
        assert match is not None
        asset_version = match.group(1)
        assert f'href="http://testserver/static-build/{asset_version}/style.css"' in text
        assert f'src="http://testserver/static-build/{asset_version}/app.js"' in text
        assert f'staticBasePath: "http://testserver/static-build/{asset_version}/"' in text
        assert "buildIdentity:" in text
        assert 'defaultRuntimeMode: "live"' in text
        assert 'defaultUiVariant: "qt"' in text
        assert "LEGALPDF_BROWSER_CLIENT_READY" in text
        assert 'document.body.dataset.clientReady = "warming"' in text
        assert 'document.body.dataset.clientWorkspace = workspaceId' in text
        assert "Simple Workspace Shell" in text
        assert 'data-view="gmail-intake"' in text
        assert 'data-view="new-job"' in text
        assert 'id="section-nav"' in text
        assert 'id="more-nav-shell"' in text
        assert 'id="operator-mode-toggle"' in text
        assert "More" in text
        assert "Operator Details" in text
        assert 'class="sidebar-card operator-only"' in text
        assert 'class="details-panel operator-only"' in text
        assert 'id="new-job-task-switcher"' in text
        assert 'id="gmail-workspace-strip"' in text
        assert 'id="gmail-workspace-strip-action"' in text
        assert "Gmail Handoff" in text
        assert "Focused Intake Review" in text
        assert "Message Details and Overrides" in text
        assert "Open Attachment Review" in text
        assert 'id="gmail-resume-step"' in text
        assert 'id="gmail-resume-result"' in text
        assert 'id="gmail-open-full-workspace"' in text
        assert 'id="gmail-open-session"' not in text
        assert 'id="gmail-preview-session"' not in text
        assert 'id="gmail-review-drawer"' in text
        assert 'id="gmail-review-drawer-backdrop"' in text
        assert 'id="gmail-close-review-drawer"' in text
        assert 'id="gmail-review-summary"' in text
        assert 'id="gmail-review-summary-details"' in text
        assert 'id="gmail-review-summary-grid"' in text
        assert 'id="gmail-noncanonical-runtime-guard"' in text
        assert 'id="gmail-restart-canonical-runtime"' in text
        assert 'id="gmail-continue-noncanonical-runtime"' not in text
        assert 'id="gmail-review-detail"' in text
        assert 'id="gmail-preview-drawer"' in text
        assert 'id="gmail-preview-drawer-backdrop"' in text
        assert 'id="gmail-close-preview-drawer"' in text
        assert 'id="gmail-preview-frame"' in text
        assert 'id="gmail-preview-page"' in text
        assert 'id="gmail-preview-open-tab"' in text
        assert 'id="gmail-preview-apply"' in text
        assert "Gmail Attachment Review" in text
        assert "Attachments" in text
        assert "Current Attachment" in text
        assert "Attachment Preview" in text
        assert "Preview the selected attachment to inspect it here." not in text
        assert 'id="gmail-session-banner"' not in text
        assert 'id="gmail-session-drawer"' in text
        assert 'id="gmail-session-drawer-backdrop"' in text
        assert 'id="gmail-close-session-drawer"' in text
        assert "Job Setup" in text
        assert "Run Status" in text
        assert "Start Translate" in text
        assert "Advanced Settings" in text
        assert 'id="translation-open-completion"' in text
        assert 'id="translation-completion-drawer"' in text
        assert 'id="translation-completion-drawer-backdrop"' in text
        assert 'id="translation-close-completion"' in text
        assert 'id="translation-arabic-review-card"' in text
        assert 'id="translation-arabic-review-open"' in text
        assert 'id="translation-arabic-review-continue-now"' in text
        assert 'id="translation-arabic-review-continue-without-changes"' in text
        assert "align or edit it manually" in text
        assert 'id="translation-gmail-step-card"' in text
        assert 'id="translation-gmail-confirm-current"' in text
        assert '<select id="case-city"' in text
        assert '<select id="service-city"' in text
        assert 'id="case-city-add"' in text
        assert 'id="service-city-add"' in text
        assert 'id="interpretation-location-guard-card"' in text
        assert 'id="travel-km-hint"' in text
        assert 'id="interpretation-city-dialog-backdrop"' in text
        assert 'id="interpretation-city-dialog-name"' in text
        assert 'id="interpretation-city-dialog-distance"' in text
        assert "Preview the selected attachment to inspect it here." not in text
        assert "Finish Translation" in text
        assert "Completion Surface" in text
        assert "Export Review Queue" in text
        assert 'id="settings-credentials-section"' in text
        assert 'id="settings-translation-key-input"' in text
        assert 'id="settings-save-translation-key"' in text
        assert 'id="settings-clear-translation-key"' in text
        assert 'id="settings-ocr-key-input"' in text
        assert 'id="settings-save-ocr-key"' in text
        assert 'id="settings-clear-ocr-key"' in text
        assert 'id="settings-native-host-state"' in text
        assert 'id="settings-test-native-host"' in text
        assert 'id="settings-repair-native-host"' in text
        assert 'id="settings-word-pdf-export-state"' in text
        assert 'id="settings-test-word-pdf"' in text
        assert "Credential Recovery" in text
        assert 'id="gmail-batch-finalize-drawer"' in text
        assert 'id="gmail-batch-finalize-drawer-backdrop"' in text
        assert 'id="gmail-batch-finalize-run"' in text
        assert 'id="gmail-batch-finalize-report"' in text
        assert "Finalize Gmail Batch" in text
        assert "Run Metrics (auto-filled)" in text
        assert "Amounts (EUR)" in text
        assert "Current Interpretation Step" in text
        assert 'id="interpretation-session-shell"' in text
        assert 'id="interpretation-session-result"' in text
        assert 'id="interpretation-session-primary"' in text
        assert 'id="interpretation-session-open-full-workspace"' in text
        assert 'class="workspace-drawer workspace-drawer-interpretation"' in text
        assert "Interpretation Intake" in text
        assert "Seed Review" in text
        assert 'id="interpretation-open-review"' in text
        assert 'id="interpretation-review-drawer"' in text
        assert 'id="interpretation-review-drawer-backdrop"' in text
        assert 'id="interpretation-review-summary-card"' in text
        assert 'id="interpretation-review-context-card"' in text
        assert 'id="interpretation-review-context-title"' in text
        assert 'id="interpretation-completion-card"' in text
        assert 'id="interpretation-review-details"' in text
        assert 'id="interpretation-review-details-summary"' in text
        assert 'id="interpretation-finalize-gmail"' in text
        assert 'id="interpretation-gmail-result"' in text
        assert 'id="interpretation-gmail-next-step-card"' not in text
        assert 'id="interpretation-open-gmail-session"' not in text
        assert "SERVICE" in text
        assert "RECIPIENT" in text
        assert "Continue In Translation" in text
        assert "Continue In Interpretation" in text
        assert 'data-view="recent-jobs"' in text
        assert "Bounded Review Flow" in text
        assert "Recent Translation Runs" in text
        assert "Translation Job Log History" in text
        assert "Interpretation History" in text
        assert 'data-view="settings"' in text
        assert 'id="settings-defaults-section"' in text
        assert 'id="settings-integrations-section"' in text
        assert 'id="settings-ops-section"' in text
        assert "Provider and Host Preflight" in text
        assert 'data-view="profile"' in text
        assert "One Profile At A Time" in text
        assert 'id="profile-editor-drawer"' in text
        assert 'id="profile-editor-drawer-backdrop"' in text
        assert 'id="profile-close-editor"' in text
        assert 'id="profile-close-editor-footer"' in text
        assert 'data-view="power-tools"' in text
        assert "bounded tool stack" in text
        assert 'data-view="extension-lab"' in text
        assert "bounded operator lab" in text
        assert "workspace-panel-gmail-session" not in text
        assert 'id="translation-postrun-panel"' not in text
        assert 'id="interpretation-export-panel"' not in text


def test_shadow_web_runtime_ready_endpoint_exposes_lightweight_readiness(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        shadow_app_module,
        "latest_window_trace_status",
        lambda _base_dir: {
            "launch_session_id": "launch-rt-1",
            "status": "trace_started",
        },
    )
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        context = client.app.state.shadow_context
        context.live_gmail_bridge._last_result = BrowserLiveBridgeSyncResult(
            status="ready",
            reason="bridge_owner_ready",
            bridge_enabled=True,
            bridge_port=8765,
            owner_kind="browser_app",
            browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            workspace_id="gmail-intake",
            started=True,
            registration_ok=True,
            registration_reason="registered",
        )
        response = client.get("/api/runtime/ready?mode=live&workspace=gmail-intake")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["normalized_payload"]["runtime"]["runtime_mode"] == "live"
        assert payload["normalized_payload"]["readiness"]["browser_app"]["ready"] is True
        assert payload["normalized_payload"]["readiness"]["gmail_bridge"]["ready"] is True
        assert payload["normalized_payload"]["readiness"]["gmail_bridge"]["owner_kind"] == "browser_app"
        assert payload["normalized_payload"]["readiness"]["gmail_bridge"]["launch_session_id"] == "launch-rt-1"
        assert payload["normalized_payload"]["launch_session"]["launch_session_id"] == "launch-rt-1"


def test_shadow_web_shell_ready_endpoint_avoids_heavy_prepare_path(tmp_path: Path, monkeypatch) -> None:
    shell_ready_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        shadow_app_module,
        "latest_window_trace_status",
        lambda _base_dir: {
            "launch_session_id": "launch-shell-1",
            "status": "trace_started",
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "prepare_gmail_intake",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("prepare_gmail_intake should not run for shell/ready")),
    )
    monkeypatch.setattr(
        shadow_app_module.GmailBrowserSessionManager,
        "build_shell_ready",
        lambda self, **kwargs: shell_ready_calls.append(dict(kwargs)) or {
            "normalized_payload": {
                "pending_status": "translation_prepared",
                "draft_prereqs": {"status": "pending"},
            }
        },
    )

    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        context = client.app.state.shadow_context
        context.live_gmail_bridge._last_result = BrowserLiveBridgeSyncResult(
            status="ready",
            reason="bridge_owner_ready",
            bridge_enabled=True,
            bridge_port=8765,
            owner_kind="browser_app",
            browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            workspace_id="gmail-intake",
            started=True,
            registration_ok=True,
            registration_reason="registered",
        )
        response = client.get("/api/bootstrap/shell/ready?mode=live&workspace=gmail-intake")

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["normalized_payload"]["shell"]["gmail_bridge_ready"] is True
        assert payload["normalized_payload"]["gmail"]["pending_status"] == "translation_prepared"
        assert payload["normalized_payload"]["gmail"]["draft_prereqs"]["status"] == "pending"
        assert payload["normalized_payload"]["shell"]["launch_session"]["launch_session_id"] == "launch-shell-1"
        assert shell_ready_calls == [
            {
                "runtime_mode": "live",
                "workspace_id": "gmail-intake",
                "settings_path": _browser_data_paths(tmp_path, "live").settings_path,
            }
        ]


def test_shadow_web_restart_canonical_runtime_endpoint_returns_restart_payload(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        shadow_app_module,
        "restart_canonical_browser_runtime",
        lambda **kwargs: captured.update(kwargs) or {
            "ok": True,
            "reason": "canonical_restart_started",
            "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            "shell_ready_url": "http://127.0.0.1:8877/api/bootstrap/shell/ready?mode=live&workspace=gmail-intake",
            "workspace_id": "gmail-intake",
            "runtime_mode": "live",
        },
    )
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        response = client.post(
            "/api/gmail/runtime/restart-canonical",
            json={"mode": "live", "workspace_id": "gmail-intake"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["normalized_payload"]["reason"] == "canonical_restart_started"
        assert payload["normalized_payload"]["workspace_id"] == "gmail-intake"
        assert payload["normalized_payload"]["runtime_mode"] == "live"
        assert captured["runtime_mode"] == "live"
        assert captured["workspace_id"] == "gmail-intake"
        assert captured["runtime_path"] == client.app.state.shadow_context.repo_root
        assert isinstance(captured["current_listener_pid"], int)


def test_shadow_web_index_supports_legacy_ui_flag(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        response = client.get("/", params={"ui": "legacy"})
        assert response.status_code == 200
        text = response.text
        assert 'defaultUiVariant: "legacy"' in text
        assert 'data-ui-variant="legacy"' in text
        assert "Action Rail" in text
        assert "Dashboard" in text


def test_shadow_web_runtime_mode_and_extension_simulator_endpoints(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        mode_response = client.get("/api/runtime-mode", params={"mode": "live", "workspace": "browser-ws-2"})
        mode_payload = mode_response.json()
        assert mode_response.status_code == 200
        assert mode_payload["normalized_payload"]["current_mode"] == "live"
        assert mode_payload["normalized_payload"]["workspace_id"] == "browser-ws-2"
        assert mode_payload["normalized_payload"]["runtime"]["live_data"] is True

        simulate = client.post(
            "/api/extension/simulate-handoff",
            json={
                "mode": "shadow",
                "workspace_id": "browser-ws-1",
                "message_context": {
                    "message_id": "msg-1",
                    "thread_id": "thr-1",
                    "subject": "Court notice",
                },
            },
        )
        simulate_payload = simulate.json()
        assert simulate.status_code == 200
        assert simulate_payload["normalized_payload"]["handoff_request"]["message_id"] == "msg-1"
        assert simulate_payload["status"] in {"ok", "unavailable"}
        assert "prepare_response" in simulate_payload["diagnostics"]


def test_shadow_web_profile_and_joblog_delete_routes(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        new_profile = client.get("/api/profile/new")
        new_profile_payload = new_profile.json()
        assert new_profile.status_code == 200
        profile_id = new_profile_payload["normalized_payload"]["profile"]["id"]

        save_profile = client.post(
            "/api/profile/save",
            json={
                "profile": {
                    "id": profile_id,
                    "first_name": "Browser",
                    "last_name": "Profile",
                    "document_name_override": "Browser Profile",
                    "email": "browser@example.com",
                    "phone_number": "+351000000000",
                    "postal_address": "Rua do Browser",
                    "iban": "PT50003506490000832760029",
                    "iva_text": "23%",
                    "irs_text": "Sem retenção",
                    "travel_origin_label": "Beja",
                    "travel_distances_by_city": {"Cuba": 26},
                },
                "make_primary": True,
            },
        )
        save_profile_payload = save_profile.json()
        assert save_profile.status_code == 200
        assert save_profile_payload["normalized_payload"]["saved_profile"]["id"] == profile_id
        assert save_profile_payload["normalized_payload"]["profile_summary"]["primary_profile_id"] == profile_id

        save_row = client.post(
            "/api/interpretation/save-row",
            json={
                "form_values": {
                    "case_number": "1095/25.0T8BJA",
                    "court_email": "beja.trabalho.ministeriopublico@tribunais.org.pt",
                    "case_entity": "Tribunal do Trabalho",
                    "case_city": "Beja",
                    "service_entity": "Tribunal do Trabalho",
                    "service_city": "Beja",
                    "service_date": "2026-02-26",
                    "travel_km_outbound": "39",
                    "pages": "0",
                    "word_count": "0",
                    "rate_per_word": "0",
                    "expected_total": "0",
                    "amount_paid": "0",
                    "api_cost": "0",
                    "profit": "0",
                },
                "service_same_checked": True,
                "use_service_location_in_honorarios_checked": False,
                "include_transport_sentence_in_honorarios_checked": True,
            },
        )
        row_id = save_row.json()["saved_result"]["row_id"]

        delete_row = client.post("/api/joblog/delete", json={"row_id": row_id})
        delete_row_payload = delete_row.json()
        assert delete_row.status_code == 200
        assert delete_row_payload["normalized_payload"]["deleted_count"] == 1
        assert delete_row_payload["normalized_payload"]["deleted_row_ids"] == [row_id]

        set_primary = client.post("/api/profile/set-primary", json={"profile_id": "primary"})
        assert set_primary.status_code == 200
        assert set_primary.json()["normalized_payload"]["profile_summary"]["primary_profile_id"] == "primary"

        delete_profile = client.post("/api/profile/delete", json={"profile_id": profile_id})
        delete_profile_payload = delete_profile.json()
        assert delete_profile.status_code == 200
        assert delete_profile_payload["normalized_payload"]["deleted_profile_id"] == profile_id

        parity = client.get("/api/parity-audit")
        parity_payload = parity.json()
        assert parity.status_code == 200
        assert parity_payload["normalized_payload"]["promotion_recommendation"]["status"] == "ready_for_daily_use"


def test_shadow_web_bootstrap_includes_gmail_workspace_payload(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/bootstrap")
        payload = response.json()
        assert response.status_code == 200
        assert "gmail" in payload["normalized_payload"]
        assert "defaults" in payload["normalized_payload"]["gmail"]
        assert payload["normalized_payload"]["shell"]["extension_launch_session_schema_version"] == 3
        assert "launch_session" in payload["normalized_payload"]["shell"]
        assert payload["normalized_payload"]["gmail"]["review_event_id"] == 0
        assert payload["normalized_payload"]["gmail"]["message_signature"] == ""
        assert payload["normalized_payload"]["extension_lab"]["prepare_reason_catalog"]


def test_shadow_web_extension_launch_session_diagnostics_route_updates_launch_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/extension/launch-session-diagnostics",
            json={
                "launch_session_id": "launch-123",
                "handoff_session_id": "handoff-456",
                "tab_resolution_strategy": "created_exact_tab",
                "workspace_surface_confirmed": True,
                "client_hydration_status": "warming",
                "surface_candidate_source": "fresh_exact_tab",
                "surface_candidate_valid": True,
                "surface_invalidation_reason": "launch_session_mismatch",
                "fresh_tab_created_after_invalidation": True,
                "bridge_context_posted": True,
                "surface_visibility_status": "visible",
                "outcome": "warming",
                "reason": "workspace_pending_with_confirmed_surface",
                "tab_id": 91,
                "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            },
        )
        payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    launch_session = payload["normalized_payload"]["launch_session"]
    assert launch_session["launch_session_id"] == "launch-123"
    assert launch_session["handoff_session_id"] == "handoff-456"
    assert launch_session["tab_resolution_strategy"] == "created_exact_tab"
    assert launch_session["workspace_surface_confirmed"] is True
    assert launch_session["client_hydration_status"] == "warming"
    assert launch_session["surface_candidate_source"] == "fresh_exact_tab"
    assert launch_session["surface_candidate_valid"] is True
    assert launch_session["surface_invalidation_reason"] == "launch_session_mismatch"
    assert launch_session["fresh_tab_created_after_invalidation"] is True
    assert launch_session["bridge_context_posted"] is True
    assert launch_session["surface_visibility_status"] == "visible"
    assert launch_session["extension_surface_outcome"] == "warming"
    assert launch_session["extension_surface_reason"] == "workspace_pending_with_confirmed_surface"
    assert launch_session["extension_surface_tab_id"] == 91


def test_shadow_web_shell_bootstrap_returns_gmail_bridge_state_and_refreshes_runtime_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    listener_state = {
        "current": ShadowListenerOwnership(
            host="127.0.0.1",
            port=8877,
            status="available",
            pid=None,
            reason="no_listener",
        )
    }

    def _classify_listener(**_kwargs):
        return listener_state["current"]

    monkeypatch.setattr(shadow_app_module, "classify_shadow_listener", _classify_listener)
    monkeypatch.setattr(
        shadow_app_module,
        "prepare_gmail_intake",
        lambda **_kwargs: {
            "ok": True,
            "reason": "browser_bridge_owner_ready",
            "ui_owner": "browser_app",
            "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            "workspace_id": "gmail-intake",
            "runtime_mode": "live",
            "bridgePort": 8765,
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "inspect_edge_native_host",
        lambda **kwargs: _native_host_state(),
    )
    monkeypatch.setattr(
        shadow_app_module,
        "document_runtime_state_payload",
        lambda: {
            "status": "browser_bundle_only",
            "native_pdf_available": False,
            "browser_pdf_bundle_supported": True,
            "reason": "native_pdf_runtime_blocked",
            "message": "Native PDF helpers are unavailable in this runtime, but browser PDF staging remains available.",
        },
    )

    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        runtime_metadata_path = _runtime_paths(tmp_path).runtime_metadata_path
        initial_payload = json.loads(runtime_metadata_path.read_text(encoding="utf-8"))
        assert initial_payload["listener_ownership"]["status"] == "available"

        client.app.state.shadow_context.live_gmail_bridge._last_result = BrowserLiveBridgeSyncResult(
            status="ready",
            reason="browser_bridge_owner_ready",
            bridge_enabled=True,
            bridge_port=8765,
            owner_kind="browser_app",
            browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            workspace_id="gmail-intake",
            started=False,
            registration_ok=True,
            registration_reason="already_registered",
        )
        listener_state["current"] = ShadowListenerOwnership(
            host="127.0.0.1",
            port=8877,
            status="owned_by_self",
            pid=4242,
            reason="listener_owned_by_current_process",
        )

        response = client.get("/api/bootstrap/shell", params={"mode": "live", "workspace": "gmail-intake"})
        payload = response.json()

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert payload["status"] == "ok"
        assert payload["normalized_payload"]["shell"]["ready"] is True
        assert payload["normalized_payload"]["shell"]["native_host_ready"] is True
        assert payload["normalized_payload"]["shell"]["asset_version"]
        assert payload["normalized_payload"]["gmail"]["defaults"]["workflow_kind"] == "translation"
        assert payload["normalized_payload"]["document_runtime"]["browser_pdf_bundle_supported"] is True
        assert payload["normalized_payload"]["native_host"]["ready"] is True
        assert payload["capability_flags"]["native_host"]["status"] == "ok"
        assert payload["capability_flags"]["document_runtime"]["status"] == "warn"
        assert payload["capability_flags"]["gmail_bridge"]["reason"] == "browser_bridge_owner_ready"
        assert payload["capability_flags"]["gmail_bridge"]["current_mode"]["prepare_response"]["browser_url"].startswith(
            "http://127.0.0.1:8877/"
        )
        assert payload["diagnostics"]["gmail_bridge_sync"]["reason"] == "browser_bridge_owner_ready"
        assert payload["diagnostics"]["native_host"]["self_test_status"] == "ok"

        refreshed_payload = json.loads(runtime_metadata_path.read_text(encoding="utf-8"))
        assert refreshed_payload["listener_ownership"]["status"] == "owned_by_self"
        assert refreshed_payload["listener_ownership"]["reason"] == "listener_owned_by_current_process"


def test_merge_response_uses_explicit_capability_flags_without_recomputing(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        context = client.app.state.shadow_context
        target = shadow_app_module.ActiveBrowserTarget(
            mode="live",
            workspace_id="gmail-intake",
            data_paths=_browser_data_paths(tmp_path, "live"),
        )
        monkeypatch.setattr(
            shadow_app_module,
            "_runtime_diagnostics",
            lambda *_args, **_kwargs: {"listener_ownership": {"status": "owned_by_self"}},
        )
        monkeypatch.setattr(
            shadow_app_module,
            "_browser_capability_flags",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("capability flags should not be recomputed")),
        )

        merged = shadow_app_module._merge_response(
            context,
            target,
            {
                "status": "ok",
                "normalized_payload": {"sample": True},
                "diagnostics": {},
                "capability_flags": {"native_host": {"status": "ok"}},
            },
        )

        assert merged["capability_flags"] == {"native_host": {"status": "ok"}}


def test_shadow_web_bootstrap_and_capabilities_share_hydrated_capability_snapshot(tmp_path: Path, monkeypatch) -> None:
    shadow_paths = _browser_data_paths(tmp_path, "shadow")
    live_paths = _browser_data_paths(tmp_path, "live")
    live_paths.settings_path.parent.mkdir(parents=True, exist_ok=True)
    live_paths.settings_path.write_text(
        '{"gmail_intake_bridge_enabled": true, "gmail_intake_port": 8765, "gmail_account_email": "adel.belghali@gmail.com"}',
        encoding="utf-8",
    )

    def _fake_prepare(*, settings_loader=None, **_kwargs):
        settings = settings_loader() if settings_loader else {}
        enabled = bool(settings.get("gmail_intake_bridge_enabled", False))
        port = int(settings.get("gmail_intake_port", 8765) or 8765)
        return {
            "ok": enabled,
            "reason": "launch_ready" if enabled else "bridge_disabled",
            "autoLaunchReady": enabled,
            "bridgePort": port if enabled else None,
            "bridgeTokenPresent": enabled,
            "focused": False,
            "flashed": False,
            "launched": False,
        }

    monkeypatch.setattr(browser_app_service, "prepare_gmail_intake", _fake_prepare)
    monkeypatch.setattr(
        browser_app_service,
        "build_edge_extension_report",
        lambda: {"stable_extension_id": "abc", "active_extension_ids": [], "stale_extension_ids": []},
    )
    monkeypatch.setattr(
        browser_app_service,
        "detect_browser_data_paths",
        lambda mode, **kwargs: live_paths if mode == "live" else shadow_paths,
    )
    monkeypatch.setattr(
        browser_app_service,
        "build_translation_capability_flags",
        lambda **kwargs: {
            "translation": {
                "status": "ready",
                "credentials_configured": True,
                "credential_source": {"kind": "stored", "name": ""},
                "auth_test_supported": True,
            }
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "build_browser_provider_state",
        lambda **kwargs: {
            "native_host": _native_host_state(),
            "word_pdf_export": {
                "ok": True,
                "finalization_ready": True,
                "message": "Word PDF export canary passed.",
                "failure_code": "",
                "details": "",
                "elapsed_ms": 1,
                "launch_preflight": {"ok": True, "message": "Launch ready", "failure_code": "", "details": ""},
                "export_canary": {"ok": True, "message": "Canary ready", "failure_code": "", "details": ""},
                "preflight": {"ok": True, "message": "Launch ready", "failure_code": "", "details": ""},
                "last_checked_at": "2026-03-30T18:00:00+00:00",
                "cache_ttl_seconds": 60,
                "used_cache": False,
            },
        },
    )

    with _build_app(tmp_path, monkeypatch) as client:
        bootstrap = client.get("/api/bootstrap", params={"mode": "shadow"})
        capabilities = client.get("/api/capabilities", params={"mode": "shadow"})
        bootstrap_payload = bootstrap.json()
        capabilities_payload = capabilities.json()

        assert bootstrap.status_code == 200
        assert capabilities.status_code == 200
        assert bootstrap_payload["capability_flags"]["word_pdf_export"]["preflight"]["ok"] is True
        assert bootstrap_payload["capability_flags"]["word_pdf_export"]["launch_preflight"]["ok"] is True
        assert bootstrap_payload["capability_flags"]["word_pdf_export"]["export_canary"]["ok"] is True
        assert bootstrap_payload["capability_flags"]["word_pdf_export"]["finalization_ready"] is True
        assert capabilities_payload["capability_flags"]["word_pdf_export"]["preflight"]["ok"] is True
        assert bootstrap_payload["capability_flags"]["browser_automation"] == capabilities_payload["capability_flags"]["browser_automation"]
        assert bootstrap_payload["capability_flags"]["gmail_bridge"]["status"] == "info"
        assert capabilities_payload["capability_flags"]["gmail_bridge"]["status"] == "info"
        assert bootstrap_payload["capability_flags"]["gmail_bridge"]["message"] == "Disabled in isolated test mode; the live app Gmail bridge is ready."
        assert bootstrap_payload["capability_flags"]["translation"]["credentials_configured"] is True
        assert capabilities_payload["capability_flags"]["translation"]["credential_source"] == {"kind": "stored", "name": ""}
        assert bootstrap_payload["capability_flags"]["native_host"]["status"] == "ok"
        assert capabilities_payload["capability_flags"]["native_host"]["self_test_status"] == "ok"
        assert capabilities_payload["normalized_payload"]["extension_lab"]["bridge_context"]["live_desktop"]["ready"] is True


def test_shadow_web_gmail_routes_delegate_to_session_manager(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _load_message(self, *, runtime_mode, workspace_id, settings_path, context_payload):
        recorded["load_message"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "context_payload": dict(context_payload),
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "load_result": {
                    "ok": True,
                    "classification": "ready",
                    "status_message": "Loaded",
                    "message": {
                        "message_id": "msg-1",
                        "thread_id": "thr-1",
                        "subject": "Court notice",
                        "attachments": [
                            {
                                "attachment_id": "att-1",
                                "filename": "notice.pdf",
                                "mime_type": "application/pdf",
                                "size_bytes": 1200,
                                "source_message_id": "msg-1",
                            }
                        ],
                    },
                },
                "message": {"message_id": "msg-1", "attachments": []},
                "review_event_id": 4,
                "message_signature": "sig-msg-1",
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    def _prepare_session(
        self,
        *,
        runtime_mode,
        workspace_id,
        settings_path,
        outputs_dir,
        workflow_kind,
        target_lang,
        output_dir_text,
        selections_payload,
    ):
        recorded["prepare_session"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "outputs_dir": str(outputs_dir),
            "workflow_kind": workflow_kind,
            "target_lang": target_lang,
            "output_dir_text": output_dir_text,
            "selections_payload": list(selections_payload),
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "active_session": {
                    "kind": "translation",
                    "current_attachment": {
                        "attachment": {
                            "attachment_id": "att-1",
                            "filename": "notice.pdf",
                        },
                        "saved_path": "C:/tmp/notice.pdf",
                        "start_page": 2,
                        "page_count": 5,
                    },
                    "current_item_number": 1,
                    "total_items": 2,
                    "completed": False,
                },
                "suggested_translation_launch": {
                    "source_path": "C:/tmp/notice.pdf",
                    "source_filename": "notice.pdf",
                    "start_page": 2,
                    "page_count": 5,
                    "output_dir": "C:/tmp/out",
                    "target_lang": "EN",
                },
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    def _build_bootstrap(self, *, runtime_mode, workspace_id, settings_path, outputs_dir, build_sha="", asset_version=""):
        recorded["build_bootstrap"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "outputs_dir": str(outputs_dir),
            "build_sha": build_sha,
            "asset_version": asset_version,
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "defaults": {"message_context": {}, "default_output_dir": str(outputs_dir)},
                "active_session": {"kind": "translation", "completed": False},
                "review_event_id": 4,
                "message_signature": "sig-msg-1",
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "load_message", _load_message)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "prepare_session", _prepare_session)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "build_bootstrap", _build_bootstrap)

    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        load_response = client.post(
            "/api/gmail/load-message",
            json={
                "mode": "live",
                "workspace_id": "gmail-ws-1",
                "message_context": {
                    "message_id": "msg-1",
                    "thread_id": "thr-1",
                    "subject": "Court notice",
                },
            },
        )
        load_payload = load_response.json()
        assert load_response.status_code == 200
        assert load_payload["normalized_payload"]["load_result"]["message"]["message_id"] == "msg-1"
        assert load_payload["normalized_payload"]["review_event_id"] == 4
        assert load_payload["normalized_payload"]["message_signature"] == "sig-msg-1"
        assert recorded["load_message"]["runtime_mode"] == "live"
        assert recorded["load_message"]["workspace_id"] == "gmail-ws-1"

        prepare_response = client.post(
            "/api/gmail/prepare-session",
            json={
                "workflow_kind": "translation",
                "target_lang": "EN",
                "output_dir": "C:/tmp/out",
                "selections": [{"attachment_id": "att-1", "start_page": 2}],
            },
        )
        prepare_payload = prepare_response.json()
        assert prepare_response.status_code == 200
        assert prepare_payload["normalized_payload"]["active_session"]["kind"] == "translation"
        assert prepare_payload["normalized_payload"]["suggested_translation_launch"]["start_page"] == 2
        assert recorded["prepare_session"]["selections_payload"] == [{"attachment_id": "att-1", "start_page": 2}]

        current_response = client.get("/api/gmail/session/current")
        current_payload = current_response.json()
        assert current_response.status_code == 200
        assert current_payload["normalized_payload"]["active_session"]["kind"] == "translation"
        assert current_payload["normalized_payload"]["review_event_id"] == 4
        assert current_payload["normalized_payload"]["message_signature"] == "sig-msg-1"


def test_shadow_web_gmail_finalize_routes_and_attachment_file(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, object] = {}
    attachment_file = tmp_path / "gmail-preview.pdf"
    attachment_file.write_bytes(b"%PDF-1.7\n")

    def _confirm_current(
        self,
        *,
        runtime_mode,
        workspace_id,
        settings_path,
        job_log_db_path,
        translation_jobs,
        job_id,
        form_values,
        row_id,
    ):
        recorded["confirm_current"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "job_id": job_id,
            "form_values": dict(form_values),
            "row_id": row_id,
            "job_log_db_path": str(job_log_db_path),
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "active_session": {"kind": "translation", "completed": True},
                "saved_result": {"row_id": 9},
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    def _finalize_batch(
        self,
        *,
        runtime_mode,
        workspace_id,
        settings_path,
        output_filename,
        profile_id,
        build_sha="",
        asset_version="",
    ):
        recorded["finalize_batch"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "output_filename": output_filename,
            "profile_id": profile_id,
            "build_sha": build_sha,
            "asset_version": asset_version,
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "docx_path": "C:/tmp/honorarios.docx",
                "pdf_path": "C:/tmp/honorarios.pdf",
                "finalization_report_context": {
                    "kind": "gmail_finalization_report",
                    "operation": "gmail_batch_finalize",
                    "status": "ok",
                    "finalization_state": "draft_ready",
                },
                "active_session": {
                    "kind": "translation",
                    "completed": True,
                    "finalization_report_context": {
                        "kind": "gmail_finalization_report",
                        "operation": "gmail_batch_finalize",
                        "status": "ok",
                        "finalization_state": "draft_ready",
                    },
                },
                "gmail_draft_result": {"ok": True, "message": "Draft ready"},
            },
            "diagnostics": {"pdf_export": {"ok": True}},
            "capability_flags": {},
        }

    def _preflight_batch_finalization(
        self,
        *,
        runtime_mode,
        workspace_id,
        settings_path,
        force_refresh,
        build_sha="",
        asset_version="",
    ):
        recorded["preflight_batch_finalization"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "force_refresh": force_refresh,
            "build_sha": build_sha,
            "asset_version": asset_version,
        }
        return {
            "status": "blocked_word_pdf_export" if force_refresh else "ok",
            "normalized_payload": {
                "finalization_state": "blocked_word_pdf_export" if force_refresh else "ready_to_finalize",
                "finalization_preflight": {
                    "finalization_ready": not force_refresh,
                    "message": "Word export canary passed." if not force_refresh else "Word PDF export canary timed out.",
                },
                "active_session": {"kind": "translation", "completed": True},
            },
            "diagnostics": {"word_pdf_export": {"finalization_ready": not force_refresh}},
            "capability_flags": {},
        }

    def _finalize_interpretation(
        self,
        *,
        runtime_mode,
        workspace_id,
        settings_path,
        form_values,
        profile_id,
        service_same_checked,
        output_filename,
    ):
        recorded["finalize_interpretation"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "form_values": dict(form_values),
            "profile_id": profile_id,
            "service_same_checked": service_same_checked,
            "output_filename": output_filename,
        }
        return {
            "status": "draft_unavailable",
            "normalized_payload": {
                "docx_path": "C:/tmp/interpretation.docx",
                "pdf_path": "C:/tmp/interpretation.pdf",
                "active_session": {"kind": "interpretation"},
            },
            "diagnostics": {"pdf_export": {"ok": True}},
            "capability_flags": {},
        }

    def _current_attachment_file(self, *, runtime_mode, workspace_id, attachment_id):
        recorded["attachment_file"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "attachment_id": attachment_id,
        }
        return attachment_file

    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "confirm_current_batch_translation", _confirm_current)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "finalize_batch", _finalize_batch)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "preflight_batch_finalization", _preflight_batch_finalization)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "finalize_interpretation", _finalize_interpretation)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "current_attachment_file", _current_attachment_file)

    with _build_app(tmp_path, monkeypatch) as client:
        confirm_response = client.post(
            "/api/gmail/batch/confirm-current",
            json={
                "job_id": "tx-123",
                "form_values": {"case_number": "456/26.0T8LSB"},
                "row_id": 4,
            },
        )
        confirm_payload = confirm_response.json()
        assert confirm_response.status_code == 200
        assert confirm_payload["normalized_payload"]["saved_result"]["row_id"] == 9
        assert recorded["confirm_current"]["job_id"] == "tx-123"

        batch_response = client.post(
            "/api/gmail/batch/finalize",
            json={"profile_id": "primary", "output_filename": "gmail_batch.docx"},
        )
        batch_payload = batch_response.json()
        assert batch_response.status_code == 200
        assert batch_payload["normalized_payload"]["gmail_draft_result"]["ok"] is True
        assert batch_payload["normalized_payload"]["finalization_report_context"]["status"] == "ok"
        assert batch_payload["normalized_payload"]["finalization_report_context"]["build_sha"] != ""
        assert batch_payload["normalized_payload"]["finalization_report_context"]["asset_version"] != ""
        assert (
            batch_payload["normalized_payload"]["active_session"]["finalization_report_context"]["status"]
            == "ok"
        )
        assert recorded["finalize_batch"]["output_filename"] == "gmail_batch.docx"

        preflight_response = client.post(
            "/api/gmail/batch/finalize-preflight",
            json={"force_refresh": True},
        )
        preflight_payload = preflight_response.json()
        assert preflight_response.status_code == 200
        assert preflight_payload["status"] == "blocked_word_pdf_export"
        assert preflight_payload["normalized_payload"]["finalization_preflight"]["finalization_ready"] is False
        assert recorded["preflight_batch_finalization"]["force_refresh"] is True

        interpretation_response = client.post(
            "/api/gmail/interpretation/finalize",
            json={
                "profile_id": "primary",
                "service_same_checked": True,
                "output_filename": "gmail_interp.docx",
                "form_values": {
                    "case_number": "1095/25.0T8BJA",
                    "court_email": "tribunal@example.test",
                },
            },
        )
        interpretation_payload = interpretation_response.json()
        assert interpretation_response.status_code == 200
        assert interpretation_payload["status"] == "draft_unavailable"
        assert recorded["finalize_interpretation"]["service_same_checked"] is True

        attachment_response = client.get("/api/gmail/attachment/att-1")
        assert attachment_response.status_code == 200
        assert attachment_response.headers["content-type"].startswith("application/pdf")
        assert attachment_response.headers["content-disposition"].startswith("inline;")
        assert recorded["attachment_file"]["attachment_id"] == "att-1"


def test_shadow_web_gmail_preview_route_keeps_inline_pdf_contract(tmp_path: Path, monkeypatch) -> None:
    preview_file = tmp_path / "preview.pdf"
    preview_file.write_bytes(b"%PDF-1.7\n")
    recorded: dict[str, object] = {}

    def _preview_attachment(self, *, runtime_mode, workspace_id, settings_path, attachment_id):
        recorded["preview_attachment"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "attachment_id": attachment_id,
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "attachment": {
                    "attachment_id": attachment_id,
                    "filename": "preview.pdf",
                    "mime_type": "application/pdf",
                    "size_bytes": preview_file.stat().st_size,
                },
                "page_count": 5,
                "preview_path": str(preview_file),
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    def _current_attachment_file(self, *, runtime_mode, workspace_id, attachment_id):
        recorded["current_attachment_file"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "attachment_id": attachment_id,
        }
        return preview_file

    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "preview_attachment", _preview_attachment)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "current_attachment_file", _current_attachment_file)

    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        preview_response = client.post("/api/gmail/preview-attachment", json={"attachment_id": "att-preview"})
        preview_payload = preview_response.json()
        assert preview_response.status_code == 200
        assert preview_payload["normalized_payload"]["preview_href"].startswith("/api/gmail/attachment/att-preview?")
        assert recorded["preview_attachment"]["attachment_id"] == "att-preview"

        attachment_response = client.get(preview_payload["normalized_payload"]["preview_href"])
        assert attachment_response.status_code == 200
        assert attachment_response.headers["content-type"].startswith("application/pdf")
        assert attachment_response.headers["content-disposition"].startswith("inline;")
        assert recorded["current_attachment_file"]["attachment_id"] == "att-preview"


def test_shadow_web_gmail_preview_and_prepare_block_noncanonical_live_runtime(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, int] = {"preview": 0, "prepare": 0}
    monkeypatch.setattr(
        shadow_app_module.GmailBrowserSessionManager,
        "preview_attachment",
        lambda self, **kwargs: recorded.__setitem__("preview", recorded["preview"] + 1) or {},
    )
    monkeypatch.setattr(
        shadow_app_module.GmailBrowserSessionManager,
        "prepare_session",
        lambda self, **kwargs: recorded.__setitem__("prepare", recorded["prepare"] + 1) or {},
    )

    with _build_app(tmp_path, monkeypatch) as client:
        preview_response = client.post("/api/gmail/preview-attachment", json={"attachment_id": "att-preview"})
        prepare_response = client.post(
            "/api/gmail/prepare-session",
            json={
                "workflow_kind": "translation",
                "target_lang": "FR",
                "output_dir": "C:/tmp/out",
                "selections": [{"attachment_id": "att-1", "start_page": 1}],
            },
        )

        assert preview_response.status_code == 409
        assert prepare_response.status_code == 409
        assert preview_response.json()["normalized_payload"]["validation_error"]["reason"] == "canonical_restart_required"
        assert prepare_response.json()["normalized_payload"]["validation_error"]["reason"] == "canonical_restart_required"
        assert preview_response.json()["diagnostics"]["error"] == "noncanonical_live_runtime"
        assert prepare_response.json()["diagnostics"]["error"] == "noncanonical_live_runtime"
        assert recorded == {"preview": 0, "prepare": 0}


def test_shadow_web_shell_ready_blocks_noncanonical_live_gmail_bridge(tmp_path: Path, monkeypatch) -> None:
    shell_ready_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        shadow_app_module.GmailBrowserSessionManager,
        "build_shell_ready",
        lambda self, **kwargs: shell_ready_calls.append(dict(kwargs)) or {
            "normalized_payload": {
                "pending_status": "translation_prepared",
                "draft_prereqs": {"status": "pending"},
            }
        },
    )

    with _build_app(tmp_path, monkeypatch) as client:
        context = client.app.state.shadow_context
        context.live_gmail_bridge._last_result = BrowserLiveBridgeSyncResult(
            status="ready",
            reason="browser_bridge_owner_ready",
            bridge_enabled=True,
            bridge_port=8765,
            owner_kind="browser_app",
            browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            workspace_id="gmail-intake",
            started=True,
            registration_ok=True,
            registration_reason="registered",
        )

        response = client.get("/api/bootstrap/shell/ready?mode=live&workspace=gmail-intake")
        payload = response.json()

        assert response.status_code == 200
        assert payload["normalized_payload"]["shell"]["gmail_bridge_ready"] is False
        assert payload["capability_flags"]["gmail_bridge"]["reason"] == "canonical_restart_required"
        assert payload["capability_flags"]["gmail_bridge"]["current_mode"]["prepare_response"]["ok"] is False
        assert payload["capability_flags"]["gmail_bridge"]["current_mode"]["owner_kind"] == "none"
        assert shell_ready_calls == [
            {
                "runtime_mode": "live",
                "workspace_id": "gmail-intake",
                "settings_path": _browser_data_paths(tmp_path, "live").settings_path,
            }
        ]

def test_shadow_web_gmail_image_attachment_route_is_inline(tmp_path: Path, monkeypatch) -> None:
    image_file = tmp_path / "preview.png"
    image_file.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr(
        shadow_app_module.GmailBrowserSessionManager,
        "current_attachment_file",
        lambda self, **kwargs: image_file,
    )

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/gmail/attachment/att-image")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/png")
        assert response.headers["content-disposition"].startswith("inline;")


def test_shadow_web_browser_pdf_bundle_route_writes_bundle_and_updates_gmail_cache(tmp_path: Path, monkeypatch) -> None:
    source_pdf = tmp_path / "bundle-source.pdf"
    source_pdf.write_bytes(b"%PDF-1.7\n")
    image = Image.new("RGB", (24, 18), color=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/browser-pdf/bundle",
            data={
                "manifest": json.dumps(
                    {
                        "source_path": str(source_pdf),
                        "attachment_id": "att-bundle",
                        "page_count": 1,
                        "pages": [
                            {
                                "page_number": 1,
                                "file_name": "page_0001.png",
                                "mime_type": "image/png",
                                "width_px": 24,
                                "height_px": 18,
                            }
                        ],
                    }
                ),
            },
            files={
                "page_images": ("page_0001.png", buffer.getvalue(), "image/png"),
            },
        )
        payload = response.json()
        assert response.status_code == 200
        assert payload["normalized_payload"]["page_count"] == 1
        manifest_path = Path(payload["normalized_payload"]["manifest_path"])
        assert manifest_path.exists()
        workspace = client.app.state.shadow_context.gmail_sessions._workspace(
            runtime_mode="live",
            workspace_id="workspace-1",
        )
        assert workspace.preview_page_counts["att-bundle"] == 1
        assert workspace.preview_paths["att-bundle"] == source_pdf.resolve()


def test_shadow_web_translation_bootstrap_and_save_history_flow(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        bootstrap = client.get("/api/translation/bootstrap")
        bootstrap_payload = bootstrap.json()
        assert bootstrap.status_code == 200
        assert bootstrap_payload["status"] == "ok"
        assert "defaults" in bootstrap_payload["normalized_payload"]
        assert bootstrap_payload["normalized_payload"]["history"] == []

        save = client.post(
            "/api/translation/save-row",
            json={
                "seed_payload": {
                    "translation_date": "2026-03-18",
                    "case_number": "",
                    "case_entity": "",
                    "case_city": "",
                    "run_id": "",
                    "target_lang": "EN",
                    "pages": 0,
                    "word_count": 0,
                    "rate_per_word": 0,
                    "expected_total": 0,
                    "amount_paid": 0,
                    "api_cost": 0,
                    "profit": 0,
                },
                "form_values": {
                    "translation_date": "2026-03-18",
                    "case_number": "456/26.0T8LSB",
                    "court_email": "tribunal@example.test",
                    "case_entity": "Tribunal Base",
                    "case_city": "Beja",
                    "run_id": "run-456",
                    "target_lang": "EN",
                    "pages": "12",
                    "word_count": "1400",
                    "total_tokens": "3200",
                    "rate_per_word": "0.08",
                    "expected_total": "112",
                    "amount_paid": "0",
                    "api_cost": "3.2",
                    "estimated_api_cost": "3.4",
                    "quality_risk_score": "0.12",
                    "profit": "108.8",
                }
            },
        )
        save_payload = save.json()
        assert save.status_code == 200
        assert save_payload["status"] == "ok"
        assert save_payload["saved_result"]["row_id"] > 0

        history = client.get("/api/translation/history")
        history_payload = history.json()
        assert history.status_code == 200
        assert len(history_payload["normalized_payload"]["history"]) == 1
        assert history_payload["normalized_payload"]["history"][0]["row"]["job_type"] == "Translation"
        assert history_payload["normalized_payload"]["history"][0]["seed"]["run_id"] == "run-456"


def test_shadow_web_arabic_review_routes_block_save_until_resolved(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        docx_path = tmp_path / "translated_ar.docx"
        docx_path.write_bytes(b"docx")
        job = _completed_ar_job(docx_path)
        monkeypatch.setattr(
            client.app.state.shadow_context.translation_jobs,
            "get_job",
            lambda job_id: job if job_id == "tx-ar-001" else None,
        )

        state = client.get("/api/translation/arabic-review/state?job_id=tx-ar-001")
        state_payload = state.json()
        assert state.status_code == 200
        assert state_payload["normalized_payload"]["arabic_review"]["required"] is True
        assert state_payload["normalized_payload"]["arabic_review"]["resolved"] is False

        restored = client.get("/api/translation/arabic-review/state")
        restored_payload = restored.json()
        assert restored.status_code == 200
        assert restored_payload["normalized_payload"]["arabic_review"]["job_id"] == "tx-ar-001"
        assert restored_payload["normalized_payload"]["arabic_review"]["completion_key"] == "job:tx-ar-001:translate"

        blocked_save = client.post(
            "/api/translation/save-row",
            json={
                "job_id": "tx-ar-001",
                "completion_key": "job:tx-ar-001:translate",
                "seed_payload": job["result"]["save_seed"],
                "form_values": {
                    "translation_date": "2026-04-02",
                    "case_number": "305/23.2GCBJA",
                    "court_email": "beja.judicial@tribunais.org.pt",
                    "case_entity": "Juizo Local Criminal de Beja",
                    "case_city": "Beja",
                    "run_id": "20260402_164400",
                    "target_lang": "AR",
                    "pages": "5",
                    "word_count": "980",
                    "rate_per_word": "0.08",
                    "expected_total": "78.4",
                    "amount_paid": "0",
                    "api_cost": "3.2",
                    "profit": "75.2",
                },
            },
        )
        blocked_payload = blocked_save.json()
        assert blocked_save.status_code == 422
        assert blocked_payload["diagnostics"]["error"] == (
            "Arabic DOCX review is required before Save-to-Job-Log or Gmail confirmation can continue. "
            "Open the durable DOCX in Word, align or edit it manually, then save."
        )
        assert blocked_payload["normalized_payload"]["validation_error"]["arabic_review"]["required"] is True

        continued = client.post(
            "/api/translation/arabic-review/continue",
            json={
                "job_id": "tx-ar-001",
                "completion_key": "job:tx-ar-001:translate",
                "continuation": "continue_without_changes",
            },
        )
        continued_payload = continued.json()
        assert continued.status_code == 200
        assert continued_payload["normalized_payload"]["arabic_review"]["resolved"] is True
        assert continued_payload["normalized_payload"]["arabic_review"]["resolution"] == "continue_without_changes"

        saved = client.post(
            "/api/translation/save-row",
            json={
                "job_id": "tx-ar-001",
                "completion_key": "job:tx-ar-001:translate",
                "seed_payload": job["result"]["save_seed"],
                "form_values": {
                    "translation_date": "2026-04-02",
                    "case_number": "305/23.2GCBJA",
                    "court_email": "beja.judicial@tribunais.org.pt",
                    "case_entity": "Juizo Local Criminal de Beja",
                    "case_city": "Beja",
                    "run_id": "20260402_164400",
                    "target_lang": "AR",
                    "pages": "5",
                    "word_count": "980",
                    "rate_per_word": "0.08",
                    "expected_total": "78.4",
                    "amount_paid": "0",
                    "api_cost": "3.2",
                    "profit": "75.2",
                },
            },
        )
        saved_payload = saved.json()
        assert saved.status_code == 200
        assert saved_payload["saved_result"]["row_id"] > 0


def test_shadow_web_arabic_review_open_reports_fallback_used(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        docx_path = tmp_path / "translated_ar.docx"
        docx_path.write_bytes(b"docx")
        job = _completed_ar_job(docx_path)
        monkeypatch.setattr(
            client.app.state.shadow_context.translation_jobs,
            "get_job",
            lambda job_id: job if job_id == "tx-ar-001" else None,
        )
        monkeypatch.setattr(
            browser_arabic_review,
            "open_docx_in_word",
            lambda path: WordAutomationResult(
                ok=False,
                action="open_docx",
                message="Word automation failed.",
            ),
        )
        monkeypatch.setattr(browser_arabic_review.os, "name", "nt", raising=False)
        opened: list[str] = []
        monkeypatch.setattr(
            browser_arabic_review.os,
            "startfile",
            lambda path: opened.append(str(path)),
            raising=False,
        )

        response = client.post(
            "/api/translation/arabic-review/open",
            json={
                "job_id": "tx-ar-001",
                "completion_key": "job:tx-ar-001:translate",
            },
        )
        payload = response.json()

        assert response.status_code == 200
        assert payload["normalized_payload"]["arabic_review"]["fallback_used"] is True
        assert opened == [str(docx_path.resolve())]


def test_shadow_web_gmail_confirm_is_blocked_by_unresolved_arabic_review(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        docx_path = tmp_path / "translated_ar.docx"
        docx_path.write_bytes(b"docx")
        job = _completed_ar_job(docx_path)
        monkeypatch.setattr(
            client.app.state.shadow_context.translation_jobs,
            "get_job",
            lambda job_id: job if job_id == "tx-ar-001" else None,
        )
        called = {"value": False}

        def _unexpected_confirm(**kwargs):
            called["value"] = True
            return {"status": "ok", "normalized_payload": {"active_session": None}, "diagnostics": {}}

        monkeypatch.setattr(
            client.app.state.shadow_context.gmail_sessions,
            "confirm_current_batch_translation",
            _unexpected_confirm,
        )

        response = client.post(
            "/api/gmail/batch/confirm-current",
            json={
                "job_id": "tx-ar-001",
                "completion_key": "job:tx-ar-001:translate",
                "form_values": {},
                "row_id": None,
            },
        )
        payload = response.json()

        assert response.status_code == 422
        assert payload["normalized_payload"]["validation_error"]["arabic_review"]["required"] is True
        assert called["value"] is False


def test_shadow_web_settings_and_power_tools_routes(tmp_path: Path, monkeypatch) -> None:
    def _fake_power_bootstrap(*, data_paths, runtime_metadata_path=None):
        return {
            "settings_admin": {
                "form_values": {"default_lang": "EN", "ocr_api_provider": "openai"},
                "provider_state": {
                    "translation": {
                        "credentials_configured": True,
                        "effective_credential_source": {"kind": "stored", "name": ""},
                        "auth_test_supported": True,
                    },
                    "ocr": {"provider": "openai", "api_configured": True},
                    "native_host": _native_host_state(),
                },
            },
                "power_tools": {
                    "glossary": {"project_glossary_path": str(data_paths.app_data_dir / "project.json")},
                    "glossary_builder": {"defaults": {"source_mode": "run_folders"}, "latest_run_dirs": []},
                    "calibration": {"defaults": {"target_lang": "EN"}},
                    "diagnostics": {
                        "outputs_root": str(data_paths.outputs_dir),
                        "latest_run_dirs": [],
                        "latest_window_trace": {"launch_session_id": "", "status": "idle"},
                    },
                },
            }

    monkeypatch.setattr(shadow_app_module, "build_power_tools_bootstrap", _fake_power_bootstrap)
    monkeypatch.setattr(
        shadow_app_module,
        "save_browser_settings",
        lambda **kwargs: {
            "status": "ok",
            "normalized_payload": {"saved": True, "form_values": {"default_lang": "FR"}},
            "diagnostics": {
                "provider_state": {
                    "translation": {
                        "credentials_configured": True,
                        "effective_credential_source": {"kind": "stored", "name": ""},
                        "auth_test_supported": True,
                    },
                    "ocr": {"provider": "openai", "api_configured": True},
                }
            },
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "run_settings_preflight",
        lambda **kwargs: {
            "status": "ok",
            "normalized_payload": {
                "translation": {
                    "credentials_configured": True,
                    "effective_credential_source": {"kind": "stored", "name": ""},
                    "auth_test_supported": True,
                },
                "ocr": {"provider": "openai", "api_configured": True, "local_available": False},
                "gmail_draft": {"ready": True, "message": "Ready"},
                "word_pdf_export": {"ok": True, "message": "Ready"},
                "native_host": _native_host_state(),
            },
            "diagnostics": {},
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "run_translation_provider_test",
        lambda **kwargs: {
            "status": "failed",
            "normalized_payload": {
                "ok": False,
                "status": "unauthorized",
                "message": "OpenAI authentication failed.",
                "credential_source": {"kind": "env", "name": "OPENAI_API_KEY"},
                "status_code": 401,
                "exception_class": "AuthenticationError",
            },
            "diagnostics": {},
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "run_ocr_provider_test",
        lambda **kwargs: {
            "status": "ok",
            "normalized_payload": {
                "provider": "openai",
                "source": {"kind": "stored", "name": "ocr_api_key"},
                "message": "OCR provider test passed.",
            },
            "diagnostics": {},
        },
    )
    monkeypatch.setattr(
        shadow_app_module,
        "create_browser_debug_bundle",
        lambda **kwargs: {
            "status": "ok",
            "normalized_payload": {"bundle_path": "C:/tmp/browser_debug_bundle.zip", "included_files": ["run_summary.json"]},
            "diagnostics": {},
        },
    )

    with _build_app(tmp_path, monkeypatch) as client:
        settings_admin = client.get("/api/settings/admin")
        settings_payload = settings_admin.json()
        assert settings_admin.status_code == 200
        assert settings_payload["normalized_payload"]["form_values"]["default_lang"] == "EN"
        assert settings_payload["normalized_payload"]["provider_state"]["translation"]["credentials_configured"] is True
        assert settings_payload["capability_flags"]["native_host"]["status"] == "ok"

        settings_save = client.post("/api/settings/save", json={"form_values": {"default_lang": "FR"}})
        save_payload = settings_save.json()
        assert settings_save.status_code == 200
        assert save_payload["normalized_payload"]["saved"] is True
        assert save_payload["normalized_payload"]["form_values"]["default_lang"] == "FR"
        assert save_payload["diagnostics"]["provider_state"]["translation"]["auth_test_supported"] is True

        settings_preflight = client.post("/api/settings/preflight", json={})
        preflight_payload = settings_preflight.json()
        assert settings_preflight.status_code == 200
        assert preflight_payload["normalized_payload"]["translation"]["effective_credential_source"] == {"kind": "stored", "name": ""}
        assert preflight_payload["normalized_payload"]["native_host"]["ready"] is True

        translation_test = client.post("/api/settings/translation-test", json={})
        translation_test_payload = translation_test.json()
        assert translation_test.status_code == 200
        assert translation_test_payload["status"] == "failed"
        assert translation_test_payload["normalized_payload"]["status"] == "unauthorized"
        assert translation_test_payload["normalized_payload"]["status_code"] == 401

        translation_test_empty = client.post("/api/settings/translation-test")
        translation_test_empty_payload = translation_test_empty.json()
        assert translation_test_empty.status_code == 200
        assert translation_test_empty_payload["status"] == "failed"
        assert translation_test_empty_payload["normalized_payload"]["status"] == "unauthorized"

        ocr_test_empty = client.post("/api/settings/ocr-test")
        ocr_test_empty_payload = ocr_test_empty.json()
        assert ocr_test_empty.status_code == 200
        assert ocr_test_empty_payload["status"] == "ok"
        assert ocr_test_empty_payload["normalized_payload"]["provider"] == "openai"

        power_bootstrap = client.get("/api/power-tools/bootstrap")
        power_payload = power_bootstrap.json()
        assert power_bootstrap.status_code == 200
        assert power_payload["normalized_payload"]["glossary_builder"]["defaults"]["source_mode"] == "run_folders"
        assert "latest_window_trace" in power_payload["normalized_payload"]["diagnostics"]

        debug_bundle = client.post("/api/power-tools/diagnostics/debug-bundle", json={"run_dir": "C:/tmp/run-1"})
        bundle_payload = debug_bundle.json()
        assert debug_bundle.status_code == 200
        assert bundle_payload["normalized_payload"]["bundle_path"].endswith(".zip")


def test_shadow_web_power_tools_arm_window_trace_endpoint(tmp_path: Path, monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        shadow_app_module,
        "arm_browser_window_trace",
        lambda **kwargs: captured.update(kwargs) or {
            "status": "ok",
            "normalized_payload": {
                "armed": True,
                "launch_session_id": "launch-arm-1",
            },
            "diagnostics": {
                "latest_window_trace": {
                    "launch_session_id": "launch-arm-1",
                    "status": "armed",
                },
            },
        },
    )
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        response = client.post(
            "/api/power-tools/diagnostics/arm-window-trace",
            json={
                "mode": "live",
                "workspace_id": "gmail-intake",
                "duration_seconds": 9,
                "sample_interval_ms": 125,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["normalized_payload"]["launch_session_id"] == "launch-arm-1"
        assert payload["diagnostics"]["latest_window_trace"]["launch_session_id"] == "launch-arm-1"
        assert captured == {
            "settings_path": _browser_data_paths(tmp_path, "live").settings_path,
            "duration_seconds": 9.0,
            "sample_interval_ms": 125,
        }


def test_shadow_web_settings_key_routes_delegate_to_secure_store_services(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _provider_state() -> dict[str, object]:
        return {
            "translation": {
                "credentials_configured": True,
                "stored_credential_configured": True,
                "effective_credential_source": {"kind": "stored", "name": ""},
                "auth_test_supported": True,
            },
            "ocr": {
                "provider": "openai",
                "stored_credential_configured": True,
                "translation_fallback_configured": True,
                "effective_credential_source": {"kind": "stored", "name": "ocr_api_key"},
                "api_configured": True,
                "local_available": False,
                "auth_test_supported": True,
            },
            "gmail_draft": {"ready": True, "message": "Ready"},
            "word_pdf_export": {"ok": True, "message": "Ready"},
            "native_host": _native_host_state(),
        }

    def _save_translation(**kwargs):
        recorded["save_translation"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"saved": True, "provider_state": _provider_state(), "message": "saved translation"},
            "diagnostics": {"provider_state": _provider_state()},
        }

    def _clear_translation(**kwargs):
        recorded["clear_translation"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"cleared": True, "provider_state": _provider_state(), "message": "cleared translation"},
            "diagnostics": {"provider_state": _provider_state()},
        }

    def _save_ocr(**kwargs):
        recorded["save_ocr"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"saved": True, "provider_state": _provider_state(), "message": "saved ocr"},
            "diagnostics": {"provider_state": _provider_state()},
        }

    def _clear_ocr(**kwargs):
        recorded["clear_ocr"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"cleared": True, "provider_state": _provider_state(), "message": "cleared ocr"},
            "diagnostics": {"provider_state": _provider_state()},
        }

    def _native_host_test(**kwargs):
        recorded["native_host_test"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"native_host": _native_host_state(), "provider_state": _provider_state(), "message": "tested native host"},
            "diagnostics": {"provider_state": _provider_state()},
        }

    def _native_host_repair(**kwargs):
        recorded["native_host_repair"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {
                "native_host": _native_host_state(),
                "repair_result": {"ok": True, "changed": True, "reason": "registered"},
                "provider_state": _provider_state(),
                "message": "repaired native host",
            },
            "diagnostics": {"provider_state": _provider_state()},
        }

    def _word_pdf_test(**kwargs):
        recorded["word_pdf_test"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {
                "word_pdf_export": {"finalization_ready": True, "message": "Word PDF export canary passed."},
                "finalization_ready": True,
                "provider_state": _provider_state(),
                "message": "tested word pdf",
            },
            "diagnostics": {"provider_state": _provider_state()},
        }

    monkeypatch.setattr(
        shadow_app_module,
        "save_browser_translation_key",
        _save_translation,
    )
    monkeypatch.setattr(
        shadow_app_module,
        "clear_browser_translation_key",
        _clear_translation,
    )
    monkeypatch.setattr(
        shadow_app_module,
        "save_browser_ocr_key",
        _save_ocr,
    )
    monkeypatch.setattr(
        shadow_app_module,
        "clear_browser_ocr_key",
        _clear_ocr,
    )
    monkeypatch.setattr(
        shadow_app_module,
        "run_native_host_test",
        _native_host_test,
    )
    monkeypatch.setattr(
        shadow_app_module,
        "repair_browser_native_host",
        _native_host_repair,
    )
    monkeypatch.setattr(
        shadow_app_module,
        "run_word_pdf_export_test",
        _word_pdf_test,
    )

    with _build_app(tmp_path, monkeypatch) as client:
        save_translation = client.post("/api/settings/translation-key/save", json={"key": "sk-browser"})
        clear_translation = client.post("/api/settings/translation-key/clear", json={})
        save_ocr = client.post("/api/settings/ocr-key/save", json={"key": "ocr-browser"})
        clear_ocr = client.post("/api/settings/ocr-key/clear", json={})
        native_host_test = client.post("/api/settings/native-host-test", json={})
        word_pdf_test = client.post("/api/settings/word-pdf-test", json={})
        native_host_repair = client.post("/api/settings/native-host-repair", json={})

    assert save_translation.status_code == 200
    assert clear_translation.status_code == 200
    assert save_ocr.status_code == 200
    assert clear_ocr.status_code == 200
    assert native_host_test.status_code == 200
    assert word_pdf_test.status_code == 200
    assert native_host_repair.status_code == 200
    assert recorded["save_translation"]["key"] == "sk-browser"
    assert recorded["save_translation"]["settings_path"].name == "settings.json"
    assert recorded["save_ocr"]["key"] == "ocr-browser"
    assert recorded["save_ocr"]["settings_path"].name == "settings.json"
    assert recorded["native_host_test"]["settings_path"].name == "settings.json"
    assert recorded["word_pdf_test"]["settings_path"].name == "settings.json"
    assert recorded["native_host_repair"]["settings_path"].name == "settings.json"
    assert save_translation.json()["normalized_payload"]["saved"] is True
    assert clear_translation.json()["normalized_payload"]["cleared"] is True
    assert save_ocr.json()["normalized_payload"]["saved"] is True
    assert clear_ocr.json()["normalized_payload"]["cleared"] is True
    assert native_host_test.json()["normalized_payload"]["native_host"]["ready"] is True
    assert word_pdf_test.json()["normalized_payload"]["finalization_ready"] is True
    assert native_host_repair.json()["normalized_payload"]["repair_result"]["changed"] is True


def test_shadow_web_stage_four_action_routes_delegate_to_services(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _fake_builder_run(**kwargs):
        recorded["builder"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"artifact_dir": "C:/tmp/builder", "suggestions": [{"source_term": "tribunal"}]},
            "diagnostics": {},
        }

    def _fake_calibration_run(**kwargs):
        recorded["calibration"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"report_md_path": "C:/tmp/calibration.md", "suggestions": []},
            "diagnostics": {},
        }

    def _fake_report(**kwargs):
        recorded["report"] = kwargs
        return {
            "status": "ok",
            "normalized_payload": {"report_kind": "run_report", "report_path": "C:/tmp/run_report.md", "preview": "# report"},
            "diagnostics": {},
        }

    monkeypatch.setattr(shadow_app_module, "run_glossary_builder", _fake_builder_run)
    monkeypatch.setattr(shadow_app_module, "run_browser_calibration_audit", _fake_calibration_run)
    monkeypatch.setattr(shadow_app_module, "generate_browser_run_report", _fake_report)

    with _build_app(tmp_path, monkeypatch) as client:
        builder = client.post(
            "/api/power-tools/glossary-builder/run",
            json={
                "source_mode": "select_pdfs",
                "run_dirs": [],
                "pdf_paths": ["C:/tmp/a.pdf"],
                "target_lang": "EN",
                "builder_mode": "headers_only",
                "lemma_enabled": True,
                "lemma_effort": "xhigh",
            },
        )
        builder_payload = builder.json()
        assert builder.status_code == 200
        assert builder_payload["normalized_payload"]["artifact_dir"] == "C:/tmp/builder"
        assert recorded["builder"]["pdf_paths"] == ["C:/tmp/a.pdf"]
        assert recorded["builder"]["mode"] == "headers_only"

        calibration = client.post(
            "/api/power-tools/calibration/run",
            json={
                "pdf_path": "C:/tmp/calibration.pdf",
                "output_dir": "C:/tmp/out",
                "target_lang": "FR",
                "sample_pages": 4,
                "user_seed": "legal",
                "include_excerpts": True,
                "excerpt_max_chars": 220,
            },
        )
        calibration_payload = calibration.json()
        assert calibration.status_code == 200
        assert calibration_payload["normalized_payload"]["report_md_path"] == "C:/tmp/calibration.md"
        assert recorded["calibration"]["target_lang"] == "FR"
        assert recorded["calibration"]["sample_pages"] == 4

        report = client.post("/api/power-tools/diagnostics/run-report", json={"run_dir": "C:/tmp/run-5"})
        report_payload = report.json()
        assert report.status_code == 200
        assert report_payload["normalized_payload"]["report_kind"] == "run_report"
        assert report_payload["normalized_payload"]["report_path"] == "C:/tmp/run_report.md"
        assert recorded["report"]["run_dir_text"] == "C:/tmp/run-5"

        browser_failure_report = client.post(
            "/api/power-tools/diagnostics/run-report",
            json={
                "browser_failure_context": {
                    "kind": "gmail_browser_failure",
                    "operation": "gmail_prepare_session",
                    "runtime_mode": "live",
                    "workspace_id": "gmail-intake",
                    "error": {
                        "code": "browser_pdf_worker_load_failed",
                        "message": "Browser PDF worker could not load.",
                    },
                },
            },
        )
        browser_failure_payload = browser_failure_report.json()
        assert browser_failure_report.status_code == 200
        assert browser_failure_payload["normalized_payload"]["report_kind"] == "run_report"
        assert recorded["report"]["browser_failure_context"]["operation"] == "gmail_prepare_session"
        assert recorded["report"]["browser_failure_context"]["build_identity"]["branch"] == "codex/beginner-first-primary-flow-ux"
        assert recorded["report"]["browser_failure_context"]["build_identity"]["is_canonical"] is False
        assert recorded["report"]["browser_failure_context"]["build_sha"] == "5c9842e"
        assert recorded["report"]["browser_failure_context"]["asset_version"] != ""

        gmail_finalization_report = client.post(
            "/api/power-tools/diagnostics/run-report",
            json={
                "gmail_finalization_context": {
                    "kind": "gmail_finalization_report",
                    "operation": "gmail_batch_finalize",
                    "status": "local_only",
                    "runtime_mode": "live",
                    "workspace_id": "gmail-intake",
                },
            },
        )
        gmail_finalization_payload = gmail_finalization_report.json()
        assert gmail_finalization_report.status_code == 200
        assert gmail_finalization_payload["normalized_payload"]["report_kind"] == "run_report"
        assert recorded["report"]["gmail_finalization_context"]["operation"] == "gmail_batch_finalize"
        assert recorded["report"]["gmail_finalization_context"]["build_sha"] != ""
        assert recorded["report"]["gmail_finalization_context"]["asset_version"] != ""


def test_generate_browser_run_report_supports_browser_failure_context_without_run_dir(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    payload = generate_browser_run_report(
        settings_path=settings_path,
        outputs_dir=outputs_dir,
        run_dir_text="",
        browser_failure_context={
            "kind": "gmail_browser_failure",
            "operation": "gmail_prepare_session",
            "runtime_mode": "live",
            "workspace_id": "gmail-intake",
            "build_sha": "6e823b2",
            "asset_version": "asset-20260330",
            "build_identity": {
                "branch": "feat/lichtfeld-wsl-setup",
                "head_sha": "6e823b2",
                "is_canonical": False,
                "reasons": ["branch mismatch"],
            },
            "error": {
                "code": "browser_pdf_worker_load_failed",
                "message": "Browser PDF worker could not load.",
                "diagnostics": {
                    "attempted_url": "http://127.0.0.1:8877/static/vendor/pdfjs/vendor/pdfjs/pdf.worker.mjs?v=6e823b2",
                    "worker_url": "http://127.0.0.1:8877/static/vendor/pdfjs/pdf.worker.mjs?v=6e823b2",
                    "raw_browser_error": "TypeError: Failed to fetch dynamically imported module",
                    "worker_boot_phase": "worker_bootstrap_blob_wrapper",
                },
            },
            "attachments": [
                {
                    "attachment_id": "att-1",
                    "filename": "sentenca.pdf",
                    "selected": True,
                    "start_page": 1,
                },
            ],
        },
    )

    normalized = payload["normalized_payload"]
    assert normalized["report_kind"] == "browser_failure_report"
    report_path = Path(normalized["report_path"])
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "# Browser Failure Report" in report_text
    assert '"operation": "gmail_prepare_session"' in report_text
    assert '"browser_pdf_worker_load_failed"' in report_text
    assert '"asset_version": "asset-20260330"' in report_text
    assert '"raw_browser_error": "TypeError: Failed to fetch dynamically imported module"' in report_text
    assert '"is_canonical": false' in report_text


def test_generate_browser_run_report_supports_gmail_finalization_context_without_run_dir(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    payload = generate_browser_run_report(
        settings_path=settings_path,
        outputs_dir=outputs_dir,
        run_dir_text="",
        gmail_finalization_context={
            "kind": "gmail_finalization_report",
            "operation": "gmail_batch_finalize",
            "status": "ok",
            "finalization_state": "draft_ready",
            "runtime_mode": "live",
            "workspace_id": "gmail-intake",
            "build_sha": "6e823b2",
            "asset_version": "asset-20260330",
            "session": {
                "session_id": "gmail_batch_04dc6f86b2de",
                "message_id": "19d0bf7e8dccffc0",
                "thread_id": "19d0bf7e8dccffc0",
                "confirmed_items": [
                    {
                        "attachment_filename": "sentença 305.pdf",
                        "translated_docx_path": "C:/Users/FA507/Downloads/sentença 305_EN_20260401_141119.docx",
                        "durable_translated_docx_path": "C:/Users/FA507/Downloads/sentença 305_EN_20260401_141119.docx",
                        "staged_translated_docx_path": "C:/Users/FA507/AppData/Local/Temp/legalpdf_gmail_batch/_draft_attachments/sentença 305_EN_20260401_141119.docx",
                        "translated_docx_path_source": "durable",
                        "translated_docx_path_exists": True,
                        "durable_translated_docx_path_exists": True,
                        "staged_translated_docx_path_exists": True,
                    }
                ],
            },
            "word_pdf_export": {
                "finalization_ready": True,
                "launch_preflight": {"ok": True, "message": "Word launched."},
                "export_canary": {"ok": True, "message": "Word export canary passed."},
            },
            "actual_export": {
                "ok": True,
            },
            "outcome": {
                "docx_path": "C:/Users/FA507/Downloads/Requerimento_Honorarios_305_23.2GCBJA_20260330.docx",
                "pdf_path": "C:/Users/FA507/Downloads/Requerimento_Honorarios_305_23.2GCBJA_20260330.pdf",
                "docx_path_exists": True,
                "pdf_path_exists": True,
                "draft_created": True,
            },
        },
    )

    normalized = payload["normalized_payload"]
    assert normalized["report_kind"] == "gmail_finalization_report"
    report_path = Path(normalized["report_path"])
    assert report_path.exists()
    report_text = report_path.read_text(encoding="utf-8")
    assert "# Gmail Finalization Report" in report_text
    assert '"operation": "gmail_batch_finalize"' in report_text
    assert '"finalization_state": "draft_ready"' in report_text
    assert '"status": "ok"' in report_text
    assert '"draft_created": true' in report_text
    assert '"translated_docx_path_source": "durable"' in report_text
    assert '"durable_translated_docx_path"' in report_text


def test_shadow_web_index_renders_static_base_bootstrap(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/?mode=live&workspace=gmail-intake")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        body = response.text
        match = re.search(r'assetVersion: "([^"]+)"', body)
        assert match is not None
        asset_version = match.group(1)
        assert f'staticBasePath: "http://testserver/static-build/{asset_version}/"' in body
        assert f'href="http://testserver/static-build/{asset_version}/style.css"' in body
        assert f'src="http://testserver/static-build/{asset_version}/app.js"' in body


def test_shadow_web_versioned_static_route_serves_current_browser_asset_graph(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        shell = client.get("/api/bootstrap/shell", params={"mode": "live", "workspace": "gmail-intake"})
        assert shell.status_code == 200
        shell_payload = shell.json()
        asset_version = shell_payload["normalized_payload"]["shell"]["asset_version"]
        assert shell_payload["normalized_payload"]["shell"]["build_identity"]["branch"] == "codex/beginner-first-primary-flow-ux"
        browser_pdf = client.get(f"/static-build/{asset_version}/browser_pdf.js")
        assert browser_pdf.status_code == 200
        assert browser_pdf.headers["content-type"].startswith("application/javascript")
        assert "resolveBrowserPdfAssetUrls" in browser_pdf.text
        module_asset = client.get(f"/static-build/{asset_version}/vendor/pdfjs/pdf.mjs")
        assert module_asset.status_code == 200
        assert module_asset.headers["content-type"].startswith("application/javascript")
        worker = client.get(f"/static-build/{asset_version}/vendor/pdfjs/pdf.worker.mjs")
        assert worker.status_code == 200
        assert worker.headers["content-type"].startswith("application/javascript")
        stale = client.get("/static-build/stale/browser_pdf.js")
        assert stale.status_code == 404


def test_shadow_web_translation_job_routes_use_manager_methods(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _start_translate(self, *, runtime_mode, workspace_id, form_values, settings_path):
        recorded["start_translate"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "form_values": dict(form_values),
            "settings_path": str(settings_path),
        }
        return {
            "job_id": "tx-stage2",
            "job_kind": "translate",
            "status": "running",
            "status_text": "Translating...",
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "config": {"source_path": form_values.get("source_path", "")},
            "progress": {"selected_index": 1, "selected_total": 4, "real_page": 1},
            "diagnostics": {},
            "logs": [],
            "artifacts": {},
            "result": {},
            "actions": {"cancel": True},
        }

    def _resume_job(self, *, job_id, settings_path):
        recorded["resume_job"] = {"job_id": job_id, "settings_path": str(settings_path)}
        return {
            "job_id": job_id,
            "job_kind": "translate",
            "status": "running",
            "status_text": "Resumed",
            "runtime_mode": "live",
            "workspace_id": "ws-live",
            "config": {},
            "progress": {},
            "diagnostics": {},
            "logs": [],
            "artifacts": {},
            "result": {},
            "actions": {"cancel": True},
        }

    def _rebuild_job(self, *, job_id, settings_path):
        recorded["rebuild_job"] = {"job_id": job_id, "settings_path": str(settings_path)}
        return {
            "job_id": job_id,
            "job_kind": "rebuild",
            "status": "completed",
            "status_text": "Rebuild complete",
            "runtime_mode": "live",
            "workspace_id": "ws-live",
            "config": {},
            "progress": {},
            "diagnostics": {},
            "logs": [],
            "artifacts": {},
            "result": {"rebuild": {"docx_path": "C:/tmp/output.docx"}},
            "actions": {},
        }

    def _cancel_job(self, *, job_id):
        recorded["cancel_job"] = {"job_id": job_id}
        return True

    def _get_job(self, job_id):
        return {
            "job_id": job_id,
            "job_kind": "translate",
            "status": "cancel_requested",
            "status_text": "Cancellation requested",
            "runtime_mode": "live",
            "workspace_id": "ws-live",
            "config": {},
            "progress": {},
            "diagnostics": {},
            "logs": [],
            "artifacts": {},
            "result": {},
            "actions": {"resume": True, "rebuild": True},
        }

    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "start_translate", _start_translate)
    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "resume_job", _resume_job)
    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "rebuild_job", _rebuild_job)
    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "cancel_job", _cancel_job)
    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "get_job", _get_job)

    with _build_app(tmp_path, monkeypatch) as client:
        start = client.post(
            "/api/translation/jobs/translate",
            json={
                "mode": "live",
                "workspace_id": "ws-live",
                "form_values": {
                    "source_path": "C:/tmp/source.pdf",
                    "output_dir": str((tmp_path / "live" / "outputs").resolve()),
                    "target_lang": "EN",
                    "gmail_batch_context": {
                        "source": "gmail_intake",
                        "session_id": "gmail_batch_123",
                        "message_id": "msg-1",
                        "thread_id": "thr-1",
                        "attachment_id": "att-1",
                        "selected_attachment_filename": "source.pdf",
                        "selected_attachment_count": 1,
                        "selected_target_lang": "EN",
                        "selected_start_page": 1,
                        "gmail_batch_session_report_path": "C:/tmp/gmail_batch_session.json",
                    },
                },
            },
        )
        start_payload = start.json()
        assert start.status_code == 200
        assert start_payload["normalized_payload"]["job"]["job_id"] == "tx-stage2"
        assert recorded["start_translate"]["runtime_mode"] == "live"
        assert recorded["start_translate"]["workspace_id"] == "ws-live"
        assert recorded["start_translate"]["form_values"]["gmail_batch_context"]["attachment_id"] == "att-1"

        cancel = client.post("/api/translation/jobs/tx-stage2/cancel", headers={"X-LegalPDF-Runtime-Mode": "live"})
        cancel_payload = cancel.json()
        assert cancel.status_code == 200
        assert cancel_payload["normalized_payload"]["job"]["status"] == "cancel_requested"
        assert recorded["cancel_job"] == {"job_id": "tx-stage2"}

        resume = client.post("/api/translation/jobs/tx-stage2/resume", headers={"X-LegalPDF-Runtime-Mode": "live"})
        resume_payload = resume.json()
        assert resume.status_code == 200
        assert resume_payload["normalized_payload"]["job"]["status_text"] == "Resumed"
        assert recorded["resume_job"]["job_id"] == "tx-stage2"

        rebuild = client.post("/api/translation/jobs/tx-stage2/rebuild", headers={"X-LegalPDF-Runtime-Mode": "live"})
        rebuild_payload = rebuild.json()
        assert rebuild.status_code == 200
        assert rebuild_payload["normalized_payload"]["job"]["job_kind"] == "rebuild"
        assert recorded["rebuild_job"]["job_id"] == "tx-stage2"


def test_shadow_web_translation_route_surfaces_auth_failure_payload(tmp_path: Path, monkeypatch) -> None:
    def _start_translate(self, *, runtime_mode, workspace_id, form_values, settings_path):
        _ = form_values, settings_path
        return {
            "job_id": "tx-auth",
            "job_kind": "translate",
            "status": "failed",
            "status_text": "OpenAI authentication failed",
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "config": {"source_path": "C:/tmp/source.pdf"},
            "progress": {"selected_index": 0, "selected_total": 1, "real_page": 0},
            "diagnostics": {"kind": "translate"},
            "logs": [],
            "artifacts": {"run_summary_path": "C:/tmp/run_summary.json"},
            "result": {
                "success": False,
                "error": "authentication_failure",
                "failure_context": {
                    "scope": "preflight",
                    "status_code": 401,
                    "credential_source": {"kind": "stored", "name": ""},
                },
            },
            "actions": {"resume": True, "rebuild": True, "download_run_summary": True},
        }

    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "start_translate", _start_translate)

    with _build_app(tmp_path, monkeypatch) as client:
        start = client.post(
            "/api/translation/jobs/translate",
            json={
                "mode": "live",
                "workspace_id": "gmail-intake",
                "form_values": {
                    "source_path": "C:/tmp/source.pdf",
                    "output_dir": str((tmp_path / "live" / "outputs").resolve()),
                    "target_lang": "EN",
                },
            },
        )
        payload = start.json()

        assert start.status_code == 200
        assert payload["normalized_payload"]["job"]["status"] == "failed"
        assert payload["normalized_payload"]["job"]["status_text"] == "OpenAI authentication failed"
        assert payload["normalized_payload"]["job"]["result"]["error"] == "authentication_failure"
        assert payload["normalized_payload"]["job"]["result"]["failure_context"]["scope"] == "preflight"


def test_shadow_web_translation_artifact_route_keeps_download_headers(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "run_summary.json"
    artifact.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        shadow_app_module.TranslationJobManager,
        "job_artifact_path",
        lambda self, **kwargs: artifact,
    )

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/translation/jobs/tx-artifact/artifact/run_summary")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/json")
        assert response.headers["content-disposition"].startswith("attachment;")


def test_shadow_web_translation_run_report_route_returns_updated_job(tmp_path: Path, monkeypatch) -> None:
    recorded: dict[str, object] = {}

    def _generate_run_report(self, *, job_id, settings_path):
        recorded["job_id"] = job_id
        recorded["settings_path"] = str(settings_path)
        return {
            "status": "ok",
            "normalized_payload": {
                "job": {
                    "job_id": job_id,
                    "job_kind": "translate",
                    "status": "completed",
                    "artifacts": {"run_report_path": "C:/tmp/run_report.md"},
                    "actions": {"download_run_report": True},
                },
                "report_kind": "run_report",
                "report_path": "C:/tmp/run_report.md",
                "preview": "# report",
            },
            "diagnostics": {},
        }

    monkeypatch.setattr(shadow_app_module.TranslationJobManager, "generate_run_report", _generate_run_report)

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post("/api/translation/jobs/tx-report/run-report")
        payload = response.json()

    assert response.status_code == 200
    assert recorded["job_id"] == "tx-report"
    assert payload["normalized_payload"]["report_kind"] == "run_report"
    assert payload["normalized_payload"]["report_path"] == "C:/tmp/run_report.md"
    assert payload["normalized_payload"]["job"]["actions"]["download_run_report"] is True


def test_shadow_web_translation_run_report_artifact_route_serves_markdown(tmp_path: Path, monkeypatch) -> None:
    artifact = tmp_path / "run_report.md"
    artifact.write_text("# Run Report\n", encoding="utf-8")

    monkeypatch.setattr(
        shadow_app_module.TranslationJobManager,
        "job_artifact_path",
        lambda self, **kwargs: artifact,
    )

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/translation/jobs/tx-artifact/artifact/run_report")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.headers["content-disposition"].startswith("attachment;")


def test_shadow_web_notification_upload_route_uses_service_response(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        shadow_app_module,
        "autofill_interpretation_from_notification_pdf",
        lambda **kwargs: {
            "status": "ok",
            "normalized_payload": {
                "case_number": "1095/25.0T8BJA",
                "case_entity": "Tribunal do Trabalho",
                "case_city": "Beja",
                "service_date": "2026-02-26",
                "court_email": "beja.trabalho.ministeriopublico@tribunais.org.pt",
                "service_entity": "",
                "service_city": "",
                "travel_km_outbound": None,
                "travel_km_return": None,
                "use_service_location_in_honorarios": False,
                "include_transport_sentence_in_honorarios": True,
                "completed_at": "2026-03-18T10:00:00",
                "translation_date": "2026-02-26",
                "job_type": "Interpretation",
                "lang": "",
                "pages": 0,
                "word_count": 0,
                "rate_per_word": 0.0,
                "expected_total": 0.0,
                "amount_paid": 0.0,
                "api_cost": 0.0,
                "run_id": "",
                "target_lang": "",
                "total_tokens": None,
                "estimated_api_cost": None,
                "quality_risk_score": None,
                "profit": 0.0,
                "pdf_path": None,
                "output_docx": None,
                "partial_docx": None,
            },
            "diagnostics": {"metadata_extraction": {"extracted_fields": ["service_date"]}},
            "capability_flags": {},
        },
    )

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/autofill-notification",
            files={"file": ("notice.pdf", b"%PDF-1.7\n", "application/pdf")},
        )
        payload = response.json()
        assert response.status_code == 200
        assert payload["status"] == "ok"
    assert payload["normalized_payload"]["service_date"] == "2026-02-26"
    assert Path(payload["diagnostics"]["uploaded_file"]).exists()


def test_shadow_web_extension_simulator_validation_returns_json(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/extension/simulate-handoff",
            json={
                "message_context": {
                    "message_id": "msg-1",
                    "thread_id": "",
                    "subject": "Court notice",
                }
            },
        )
        payload = response.json()
        assert response.status_code == 422
        assert payload["status"] == "failed"
        assert "thread_id" in payload["diagnostics"]["error"]


def test_shadow_web_export_route_returns_validation_json(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        shadow_app_module,
        "export_interpretation_honorarios",
        lambda **kwargs: (_ for _ in ()).throw(
            InterpretationValidationError(
                code="unknown_service_city",
                message="Service city must be selected from a known city or added first.",
                field="service_city",
                city="Camões",
                travel_origin_label="Marmelar",
                city_source="imported_metadata",
            )
        ),
    )

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/export-honorarios",
            json={
                "form_values": {
                    "case_number": "1095/25.0T8BJA",
                    "case_entity": "Tribunal do Trabalho",
                    "case_city": "Beja",
                    "service_entity": "",
                    "service_city": "",
                    "service_date": "",
                },
                "service_same_checked": True,
            },
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["status"] == "failed"
    assert payload["diagnostics"]["error"] == "Service city must be selected from a known city or added first."
    assert payload["diagnostics"]["validation_error"]["code"] == "unknown_service_city"
    assert payload["diagnostics"]["validation_error"]["city"] == "Camões"
    assert payload["normalized_payload"]["validation_error"]["travel_origin_label"] == "Marmelar"


def test_shadow_web_gmail_interpretation_finalize_route_returns_structured_validation_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        client.app.state.shadow_context.gmail_sessions.finalize_interpretation = lambda **_kwargs: (_ for _ in ()).throw(
            InterpretationValidationError(
                code="distance_required",
                message="One-way distance from Marmelar to Beja is required.",
                field="travel_km_outbound",
                city="Beja",
                travel_origin_label="Marmelar",
                city_source="current_selection",
            )
        )
        response = client.post(
            "/api/gmail/interpretation/finalize",
            json={
                "form_values": {
                    "case_number": "305/23.2GCBJA",
                    "case_entity": "Ministério Público",
                    "case_city": "Beja",
                    "service_city": "Beja",
                    "service_date": "2026-03-20",
                },
                "service_same_checked": True,
            },
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["status"] == "failed"
    assert payload["diagnostics"]["validation_error"]["code"] == "distance_required"
    assert payload["normalized_payload"]["validation_error"]["field"] == "travel_km_outbound"


def test_shadow_web_add_interpretation_city_route_returns_updated_reference(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/cities/add",
            json={
                "field_name": "service_city",
                "city": "Serpa",
                "profile_id": "primary",
                "include_transport_sentence_in_honorarios": True,
                "travel_km_outbound": "32",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["normalized_payload"]["city"] == "Serpa"
    assert "Serpa" in payload["normalized_payload"]["interpretation_reference"]["available_cities"]
    assert payload["normalized_payload"]["profile_distance_summary"]["travel_distances_by_city"]["Serpa"] == 32.0


def test_shadow_web_add_interpretation_city_route_returns_structured_distance_validation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/cities/add",
            json={
                "field_name": "service_city",
                "city": "Serpa",
                "profile_id": "primary",
                "include_transport_sentence_in_honorarios": True,
                "travel_km_outbound": "",
            },
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["status"] == "failed"
    assert payload["diagnostics"]["validation_error"]["code"] == "distance_required"
    assert payload["diagnostics"]["validation_error"]["city"] == "Serpa"
