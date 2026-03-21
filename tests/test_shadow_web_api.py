from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import legalpdf_translate.browser_app_service as browser_app_service
import legalpdf_translate.shadow_web.app as shadow_app_module
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.shadow_runtime import BrowserDataPaths, ShadowRuntimePaths
from legalpdf_translate.word_automation import WordAutomationResult


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


def _build_app(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(shadow_app_module, "detect_runtime_build_identity", lambda **kwargs: _identity())
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
    app = shadow_app_module.create_shadow_app(repo_root=tmp_path, port=8877, enable_live_gmail_bridge=False)
    return TestClient(app)


def test_shadow_web_bootstrap_and_save_row_flow(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
        bootstrap = client.get("/api/bootstrap")
        assert bootstrap.status_code == 200
        bootstrap_payload = bootstrap.json()
        assert bootstrap_payload["status"] == "ok"
        assert bootstrap_payload["normalized_payload"]["runtime"]["port"] == 8877
        assert bootstrap_payload["normalized_payload"]["runtime"]["runtime_mode"] == "live"
        assert bootstrap_payload["normalized_payload"]["blank_seed"]["service_date"] == ""
        assert any(item["id"] == "gmail-intake" for item in bootstrap_payload["normalized_payload"]["navigation"])
        assert any(item["id"] == "extension-lab" for item in bootstrap_payload["normalized_payload"]["navigation"])
        assert any(item["id"] == "power-tools" for item in bootstrap_payload["normalized_payload"]["navigation"])
        assert "settings_admin" in bootstrap_payload["normalized_payload"]
        assert "power_tools" in bootstrap_payload["normalized_payload"]
        assert bootstrap_payload["normalized_payload"]["parity_audit"]["promotion_recommendation"]["status"] == "ready_for_daily_use"

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
    with _build_app(tmp_path, monkeypatch) as client:
        response = client.get("/")
        assert response.status_code == 200
        text = response.text
        assert 'defaultRuntimeMode: "live"' in text
        assert 'defaultUiVariant: "qt"' in text
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
        assert 'id="gmail-open-session"' in text
        assert 'id="gmail-preview-session"' in text
        assert 'id="gmail-session-banner"' in text
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
        assert "Finish Translation" in text
        assert "Completion Surface" in text
        assert "Export Review Queue" in text
        assert "Run Metrics (auto-filled)" in text
        assert "Amounts (EUR)" in text
        assert "Interpretation Intake" in text
        assert "Seed Review" in text
        assert 'id="interpretation-open-review"' in text
        assert 'id="interpretation-review-drawer"' in text
        assert 'id="interpretation-review-drawer-backdrop"' in text
        assert 'id="interpretation-open-gmail-session"' in text
        assert "SERVICE" in text
        assert "RECIPIENT" in text
        assert "Continue In Translation" in text
        assert "Continue In Interpretation" in text
        assert "Open Session Actions" in text
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


def test_shadow_web_index_supports_legacy_ui_flag(tmp_path: Path, monkeypatch) -> None:
    with _build_app(tmp_path, monkeypatch) as client:
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
        assert payload["normalized_payload"]["extension_lab"]["prepare_reason_catalog"]


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
        shadow_app_module,
        "probe_word_pdf_export_support",
        lambda **kwargs: WordAutomationResult(
            ok=True,
            action="probe",
            message="Word PDF export is ready.",
            failure_code="",
            details="",
        ),
    )

    with _build_app(tmp_path, monkeypatch) as client:
        bootstrap = client.get("/api/bootstrap", params={"mode": "shadow"})
        capabilities = client.get("/api/capabilities", params={"mode": "shadow"})
        bootstrap_payload = bootstrap.json()
        capabilities_payload = capabilities.json()

        assert bootstrap.status_code == 200
        assert capabilities.status_code == 200
        assert bootstrap_payload["capability_flags"]["word_pdf_export"]["preflight"]["ok"] is True
        assert capabilities_payload["capability_flags"]["word_pdf_export"]["preflight"]["ok"] is True
        assert bootstrap_payload["capability_flags"]["browser_automation"] == capabilities_payload["capability_flags"]["browser_automation"]
        assert bootstrap_payload["capability_flags"]["gmail_bridge"]["status"] == "info"
        assert capabilities_payload["capability_flags"]["gmail_bridge"]["status"] == "info"
        assert bootstrap_payload["capability_flags"]["gmail_bridge"]["message"] == "Disabled in isolated test mode; the live app Gmail bridge is ready."
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

    def _build_bootstrap(self, *, runtime_mode, workspace_id, settings_path, outputs_dir):
        recorded["build_bootstrap"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "outputs_dir": str(outputs_dir),
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "defaults": {"message_context": {}, "default_output_dir": str(outputs_dir)},
                "active_session": {"kind": "translation", "completed": False},
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "load_message", _load_message)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "prepare_session", _prepare_session)
    monkeypatch.setattr(shadow_app_module.GmailBrowserSessionManager, "build_bootstrap", _build_bootstrap)

    with _build_app(tmp_path, monkeypatch) as client:
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

    def _finalize_batch(self, *, runtime_mode, workspace_id, settings_path, output_filename, profile_id):
        recorded["finalize_batch"] = {
            "runtime_mode": runtime_mode,
            "workspace_id": workspace_id,
            "settings_path": str(settings_path),
            "output_filename": output_filename,
            "profile_id": profile_id,
        }
        return {
            "status": "ok",
            "normalized_payload": {
                "docx_path": "C:/tmp/honorarios.docx",
                "pdf_path": "C:/tmp/honorarios.pdf",
                "active_session": {"kind": "translation", "completed": True},
                "gmail_draft_result": {"ok": True, "message": "Draft ready"},
            },
            "diagnostics": {"pdf_export": {"ok": True}},
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
        assert recorded["finalize_batch"]["output_filename"] == "gmail_batch.docx"

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
        assert recorded["attachment_file"]["attachment_id"] == "att-1"


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


def test_shadow_web_settings_and_power_tools_routes(tmp_path: Path, monkeypatch) -> None:
    def _fake_power_bootstrap(*, data_paths, runtime_metadata_path=None):
        return {
            "settings_admin": {
                "form_values": {"default_lang": "EN", "ocr_api_provider": "openai"},
                "provider_state": {"ocr": {"provider": "openai", "api_configured": True}},
            },
            "power_tools": {
                "glossary": {"project_glossary_path": str(data_paths.app_data_dir / "project.json")},
                "glossary_builder": {"defaults": {"source_mode": "run_folders"}, "latest_run_dirs": []},
                "calibration": {"defaults": {"target_lang": "EN"}},
                "diagnostics": {"outputs_root": str(data_paths.outputs_dir), "latest_run_dirs": []},
            },
        }

    monkeypatch.setattr(shadow_app_module, "build_power_tools_bootstrap", _fake_power_bootstrap)
    monkeypatch.setattr(
        shadow_app_module,
        "save_browser_settings",
        lambda **kwargs: {
            "status": "ok",
            "normalized_payload": {"saved": True, "form_values": {"default_lang": "FR"}},
            "diagnostics": {"provider_state": {"ocr": {"provider": "openai", "api_configured": True}}},
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

        settings_save = client.post("/api/settings/save", json={"form_values": {"default_lang": "FR"}})
        save_payload = settings_save.json()
        assert settings_save.status_code == 200
        assert save_payload["normalized_payload"]["saved"] is True
        assert save_payload["normalized_payload"]["form_values"]["default_lang"] == "FR"

        power_bootstrap = client.get("/api/power-tools/bootstrap")
        power_payload = power_bootstrap.json()
        assert power_bootstrap.status_code == 200
        assert power_payload["normalized_payload"]["glossary_builder"]["defaults"]["source_mode"] == "run_folders"

        debug_bundle = client.post("/api/power-tools/diagnostics/debug-bundle", json={"run_dir": "C:/tmp/run-1"})
        bundle_payload = debug_bundle.json()
        assert debug_bundle.status_code == 200
        assert bundle_payload["normalized_payload"]["bundle_path"].endswith(".zip")


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
            "normalized_payload": {"report_path": "C:/tmp/run_report.md", "preview": "# report"},
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
        assert report_payload["normalized_payload"]["report_path"] == "C:/tmp/run_report.md"
        assert recorded["report"]["run_dir_text"] == "C:/tmp/run-5"


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
                },
            },
        )
        start_payload = start.json()
        assert start.status_code == 200
        assert start_payload["normalized_payload"]["job"]["job_id"] == "tx-stage2"
        assert recorded["start_translate"]["runtime_mode"] == "live"
        assert recorded["start_translate"]["workspace_id"] == "ws-live"

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
        lambda **kwargs: (_ for _ in ()).throw(ValueError("Service date is required.")),
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
    assert payload["diagnostics"]["error"] == "Service date is required."
