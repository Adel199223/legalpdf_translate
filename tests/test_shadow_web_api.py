from __future__ import annotations

import io
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlencode, urlparse

from fastapi.testclient import TestClient
from PIL import Image

from .browser_esm_probe import run_browser_esm_json_probe
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
_GOOGLE_PHOTOS_CALLBACK_PATH = "/api/interpretation/google-photos/oauth/callback"


def _google_photos_callback_url(**query: str) -> str:
    return f"{_GOOGLE_PHOTOS_CALLBACK_PATH}?{urlencode(query)}"


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
        assert [item["title"] for item in bootstrap_payload["normalized_payload"]["dashboard_cards"]] == [
            "Interpretation Requests",
            "Translation",
            "Gmail Attachments",
            "Technical Tools",
            "Glossary and Reports",
        ]
        assert bootstrap_payload["normalized_payload"]["parity_audit"]["summary"] == (
            "The browser app is ready for the daily workflows: translation, interpretation requests, Gmail attachments, and saved work."
        )
        assert [item["title"] for item in bootstrap_payload["normalized_payload"]["parity_audit"]["checklist"]] == [
            "Main app screens",
            "Translation",
            "Interpretation requests",
            "Gmail attachments",
            "Saved work",
            "Settings and profile",
            "Technical tools",
        ]
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
        assert 'document.body.dataset.operatorChrome = operatorMode ? "on" : "off"' in text
        assert 'document.body.dataset.beginnerSurface = uiVariant === "qt" && ["dashboard", "new-job", "recent-jobs", "profile", "settings"].includes(activeView) && !operatorMode ? "true" : "false"' in text
        assert "<title>LegalPDF Translate</title>" in text
        assert "Simple Workspace Shell" not in text
        assert "Browser App" not in text
        assert "Guided Translation" in text
        assert "Choose a document, confirm the language, then start translation." in text
        assert 'id="topbar-eyebrow"' in text
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
        dashboard_view_start = text.index('data-view="dashboard"')
        gmail_view_start = text.index('data-view="gmail-intake"')
        new_job_view_start = text.index('data-view="new-job"')
        profile_drawer_start = text.index('id="profile-editor-drawer-backdrop"')
        gmail_review_drawer_start = text.index('id="gmail-review-drawer-backdrop"')
        gmail_session_drawer_start = text.index('id="gmail-session-drawer-backdrop"')
        translation_completion_drawer_start = text.index('id="translation-completion-drawer-backdrop"')
        gmail_batch_finalize_drawer_start = text.index('id="gmail-batch-finalize-drawer-backdrop"')
        interpretation_review_drawer_start = text.index('id="interpretation-review-drawer-backdrop"')
        interpretation_city_dialog_start = text.index('id="interpretation-city-dialog-backdrop"')
        recent_jobs_view_start = text.index('data-view="recent-jobs"')
        settings_view_start = text.index('data-view="settings"')
        profile_view_start = text.index('data-view="profile"')
        power_tools_view_start = text.index('data-view="power-tools"')
        extension_lab_view_start = text.index('data-view="extension-lab"')
        runtime_details_start = text.index('id="runtime-details"')
        runtime_details_end = text.index("</details>", runtime_details_start) + len("</details>")
        dashboard_view = text[dashboard_view_start:gmail_view_start]
        dashboard_beginner_view = text[dashboard_view_start:runtime_details_start] + text[runtime_details_end:gmail_view_start]
        gmail_view = text[gmail_view_start:new_job_view_start]
        new_job_view = text[new_job_view_start:profile_drawer_start]
        gmail_review_drawer = text[gmail_review_drawer_start:gmail_session_drawer_start]
        gmail_session_drawer = text[gmail_session_drawer_start:translation_completion_drawer_start]
        translation_completion_drawer = text[translation_completion_drawer_start:gmail_batch_finalize_drawer_start]
        gmail_batch_finalize_drawer = text[gmail_batch_finalize_drawer_start:interpretation_review_drawer_start]
        interpretation_review_drawer = text[interpretation_review_drawer_start:interpretation_city_dialog_start]
        recent_jobs_view = text[recent_jobs_view_start:settings_view_start]
        settings_view = text[settings_view_start:profile_view_start]
        profile_view = text[profile_view_start:power_tools_view_start]
        power_tools_view = text[power_tools_view_start:extension_lab_view_start]
        extension_lab_view = text[extension_lab_view_start:profile_drawer_start]
        profile_drawer = text[profile_drawer_start:gmail_review_drawer_start]
        assert "Overview" in dashboard_view
        assert "App Status" in dashboard_view
        assert "What You Can Do" in dashboard_view
        assert "Checking app status..." in dashboard_view
        assert "Checking available app features..." in dashboard_view
        assert "job-log rows" not in dashboard_beginner_view
        assert "mode provenance" not in dashboard_beginner_view
        assert "Gmail bridge" not in dashboard_beginner_view
        assert "job-log writes" not in dashboard_beginner_view
        assert "Save to Job Log" not in dashboard_beginner_view
        assert "artifacts" not in dashboard_beginner_view
        assert "Browser shell and runtime modes" not in dashboard_beginner_view
        assert "Recent Jobs and Job Log actions" not in dashboard_beginner_view
        assert 'id="gmail-workspace-strip"' in new_job_view
        assert 'id="gmail-workspace-strip-action"' in new_job_view
        assert "Review Gmail Attachments" in gmail_view
        assert "Review Attachments" in gmail_view
        assert "Open this from Gmail or load a message manually from details." in gmail_view
        assert "Advanced message details" in gmail_view
        assert "More options" in gmail_view
        assert "Open full app view" in gmail_view
        assert "Reset Gmail review" in gmail_view
        assert "Gmail Handoff" not in gmail_view
        assert "Focused Intake Review" not in gmail_view
        assert "Message Details and Overrides" not in gmail_view
        assert "Open Attachment Review" not in gmail_view
        assert "Refresh Gmail State" not in gmail_view
        assert "Open Full Workspace" not in gmail_view
        assert "Reset Gmail Workspace" not in gmail_view
        assert "browser workspace" not in gmail_view
        assert 'id="gmail-resume-step"' in text
        assert 'id="gmail-resume-result"' in text
        assert 'id="gmail-load-demo-review"' in gmail_view
        assert "Load demo attachments" in gmail_view
        assert 'id="gmail-restore-bar"' in gmail_view
        assert 'id="gmail-restore-review"' in gmail_view
        assert 'id="gmail-restore-preview"' in gmail_view
        assert "Review Attachments — Restore" in gmail_view
        assert "PDF Preview — Restore" in gmail_view
        assert 'id="gmail-open-full-workspace"' in gmail_view
        assert 'id="gmail-open-session"' not in text
        assert 'id="gmail-preview-session"' not in text
        assert 'id="gmail-review-drawer"' in text
        assert 'id="gmail-review-drawer-backdrop"' in text
        assert 'id="gmail-minimize-review-drawer"' in text
        assert 'id="gmail-close-review-drawer"' in text
        assert 'id="gmail-review-summary"' in text
        assert 'id="gmail-review-summary-details"' in text
        assert 'id="gmail-review-summary-grid"' in text
        assert 'id="gmail-noncanonical-runtime-guard"' in text
        assert 'id="gmail-restart-canonical-runtime"' in text
        assert "Live Gmail needs the main app runtime" in text
        assert "Restart live Gmail runtime" in text
        assert 'id="gmail-continue-noncanonical-runtime"' not in text
        assert 'id="gmail-review-detail"' in text
        assert 'id="gmail-preview-drawer"' in text
        assert 'id="gmail-preview-drawer-backdrop"' in text
        assert 'id="gmail-back-to-review-drawer"' in text
        assert 'id="gmail-minimize-preview-drawer"' in text
        assert 'id="gmail-close-preview-drawer"' in text
        assert 'id="gmail-preview-frame"' in text
        assert 'id="gmail-preview-page"' in text
        assert 'id="gmail-preview-open-tab"' in text
        assert 'id="gmail-preview-apply"' in text
        assert "Choose Attachments" in gmail_review_drawer
        assert "Step 1: Choose workflow" in gmail_review_drawer
        assert "English (EN)" in gmail_review_drawer
        assert "French (FR)" in gmail_review_drawer
        assert "Arabic (AR)" in gmail_review_drawer
        assert "Continue with selected attachments" in gmail_review_drawer
        assert "Current document" in gmail_review_drawer
        assert "Use" in gmail_review_drawer
        assert "Document" in gmail_review_drawer
        assert "Kind" in gmail_review_drawer
        assert "Start page" in gmail_review_drawer
        assert "Gmail Attachment Review" not in gmail_review_drawer
        assert "Attachment Preview" in text
        assert "Preview the selected attachment to inspect it here." not in text
        assert 'id="gmail-session-banner"' not in text
        assert 'id="gmail-session-drawer"' in text
        assert 'id="gmail-session-drawer-backdrop"' in text
        assert 'id="gmail-close-session-drawer"' in text
        assert 'id="translation-numeric-warning"' in text
        assert 'id="translation-completion-numeric-warning"' in text
        assert 'id="translation-save-numeric-warning"' in text
        assert 'id="translation-gmail-step-numeric-warning"' in text
        assert 'id="gmail-batch-finalize-numeric-warning"' in text
        assert "Continue Gmail Step" in gmail_session_drawer
        assert "Gmail Session" not in gmail_session_drawer
        assert "Session Actions" not in gmail_session_drawer
        assert "Final DOCX filename" in gmail_session_drawer
        assert "Create Gmail reply" in gmail_session_drawer
        assert "Gmail attachment ready" in new_job_view
        assert "Review the Gmail message and attachments before you continue." in new_job_view
        assert "Review Gmail message" in new_job_view
        assert "Job Setup" in text
        assert "Run Status" in text
        assert "Start Translate" in text
        assert "Advanced Settings" in text
        assert 'id="translation-source-card"' in text
        assert 'id="translation-source-browse"' in text
        assert 'id="translation-source-clear"' in text
        assert 'id="translation-source-stage-status"' in text
        assert 'id="translation-source-path-summary"' in text
        assert 'id="translation-output-summary-label"' in text
        assert 'id="translation-output-summary-copy"' in text
        assert 'id="translation-output-summary-path"' in text
        assert 'id="translation-output-change-section"' in text
        assert "Using default output folder" in text
        assert "Change folder/path" in text
        assert "English (EN)" in text
        assert "French (FR)" in text
        assert "Arabic (AR)" in text
        assert 'id="translation-run-status-shell"' in text
        assert 'id="translation-progress-percent"' in text
        assert 'id="translation-progress-bar"' in text
        assert 'id="translation-run-pages"' in text
        assert 'id="translation-run-current-page"' in text
        assert 'id="translation-run-image-retry"' in text
        assert 'id="translation-run-alerts"' in text
        assert 'id="translation-action-helper"' in text
        assert 'id="translation-open-completion"' in text
        assert 'id="translation-completion-drawer"' in text
        assert 'id="translation-completion-drawer-backdrop"' in text
        assert 'id="translation-close-completion"' in text
        assert 'id="translation-arabic-review-card"' in text
        assert 'id="translation-arabic-review-open"' in text
        assert 'id="translation-arabic-review-continue-now"' in text
        assert 'id="translation-arabic-review-continue-without-changes"' in text
        assert "Open the translated DOCX in Word, make any alignment or formatting fixes, save it, then return here." in translation_completion_drawer
        assert 'id="translation-gmail-step-card"' in text
        assert 'id="translation-gmail-confirm-current"' in text
        assert '<select id="case-city"' in text
        assert '<select id="service-city"' in text
        assert 'id="case-city-add"' in text
        assert 'id="service-city-add"' in text
        assert 'id="interpretation-location-guard-card"' in text
        assert 'id="travel-km-hint"' in text
        assert 'class="workspace-drawer-backdrop workspace-dialog-backdrop hidden" id="interpretation-city-dialog-backdrop"' in text
        assert 'id="interpretation-city-dialog-name"' in text
        assert 'id="interpretation-city-dialog-distance"' in text
        assert "Preview the selected attachment to inspect it here." not in text
        assert "Finish Translation" in translation_completion_drawer
        assert "Save Case Record" in translation_completion_drawer
        assert "Download translated DOCX" in translation_completion_drawer
        assert "Review Arabic document in Word" in translation_completion_drawer
        assert "Translated DOCX" in translation_completion_drawer
        assert "Save this Gmail attachment" in translation_completion_drawer
        assert "Create Gmail Reply" in gmail_batch_finalize_drawer
        assert "Create Gmail reply" in gmail_batch_finalize_drawer
        assert "Completion Surface" not in translation_completion_drawer
        assert "Save To Job Log" not in translation_completion_drawer
        assert "bounded translation finish surface" not in translation_completion_drawer
        assert "Durable DOCX" not in translation_completion_drawer
        assert "Confirm Current Translation Row" not in translation_completion_drawer
        assert "Finalize Gmail Batch" not in gmail_batch_finalize_drawer
        assert "Finalize Gmail Batch Reply" not in gmail_batch_finalize_drawer
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
        assert "Provider keys and local tools" in text
        assert 'id="gmail-batch-finalize-drawer"' in text
        assert 'id="gmail-batch-finalize-drawer-backdrop"' in text
        assert 'id="gmail-batch-finalize-run"' in text
        assert 'id="gmail-batch-finalize-report"' in text
        assert "Run Metrics (auto-filled)" in text
        assert "Amounts (EUR)" in text
        assert "Gmail interpretation ready" in new_job_view
        assert "Review the notice details, then create the Gmail reply." in new_job_view
        assert "Review Gmail message" in new_job_view
        assert 'id="interpretation-session-shell"' in text
        assert 'id="interpretation-session-result"' in text
        assert 'id="interpretation-session-primary"' in text
        assert 'id="interpretation-session-open-full-workspace"' in text
        assert 'class="workspace-drawer workspace-drawer-interpretation"' in text
        assert "Start Interpretation Request" in new_job_view
        assert "Connect Google Photos" in new_job_view
        assert "Choose from Google Photos" in new_job_view
        assert "Open Google sign-in" in new_job_view
        assert "Open Google Photos Picker" in new_job_view
        assert 'id="google-photos-open-signin"' in text
        assert 'id="google-photos-open-picker"' in text
        assert 'rel="noopener noreferrer"' in text
        assert 'id="google-photos-summary"' in text
        assert "Review Case Details" in new_job_view
        assert "Review details" in new_job_view
        assert "Start blank request" in new_job_view
        assert "Refresh history" in new_job_view
        assert "Current Interpretation Step" not in new_job_view
        assert "Open Full Workspace" not in new_job_view
        assert "Interpretation Intake" not in new_job_view
        assert "Seed Review" not in new_job_view
        assert "Action Rail" not in new_job_view
        assert "bounded review surface" not in interpretation_review_drawer
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
        assert "Review Interpretation Request" in interpretation_review_drawer
        assert "Service details" in interpretation_review_drawer
        assert "Using the case details" in interpretation_review_drawer
        assert "Document text" in interpretation_review_drawer
        assert "Optional wording and filename" in interpretation_review_drawer
        assert "Recipient" in interpretation_review_drawer
        assert "Recipient is filled automatically" in interpretation_review_drawer
        assert "Optional amounts and internal totals" in interpretation_review_drawer
        assert "Save case record" in interpretation_review_drawer
        assert "Create fee-request document" in interpretation_review_drawer
        assert "Create Gmail reply" in interpretation_review_drawer
        assert "Gmail reply details will appear here after the final step." in interpretation_review_drawer
        assert "Honorários Output" not in interpretation_review_drawer
        assert "Finalize Gmail Reply" not in interpretation_review_drawer
        assert "Save Interpretation Row" not in interpretation_review_drawer
        assert "Generate DOCX + PDF" not in interpretation_review_drawer
        assert "SERVICE" not in interpretation_review_drawer
        assert "TEXT" not in interpretation_review_drawer
        assert "RECIPIENT" not in interpretation_review_drawer
        assert 'id="interpretation-gmail-next-step-card"' not in text
        assert 'id="interpretation-open-gmail-session"' not in text
        assert "Service details" in text
        assert "Recipient" in text
        assert "Continue translation" in text
        assert "Continue interpretation" in text
        assert 'data-view="recent-jobs"' in text
        assert "Recent Work" in recent_jobs_view
        assert "Saved Cases" in recent_jobs_view
        assert "Loading saved cases..." in recent_jobs_view
        assert "Open saved work" in recent_jobs_view
        assert "Translation Runs" in recent_jobs_view
        assert "Saved Translation Cases" in recent_jobs_view
        assert "Saved Interpretation Requests" in recent_jobs_view
        assert "Job Log Overview" not in recent_jobs_view
        assert "job-log rows" not in recent_jobs_view
        assert "Bounded Review Flow" not in recent_jobs_view
        assert "bounded finish surface" not in recent_jobs_view
        assert "bounded review surface" not in recent_jobs_view
        assert "Translation Job Log History" not in recent_jobs_view
        assert 'data-view="settings"' in text
        assert 'id="settings-defaults-section"' in text
        assert 'id="settings-integrations-section"' in text
        assert 'id="settings-ops-section"' in text
        assert "App Settings" in settings_view
        assert "Daily defaults" in settings_view
        assert "Text, image, and Gmail tools" in settings_view
        assert "Provider keys and local tools" in settings_view
        assert "Advanced diagnostics and saved-work options" in settings_view
        assert "Check app tools" in settings_view
        assert "Default language" in settings_view
        assert "Gmail helper path" in settings_view
        assert "Enable Gmail attachment intake" in settings_view
        assert "Saved work database" in settings_view
        assert "Save settings" in settings_view
        assert "bounded operator sheet" not in settings_view
        assert "runtime summary" not in settings_view
        assert "admin controls" not in settings_view
        assert "Provider and Host Preflight" not in settings_view
        assert "Gmail Bridge" not in settings_view
        assert "Job Log DB" not in settings_view
        assert "Default Rate / Word JSON" not in settings_view
        assert 'data-view="profile"' in text
        assert "Profiles" in profile_view
        assert "Set the contact, payment, and travel details used in fee-request documents and Gmail replies." in profile_view
        assert "Choose the details used in documents" in profile_view
        assert "Copy profiles from live app" in profile_view
        assert "Edit Profile" in profile_drawer
        assert "Interpretation distances" in profile_drawer
        assert "Add or update distance" in profile_drawer
        assert "Advanced distance data" in profile_drawer
        assert "Save profile" in profile_drawer
        assert "Keep profile management bounded" not in profile_view
        assert "Editor Surface" not in profile_view
        assert "One Profile At A Time" not in profile_view
        assert "bounded drawer" not in profile_view
        assert "Travel Distances JSON" not in profile_drawer
        assert "Import Live Profiles" not in profile_view
        assert "Set Primary" not in profile_drawer
        assert "active runtime mode" not in profile_view
        assert 'id="profile-editor-drawer"' in text
        assert 'id="profile-editor-drawer-backdrop"' in text
        assert 'id="profile-close-editor"' in text
        assert 'id="profile-close-editor-footer"' in text
        assert 'data-view="power-tools"' in text
        assert "Advanced Tools" in power_tools_view
        assert "Glossary Setup" in power_tools_view
        assert "Build Glossary Suggestions" in power_tools_view
        assert "Quality Check" in power_tools_view
        assert "Troubleshooting Files and Run Report" in power_tools_view
        assert "Recent run folders" in power_tools_view
        assert "Specific PDFs" in power_tools_view
        assert "Full text" in power_tools_view
        assert "Headers only" in power_tools_view
        assert "Thorough" in power_tools_view
        assert "Extra thorough" in power_tools_view
        assert "This stays an operator surface" not in power_tools_view
        assert "bounded tool stack" not in power_tools_view
        assert 'data-view="extension-lab"' in text
        assert "Browser Helper Checks" in extension_lab_view
        assert "Technical Gmail Handoff Test" in extension_lab_view
        assert "Readiness Reason Guide" in extension_lab_view
        assert "Refresh checks" in extension_lab_view
        assert "Preview handoff request" in extension_lab_view
        assert "Use the technical details below only when troubleshooting." in extension_lab_view
        assert "bounded operator lab" not in extension_lab_view
        assert "Prepare Reason Catalog" not in extension_lab_view
        assert "Handoff Simulator" not in extension_lab_view
        assert "This stays an operator surface" not in extension_lab_view
        assert 'id="power-tools-refresh"' in text
        assert 'id="power-tools-status"' in text
        assert 'id="power-tools-glossary-details"' in text
        assert 'id="power-tools-builder-details"' in text
        assert 'id="power-tools-calibration-details"' in text
        assert 'id="power-tools-diagnostics-details"' in text
        assert 'id="power-tools-latest-run-dirs"' in text
        assert 'id="refresh-extension"' in text
        assert 'id="extension-status"' in text
        assert 'id="extension-details"' in text
        assert 'id="extension-reason-catalog"' in text
        assert 'id="extension-simulator-form"' in text
        assert 'id="sim-message-id"' in text
        assert 'id="sim-thread-id"' in text
        assert 'id="sim-subject"' in text
        assert 'id="sim-account-email"' in text
        assert 'id="simulate-handoff"' in text
        assert 'id="simulator-details"' in text
        assert '<option value="run_folders">Recent run folders</option>' in text
        assert '<option value="select_pdfs">Specific PDFs</option>' in text
        assert '<option value="full_text">Full text</option>' in text
        assert '<option value="headers_only">Headers only</option>' in text
        assert '<option value="high">Thorough</option>' in text
        assert '<option value="xhigh">Extra thorough</option>' in text
        assert "workspace-panel-gmail-session" not in text
        assert 'id="translation-postrun-panel"' not in text
        assert 'id="interpretation-export-panel"' not in text


def test_shadow_web_operator_routes_expose_guided_qt_topbar_copy() -> None:
    shell_js = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "shell_presentation.js"
    ).read_text(encoding="utf-8")

    assert 'activeView === "power-tools"' in shell_js
    assert 'eyebrow: "Advanced Tools"' in shell_js
    assert 'title: "LegalPDF Translate | Advanced Tools"' in shell_js
    assert 'status: "Use glossary, quality-check, and troubleshooting tools when you need more control."' in shell_js
    assert 'activeView === "extension-lab"' in shell_js
    assert 'eyebrow: "Browser Helper"' in shell_js
    assert 'title: "LegalPDF Translate | Browser Helper Checks"' in shell_js
    assert 'status: "Check the browser helper used for Gmail intake. Technical details stay below."' in shell_js


def test_shadow_web_shell_presentation_module_centralizes_navigation_and_topbar_copy() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    shell_module = static_dir / "shell_presentation.js"

    assert shell_module.exists()
    assert 'from "./shell_presentation.js"' in app_js

    script = """
const shell = await import(__SHELL_MODULE_URL__);

const navigation = [
  { id: "dashboard", label: "Dashboard", status: "ready" },
  { id: "settings", label: "Settings", status: "ready" },
  { id: "new-job", label: "New Job", status: "ready" },
  { id: "gmail-intake", label: "Gmail", status: "warming" },
  { id: "recent-jobs", label: "Recent Work", status: "ready" },
  { id: "profile", label: "Profile", status: "ready" },
  { id: "power-tools", label: "Power Tools", status: "ready" },
  { id: "extension-lab", label: "Extension Lab", status: "ready" },
];

const hiddenGmail = shell.buildNavigationGroups(navigation, { showGmailNav: false });
const visibleGmail = shell.buildNavigationGroups(navigation, { showGmailNav: true });
const payload = {
  dashboard: shell.deriveRouteAwareTopbarStatus({
    runtime: { live_data: false },
    activeView: "dashboard",
    uiVariant: "qt",
    operatorChromeActive: false,
  }),
  powerTools: shell.deriveRouteAwareTopbarStatus({
    runtime: { live_data: true },
    activeView: "power-tools",
    uiVariant: "qt",
    operatorChromeActive: true,
  }),
  fallback: shell.deriveRouteAwareTopbarStatus({
    runtime: { live_data: false },
    activeView: "custom-view",
    uiVariant: "legacy",
    operatorChromeActive: false,
    navLabel: "Custom View",
  }),
  hiddenPrimaryIds: hiddenGmail.primary.map((item) => item.id),
  visiblePrimaryIds: visibleGmail.primary.map((item) => item.id),
  moreIds: visibleGmail.more.map((item) => item.id),
  dailyBanner: shell.shouldShowDailyRuntimeModeBanner({
    uiVariant: "qt",
    activeView: "new-job",
    operatorChromeActive: false,
  }),
  operatorRoute: shell.isOperatorRoute("extension-lab"),
  runtimeLabel: shell.runtimeModeDisplayLabel({ live_data: true }),
  beginnerLabel: shell.beginnerSurfaceTargetLabel("profile"),
};

console.log(JSON.stringify(payload));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__SHELL_MODULE_URL__": "shell_presentation.js"},
        timeout_seconds=30,
    )

    assert results["dashboard"] == {
        "eyebrow": "Overview",
        "title": "LegalPDF Translate",
        "status": "Check what is ready and choose what you want to do next.",
        "tone": "ok",
    }
    assert results["powerTools"] == {
        "eyebrow": "Advanced Tools",
        "title": "LegalPDF Translate | Advanced Tools",
        "status": "Use glossary, quality-check, and troubleshooting tools when you need more control.",
        "tone": "info",
    }
    assert results["fallback"]["status"] == "Test mode: using isolated app data. Live Gmail and saved work may differ."
    assert results["hiddenPrimaryIds"] == ["new-job", "recent-jobs"]
    assert results["visiblePrimaryIds"] == ["new-job", "gmail-intake", "recent-jobs"]
    assert results["moreIds"] == ["dashboard", "settings", "profile", "power-tools", "extension-lab"]
    assert results["dailyBanner"] is True
    assert results["operatorRoute"] is True
    assert results["runtimeLabel"] == "Live mode"
    assert results["beginnerLabel"] == "profile setup screen"


def test_shadow_web_shell_ui_module_centralizes_safe_navigation_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    shell_ui_js = static_dir / "shell_ui.js"
    shell_ui_source = shell_ui_js.read_text(encoding="utf-8")

    assert shell_ui_js.exists()
    assert 'from "./shell_ui.js"' in app_js
    assert "export function renderNavigationInto" in shell_ui_source
    assert "export function renderLiveBannerInto" in shell_ui_source
    assert "export function renderRuntimeModeSelectorInto" in shell_ui_source
    assert "export function renderShellVisibilityInto" in shell_ui_source
    assert "export function renderRuntimeModeBannerInto" in shell_ui_source
    assert "export function renderOperatorChromeInto" in shell_ui_source
    assert "export function renderShellChromeInto" in shell_ui_source
    assert "renderNavigationInto({" in app_js
    assert 'renderLiveBannerInto(qs("live-banner"), runtime);' in app_js
    assert 'renderRuntimeModeSelectorInto(qs("runtime-mode-select"), runtimeMode);' in app_js
    assert "renderShellVisibilityInto({" in app_js
    assert "renderRuntimeModeBannerInto(" in app_js
    assert "renderOperatorChromeInto(" in app_js
    assert "renderShellChromeInto(" in app_js
    assert "MORE_NAV_ORDER.includes(appState.activeView)" not in app_js
    assert "button.innerHTML" not in app_js
    assert "innerHTML" not in shell_ui_source

    script = r"""
const shellUi = await import(__SHELL_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    children: [],
    parentNode: null,
    dataset: {},
    attributes: {},
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    open: false,
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      contains(name) {
        return classNames.has(String(name));
      },
      toggle(name, force) {
        const key = String(name);
        const enabled = force === undefined ? !classNames.has(key) : Boolean(force);
        if (enabled) {
          classNames.add(key);
        } else {
          classNames.delete(key);
        }
        syncClassList(element, classNames);
        return enabled;
      },
    },
    setAttribute(name, value) {
      this.attributes[name] = String(value ?? "");
    },
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(this.attributes, name)
        ? this.attributes[name]
        : null;
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function serializeButtons(container) {
  return container.children.map((button) => ({
    tagName: button.tagName,
    type: button.type,
    className: button.className,
    view: button.dataset.view,
    labelTag: button.children[0]?.tagName || "",
    label: button.children[0]?.textContent || "",
    metaClass: button.children[1]?.className || "",
    meta: button.children[1]?.textContent || "",
  }));
}

function serializeOptions(select) {
  return select.children.map((option) => ({
    tagName: option.tagName,
    value: option.value,
    text: option.textContent,
    selected: Boolean(option.selected),
  }));
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const items = [
  { id: "dashboard", label: `Dashboard ${malicious}`, status: "ready" },
  { id: "settings", label: "Settings", status: `warming ${malicious}` },
  { id: "new-job", label: `New Job ${malicious}`, status: "ready" },
  { id: "gmail-intake", label: `Gmail ${malicious}`, status: `warming ${malicious}` },
  { id: "recent-jobs", label: "Recent Work", status: "blocked" },
  { id: "profile", label: "Profile", status: "ready" },
  { id: "power-tools", label: "Power Tools", status: "ready" },
  { id: "extension-lab", label: "Extension Lab", status: "ready" },
];

const primaryContainer = document.createElement("nav");
const moreContainer = document.createElement("nav");
const moreShell = document.createElement("details");
shellUi.renderNavigationInto({
  primaryContainer,
  moreContainer,
  moreShell,
  items,
  activeView: "new-job",
  showGmailNav: false,
});
const hiddenSnapshot = {
  primary: serializeButtons(primaryContainer),
  more: serializeButtons(moreContainer),
  moreOpen: moreShell.open,
  moreClass: moreShell.className,
};

shellUi.renderNavigationInto({
  primaryContainer,
  moreContainer,
  moreShell,
  items,
  activeView: "settings",
  showGmailNav: true,
});

const runtimeSelect = document.createElement("select");
shellUi.renderRuntimeModeSelectorInto(runtimeSelect, {
  current_mode: "live",
  supported_modes: [
    { id: "shadow", label: `Shadow ${malicious}` },
    { id: "live", label: `Live ${malicious}` },
  ],
});

const emptyRuntimeSelect = document.createElement("select");
emptyRuntimeSelect.appendChild(document.createElement("option"));
shellUi.renderRuntimeModeSelectorInto(emptyRuntimeSelect, {
  current_mode: "",
  supported_modes: [],
});

const liveBanner = document.createElement("div");
liveBanner.className = "live-banner hidden";
shellUi.renderLiveBannerInto(liveBanner, { live_data: true });
const liveBannerSnapshot = {
  text: liveBanner.textContent,
  className: liveBanner.className,
};
shellUi.renderLiveBannerInto(liveBanner, { live_data: false });
const shadowBannerSnapshot = {
  text: liveBanner.textContent,
  className: liveBanner.className,
};

const runtimeModeBanner = document.createElement("div");
runtimeModeBanner.className = "runtime-mode-banner hidden";
runtimeModeBanner.dataset.mode = "stale";
shellUi.renderRuntimeModeBannerInto(runtimeModeBanner, {
  show: true,
  message: `Shadow ${malicious}`,
  mode: "shadow",
});
const visibleRuntimeModeBanner = {
  text: runtimeModeBanner.textContent,
  className: runtimeModeBanner.className,
  mode: runtimeModeBanner.dataset.mode || "",
  imgCount: countTag(runtimeModeBanner, "img"),
  scriptCount: countTag(runtimeModeBanner, "script"),
  innerHTMLWrites: countInnerHtmlWrites(runtimeModeBanner),
};
shellUi.renderRuntimeModeBannerInto(runtimeModeBanner, {
  show: false,
  message: `Live ${malicious}`,
  mode: "live",
});
const hiddenRuntimeModeBanner = {
  text: runtimeModeBanner.textContent,
  className: runtimeModeBanner.className,
  hasMode: Object.prototype.hasOwnProperty.call(runtimeModeBanner.dataset, "mode"),
  innerHTMLWrites: countInnerHtmlWrites(runtimeModeBanner),
};
shellUi.renderRuntimeModeBannerInto(runtimeModeBanner, {
  show: true,
  message: "",
  mode: "live",
});
const emptyVisibleRuntimeModeBanner = {
  text: runtimeModeBanner.textContent,
  className: runtimeModeBanner.className,
  mode: runtimeModeBanner.dataset.mode || "",
  innerHTMLWrites: countInnerHtmlWrites(runtimeModeBanner),
};

const operatorBody = document.createElement("body");
const operatorToggle = document.createElement("button");
const operatorHint = document.createElement("p");
operatorToggle.textContent = `Seed ${malicious}`;
operatorHint.textContent = `Seed ${malicious}`;
shellUi.renderOperatorChromeInto(
  { body: operatorBody, toggle: operatorToggle, hint: operatorHint },
  { active: true, operatorMode: false },
);
const operatorActiveAuto = {
  bodyMode: operatorBody.dataset.operatorChrome,
  ariaPressed: operatorToggle.getAttribute("aria-pressed"),
  toggleText: operatorToggle.textContent,
  hintText: operatorHint.textContent,
  imgCount: countTag(operatorToggle, "img") + countTag(operatorHint, "img"),
  scriptCount: countTag(operatorToggle, "script") + countTag(operatorHint, "script"),
  innerHTMLWrites: countInnerHtmlWrites(operatorToggle, operatorHint),
};
shellUi.renderOperatorChromeInto(
  { body: operatorBody, toggle: operatorToggle, hint: operatorHint },
  { active: true, operatorMode: true },
);
const operatorExplicit = {
  bodyMode: operatorBody.dataset.operatorChrome,
  ariaPressed: operatorToggle.getAttribute("aria-pressed"),
  toggleText: operatorToggle.textContent,
  hintText: operatorHint.textContent,
  innerHTMLWrites: countInnerHtmlWrites(operatorToggle, operatorHint),
};
shellUi.renderOperatorChromeInto(
  { body: operatorBody, toggle: operatorToggle, hint: operatorHint },
  { active: false, operatorMode: false },
);
const operatorInactive = {
  bodyMode: operatorBody.dataset.operatorChrome,
  ariaPressed: operatorToggle.getAttribute("aria-pressed"),
  toggleText: operatorToggle.textContent,
  hintText: operatorHint.textContent,
  innerHTMLWrites: countInnerHtmlWrites(operatorToggle, operatorHint),
};
const operatorBodyOnly = document.createElement("body");
const operatorMissingToggleResultType = typeof shellUi.renderOperatorChromeInto(
  { body: operatorBodyOnly, toggle: null, hint: null },
  { active: true, operatorMode: true },
);

const shellChromeBody = document.createElement("body");
const shellChromeEyebrow = document.createElement("p");
const shellChromeTitle = document.createElement("h2");
const shellChromeWorkspace = document.createElement("strong");
const shellChromeRuntime = document.createElement("p");
shellChromeWorkspace.textContent = "Keep workspace";
shellChromeRuntime.textContent = "Keep runtime";
shellUi.renderShellChromeInto(
  {
    body: shellChromeBody,
    eyebrow: shellChromeEyebrow,
    title: shellChromeTitle,
    workspaceLabel: shellChromeWorkspace,
    runtimeModeLabel: shellChromeRuntime,
  },
  {
    activeView: `profile ${malicious}`,
    beginnerSurface: true,
    eyebrow: `Profile ${malicious}`,
    title: `Profiles ${malicious}`,
    workspaceLabel: `workspace-1 ${malicious}`,
    runtimeModeLabel: `Test mode ${malicious}`,
  },
);
const shellChromeVisible = {
  activeView: shellChromeBody.dataset.activeView,
  beginnerSurface: shellChromeBody.dataset.beginnerSurface,
  eyebrow: shellChromeEyebrow.textContent,
  title: shellChromeTitle.textContent,
  workspace: shellChromeWorkspace.textContent,
  runtime: shellChromeRuntime.textContent,
  imgCount: countTag(shellChromeEyebrow, "img")
    + countTag(shellChromeTitle, "img")
    + countTag(shellChromeWorkspace, "img")
    + countTag(shellChromeRuntime, "img"),
  scriptCount: countTag(shellChromeEyebrow, "script")
    + countTag(shellChromeTitle, "script")
    + countTag(shellChromeWorkspace, "script")
    + countTag(shellChromeRuntime, "script"),
  innerHTMLWrites: countInnerHtmlWrites(
    shellChromeEyebrow,
    shellChromeTitle,
    shellChromeWorkspace,
    shellChromeRuntime,
  ),
};
shellUi.renderShellChromeInto(
  {
    body: shellChromeBody,
    eyebrow: shellChromeEyebrow,
    title: shellChromeTitle,
    workspaceLabel: shellChromeWorkspace,
    runtimeModeLabel: shellChromeRuntime,
  },
  {
    activeView: "extension-lab",
    beginnerSurface: false,
    eyebrow: "Extension Lab",
    title: "Extension Lab",
    workspaceLabel: "",
    runtimeModeLabel: "",
  },
);
const shellChromeSkippedLabels = {
  activeView: shellChromeBody.dataset.activeView,
  beginnerSurface: shellChromeBody.dataset.beginnerSurface,
  eyebrow: shellChromeEyebrow.textContent,
  title: shellChromeTitle.textContent,
  workspace: shellChromeWorkspace.textContent,
  runtime: shellChromeRuntime.textContent,
  innerHTMLWrites: countInnerHtmlWrites(
    shellChromeEyebrow,
    shellChromeTitle,
    shellChromeWorkspace,
    shellChromeRuntime,
  ),
};

const newJobView = document.createElement("section");
newJobView.className = "page-view";
newJobView.dataset.view = "new-job";
const settingsView = document.createElement("section");
settingsView.className = "page-view hidden";
settingsView.dataset.view = "settings";
const newJobButton = document.createElement("button");
newJobButton.className = "nav-button active";
newJobButton.dataset.view = "new-job";
const settingsButton = document.createElement("button");
settingsButton.className = "nav-button";
settingsButton.dataset.view = "settings";
const visibilityMoreShell = document.createElement("details");

shellUi.renderShellVisibilityInto({
  views: [newJobView, settingsView],
  navButtons: [newJobButton, settingsButton],
  moreShell: visibilityMoreShell,
  activeView: "settings",
});
const settingsVisibility = {
  newJobClass: newJobView.className,
  settingsClass: settingsView.className,
  newJobButtonClass: newJobButton.className,
  settingsButtonClass: settingsButton.className,
  moreOpen: visibilityMoreShell.open,
  moreClass: visibilityMoreShell.className,
  innerHTMLWrites: countInnerHtmlWrites(
    newJobView,
    settingsView,
    newJobButton,
    settingsButton,
    visibilityMoreShell,
  ),
};

shellUi.renderShellVisibilityInto({
  views: [newJobView, settingsView],
  navButtons: [newJobButton, settingsButton],
  moreShell: visibilityMoreShell,
  activeView: "new-job",
});
const newJobVisibility = {
  newJobClass: newJobView.className,
  settingsClass: settingsView.className,
  newJobButtonClass: newJobButton.className,
  settingsButtonClass: settingsButton.className,
  moreOpen: visibilityMoreShell.open,
  moreClass: visibilityMoreShell.className,
};

console.log(JSON.stringify({
  exportedType: typeof shellUi.renderNavigationInto,
  runtimeControlExportTypes: {
    liveBanner: typeof shellUi.renderLiveBannerInto,
    runtimeSelector: typeof shellUi.renderRuntimeModeSelectorInto,
    shellVisibility: typeof shellUi.renderShellVisibilityInto,
    runtimeModeBanner: typeof shellUi.renderRuntimeModeBannerInto,
    operatorChrome: typeof shellUi.renderOperatorChromeInto,
    shellChrome: typeof shellUi.renderShellChromeInto,
  },
  hidden: hiddenSnapshot,
  visible: {
    primary: serializeButtons(primaryContainer),
    more: serializeButtons(moreContainer),
    moreOpen: moreShell.open,
    moreClass: moreShell.className,
    text: `${primaryContainer.textContent}${moreContainer.textContent}`,
    imgCount: countTag(primaryContainer, "img") + countTag(moreContainer, "img"),
    scriptCount: countTag(primaryContainer, "script") + countTag(moreContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(primaryContainer, moreContainer, moreShell),
  },
  runtimeControls: {
    options: serializeOptions(runtimeSelect),
    text: runtimeSelect.textContent,
    imgCount: countTag(runtimeSelect, "img"),
    scriptCount: countTag(runtimeSelect, "script"),
    innerHTMLWrites: countInnerHtmlWrites(runtimeSelect),
    emptyOptions: serializeOptions(emptyRuntimeSelect),
    emptyInnerHTMLWrites: countInnerHtmlWrites(emptyRuntimeSelect),
    liveBanner: liveBannerSnapshot,
    shadowBanner: shadowBannerSnapshot,
    missingRuntimeResultType: typeof shellUi.renderRuntimeModeSelectorInto(null, {
      supported_modes: [{ id: "ignored", label: "Ignored" }],
    }),
    missingBannerResultType: typeof shellUi.renderLiveBannerInto(null, { live_data: true }),
    runtimeModeBanner: {
      visible: visibleRuntimeModeBanner,
      hidden: hiddenRuntimeModeBanner,
      emptyVisible: emptyVisibleRuntimeModeBanner,
      missingResultType: typeof shellUi.renderRuntimeModeBannerInto(null, {
        show: true,
        message: "Ignored",
        mode: "live",
      }),
    },
    operatorChrome: {
      activeAuto: operatorActiveAuto,
      explicit: operatorExplicit,
      inactive: operatorInactive,
      missingToggleResultType: operatorMissingToggleResultType,
      bodyOnlyMode: operatorBodyOnly.dataset.operatorChrome,
      missingResultType: typeof shellUi.renderOperatorChromeInto(
        { body: null, toggle: null, hint: null },
        { active: true, operatorMode: true },
      ),
    },
    shellChrome: {
      visible: shellChromeVisible,
      skippedLabels: shellChromeSkippedLabels,
      missingResultType: typeof shellUi.renderShellChromeInto(
        {
          body: null,
          eyebrow: null,
          title: null,
          workspaceLabel: null,
          runtimeModeLabel: null,
        },
        {
          activeView: "ignored",
          beginnerSurface: true,
          eyebrow: "Ignored",
          title: "Ignored",
          workspaceLabel: "Ignored",
          runtimeModeLabel: "Ignored",
        },
      ),
    },
  },
  shellVisibility: {
    settings: settingsVisibility,
    newJob: newJobVisibility,
    missingResultType: typeof shellUi.renderShellVisibilityInto({
      views: null,
      navButtons: null,
      moreShell: null,
      activeView: "settings",
    }),
  },
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__SHELL_UI_MODULE_URL__": "shell_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["runtimeControlExportTypes"] == {
        "liveBanner": "function",
        "runtimeSelector": "function",
        "shellVisibility": "function",
        "runtimeModeBanner": "function",
        "operatorChrome": "function",
        "shellChrome": "function",
    }
    assert [button["view"] for button in results["hidden"]["primary"]] == ["new-job", "recent-jobs"]
    assert [button["view"] for button in results["hidden"]["more"]] == [
        "dashboard",
        "settings",
        "profile",
        "power-tools",
        "extension-lab",
    ]
    assert results["hidden"]["moreOpen"] is False
    assert results["hidden"]["moreClass"] == ""
    assert results["hidden"]["primary"][0]["className"] == "nav-button active"
    assert results["hidden"]["primary"][0]["labelTag"] == "SPAN"
    assert results["hidden"]["primary"][0]["label"] == "New Job <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["hidden"]["primary"][0]["metaClass"] == "nav-meta"
    assert results["hidden"]["primary"][0]["meta"] == "Ready"
    assert results["hidden"]["primary"][1]["meta"] == "blocked"

    assert [button["view"] for button in results["visible"]["primary"]] == ["new-job", "gmail-intake", "recent-jobs"]
    assert [button["view"] for button in results["visible"]["more"]] == [
        "dashboard",
        "settings",
        "profile",
        "power-tools",
        "extension-lab",
    ]
    assert results["visible"]["moreOpen"] is True
    assert results["visible"]["moreClass"] == "has-active-view"
    active_buttons = [
        button for button in [*results["visible"]["primary"], *results["visible"]["more"]]
        if "active" in button["className"].split()
    ]
    assert [button["view"] for button in active_buttons] == ["settings"]
    gmail_button = results["visible"]["primary"][1]
    assert gmail_button["label"] == "Gmail <img src=x onerror=alert(1)><script>bad()</script>"
    assert gmail_button["meta"] == "warming <img src=x onerror=alert(1)><script>bad()</script>"
    assert gmail_button["metaClass"] == "nav-meta"
    assert "Dashboard <img src=x onerror=alert(1)><script>bad()</script>" in results["visible"]["text"]
    assert results["visible"]["imgCount"] == 0
    assert results["visible"]["scriptCount"] == 0
    assert results["visible"]["innerHTMLWrites"] == 0
    assert results["runtimeControls"]["options"] == [
        {
            "tagName": "OPTION",
            "value": "shadow",
            "text": "Shadow <img src=x onerror=alert(1)><script>bad()</script>",
            "selected": False,
        },
        {
            "tagName": "OPTION",
            "value": "live",
            "text": "Live <img src=x onerror=alert(1)><script>bad()</script>",
            "selected": True,
        },
    ]
    assert "Shadow <img src=x onerror=alert(1)><script>bad()</script>" in results["runtimeControls"]["text"]
    assert results["runtimeControls"]["imgCount"] == 0
    assert results["runtimeControls"]["scriptCount"] == 0
    assert results["runtimeControls"]["innerHTMLWrites"] == 0
    assert results["runtimeControls"]["emptyOptions"] == []
    assert results["runtimeControls"]["emptyInnerHTMLWrites"] == 0
    assert results["runtimeControls"]["liveBanner"] == {
        "text": "Live mode: using your real settings, Gmail drafts, and saved work.",
        "className": "live-banner",
    }
    assert results["runtimeControls"]["shadowBanner"] == {"text": "", "className": "live-banner hidden"}
    assert results["runtimeControls"]["missingRuntimeResultType"] == "undefined"
    assert results["runtimeControls"]["missingBannerResultType"] == "undefined"
    assert results["runtimeControls"]["runtimeModeBanner"]["visible"] == {
        "text": "Shadow <img src=x onerror=alert(1)><script>bad()</script>",
        "className": "runtime-mode-banner",
        "mode": "shadow",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["runtimeModeBanner"]["hidden"] == {
        "text": "",
        "className": "runtime-mode-banner hidden",
        "hasMode": False,
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["runtimeModeBanner"]["emptyVisible"] == {
        "text": "",
        "className": "runtime-mode-banner",
        "mode": "live",
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["runtimeModeBanner"]["missingResultType"] == "undefined"
    assert results["runtimeControls"]["operatorChrome"]["activeAuto"] == {
        "bodyMode": "on",
        "ariaPressed": "false",
        "toggleText": "Show Technical Details",
        "hintText": "Build, listener, and diagnostics panels stay hidden until you ask for them or a failure occurs.",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["operatorChrome"]["explicit"] == {
        "bodyMode": "on",
        "ariaPressed": "true",
        "toggleText": "Hide Technical Details",
        "hintText": "Technical build, listener, and diagnostics panels stay visible across the shell until you turn them off.",
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["operatorChrome"]["inactive"] == {
        "bodyMode": "off",
        "ariaPressed": "false",
        "toggleText": "Show Technical Details",
        "hintText": "Build, listener, and diagnostics panels stay hidden until you ask for them or a failure occurs.",
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["operatorChrome"]["missingToggleResultType"] == "undefined"
    assert results["runtimeControls"]["operatorChrome"]["bodyOnlyMode"] == "on"
    assert results["runtimeControls"]["operatorChrome"]["missingResultType"] == "undefined"
    assert results["runtimeControls"]["shellChrome"]["visible"] == {
        "activeView": "profile <img src=x onerror=alert(1)><script>bad()</script>",
        "beginnerSurface": "true",
        "eyebrow": "Profile <img src=x onerror=alert(1)><script>bad()</script>",
        "title": "Profiles <img src=x onerror=alert(1)><script>bad()</script>",
        "workspace": "workspace-1 <img src=x onerror=alert(1)><script>bad()</script>",
        "runtime": "Test mode <img src=x onerror=alert(1)><script>bad()</script>",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["shellChrome"]["skippedLabels"] == {
        "activeView": "extension-lab",
        "beginnerSurface": "false",
        "eyebrow": "Extension Lab",
        "title": "Extension Lab",
        "workspace": "workspace-1 <img src=x onerror=alert(1)><script>bad()</script>",
        "runtime": "Test mode <img src=x onerror=alert(1)><script>bad()</script>",
        "innerHTMLWrites": 0,
    }
    assert results["runtimeControls"]["shellChrome"]["missingResultType"] == "undefined"
    assert results["shellVisibility"]["settings"] == {
        "newJobClass": "page-view hidden",
        "settingsClass": "page-view",
        "newJobButtonClass": "nav-button",
        "settingsButtonClass": "nav-button active",
        "moreOpen": True,
        "moreClass": "has-active-view",
        "innerHTMLWrites": 0,
    }
    assert results["shellVisibility"]["newJob"] == {
        "newJobClass": "page-view",
        "settingsClass": "page-view hidden",
        "newJobButtonClass": "nav-button active",
        "settingsButtonClass": "nav-button",
        "moreOpen": True,
        "moreClass": "",
    }
    assert results["shellVisibility"]["missingResultType"] == "undefined"


def test_shadow_web_new_job_ui_module_centralizes_task_switch_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    new_job_ui_js = static_dir / "new_job_ui.js"
    assert new_job_ui_js.exists()
    new_job_ui_source = new_job_ui_js.read_text(encoding="utf-8")

    assert 'from "./new_job_ui.js"' in app_js
    assert "export function syncNewJobTaskControlsInto" in new_job_ui_source
    assert "syncNewJobTaskControlsInto({" in app_js
    assert 'qsa("[data-task-panel]").forEach' not in app_js
    assert 'qsa(".task-switch").forEach' not in app_js
    assert "innerHTML" not in new_job_ui_source

    script = r"""
const newJobUi = await import(__NEW_JOB_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    dataset: {},
    attributes: {},
    innerHTMLAssignments: [],
    _innerHTML: "",
    _textContent: "",
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      contains(name) {
        return classNames.has(String(name));
      },
      toggle(name, force) {
        const key = String(name);
        const enabled = force === undefined ? !classNames.has(key) : Boolean(force);
        if (enabled) {
          classNames.add(key);
        } else {
          classNames.delete(key);
        }
        syncClassList(element, classNames);
        return enabled;
      },
    },
    setAttribute(name, value) {
      this.attributes[name] = String(value ?? "");
    },
    getAttribute(name) {
      return Object.prototype.hasOwnProperty.call(this.attributes, name)
        ? this.attributes[name]
        : null;
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      this._innerHTML = String(value ?? "");
      this.innerHTMLAssignments.push(this._innerHTML);
      this._textContent = "";
    },
  });
  return element;
}

function countInnerHtmlWrites(...nodes) {
  return nodes.reduce((total, node) => total + (node?.innerHTMLAssignments || []).length, 0);
}

function makePanel(task, className = "simple-task-shell") {
  const panel = makeElement("div");
  panel.className = className;
  panel.dataset.taskPanel = task;
  return panel;
}

function makeSwitch(task, className = "task-switch") {
  const button = makeElement("button");
  button.className = className;
  button.dataset.task = task;
  button.setAttribute("aria-selected", "false");
  return button;
}

const translationPanel = makePanel("translation");
const interpretationPanel = makePanel("interpretation", "simple-task-shell hidden");
const translationSwitch = makeSwitch("translation", "task-switch active");
const interpretationSwitch = makeSwitch("interpretation");
const maliciousSwitch = makeSwitch(`<img src=x onerror=alert(1)>`);

newJobUi.syncNewJobTaskControlsInto({
  panels: [translationPanel, interpretationPanel],
  switches: [translationSwitch, interpretationSwitch, maliciousSwitch],
  activeTask: "interpretation",
});
const interpretationState = {
  translationPanelClass: translationPanel.className,
  interpretationPanelClass: interpretationPanel.className,
  translationSwitchClass: translationSwitch.className,
  translationAria: translationSwitch.getAttribute("aria-selected"),
  interpretationSwitchClass: interpretationSwitch.className,
  interpretationAria: interpretationSwitch.getAttribute("aria-selected"),
  maliciousSwitchClass: maliciousSwitch.className,
  maliciousAria: maliciousSwitch.getAttribute("aria-selected"),
  innerHTMLWrites: countInnerHtmlWrites(
    translationPanel,
    interpretationPanel,
    translationSwitch,
    interpretationSwitch,
    maliciousSwitch,
  ),
};

newJobUi.syncNewJobTaskControlsInto({
  panels: [translationPanel, interpretationPanel],
  switches: [translationSwitch, interpretationSwitch, maliciousSwitch],
  activeTask: `<img src=x onerror=alert(1)>`,
});
const maliciousTaskState = {
  translationPanelClass: translationPanel.className,
  interpretationPanelClass: interpretationPanel.className,
  translationSwitchClass: translationSwitch.className,
  translationAria: translationSwitch.getAttribute("aria-selected"),
  interpretationSwitchClass: interpretationSwitch.className,
  interpretationAria: interpretationSwitch.getAttribute("aria-selected"),
  maliciousSwitchClass: maliciousSwitch.className,
  maliciousAria: maliciousSwitch.getAttribute("aria-selected"),
  innerHTMLWrites: countInnerHtmlWrites(
    translationPanel,
    interpretationPanel,
    translationSwitch,
    interpretationSwitch,
    maliciousSwitch,
  ),
};

const missingResult = newJobUi.syncNewJobTaskControlsInto({
  panels: null,
  switches: null,
  activeTask: "interpretation",
});

console.log(JSON.stringify({
  exportedType: typeof newJobUi.syncNewJobTaskControlsInto,
  interpretationState,
  maliciousTaskState,
  missingResultType: typeof missingResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__NEW_JOB_UI_MODULE_URL__": "new_job_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["interpretationState"] == {
        "translationPanelClass": "simple-task-shell hidden",
        "interpretationPanelClass": "simple-task-shell",
        "translationSwitchClass": "task-switch",
        "translationAria": "false",
        "interpretationSwitchClass": "task-switch active",
        "interpretationAria": "true",
        "maliciousSwitchClass": "task-switch",
        "maliciousAria": "false",
        "innerHTMLWrites": 0,
    }
    assert results["maliciousTaskState"] == {
        "translationPanelClass": "simple-task-shell",
        "interpretationPanelClass": "simple-task-shell hidden",
        "translationSwitchClass": "task-switch active",
        "translationAria": "true",
        "interpretationSwitchClass": "task-switch",
        "interpretationAria": "false",
        "maliciousSwitchClass": "task-switch",
        "maliciousAria": "false",
        "innerHTMLWrites": 0,
    }
    assert results["missingResultType"] == "undefined"


def test_google_photos_busy_guard_allows_connect_when_choose_is_disabled() -> None:
    script = """
function makeButton(id, { disabled = false, textContent = id } = {}) {
  return {
    id,
    tagName: "BUTTON",
    disabled,
    textContent,
    dataset: {},
    attributes: {},
    setAttribute(name, value) {
      this.attributes[name] = String(value);
    },
  };
}

const elements = new Map([
  ["google-photos-connect", makeButton("google-photos-connect", { textContent: "Connect Google Photos" })],
  ["google-photos-choose", makeButton("google-photos-choose", {
    disabled: true,
    textContent: "Choose from Google Photos",
  })],
  ["photo-submit", makeButton("photo-submit", { textContent: "Recover from photo or screenshot" })],
]);

globalThis.document = {
  body: { dataset: {} },
  getElementById(id) {
    return elements.get(id) || null;
  },
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
  createElement(tagName) {
    return { tagName: String(tagName).toUpperCase(), dataset: {}, children: [], appendChild() {} };
  },
  addEventListener() {},
};

globalThis.window = {
  LEGALPDF_BROWSER_BOOTSTRAP: {
    defaultRuntimeMode: "shadow",
    defaultWorkspaceId: "google-photos-stage2",
    defaultUiVariant: "qt",
    shadowHost: "127.0.0.1",
    shadowPort: 8890,
    buildSha: "test",
    assetVersion: "test-assets",
    staticBasePath: "http://127.0.0.1:8890/static-build/test-assets/",
  },
  location: new URL("http://127.0.0.1:8890/?mode=shadow&workspace=google-photos-stage2#new-job"),
  history: { replaceState() {} },
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() {},
  setTimeout() { return 1; },
  clearTimeout() {},
  confirm() { return true; },
};
globalThis.CustomEvent = class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
};

const appModule = await import(__APP_MODULE_URL__);

let connectActions = 0;
await appModule.runWithBusy(
  ["google-photos-connect", "google-photos-choose"],
  { "google-photos-connect": "Connecting..." },
  async () => {
    connectActions += 1;
  },
  { guardIds: ["google-photos-connect"] },
);

elements.get("google-photos-choose").disabled = true;
let chooseActions = 0;
await appModule.runWithBusy(
  ["google-photos-connect", "google-photos-choose", "photo-submit"],
  { "google-photos-choose": "Choosing..." },
  async () => {
    chooseActions += 1;
  },
  { guardIds: ["google-photos-choose"] },
);

console.log(JSON.stringify({
  connectActions,
  chooseActions,
  connectAriaBusy: elements.get("google-photos-connect").attributes["aria-busy"],
  chooseAriaBusy: elements.get("google-photos-choose").attributes["aria-busy"],
}));
"""
    results = run_browser_esm_json_probe(script, {"__APP_MODULE_URL__": "app.js"}, timeout_seconds=30)

    assert results["connectActions"] == 1
    assert results["chooseActions"] == 0
    assert results["connectAriaBusy"] == "false"
    assert results["chooseAriaBusy"] == "false"


def test_google_photos_oauth_fallback_is_visible_without_rendering_url_text() -> None:
    script = """
function makeClassList(initial = []) {
  const values = new Set(initial);
  return {
    add(value) {
      values.add(value);
    },
    remove(value) {
      values.delete(value);
    },
    contains(value) {
      return values.has(value);
    },
    toArray() {
      return Array.from(values).sort();
    },
  };
}

function makeElement(id, { tagName = "DIV", disabled = false, textContent = "" } = {}) {
  return {
    id,
    tagName,
    disabled,
    textContent,
    dataset: {},
    attributes: {},
    classList: makeClassList(id === "google-photos-open-signin" ? ["hidden"] : []),
    href: "",
    tabIndex: 0,
    setAttribute(name, value) {
      this.attributes[name] = String(value);
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "href") {
        this.href = "";
      }
    },
  };
}

const elements = new Map([
  ["google-photos-status", makeElement("google-photos-status")],
  ["google-photos-connect", makeElement("google-photos-connect", {
    tagName: "BUTTON",
    textContent: "Connect Google Photos",
  })],
  ["google-photos-choose", makeElement("google-photos-choose", {
    tagName: "BUTTON",
    disabled: true,
    textContent: "Choose from Google Photos",
  })],
  ["google-photos-open-signin", makeElement("google-photos-open-signin", {
    tagName: "A",
    textContent: "Open Google sign-in",
  })],
  ["google-photos-open-picker", makeElement("google-photos-open-picker", {
    tagName: "A",
    textContent: "Open Google Photos Picker",
  })],
]);

const storageWrites = [];
function makeStorage() {
  return {
    setItem(key, value) {
      storageWrites.push([String(key), String(value)]);
    },
    getItem() {
      return null;
    },
    removeItem() {},
  };
}

globalThis.document = {
  body: { dataset: {} },
  getElementById(id) {
    return elements.get(id) || null;
  },
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
  createElement(tagName) {
    return { tagName: String(tagName).toUpperCase(), dataset: {}, children: [], appendChild() {} };
  },
  addEventListener() {},
};

globalThis.window = {
  LEGALPDF_BROWSER_BOOTSTRAP: {
    defaultRuntimeMode: "shadow",
    defaultWorkspaceId: "google-photos-stage2",
    defaultUiVariant: "qt",
    shadowHost: "127.0.0.1",
    shadowPort: 8890,
    buildSha: "test",
    assetVersion: "test-assets",
    staticBasePath: "http://127.0.0.1:8890/static-build/test-assets/",
  },
  location: new URL("http://127.0.0.1:8890/?mode=shadow&workspace=google-photos-stage2#new-job"),
  history: { replaceState() {} },
  localStorage: makeStorage(),
  sessionStorage: makeStorage(),
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() {},
  setTimeout() { return 1; },
  clearTimeout() {},
  confirm() { return true; },
};
globalThis.localStorage = globalThis.window.localStorage;
globalThis.sessionStorage = globalThis.window.sessionStorage;
globalThis.CustomEvent = class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
};

const appModule = await import(__APP_MODULE_URL__);
const authUrl = "https://oauth.example.invalid/start";
appModule.setGooglePhotosAuthFallback(authUrl, { visible: true });
appModule.renderGooglePhotosStatus({
  configured: true,
  connected: false,
  client_id_configured: true,
  client_secret_env_configured: true,
});

const fallback = elements.get("google-photos-open-signin");
const disconnectedSnapshot = {
  fallbackHidden: fallback.classList.contains("hidden"),
  fallbackHref: fallback.href,
  fallbackText: fallback.textContent,
  statusText: elements.get("google-photos-status").textContent,
  chooseDisabled: elements.get("google-photos-choose").disabled,
  storageWrites: storageWrites.length,
};

appModule.renderGooglePhotosStatus({
  configured: true,
  connected: true,
  client_id_configured: true,
  client_secret_env_configured: true,
});
appModule.setGooglePhotosAuthFallback("https://oauth.example.invalid/stale", { visible: true });
appModule.setGooglePhotosPickerFallback("https://picker.example.invalid/stale-session", { visible: true });
appModule.resetGooglePhotosPickerState({ clearAuth: true, sessionDeleted: true });

console.log(JSON.stringify({
  disconnectedSnapshot,
  connectedSnapshot: {
    fallbackHidden: fallback.classList.contains("hidden"),
    fallbackHref: fallback.href,
    ariaHidden: fallback.attributes["aria-hidden"],
    tabIndex: fallback.tabIndex,
    chooseDisabled: elements.get("google-photos-choose").disabled,
    statusText: elements.get("google-photos-status").textContent,
  },
  resetSnapshot: {
    authFallbackHidden: elements.get("google-photos-open-signin").classList.contains("hidden"),
    authFallbackHref: elements.get("google-photos-open-signin").href,
    pickerFallbackHidden: elements.get("google-photos-open-picker").classList.contains("hidden"),
    pickerFallbackHref: elements.get("google-photos-open-picker").href,
    safeState: appModule.googlePhotosUiSafeSnapshot(),
  },
}));
"""
    results = run_browser_esm_json_probe(script, {"__APP_MODULE_URL__": "app.js"}, timeout_seconds=30)

    disconnected = results["disconnectedSnapshot"]
    assert disconnected["fallbackHidden"] is False
    assert disconnected["fallbackHref"] == "https://oauth.example.invalid/start"
    assert disconnected["fallbackText"] == "Open Google sign-in"
    assert disconnected["fallbackText"] != disconnected["fallbackHref"]
    assert "Google sign-in is ready" in disconnected["statusText"]
    assert disconnected["chooseDisabled"] is True
    assert disconnected["storageWrites"] == 0

    connected = results["connectedSnapshot"]
    assert connected["fallbackHidden"] is True
    assert connected["fallbackHref"] == ""
    assert connected["ariaHidden"] == "true"
    assert connected["tabIndex"] == -1
    assert connected["chooseDisabled"] is False
    assert "Google Photos connected" in connected["statusText"]

    reset = results["resetSnapshot"]
    assert reset["authFallbackHidden"] is True
    assert reset["authFallbackHref"] == ""
    assert reset["pickerFallbackHidden"] is True
    assert reset["pickerFallbackHref"] == ""
    assert reset["safeState"]["hasSessionId"] is False
    assert reset["safeState"]["hasAuthUrl"] is False
    assert reset["safeState"]["hasPickerUrl"] is False
    assert reset["safeState"]["selectedItemCount"] == 0
    assert reset["safeState"]["pickerDiagnostics"]["picker_session_deleted"] is True


def test_google_photos_picker_fallback_uses_autoclose_without_rendering_url_text() -> None:
    script = """
function makeClassList(initial = []) {
  const values = new Set(initial);
  return {
    add(value) {
      values.add(value);
    },
    remove(value) {
      values.delete(value);
    },
    contains(value) {
      return values.has(value);
    },
    toArray() {
      return Array.from(values).sort();
    },
  };
}

function makeElement(id, { tagName = "DIV", disabled = false, textContent = "" } = {}) {
  return {
    id,
    tagName,
    disabled,
    textContent,
    dataset: {},
    attributes: {},
    classList: makeClassList(id === "google-photos-open-picker" ? ["hidden"] : []),
    href: "",
    tabIndex: 0,
    setAttribute(name, value) {
      this.attributes[name] = String(value);
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "href") {
        this.href = "";
      }
    },
  };
}

const elements = new Map([
  ["google-photos-status", makeElement("google-photos-status")],
  ["google-photos-connect", makeElement("google-photos-connect", {
    tagName: "BUTTON",
    textContent: "Connect Google Photos",
  })],
  ["google-photos-choose", makeElement("google-photos-choose", {
    tagName: "BUTTON",
    textContent: "Choose from Google Photos",
  })],
  ["google-photos-open-picker", makeElement("google-photos-open-picker", {
    tagName: "A",
    textContent: "Open Google Photos Picker",
  })],
]);

const storageWrites = [];
function makeStorage() {
  return {
    setItem(key, value) {
      storageWrites.push([String(key), String(value)]);
    },
    getItem() {
      return null;
    },
    removeItem() {},
  };
}

globalThis.document = {
  body: { dataset: {} },
  getElementById(id) {
    return elements.get(id) || null;
  },
  querySelector() {
    return null;
  },
  querySelectorAll() {
    return [];
  },
  createElement(tagName) {
    return { tagName: String(tagName).toUpperCase(), dataset: {}, children: [], appendChild() {} };
  },
  addEventListener() {},
};

globalThis.window = {
  LEGALPDF_BROWSER_BOOTSTRAP: {
    defaultRuntimeMode: "shadow",
    defaultWorkspaceId: "google-photos-stage2",
    defaultUiVariant: "qt",
    shadowHost: "127.0.0.1",
    shadowPort: 8890,
    buildSha: "test",
    assetVersion: "test-assets",
    staticBasePath: "http://127.0.0.1:8890/static-build/test-assets/",
  },
  location: new URL("http://127.0.0.1:8890/?mode=shadow&workspace=google-photos-stage2#new-job"),
  history: { replaceState() {} },
  localStorage: makeStorage(),
  sessionStorage: makeStorage(),
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent() {},
  setTimeout() { return 1; },
  clearTimeout() {},
  confirm() { return true; },
};
globalThis.localStorage = globalThis.window.localStorage;
globalThis.sessionStorage = globalThis.window.sessionStorage;
globalThis.CustomEvent = class CustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
};

const appModule = await import(__APP_MODULE_URL__);
const pickerUri = "https://picker.example.invalid/session-123";
const pickerWithSlash = "https://picker.example.invalid/session-456/";
const pickerWithAutoclose = "https://picker.example.invalid/session-789/autoclose";
appModule.setGooglePhotosPickerFallback(pickerUri, { visible: true });
const fallback = elements.get("google-photos-open-picker");
const visibleSnapshot = {
  fallbackHidden: fallback.classList.contains("hidden"),
  fallbackHref: fallback.href,
  fallbackText: fallback.textContent,
  storageWrites: storageWrites.length,
  appendedOnce: appModule.googlePhotosPickerBrowserUrl(pickerWithSlash),
  alreadyAutoclose: appModule.googlePhotosPickerBrowserUrl(pickerWithAutoclose),
  noAutoclose: appModule.googlePhotosPickerBrowserUrl("https://picker.example.invalid/session-no-auto", { autoclose: false }),
};
appModule.setGooglePhotosPickerFallback("", { visible: false });
const hiddenSnapshot = {
  fallbackHidden: fallback.classList.contains("hidden"),
  fallbackHref: fallback.href,
  ariaHidden: fallback.attributes["aria-hidden"],
  tabIndex: fallback.tabIndex,
};
appModule.resetGooglePhotosPickerState({ clearAuth: false });
const afterResetHref = fallback.href;
appModule.setGooglePhotosPickerFallback("https://picker.example.invalid/session-new", { visible: true });
const freshSessionHref = fallback.href;
const reconnectDiagnostics = appModule.buildGooglePhotosPickerDiagnostics({
  google_ui_blocker_seen: true,
  google_ui_blocker_category: "reconnect_to_partner_app",
});
console.log(JSON.stringify({
  visibleSnapshot,
  hiddenSnapshot,
  afterResetHref,
  freshSessionHref,
  reconnectDiagnostics,
}));
"""
    results = run_browser_esm_json_probe(script, {"__APP_MODULE_URL__": "app.js"}, timeout_seconds=30)

    visible = results["visibleSnapshot"]
    assert visible["fallbackHidden"] is False
    assert visible["fallbackHref"] == "https://picker.example.invalid/session-123/autoclose"
    assert visible["fallbackText"] == "Open Google Photos Picker"
    assert visible["fallbackText"] != visible["fallbackHref"]
    assert visible["storageWrites"] == 0
    assert visible["appendedOnce"] == "https://picker.example.invalid/session-456/autoclose"
    assert visible["alreadyAutoclose"] == "https://picker.example.invalid/session-789/autoclose"
    assert visible["noAutoclose"] == "https://picker.example.invalid/session-no-auto"

    hidden = results["hiddenSnapshot"]
    assert hidden["fallbackHidden"] is True
    assert hidden["fallbackHref"] == ""
    assert hidden["ariaHidden"] == "true"
    assert hidden["tabIndex"] == -1
    assert results["afterResetHref"] == ""
    assert results["freshSessionHref"] == "https://picker.example.invalid/session-new/autoclose"
    assert results["reconnectDiagnostics"]["google_ui_blocker_seen"] is True
    assert results["reconnectDiagnostics"]["google_ui_blocker_category"] == "reconnect_to_partner_app"
    assert results["reconnectDiagnostics"]["safe_failure_category"] == "picker_reconnect_to_partner_app"


def test_google_photos_ui_module_centralizes_picker_fallback_contracts() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    google_photos_ui_js = static_dir / "google_photos_ui.js"

    assert google_photos_ui_js.exists()
    assert 'from "./google_photos_ui.js"' in app_js

    script = """
const ui = await import(__GOOGLE_PHOTOS_UI_MODULE_URL__);

const raw = "https://picker.example.invalid/session-1/";
const alreadyAutoclose = "https://picker.example.invalid/session-2/autoclose";
const direct = ui.googlePhotosPickerBrowserUrl(raw);
const diagnostics = ui.buildGooglePhotosPickerDiagnostics({
  google_ui_blocker_seen: true,
  google_ui_blocker_category: "reconnect_to_partner_app",
});
console.log(JSON.stringify({
  direct,
  alreadyAutoclose: ui.googlePhotosPickerBrowserUrl(alreadyAutoclose),
  noAutoclose: ui.googlePhotosPickerBrowserUrl("https://picker.example.invalid/session-3", { autoclose: false }),
  diagnostics,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__GOOGLE_PHOTOS_UI_MODULE_URL__": "google_photos_ui.js"},
        timeout_seconds=30,
    )

    assert results["direct"] == "https://picker.example.invalid/session-1/autoclose"
    assert results["alreadyAutoclose"] == "https://picker.example.invalid/session-2/autoclose"
    assert results["noAutoclose"] == "https://picker.example.invalid/session-3"
    assert results["diagnostics"]["google_ui_blocker_seen"] is True
    assert results["diagnostics"]["google_ui_blocker_category"] == "reconnect_to_partner_app"
    assert results["diagnostics"]["safe_failure_category"] == "picker_reconnect_to_partner_app"


def test_google_photos_ui_module_centralizes_safe_summary_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    google_photos_ui_js = (static_dir / "google_photos_ui.js").read_text(encoding="utf-8")

    assert 'from "./google_photos_ui.js"' in app_js
    assert "export function renderGooglePhotosSummaryInto" in google_photos_ui_js
    assert "renderGooglePhotosSummaryInto(qs(\"google-photos-summary\"), {" in app_js
    assert "renderGooglePhotosSummaryInto," in app_js
    assert 'appendResultGridItem(grid, "Photo Taken Date"' not in app_js
    assert 'appendResultGridItem(grid, "Google Photos Location"' not in app_js

    script = r"""
const googlePhotosUi = await import(__GOOGLE_PHOTOS_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    children: [],
    parentNode: null,
    title: "",
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      contains(name) {
        return classNames.has(String(name));
      },
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function collectClasses(node) {
  const classes = [];
  walk(node, (current) => {
    if (String(current.className || "").trim()) {
      classes.push(current.className);
    }
  });
  return classes;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const container = document.createElement("div");
container.className = "result-card empty-state";
googlePhotosUi.renderGooglePhotosSummaryInto(container, {
  selectedPhoto: {
    source_filename: `Photo ${malicious}.jpg`,
    photo_taken_at: `2026-04-29 ${malicious}`,
    create_time: "fallback-not-used",
    camera: {
      make: `Canon ${malicious}`,
      model: `R5 ${malicious}`,
    },
    dimensions: {
      width: `800${malicious}`,
      height: "600",
    },
    location_message: `Selected location ${malicious}`,
  },
  diagnostics: {
    photo_taken_date_policy: `Policy ${malicious}`,
    downloaded_exif_date: `Exif ${malicious}`,
    location_message: `Diagnostics location ${malicious}`,
    service_city_source_label: `Service city ${malicious}`,
  },
  message: `Message ${malicious}`,
});

const selectedGrid = container.children[1];
const pendingContainer = document.createElement("div");
pendingContainer.className = "result-card empty-state";
googlePhotosUi.renderGooglePhotosSummaryInto(pendingContainer, {
  diagnostics: {},
});

const emptyContainer = document.createElement("div");
googlePhotosUi.renderGooglePhotosSummaryInto(emptyContainer, {});
const nullResult = googlePhotosUi.renderGooglePhotosSummaryInto(null, {
  selectedPhoto: { source_filename: "ignored.jpg" },
});

console.log(JSON.stringify({
  exportedType: typeof googlePhotosUi.renderGooglePhotosSummaryInto,
  selected: {
    className: container.className,
    text: container.textContent,
    childClasses: container.children.map((child) => child.className || ""),
    gridLabels: selectedGrid.children.map((child) => child.children[0]?.textContent || ""),
    gridValues: selectedGrid.children.map((child) => child.children[1]?.textContent || ""),
    classes: collectClasses(container),
    imgCount: countTag(container, "img"),
    scriptCount: countTag(container, "script"),
    innerHTMLWrites: countInnerHtmlWrites(container),
  },
  pending: {
    className: pendingContainer.className,
    text: pendingContainer.textContent,
    classes: collectClasses(pendingContainer),
    imgCount: countTag(pendingContainer, "img"),
    scriptCount: countTag(pendingContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(pendingContainer),
  },
  empty: {
    className: emptyContainer.className,
    text: emptyContainer.textContent,
    childCount: emptyContainer.children.length,
  },
  nullResultType: nullResult === undefined ? "undefined" : typeof nullResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__GOOGLE_PHOTOS_UI_MODULE_URL__": "google_photos_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["selected"]["className"] == "result-card"
    assert results["selected"]["childClasses"] == ["result-header", "result-grid"]
    assert results["selected"]["gridLabels"] == [
        "Photo Taken Date",
        "Photo Date Policy",
        "Filename",
        "Camera",
        "Dimensions",
        "Downloaded EXIF Date",
        "Google Photos Location",
        "Service City Source",
    ]
    assert "Photo <img src=x onerror=alert(1)><script>bad()</script>.jpg" in results["selected"]["text"]
    assert "Message <img src=x onerror=alert(1)><script>bad()</script>" in results["selected"]["text"]
    assert "Policy <img src=x onerror=alert(1)><script>bad()</script>" in results["selected"]["gridValues"]
    assert "Diagnostics location <img src=x onerror=alert(1)><script>bad()</script>" in results["selected"]["gridValues"]
    assert "Selected location <img src=x onerror=alert(1)><script>bad()</script>" not in results["selected"]["gridValues"]
    assert "status-chip ok" in results["selected"]["classes"]
    assert results["selected"]["classes"].count("word-break") == 8
    assert results["selected"]["imgCount"] == 0
    assert results["selected"]["scriptCount"] == 0
    assert results["selected"]["innerHTMLWrites"] == 0

    assert results["pending"]["className"] == "result-card"
    assert "Google Photos selection" in results["pending"]["text"]
    assert "Pending" in results["pending"]["text"]
    assert "Photo taken date: provenance only" in results["pending"]["text"]
    assert "Google Photos location: unavailable from Picker API" in results["pending"]["text"]
    assert "Service city source: not available" in results["pending"]["text"]
    assert "status-chip info" in results["pending"]["classes"]
    assert results["pending"]["imgCount"] == 0
    assert results["pending"]["scriptCount"] == 0
    assert results["pending"]["innerHTMLWrites"] == 0

    assert results["empty"]["className"] == "empty-state"
    assert results["empty"]["text"] == "No Google Photos selection yet."
    assert results["empty"]["childCount"] == 0
    assert results["nullResultType"] == "undefined"


def test_google_photos_click_handlers_guard_primary_actions_only() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    google_photos_ui_js = (static_dir / "google_photos_ui.js").read_text(encoding="utf-8")

    assert "export async function runWithBusy(buttonIds, busyLabels, action, options = {})" in app_js
    assert "const guardIds = options.guardIds || buttonIds;" in app_js
    assert 'from "./google_photos_ui.js"' in app_js
    assert "export function setGooglePhotosAuthFallback" in google_photos_ui_js
    assert "export function setGooglePhotosPickerFallback" in google_photos_ui_js
    assert "export function googlePhotosPickerBrowserUrl" in google_photos_ui_js
    assert "export function resetGooglePhotosPickerState" in google_photos_ui_js
    assert "export function googlePhotosUiSafeSnapshot" in google_photos_ui_js
    assert 'fetchJson("/api/interpretation/google-photos/disconnect"' in app_js
    assert "GOOGLE_PHOTOS_RECONNECT_GUIDANCE" in app_js
    assert 'handleUpload("photo-upload-form", "/api/interpretation/autofill-photo", { sourceKind: "photo" })' in app_js
    assert 'applyInterpretationSeed(importPayload.normalized_payload, { sourceKind: "google_photos" })' in app_js
    assert "localStorage.setItem" not in app_js
    assert "sessionStorage.setItem" not in app_js
    assert "localStorage.setItem" not in google_photos_ui_js
    assert "sessionStorage.setItem" not in google_photos_ui_js
    assert 'window.open(authUrl, "_blank", "noopener,noreferrer")' in app_js
    assert "/autoclose" in google_photos_ui_js
    assert '}, { guardIds: ["google-photos-connect"] });' in app_js
    assert '}, { guardIds: ["google-photos-choose"] });' in app_js


def test_new_profile_click_handler_does_not_guard_on_disabled_profile_action_buttons() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")

    start = app_js.index('qs("new-profile").addEventListener("click"')
    end = app_js.index('qs("profile-save").addEventListener("click"', start)
    click_handler = app_js[start:end]

    assert "handleNewProfile()" in click_handler
    assert "guardIds:" in click_handler

    guard_start = click_handler.index("guardIds:")
    guard_end = click_handler.index("});", guard_start)
    guard_block = click_handler[guard_start:guard_end]

    assert '"import-live-profiles"' in guard_block
    assert '"new-profile"' in guard_block
    assert '"profile-save"' in guard_block
    assert '"profile-set-primary"' not in guard_block
    assert '"profile-delete"' not in guard_block


def test_extension_lab_presentation_module_centralizes_card_copy() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    extension_lab_module = static_dir / "extension_lab_presentation.js"

    assert extension_lab_module.exists()
    assert 'from "./extension_lab_presentation.js"' in app_js

    script = """
const lab = await import(__EXTENSION_LAB_PRESENTATION_MODULE_URL__);

const payload = {
  ready: lab.extensionReadinessCardText({ ok: true }, { status: "bad", message: "Stable ID: should stay hidden" }),
  infoMode: lab.extensionReadinessCardText({ ok: false }, { status: "info", message: "UI owner: should stay hidden" }),
  needsAttention: lab.extensionReadinessCardText({ ok: false }, { status: "warn", message: "Launch target: should stay hidden" }),
  installed: lab.extensionInstallCardText({ active_extension_ids: ["abc"], stale_extension_ids: [] }),
  stale: lab.extensionInstallCardText({ active_extension_ids: [], stale_extension_ids: ["old"] }),
  missing: lab.extensionInstallCardText({ active_extension_ids: [], stale_extension_ids: [] }),
  liveMode: lab.extensionModeCardText({ live_data: true }, { status: "warn", message: "Stable ID: should stay hidden" }),
  isolatedInfo: lab.extensionModeCardText({ live_data: false }, { status: "info", message: "UI owner: should stay hidden" }),
  isolatedWarn: lab.extensionModeCardText({ live_data: false }, { status: "warn", message: "Launch target: should stay hidden" }),
  cards: lab.buildExtensionLabCards({
    prepare: { ok: false },
    extensionReport: { active_extension_ids: ["abc"], stale_extension_ids: ["old"] },
    bridgeSummary: { status: "info", label: "Test mode" },
    runtime: { live_data: false },
  }),
};
console.log(JSON.stringify(payload));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__EXTENSION_LAB_PRESENTATION_MODULE_URL__": "extension_lab_presentation.js"},
        timeout_seconds=30,
    )

    assert results["ready"] == "Ready for Gmail intake in this mode."
    assert (
        results["infoMode"]
        == "This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting."
    )
    assert (
        results["needsAttention"]
        == "Needs attention before Gmail intake can start here. Open technical details below when troubleshooting."
    )
    assert results["installed"] == "Browser helper details were found. Open technical details below for installation IDs."
    assert results["stale"] == "Older browser helper details were found. Open technical details below when troubleshooting."
    assert results["missing"] == "No browser helper installation details were reported."
    assert results["liveMode"] == (
        "Using live app settings and saved work.\n"
        "Use this page when Gmail intake needs a deeper technical check."
    )
    assert results["isolatedInfo"] == (
        "Using isolated test settings and saved work.\n"
        "This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting."
    )
    assert results["isolatedWarn"] == (
        "Using isolated test settings and saved work.\n"
        "Live Gmail readiness can differ from this isolated test mode."
    )
    assert results["cards"] == [
        {
            "title": "Gmail helper readiness",
            "text": "This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting.",
            "status": "info",
            "label": "Test mode",
        },
        {
            "title": "Installed browser helper",
            "text": "Browser helper details were found. Open technical details below for installation IDs.",
            "status": "ok",
            "label": "Detected",
        },
        {
            "title": "Current mode",
            "text": (
                "Using isolated test settings and saved work.\n"
                "This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting."
            ),
            "status": "info",
            "label": "Test mode",
        },
    ]


def test_extension_lab_ui_module_centralizes_safe_prepare_reason_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    extension_lab_ui_module = static_dir / "extension_lab_ui.js"

    assert extension_lab_ui_module.exists()
    assert 'from "./extension_lab_ui.js"' in app_js
    assert "export function renderExtensionPrepareReasonCatalogInto" not in app_js
    assert "renderExtensionPrepareReasonCatalogInto(reasonCatalog, data.prepare_reason_catalog || [])" in app_js

    script = r"""
const labUi = await import(__EXTENSION_LAB_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = node.tagName === target ? 1 : 0;
  for (const child of node.children || []) {
    total += countTag(child, target);
  }
  return total;
}

function countInnerHtmlWrites(node) {
  let total = (node.innerHTMLAssignments || []).length;
  for (const child of node.children || []) {
    total += countInnerHtmlWrites(child);
  }
  return total;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const container = document.createElement("div");
labUi.renderExtensionPrepareReasonCatalogInto(container, [
  { reason: malicious, message: `Message ${malicious}` },
  { reason: "", message: "" },
]);
const emptyContainer = document.createElement("div");
labUi.renderExtensionPrepareReasonCatalogInto(emptyContainer, []);
const nullResult = labUi.renderExtensionPrepareReasonCatalogInto(null, [{ reason: "ignored", message: "Ignored" }]);

console.log(JSON.stringify({
  exportedType: typeof labUi.renderExtensionPrepareReasonCatalogInto,
  text: container.textContent,
  articleCount: countTag(container, "article"),
  imgCount: countTag(container, "img"),
  scriptCount: countTag(container, "script"),
  innerHTMLWrites: countInnerHtmlWrites(container),
  fallbackText: container.children[1]?.textContent || "",
  emptyText: emptyContainer.textContent,
  emptyClass: emptyContainer.children[0]?.className || "",
  nullResultType: nullResult === undefined ? "undefined" : typeof nullResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__EXTENSION_LAB_UI_MODULE_URL__": "extension_lab_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert "Message <img src=x onerror=alert(1)><script>bad()</script>" in results["text"]
    assert "Code: <img src=x onerror=alert(1)><script>bad()</script>" in results["text"]
    assert results["articleCount"] == 2
    assert results["imgCount"] == 0
    assert results["scriptCount"] == 0
    assert results["innerHTMLWrites"] == 0
    assert results["fallbackText"] == "No message available.Code: Unknown reason"
    assert results["emptyText"] == "No prepare reasons are available."
    assert results["emptyClass"] == "empty-state"
    assert results["nullResultType"] == "undefined"


def test_recovery_result_ui_module_centralizes_safe_card_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    recovery_ui_module = static_dir / "recovery_result_ui.js"

    assert recovery_ui_module.exists()
    assert 'from "./recovery_result_ui.js"' in app_js
    assert "function renderRecoveryResult(" not in app_js
    assert '"Recommended URL"' not in app_js
    assert "renderRecoveryResultInto(qs(containerId), details)" in app_js
    assert '"parity-audit-result"' in app_js
    assert '"translation-result"' in app_js
    assert '"gmail-message-result"' in app_js
    assert '"gmail-session-result"' in app_js

    script = r"""
const recoveryUi = await import(__RECOVERY_UI_MODULE_URL__);

function createClassList(element) {
  return {
    add(...names) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      names.forEach((name) => classes.add(name));
      element.className = Array.from(classes).join(" ");
    },
    remove(...names) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      names.forEach((name) => classes.delete(name));
      element.className = Array.from(classes).join(" ");
    },
    contains(name) {
      return String(element.className || "").split(/\s+/).filter(Boolean).includes(name);
    },
  };
}

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  element.classList = createClassList(element);
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function collectClasses(node) {
  const classes = [];
  walk(node, (current) => {
    if (String(current.className || "").trim()) {
      classes.push(current.className);
    }
  });
  return classes;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const container = document.createElement("div");
container.className = "result-card empty-state";
recoveryUi.renderRecoveryResultInto(container, {
  title: `Server unavailable ${malicious}`,
  host: `127.0.0.1${malicious}`,
  port: `8877${malicious}`,
  recommendedUrl: `http://127.0.0.1:8877/${malicious}`,
  launcherCommand: `python tooling/launch_browser_app.py ${malicious}`,
  recoverySteps: [`Restart ${malicious}`, "Open the current browser workspace again"],
});
const nullResult = recoveryUi.renderRecoveryResultInto(null, {
  title: "Ignored",
  host: "127.0.0.1",
  port: "8877",
  recommendedUrl: "http://127.0.0.1:8877/",
  launcherCommand: "python launch.py",
  recoverySteps: ["ignored"],
});

console.log(JSON.stringify({
  exportedType: typeof recoveryUi.renderRecoveryResultInto,
  text: container.textContent,
  className: container.className,
  directChildClasses: container.children.map((child) => child.className || ""),
  classes: collectClasses(container),
  childTags: container.children.map((child) => child.tagName),
  gridText: container.children[1]?.textContent || "",
  recoveryText: container.children[2]?.textContent || "",
  listItemCount: countTag(container, "li"),
  imgCount: countTag(container, "img"),
  scriptCount: countTag(container, "script"),
  innerHTMLWrites: countInnerHtmlWrites(container),
  nullResultType: nullResult === undefined ? "undefined" : typeof nullResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__RECOVERY_UI_MODULE_URL__": "recovery_result_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["className"] == "result-card"
    assert results["childTags"] == ["DIV", "DIV", "DIV"]
    assert results["directChildClasses"] == ["result-header", "result-grid", ""]
    assert "status-chip bad" in results["classes"]
    assert "word-break" in results["classes"]
    assert "Server unavailable <img src=x onerror=alert(1)><script>bad()</script>" in results["text"]
    assert "Unavailable" in results["text"]
    assert "Listener" in results["gridText"]
    assert "127.0.0.1<img src=x onerror=alert(1)><script>bad()</script>:8877<img src=x onerror=alert(1)><script>bad()</script>" in results["gridText"]
    assert "Recommended URL" in results["gridText"]
    assert "http://127.0.0.1:8877/<img src=x onerror=alert(1)><script>bad()</script>" in results["gridText"]
    assert "Launcher" in results["gridText"]
    assert "python tooling/launch_browser_app.py <img src=x onerror=alert(1)><script>bad()</script>" in results["gridText"]
    assert "Recovery" in results["recoveryText"]
    assert "Restart <img src=x onerror=alert(1)><script>bad()</script>" in results["recoveryText"]
    assert "Open the current browser workspace again" in results["recoveryText"]
    assert results["listItemCount"] == 2
    assert results["imgCount"] == 0
    assert results["scriptCount"] == 0
    assert results["innerHTMLWrites"] == 0
    assert results["nullResultType"] == "undefined"


def test_profile_ui_module_centralizes_safe_distance_row_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    profile_ui_module = static_dir / "profile_ui.js"

    assert profile_ui_module.exists()
    profile_ui_js = profile_ui_module.read_text(encoding="utf-8")
    assert 'from "./profile_ui.js"' in app_js
    assert "export function renderProfileDistanceRowsInto" not in app_js
    assert "export function renderProfileOptionsInto" not in app_js
    assert "export function renderProfileOptionsInto" in profile_ui_js
    assert "renderProfileDistanceRowsInto(container, profileUiState.distanceRows, {" in app_js
    assert 'renderProfileOptionsInto(qs("profile-id"), profiles, primaryProfileId);' in app_js

    script = r"""
const profileUi = await import(__PROFILE_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const listeners = new Map();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    attributes: {},
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    setAttribute(name, value) {
      this.attributes[name] = String(value ?? "");
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
    addEventListener(type, handler) {
      if (!listeners.has(type)) {
        listeners.set(type, []);
      }
      listeners.get(type).push(handler);
    },
    click() {
      for (const handler of listeners.get("click") || []) {
        handler({ target: this, currentTarget: this, preventDefault() {} });
      }
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    if (!node) {
      return;
    }
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function firstButton(node) {
  let button = null;
  walk(node, (current) => {
    if (!button && current.tagName === "BUTTON") {
      button = current;
    }
  });
  return button;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const container = document.createElement("div");
let removedCity = "";
profileUi.renderProfileDistanceRowsInto(container, [
  { city: malicious, distanceLabel: "12 km one way" },
], {
  onRemove(row) {
    removedCity = row.city;
  },
});
const button = firstButton(container);
button.click();

const emptyContainer = document.createElement("div");
profileUi.renderProfileDistanceRowsInto(emptyContainer, []);
const nullResult = profileUi.renderProfileDistanceRowsInto(null, [{ city: "ignored", distanceLabel: "1 km" }]);

const profileSelect = document.createElement("select");
profileUi.renderProfileOptionsInto(profileSelect, [
  { id: "safe-profile", document_name: "Safe Profile" },
  { id: malicious, document_name: `Unsafe ${malicious}` },
  { id: "fallback-profile", document_name: "" },
], malicious);

const emptySelect = document.createElement("select");
profileUi.renderProfileOptionsInto(emptySelect, [], "");

const nullSelectResult = profileUi.renderProfileOptionsInto(null, [{ id: "ignored", document_name: "Ignored" }], "ignored");

console.log(JSON.stringify({
  exportedType: typeof profileUi.renderProfileDistanceRowsInto,
  profileOptionsExportedType: typeof profileUi.renderProfileOptionsInto,
  text: container.textContent,
  articleCount: countTag(container, "article"),
  imgCount: countTag(container, "img"),
  scriptCount: countTag(container, "script"),
  innerHTMLWrites: countInnerHtmlWrites(container),
  buttonText: button.textContent,
  buttonClass: button.className,
  buttonType: button.type,
  ariaLabel: button.attributes["aria-label"],
  removedCity,
  emptyText: emptyContainer.textContent,
  emptyClass: emptyContainer.children[0]?.className || "",
  nullResultType: nullResult === undefined ? "undefined" : typeof nullResult,
  profileSelectDisabled: profileSelect.disabled,
  profileOptions: profileSelect.children.map((option) => ({
    tagName: option.tagName,
    value: option.value,
    text: option.textContent,
    selected: Boolean(option.selected),
  })),
  profileSelectText: profileSelect.textContent,
  profileSelectImgCount: countTag(profileSelect, "img"),
  profileSelectScriptCount: countTag(profileSelect, "script"),
  profileSelectInnerHTMLWrites: countInnerHtmlWrites(profileSelect),
  emptySelectDisabled: emptySelect.disabled,
  emptyOptions: emptySelect.children.map((option) => ({
    tagName: option.tagName,
    value: option.value,
    text: option.textContent,
    selected: Boolean(option.selected),
  })),
  nullSelectResultType: nullSelectResult === undefined ? "undefined" : typeof nullSelectResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__PROFILE_UI_MODULE_URL__": "profile_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["profileOptionsExportedType"] == "function"
    assert "<img src=x onerror=alert(1)><script>bad()</script>" in results["text"]
    assert "12 km one way" in results["text"]
    assert results["articleCount"] == 1
    assert results["imgCount"] == 0
    assert results["scriptCount"] == 0
    assert results["innerHTMLWrites"] == 0
    assert results["buttonText"] == "Delete destination"
    assert results["buttonClass"] == "ghost-button"
    assert results["buttonType"] == "button"
    assert results["ariaLabel"] == "Delete destination <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["removedCity"] == "<img src=x onerror=alert(1)><script>bad()</script>"
    assert results["emptyText"] == "No city distances saved yet. Add the cities you use most often."
    assert results["emptyClass"] == "result-card empty-state"
    assert results["nullResultType"] == "undefined"
    assert results["profileSelectDisabled"] is False
    assert results["profileOptions"] == [
        {
            "tagName": "OPTION",
            "value": "safe-profile",
            "text": "Safe Profile",
            "selected": False,
        },
        {
            "tagName": "OPTION",
            "value": "<img src=x onerror=alert(1)><script>bad()</script>",
            "text": "Unsafe <img src=x onerror=alert(1)><script>bad()</script>",
            "selected": True,
        },
        {
            "tagName": "OPTION",
            "value": "fallback-profile",
            "text": "fallback-profile",
            "selected": False,
        },
    ]
    assert "Unsafe <img src=x onerror=alert(1)><script>bad()</script>" in results["profileSelectText"]
    assert results["profileSelectImgCount"] == 0
    assert results["profileSelectScriptCount"] == 0
    assert results["profileSelectInnerHTMLWrites"] == 0
    assert results["emptySelectDisabled"] is True
    assert results["emptyOptions"] == [
        {
            "tagName": "OPTION",
            "value": "",
            "text": "No profiles available",
            "selected": True,
        },
    ]
    assert results["nullSelectResultType"] == "undefined"


def test_profile_ui_module_centralizes_safe_profile_card_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    profile_ui_module = static_dir / "profile_ui.js"

    assert profile_ui_module.exists()
    profile_ui_js = profile_ui_module.read_text(encoding="utf-8")
    assert "export function renderPrimaryProfileCardInto" in profile_ui_js
    assert "export function renderProfileListInto" in profile_ui_js
    assert "export function syncProfileEditorDrawerStateInto" in profile_ui_js
    assert "syncProfileEditorDrawerStateInto(backdrop, document.body, profileUiState.editorDrawerOpen);" in app_js
    assert "renderPrimaryProfileCardInto(primaryCard, primary);" in app_js
    assert "renderProfileListInto(container, summary.profiles || [], {" in app_js
    assert "primaryCard.innerHTML" not in app_js
    assert "article.innerHTML" not in app_js
    assert "profile-card-helper" not in app_js
    profile_drawer_start = app_js.index("function setProfileEditorDrawerOpen")
    open_profile_drawer_start = app_js.index("function openProfileEditorDrawer", profile_drawer_start)
    profile_drawer_block = app_js[profile_drawer_start:open_profile_drawer_start]
    assert "profileUiState.editorDrawerOpen = Boolean(open)" in profile_drawer_block
    assert "innerHTML" not in profile_drawer_block
    assert "backdrop.classList.toggle" not in profile_drawer_block
    assert "backdrop.setAttribute(\"aria-hidden\"" not in profile_drawer_block
    assert "document.body.dataset.profileEditorDrawer" not in profile_drawer_block

    script = r"""
const profileUi = await import(__PROFILE_UI_MODULE_URL__);

function createClassList(element) {
  return {
    add(...names) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      names.forEach((name) => classes.add(name));
      element.className = Array.from(classes).join(" ");
    },
    remove(...names) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      names.forEach((name) => classes.delete(name));
      element.className = Array.from(classes).join(" ");
    },
    toggle(name, force) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      const shouldAdd = force === undefined ? !classes.has(name) : Boolean(force);
      if (shouldAdd) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
      element.className = Array.from(classes).join(" ");
      return shouldAdd;
    },
    contains(name) {
      return String(element.className || "").split(/\s+/).filter(Boolean).includes(name);
    },
  };
}

function makeElement(tagName = "div") {
  const listeners = new Map();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    dataset: {},
    attributes: {},
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    disabled: false,
    setAttribute(name, value) {
      this.attributes[name] = String(value ?? "");
    },
    getAttribute(name) {
      return this.attributes[name] ?? null;
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
    addEventListener(type, handler) {
      if (!listeners.has(type)) {
        listeners.set(type, []);
      }
      listeners.get(type).push(handler);
    },
    click() {
      for (const handler of listeners.get("click") || []) {
        handler({ target: this, currentTarget: this, preventDefault() {} });
      }
    },
  };
  element.classList = createClassList(element);
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function buttonSummaries(node) {
  const buttons = [];
  walk(node, (current) => {
    if (current.tagName === "BUTTON") {
      buttons.push({
        text: current.textContent,
        type: current.type,
        disabled: Boolean(current.disabled),
      });
    }
  });
  return buttons;
}

function classNames(node) {
  const classes = [];
  walk(node, (current) => {
    if (current.className) {
      classes.push(current.className);
    }
  });
  return classes;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const primaryProfile = {
  id: `primary-${malicious}`,
  document_name: `Main ${malicious}`,
  email: `main@example.com${malicious}`,
  phone_number: "555-0101",
  travel_origin_label: `Lisbon ${malicious}`,
  travel_distances_by_city: { Porto: 313, Faro: 278 },
  is_primary: true,
};
const secondaryProfile = {
  id: "secondary",
  document_name: `Second ${malicious}`,
  email: "",
  phone_number: "",
  travel_origin_label: "",
  travel_distances_by_city: { Porto: 313 },
  is_primary: false,
};

const primaryCard = document.createElement("article");
profileUi.renderPrimaryProfileCardInto(primaryCard, primaryProfile);

const emptyPrimaryCard = document.createElement("article");
profileUi.renderPrimaryProfileCardInto(emptyPrimaryCard, null);

const list = document.createElement("div");
const calls = [];
profileUi.renderProfileListInto(list, [primaryProfile, secondaryProfile], {
  count: 2,
  onEdit(profile) {
    calls.push(`edit:${profile.id}`);
  },
  onSetPrimary(profile) {
    calls.push(`primary:${profile.id}`);
  },
  onDelete(profile) {
    calls.push(`delete:${profile.id}`);
  },
});
const buttons = buttonSummaries(list);
walk(list, (node) => {
  if (node.tagName === "BUTTON" && !node.disabled) {
    node.click();
  }
});

const singleList = document.createElement("div");
profileUi.renderProfileListInto(singleList, [primaryProfile], { count: 1 });

const emptyList = document.createElement("div");
profileUi.renderProfileListInto(emptyList, [], { count: 0 });

const openBackdrop = document.createElement("div");
openBackdrop.classList.add("hidden");
const openBody = document.createElement("body");
profileUi.syncProfileEditorDrawerStateInto(openBackdrop, openBody, true);

const closedBackdrop = document.createElement("div");
const closedBody = document.createElement("body");
closedBody.dataset.profileEditorDrawer = "open";
profileUi.syncProfileEditorDrawerStateInto(closedBackdrop, closedBody, false);

const truthyBackdrop = document.createElement("div");
const truthyBody = document.createElement("body");
profileUi.syncProfileEditorDrawerStateInto(truthyBackdrop, truthyBody, "yes");

const missingBodyBackdrop = document.createElement("div");
profileUi.syncProfileEditorDrawerStateInto(missingBodyBackdrop, null, false);

const nullBackdropBody = document.createElement("body");
nullBackdropBody.dataset.profileEditorDrawer = "unchanged";
const nullBackdropResult = profileUi.syncProfileEditorDrawerStateInto(null, nullBackdropBody, true);

const nullPrimaryResult = profileUi.renderPrimaryProfileCardInto(null, primaryProfile);
const nullListResult = profileUi.renderProfileListInto(null, [primaryProfile], { count: 1 });

console.log(JSON.stringify({
  primaryExportedType: typeof profileUi.renderPrimaryProfileCardInto,
  listExportedType: typeof profileUi.renderProfileListInto,
  drawerStateExportedType: typeof profileUi.syncProfileEditorDrawerStateInto,
  primaryText: primaryCard.textContent,
  primaryClass: primaryCard.className,
  emptyPrimaryText: emptyPrimaryCard.textContent,
  emptyPrimaryClass: emptyPrimaryCard.className,
  listText: list.textContent,
  listClasses: classNames(list),
  articleCount: countTag(list, "article"),
  buttonSummaries: buttons,
  singleButtonSummaries: buttonSummaries(singleList),
  calls,
  emptyListText: emptyList.textContent,
  emptyListClass: emptyList.children[0]?.className || "",
  imgCount: countTag(primaryCard, "img") + countTag(list, "img"),
  scriptCount: countTag(primaryCard, "script") + countTag(list, "script"),
  innerHTMLWrites: countInnerHtmlWrites(primaryCard) + countInnerHtmlWrites(list),
  drawerOpen: {
    className: openBackdrop.className,
    ariaHidden: openBackdrop.getAttribute("aria-hidden"),
    bodyState: openBody.dataset.profileEditorDrawer || "",
    innerHTMLWrites: countInnerHtmlWrites(openBackdrop) + countInnerHtmlWrites(openBody),
  },
  drawerClosed: {
    className: closedBackdrop.className,
    ariaHidden: closedBackdrop.getAttribute("aria-hidden"),
    bodyState: closedBody.dataset.profileEditorDrawer || "",
    innerHTMLWrites: countInnerHtmlWrites(closedBackdrop) + countInnerHtmlWrites(closedBody),
  },
  drawerTruthy: {
    className: truthyBackdrop.className,
    ariaHidden: truthyBackdrop.getAttribute("aria-hidden"),
    bodyState: truthyBody.dataset.profileEditorDrawer || "",
    innerHTMLWrites: countInnerHtmlWrites(truthyBackdrop) + countInnerHtmlWrites(truthyBody),
  },
  drawerMissingBody: {
    className: missingBodyBackdrop.className,
    ariaHidden: missingBodyBackdrop.getAttribute("aria-hidden"),
    innerHTMLWrites: countInnerHtmlWrites(missingBodyBackdrop),
  },
  nullBackdropBodyState: nullBackdropBody.dataset.profileEditorDrawer,
  nullBackdropInnerHTMLWrites: countInnerHtmlWrites(nullBackdropBody),
  nullPrimaryResultType: nullPrimaryResult === undefined ? "undefined" : typeof nullPrimaryResult,
  nullListResultType: nullListResult === undefined ? "undefined" : typeof nullListResult,
  nullBackdropResultType: nullBackdropResult === undefined ? "undefined" : typeof nullBackdropResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__PROFILE_UI_MODULE_URL__": "profile_ui.js"},
        timeout_seconds=30,
    )

    assert results["primaryExportedType"] == "function"
    assert results["listExportedType"] == "function"
    assert results["drawerStateExportedType"] == "function"
    assert "Main <img src=x onerror=alert(1)><script>bad()</script>" in results["primaryText"]
    assert "main@example.com<img src=x onerror=alert(1)><script>bad()</script> | 555-0101" in results["primaryText"]
    assert "Travel origin: Lisbon <img src=x onerror=alert(1)><script>bad()</script>" in results["primaryText"]
    assert "2 saved city distances." in results["primaryText"]
    assert "Main profile" in results["primaryText"]
    assert results["primaryClass"] == ""
    assert results["emptyPrimaryText"] == "No main profile is set yet. Add a profile or choose one from the list."
    assert results["emptyPrimaryClass"] == "empty-state"
    assert "Profile record" in results["listText"]
    assert "Second <img src=x onerror=alert(1)><script>bad()</script>" in results["listText"]
    assert "Add email or phone details to use them in Gmail replies." in results["listText"]
    assert "Edit this profile's contact, payment, and travel details." in results["listText"]
    assert "1 saved city distance" in results["listText"]
    assert results["articleCount"] == 2
    assert "profile-card" in results["listClasses"]
    assert "history-actions" in results["listClasses"]
    assert results["buttonSummaries"] == [
        {"text": "Edit", "type": "button", "disabled": False},
        {"text": "Main profile", "type": "button", "disabled": True},
        {"text": "Delete profile", "type": "button", "disabled": False},
        {"text": "Edit", "type": "button", "disabled": False},
        {"text": "Use as main profile", "type": "button", "disabled": False},
        {"text": "Delete profile", "type": "button", "disabled": False},
    ]
    assert results["singleButtonSummaries"][2] == {
        "text": "Delete profile",
        "type": "button",
        "disabled": True,
    }
    assert results["calls"] == [
        "edit:primary-<img src=x onerror=alert(1)><script>bad()</script>",
        "delete:primary-<img src=x onerror=alert(1)><script>bad()</script>",
        "edit:secondary",
        "primary:secondary",
        "delete:secondary",
    ]
    assert results["emptyListText"] == "No profiles yet. Add a profile to get started."
    assert results["emptyListClass"] == "result-card empty-state"
    assert results["imgCount"] == 0
    assert results["scriptCount"] == 0
    assert results["innerHTMLWrites"] == 0
    assert results["drawerOpen"] == {
        "className": "",
        "ariaHidden": "false",
        "bodyState": "open",
        "innerHTMLWrites": 0,
    }
    assert results["drawerClosed"] == {
        "className": "hidden",
        "ariaHidden": "true",
        "bodyState": "closed",
        "innerHTMLWrites": 0,
    }
    assert results["drawerTruthy"] == {
        "className": "",
        "ariaHidden": "false",
        "bodyState": "open",
        "innerHTMLWrites": 0,
    }
    assert results["drawerMissingBody"] == {
        "className": "hidden",
        "ariaHidden": "true",
        "innerHTMLWrites": 0,
    }
    assert results["nullBackdropBodyState"] == "unchanged"
    assert results["nullBackdropInnerHTMLWrites"] == 0
    assert results["nullPrimaryResultType"] == "undefined"
    assert results["nullListResultType"] == "undefined"
    assert results["nullBackdropResultType"] == "undefined"


def test_profile_ui_module_centralizes_safe_profile_editor_chrome_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    profile_ui_module = static_dir / "profile_ui.js"

    assert profile_ui_module.exists()
    profile_ui_js = profile_ui_module.read_text(encoding="utf-8")
    assert "export function renderProfileDistanceStatusInto" in profile_ui_js
    assert "export function renderProfileDistanceJsonInto" in profile_ui_js
    assert "export function renderProfileEditorChromeInto" in profile_ui_js
    assert "renderProfileDistanceStatusInto" in app_js
    assert "renderProfileDistanceJsonInto" in app_js
    assert "renderProfileEditorChromeInto" in app_js

    distance_status_start = app_js.index("function setProfileDistanceStatus")
    distance_json_start = app_js.index("function syncProfileDistanceJsonField", distance_status_start)
    distance_status_block = app_js[distance_status_start:distance_json_start]
    assert 'renderProfileDistanceStatusInto(qs("profile-distance-status"), { tone, message });' in distance_status_block
    assert "node.textContent" not in distance_status_block
    assert "node.dataset.tone" not in distance_status_block
    assert "innerHTML" not in distance_status_block

    distance_rows_start = app_js.index("function renderProfileDistanceRows", distance_json_start)
    distance_json_block = app_js[distance_json_start:distance_rows_start]
    assert "renderProfileDistanceJsonInto(jsonField, formatDistanceJson(profileUiState.distanceRows));" in distance_json_block
    assert "jsonField.value =" not in distance_json_block
    assert "profileUiState.distanceJsonDirty = false" in distance_json_block
    assert "innerHTML" not in distance_json_block

    apply_start = app_js.index("function applyProfileEditor")
    collect_start = app_js.index("function collectProfileFormValues", apply_start)
    apply_block = app_js[apply_start:collect_start]
    assert "renderProfileEditorChromeInto({" in apply_block
    assert 'status: qs("profile-editor-status")' in apply_block
    assert 'setPrimaryButton: qs("profile-set-primary")' in apply_block
    assert 'deleteButton: qs("profile-delete")' in apply_block
    assert 'distanceAdvancedDetails: qs("profile-distance-advanced-details")' in apply_block
    assert "statusMessage: presentation.editorStatus" in apply_block
    assert "hasProfile: Boolean(resolved.id)" in apply_block
    assert "useAsMainLabel: presentation.useAsMainLabel" in apply_block
    assert 'deleteLabel: "Delete profile"' in apply_block
    assert "collapseDistanceAdvanced: true" in apply_block
    assert 'qs("profile-editor-status").textContent' not in apply_block
    assert 'qs("profile-set-primary").disabled' not in apply_block
    assert 'qs("profile-delete").disabled' not in apply_block
    assert 'qs("profile-set-primary").textContent' not in apply_block
    assert 'qs("profile-delete").textContent' not in apply_block
    assert 'qs("profile-distance-advanced-details").open' not in apply_block
    assert "innerHTML" not in apply_block

    script = r"""
const profileUi = await import(__PROFILE_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    dataset: {},
    children: [],
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    disabled: false,
    open: false,
    value: "",
  };
  Object.defineProperty(element, "textContent", {
    get() {
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
    },
  });
  return element;
}

function countInnerHtmlWrites(...nodes) {
  return nodes.reduce((total, node) => total + (node?.innerHTMLAssignments || []).length, 0);
}

function summarizeChrome(nodes) {
  return {
    statusText: nodes.status.textContent,
    setPrimaryText: nodes.setPrimaryButton.textContent,
    setPrimaryDisabled: Boolean(nodes.setPrimaryButton.disabled),
    deleteText: nodes.deleteButton.textContent,
    deleteDisabled: Boolean(nodes.deleteButton.disabled),
    detailsOpen: Boolean(nodes.distanceAdvancedDetails.open),
    imgCount:
      (nodes.status.textContent.match(/<img/g) || []).length
      + (nodes.setPrimaryButton.textContent.match(/<img/g) || []).length
      + (nodes.deleteButton.textContent.match(/<img/g) || []).length,
    scriptCount:
      (nodes.status.textContent.match(/<script/g) || []).length
      + (nodes.setPrimaryButton.textContent.match(/<script/g) || []).length
      + (nodes.deleteButton.textContent.match(/<script/g) || []).length,
    innerHTMLWrites: countInnerHtmlWrites(
      nodes.status,
      nodes.setPrimaryButton,
      nodes.deleteButton,
      nodes.distanceAdvancedDetails,
    ),
  };
}

function makeChromeNodes() {
  const nodes = {
    status: makeElement("p"),
    setPrimaryButton: makeElement("button"),
    deleteButton: makeElement("button"),
    distanceAdvancedDetails: makeElement("details"),
  };
  nodes.distanceAdvancedDetails.open = true;
  return nodes;
}

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;

const distanceStatus = makeElement("p");
profileUi.renderProfileDistanceStatusInto(distanceStatus, {
  tone: "ok",
  message: `Saved ${malicious}`,
});
const distanceStatusWithEmptyTone = makeElement("p");
distanceStatusWithEmptyTone.dataset.tone = "stale";
profileUi.renderProfileDistanceStatusInto(distanceStatusWithEmptyTone, {
  tone: "",
  message: `Cleared ${malicious}`,
});
const nullDistanceStatusResult = profileUi.renderProfileDistanceStatusInto(null, {
  tone: "bad",
  message: "ignored",
});

const jsonField = makeElement("textarea");
profileUi.renderProfileDistanceJsonInto(jsonField, `{"City":"${malicious}"}`);
const nullJsonResult = profileUi.renderProfileDistanceJsonInto(null, "ignored");

const existingNodes = makeChromeNodes();
profileUi.renderProfileEditorChromeInto(existingNodes, {
  statusMessage: `Existing ${malicious}`,
  hasProfile: true,
  useAsMainLabel: `Use ${malicious}`,
  deleteLabel: `Delete ${malicious}`,
  collapseDistanceAdvanced: true,
});

const draftNodes = makeChromeNodes();
profileUi.renderProfileEditorChromeInto(draftNodes, {
  statusMessage: `Draft ${malicious}`,
  hasProfile: false,
  useAsMainLabel: "Use as main profile",
  deleteLabel: "Delete profile",
  collapseDistanceAdvanced: true,
});

const preservedDetailsNodes = makeChromeNodes();
profileUi.renderProfileEditorChromeInto(preservedDetailsNodes, {
  statusMessage: "Preserve details",
  hasProfile: true,
  useAsMainLabel: "Main profile",
  deleteLabel: "Delete profile",
  collapseDistanceAdvanced: false,
});

const missingNodeResult = profileUi.renderProfileEditorChromeInto({
  status: null,
  setPrimaryButton: null,
  deleteButton: null,
  distanceAdvancedDetails: null,
}, {
  statusMessage: `Missing ${malicious}`,
  hasProfile: false,
  useAsMainLabel: `Missing ${malicious}`,
  deleteLabel: `Delete ${malicious}`,
  collapseDistanceAdvanced: true,
});

console.log(JSON.stringify({
  distanceStatusExportedType: typeof profileUi.renderProfileDistanceStatusInto,
  distanceJsonExportedType: typeof profileUi.renderProfileDistanceJsonInto,
  editorChromeExportedType: typeof profileUi.renderProfileEditorChromeInto,
  distanceStatus: {
    text: distanceStatus.textContent,
    tone: distanceStatus.dataset.tone || "",
    innerHTMLWrites: countInnerHtmlWrites(distanceStatus),
  },
  emptyToneStatus: {
    text: distanceStatusWithEmptyTone.textContent,
    tonePresent: Object.prototype.hasOwnProperty.call(distanceStatusWithEmptyTone.dataset, "tone"),
    innerHTMLWrites: countInnerHtmlWrites(distanceStatusWithEmptyTone),
  },
  jsonField: {
    value: jsonField.value,
    text: jsonField.textContent,
    innerHTMLWrites: countInnerHtmlWrites(jsonField),
  },
  existing: summarizeChrome(existingNodes),
  draft: summarizeChrome(draftNodes),
  preservedDetails: summarizeChrome(preservedDetailsNodes),
  nullDistanceStatusResultType: nullDistanceStatusResult === undefined ? "undefined" : typeof nullDistanceStatusResult,
  nullJsonResultType: nullJsonResult === undefined ? "undefined" : typeof nullJsonResult,
  missingNodeResultType: missingNodeResult === undefined ? "undefined" : typeof missingNodeResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__PROFILE_UI_MODULE_URL__": "profile_ui.js"},
        timeout_seconds=30,
    )

    assert results["distanceStatusExportedType"] == "function"
    assert results["distanceJsonExportedType"] == "function"
    assert results["editorChromeExportedType"] == "function"
    assert results["distanceStatus"] == {
        "text": "Saved <img src=x onerror=alert(1)><script>bad()</script>",
        "tone": "ok",
        "innerHTMLWrites": 0,
    }
    assert results["emptyToneStatus"] == {
        "text": "Cleared <img src=x onerror=alert(1)><script>bad()</script>",
        "tonePresent": False,
        "innerHTMLWrites": 0,
    }
    assert results["jsonField"] == {
        "value": '{"City":"<img src=x onerror=alert(1)><script>bad()</script>"}',
        "text": "",
        "innerHTMLWrites": 0,
    }
    assert results["existing"] == {
        "statusText": "Existing <img src=x onerror=alert(1)><script>bad()</script>",
        "setPrimaryText": "Use <img src=x onerror=alert(1)><script>bad()</script>",
        "setPrimaryDisabled": False,
        "deleteText": "Delete <img src=x onerror=alert(1)><script>bad()</script>",
        "deleteDisabled": False,
        "detailsOpen": False,
        "imgCount": 3,
        "scriptCount": 3,
        "innerHTMLWrites": 0,
    }
    assert results["draft"] == {
        "statusText": "Draft <img src=x onerror=alert(1)><script>bad()</script>",
        "setPrimaryText": "Use as main profile",
        "setPrimaryDisabled": True,
        "deleteText": "Delete profile",
        "deleteDisabled": True,
        "detailsOpen": False,
        "imgCount": 1,
        "scriptCount": 1,
        "innerHTMLWrites": 0,
    }
    assert results["preservedDetails"] == {
        "statusText": "Preserve details",
        "setPrimaryText": "Main profile",
        "setPrimaryDisabled": False,
        "deleteText": "Delete profile",
        "deleteDisabled": False,
        "detailsOpen": True,
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["nullDistanceStatusResultType"] == "undefined"
    assert results["nullJsonResultType"] == "undefined"
    assert results["missingNodeResultType"] == "undefined"


def test_dashboard_ui_module_centralizes_safe_card_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    dashboard_ui_module = static_dir / "dashboard_ui.js"

    assert dashboard_ui_module.exists()
    assert 'from "./dashboard_ui.js"' in app_js
    assert "export function renderDashboardCardsInto" not in app_js
    assert "export function renderSummaryGridInto" not in app_js
    assert "export function renderCapabilityCardsInto" not in app_js
    assert "export function renderParityAuditInto" not in app_js
    assert 'renderDashboardCardsInto(qs("dashboard-cards"), cards)' in app_js
    assert "renderSummaryGridInto(qs(containerId), items)" in app_js
    assert "renderCapabilityCardsInto(qs(containerId), cards)" in app_js
    assert "renderParityAuditInto({" in app_js
    assert 'resultContainer: qs("parity-audit-result")' in app_js

    script = r"""
const dashboardUi = await import(__DASHBOARD_UI_MODULE_URL__);

function createClassList(element) {
  return {
    add(...names) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      names.forEach((name) => classes.add(name));
      element.className = Array.from(classes).join(" ");
    },
    remove(...names) {
      const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
      names.forEach((name) => classes.delete(name));
      element.className = Array.from(classes).join(" ");
    },
  };
}

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  element.classList = createClassList(element);
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function collectClasses(node) {
  const classes = [];
  walk(node, (current) => {
    if (String(current.className || "").trim()) {
      classes.push(current.className);
    }
  });
  return classes;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const dashboardContainer = document.createElement("div");
dashboardUi.renderDashboardCardsInto(dashboardContainer, [
  { title: malicious, description: `Description ${malicious}`, status: "ready" },
  { title: "Queued", description: "Waiting", status: "warming_up" },
]);

const summaryContainer = document.createElement("div");
dashboardUi.renderSummaryGridInto(summaryContainer, [
  { label: `Saved ${malicious}`, value: `Value ${malicious}` },
]);

const capabilityContainer = document.createElement("div");
dashboardUi.renderCapabilityCardsInto(capabilityContainer, [
  { title: `Capability ${malicious}`, text: `Line one\nLine ${malicious}`, status: "bad", label: "Blocked" },
  { title: "Info", text: "Status detail", status: "info", label: "Checking" },
]);

const parityStatus = document.createElement("div");
const parityGrid = document.createElement("div");
const parityResult = document.createElement("div");
parityResult.className = "result-card empty-state";
dashboardUi.renderParityAuditInto({
  statusNode: parityStatus,
  gridContainer: parityGrid,
  resultContainer: parityResult,
  audit: {
    checklist: [
      { title: `Ready ${malicious}`, description: `Ready detail ${malicious}`, status: "ready" },
      { title: "Blocked item", description: "Blocked detail", status: "blocked" },
      { title: "Needs review", description: "Review detail", status: "needs_review" },
    ],
    promotion_recommendation: {
      status: "ready_for_daily_use",
      headline: `Headline ${malicious}`,
      recommended_workflows: [`Workflow ${malicious}`],
    },
    remaining_limitations: [`Limitation ${malicious}`],
  },
  presentation: {
    parityStatus: `Parity status ${malicious}`,
    readyCountLine: `Ready count ${malicious}`,
    resultChipLabel: "Ready for daily use",
    resultNextTitle: `Next ${malicious}`,
    resultLimitsTitle: `Limits ${malicious}`,
  },
});

const fallbackStatus = document.createElement("div");
const fallbackGrid = document.createElement("div");
const fallbackResult = document.createElement("div");
fallbackResult.className = "result-card empty-state";
dashboardUi.renderParityAuditInto({
  statusNode: fallbackStatus,
  gridContainer: fallbackGrid,
  resultContainer: fallbackResult,
  audit: {
    checklist: [],
    promotion_recommendation: { status: "blocked" },
    remaining_limitations: [],
  },
  presentation: {
    parityStatus: "Fallback parity status",
    readyCountLine: "Fallback ready count",
    resultChipLabel: "Not ready",
    resultNextTitle: "Fallback next",
    resultLimitsTitle: "Fallback limits",
  },
});

const nullDashboard = dashboardUi.renderDashboardCardsInto(null, []);
const nullSummary = dashboardUi.renderSummaryGridInto(null, []);
const nullCapability = dashboardUi.renderCapabilityCardsInto(null, []);
const nullParity = dashboardUi.renderParityAuditInto({
  statusNode: null,
  gridContainer: null,
  resultContainer: null,
  audit: {},
  presentation: {
    parityStatus: "",
    readyCountLine: "",
    resultChipLabel: "",
    resultNextTitle: "",
    resultLimitsTitle: "",
  },
});

console.log(JSON.stringify({
  exportedTypes: {
    dashboard: typeof dashboardUi.renderDashboardCardsInto,
    summary: typeof dashboardUi.renderSummaryGridInto,
    capability: typeof dashboardUi.renderCapabilityCardsInto,
    parity: typeof dashboardUi.renderParityAuditInto,
  },
  dashboard: {
    text: dashboardContainer.textContent,
    articleCount: countTag(dashboardContainer, "article"),
    imgCount: countTag(dashboardContainer, "img"),
    scriptCount: countTag(dashboardContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(dashboardContainer),
    classes: collectClasses(dashboardContainer),
  },
  summary: {
    text: summaryContainer.textContent,
    articleCount: countTag(summaryContainer, "article"),
    imgCount: countTag(summaryContainer, "img"),
    scriptCount: countTag(summaryContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(summaryContainer),
    classes: collectClasses(summaryContainer),
  },
  capability: {
    text: capabilityContainer.textContent,
    articleCount: countTag(capabilityContainer, "article"),
    brCount: countTag(capabilityContainer, "br"),
    imgCount: countTag(capabilityContainer, "img"),
    scriptCount: countTag(capabilityContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(capabilityContainer),
    classes: collectClasses(capabilityContainer),
  },
  parity: {
    statusText: parityStatus.textContent,
    gridText: parityGrid.textContent,
    resultText: parityResult.textContent,
    gridArticleCount: countTag(parityGrid, "article"),
    resultHeaderCount: collectClasses(parityResult).filter((name) => name === "result-header").length,
    gridImgCount: countTag(parityGrid, "img"),
    gridScriptCount: countTag(parityGrid, "script"),
    resultImgCount: countTag(parityResult, "img"),
    resultScriptCount: countTag(parityResult, "script"),
    innerHTMLWrites: countInnerHtmlWrites(parityGrid) + countInnerHtmlWrites(parityResult),
    gridClasses: collectClasses(parityGrid),
    resultClasses: collectClasses(parityResult),
    resultContainerClass: parityResult.className,
  },
  fallbackParity: {
    statusText: fallbackStatus.textContent,
    gridArticleCount: countTag(fallbackGrid, "article"),
    resultText: fallbackResult.textContent,
    resultClasses: collectClasses(fallbackResult),
    resultContainerClass: fallbackResult.className,
  },
  nullResultTypes: [
    nullDashboard === undefined ? "undefined" : typeof nullDashboard,
    nullSummary === undefined ? "undefined" : typeof nullSummary,
    nullCapability === undefined ? "undefined" : typeof nullCapability,
    nullParity === undefined ? "undefined" : typeof nullParity,
  ],
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__DASHBOARD_UI_MODULE_URL__": "dashboard_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedTypes"] == {
        "dashboard": "function",
        "summary": "function",
        "capability": "function",
        "parity": "function",
    }
    assert "<img src=x onerror=alert(1)><script>bad()</script>" in results["dashboard"]["text"]
    assert "Ready" in results["dashboard"]["text"]
    assert "warming up" in results["dashboard"]["text"]
    assert results["dashboard"]["articleCount"] == 2
    assert results["dashboard"]["imgCount"] == 0
    assert results["dashboard"]["scriptCount"] == 0
    assert results["dashboard"]["innerHTMLWrites"] == 0
    assert "launch-card ready" in results["dashboard"]["classes"]
    assert "launch-card planned" in results["dashboard"]["classes"]
    assert "status-chip ok" in results["dashboard"]["classes"]
    assert "status-chip warn" in results["dashboard"]["classes"]

    assert "Saved <img src=x onerror=alert(1)><script>bad()</script>" in results["summary"]["text"]
    assert "Value <img src=x onerror=alert(1)><script>bad()</script>" in results["summary"]["text"]
    assert results["summary"]["articleCount"] == 1
    assert results["summary"]["imgCount"] == 0
    assert results["summary"]["scriptCount"] == 0
    assert results["summary"]["innerHTMLWrites"] == 0
    assert "summary-card" in results["summary"]["classes"]
    assert "word-break" in results["summary"]["classes"]

    assert "Capability <img src=x onerror=alert(1)><script>bad()</script>" in results["capability"]["text"]
    assert "Line <img src=x onerror=alert(1)><script>bad()</script>" in results["capability"]["text"]
    assert "Blocked" in results["capability"]["text"]
    assert "Checking" in results["capability"]["text"]
    assert results["capability"]["articleCount"] == 2
    assert results["capability"]["brCount"] == 1
    assert results["capability"]["imgCount"] == 0
    assert results["capability"]["scriptCount"] == 0
    assert results["capability"]["innerHTMLWrites"] == 0
    assert "status-card" in results["capability"]["classes"]
    assert "status-chip bad" in results["capability"]["classes"]
    assert "status-chip info" in results["capability"]["classes"]

    assert "Parity status <img src=x onerror=alert(1)><script>bad()</script>" == results["parity"]["statusText"]
    assert "Ready <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["gridText"]
    assert "Ready detail <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["gridText"]
    assert "blocked" in results["parity"]["gridText"]
    assert "needs review" in results["parity"]["gridText"]
    assert "Headline <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["resultText"]
    assert "Ready count <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["resultText"]
    assert "Workflow <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["resultText"]
    assert "Limitation <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["resultText"]
    assert "Next <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["resultText"]
    assert "Limits <img src=x onerror=alert(1)><script>bad()</script>" in results["parity"]["resultText"]
    assert results["parity"]["gridArticleCount"] == 3
    assert results["parity"]["resultHeaderCount"] == 1
    assert results["parity"]["gridImgCount"] == 0
    assert results["parity"]["gridScriptCount"] == 0
    assert results["parity"]["resultImgCount"] == 0
    assert results["parity"]["resultScriptCount"] == 0
    assert results["parity"]["innerHTMLWrites"] == 0
    assert "status-chip ok" in results["parity"]["gridClasses"]
    assert "status-chip bad" in results["parity"]["gridClasses"]
    assert "status-chip warn" in results["parity"]["gridClasses"]
    assert "status-chip ok" in results["parity"]["resultClasses"]
    assert results["parity"]["resultContainerClass"] == "result-card"
    assert results["fallbackParity"]["statusText"] == "Fallback parity status"
    assert results["fallbackParity"]["gridArticleCount"] == 0
    assert "Promotion recommendation unavailable." in results["fallbackParity"]["resultText"]
    assert "No recommendation items available." in results["fallbackParity"]["resultText"]
    assert "No limitations recorded." in results["fallbackParity"]["resultText"]
    assert "status-chip warn" in results["fallbackParity"]["resultClasses"]
    assert results["fallbackParity"]["resultContainerClass"] == "result-card"
    assert results["nullResultTypes"] == ["undefined", "undefined", "undefined", "undefined"]


def test_result_card_ui_module_centralizes_safe_result_helpers() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    result_card_ui_module = static_dir / "result_card_ui.js"
    interpretation_result_ui_js = (static_dir / "interpretation_result_ui.js").read_text(encoding="utf-8")

    assert result_card_ui_module.exists()
    assert 'from "./result_card_ui.js"' in interpretation_result_ui_js
    assert 'from "./result_card_ui.js"' not in app_js
    assert "function createStatusChip" not in app_js
    assert "function createResultHeader" not in app_js
    assert "function appendResultGridItem" not in app_js
    assert "container.appendChild(createResultHeader({" not in app_js
    assert 'appendResultGridItem(grid, "DOCX", result.docx_path || "Unavailable", { className: "word-break" })' not in app_js
    assert "appendResultGridItem(grid, \"Photo Taken Date\"" not in app_js

    script = r"""
const resultCardUi = await import(__RESULT_CARD_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    children: [],
    parentNode: null,
    title: "",
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function collectClasses(node) {
  const classes = [];
  walk(node, (current) => {
    if (String(current.className || "").trim()) {
      classes.push(current.className);
    }
  });
  return classes;
}

function firstTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let found = null;
  walk(node, (current) => {
    if (!found && current.tagName === target) {
      found = current;
    }
  });
  return found;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const header = resultCardUi.createResultHeader({
  title: `Title ${malicious}`,
  message: `Message ${malicious}`,
  label: `Label ${malicious}`,
  tone: "bad",
});
const emptyMessageHeader = resultCardUi.createResultHeader({
  title: "No message header",
  message: "",
  label: "Ready",
  tone: "ok",
});
const chip = resultCardUi.createStatusChip(`Chip ${malicious}`, "warn");
const grid = document.createElement("div");
grid.className = "result-grid";
const returnedItem = resultCardUi.appendResultGridItem(
  grid,
  `Grid ${malicious}`,
  `Line one\nLine ${malicious}`,
  {
    className: "word-break",
    multiline: true,
    titleValue: `Tooltip ${malicious}`,
  },
);
const paragraph = firstTag(returnedItem, "p");

console.log(JSON.stringify({
  exportedTypes: {
    chip: typeof resultCardUi.createStatusChip,
    header: typeof resultCardUi.createResultHeader,
    gridItem: typeof resultCardUi.appendResultGridItem,
  },
  header: {
    text: header.textContent,
    paragraphCount: countTag(header, "p"),
    imgCount: countTag(header, "img"),
    scriptCount: countTag(header, "script"),
    innerHTMLWrites: countInnerHtmlWrites(header),
    classes: collectClasses(header),
  },
  emptyMessageHeader: {
    paragraphCount: countTag(emptyMessageHeader, "p"),
    text: emptyMessageHeader.textContent,
  },
  chip: {
    text: chip.textContent,
    className: chip.className,
    imgCount: countTag(chip, "img"),
    scriptCount: countTag(chip, "script"),
    innerHTMLWrites: countInnerHtmlWrites(chip),
  },
  grid: {
    returnedIsAppended: grid.children[0] === returnedItem,
    text: grid.textContent,
    itemTag: returnedItem.tagName,
    brCount: countTag(grid, "br"),
    paragraphClass: paragraph?.className || "",
    paragraphTitle: paragraph?.title || "",
    imgCount: countTag(grid, "img"),
    scriptCount: countTag(grid, "script"),
    innerHTMLWrites: countInnerHtmlWrites(grid),
  },
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__RESULT_CARD_UI_MODULE_URL__": "result_card_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedTypes"] == {
        "chip": "function",
        "header": "function",
        "gridItem": "function",
    }
    assert "Title <img src=x onerror=alert(1)><script>bad()</script>" in results["header"]["text"]
    assert "Message <img src=x onerror=alert(1)><script>bad()</script>" in results["header"]["text"]
    assert "Label <img src=x onerror=alert(1)><script>bad()</script>" in results["header"]["text"]
    assert results["header"]["paragraphCount"] == 1
    assert results["header"]["imgCount"] == 0
    assert results["header"]["scriptCount"] == 0
    assert results["header"]["innerHTMLWrites"] == 0
    assert "result-header" in results["header"]["classes"]
    assert "status-chip bad" in results["header"]["classes"]
    assert results["emptyMessageHeader"]["paragraphCount"] == 0
    assert results["emptyMessageHeader"]["text"] == "No message headerReady"

    assert results["chip"]["text"] == "Chip <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["chip"]["className"] == "status-chip warn"
    assert results["chip"]["imgCount"] == 0
    assert results["chip"]["scriptCount"] == 0
    assert results["chip"]["innerHTMLWrites"] == 0

    assert results["grid"]["returnedIsAppended"] is True
    assert "Grid <img src=x onerror=alert(1)><script>bad()</script>" in results["grid"]["text"]
    assert "Line <img src=x onerror=alert(1)><script>bad()</script>" in results["grid"]["text"]
    assert results["grid"]["itemTag"] == "DIV"
    assert results["grid"]["brCount"] == 1
    assert results["grid"]["paragraphClass"] == "word-break"
    assert results["grid"]["paragraphTitle"] == "Tooltip <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["grid"]["imgCount"] == 0
    assert results["grid"]["scriptCount"] == 0
    assert results["grid"]["innerHTMLWrites"] == 0


def test_interpretation_reference_ui_module_centralizes_safe_select_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_reference_ui_js = static_dir / "interpretation_reference_ui.js"

    assert interpretation_reference_ui_js.exists()
    interpretation_reference_ui_text = interpretation_reference_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_reference_ui.js"' in app_js
    assert "export function renderInterpretationCityOptionsInto" in interpretation_reference_ui_text
    assert "export function renderCourtEmailOptionsInto" in interpretation_reference_ui_text
    assert "export function renderServiceEntityOptionsInto" in interpretation_reference_ui_text
    assert "export function renderInterpretationFieldWarningInto" in interpretation_reference_ui_text
    assert "export function renderInterpretationDistanceHintInto" in interpretation_reference_ui_text
    assert "export function renderInterpretationActionButtonsInto" in interpretation_reference_ui_text
    assert "export function renderInterpretationCityAddButtonsInto" in interpretation_reference_ui_text
    assert "export function syncInterpretationCityDialogStateInto" in interpretation_reference_ui_text
    assert "export function renderInterpretationCityDialogContentInto" in interpretation_reference_ui_text
    assert "renderInterpretationCityOptionsInto(select, reference.availableCities, currentValue);" in app_js
    assert "renderCourtEmailOptionsInto(select, {" in app_js
    assert "renderServiceEntityOptionsInto(select, options, selectedValue);" in app_js
    assert "renderInterpretationFieldWarningInto(node, { message, tone });" in app_js
    assert "renderInterpretationDistanceHintInto(" in app_js
    assert "renderInterpretationActionButtonsInto(actionButtons, { blocked });" in app_js
    assert "renderInterpretationCityAddButtonsInto({" in app_js
    assert "syncInterpretationCityDialogStateInto(backdrop, document.body, interpretationCityState.dialogOpen);" in app_js
    assert "renderInterpretationCityDialogContentInto({" in app_js

    city_start = app_js.index("function populateInterpretationCitySelect")
    court_email_start = app_js.index("function populateCourtEmailSelect", city_start)
    city_block = app_js[city_start:court_email_start]
    assert "innerHTML" not in city_block
    assert "document.createElement(\"option\")" not in city_block

    service_entity_start = app_js.index("function populateServiceEntitySelect", court_email_start)
    court_email_block = app_js[court_email_start:service_entity_start]
    assert "innerHTML" not in court_email_block
    assert "document.createElement(\"option\")" not in court_email_block

    refresh_reference_start = app_js.index("function refreshInterpretationReferenceBoundControls", service_entity_start)
    service_entity_block = app_js[service_entity_start:refresh_reference_start]
    assert "innerHTML" not in service_entity_block
    assert "document.createElement(\"option\")" not in service_entity_block

    field_warning_start = app_js.index("function setInterpretationFieldWarning")
    location_guard_start = app_js.index("function setInterpretationLocationGuard", field_warning_start)
    field_warning_block = app_js[field_warning_start:location_guard_start]
    assert "innerHTML" not in field_warning_block
    assert "node.textContent" not in field_warning_block
    assert "classList.toggle(\"hidden\"" not in field_warning_block
    assert "classList.toggle(\"is-warning\"" not in field_warning_block
    assert "classList.toggle(\"is-danger\"" not in field_warning_block

    distance_sync_start = app_js.index("function syncInterpretationDistanceFromReference")
    action_availability_start = app_js.index("function updateInterpretationActionAvailability", distance_sync_start)
    distance_sync_block = app_js[distance_sync_start:action_availability_start]
    assert "innerHTML" not in distance_sync_block
    assert "hint.textContent" not in distance_sync_block

    city_controls_end = app_js.index("function syncInterpretationCityControls", action_availability_start)
    action_availability_block = app_js[action_availability_start:city_controls_end]
    assert "innerHTML" not in action_availability_block
    assert "button.disabled" not in action_availability_block
    assert "button.classList.add(\"hidden\")" not in action_availability_block
    assert "caseAddButton.textContent" not in action_availability_block
    assert "serviceAddButton.textContent" not in action_availability_block
    assert "serviceAddButton.disabled" not in action_availability_block

    city_dialog_start = app_js.index("function setInterpretationCityDialogOpen")
    close_dialog_start = app_js.index("function closeInterpretationCityDialog", city_dialog_start)
    city_dialog_block = app_js[city_dialog_start:close_dialog_start]
    assert "interpretationCityState.dialogOpen = Boolean(open)" in city_dialog_block
    assert "innerHTML" not in city_dialog_block
    assert "escapeHtml" not in city_dialog_block
    assert "backdrop.classList.toggle" not in city_dialog_block
    assert "backdrop.setAttribute(\"aria-hidden\"" not in city_dialog_block
    assert "document.body.dataset.interpretationCityDialog" not in city_dialog_block

    open_dialog_start = app_js.index("function openInterpretationCityDialog")
    reference_update_start = app_js.index("function applyInterpretationReferenceUpdate", open_dialog_start)
    open_dialog_block = app_js[open_dialog_start:reference_update_start]
    assert "renderInterpretationCityDialogContentInto({" in open_dialog_block
    assert "title.textContent" not in open_dialog_block
    assert "status.textContent" not in open_dialog_block
    assert "cityInput.readOnly" not in open_dialog_block
    assert "distanceShell.classList.toggle(\"hidden\"" not in open_dialog_block
    assert "distanceHint.textContent" not in open_dialog_block
    assert "confirmButton.textContent" not in open_dialog_block

    script = r"""
const interpretationReferenceUi = await import(__INTERPRETATION_REFERENCE_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const classes = new Set();
  const attributes = new Map();
  const syncClassName = () => {
    element.className = Array.from(classes).join(" ");
  };
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    children: [],
    parentNode: null,
    dataset: {},
    value: "",
    selected: false,
    disabled: false,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
    getAttribute(name) {
      return attributes.has(String(name)) ? attributes.get(String(name)) : null;
    },
    setAttribute(name, value) {
      attributes.set(String(name), String(value));
    },
    classList: {
      add(...names) {
        for (const name of names) {
          classes.add(String(name));
        }
        syncClassName();
      },
      remove(...names) {
        for (const name of names) {
          classes.delete(String(name));
        }
        syncClassName();
      },
      contains(name) {
        return classes.has(String(name));
      },
      toggle(name, force) {
        const key = String(name);
        const shouldAdd = force === undefined ? !classes.has(key) : Boolean(force);
        if (shouldAdd) {
          classes.add(key);
        } else {
          classes.delete(key);
        }
        syncClassName();
        return shouldAdd;
      },
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function summarizeSelect(select) {
  return {
    value: select.value,
    optionValues: select.children.map((option) => option.value),
    optionTexts: select.children.map((option) => option.textContent),
    selectedFlags: select.children.map((option) => Boolean(option.selected)),
    text: select.textContent,
    imgCount: countTag(select, "img"),
    scriptCount: countTag(select, "script"),
    innerHTMLWrites: countInnerHtmlWrites(select),
  };
}

function summarizeWarning(node) {
  return {
    className: node.className,
    text: node.textContent,
    hidden: node.classList.contains("hidden"),
    isWarning: node.classList.contains("is-warning"),
    isDanger: node.classList.contains("is-danger"),
    imgCount: countTag(node, "img"),
    scriptCount: countTag(node, "script"),
    innerHTMLWrites: countInnerHtmlWrites(node),
  };
}

function summarizeTextNode(node) {
  return {
    text: node.textContent,
    imgCount: countTag(node, "img"),
    scriptCount: countTag(node, "script"),
    innerHTMLWrites: countInnerHtmlWrites(node),
  };
}

function summarizeButton(node) {
  return {
    text: node.textContent,
    disabled: Boolean(node.disabled),
    hidden: node.classList.contains("hidden"),
    imgCount: countTag(node, "img"),
    scriptCount: countTag(node, "script"),
    innerHTMLWrites: countInnerHtmlWrites(node),
  };
}

function summarizeCityDialogContent(nodes) {
  return {
    title: nodes.title.textContent,
    status: nodes.status.textContent,
    readOnly: Boolean(nodes.cityInput.readOnly),
    distanceHidden: nodes.distanceShell.classList.contains("hidden"),
    distanceHint: nodes.distanceHint.textContent,
    confirmLabel: nodes.confirmButton.textContent,
    imgCount:
      countTag(nodes.title, "img")
      + countTag(nodes.status, "img")
      + countTag(nodes.distanceHint, "img")
      + countTag(nodes.confirmButton, "img"),
    scriptCount:
      countTag(nodes.title, "script")
      + countTag(nodes.status, "script")
      + countTag(nodes.distanceHint, "script")
      + countTag(nodes.confirmButton, "script"),
    innerHTMLWrites: countInnerHtmlWrites(
      nodes.title,
      nodes.status,
      nodes.cityInput,
      nodes.distanceShell,
      nodes.distanceHint,
      nodes.confirmButton,
    ),
  };
}

function cityDialogNodes() {
  return {
    title: document.createElement("h2"),
    status: document.createElement("p"),
    cityInput: document.createElement("input"),
    distanceShell: document.createElement("div"),
    distanceHint: document.createElement("p"),
    confirmButton: document.createElement("button"),
  };
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;

const citySelect = document.createElement("select");
const staleCityOption = document.createElement("option");
staleCityOption.value = "stale";
staleCityOption.textContent = "stale";
citySelect.appendChild(staleCityOption);
interpretationReferenceUi.renderInterpretationCityOptionsInto(
  citySelect,
  [`Beja ${malicious}`, "Cuba"],
  `Beja ${malicious}`,
);

const emailSelect = document.createElement("select");
const staleEmailOption = document.createElement("option");
staleEmailOption.value = "stale";
staleEmailOption.textContent = "stale";
emailSelect.appendChild(staleEmailOption);
interpretationReferenceUi.renderCourtEmailOptionsInto(emailSelect, {
  options: [`court-${malicious}@example.test`, "second@example.test"],
  selectedEmail: `court-${malicious}@example.test`,
});

const emptyEmailSelect = document.createElement("select");
interpretationReferenceUi.renderCourtEmailOptionsInto(emptyEmailSelect, {
  options: [],
  selectedEmail: "",
});

const serviceSelect = document.createElement("select");
const staleServiceOption = document.createElement("option");
staleServiceOption.value = "stale";
staleServiceOption.textContent = "stale";
serviceSelect.appendChild(staleServiceOption);
interpretationReferenceUi.renderServiceEntityOptionsInto(
  serviceSelect,
  [`GNR ${malicious}`, "PSP"],
  `GNR ${malicious}`,
);

const nullCityResult = interpretationReferenceUi.renderInterpretationCityOptionsInto(null, ["Ignored"], "Ignored");
const nullEmailResult = interpretationReferenceUi.renderCourtEmailOptionsInto(null, {
  options: ["ignored@example.test"],
  selectedEmail: "ignored@example.test",
});
const nullServiceResult = interpretationReferenceUi.renderServiceEntityOptionsInto(null, ["Ignored"], "Ignored");
const nullWarningResult = interpretationReferenceUi.renderInterpretationFieldWarningInto(null, {
  message: `Ignored ${malicious}`,
  tone: "danger",
});

const warningNode = document.createElement("p");
interpretationReferenceUi.renderInterpretationFieldWarningInto(warningNode, {
  message: `  Imported city ${malicious}  `,
  tone: "warning",
});

const dangerNode = document.createElement("p");
interpretationReferenceUi.renderInterpretationFieldWarningInto(dangerNode, {
  message: `Blocked city ${malicious}`,
  tone: "danger",
});

const otherToneNode = document.createElement("p");
interpretationReferenceUi.renderInterpretationFieldWarningInto(otherToneNode, {
  message: `Review city ${malicious}`,
  tone: "info",
});

const emptyNode = document.createElement("p");
interpretationReferenceUi.renderInterpretationFieldWarningInto(emptyNode, {
  message: "   ",
  tone: "danger",
});

const distanceHint = document.createElement("p");
interpretationReferenceUi.renderInterpretationDistanceHintInto(
  distanceHint,
  `Saved distance ${malicious}`,
);

const visibleActionButton = document.createElement("button");
visibleActionButton.setAttribute("aria-busy", "false");
const hiddenBusyActionButton = document.createElement("button");
hiddenBusyActionButton.classList.add("hidden");
hiddenBusyActionButton.setAttribute("aria-busy", "true");
interpretationReferenceUi.renderInterpretationActionButtonsInto(
  [visibleActionButton, hiddenBusyActionButton, null],
  { blocked: false },
);

const blockedActionButton = document.createElement("button");
blockedActionButton.setAttribute("aria-busy", "false");
interpretationReferenceUi.renderInterpretationActionButtonsInto(
  [blockedActionButton],
  { blocked: true },
);

const caseAddButton = document.createElement("button");
const serviceAddButton = document.createElement("button");
interpretationReferenceUi.renderInterpretationCityAddButtonsInto(
  { caseButton: caseAddButton, serviceButton: serviceAddButton },
  {
    provisionalCaseCity: `Beja ${malicious}`,
    provisionalServiceCity: `Cuba ${malicious}`,
    serviceSame: true,
  },
);

const emptyCaseAddButton = document.createElement("button");
const emptyServiceAddButton = document.createElement("button");
emptyServiceAddButton.disabled = true;
interpretationReferenceUi.renderInterpretationCityAddButtonsInto(
  { caseButton: emptyCaseAddButton, serviceButton: emptyServiceAddButton },
  { provisionalCaseCity: "", provisionalServiceCity: "", serviceSame: false },
);

const nullDistanceResult = interpretationReferenceUi.renderInterpretationDistanceHintInto(null, "ignored");
const nullActionResult = interpretationReferenceUi.renderInterpretationActionButtonsInto(null, { blocked: true });
const nullAddButtonResult = interpretationReferenceUi.renderInterpretationCityAddButtonsInto(null, {
  provisionalCaseCity: "Ignored",
  provisionalServiceCity: "Ignored",
  serviceSame: true,
});

const openBackdrop = document.createElement("div");
openBackdrop.classList.add("hidden");
const openBody = document.createElement("body");
interpretationReferenceUi.syncInterpretationCityDialogStateInto(openBackdrop, openBody, true);

const closedBackdrop = document.createElement("div");
const closedBody = document.createElement("body");
closedBody.dataset.interpretationCityDialog = "open";
interpretationReferenceUi.syncInterpretationCityDialogStateInto(closedBackdrop, closedBody, false);

const truthyBackdrop = document.createElement("div");
const truthyBody = document.createElement("body");
interpretationReferenceUi.syncInterpretationCityDialogStateInto(truthyBackdrop, truthyBody, "yes");

const missingBodyBackdrop = document.createElement("div");
interpretationReferenceUi.syncInterpretationCityDialogStateInto(missingBodyBackdrop, null, false);

const nullBackdropBody = document.createElement("body");
nullBackdropBody.dataset.interpretationCityDialog = "unchanged";
const nullBackdropResult = interpretationReferenceUi.syncInterpretationCityDialogStateInto(null, nullBackdropBody, true);

const addCaseDialog = cityDialogNodes();
interpretationReferenceUi.renderInterpretationCityDialogContentInto(addCaseDialog, {
  title: `Add Case City ${malicious}`,
  status: `Confirm the city details before continuing. ${malicious}`,
  lockedCity: false,
  showDistance: false,
  distanceHint: `Optional one-way distance from Lisbon ${malicious}.`,
  confirmLabel: `Save City ${malicious}`,
});

const distanceDialog = cityDialogNodes();
distanceDialog.distanceShell.classList.add("hidden");
interpretationReferenceUi.renderInterpretationCityDialogContentInto(distanceDialog, {
  title: `Confirm One-Way Distance ${malicious}`,
  status: `Enter the one-way distance from Porto ${malicious} to Beja ${malicious}.`,
  lockedCity: true,
  showDistance: true,
  distanceHint: `Optional one-way distance from Porto ${malicious}.`,
  confirmLabel: `Use distance ${malicious}`,
});

const missingNodesDialog = {
  title: document.createElement("h2"),
  status: null,
  cityInput: null,
  distanceShell: document.createElement("div"),
  distanceHint: null,
  confirmButton: document.createElement("button"),
};
interpretationReferenceUi.renderInterpretationCityDialogContentInto(missingNodesDialog, {
  title: "Partial dialog",
  status: "Ignored status",
  lockedCity: true,
  showDistance: false,
  distanceHint: "Ignored hint",
  confirmLabel: "Confirm partial",
});

const nullDialogContentResult = interpretationReferenceUi.renderInterpretationCityDialogContentInto(null, {
  title: `Ignored ${malicious}`,
  status: `Ignored ${malicious}`,
  lockedCity: true,
  showDistance: true,
  distanceHint: `Ignored ${malicious}`,
  confirmLabel: `Ignored ${malicious}`,
});

console.log(JSON.stringify({
  exportedTypes: {
    city: typeof interpretationReferenceUi.renderInterpretationCityOptionsInto,
    email: typeof interpretationReferenceUi.renderCourtEmailOptionsInto,
    service: typeof interpretationReferenceUi.renderServiceEntityOptionsInto,
    fieldWarning: typeof interpretationReferenceUi.renderInterpretationFieldWarningInto,
    distanceHint: typeof interpretationReferenceUi.renderInterpretationDistanceHintInto,
    actionButtons: typeof interpretationReferenceUi.renderInterpretationActionButtonsInto,
    cityAddButtons: typeof interpretationReferenceUi.renderInterpretationCityAddButtonsInto,
    cityDialogState: typeof interpretationReferenceUi.syncInterpretationCityDialogStateInto,
    cityDialogContent: typeof interpretationReferenceUi.renderInterpretationCityDialogContentInto,
  },
  city: summarizeSelect(citySelect),
  email: summarizeSelect(emailSelect),
  emptyEmail: summarizeSelect(emptyEmailSelect),
  service: summarizeSelect(serviceSelect),
  warning: summarizeWarning(warningNode),
  danger: summarizeWarning(dangerNode),
  otherTone: summarizeWarning(otherToneNode),
  emptyWarning: summarizeWarning(emptyNode),
  distanceHint: summarizeTextNode(distanceHint),
  visibleActionButton: summarizeButton(visibleActionButton),
  hiddenBusyActionButton: summarizeButton(hiddenBusyActionButton),
  blockedActionButton: summarizeButton(blockedActionButton),
  caseAddButton: summarizeButton(caseAddButton),
  serviceAddButton: summarizeButton(serviceAddButton),
  emptyCaseAddButton: summarizeButton(emptyCaseAddButton),
  emptyServiceAddButton: summarizeButton(emptyServiceAddButton),
  cityDialogOpen: {
    className: openBackdrop.className,
    ariaHidden: openBackdrop.getAttribute("aria-hidden"),
    bodyState: openBody.dataset.interpretationCityDialog || "",
    innerHTMLWrites: countInnerHtmlWrites(openBackdrop, openBody),
  },
  cityDialogClosed: {
    className: closedBackdrop.className,
    ariaHidden: closedBackdrop.getAttribute("aria-hidden"),
    bodyState: closedBody.dataset.interpretationCityDialog || "",
    innerHTMLWrites: countInnerHtmlWrites(closedBackdrop, closedBody),
  },
  cityDialogTruthy: {
    className: truthyBackdrop.className,
    ariaHidden: truthyBackdrop.getAttribute("aria-hidden"),
    bodyState: truthyBody.dataset.interpretationCityDialog || "",
    innerHTMLWrites: countInnerHtmlWrites(truthyBackdrop, truthyBody),
  },
  cityDialogMissingBody: {
    className: missingBodyBackdrop.className,
    ariaHidden: missingBodyBackdrop.getAttribute("aria-hidden"),
    bodyState: "",
    innerHTMLWrites: countInnerHtmlWrites(missingBodyBackdrop),
  },
  cityDialogAddCase: summarizeCityDialogContent(addCaseDialog),
  cityDialogDistance: summarizeCityDialogContent(distanceDialog),
  cityDialogMissingNodes: {
    title: missingNodesDialog.title.textContent,
    distanceHidden: missingNodesDialog.distanceShell.classList.contains("hidden"),
    confirmLabel: missingNodesDialog.confirmButton.textContent,
    innerHTMLWrites: countInnerHtmlWrites(
      missingNodesDialog.title,
      missingNodesDialog.distanceShell,
      missingNodesDialog.confirmButton,
    ),
  },
  nullBackdropBodyState: nullBackdropBody.dataset.interpretationCityDialog,
  nullBackdropInnerHTMLWrites: countInnerHtmlWrites(nullBackdropBody),
  nullCityResult,
  nullEmailResult,
  nullServiceResult,
  nullWarningResult,
  nullDistanceResult,
  nullActionResult,
  nullAddButtonResult,
  nullBackdropResult,
  nullDialogContentResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REFERENCE_UI_MODULE_URL__": "interpretation_reference_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedTypes"] == {
        "city": "function",
        "email": "function",
        "service": "function",
        "fieldWarning": "function",
        "distanceHint": "function",
        "actionButtons": "function",
        "cityAddButtons": "function",
        "cityDialogState": "function",
        "cityDialogContent": "function",
    }
    assert results["city"]["optionTexts"][0] == "Select a city"
    assert results["city"]["optionValues"][0] == ""
    assert "Beja <img src=x onerror=alert(1)><script>bad()</script>" in results["city"]["text"]
    assert results["city"]["optionValues"][1] == "Beja <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["city"]["value"] == "Beja <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["city"]["imgCount"] == 0
    assert results["city"]["scriptCount"] == 0
    assert results["city"]["innerHTMLWrites"] == 0

    assert results["email"]["optionTexts"][0] == "Select a court email"
    assert "court-<img src=x onerror=alert(1)><script>bad()</script>@example.test" in results["email"]["text"]
    assert results["email"]["value"] == "court-<img src=x onerror=alert(1)><script>bad()</script>@example.test"
    assert results["email"]["innerHTMLWrites"] == 0
    assert results["emptyEmail"]["optionTexts"] == ["No email saved for this city"]
    assert results["emptyEmail"]["optionValues"] == [""]
    assert results["emptyEmail"]["value"] == ""

    assert results["service"]["optionTexts"][0] == "Select service entity"
    assert "GNR <img src=x onerror=alert(1)><script>bad()</script>" in results["service"]["text"]
    assert results["service"]["value"] == "GNR <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["service"]["imgCount"] == 0
    assert results["service"]["scriptCount"] == 0
    assert results["service"]["innerHTMLWrites"] == 0

    assert results["warning"]["text"] == "Imported city <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["warning"]["hidden"] is False
    assert results["warning"]["isWarning"] is True
    assert results["warning"]["isDanger"] is False
    assert results["warning"]["imgCount"] == 0
    assert results["warning"]["scriptCount"] == 0
    assert results["warning"]["innerHTMLWrites"] == 0

    assert results["danger"]["text"] == "Blocked city <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["danger"]["hidden"] is False
    assert results["danger"]["isWarning"] is False
    assert results["danger"]["isDanger"] is True
    assert results["danger"]["imgCount"] == 0
    assert results["danger"]["scriptCount"] == 0
    assert results["danger"]["innerHTMLWrites"] == 0

    assert results["otherTone"]["text"] == "Review city <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["otherTone"]["hidden"] is False
    assert results["otherTone"]["isWarning"] is False
    assert results["otherTone"]["isDanger"] is False
    assert results["otherTone"]["innerHTMLWrites"] == 0

    assert results["emptyWarning"]["text"] == ""
    assert results["emptyWarning"]["hidden"] is True
    assert results["emptyWarning"]["isWarning"] is False
    assert results["emptyWarning"]["isDanger"] is False
    assert results["emptyWarning"]["innerHTMLWrites"] == 0

    assert results["distanceHint"]["text"] == "Saved distance <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["distanceHint"]["imgCount"] == 0
    assert results["distanceHint"]["scriptCount"] == 0
    assert results["distanceHint"]["innerHTMLWrites"] == 0

    assert results["visibleActionButton"]["disabled"] is False
    assert results["visibleActionButton"]["hidden"] is False
    assert results["visibleActionButton"]["innerHTMLWrites"] == 0
    assert results["hiddenBusyActionButton"]["disabled"] is True
    assert results["hiddenBusyActionButton"]["hidden"] is True
    assert results["hiddenBusyActionButton"]["innerHTMLWrites"] == 0
    assert results["blockedActionButton"]["disabled"] is True
    assert results["blockedActionButton"]["innerHTMLWrites"] == 0

    assert results["caseAddButton"]["text"] == "Add “Beja <img src=x onerror=alert(1)><script>bad()</script>”"
    assert results["caseAddButton"]["disabled"] is False
    assert results["caseAddButton"]["imgCount"] == 0
    assert results["caseAddButton"]["scriptCount"] == 0
    assert results["caseAddButton"]["innerHTMLWrites"] == 0
    assert results["serviceAddButton"]["text"] == "Add “Cuba <img src=x onerror=alert(1)><script>bad()</script>”"
    assert results["serviceAddButton"]["disabled"] is True
    assert results["serviceAddButton"]["imgCount"] == 0
    assert results["serviceAddButton"]["scriptCount"] == 0
    assert results["serviceAddButton"]["innerHTMLWrites"] == 0
    assert results["emptyCaseAddButton"]["text"] == "Add city..."
    assert results["emptyCaseAddButton"]["disabled"] is False
    assert results["emptyServiceAddButton"]["text"] == "Add city..."
    assert results["emptyServiceAddButton"]["disabled"] is False

    assert results["cityDialogOpen"]["className"] == ""
    assert results["cityDialogOpen"]["ariaHidden"] == "false"
    assert results["cityDialogOpen"]["bodyState"] == "open"
    assert results["cityDialogOpen"]["innerHTMLWrites"] == 0

    assert results["cityDialogClosed"]["className"] == "hidden"
    assert results["cityDialogClosed"]["ariaHidden"] == "true"
    assert results["cityDialogClosed"]["bodyState"] == "closed"
    assert results["cityDialogClosed"]["innerHTMLWrites"] == 0

    assert results["cityDialogTruthy"]["className"] == ""
    assert results["cityDialogTruthy"]["ariaHidden"] == "false"
    assert results["cityDialogTruthy"]["bodyState"] == "open"
    assert results["cityDialogTruthy"]["innerHTMLWrites"] == 0

    assert results["cityDialogMissingBody"]["className"] == "hidden"
    assert results["cityDialogMissingBody"]["ariaHidden"] == "true"
    assert results["cityDialogMissingBody"]["bodyState"] == ""
    assert results["cityDialogMissingBody"]["innerHTMLWrites"] == 0

    assert results["cityDialogAddCase"]["title"] == "Add Case City <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["cityDialogAddCase"]["status"] == "Confirm the city details before continuing. <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["cityDialogAddCase"]["readOnly"] is False
    assert results["cityDialogAddCase"]["distanceHidden"] is True
    assert results["cityDialogAddCase"]["distanceHint"] == "Optional one-way distance from Lisbon <img src=x onerror=alert(1)><script>bad()</script>."
    assert results["cityDialogAddCase"]["confirmLabel"] == "Save City <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["cityDialogAddCase"]["imgCount"] == 0
    assert results["cityDialogAddCase"]["scriptCount"] == 0
    assert results["cityDialogAddCase"]["innerHTMLWrites"] == 0

    assert results["cityDialogDistance"]["title"] == "Confirm One-Way Distance <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["cityDialogDistance"]["status"] == "Enter the one-way distance from Porto <img src=x onerror=alert(1)><script>bad()</script> to Beja <img src=x onerror=alert(1)><script>bad()</script>."
    assert results["cityDialogDistance"]["readOnly"] is True
    assert results["cityDialogDistance"]["distanceHidden"] is False
    assert results["cityDialogDistance"]["distanceHint"] == "Optional one-way distance from Porto <img src=x onerror=alert(1)><script>bad()</script>."
    assert results["cityDialogDistance"]["confirmLabel"] == "Use distance <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["cityDialogDistance"]["imgCount"] == 0
    assert results["cityDialogDistance"]["scriptCount"] == 0
    assert results["cityDialogDistance"]["innerHTMLWrites"] == 0

    assert results["cityDialogMissingNodes"] == {
        "title": "Partial dialog",
        "distanceHidden": True,
        "confirmLabel": "Confirm partial",
        "innerHTMLWrites": 0,
    }

    assert results["nullBackdropBodyState"] == "unchanged"
    assert results["nullBackdropInnerHTMLWrites"] == 0

    assert "nullCityResult" not in results
    assert "nullEmailResult" not in results
    assert "nullServiceResult" not in results
    assert "nullWarningResult" not in results
    assert "nullDistanceResult" not in results
    assert "nullActionResult" not in results
    assert "nullAddButtonResult" not in results
    assert "nullBackdropResult" not in results
    assert "nullDialogContentResult" not in results


def test_interpretation_review_ui_module_centralizes_safe_context_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_review_ui_js = static_dir / "interpretation_review_ui.js"

    assert interpretation_review_ui_js.exists()
    interpretation_review_ui_text = interpretation_review_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_review_ui.js"' in app_js
    assert "export function renderInterpretationReviewContextInto" in interpretation_review_ui_text
    assert "renderInterpretationReviewContextInto({" in app_js
    assert "reviewMode," in app_js
    assert "gmailResultEmpty: presentation.drawer.gmailResultEmpty," in app_js

    review_context_start = app_js.index("function renderInterpretationReviewContext")
    details_shell_start = app_js.index("function syncInterpretationReviewDetailsShell", review_context_start)
    review_context_block = app_js[review_context_start:details_shell_start]
    assert "currentInterpretationPresentation(snapshot)" in review_context_block
    assert "interpretationSessionChip(activeSession, workspaceMode)" in review_context_block
    assert "presentation.actions.finalizeGmail" in review_context_block
    assert "innerHTML" not in review_context_block
    assert "escapeHtml" not in review_context_block
    assert "textContent = presentation.drawer.contextTitle" not in review_context_block
    assert "textContent = presentation.drawer.contextCopy" not in review_context_block

    script = r"""
const interpretationReviewUi = await import(__INTERPRETATION_REVIEW_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      toggle(name, force) {
        const key = String(name);
        const shouldAdd = force === undefined ? !classNames.has(key) : Boolean(force);
        if (shouldAdd) {
          classNames.add(key);
        } else {
          classNames.delete(key);
        }
        syncClassList(element, classNames);
        return shouldAdd;
      },
      contains(name) {
        return classNames.has(String(name));
      },
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    if (!node) {
      return;
    }
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function summarize(nodes) {
  return {
    containerClass: nodes.container.className,
    title: nodes.titleNode.textContent,
    copy: nodes.copyNode.textContent,
    chipClass: nodes.chipNode.className,
    chipText: nodes.chipNode.textContent,
    buttonText: nodes.gmailButton.textContent,
    resultClass: nodes.result.className,
    resultText: nodes.result.textContent,
    imgCount: countTag(nodes.container, "img")
      + countTag(nodes.titleNode, "img")
      + countTag(nodes.copyNode, "img")
      + countTag(nodes.chipNode, "img")
      + countTag(nodes.gmailButton, "img")
      + countTag(nodes.result, "img"),
    scriptCount: countTag(nodes.container, "script")
      + countTag(nodes.titleNode, "script")
      + countTag(nodes.copyNode, "script")
      + countTag(nodes.chipNode, "script")
      + countTag(nodes.gmailButton, "script")
      + countTag(nodes.result, "script"),
    innerHTMLWrites: countInnerHtmlWrites(
      nodes.container,
      nodes.titleNode,
      nodes.copyNode,
      nodes.chipNode,
      nodes.gmailButton,
      nodes.result,
    ),
  };
}

function makeNodes({ resultEmpty = true } = {}) {
  const nodes = {
    container: makeElement("article"),
    titleNode: makeElement("h2"),
    copyNode: makeElement("p"),
    chipNode: makeElement("span"),
    gmailButton: makeElement("button"),
    result: makeElement("div"),
  };
  nodes.container.className = "context-card hidden";
  nodes.result.className = resultEmpty ? "result-card empty-state" : "result-card";
  return nodes;
}

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;

const visibleNodes = makeNodes();
interpretationReviewUi.renderInterpretationReviewContextInto(visibleNodes, {
  reviewMode: true,
  title: `Review title ${malicious}`,
  copy: `Review copy ${malicious}`,
  chip: {
    tone: "bad",
    label: `Chip label ${malicious}`,
  },
  finalizeGmailLabel: `Finalize ${malicious}`,
  gmailResultEmpty: `Gmail empty ${malicious}`,
});

const hiddenNodes = makeNodes();
hiddenNodes.titleNode.textContent = "Old title";
hiddenNodes.copyNode.textContent = "Old copy";
hiddenNodes.chipNode.className = "status-chip old";
hiddenNodes.chipNode.textContent = "Old chip";
hiddenNodes.gmailButton.textContent = "Old button";
hiddenNodes.result.textContent = "Old result";
interpretationReviewUi.renderInterpretationReviewContextInto(hiddenNodes, {
  reviewMode: false,
  title: `Hidden title ${malicious}`,
  copy: `Hidden copy ${malicious}`,
  chip: {
    tone: "warn",
    label: `Hidden chip ${malicious}`,
  },
  finalizeGmailLabel: `Hidden button ${malicious}`,
  gmailResultEmpty: `Hidden result ${malicious}`,
});

const nonEmptyResultNodes = makeNodes({ resultEmpty: false });
nonEmptyResultNodes.result.textContent = "Existing rendered result";
interpretationReviewUi.renderInterpretationReviewContextInto(nonEmptyResultNodes, {
  reviewMode: true,
  title: "Visible title",
  copy: "Visible copy",
  chip: {
    tone: "ok",
    label: "Ready",
  },
  finalizeGmailLabel: "Finalize",
  gmailResultEmpty: `Should not replace ${malicious}`,
});

const missingNodesContainer = makeElement("article");
missingNodesContainer.className = "context-card hidden";
const missingResult = makeElement("div");
missingResult.className = "empty-state";
interpretationReviewUi.renderInterpretationReviewContextInto({
  container: missingNodesContainer,
  titleNode: null,
  copyNode: null,
  chipNode: null,
  gmailButton: null,
  result: missingResult,
}, {
  reviewMode: true,
  title: `Ignored title ${malicious}`,
  copy: `Ignored copy ${malicious}`,
  chip: {
    tone: "warn",
    label: `Ignored chip ${malicious}`,
  },
  finalizeGmailLabel: `Ignored button ${malicious}`,
  gmailResultEmpty: `Fallback ${malicious}`,
});

const nullContainerResult = interpretationReviewUi.renderInterpretationReviewContextInto({
  container: null,
  titleNode: makeElement("h2"),
  copyNode: makeElement("p"),
  chipNode: makeElement("span"),
  gmailButton: makeElement("button"),
  result: makeElement("div"),
}, {
  reviewMode: true,
  title: "Ignored",
});

console.log(JSON.stringify({
  exportedType: typeof interpretationReviewUi.renderInterpretationReviewContextInto,
  visible: summarize(visibleNodes),
  hidden: summarize(hiddenNodes),
  nonEmptyResult: summarize(nonEmptyResultNodes),
  missingNodes: {
    containerClass: missingNodesContainer.className,
    resultText: missingResult.textContent,
    innerHTMLWrites: countInnerHtmlWrites(missingNodesContainer, missingResult),
    imgCount: countTag(missingNodesContainer, "img") + countTag(missingResult, "img"),
    scriptCount: countTag(missingNodesContainer, "script") + countTag(missingResult, "script"),
  },
  nullContainerResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REVIEW_UI_MODULE_URL__": "interpretation_review_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["visible"]["containerClass"] == "context-card"
    assert results["visible"]["title"] == "Review title <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["copy"] == "Review copy <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["chipClass"] == "status-chip bad"
    assert results["visible"]["chipText"] == "Chip label <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["buttonText"] == "Finalize <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["resultText"] == "Gmail empty <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["imgCount"] == 0
    assert results["visible"]["scriptCount"] == 0
    assert results["visible"]["innerHTMLWrites"] == 0

    assert results["hidden"]["containerClass"] == "context-card hidden"
    assert results["hidden"]["title"] == "Old title"
    assert results["hidden"]["copy"] == "Old copy"
    assert results["hidden"]["chipClass"] == "status-chip old"
    assert results["hidden"]["chipText"] == "Old chip"
    assert results["hidden"]["buttonText"] == "Old button"
    assert results["hidden"]["resultText"] == "Old result"
    assert results["hidden"]["innerHTMLWrites"] == 0

    assert results["nonEmptyResult"]["containerClass"] == "context-card"
    assert results["nonEmptyResult"]["resultText"] == "Existing rendered result"
    assert results["nonEmptyResult"]["chipClass"] == "status-chip ok"
    assert results["nonEmptyResult"]["innerHTMLWrites"] == 0

    assert results["missingNodes"]["containerClass"] == "context-card"
    assert results["missingNodes"]["resultText"] == "Fallback <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["missingNodes"]["imgCount"] == 0
    assert results["missingNodes"]["scriptCount"] == 0
    assert results["missingNodes"]["innerHTMLWrites"] == 0
    assert "nullContainerResult" not in results


def test_interpretation_review_ui_module_centralizes_safe_details_shell_sync() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_review_ui_js = static_dir / "interpretation_review_ui.js"

    assert interpretation_review_ui_js.exists()
    interpretation_review_ui_text = interpretation_review_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_review_ui.js"' in app_js
    assert "export function syncInterpretationReviewDetailsShellInto" in interpretation_review_ui_text
    assert "syncInterpretationReviewDetailsShellInto(details, summaryNode, {" in app_js
    assert "openSummary: presentation.drawer.detailsSummaryOpen," in app_js
    assert "closedSummary: presentation.drawer.detailsSummaryClosed," in app_js

    details_shell_start = app_js.index("function syncInterpretationReviewDetailsShell")
    completion_start = app_js.index("function renderInterpretationCompletionCard", details_shell_start)
    details_shell_block = app_js[details_shell_start:completion_start]
    assert "currentInterpretationPresentation()" in details_shell_block
    assert "innerHTML" not in details_shell_block
    assert "escapeHtml" not in details_shell_block
    assert "details.open =" not in details_shell_block
    assert "dataset.autocollapsed" not in details_shell_block
    assert "summaryNode.textContent" not in details_shell_block

    script = r"""
const interpretationReviewUi = await import(__INTERPRETATION_REVIEW_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    children: [],
    parentNode: null,
    dataset: {},
    open: false,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    if (!node) {
      return;
    }
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function summarize(details, summaryNode = null) {
  return {
    open: details.open,
    autocollapsed: details.dataset.autocollapsed || "",
    hasAutocollapsed: Object.prototype.hasOwnProperty.call(details.dataset, "autocollapsed"),
    summary: summaryNode ? summaryNode.textContent : "",
    imgCount: countTag(details, "img") + (summaryNode ? countTag(summaryNode, "img") : 0),
    scriptCount: countTag(details, "script") + (summaryNode ? countTag(summaryNode, "script") : 0),
    innerHTMLWrites: countInnerHtmlWrites(details, summaryNode),
  };
}

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;

const incompleteDetails = makeElement("details");
incompleteDetails.open = false;
incompleteDetails.dataset.autocollapsed = "done";
const incompleteSummary = makeElement("summary");
interpretationReviewUi.syncInterpretationReviewDetailsShellInto(
  incompleteDetails,
  incompleteSummary,
  {
    completed: false,
    openSummary: `Open ${malicious}`,
    closedSummary: `Closed ${malicious}`,
  },
);

const completedDetails = makeElement("details");
completedDetails.open = true;
const completedSummary = makeElement("summary");
interpretationReviewUi.syncInterpretationReviewDetailsShellInto(
  completedDetails,
  completedSummary,
  {
    completed: true,
    openSummary: `Open ${malicious}`,
    closedSummary: `Closed ${malicious}`,
  },
);

const alreadyAutocollapsedDetails = makeElement("details");
alreadyAutocollapsedDetails.open = true;
alreadyAutocollapsedDetails.dataset.autocollapsed = "done";
const alreadyAutocollapsedSummary = makeElement("summary");
interpretationReviewUi.syncInterpretationReviewDetailsShellInto(
  alreadyAutocollapsedDetails,
  alreadyAutocollapsedSummary,
  {
    completed: true,
    openSummary: "Open again",
    closedSummary: `Closed again ${malicious}`,
  },
);

const missingSummaryDetails = makeElement("details");
missingSummaryDetails.open = true;
interpretationReviewUi.syncInterpretationReviewDetailsShellInto(
  missingSummaryDetails,
  null,
  {
    completed: true,
    openSummary: `Ignored open ${malicious}`,
    closedSummary: `Ignored closed ${malicious}`,
  },
);

const nullDetailsSummary = makeElement("summary");
const nullDetailsResult = interpretationReviewUi.syncInterpretationReviewDetailsShellInto(
  null,
  nullDetailsSummary,
  {
    completed: false,
    openSummary: `Null open ${malicious}`,
    closedSummary: `Null closed ${malicious}`,
  },
);

console.log(JSON.stringify({
  exportedType: typeof interpretationReviewUi.syncInterpretationReviewDetailsShellInto,
  incomplete: summarize(incompleteDetails, incompleteSummary),
  completed: summarize(completedDetails, completedSummary),
  alreadyAutocollapsed: summarize(alreadyAutocollapsedDetails, alreadyAutocollapsedSummary),
  missingSummary: summarize(missingSummaryDetails),
  nullDetailsSummaryText: nullDetailsSummary.textContent,
  nullDetailsInnerHTMLWrites: countInnerHtmlWrites(nullDetailsSummary),
  nullDetailsResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REVIEW_UI_MODULE_URL__": "interpretation_review_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["incomplete"]["open"] is True
    assert results["incomplete"]["hasAutocollapsed"] is False
    assert results["incomplete"]["summary"] == "Open <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["incomplete"]["imgCount"] == 0
    assert results["incomplete"]["scriptCount"] == 0
    assert results["incomplete"]["innerHTMLWrites"] == 0

    assert results["completed"]["open"] is False
    assert results["completed"]["autocollapsed"] == "done"
    assert results["completed"]["summary"] == "Closed <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["completed"]["imgCount"] == 0
    assert results["completed"]["scriptCount"] == 0
    assert results["completed"]["innerHTMLWrites"] == 0

    assert results["alreadyAutocollapsed"]["open"] is True
    assert results["alreadyAutocollapsed"]["autocollapsed"] == "done"
    assert results["alreadyAutocollapsed"]["summary"] == "Closed again <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["alreadyAutocollapsed"]["innerHTMLWrites"] == 0

    assert results["missingSummary"]["open"] is False
    assert results["missingSummary"]["autocollapsed"] == "done"
    assert results["missingSummary"]["innerHTMLWrites"] == 0
    assert results["nullDetailsSummaryText"] == ""
    assert results["nullDetailsInnerHTMLWrites"] == 0
    assert "nullDetailsResult" not in results


def test_interpretation_review_ui_module_centralizes_safe_disclosure_section_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_review_ui_js = static_dir / "interpretation_review_ui.js"

    assert interpretation_review_ui_js.exists()
    interpretation_review_ui_text = interpretation_review_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_review_ui.js"' in app_js
    assert "export function renderInterpretationDisclosureSectionsInto" in interpretation_review_ui_text
    assert "renderInterpretationDisclosureSectionsInto({" in app_js
    assert "function setDisclosureState" not in app_js

    disclosure_start = app_js.index("function syncInterpretationDisclosureState")
    next_function_start = app_js.index("function interpretationActiveSession", disclosure_start)
    disclosure_block = app_js[disclosure_start:next_function_start]
    assert "deriveInterpretationDrawerLayout" in disclosure_block
    assert "deriveInterpretationDisclosurePresentation" in disclosure_block
    assert "innerHTML" not in disclosure_block
    assert "escapeHtml" not in disclosure_block
    assert "setDisclosureState(" not in disclosure_block
    assert ".open =" not in disclosure_block
    assert ".textContent =" not in disclosure_block

    script = r"""
const interpretationReviewUi = await import(__INTERPRETATION_REVIEW_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    children: [],
    parentNode: null,
    open: false,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    if (!node) {
      return;
    }
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function makeSection() {
  return {
    details: makeElement("details"),
    summary: makeElement("summary"),
  };
}

function summarize(section) {
  return {
    open: section.details.open,
    summary: section.summary.textContent,
    imgCount: countTag(section.details, "img") + countTag(section.summary, "img"),
    scriptCount: countTag(section.details, "script") + countTag(section.summary, "script"),
    innerHTMLWrites: countInnerHtmlWrites(section.details, section.summary),
  };
}

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const service = makeSection();
const text = makeSection();
const recipient = makeSection();
const amounts = makeSection();
const nodes = {
  serviceDetails: service.details,
  serviceSummary: service.summary,
  textDetails: text.details,
  textSummary: text.summary,
  recipientDetails: recipient.details,
  recipientSummary: recipient.summary,
  amountsDetails: amounts.details,
  amountsSummary: amounts.summary,
};

interpretationReviewUi.renderInterpretationDisclosureSectionsInto(nodes, {
  serviceOpen: true,
  serviceSummary: `Service ${malicious}`,
  textOpen: false,
  textSummary: `Text ${malicious}`,
  recipientOpen: true,
  recipientSummary: `Recipient ${malicious}`,
  amountsOpen: false,
  amountsSummary: `Amounts ${malicious}`,
});

const missingSummary = makeElement("summary");
const missingDetails = makeElement("details");
missingDetails.open = true;
const missingResult = interpretationReviewUi.renderInterpretationDisclosureSectionsInto({
  serviceDetails: null,
  serviceSummary: missingSummary,
  textDetails: missingDetails,
  textSummary: null,
  recipientDetails: null,
  recipientSummary: null,
  amountsDetails: null,
  amountsSummary: null,
}, {
  serviceOpen: true,
  serviceSummary: `Missing service ${malicious}`,
  textOpen: false,
  textSummary: `Missing text ${malicious}`,
});

const nullNodesResult = interpretationReviewUi.renderInterpretationDisclosureSectionsInto(null, {
  serviceOpen: true,
  serviceSummary: `Null service ${malicious}`,
});

console.log(JSON.stringify({
  exportedType: typeof interpretationReviewUi.renderInterpretationDisclosureSectionsInto,
  service: summarize(service),
  text: summarize(text),
  recipient: summarize(recipient),
  amounts: summarize(amounts),
  missingSummaryText: missingSummary.textContent,
  missingDetailsOpen: missingDetails.open,
  missingInnerHTMLWrites: countInnerHtmlWrites(missingSummary, missingDetails),
  missingResult,
  nullNodesResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REVIEW_UI_MODULE_URL__": "interpretation_review_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["service"] == {
        "open": True,
        "summary": "Service <img src=x onerror=alert(1)><script>bad()</script>",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["text"] == {
        "open": False,
        "summary": "Text <img src=x onerror=alert(1)><script>bad()</script>",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["recipient"] == {
        "open": True,
        "summary": "Recipient <img src=x onerror=alert(1)><script>bad()</script>",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["amounts"] == {
        "open": False,
        "summary": "Amounts <img src=x onerror=alert(1)><script>bad()</script>",
        "imgCount": 0,
        "scriptCount": 0,
        "innerHTMLWrites": 0,
    }
    assert results["missingSummaryText"] == "Missing service <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["missingDetailsOpen"] is False
    assert results["missingInnerHTMLWrites"] == 0
    assert "missingResult" not in results
    assert "nullNodesResult" not in results


def test_interpretation_review_ui_module_centralizes_safe_drawer_state_sync() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_review_ui_js = static_dir / "interpretation_review_ui.js"

    assert interpretation_review_ui_js.exists()
    interpretation_review_ui_text = interpretation_review_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_review_ui.js"' in app_js
    assert "export function syncInterpretationReviewDrawerStateInto" in interpretation_review_ui_text
    assert "syncInterpretationReviewDrawerStateInto(backdrop, document.body, interpretationUiState.reviewDrawerOpen);" in app_js

    drawer_state_start = app_js.index("function setInterpretationReviewDrawerOpen")
    drawer_open_export_start = app_js.index("export function openInterpretationReviewDrawer", drawer_state_start)
    drawer_state_block = app_js[drawer_state_start:drawer_open_export_start]
    assert "interpretationUiState.reviewDrawerOpen = Boolean(open)" in drawer_state_block
    assert "notifyInterpretationUiStateChanged()" in drawer_state_block
    assert "innerHTML" not in drawer_state_block
    assert "escapeHtml" not in drawer_state_block
    assert "backdrop.classList.toggle" not in drawer_state_block
    assert "backdrop.setAttribute(\"aria-hidden\"" not in drawer_state_block
    assert "document.body.dataset.interpretationReviewDrawer" not in drawer_state_block

    script = r"""
const interpretationReviewUi = await import(__INTERPRETATION_REVIEW_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    attributes: {},
    dataset: {},
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      toggle(name, force) {
        const key = String(name);
        const shouldAdd = force === undefined ? !classNames.has(key) : Boolean(force);
        if (shouldAdd) {
          classNames.add(key);
        } else {
          classNames.delete(key);
        }
        syncClassList(element, classNames);
        return shouldAdd;
      },
      contains(name) {
        return classNames.has(String(name));
      },
    },
    setAttribute(name, value) {
      this.attributes[String(name)] = String(value ?? "");
    },
    getAttribute(name) {
      return this.attributes[String(name)] ?? null;
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    if (!node) {
      return;
    }
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function summarize(backdrop, body = null) {
  return {
    className: backdrop.className,
    ariaHidden: backdrop.getAttribute("aria-hidden"),
    bodyState: body?.dataset?.interpretationReviewDrawer || "",
    innerHTMLWrites: countInnerHtmlWrites(backdrop, body),
  };
}

const openBackdrop = makeElement("div");
openBackdrop.classList.add("hidden");
const openBody = makeElement("body");
interpretationReviewUi.syncInterpretationReviewDrawerStateInto(openBackdrop, openBody, true);

const closedBackdrop = makeElement("div");
const closedBody = makeElement("body");
closedBody.dataset.interpretationReviewDrawer = "open";
interpretationReviewUi.syncInterpretationReviewDrawerStateInto(closedBackdrop, closedBody, false);

const truthyBackdrop = makeElement("div");
const truthyBody = makeElement("body");
interpretationReviewUi.syncInterpretationReviewDrawerStateInto(truthyBackdrop, truthyBody, "yes");

const missingBodyBackdrop = makeElement("div");
interpretationReviewUi.syncInterpretationReviewDrawerStateInto(missingBodyBackdrop, null, false);

const nullBackdropBody = makeElement("body");
nullBackdropBody.dataset.interpretationReviewDrawer = "unchanged";
const nullBackdropResult = interpretationReviewUi.syncInterpretationReviewDrawerStateInto(null, nullBackdropBody, true);

console.log(JSON.stringify({
  exportedType: typeof interpretationReviewUi.syncInterpretationReviewDrawerStateInto,
  open: summarize(openBackdrop, openBody),
  closed: summarize(closedBackdrop, closedBody),
  truthy: summarize(truthyBackdrop, truthyBody),
  missingBody: summarize(missingBodyBackdrop),
  nullBackdropBodyState: nullBackdropBody.dataset.interpretationReviewDrawer,
  nullBackdropInnerHTMLWrites: countInnerHtmlWrites(nullBackdropBody),
  nullBackdropResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REVIEW_UI_MODULE_URL__": "interpretation_review_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["open"]["className"] == ""
    assert results["open"]["ariaHidden"] == "false"
    assert results["open"]["bodyState"] == "open"
    assert results["open"]["innerHTMLWrites"] == 0

    assert results["closed"]["className"] == "hidden"
    assert results["closed"]["ariaHidden"] == "true"
    assert results["closed"]["bodyState"] == "closed"
    assert results["closed"]["innerHTMLWrites"] == 0

    assert results["truthy"]["className"] == ""
    assert results["truthy"]["ariaHidden"] == "false"
    assert results["truthy"]["bodyState"] == "open"
    assert results["truthy"]["innerHTMLWrites"] == 0

    assert results["missingBody"]["className"] == "hidden"
    assert results["missingBody"]["ariaHidden"] == "true"
    assert results["missingBody"]["bodyState"] == ""
    assert results["missingBody"]["innerHTMLWrites"] == 0

    assert results["nullBackdropBodyState"] == "unchanged"
    assert results["nullBackdropInnerHTMLWrites"] == 0
    assert "nullBackdropResult" not in results


def test_interpretation_review_ui_module_centralizes_safe_surface_chrome_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_review_ui_js = static_dir / "interpretation_review_ui.js"

    assert interpretation_review_ui_js.exists()
    interpretation_review_ui_text = interpretation_review_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_review_ui.js"' in app_js
    assert "export function renderInterpretationReviewSurfaceInto" in interpretation_review_ui_text
    assert "renderInterpretationReviewSurfaceInto({" in app_js
    assert "actions: drawerLayout.actions," in app_js
    assert "resetGmailResult: !hasGmailInterpretationSession," in app_js

    review_surface_start = app_js.index("function syncInterpretationReviewSurface")
    focus_field_start = app_js.index("function focusInterpretationField", review_surface_start)
    review_surface_block = app_js[review_surface_start:focus_field_start]
    assert "deriveInterpretationDrawerLayout" in review_surface_block
    assert "renderInterpretationSessionShell(snapshot)" in review_surface_block
    assert "renderInterpretationReviewContext(snapshot)" in review_surface_block
    assert "renderInterpretationReviewSurfaceInto({" in review_surface_block
    assert "innerHTML" not in review_surface_block
    assert "escapeHtml" not in review_surface_block
    assert "button.textContent = presentation.actions.openReview" not in review_surface_block
    assert "drawerTitle.textContent = presentation.drawer.title" not in review_surface_block
    assert "gmailButton.classList.toggle" not in review_surface_block
    assert "gmailResult.textContent = presentation.drawer.gmailResultEmpty" not in review_surface_block
    assert "statusNode.textContent = presentation.drawer.status" not in review_surface_block

    script = r"""
const interpretationReviewUi = await import(__INTERPRETATION_REVIEW_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      toggle(name, force) {
        const key = String(name);
        const shouldAdd = force === undefined ? !classNames.has(key) : Boolean(force);
        if (shouldAdd) {
          classNames.add(key);
        } else {
          classNames.delete(key);
        }
        syncClassList(element, classNames);
        return shouldAdd;
      },
      contains(name) {
        return classNames.has(String(name));
      },
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function makeSurfaceNodes() {
  return {
    openButton: makeElement("button"),
    drawerTitle: makeElement("h2"),
    clearButton: makeElement("button"),
    clearTopButton: makeElement("button"),
    reloadHistoryButton: makeElement("button"),
    saveButton: makeElement("button"),
    exportButton: makeElement("button"),
    gmailButton: makeElement("button"),
    closeFooterButton: makeElement("button"),
    gmailResult: makeElement("div"),
    statusNode: makeElement("p"),
  };
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(...nodes) {
  let total = 0;
  nodes.forEach((node) => {
    if (!node) {
      return;
    }
    walk(node, (current) => {
      total += (current.innerHTMLAssignments || []).length;
    });
  });
  return total;
}

function summarize(nodes) {
  const allNodes = Object.values(nodes).filter(Boolean);
  return {
    openText: nodes.openButton?.textContent || "",
    drawerTitle: nodes.drawerTitle?.textContent || "",
    clearText: nodes.clearButton?.textContent || "",
    clearTopText: nodes.clearTopButton?.textContent || "",
    reloadText: nodes.reloadHistoryButton?.textContent || "",
    saveText: nodes.saveButton?.textContent || "",
    exportText: nodes.exportButton?.textContent || "",
    gmailText: nodes.gmailButton?.textContent || "",
    statusText: nodes.statusNode?.textContent || "",
    gmailButtonClass: nodes.gmailButton?.className || "",
    saveButtonClass: nodes.saveButton?.className || "",
    exportButtonClass: nodes.exportButton?.className || "",
    clearButtonClass: nodes.clearButton?.className || "",
    closeFooterClass: nodes.closeFooterButton?.className || "",
    gmailResultClass: nodes.gmailResult?.className || "",
    gmailResultText: nodes.gmailResult?.textContent || "",
    imgCount: allNodes.reduce((total, node) => total + countTag(node, "img"), 0),
    scriptCount: allNodes.reduce((total, node) => total + countTag(node, "script"), 0),
    innerHTMLWrites: countInnerHtmlWrites(...allNodes),
  };
}

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;

const visibleNodes = makeSurfaceNodes();
interpretationReviewUi.renderInterpretationReviewSurfaceInto(visibleNodes, {
  labels: {
    openReview: `Open ${malicious}`,
    drawerTitle: `Drawer ${malicious}`,
    startBlank: `Blank ${malicious}`,
    refreshHistory: `Reload ${malicious}`,
    saveRow: `Save ${malicious}`,
    export: `Export ${malicious}`,
    finalizeGmail: `Finalize ${malicious}`,
    status: `Status ${malicious}`,
  },
  actions: {
    showFinalizeGmail: false,
    showSaveRow: true,
    showGenerateDocxPdf: false,
    showNewBlank: true,
    showFooterClose: false,
  },
  resetGmailResult: true,
  gmailResultEmpty: `Empty ${malicious}`,
});

const preservedNodes = makeSurfaceNodes();
preservedNodes.gmailResult.classList.add("existing");
preservedNodes.gmailResult.textContent = "Existing Gmail result";
interpretationReviewUi.renderInterpretationReviewSurfaceInto(preservedNodes, {
  labels: {
    openReview: "Open",
    drawerTitle: "Drawer",
    startBlank: "Blank",
    refreshHistory: "Reload",
    saveRow: "Save",
    export: "Export",
    finalizeGmail: "Finalize",
    status: "Status",
  },
  actions: {
    showFinalizeGmail: true,
    showSaveRow: false,
    showGenerateDocxPdf: true,
    showNewBlank: false,
    showFooterClose: true,
  },
  resetGmailResult: false,
  gmailResultEmpty: `Should not replace ${malicious}`,
});

const missingNodesGmailResult = makeElement("div");
interpretationReviewUi.renderInterpretationReviewSurfaceInto({
  gmailResult: missingNodesGmailResult,
}, {
  resetGmailResult: true,
  gmailResultEmpty: `Missing ${malicious}`,
});

const nullNodesResult = interpretationReviewUi.renderInterpretationReviewSurfaceInto(null, {
  labels: { openReview: `Null ${malicious}` },
});

console.log(JSON.stringify({
  exportedType: typeof interpretationReviewUi.renderInterpretationReviewSurfaceInto,
  visible: summarize(visibleNodes),
  preserved: summarize(preservedNodes),
  missingNodes: {
    gmailResultClass: missingNodesGmailResult.className,
    gmailResultText: missingNodesGmailResult.textContent,
    imgCount: countTag(missingNodesGmailResult, "img"),
    scriptCount: countTag(missingNodesGmailResult, "script"),
    innerHTMLWrites: countInnerHtmlWrites(missingNodesGmailResult),
  },
  nullNodesResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_REVIEW_UI_MODULE_URL__": "interpretation_review_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedType"] == "function"
    assert results["visible"]["openText"] == "Open <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["drawerTitle"] == "Drawer <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["clearText"] == "Blank <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["clearTopText"] == "Blank <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["reloadText"] == "Reload <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["saveText"] == "Save <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["exportText"] == "Export <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["gmailText"] == "Finalize <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["statusText"] == "Status <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["gmailButtonClass"] == "hidden"
    assert results["visible"]["saveButtonClass"] == ""
    assert results["visible"]["exportButtonClass"] == "hidden"
    assert results["visible"]["clearButtonClass"] == ""
    assert results["visible"]["closeFooterClass"] == "hidden"
    assert results["visible"]["gmailResultClass"] == "empty-state"
    assert results["visible"]["gmailResultText"] == "Empty <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["visible"]["imgCount"] == 0
    assert results["visible"]["scriptCount"] == 0
    assert results["visible"]["innerHTMLWrites"] == 0

    assert results["preserved"]["gmailButtonClass"] == ""
    assert results["preserved"]["saveButtonClass"] == "hidden"
    assert results["preserved"]["exportButtonClass"] == ""
    assert results["preserved"]["clearButtonClass"] == "hidden"
    assert results["preserved"]["closeFooterClass"] == ""
    assert results["preserved"]["gmailResultClass"] == "existing"
    assert results["preserved"]["gmailResultText"] == "Existing Gmail result"
    assert results["preserved"]["innerHTMLWrites"] == 0

    assert results["missingNodes"]["gmailResultClass"] == "empty-state"
    assert results["missingNodes"]["gmailResultText"] == "Missing <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["missingNodes"]["imgCount"] == 0
    assert results["missingNodes"]["scriptCount"] == 0
    assert results["missingNodes"]["innerHTMLWrites"] == 0
    assert "nullNodesResult" not in results


def test_interpretation_result_ui_module_centralizes_safe_interpretation_result_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    interpretation_result_ui_js = static_dir / "interpretation_result_ui.js"

    assert interpretation_result_ui_js.exists()
    interpretation_result_ui_text = interpretation_result_ui_js.read_text(encoding="utf-8")
    assert 'from "./interpretation_result_ui.js"' in app_js
    assert "export function renderInterpretationExportResultInto" in interpretation_result_ui_text
    assert "export function renderInterpretationGmailResultInto" in interpretation_result_ui_text
    assert "export function renderInterpretationCompletionCardInto" in interpretation_result_ui_text
    assert "export function renderInterpretationSessionCardInto" in interpretation_result_ui_text
    assert "export function renderInterpretationSeedCardInto" in interpretation_result_ui_text
    assert "export function renderInterpretationReviewSummaryCardInto" in interpretation_result_ui_text
    assert "export function renderInterpretationLocationGuardInto" in interpretation_result_ui_text
    assert "export function resetInterpretationExportResultInto" in interpretation_result_ui_text
    assert "renderInterpretationExportResultInto(container, payload, currentInterpretationPresentation());" in app_js
    assert "renderInterpretationGmailResultInto(container, payload, currentInterpretationPresentation());" in app_js
    assert "renderInterpretationCompletionCardInto(container, {" in app_js
    assert "renderInterpretationSessionCardInto(result, {" in app_js
    assert "renderInterpretationSeedCardInto(container, {" in app_js
    assert "renderInterpretationReviewSummaryCardInto(container, {" in app_js
    assert "renderInterpretationLocationGuardInto(card, { message, tone });" in app_js
    assert "resetInterpretationExportResultInto(panel, result, presentation.export.emptyState);" in app_js
    assert 'qs("interpretation-review-export-panel")?.classList.remove("hidden");' in app_js
    session_start = app_js.index("function renderInterpretationSessionShell")
    seed_start = app_js.index("function renderInterpretationSeedCard", session_start)
    session_block = app_js[session_start:seed_start]
    assert 'result.classList.remove("empty-state");' in session_block
    assert "presentation.home.resultTitle" in session_block
    assert "interpretationLocationSummary(snapshot)" in session_block
    assert "innerHTML" not in session_block
    assert "escapeHtml" not in session_block
    review_summary_start = app_js.index("function renderInterpretationReviewSummary", seed_start)
    seed_block = app_js[seed_start:review_summary_start]
    assert 'container.classList.add("empty-state");' in seed_block
    assert 'container.classList.remove("empty-state");' in seed_block
    assert "presentation.reviewHome.emptyState" in seed_block
    assert "hasInterpretationReviewData(snapshot)" in seed_block
    assert "innerHTML" not in seed_block
    assert "escapeHtml" not in seed_block
    review_context_start = app_js.index("function renderInterpretationReviewContext", review_summary_start)
    review_summary_block = app_js[review_summary_start:review_context_start]
    assert 'container.classList.add("empty-state");' in review_summary_block
    assert 'container.classList.remove("empty-state");' in review_summary_block
    assert "presentation.drawer.summaryEmpty" in review_summary_block
    assert "interpretationLocationSummary(snapshot)" in review_summary_block
    assert "innerHTML" not in review_summary_block
    assert "escapeHtml" not in review_summary_block
    gmail_start = app_js.index("export function renderInterpretationGmailResult")
    dashboard_start = app_js.index("function renderDashboard", gmail_start)
    gmail_block = app_js[gmail_start:dashboard_start]
    assert "interpretationUiState.completionPayload = payload;" in gmail_block
    assert "openInterpretationReviewDrawer();" in gmail_block
    assert "syncInterpretationReviewSurface();" in gmail_block
    assert "notifyInterpretationUiStateChanged();" in gmail_block
    assert "innerHTML" not in gmail_block
    assert "escapeHtml" not in gmail_block
    assert 'appendResultGridItem(grid, "Reply status"' not in gmail_block
    completion_start = app_js.index("function renderInterpretationCompletionCard")
    warning_start = app_js.index("function setInterpretationFieldWarning", completion_start)
    completion_block = app_js[completion_start:warning_start]
    assert 'container.classList.toggle("hidden", !completed);' in completion_block
    assert "syncInterpretationReviewDetailsShell(completed);" in completion_block
    assert "interpretationCaseLocation(snapshot)" in completion_block
    assert "interpretationServiceLocation(snapshot)" in completion_block
    assert "innerHTML" not in completion_block
    assert "escapeHtml" not in completion_block
    guard_start = app_js.index("function setInterpretationLocationGuard", warning_start)
    reference_start = app_js.index("function applyInterpretationCityValue", guard_start)
    guard_block = app_js[guard_start:reference_start]
    assert 'const message = String(rawMessage || "").trim();' in guard_block
    assert "renderInterpretationLocationGuardInto(card, { message, tone });" in guard_block
    assert "innerHTML" not in guard_block
    assert "escapeHtml" not in guard_block
    export_reset_start = app_js.index("function resetInterpretationExportResult")
    drawer_open_start = app_js.index("function setInterpretationReviewDrawerOpen", export_reset_start)
    export_reset_block = app_js[export_reset_start:drawer_open_start]
    assert "interpretationUiState.completionPayload = null;" in export_reset_block
    assert "notifyInterpretationUiStateChanged();" in export_reset_block
    assert "resetInterpretationExportResultInto(panel, result, presentation.export.emptyState);" in export_reset_block
    assert "classList.add" not in export_reset_block
    assert "textContent" not in export_reset_block
    assert "innerHTML" not in export_reset_block
    assert 'appendResultGridItem(grid, "DOCX"' not in app_js
    assert 'appendResultGridItem(grid, "PDF Export"' not in app_js

    script = r"""
const interpretationResultUi = await import(__INTERPRETATION_RESULT_UI_MODULE_URL__);

function syncClassList(element, classes) {
  element.className = Array.from(classes).join(" ");
}

function makeElement(tagName = "div") {
  const classNames = new Set();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    _className: "",
    children: [],
    parentNode: null,
    title: "",
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    classList: {
      add(...names) {
        names.forEach((name) => {
          if (name) {
            classNames.add(String(name));
          }
        });
        syncClassList(element, classNames);
      },
      remove(...names) {
        names.forEach((name) => classNames.delete(String(name)));
        syncClassList(element, classNames);
      },
      contains(name) {
        return classNames.has(String(name));
      },
    },
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
  };
  Object.defineProperty(element, "className", {
    get() {
      return this._className;
    },
    set(value) {
      this._className = String(value ?? "");
      classNames.clear();
      this._className.split(/\s+/).filter(Boolean).forEach((name) => classNames.add(name));
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function collectClasses(node) {
  const classes = [];
  walk(node, (current) => {
    if (String(current.className || "").trim()) {
      classes.push(current.className);
    }
  });
  return classes;
}

function summarize(container) {
  const grid = container.children[1];
  return {
    className: container.className,
    text: container.textContent,
    childClasses: container.children.map((child) => child.className || ""),
    gridLabels: grid.children.map((child) => child.children[0]?.textContent || ""),
    gridValues: grid.children.map((child) => child.children[1]?.textContent || ""),
    classes: collectClasses(container),
    imgCount: countTag(container, "img"),
    scriptCount: countTag(container, "script"),
    innerHTMLWrites: countInnerHtmlWrites(container),
  };
}

function summarizeGuard(container) {
  return {
    className: container.className,
    text: container.textContent,
    childClasses: container.children.map((child) => child.className || ""),
    classes: collectClasses(container),
    imgCount: countTag(container, "img"),
    scriptCount: countTag(container, "script"),
    innerHTMLWrites: countInnerHtmlWrites(container),
  };
}

function summarizeReset(panel, result) {
  return {
    panelClassName: panel.className,
    panelHidden: panel.classList.contains("hidden"),
    resultClassName: result.className,
    resultText: result.textContent,
    resultChildCount: result.children.length,
    imgCount: countTag(result, "img"),
    scriptCount: countTag(result, "script"),
    panelInnerHTMLWrites: countInnerHtmlWrites(panel),
    resultInnerHTMLWrites: countInnerHtmlWrites(result),
  };
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const presentation = {
  export: {
    readyLabel: `Ready ${malicious}`,
    localOnlyLabel: `Local only ${malicious}`,
    failedLabel: `Failed ${malicious}`,
    readyTitle: `Ready title ${malicious}`,
    localOnlyTitle: `Local title ${malicious}`,
    failedTitle: `Failed title ${malicious}`,
    pdfReadyLabel: `PDF ready ${malicious}`,
  },
  drawer: {
    gmailResultEmpty: `No Gmail result ${malicious}`,
  },
  gmailResult: {
    createdTitle: `Gmail reply created ${malicious}`,
    localOnlyTitle: `Local-only Gmail reply ${malicious}`,
    warningTitle: `Gmail reply needs attention ${malicious}`,
    createdLabel: `Created ${malicious}`,
    localOnlyLabel: `Local only ${malicious}`,
    warningLabel: `Needs attention ${malicious}`,
  },
};
const okContainer = document.createElement("div");
okContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationExportResultInto(okContainer, {
  status: "ok",
  normalized_payload: {
    docx_path: `C:/cases/result ${malicious}.docx`,
    pdf_path: `C:/cases/result ${malicious}.pdf`,
  },
  diagnostics: {
    pdf_export: {
      ok: true,
      failure_message: `Ignored ${malicious}`,
    },
  },
}, presentation);

const localOnlyContainer = document.createElement("div");
localOnlyContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationExportResultInto(localOnlyContainer, {
  status: "local_only",
  normalized_payload: {},
  diagnostics: {
    pdf_export: {
      ok: false,
      failure_message: `PDF failure ${malicious}`,
    },
  },
}, presentation);

const failedContainer = document.createElement("div");
failedContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationExportResultInto(failedContainer, {
  status: "error",
  diagnostics: {
    pdf_export: {
      ok: false,
    },
  },
}, presentation);

const gmailOkContainer = document.createElement("div");
gmailOkContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationGmailResultInto(gmailOkContainer, {
  status: "ok",
  normalized_payload: {
    docx_path: `C:/cases/gmail ${malicious}.docx`,
    pdf_path: `C:/cases/gmail ${malicious}.pdf`,
    gmail_draft_result: {
      message: `Draft ready ${malicious}`,
    },
  },
}, presentation);

const gmailLocalOnlyContainer = document.createElement("div");
gmailLocalOnlyContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationGmailResultInto(gmailLocalOnlyContainer, {
  status: "local_only",
  normalized_payload: {
    draft_prereqs: {
      message: `Draft prerequisites ${malicious}`,
    },
  },
}, presentation);

const gmailWarningContainer = document.createElement("div");
gmailWarningContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationGmailResultInto(gmailWarningContainer, {
  status: "warning",
  normalized_payload: {
    pdf_path: `C:/cases/fallback ${malicious}.pdf`,
  },
}, presentation);

const gmailEmptyContainer = document.createElement("div");
gmailEmptyContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationGmailResultInto(gmailEmptyContainer, {
  status: "error",
  normalized_payload: {},
}, presentation);
const nullContainerResult = interpretationResultUi.renderInterpretationGmailResultInto(null, {
  status: "ok",
  normalized_payload: {},
}, presentation);

const completionContainer = document.createElement("div");
completionContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationCompletionCardInto(completionContainer, {
  title: `Completion title ${malicious}`,
  message: `Completion message ${malicious}`,
  chip: {
    tone: "warn",
    label: `Completion label ${malicious}`,
  },
  docxPath: `C:/cases/completion ${malicious}.docx`,
  pdfPath: `C:/cases/completion ${malicious}.pdf`,
  caseLocation: `Case ${malicious}`,
  serviceLocation: `Service ${malicious}`,
});

const completionFallbackContainer = document.createElement("div");
completionFallbackContainer.className = "result-card empty-state";
interpretationResultUi.renderInterpretationCompletionCardInto(completionFallbackContainer, {
  title: `Fallback title ${malicious}`,
  message: "",
  chip: {
    tone: "bad",
    label: `Fallback label ${malicious}`,
  },
  docxPath: "",
  pdfPath: "",
  caseLocation: `Fallback case ${malicious}`,
  serviceLocation: `Fallback service ${malicious}`,
});
const nullCompletionResult = interpretationResultUi.renderInterpretationCompletionCardInto(null, {
  title: "Ignored",
});

const sessionContainer = document.createElement("div");
sessionContainer.className = "result-card";
interpretationResultUi.renderInterpretationSessionCardInto(sessionContainer, {
  title: `Session title ${malicious}`,
  message: `Notice ${malicious}.pdf`,
  chip: {
    tone: "ok",
    label: `Session label ${malicious}`,
  },
  caseNumber: `Case number ${malicious}`,
  courtEmail: `court-${malicious}@example.test`,
  serviceDate: `2026-05-01 ${malicious}`,
  location: `Location ${malicious}`,
});

const sessionFallbackContainer = document.createElement("div");
sessionFallbackContainer.className = "result-card";
interpretationResultUi.renderInterpretationSessionCardInto(sessionFallbackContainer, {
  title: `Session fallback ${malicious}`,
  message: "",
  chip: {
    tone: "info",
    label: `Session fallback label ${malicious}`,
  },
  caseNumber: "",
  courtEmail: "",
  serviceDate: "",
  location: "",
});

const seedContainer = document.createElement("div");
seedContainer.className = "result-card";
interpretationResultUi.renderInterpretationSeedCardInto(seedContainer, {
  title: `Seed title ${malicious}`,
  message: `Seed message ${malicious}`,
  chip: {
    tone: "info",
    label: `Seed label ${malicious}`,
  },
  caseValue: `Seed case ${malicious}`,
  courtEmail: `seed-${malicious}@example.test`,
  serviceDate: `2026-05-02 ${malicious}`,
  location: `Seed location ${malicious}`,
});

const seedFallbackContainer = document.createElement("div");
seedFallbackContainer.className = "result-card";
interpretationResultUi.renderInterpretationSeedCardInto(seedFallbackContainer, {
  title: `Seed fallback ${malicious}`,
  message: "",
  chip: {
    tone: "ok",
    label: `Seed fallback label ${malicious}`,
  },
  caseValue: "",
  courtEmail: "",
  serviceDate: "",
  location: "",
});

const reviewSummaryContainer = document.createElement("div");
reviewSummaryContainer.className = "result-card";
interpretationResultUi.renderInterpretationReviewSummaryCardInto(reviewSummaryContainer, {
  title: `Review title ${malicious}`,
  message: `Review subtitle ${malicious}`,
  chip: {
    tone: "warn",
    label: `Review label ${malicious}`,
  },
  caseNumber: `Review case ${malicious}`,
  courtEmail: `review-${malicious}@example.test`,
  serviceDate: `2026-05-03 ${malicious}`,
  location: `Review location ${malicious}`,
});

const reviewSummaryFallbackContainer = document.createElement("div");
reviewSummaryFallbackContainer.className = "result-card";
interpretationResultUi.renderInterpretationReviewSummaryCardInto(reviewSummaryFallbackContainer, {
  title: `Review fallback ${malicious}`,
  message: "",
  chip: {
    tone: "bad",
    label: `Review fallback label ${malicious}`,
  },
  caseNumber: "",
  courtEmail: "",
  serviceDate: "",
  location: "",
});
const nullSessionResult = interpretationResultUi.renderInterpretationSessionCardInto(null, {});
const nullSeedResult = interpretationResultUi.renderInterpretationSeedCardInto(null, {});
const nullReviewSummaryResult = interpretationResultUi.renderInterpretationReviewSummaryCardInto(null, {});

const guardWarningContainer = document.createElement("div");
guardWarningContainer.className = "result-card hidden empty-state";
interpretationResultUi.renderInterpretationLocationGuardInto(guardWarningContainer, {
  message: `Choose city ${malicious}`,
  tone: "warning",
});

const guardDangerContainer = document.createElement("div");
guardDangerContainer.className = "result-card hidden empty-state";
interpretationResultUi.renderInterpretationLocationGuardInto(guardDangerContainer, {
  message: `Blocked city ${malicious}`,
  tone: "danger",
});

const guardOtherToneContainer = document.createElement("div");
guardOtherToneContainer.className = "result-card hidden empty-state";
interpretationResultUi.renderInterpretationLocationGuardInto(guardOtherToneContainer, {
  message: `Review city ${malicious}`,
  tone: "info",
});

const guardEmptyContainer = document.createElement("div");
guardEmptyContainer.className = "result-card";
interpretationResultUi.renderInterpretationLocationGuardInto(guardEmptyContainer, {
  message: "",
  tone: "danger",
});
const nullGuardResult = interpretationResultUi.renderInterpretationLocationGuardInto(null, {
  message: `Ignored ${malicious}`,
  tone: "danger",
});
const exportResetPanel = document.createElement("section");
const exportResetResult = document.createElement("article");
exportResetPanel.classList.add("visible-before-reset");
exportResetResult.classList.add("result-card");
exportResetResult.appendChild(document.createElement("strong"));
interpretationResultUi.resetInterpretationExportResultInto(
  exportResetPanel,
  exportResetResult,
  `Export result empty ${malicious}`,
);
const partialResetResult = document.createElement("article");
partialResetResult.classList.add("result-card");
interpretationResultUi.resetInterpretationExportResultInto(
  null,
  partialResetResult,
  `Partial empty ${malicious}`,
);
const nullResetResult = interpretationResultUi.resetInterpretationExportResultInto(null, null, `Ignored ${malicious}`);

console.log(JSON.stringify({
  exportedTypes: {
    export: typeof interpretationResultUi.renderInterpretationExportResultInto,
    gmail: typeof interpretationResultUi.renderInterpretationGmailResultInto,
    completion: typeof interpretationResultUi.renderInterpretationCompletionCardInto,
    session: typeof interpretationResultUi.renderInterpretationSessionCardInto,
    seed: typeof interpretationResultUi.renderInterpretationSeedCardInto,
    reviewSummary: typeof interpretationResultUi.renderInterpretationReviewSummaryCardInto,
    locationGuard: typeof interpretationResultUi.renderInterpretationLocationGuardInto,
    exportReset: typeof interpretationResultUi.resetInterpretationExportResultInto,
  },
  ok: summarize(okContainer),
  localOnly: summarize(localOnlyContainer),
  failed: summarize(failedContainer),
  gmailOk: summarize(gmailOkContainer),
  gmailLocalOnly: summarize(gmailLocalOnlyContainer),
  gmailWarning: summarize(gmailWarningContainer),
  gmailEmpty: summarize(gmailEmptyContainer),
  completion: summarize(completionContainer),
  completionFallback: summarize(completionFallbackContainer),
  session: summarize(sessionContainer),
  sessionFallback: summarize(sessionFallbackContainer),
  seed: summarize(seedContainer),
  seedFallback: summarize(seedFallbackContainer),
  reviewSummary: summarize(reviewSummaryContainer),
  reviewSummaryFallback: summarize(reviewSummaryFallbackContainer),
  guardWarning: summarizeGuard(guardWarningContainer),
  guardDanger: summarizeGuard(guardDangerContainer),
  guardOtherTone: summarizeGuard(guardOtherToneContainer),
  guardEmpty: summarizeGuard(guardEmptyContainer),
  exportReset: summarizeReset(exportResetPanel, exportResetResult),
  partialExportReset: {
    resultClassName: partialResetResult.className,
    resultText: partialResetResult.textContent,
    resultInnerHTMLWrites: countInnerHtmlWrites(partialResetResult),
    imgCount: countTag(partialResetResult, "img"),
    scriptCount: countTag(partialResetResult, "script"),
  },
  nullContainerResult,
  nullCompletionResult,
  nullSessionResult,
  nullSeedResult,
  nullReviewSummaryResult,
  nullGuardResult,
  nullResetResult,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__INTERPRETATION_RESULT_UI_MODULE_URL__": "interpretation_result_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedTypes"] == {
        "export": "function",
        "gmail": "function",
        "completion": "function",
        "session": "function",
        "seed": "function",
        "reviewSummary": "function",
        "locationGuard": "function",
        "exportReset": "function",
    }
    assert results["ok"]["className"] == "result-card"
    assert results["ok"]["childClasses"] == ["result-header", "result-grid"]
    assert results["ok"]["gridLabels"] == ["DOCX", "PDF", "PDF Export"]
    assert "Ready title <img src=x onerror=alert(1)><script>bad()</script>" in results["ok"]["text"]
    assert "Ready <img src=x onerror=alert(1)><script>bad()</script>" in results["ok"]["text"]
    assert "C:/cases/result <img src=x onerror=alert(1)><script>bad()</script>.docx" in results["ok"]["gridValues"]
    assert "C:/cases/result <img src=x onerror=alert(1)><script>bad()</script>.pdf" in results["ok"]["gridValues"]
    assert "PDF ready <img src=x onerror=alert(1)><script>bad()</script>" in results["ok"]["gridValues"]
    assert "status-chip ok" in results["ok"]["classes"]
    assert results["ok"]["classes"].count("word-break") == 2
    assert results["ok"]["imgCount"] == 0
    assert results["ok"]["scriptCount"] == 0
    assert results["ok"]["innerHTMLWrites"] == 0

    assert results["localOnly"]["className"] == "result-card"
    assert "PDF failure <img src=x onerror=alert(1)><script>bad()</script>" in results["localOnly"]["text"]
    assert "Local only <img src=x onerror=alert(1)><script>bad()</script>" in results["localOnly"]["text"]
    assert results["localOnly"]["gridValues"] == [
        "Unavailable",
        "Unavailable",
        "PDF failure <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip warn" in results["localOnly"]["classes"]
    assert results["localOnly"]["imgCount"] == 0
    assert results["localOnly"]["scriptCount"] == 0
    assert results["localOnly"]["innerHTMLWrites"] == 0

    assert results["failed"]["className"] == "result-card"
    assert "Failed title <img src=x onerror=alert(1)><script>bad()</script>" in results["failed"]["text"]
    assert "Failed <img src=x onerror=alert(1)><script>bad()</script>" in results["failed"]["text"]
    assert results["failed"]["gridValues"] == ["Unavailable", "Unavailable", "Unavailable"]
    assert "status-chip bad" in results["failed"]["classes"]
    assert results["failed"]["imgCount"] == 0
    assert results["failed"]["scriptCount"] == 0
    assert results["failed"]["innerHTMLWrites"] == 0

    assert results["gmailOk"]["className"] == "result-card"
    assert results["gmailOk"]["childClasses"] == ["result-header", "result-grid"]
    assert results["gmailOk"]["gridLabels"] == ["DOCX", "PDF", "Reply status"]
    assert "Gmail reply created <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailOk"]["text"]
    assert "Draft ready <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailOk"]["text"]
    assert "Created <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailOk"]["text"]
    assert "C:/cases/gmail <img src=x onerror=alert(1)><script>bad()</script>.docx" in results["gmailOk"]["gridValues"]
    assert "C:/cases/gmail <img src=x onerror=alert(1)><script>bad()</script>.pdf" in results["gmailOk"]["gridValues"]
    assert "status-chip ok" in results["gmailOk"]["classes"]
    assert results["gmailOk"]["classes"].count("word-break") == 2
    assert results["gmailOk"]["imgCount"] == 0
    assert results["gmailOk"]["scriptCount"] == 0
    assert results["gmailOk"]["innerHTMLWrites"] == 0

    assert results["gmailLocalOnly"]["className"] == "result-card"
    assert "Local-only Gmail reply <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailLocalOnly"]["text"]
    assert "Draft prerequisites <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailLocalOnly"]["text"]
    assert "Local only <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailLocalOnly"]["text"]
    assert results["gmailLocalOnly"]["gridValues"] == [
        "Unavailable",
        "Unavailable",
        "Local only <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip warn" in results["gmailLocalOnly"]["classes"]
    assert results["gmailLocalOnly"]["imgCount"] == 0
    assert results["gmailLocalOnly"]["scriptCount"] == 0
    assert results["gmailLocalOnly"]["innerHTMLWrites"] == 0

    assert results["gmailWarning"]["className"] == "result-card"
    assert "Gmail reply needs attention <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailWarning"]["text"]
    assert "C:/cases/fallback <img src=x onerror=alert(1)><script>bad()</script>.pdf" in results["gmailWarning"]["text"]
    assert "Needs attention <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailWarning"]["text"]
    assert results["gmailWarning"]["gridValues"] == [
        "Unavailable",
        "C:/cases/fallback <img src=x onerror=alert(1)><script>bad()</script>.pdf",
        "Needs attention <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip bad" in results["gmailWarning"]["classes"]
    assert results["gmailWarning"]["imgCount"] == 0
    assert results["gmailWarning"]["scriptCount"] == 0
    assert results["gmailWarning"]["innerHTMLWrites"] == 0

    assert results["gmailEmpty"]["className"] == "result-card"
    assert "No Gmail result <img src=x onerror=alert(1)><script>bad()</script>" in results["gmailEmpty"]["text"]
    assert results["gmailEmpty"]["gridValues"] == [
        "Unavailable",
        "Unavailable",
        "Needs attention <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert results["gmailEmpty"]["imgCount"] == 0
    assert results["gmailEmpty"]["scriptCount"] == 0
    assert results["gmailEmpty"]["innerHTMLWrites"] == 0
    assert "nullContainerResult" not in results

    assert results["completion"]["className"] == "result-card"
    assert results["completion"]["childClasses"] == ["result-header", "result-grid"]
    assert results["completion"]["gridLabels"] == ["DOCX", "PDF", "Case Location", "Service Location"]
    assert "Completion title <img src=x onerror=alert(1)><script>bad()</script>" in results["completion"]["text"]
    assert "Completion message <img src=x onerror=alert(1)><script>bad()</script>" in results["completion"]["text"]
    assert "Completion label <img src=x onerror=alert(1)><script>bad()</script>" in results["completion"]["text"]
    assert results["completion"]["gridValues"] == [
        "C:/cases/completion <img src=x onerror=alert(1)><script>bad()</script>.docx",
        "C:/cases/completion <img src=x onerror=alert(1)><script>bad()</script>.pdf",
        "Case <img src=x onerror=alert(1)><script>bad()</script>",
        "Service <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip warn" in results["completion"]["classes"]
    assert results["completion"]["classes"].count("word-break") == 4
    assert results["completion"]["imgCount"] == 0
    assert results["completion"]["scriptCount"] == 0
    assert results["completion"]["innerHTMLWrites"] == 0

    assert results["completionFallback"]["className"] == "result-card"
    assert results["completionFallback"]["gridValues"] == [
        "Unavailable in this session view",
        "Unavailable",
        "Fallback case <img src=x onerror=alert(1)><script>bad()</script>",
        "Fallback service <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "Fallback title <img src=x onerror=alert(1)><script>bad()</script>" in results["completionFallback"]["text"]
    assert "Fallback label <img src=x onerror=alert(1)><script>bad()</script>" in results["completionFallback"]["text"]
    assert "status-chip bad" in results["completionFallback"]["classes"]
    assert results["completionFallback"]["imgCount"] == 0
    assert results["completionFallback"]["scriptCount"] == 0
    assert results["completionFallback"]["innerHTMLWrites"] == 0
    assert "nullCompletionResult" not in results

    assert results["session"]["className"] == "result-card"
    assert results["session"]["childClasses"] == ["result-header", "result-grid"]
    assert results["session"]["gridLabels"] == ["Case Number", "Court Email", "Service Date", "Location"]
    assert "Session title <img src=x onerror=alert(1)><script>bad()</script>" in results["session"]["text"]
    assert "Notice <img src=x onerror=alert(1)><script>bad()</script>.pdf" in results["session"]["text"]
    assert "Session label <img src=x onerror=alert(1)><script>bad()</script>" in results["session"]["text"]
    assert results["session"]["gridValues"] == [
        "Case number <img src=x onerror=alert(1)><script>bad()</script>",
        "court-<img src=x onerror=alert(1)><script>bad()</script>@example.test",
        "2026-05-01 <img src=x onerror=alert(1)><script>bad()</script>",
        "Location <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip ok" in results["session"]["classes"]
    assert results["session"]["classes"].count("word-break") == 4
    assert results["session"]["imgCount"] == 0
    assert results["session"]["scriptCount"] == 0
    assert results["session"]["innerHTMLWrites"] == 0

    assert results["sessionFallback"]["gridValues"] == [
        "Not set yet",
        "Not set yet",
        "Not set yet",
        "Not set yet",
    ]
    assert "status-chip info" in results["sessionFallback"]["classes"]
    assert results["sessionFallback"]["innerHTMLWrites"] == 0

    assert results["seed"]["className"] == "result-card"
    assert results["seed"]["childClasses"] == ["result-header", "result-grid"]
    assert results["seed"]["gridLabels"] == ["Case", "Court Email", "Service Date", "Location"]
    assert "Seed title <img src=x onerror=alert(1)><script>bad()</script>" in results["seed"]["text"]
    assert "Seed message <img src=x onerror=alert(1)><script>bad()</script>" in results["seed"]["text"]
    assert "Seed label <img src=x onerror=alert(1)><script>bad()</script>" in results["seed"]["text"]
    assert results["seed"]["gridValues"] == [
        "Seed case <img src=x onerror=alert(1)><script>bad()</script>",
        "seed-<img src=x onerror=alert(1)><script>bad()</script>@example.test",
        "2026-05-02 <img src=x onerror=alert(1)><script>bad()</script>",
        "Seed location <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip info" in results["seed"]["classes"]
    assert results["seed"]["classes"].count("word-break") == 4
    assert results["seed"]["imgCount"] == 0
    assert results["seed"]["scriptCount"] == 0
    assert results["seed"]["innerHTMLWrites"] == 0

    assert results["seedFallback"]["gridValues"] == [
        "Not set yet",
        "Not set yet",
        "Not set yet",
        "Not set yet",
    ]
    assert "status-chip ok" in results["seedFallback"]["classes"]
    assert results["seedFallback"]["innerHTMLWrites"] == 0

    assert results["reviewSummary"]["className"] == "result-card"
    assert results["reviewSummary"]["childClasses"] == ["result-header", "result-grid"]
    assert results["reviewSummary"]["gridLabels"] == ["Case Number", "Court Email", "Service Date", "Location"]
    assert "Review title <img src=x onerror=alert(1)><script>bad()</script>" in results["reviewSummary"]["text"]
    assert "Review subtitle <img src=x onerror=alert(1)><script>bad()</script>" in results["reviewSummary"]["text"]
    assert "Review label <img src=x onerror=alert(1)><script>bad()</script>" in results["reviewSummary"]["text"]
    assert results["reviewSummary"]["gridValues"] == [
        "Review case <img src=x onerror=alert(1)><script>bad()</script>",
        "review-<img src=x onerror=alert(1)><script>bad()</script>@example.test",
        "2026-05-03 <img src=x onerror=alert(1)><script>bad()</script>",
        "Review location <img src=x onerror=alert(1)><script>bad()</script>",
    ]
    assert "status-chip warn" in results["reviewSummary"]["classes"]
    assert results["reviewSummary"]["classes"].count("word-break") == 4
    assert results["reviewSummary"]["imgCount"] == 0
    assert results["reviewSummary"]["scriptCount"] == 0
    assert results["reviewSummary"]["innerHTMLWrites"] == 0

    assert results["reviewSummaryFallback"]["gridValues"] == [
        "Not set yet",
        "Not set yet",
        "Not set yet",
        "Not set yet",
    ]
    assert "status-chip bad" in results["reviewSummaryFallback"]["classes"]
    assert results["reviewSummaryFallback"]["innerHTMLWrites"] == 0
    assert "nullSessionResult" not in results
    assert "nullSeedResult" not in results
    assert "nullReviewSummaryResult" not in results
    assert results["guardWarning"]["className"] == "result-card"
    assert results["guardWarning"]["childClasses"] == ["result-header"]
    assert "Choose city <img src=x onerror=alert(1)><script>bad()</script>" in results["guardWarning"]["text"]
    assert "Needs review" in results["guardWarning"]["text"]
    assert "status-chip warn" in results["guardWarning"]["classes"]
    assert results["guardWarning"]["imgCount"] == 0
    assert results["guardWarning"]["scriptCount"] == 0
    assert results["guardWarning"]["innerHTMLWrites"] == 0

    assert results["guardDanger"]["className"] == "result-card"
    assert "Blocked city <img src=x onerror=alert(1)><script>bad()</script>" in results["guardDanger"]["text"]
    assert "Action blocked" in results["guardDanger"]["text"]
    assert "status-chip bad" in results["guardDanger"]["classes"]
    assert results["guardDanger"]["imgCount"] == 0
    assert results["guardDanger"]["scriptCount"] == 0
    assert results["guardDanger"]["innerHTMLWrites"] == 0

    assert results["guardOtherTone"]["className"] == "result-card"
    assert "Review city <img src=x onerror=alert(1)><script>bad()</script>" in results["guardOtherTone"]["text"]
    assert "Needs review" in results["guardOtherTone"]["text"]
    assert "status-chip warn" in results["guardOtherTone"]["classes"]
    assert results["guardOtherTone"]["innerHTMLWrites"] == 0

    assert results["guardEmpty"]["className"] == "result-card hidden empty-state"
    assert results["guardEmpty"]["text"] == ""
    assert results["guardEmpty"]["childClasses"] == []
    assert results["guardEmpty"]["innerHTMLWrites"] == 0
    assert results["exportReset"]["panelClassName"] == "visible-before-reset hidden"
    assert results["exportReset"]["panelHidden"] is True
    assert results["exportReset"]["resultClassName"] == "result-card empty-state"
    assert results["exportReset"]["resultText"] == "Export result empty <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["exportReset"]["resultChildCount"] == 0
    assert results["exportReset"]["imgCount"] == 0
    assert results["exportReset"]["scriptCount"] == 0
    assert results["exportReset"]["panelInnerHTMLWrites"] == 0
    assert results["exportReset"]["resultInnerHTMLWrites"] == 0
    assert results["partialExportReset"]["resultClassName"] == "result-card empty-state"
    assert results["partialExportReset"]["resultText"] == "Partial empty <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["partialExportReset"]["imgCount"] == 0
    assert results["partialExportReset"]["scriptCount"] == 0
    assert results["partialExportReset"]["resultInnerHTMLWrites"] == 0
    assert "nullGuardResult" not in results
    assert "nullResetResult" not in results


def test_recent_work_ui_module_centralizes_safe_history_rendering() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    recent_work_ui_module = static_dir / "recent_work_ui.js"

    assert recent_work_ui_module.exists()
    assert 'from "./recent_work_ui.js"' in app_js
    assert "function appendHistoryMetaBits" not in app_js
    assert "export function renderRecentJobsInto" not in app_js
    assert "export function renderInterpretationHistoryInto" not in app_js
    assert "renderRecentJobsInto(container, items, historyById, translationHistoryById, {" in app_js
    assert "renderInterpretationHistoryInto(container, items, {" in app_js

    script = r"""
const recentWorkUi = await import(__RECENT_WORK_UI_MODULE_URL__);

function makeElement(tagName = "div") {
  const listeners = new Map();
  const element = {
    tagName: String(tagName || "div").toUpperCase(),
    className: "",
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: "",
    _innerHTML: "",
    disabled: false,
    type: "",
    appendChild(node) {
      if (node) {
        node.parentNode = this;
        this.children.push(node);
      }
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
    addEventListener(type, handler) {
      if (!listeners.has(type)) {
        listeners.set(type, []);
      }
      listeners.get(type).push(handler);
    },
    click() {
      for (const handler of listeners.get("click") || []) {
        handler({ target: this, currentTarget: this, preventDefault() {} });
      }
    },
  };
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement(match[1]);
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  return element;
}

function walk(node, visitor) {
  visitor(node);
  for (const child of node.children || []) {
    walk(child, visitor);
  }
}

function countTag(node, tagName) {
  const target = String(tagName || "").toUpperCase();
  let total = 0;
  walk(node, (current) => {
    if (current.tagName === target) {
      total += 1;
    }
  });
  return total;
}

function countInnerHtmlWrites(node) {
  let total = 0;
  walk(node, (current) => {
    total += (current.innerHTMLAssignments || []).length;
  });
  return total;
}

function collectClasses(node) {
  const classes = [];
  walk(node, (current) => {
    if (String(current.className || "").trim()) {
      classes.push(current.className);
    }
  });
  return classes;
}

function allButtons(node) {
  const buttons = [];
  walk(node, (current) => {
    if (current.tagName === "BUTTON") {
      buttons.push(current);
    }
  });
  return buttons;
}

globalThis.document = {
  createElement(tagName) {
    return makeElement(tagName);
  },
};

const malicious = `<img src=x onerror=alert(1)><script>bad()</script>`;
const translationRecord = { row: { id: 7 }, kind: "translation-record" };
const interpretationRecord = { row: { id: 8 }, kind: "interpretation-record" };
let openedTranslation = "";
let openedInterpretation = "";
let deletedRecentId = "";
const recentContainer = document.createElement("div");
recentWorkUi.renderRecentJobsInto(
  recentContainer,
  [
    {
      id: "7",
      job_type: "Translation",
      case_number: malicious,
      case_entity: "Entity <b>unsafe</b>",
      case_city: "Beja<script>",
      service_date: "2026-04-21",
      completed_at: "",
      target_lang: "AR",
    },
    {
      id: "8",
      job_type: "Interpretation",
      case_number: "Interpretation case",
      case_entity: "Court",
      case_city: "Lisbon",
      service_date: "",
      completed_at: "2026-04-22",
      target_lang: "",
    },
    {
      id: "9",
      job_type: "Translation",
      case_number: "Unavailable",
      case_entity: "",
      case_city: "",
      service_date: "",
      completed_at: "",
      target_lang: "",
    },
  ],
  new Map([[8, interpretationRecord]]),
  new Map([[7, translationRecord]]),
  {
    onOpenInterpretation(item) {
      openedInterpretation = item.kind;
    },
    onOpenTranslation(item) {
      openedTranslation = item.kind;
    },
    onDelete(item) {
      deletedRecentId = item.id;
    },
  },
);

const recentButtons = allButtons(recentContainer);
recentButtons[0].click();
recentButtons[1].click();
recentButtons[2].click();

const recentEmptyContainer = document.createElement("div");
recentWorkUi.renderRecentJobsInto(recentEmptyContainer, [], new Map(), new Map());

const historyItem = {
  row: {
    id: 11,
    case_number: malicious,
    case_entity: "Tribunal <svg>",
    case_city: "Cuba<img>",
    service_date: "2026-05-01",
  },
};
let openedHistoryId = 0;
let deletedHistoryId = 0;
const historyContainer = document.createElement("div");
recentWorkUi.renderInterpretationHistoryInto(historyContainer, [historyItem], {
  onOpen(item) {
    openedHistoryId = item.row.id;
  },
  onDelete(item) {
    deletedHistoryId = item.row.id;
  },
});
const historyButtons = allButtons(historyContainer);
historyButtons[0].click();
historyButtons[1].click();

const historyEmptyContainer = document.createElement("div");
recentWorkUi.renderInterpretationHistoryInto(historyEmptyContainer, []);

const nullRecent = recentWorkUi.renderRecentJobsInto(null, [], new Map(), new Map());
const nullHistory = recentWorkUi.renderInterpretationHistoryInto(null, []);

console.log(JSON.stringify({
  exportedTypes: {
    recent: typeof recentWorkUi.renderRecentJobsInto,
    interpretationHistory: typeof recentWorkUi.renderInterpretationHistoryInto,
  },
  recent: {
    text: recentContainer.textContent,
    articleCount: countTag(recentContainer, "article"),
    buttonTexts: recentButtons.map((button) => button.textContent),
    disabledButtons: recentButtons.filter((button) => button.disabled).map((button) => button.textContent),
    imgCount: countTag(recentContainer, "img"),
    scriptCount: countTag(recentContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(recentContainer),
    classes: collectClasses(recentContainer),
    openedTranslation,
    openedInterpretation,
    deletedRecentId,
  },
  recentEmpty: {
    text: recentEmptyContainer.textContent,
    className: recentEmptyContainer.children[0]?.className || "",
  },
  history: {
    text: historyContainer.textContent,
    articleCount: countTag(historyContainer, "article"),
    buttonTexts: historyButtons.map((button) => button.textContent),
    imgCount: countTag(historyContainer, "img"),
    scriptCount: countTag(historyContainer, "script"),
    innerHTMLWrites: countInnerHtmlWrites(historyContainer),
    classes: collectClasses(historyContainer),
    openedHistoryId,
    deletedHistoryId,
  },
  historyEmpty: {
    text: historyEmptyContainer.textContent,
    className: historyEmptyContainer.children[0]?.className || "",
  },
  nullResultTypes: [
    nullRecent === undefined ? "undefined" : typeof nullRecent,
    nullHistory === undefined ? "undefined" : typeof nullHistory,
  ],
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__RECENT_WORK_UI_MODULE_URL__": "recent_work_ui.js"},
        timeout_seconds=30,
    )

    assert results["exportedTypes"] == {
        "recent": "function",
        "interpretationHistory": "function",
    }
    assert "<img src=x onerror=alert(1)><script>bad()</script>" in results["recent"]["text"]
    assert "Entity <b>unsafe</b> | Beja<script> | 2026-04-21" in results["recent"]["text"]
    assert "Translation" in results["recent"]["text"]
    assert "Interpretation" in results["recent"]["text"]
    assert "AR" in results["recent"]["text"]
    assert "Open unavailable" in results["recent"]["text"]
    assert results["recent"]["articleCount"] == 3
    assert results["recent"]["buttonTexts"] == [
        "Open",
        "Delete record",
        "Open",
        "Delete record",
        "Open unavailable",
        "Delete record",
    ]
    assert results["recent"]["disabledButtons"] == ["Open unavailable"]
    assert results["recent"]["imgCount"] == 0
    assert results["recent"]["scriptCount"] == 0
    assert results["recent"]["innerHTMLWrites"] == 0
    assert "history-item" in results["recent"]["classes"]
    assert "history-meta" in results["recent"]["classes"]
    assert "history-actions" in results["recent"]["classes"]
    assert results["recent"]["openedTranslation"] == "translation-record"
    assert results["recent"]["openedInterpretation"] == "interpretation-record"
    assert results["recent"]["deletedRecentId"] == "7"
    assert results["recentEmpty"]["text"] == "No saved cases yet."
    assert results["recentEmpty"]["className"] == "empty-state"

    assert "<img src=x onerror=alert(1)><script>bad()</script>" in results["history"]["text"]
    assert "Tribunal <svg> | Cuba<img> | 2026-05-01" in results["history"]["text"]
    assert results["history"]["articleCount"] == 1
    assert results["history"]["buttonTexts"] == ["Open", "Delete record"]
    assert results["history"]["imgCount"] == 0
    assert results["history"]["scriptCount"] == 0
    assert results["history"]["innerHTMLWrites"] == 0
    assert "history-item" in results["history"]["classes"]
    assert "history-actions" in results["history"]["classes"]
    assert results["history"]["openedHistoryId"] == 11
    assert results["history"]["deletedHistoryId"] == 11
    assert results["historyEmpty"]["text"] == "No saved interpretation requests yet."
    assert results["historyEmpty"]["className"] == "empty-state"
    assert results["nullResultTypes"] == ["undefined", "undefined"]


def test_shadow_web_extension_lab_top_level_card_copy_stays_friendly() -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    extension_lab_js = (static_dir / "extension_lab_presentation.js").read_text(encoding="utf-8")

    readiness_start = extension_lab_js.index("export function extensionReadinessCardText")
    install_start = extension_lab_js.index("export function extensionInstallCardText")
    mode_start = extension_lab_js.index("export function extensionModeCardText")
    build_cards_start = extension_lab_js.index("export function buildExtensionLabCards")
    render_start = app_js.index("function renderExtensionLab")
    show_live_start = app_js.index("function showLiveBanner")

    readiness_block = extension_lab_js[readiness_start:install_start]
    install_block = extension_lab_js[install_start:mode_start]
    mode_block = extension_lab_js[mode_start:build_cards_start]
    card_builder_block = extension_lab_js[build_cards_start:]
    render_block = app_js[render_start:show_live_start]

    assert "bridgeSummary.message" not in readiness_block
    assert '"Ready for Gmail intake in this mode."' in readiness_block
    assert '"This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting."' in readiness_block
    assert '"Needs attention before Gmail intake can start here. Open technical details below when troubleshooting."' in readiness_block

    assert "Stable ID:" not in install_block
    assert "stable_extension_id" not in install_block
    assert '"Browser helper details were found. Open technical details below for installation IDs."' in install_block
    assert '"Older browser helper details were found. Open technical details below when troubleshooting."' in install_block
    assert '"No browser helper installation details were reported."' in install_block

    assert "bridgeSummary.message" not in mode_block
    assert '"Using live app settings and saved work."' in mode_block
    assert '"Using isolated test settings and saved work."' in mode_block
    assert '"Use this page when Gmail intake needs a deeper technical check."' in mode_block
    assert '"This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting."' in mode_block
    assert '"Live Gmail readiness can differ from this isolated test mode."' in mode_block
    assert "Stable ID:" not in mode_block
    assert "UI owner" not in mode_block
    assert "Launch target" not in mode_block

    assert '"Gmail helper readiness"' in card_builder_block
    assert '"Installed browser helper"' in card_builder_block
    assert '"Current mode"' in card_builder_block
    assert 'const cards = buildExtensionLabCards({ prepare, extensionReport, bridgeSummary, runtime });' in render_block
    assert 'setDiagnostics("extension", { prepare_response: prepare, extension_report: extensionReport, bridge_summary: bridgeSummary, notes: data.notes || [] }, {' in render_block


def test_diagnostics_presentation_module_centralizes_safe_diagnostic_formatting(tmp_path: Path, monkeypatch) -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    power_tools_js = (static_dir / "power-tools.js").read_text(encoding="utf-8")
    diagnostics_ui_js = (static_dir / "diagnostics_ui.js").read_text(encoding="utf-8")
    diagnostics_module = static_dir / "diagnostics_presentation.js"

    assert diagnostics_module.exists()
    assert 'from "./diagnostics_presentation.js"' not in app_js
    assert 'from "./diagnostics_presentation.js"' in diagnostics_ui_js
    assert 'from "./diagnostics_presentation.js"' in power_tools_js

    script = """
const diagnostics = await import(__DIAGNOSTICS_PRESENTATION_MODULE_URL__);
const error = new Error("Bridge unavailable");
error.status = 503;
error.payload = { retryable: true };

const circular = {};
circular.self = circular;

console.log(JSON.stringify({
  stringValue: diagnostics.formatDiagnosticValue("already formatted"),
  missingValue: diagnostics.formatDiagnosticValue(null),
  objectValue: diagnostics.formatDiagnosticValue({ status: "ok", count: 2 }),
  errorValue: diagnostics.formatDiagnosticValue(error),
  circularValue: diagnostics.formatDiagnosticValue(circular),
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__DIAGNOSTICS_PRESENTATION_MODULE_URL__": "diagnostics_presentation.js"},
        timeout_seconds=30,
    )

    assert results["stringValue"] == "already formatted"
    assert results["missingValue"] == ""
    assert results["objectValue"] == '{\n  "status": "ok",\n  "count": 2\n}'
    assert results["errorValue"] == (
        '{\n'
        '  "status": "failed",\n'
        '  "message": "Bridge unavailable",\n'
        '  "http_status": 503,\n'
        '  "payload": {\n'
        '    "retryable": true\n'
        "  }\n"
        "}"
    )
    assert results["circularValue"] == "[object Object]"

    with _build_app(tmp_path, monkeypatch) as client:
        shell = client.get("/api/bootstrap/shell", params={"mode": "live", "workspace": "dashboard"})
        assert shell.status_code == 200
        asset_version = shell.json()["normalized_payload"]["shell"]["asset_version"]
        diagnostics_asset = client.get(f"/static-build/{asset_version}/diagnostics_presentation.js")
        assert diagnostics_asset.status_code == 200
        assert diagnostics_asset.headers["content-type"].startswith("application/javascript")
        assert "formatDiagnosticValue" in diagnostics_asset.text


def test_diagnostics_ui_module_centralizes_safe_status_rendering(tmp_path: Path, monkeypatch) -> None:
    static_dir = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    diagnostics_ui_module = static_dir / "diagnostics_ui.js"

    assert diagnostics_ui_module.exists()
    diagnostics_ui_js = diagnostics_ui_module.read_text(encoding="utf-8")
    assert 'from "./diagnostics_ui.js"' in app_js
    assert 'from "./diagnostics_presentation.js"' in diagnostics_ui_js
    assert 'from "./diagnostics_presentation.js"' not in app_js
    assert "export function setDiagnostics" in diagnostics_ui_js
    assert "export function setPanelStatus" in diagnostics_ui_js
    assert "export function setTopbarStatus" in diagnostics_ui_js

    script = """
const diagnosticsUi = await import(__DIAGNOSTICS_UI_MODULE_URL__);

class Element {
  constructor(id) {
    this.id = id;
    this.textContent = "";
    this.dataset = {};
    this.open = false;
    this.innerHTMLAssignments = [];
    this._innerHTML = "";
  }
}

Object.defineProperty(Element.prototype, "innerHTML", {
  get() {
    return this._innerHTML;
  },
  set(value) {
    this._innerHTML = value;
    this.innerHTMLAssignments.push(value);
  },
});

const nodes = new Map();
function createNode(id) {
  const element = new Element(id);
  nodes.set(id, element);
  return element;
}

const diagnostics = createNode("review-diagnostics");
const hint = createNode("review-hint");
const details = createNode("review-details");
const panelStatus = createNode("review-status");
const topbarStatus = createNode("topbar-status");

globalThis.document = {
  getElementById(id) {
    return nodes.get(id) || null;
  },
};

diagnosticsUi.setDiagnostics(
  "review",
  { message: "<img src=x onerror=alert(1)>", ok: true },
  { hint: "Safe <hint>", open: true },
);
const firstDiagnostics = {
  text: diagnostics.textContent,
  hint: hint.textContent,
  detailsOpen: details.open,
  reveal: details.dataset.reveal || null,
};

diagnosticsUi.setDiagnostics("review", "Plain <b>diagnostic</b>", { open: false });
const secondDiagnostics = {
  text: diagnostics.textContent,
  preservedHint: hint.textContent,
  detailsOpen: details.open,
  reveal: details.dataset.reveal || null,
};

diagnosticsUi.setPanelStatus("review", "warning", "Careful <b>status</b>");
const firstPanelStatus = {
  text: panelStatus.textContent,
  tone: panelStatus.dataset.tone || null,
};

diagnosticsUi.setPanelStatus("review", "", "Cleared <script>");
const secondPanelStatus = {
  text: panelStatus.textContent,
  tone: panelStatus.dataset.tone || null,
};

diagnosticsUi.setTopbarStatus("Topbar <em>ready</em>", "success");
const firstTopbarStatus = {
  text: topbarStatus.textContent,
  tone: topbarStatus.dataset.tone || null,
};

diagnosticsUi.setTopbarStatus("Topbar neutral", "");
const secondTopbarStatus = {
  text: topbarStatus.textContent,
  tone: topbarStatus.dataset.tone || null,
};

diagnosticsUi.setDiagnostics("missing", { ignored: true }, { hint: "Ignored", open: true });
diagnosticsUi.setPanelStatus("missing", "warning", "Ignored");
nodes.delete("topbar-status");
diagnosticsUi.setTopbarStatus("Ignored", "warning");

const innerHTMLWrites = [
  diagnostics,
  hint,
  details,
  panelStatus,
  topbarStatus,
].reduce((total, node) => total + node.innerHTMLAssignments.length, 0);

console.log(JSON.stringify({
  firstDiagnostics,
  secondDiagnostics,
  firstPanelStatus,
  secondPanelStatus,
  firstTopbarStatus,
  secondTopbarStatus,
  innerHTMLWrites,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__DIAGNOSTICS_UI_MODULE_URL__": "diagnostics_ui.js"},
        timeout_seconds=30,
    )

    assert results["firstDiagnostics"] == {
        "text": '{\n  "message": "<img src=x onerror=alert(1)>",\n  "ok": true\n}',
        "hint": "Safe <hint>",
        "detailsOpen": True,
        "reveal": "true",
    }
    assert results["secondDiagnostics"] == {
        "text": "Plain <b>diagnostic</b>",
        "preservedHint": "Safe <hint>",
        "detailsOpen": False,
        "reveal": None,
    }
    assert results["firstPanelStatus"] == {
        "text": "Careful <b>status</b>",
        "tone": "warning",
    }
    assert results["secondPanelStatus"] == {
        "text": "Cleared <script>",
        "tone": None,
    }
    assert results["firstTopbarStatus"] == {
        "text": "Topbar <em>ready</em>",
        "tone": "success",
    }
    assert results["secondTopbarStatus"] == {
        "text": "Topbar neutral",
        "tone": None,
    }
    assert results["innerHTMLWrites"] == 0

    with _build_app(tmp_path, monkeypatch) as client:
        shell = client.get("/api/bootstrap/shell", params={"mode": "live", "workspace": "dashboard"})
        assert shell.status_code == 200
        asset_version = shell.json()["normalized_payload"]["shell"]["asset_version"]
        diagnostics_asset = client.get(f"/static-build/{asset_version}/diagnostics_ui.js")
        assert diagnostics_asset.status_code == 200
        assert diagnostics_asset.headers["content-type"].startswith("application/javascript")
        assert "setDiagnostics" in diagnostics_asset.text
        assert "setPanelStatus" in diagnostics_asset.text
        assert "setTopbarStatus" in diagnostics_asset.text


def test_shadow_web_live_mode_and_gmail_runtime_copy_stay_beginner_safe() -> None:
    root = Path(__file__).resolve().parents[1]
    static_dir = root / "src" / "legalpdf_translate" / "shadow_web" / "static"
    template = (root / "src" / "legalpdf_translate" / "shadow_web" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    shell_js = (static_dir / "shell_presentation.js").read_text(encoding="utf-8")
    guard_js = (static_dir / "gmail_runtime_guard.js").read_text(encoding="utf-8")
    dashboard_js = (static_dir / "dashboard_presentation.js").read_text(encoding="utf-8")
    gmail_js = (static_dir / "gmail.js").read_text(encoding="utf-8")

    assert 'id="runtime-mode-banner"' in template
    assert '"Live mode: using your real settings, Gmail drafts, and saved work."' in shell_js
    assert '"Test mode: using isolated app data. Live Gmail and saved work may differ."' in shell_js
    assert "DAILY_RUNTIME_MODE_BANNER_ROUTES" in shell_js
    assert 'runtimeMode === "live"' in shell_js
    assert "appState.runtimeMode" in app_js
    assert '"Warming the browser shell and Gmail workspace..."' in app_js
    assert '"Warming the browser shell, Gmail bridge, and workspace..."' not in app_js
    assert '"Live mode"' in shell_js
    assert '"Test mode"' in shell_js

    assert '"Live Gmail needs the main app runtime"' in guard_js
    assert '"Restart live Gmail runtime"' in guard_js
    assert (
        '"Live Gmail extension intake requires the canonical main runtime. Use shadow/test mode for feature-branch UI review."'
        in guard_js
    )
    assert '"Live Gmail is running from a noncanonical build"' not in guard_js

    assert '"Optional setup for live Gmail intake."' in dashboard_js
    assert '"Live Gmail attachments are ready when you need them."' in dashboard_js
    assert '"Gmail tools need attention before live Gmail work."' not in dashboard_js

    warning_start = gmail_js.index("function renderGmailFinalizeNumericMismatchWarning")
    warning_end = gmail_js.index("function interpretationUiSnapshot")
    warning_block = gmail_js[warning_start:warning_end]
    assert '"gmail-batch-finalize-numeric-warning"' in warning_block
    assert "container.textContent" in warning_block
    assert ".innerHTML" not in warning_block

    banner_start = app_js.index("function syncRuntimeModeBanner")
    banner_end = app_js.index("function syncShellChrome")
    banner_block = app_js[banner_start:banner_end]
    assert "shouldShowDailyRuntimeModeBanner({" in banner_block
    assert "Boolean(appState.bootstrap?.normalized_payload?.runtime)" not in banner_block
    assert "operatorChromeActive()" in banner_block

    shell_start = app_js.index("function syncShellChrome")
    shell_end = app_js.index("function beginnerSurfaceTargetLabel")
    shell_block = app_js[shell_start:shell_end]
    assert "setTopbarStatus(chrome.status, chrome.tone);" in shell_block
    assert "runtime.workspace_id || appState.bootstrap?.normalized_payload?.runtime" not in shell_block


def test_interpretation_review_drawer_uses_city_scoped_email_and_service_entity_selectors() -> None:
    root = Path(__file__).resolve().parents[1]
    static_dir = root / "src" / "legalpdf_translate" / "shadow_web" / "static"
    template = (root / "src" / "legalpdf_translate" / "shadow_web" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    style_css = (static_dir / "style.css").read_text(encoding="utf-8")

    assert '<select id="court-email" name="court_email"></select>' in template
    assert 'id="court-email-add"' in template
    assert 'id="court-email-editor"' in template
    assert '<select id="service-entity" name="service_entity"></select>' in template
    assert '"/api/interpretation/court-emails/add"' in app_js
    assert "deriveCourtEmailSelection" in app_js
    assert "interpretation-court-email-field" in template
    assert "width: min(920px, calc(100vw - 24px));" in style_css
    assert "#interpretation-form .interpretation-court-email-field" in style_css
    assert ".checkbox-field label" in style_css
    assert '.checkbox-field input[type="checkbox"]' in style_css
    assert "width: auto;" in style_css
    assert "align-items: center;" in style_css


def test_shadow_web_tiny_presentation_cleanup_copy_is_distinct() -> None:
    root = Path(__file__).resolve().parents[1]
    static_dir = root / "src" / "legalpdf_translate" / "shadow_web" / "static"
    template = (root / "src" / "legalpdf_translate" / "shadow_web" / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    app_js = (static_dir / "app.js").read_text(encoding="utf-8")
    profile_ui_js = (static_dir / "profile_ui.js").read_text(encoding="utf-8")
    recent_work_ui_js = (static_dir / "recent_work_ui.js").read_text(encoding="utf-8")
    translation_js = (static_dir / "translation.js").read_text(encoding="utf-8")

    assert '"No saved work yet. Completed translations and interpretation requests will appear here."' in translation_js
    assert '"No saved cases yet."' in translation_js
    assert "deriveRecentWorkPresentation().recentCasesEmpty" in recent_work_ui_js
    assert "presentation.recentWorkEmpty" in app_js

    assert "Main profile summary" in template
    assert "Profile records" in template
    assert "Edit saved contact, payment, and travel details here." in template
    assert "Profile record" in profile_ui_js
    assert "Edit this profile's contact, payment, and travel details." in profile_ui_js


def test_shadow_web_client_prefers_url_launch_session_state_over_stale_bootstrap() -> None:
    app_js = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "legalpdf_translate"
        / "shadow_web"
        / "static"
        / "app.js"
    ).read_text(encoding="utf-8")

    launch_start = app_js.index("function deriveClientLaunchSessionId")
    handoff_start = app_js.index("function deriveClientHandoffSessionId")
    launch_block = app_js[launch_start:handoff_start]
    assert launch_block.index("urlState.launchSessionId") < launch_block.index("shellLaunchSession.launch_session_id")

    schema_start = app_js.index("function deriveClientLaunchSessionSchemaVersion")
    handoff_block = app_js[handoff_start:schema_start]
    assert handoff_block.index("urlState.handoffSessionId") < handoff_block.index("gmailPayload.handoff_session_id")

    marker_start = app_js.index("function setClientHydrationMarker")
    schema_block = app_js[schema_start:marker_start]
    assert "if (urlState.launchSessionSchemaVersion > 0)" in schema_block


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
                "runtime_state_root": _browser_data_paths(tmp_path, "live").app_data_dir,
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
        assert payload["normalized_payload"]["shell"]["extension_launch_session_schema_version"] == 4
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
                "runtime_state_root_compatible": True,
                "expected_runtime_state_root": str(_browser_data_paths(tmp_path, "live").app_data_dir),
                "observed_runtime_state_root": str(_browser_data_paths(tmp_path, "live").app_data_dir),
            },
        )
        followup_response = client.post(
            "/api/extension/launch-session-diagnostics",
            json={
                "launch_session_id": "launch-123",
                "handoff_session_id": "handoff-456",
                "bridge_context_posted": True,
                "outcome": "loaded",
                "reason": "workspace_loaded",
                "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            },
        )
        inferred_response = client.post(
            "/api/extension/launch-session-diagnostics",
            json={
                "launch_session_id": "launch-inferred",
                "handoff_session_id": "handoff-inferred",
                "click_phase": "bridge_context_posted",
                "workspace_surface_confirmed": True,
                "bridge_context_posted": True,
                "runtime_state_root_compatible": False,
                "expected_runtime_state_root": "",
                "observed_runtime_state_root": "",
                "outcome": "loaded",
                "reason": "loaded",
                "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            },
        )
        payload = response.json()
        followup_payload = followup_response.json()
        inferred_payload = inferred_response.json()

    assert response.status_code == 200
    assert followup_response.status_code == 200
    assert inferred_response.status_code == 200
    assert payload["status"] == "ok"
    launch_session = payload["normalized_payload"]["launch_session"]
    assert launch_session["launch_session_id"] == "launch-123"
    assert launch_session["handoff_session_id"] == "handoff-456"
    assert launch_session["click_phase"] == ""
    assert launch_session["click_failure_reason"] == ""
    assert launch_session["source_gmail_url"] == ""
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
    assert launch_session["runtime_state_root_compatible"] is True
    assert launch_session["expected_runtime_state_root"] == str(_browser_data_paths(tmp_path, "live").app_data_dir)
    assert launch_session["observed_runtime_state_root"] == str(_browser_data_paths(tmp_path, "live").app_data_dir)
    followup_launch_session = followup_payload["normalized_payload"]["launch_session"]
    assert followup_launch_session["extension_surface_outcome"] == "loaded"
    assert followup_launch_session["runtime_state_root_compatible"] is True
    assert followup_launch_session["expected_runtime_state_root"] == str(_browser_data_paths(tmp_path, "live").app_data_dir)
    assert followup_launch_session["observed_runtime_state_root"] == str(_browser_data_paths(tmp_path, "live").app_data_dir)
    inferred_launch_session = inferred_payload["normalized_payload"]["launch_session"]
    assert inferred_launch_session["runtime_state_root_compatible"] is True
    assert inferred_launch_session["expected_runtime_state_root"] == str(_browser_data_paths(tmp_path, "live").app_data_dir)
    assert inferred_launch_session["observed_runtime_state_root"] == str(_browser_data_paths(tmp_path, "live").app_data_dir)


def test_shadow_web_gmail_bootstrap_accepts_workspace_id_query_alias(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/gmail/bootstrap?mode=live&workspace_id=gmail-intake")

    assert response.status_code == 200
    payload = response.json()
    assert payload["normalized_payload"]["runtime"]["workspace_id"] == "gmail-intake"
    assert payload["normalized_payload"]["workspace"]["id"] == "gmail-intake"


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

    def _build_bootstrap(
        self,
        *,
        runtime_mode,
        workspace_id,
        settings_path,
        outputs_dir,
        runtime_state_root=None,
        build_sha="",
        asset_version="",
    ):
        recorded["build_bootstrap"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "outputs_dir": str(outputs_dir),
            "runtime_state_root": str(runtime_state_root) if runtime_state_root is not None else "",
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


def test_shadow_web_gmail_demo_review_fixture_is_shadow_only_and_previewable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch, build_identity=_canonical_identity()) as client:
        live_response = client.post(
            "/api/gmail/demo-review",
            json={"mode": "live", "workspace_id": "gmail-demo"},
        )
        assert live_response.status_code == 422
        assert "shadow/test mode" in live_response.json()["diagnostics"]["error"]

        demo_response = client.post(
            "/api/gmail/demo-review",
            json={"mode": "shadow", "workspace_id": "gmail-demo"},
        )
        demo_payload = demo_response.json()
        assert demo_response.status_code == 200
        assert demo_payload["normalized_payload"]["shadow_demo"] is True
        load_result = demo_payload["normalized_payload"]["load_result"]
        assert load_result["ok"] is True
        attachments = load_result["message"]["attachments"]
        assert len(attachments) == 1
        assert attachments[0]["attachment_id"] == "demo-gmail-review-pdf"
        assert attachments[0]["mime_type"] == "application/pdf"

        bootstrap_response = client.get("/api/gmail/bootstrap?mode=shadow&workspace=gmail-demo")
        bootstrap_payload = bootstrap_response.json()
        bootstrap_load = bootstrap_payload["normalized_payload"]["load_result"]
        assert bootstrap_response.status_code == 200
        assert bootstrap_load["ok"] is True
        assert bootstrap_load["message"]["attachments"][0]["attachment_id"] == "demo-gmail-review-pdf"

        preview_response = client.post(
            "/api/gmail/preview-attachment",
            json={"mode": "shadow", "workspace_id": "gmail-demo", "attachment_id": "demo-gmail-review-pdf"},
        )
        preview_payload = preview_response.json()
        assert preview_response.status_code == 200
        assert preview_payload["normalized_payload"]["page_count"] == 1
        assert preview_payload["normalized_payload"]["preview_href"].startswith(
            "/api/gmail/attachment/demo-gmail-review-pdf?"
        )

        attachment_response = client.get(preview_payload["normalized_payload"]["preview_href"])
        assert attachment_response.status_code == 200
        assert attachment_response.headers["content-type"].startswith("application/pdf")
        assert attachment_response.headers["content-disposition"].startswith("inline;")


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
                "runtime_state_root": _browser_data_paths(tmp_path, "live").app_data_dir,
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
        extension_lab_asset = client.get(f"/static-build/{asset_version}/extension_lab_presentation.js")
        assert extension_lab_asset.status_code == 200
        assert extension_lab_asset.headers["content-type"].startswith("application/javascript")
        assert "buildExtensionLabCards" in extension_lab_asset.text
        extension_lab_ui_asset = client.get(f"/static-build/{asset_version}/extension_lab_ui.js")
        assert extension_lab_ui_asset.status_code == 200
        assert extension_lab_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderExtensionPrepareReasonCatalogInto" in extension_lab_ui_asset.text
        profile_ui_asset = client.get(f"/static-build/{asset_version}/profile_ui.js")
        assert profile_ui_asset.status_code == 200
        assert profile_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderProfileDistanceRowsInto" in profile_ui_asset.text
        assert "renderProfileOptionsInto" in profile_ui_asset.text
        assert "renderPrimaryProfileCardInto" in profile_ui_asset.text
        assert "renderProfileListInto" in profile_ui_asset.text
        assert "syncProfileEditorDrawerStateInto" in profile_ui_asset.text
        assert "renderProfileDistanceStatusInto" in profile_ui_asset.text
        assert "renderProfileDistanceJsonInto" in profile_ui_asset.text
        assert "renderProfileEditorChromeInto" in profile_ui_asset.text
        dashboard_ui_asset = client.get(f"/static-build/{asset_version}/dashboard_ui.js")
        assert dashboard_ui_asset.status_code == 200
        assert dashboard_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderDashboardCardsInto" in dashboard_ui_asset.text
        assert "renderSummaryGridInto" in dashboard_ui_asset.text
        assert "renderCapabilityCardsInto" in dashboard_ui_asset.text
        assert "renderParityAuditInto" in dashboard_ui_asset.text
        recent_work_ui_asset = client.get(f"/static-build/{asset_version}/recent_work_ui.js")
        assert recent_work_ui_asset.status_code == 200
        assert recent_work_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderRecentJobsInto" in recent_work_ui_asset.text
        assert "renderInterpretationHistoryInto" in recent_work_ui_asset.text
        result_card_ui_asset = client.get(f"/static-build/{asset_version}/result_card_ui.js")
        assert result_card_ui_asset.status_code == 200
        assert result_card_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "createResultHeader" in result_card_ui_asset.text
        assert "appendResultGridItem" in result_card_ui_asset.text
        recovery_ui_asset = client.get(f"/static-build/{asset_version}/recovery_result_ui.js")
        assert recovery_ui_asset.status_code == 200
        assert recovery_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderRecoveryResultInto" in recovery_ui_asset.text
        google_photos_ui_asset = client.get(f"/static-build/{asset_version}/google_photos_ui.js")
        assert google_photos_ui_asset.status_code == 200
        assert google_photos_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderGooglePhotosSummaryInto" in google_photos_ui_asset.text
        shell_ui_asset = client.get(f"/static-build/{asset_version}/shell_ui.js")
        assert shell_ui_asset.status_code == 200
        assert shell_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderNavigationInto" in shell_ui_asset.text
        assert "renderLiveBannerInto" in shell_ui_asset.text
        assert "renderRuntimeModeSelectorInto" in shell_ui_asset.text
        assert "renderShellVisibilityInto" in shell_ui_asset.text
        assert "renderRuntimeModeBannerInto" in shell_ui_asset.text
        assert "renderOperatorChromeInto" in shell_ui_asset.text
        assert "renderShellChromeInto" in shell_ui_asset.text
        new_job_ui_asset = client.get(f"/static-build/{asset_version}/new_job_ui.js")
        assert new_job_ui_asset.status_code == 200
        assert new_job_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "syncNewJobTaskControlsInto" in new_job_ui_asset.text
        diagnostics_ui_asset = client.get(f"/static-build/{asset_version}/diagnostics_ui.js")
        assert diagnostics_ui_asset.status_code == 200
        assert diagnostics_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "setDiagnostics" in diagnostics_ui_asset.text
        assert "setPanelStatus" in diagnostics_ui_asset.text
        assert "setTopbarStatus" in diagnostics_ui_asset.text
        interpretation_reference_ui_asset = client.get(f"/static-build/{asset_version}/interpretation_reference_ui.js")
        assert interpretation_reference_ui_asset.status_code == 200
        assert interpretation_reference_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderInterpretationCityOptionsInto" in interpretation_reference_ui_asset.text
        assert "renderCourtEmailOptionsInto" in interpretation_reference_ui_asset.text
        assert "renderServiceEntityOptionsInto" in interpretation_reference_ui_asset.text
        assert "renderInterpretationFieldWarningInto" in interpretation_reference_ui_asset.text
        assert "renderInterpretationDistanceHintInto" in interpretation_reference_ui_asset.text
        assert "renderInterpretationActionButtonsInto" in interpretation_reference_ui_asset.text
        assert "renderInterpretationCityAddButtonsInto" in interpretation_reference_ui_asset.text
        assert "syncInterpretationCityDialogStateInto" in interpretation_reference_ui_asset.text
        assert "renderInterpretationCityDialogContentInto" in interpretation_reference_ui_asset.text
        interpretation_review_ui_asset = client.get(f"/static-build/{asset_version}/interpretation_review_ui.js")
        assert interpretation_review_ui_asset.status_code == 200
        assert interpretation_review_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderInterpretationReviewContextInto" in interpretation_review_ui_asset.text
        assert "syncInterpretationReviewDetailsShellInto" in interpretation_review_ui_asset.text
        assert "syncInterpretationReviewDrawerStateInto" in interpretation_review_ui_asset.text
        assert "renderInterpretationReviewSurfaceInto" in interpretation_review_ui_asset.text
        assert "renderInterpretationDisclosureSectionsInto" in interpretation_review_ui_asset.text
        interpretation_result_ui_asset = client.get(f"/static-build/{asset_version}/interpretation_result_ui.js")
        assert interpretation_result_ui_asset.status_code == 200
        assert interpretation_result_ui_asset.headers["content-type"].startswith("application/javascript")
        assert "renderInterpretationExportResultInto" in interpretation_result_ui_asset.text
        assert "renderInterpretationGmailResultInto" in interpretation_result_ui_asset.text
        assert "renderInterpretationCompletionCardInto" in interpretation_result_ui_asset.text
        assert "renderInterpretationSessionCardInto" in interpretation_result_ui_asset.text
        assert "renderInterpretationSeedCardInto" in interpretation_result_ui_asset.text
        assert "renderInterpretationReviewSummaryCardInto" in interpretation_result_ui_asset.text
        assert "renderInterpretationLocationGuardInto" in interpretation_result_ui_asset.text
        assert "resetInterpretationExportResultInto" in interpretation_result_ui_asset.text
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


def test_shadow_web_google_photos_status_route_is_sanitized(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/interpretation/google-photos/status")

    payload = response.json()
    google_photos = payload["normalized_payload"]["google_photos"]
    assert response.status_code == 200
    assert google_photos["api"] == "google_photos_picker"
    assert google_photos["connected"] is False
    assert google_photos["location_metadata_available"] is False
    assert "auth_url" not in google_photos
    assert "access_token" not in str(payload)
    assert "refresh_token" not in str(payload)


def test_shadow_web_google_photos_disconnect_clears_local_token_safely(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    token_path = tmp_path / "shadow" / "google-photos-token.json"
    diagnostic_path = tmp_path / "shadow" / "google_photos_picker_last_callback_diagnostic.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(
            {
                "google_photos_client_id": "test-client-id",
                "google_photos_token_path": str(token_path),
            }
        ),
        encoding="utf-8",
    )
    token_path.write_text(
        json.dumps({"access_token": "test-access-token", "refresh_token": "test-refresh-token", "expires_at": 9999999999}),
        encoding="utf-8",
    )
    diagnostic_path.write_text(json.dumps({"safe_failure_category": "connected"}), encoding="utf-8")

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post("/api/interpretation/google-photos/disconnect?mode=shadow&workspace=google-photos-review")
        status_response = client.get("/api/interpretation/google-photos/status?mode=shadow&workspace=google-photos-review")

    payload = response.json()
    google_photos = payload["normalized_payload"]["google_photos"]
    serialized = json.dumps(payload)
    status_payload = status_response.json()["normalized_payload"]["google_photos"]
    assert response.status_code == 200
    assert google_photos["connected"] is False
    assert google_photos["disconnected"] is True
    assert google_photos["token_deleted"] is True
    assert google_photos["callback_diagnostic_cleared"] is True
    assert google_photos["location_metadata_available"] is False
    assert not token_path.exists()
    assert not diagnostic_path.exists()
    assert status_payload["connected"] is False
    assert status_payload["last_callback_diagnostic"] == {}
    assert "test-access-token" not in serialized
    assert "test-refresh-token" not in serialized
    assert "auth_url" not in google_photos


def test_shadow_web_google_photos_connect_creates_pending_state_without_secrets(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": "test-client-id"}), encoding="utf-8")

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post("/api/interpretation/google-photos/connect?mode=shadow&workspace=google-photos-review")

    payload = response.json()
    google_photos = payload["normalized_payload"]["google_photos"]
    state = parse_qs(urlparse(google_photos["auth_url"]).query)["state"][0]
    pending_path = tmp_path / "shadow" / "google_photos_picker_pending_oauth_states.json"
    pending_raw = pending_path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert google_photos["scope"] == "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
    assert state not in pending_raw
    assert "access_token" not in pending_raw
    assert "refresh_token" not in pending_raw
    assert "configured" not in pending_raw


def test_shadow_web_google_photos_oauth_callback_consumes_state_and_rejects_replay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": "test-client-id"}), encoding="utf-8")
    calls: list[dict[str, object]] = []

    def fake_token_request(config, **kwargs):
        calls.append(dict(kwargs))
        return {"access_token": "test-access-token", "refresh_token": "test-refresh-token", "expires_in": 3600}

    monkeypatch.setattr(shadow_app_module, "request_google_photos_authorization_token", fake_token_request)

    with _build_app(tmp_path, monkeypatch) as client:
        connect_response = client.post("/api/interpretation/google-photos/connect?mode=shadow&workspace=google-photos-review")
        auth_url = connect_response.json()["normalized_payload"]["google_photos"]["auth_url"]
        state = parse_qs(urlparse(auth_url).query)["state"][0]
        callback_response = client.get(_google_photos_callback_url(state=state, code="authorization-code"))
        connected_status_response = client.get(
            "/api/interpretation/google-photos/status?mode=shadow&workspace=google-photos-review"
        )
        replay_response = client.get(_google_photos_callback_url(state=state, code="authorization-code"))
        replay_status_response = client.get(
            "/api/interpretation/google-photos/status?mode=shadow&workspace=google-photos-review"
        )

    pending_raw = (tmp_path / "shadow" / "google_photos_picker_pending_oauth_states.json").read_text(encoding="utf-8")
    assert callback_response.status_code == 200
    assert "Google Photos connected" in callback_response.text
    assert calls[0]["code"] == "authorization-code"
    assert replay_response.status_code == 400
    assert "state_invalid_or_expired" in replay_response.text
    assert state not in pending_raw
    token_raw = (tmp_path / "shadow" / "google_photos_picker_token.json").read_text(encoding="utf-8")
    assert "test-access-token" in token_raw
    diagnostic = connected_status_response.json()["normalized_payload"]["google_photos"]["last_callback_diagnostic"]
    assert diagnostic["safe_failure_category"] == "connected"
    assert diagnostic["state_verified"] is True
    assert diagnostic["token_path_same_for_callback_and_status"] is True
    replay_diagnostic = replay_status_response.json()["normalized_payload"]["google_photos"]["last_callback_diagnostic"]
    assert replay_diagnostic["safe_failure_category"] == "state_invalid_or_expired"


def test_shadow_web_google_photos_oauth_callback_rejects_missing_state(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get(_google_photos_callback_url(code="authorization-code"))

    assert response.status_code == 400
    assert "state_missing" in response.text


def test_shadow_web_google_photos_oauth_callback_reports_safe_failure_categories(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": "test-client-id"}), encoding="utf-8")

    with _build_app(tmp_path, monkeypatch) as client:
        connect_response = client.post("/api/interpretation/google-photos/connect?mode=shadow&workspace=diag-workspace")
        state = parse_qs(urlparse(connect_response.json()["normalized_payload"]["google_photos"]["auth_url"]).query)["state"][0]
        error_response = client.get(_google_photos_callback_url(state=state, error="access_denied"))
        status_response = client.get("/api/interpretation/google-photos/status?mode=shadow&workspace=diag-workspace")

    assert error_response.status_code == 400
    assert "oauth_error_param_present" in error_response.text
    diagnostic = status_response.json()["normalized_payload"]["google_photos"]["last_callback_diagnostic"]
    assert diagnostic["safe_failure_category"] == "oauth_error_param_present"
    assert diagnostic["oauth_error_param_present"] is True
    assert diagnostic["state_verified"] is True
    serialized = json.dumps(diagnostic)
    assert "access_denied" not in serialized
    assert "test-client-id" not in serialized
    assert state not in serialized


def test_shadow_web_google_photos_oauth_callback_reports_missing_code(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": "test-client-id"}), encoding="utf-8")

    with _build_app(tmp_path, monkeypatch) as client:
        connect_response = client.post("/api/interpretation/google-photos/connect?mode=shadow&workspace=diag-workspace")
        state = parse_qs(urlparse(connect_response.json()["normalized_payload"]["google_photos"]["auth_url"]).query)["state"][0]
        response = client.get(_google_photos_callback_url(state=state))
        diagnostic = client.get(
            "/api/interpretation/google-photos/status?mode=shadow&workspace=diag-workspace"
        ).json()["normalized_payload"]["google_photos"]["last_callback_diagnostic"]

    assert response.status_code == 400
    assert "code_missing" in response.text
    assert diagnostic["safe_failure_category"] == "code_missing"
    assert diagnostic["code_present"] is False


def test_shadow_web_google_photos_oauth_callback_maps_exchange_failure_without_leaking_body(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from legalpdf_translate.google_photos_oauth import GooglePhotosOAuthTokenExchangeError

    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": "test-client-id"}), encoding="utf-8")

    def fake_token_request(config, **kwargs):
        raise GooglePhotosOAuthTokenExchangeError("token_exchange_invalid_client")

    monkeypatch.setattr(shadow_app_module, "request_google_photos_authorization_token", fake_token_request)

    with _build_app(tmp_path, monkeypatch) as client:
        connect_response = client.post("/api/interpretation/google-photos/connect?mode=shadow&workspace=diag-workspace")
        state = parse_qs(urlparse(connect_response.json()["normalized_payload"]["google_photos"]["auth_url"]).query)["state"][0]
        response = client.get(_google_photos_callback_url(state=state, code="secret-code"))
        diagnostic = client.get(
            "/api/interpretation/google-photos/status?mode=shadow&workspace=diag-workspace"
        ).json()["normalized_payload"]["google_photos"]["last_callback_diagnostic"]

    assert response.status_code == 502
    assert "token_exchange_invalid_client" in response.text
    assert diagnostic["safe_failure_category"] == "token_exchange_invalid_client"
    assert diagnostic["token_exchange_attempted"] is True
    serialized = json.dumps(diagnostic)
    assert "secret-code" not in serialized
    assert "test-client-id" not in serialized


def test_shadow_web_google_photos_oauth_callback_detects_saved_token_but_empty_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "shadow" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": "test-client-id"}), encoding="utf-8")

    def fake_token_request(config, **kwargs):
        return {"expires_in": 3600}

    monkeypatch.setattr(shadow_app_module, "request_google_photos_authorization_token", fake_token_request)

    with _build_app(tmp_path, monkeypatch) as client:
        connect_response = client.post("/api/interpretation/google-photos/connect?mode=shadow&workspace=diag-workspace")
        state = parse_qs(urlparse(connect_response.json()["normalized_payload"]["google_photos"]["auth_url"]).query)["state"][0]
        response = client.get(_google_photos_callback_url(state=state, code="authorization-code"))
        diagnostic = client.get(
            "/api/interpretation/google-photos/status?mode=shadow&workspace=diag-workspace"
        ).json()["normalized_payload"]["google_photos"]["last_callback_diagnostic"]

    assert response.status_code == 400
    assert "token_saved_but_status_empty" in response.text
    assert diagnostic["safe_failure_category"] == "token_saved_but_status_empty"
    assert diagnostic["token_save_succeeded"] is True
    assert diagnostic["token_path_same_for_callback_and_status"] is True


def test_shadow_web_google_photos_session_route_uses_interpretation_service(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_create_session(**kwargs):
        return {
            "status": "ok",
            "normalized_payload": {
                "google_photos": {
                    "session": {
                        "session_id": "session-1",
                        "picker_uri": "https://picker.example.invalid/session-1",
                        "is_ready": False,
                        "media_items_set": False,
                    },
                    "location_metadata_available": False,
                }
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    monkeypatch.setattr(shadow_app_module, "create_google_photos_picker_session", fake_create_session)

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post("/api/interpretation/google-photos/session")

    payload = response.json()
    assert response.status_code == 200
    assert payload["normalized_payload"]["google_photos"]["session"]["session_id"] == "session-1"
    assert payload["normalized_payload"]["google_photos"]["location_metadata_available"] is False


def test_shadow_web_google_photos_delete_session_route_uses_interpretation_service(
    tmp_path: Path,
    monkeypatch,
) -> None:
    called: dict[str, object] = {}

    def fake_delete_session(**kwargs):
        called.update(kwargs)
        return {
            "status": "ok",
            "normalized_payload": {"google_photos": {"session_deleted": True}},
            "diagnostics": {},
            "capability_flags": {},
        }

    monkeypatch.setattr(shadow_app_module, "delete_google_photos_picker_session", fake_delete_session)

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.delete("/api/interpretation/google-photos/session/session-1")

    payload = response.json()
    assert response.status_code == 200
    assert called["session_id"] == "session-1"
    assert payload["normalized_payload"]["google_photos"]["session_deleted"] is True


def test_shadow_web_google_photos_import_route_stays_in_interpretation_flow(
    tmp_path: Path,
    monkeypatch,
) -> None:
    called: dict[str, object] = {}

    def fake_import(**kwargs):
        called.update(kwargs)
        return {
            "status": "ok",
            "normalized_payload": {
                "case_number": "69/26.8PBBBJA",
                "case_entity": "Ministerio Publico de Moura",
                "case_city": "Moura",
                "service_date": "",
                "court_email": "",
                "service_entity": "",
                "service_city": "",
                "travel_km_outbound": None,
                "travel_km_return": None,
                "use_service_location_in_honorarios": False,
                "include_transport_sentence_in_honorarios": True,
                "completed_at": "2026-04-27T10:00:00",
                "translation_date": "",
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
            "diagnostics": {
                "metadata_extraction": {"source": "google_photos_picker", "extracted_fields": ["case_city"]},
                "google_photos": {
                    "selected_photo": {
                        "selection_key": "safe-selection",
                        "source_filename": "notice.jpg",
                        "location_status": "unavailable",
                    }
                },
            },
            "capability_flags": {},
        }

    monkeypatch.setattr(shadow_app_module, "import_google_photos_selection", fake_import)

    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/google-photos/import",
            json={"session_id": "session-1", "selection_key": "safe-selection"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert called["session_id"] == "session-1"
    assert called["selection_key"] == "safe-selection"
    assert payload["normalized_payload"]["job_type"] == "Interpretation"
    assert payload["normalized_payload"]["case_city"] == "Moura"
    assert "translation_route" not in str(payload)


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


def test_shadow_web_add_interpretation_city_route_accepts_blank_distance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/cities/add",
            json={
                "field_name": "service_city",
                "city": "Aljustrel",
                "profile_id": "primary",
                "include_transport_sentence_in_honorarios": True,
                "travel_km_outbound": "",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["normalized_payload"]["city"] == "Aljustrel"
    assert payload["normalized_payload"]["profile_distance_summary"]["travel_distances_by_city"].get("Aljustrel") is None


def test_shadow_web_add_interpretation_city_route_rejects_explicit_bad_distance(
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
                "travel_km_outbound": "0",
            },
        )

    payload = response.json()
    assert response.status_code == 422
    assert payload["status"] == "failed"
    assert payload["diagnostics"]["validation_error"]["code"] == "distance_must_be_positive"
    assert payload["diagnostics"]["validation_error"]["city"] == "Serpa"


def test_shadow_web_add_interpretation_court_email_route_updates_city_options(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/interpretation/court-emails/add",
            json={
                "city": "Beja",
                "email": "beja.novo@tribunais.org.pt",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["normalized_payload"]["city"] == "Beja"
    assert payload["normalized_payload"]["email"] == "beja.novo@tribunais.org.pt"
    assert "beja.novo@tribunais.org.pt" in (
        payload["normalized_payload"]["interpretation_reference"]["court_email_options_by_city"]["Beja"]
    )
