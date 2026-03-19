from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
from zipfile import ZipFile

import legalpdf_translate.browser_app_service as browser_app_service
import legalpdf_translate.interpretation_service as interpretation_service
import legalpdf_translate.power_tools_service as power_tools_service
import legalpdf_translate.shadow_runtime as shadow_runtime
import legalpdf_translate.translation_service as translation_service
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.joblog_db import list_job_runs, open_job_log
from legalpdf_translate.metadata_autofill import (
    MetadataExtractionDiagnostics,
    MetadataExtractionResult,
    MetadataSuggestion,
)
from legalpdf_translate.user_settings import load_gui_settings_from_path, load_joblog_settings_from_path
from legalpdf_translate.user_profile import distance_for_city, primary_profile
from legalpdf_translate.user_settings import load_profile_settings_from_path


def _identity(*, head_sha: str = "abc1234") -> RuntimeBuildIdentity:
    return RuntimeBuildIdentity(
        worktree_path="C:/Users/FA507/.codex/legalpdf_translate_beginner_first_ux",
        branch="codex/beginner-first-primary-flow-ux",
        head_sha=head_sha,
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


def test_shadow_build_key_is_isolated_but_stable_across_head_updates(tmp_path: Path) -> None:
    first = shadow_runtime.shadow_build_key(_identity(head_sha="abc1234"))
    second = shadow_runtime.shadow_build_key(_identity(head_sha="def5678"))
    assert first == second

    paths = shadow_runtime.detect_shadow_runtime_paths(
        identity=_identity(),
        appdata_root=tmp_path,
    )
    assert paths.settings_path == paths.app_data_dir / "settings.json"
    assert paths.job_log_db_path == paths.app_data_dir / "job_log.sqlite3"
    assert "LegalPDFTranslateShadow" in str(paths.app_data_dir)


def test_detect_browser_data_paths_live_uses_selected_settings_root(tmp_path: Path, monkeypatch) -> None:
    live_settings = tmp_path / "live" / "settings.json"
    live_settings.parent.mkdir(parents=True, exist_ok=True)
    live_outdir = tmp_path / "chosen-live-outdir"
    live_settings.write_text(json.dumps({"default_outdir": str(live_outdir)}), encoding="utf-8")
    monkeypatch.setattr(shadow_runtime, "live_settings_path", lambda: live_settings)

    paths = shadow_runtime.detect_browser_data_paths(mode="live")

    assert paths.mode == "live"
    assert paths.live_data is True
    assert paths.settings_path == live_settings.resolve()
    assert paths.job_log_db_path == live_settings.resolve().with_name("job_log.sqlite3")
    assert paths.outputs_dir == live_outdir.resolve()


def test_classify_shadow_listener_reports_self_or_other(monkeypatch) -> None:
    monkeypatch.setattr(shadow_runtime, "detect_listener_pid", lambda port: 4242)
    unavailable = shadow_runtime.classify_shadow_listener(port=8877)
    assert unavailable.status == "unavailable"
    assert unavailable.pid == 4242

    owned = shadow_runtime.classify_shadow_listener(port=8877, expected_pid=4242)
    assert owned.status == "owned_by_self"
    assert owned.pid == 4242


def test_autofill_interpretation_notification_pdf_returns_seed_and_diagnostics(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")

    extraction = MetadataExtractionResult(
        suggestion=MetadataSuggestion(
            case_entity="Tribunal do Trabalho",
            case_city="Beja",
            case_number="1095/25.0T8BJA",
            court_email="beja.trabalho.ministeriopublico@tribunais.org.pt",
            service_date="2026-02-26",
        ),
        diagnostics=MetadataExtractionDiagnostics(
            page_numbers=(1,),
            ocr_attempted_pages=(1,),
            ocr_attempted=True,
            api_ocr_configured=True,
            extracted_fields=("case_entity", "case_city", "case_number", "service_date"),
        ),
    )
    monkeypatch.setattr(
        interpretation_service,
        "extract_interpretation_notification_metadata_from_pdf_with_diagnostics",
        lambda *args, **kwargs: extraction,
    )

    response = interpretation_service.autofill_interpretation_from_notification_pdf(
        pdf_path=pdf_path,
        settings_path=settings_file,
    )

    assert response["status"] == "ok"
    assert response["normalized_payload"]["case_number"] == "1095/25.0T8BJA"
    assert response["normalized_payload"]["service_date"] == "2026-02-26"
    assert response["diagnostics"]["metadata_extraction"]["ocr_attempted"] is True


def test_browser_bootstrap_includes_stage_one_shell_sections(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    db_path = tmp_path / "shadow" / "job_log.sqlite3"
    data_paths = shadow_runtime.BrowserDataPaths(
        mode="shadow",
        label="Isolated Test Data",
        app_data_dir=settings_file.parent,
        settings_path=settings_file,
        job_log_db_path=db_path,
        outputs_dir=settings_file.parent / "outputs",
        live_data=False,
        banner_text="",
    )
    monkeypatch.setattr(
        browser_app_service,
        "build_extension_lab_summary",
        lambda **kwargs: {
            "prepare_response": {"ok": False, "reason": "bridge_disabled", "autoLaunchReady": False},
            "extension_report": {"stable_extension_id": "abc", "active_extension_ids": [], "stale_extension_ids": []},
            "simulator_defaults": {"message_id": "m1", "thread_id": "t1", "subject": "hello", "account_email": ""},
            "notes": ["Shadow mode"],
        },
    )

    response = browser_app_service.build_browser_bootstrap(data_paths=data_paths)

    assert response["status"] == "ok"
    assert response["normalized_payload"]["runtime_mode"]["current_mode"] == "shadow"
    assert any(item["id"] == "extension-lab" for item in response["normalized_payload"]["navigation"])
    assert any(card["id"] == "translation" for card in response["normalized_payload"]["dashboard_cards"])
    assert response["normalized_payload"]["parity_audit"]["promotion_recommendation"]["status"] == "ready_for_daily_use"


def test_extension_lab_summary_marks_isolated_shadow_bridge_as_info_when_live_desktop_is_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    shadow_settings = tmp_path / "shadow" / "settings.json"
    live_settings = tmp_path / "live" / "settings.json"
    shadow_settings.parent.mkdir(parents=True, exist_ok=True)
    live_settings.parent.mkdir(parents=True, exist_ok=True)
    shadow_settings.write_text(json.dumps({"gmail_intake_bridge_enabled": False}), encoding="utf-8")
    live_settings.write_text(
        json.dumps(
            {
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_port": 8765,
                "gmail_account_email": "adel.belghali@gmail.com",
            }
        ),
        encoding="utf-8",
    )
    shadow_paths = shadow_runtime.BrowserDataPaths(
        mode="shadow",
        label="Isolated Test Data",
        app_data_dir=shadow_settings.parent,
        settings_path=shadow_settings,
        job_log_db_path=shadow_settings.with_name("job_log.sqlite3"),
        outputs_dir=shadow_settings.parent / "outputs",
        live_data=False,
        banner_text="",
    )
    live_paths = shadow_runtime.BrowserDataPaths(
        mode="live",
        label="Live App Data",
        app_data_dir=live_settings.parent,
        settings_path=live_settings,
        job_log_db_path=live_settings.with_name("job_log.sqlite3"),
        outputs_dir=live_settings.parent / "outputs",
        live_data=True,
        banner_text="LIVE APP DATA",
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

    response = browser_app_service.build_extension_lab_summary(data_paths=shadow_paths)

    assert response["bridge_summary"]["status"] == "info"
    assert response["bridge_summary"]["message"] == "Disabled in isolated test mode; the live app Gmail bridge is ready."
    assert response["bridge_context"]["shadow_isolation_active"] is True
    assert response["bridge_context"]["live_desktop_ready_while_shadow_disabled"] is True
    assert response["bridge_context"]["current_mode"]["bridge_enabled"] is False
    assert response["bridge_context"]["live_desktop"]["ready"] is True


def test_power_tools_bootstrap_and_settings_save_persist_to_runtime_paths(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    data_paths = shadow_runtime.BrowserDataPaths(
        mode="shadow",
        label="Isolated Test Data",
        app_data_dir=settings_file.parent,
        settings_path=settings_file,
        job_log_db_path=settings_file.with_name("job_log.sqlite3"),
        outputs_dir=settings_file.parent / "outputs",
        live_data=False,
        banner_text="",
    )
    data_paths.outputs_dir.mkdir(parents=True, exist_ok=True)

    initial = power_tools_service.build_power_tools_bootstrap(data_paths=data_paths)
    assert "settings_admin" in initial
    assert "power_tools" in initial
    assert initial["power_tools"]["glossary_builder"]["defaults"]["source_mode"] == "run_folders"

    saved = power_tools_service.save_browser_settings(
        settings_path=settings_file,
        values={
            "default_lang": "FR",
            "default_effort": "xhigh",
            "default_effort_policy": "fixed_xhigh",
            "default_images_mode": "always",
            "default_workers": 4,
            "ocr_mode_default": "always",
            "ocr_engine_default": "api",
            "ocr_api_provider": "openai",
            "ocr_api_provider_default": "openai",
            "default_rate_per_word": {"FR": 0.09},
            "service_equals_case_by_default": False,
        },
    )

    assert saved["status"] == "ok"
    assert saved["normalized_payload"]["form_values"]["default_lang"] == "FR"
    assert saved["normalized_payload"]["form_values"]["ocr_api_key_env_name"] == "OPENAI_API_KEY"

    gui = load_gui_settings_from_path(settings_file)
    joblog = load_joblog_settings_from_path(settings_file)
    assert gui["default_lang"] == "FR"
    assert gui["ocr_engine_default"] == "api"
    assert joblog["default_rate_per_word"]["FR"] == 0.09
    assert joblog["service_equals_case_by_default"] is False


def test_run_browser_calibration_audit_uses_parsed_enum_settings(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    power_tools_service.save_browser_settings(
        settings_path=settings_file,
        values={
            "default_lang": "AR",
            "default_effort": "xhigh",
            "default_effort_policy": "fixed_xhigh",
            "default_images_mode": "always",
            "default_workers": 2,
            "ocr_mode_default": "always",
            "ocr_engine_default": "api",
            "ocr_api_provider": "openai",
            "ocr_api_provider_default": "openai",
        },
    )
    pdf_path = tmp_path / "audit.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")
    (tmp_path / "audit").mkdir(parents=True, exist_ok=True)
    captured: dict[str, object] = {}

    def _fake_run_calibration_audit(**kwargs):
        captured["config"] = kwargs["config"]
        return {
            "report": {"grade": "ok"},
            "suggestions": [{"key": "effort"}],
            "report_json_path": tmp_path / "audit" / "calibration_report.json",
            "report_md_path": tmp_path / "audit" / "calibration_report.md",
            "suggestions_json_path": tmp_path / "audit" / "calibration_suggestions.json",
        }

    monkeypatch.setattr(power_tools_service, "run_calibration_audit", _fake_run_calibration_audit)

    response = power_tools_service.run_browser_calibration_audit(
        settings_path=settings_file,
        pdf_path_text=str(pdf_path),
        output_dir_text=str(tmp_path / "audit"),
        target_lang="AR",
        sample_pages=3,
        user_seed="focused terminology",
        include_excerpts=True,
        excerpt_max_chars=180,
    )

    assert response["status"] == "ok"
    config = captured["config"]
    assert config.effort.value == "xhigh"
    assert config.effort_policy.value == "fixed_xhigh"
    assert config.image_mode.value == "always"
    assert config.ocr_mode.value == "always"
    assert config.ocr_engine.value == "api"
    assert config.target_lang.value == "AR"


def test_create_browser_debug_bundle_includes_selected_run_files(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    outputs_dir = tmp_path / "shadow" / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    power_tools_service.save_browser_settings(settings_path=settings_file, values={})

    runtime_metadata_path = tmp_path / "shadow" / "shadow_runtime.json"
    runtime_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_metadata_path.write_text(json.dumps({"listener": "127.0.0.1:8877"}), encoding="utf-8")

    run_dir = outputs_dir / "run_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run_summary.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    response = power_tools_service.create_browser_debug_bundle(
        settings_path=settings_file,
        outputs_dir=outputs_dir,
        runtime_metadata_path=runtime_metadata_path,
        selected_run_dir_text=str(run_dir),
    )

    bundle_path = Path(response["normalized_payload"]["bundle_path"])
    assert response["status"] == "ok"
    assert bundle_path.exists()
    with ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
    assert "settings_snapshot.json" in names
    assert "run_summary.json" in names
    assert "shadow_runtime.json" in names


def test_shadow_bootstrap_blank_seed_leaves_service_date_empty(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    db_path = tmp_path / "shadow" / "job_log.sqlite3"

    response = interpretation_service.build_shadow_bootstrap(
        settings_path=settings_file,
        job_log_db_path=db_path,
    )

    assert response["status"] == "ok"
    assert response["normalized_payload"]["blank_seed"]["service_date"] == ""


def test_save_interpretation_row_persists_to_isolated_settings_and_joblog(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    db_path = tmp_path / "shadow" / "job_log.sqlite3"

    response = interpretation_service.save_interpretation_row(
        settings_path=settings_file,
        job_log_db_path=db_path,
        form_values={
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
        service_same_checked=True,
        include_transport_sentence_in_honorarios_checked=True,
    )

    assert response["status"] == "ok"
    assert response["saved_result"]["row_id"] > 0

    with closing(open_job_log(db_path)) as conn:
        rows = list_job_runs(conn, limit=5)
    assert len(rows) == 1
    assert rows[0]["job_type"] == "Interpretation"
    assert rows[0]["service_date"] == "2026-02-26"

    profiles, primary_profile_id = load_profile_settings_from_path(settings_file)
    profile = primary_profile(profiles, primary_profile_id)
    assert distance_for_city(profile, "Beja") == 39.0


def test_browser_profile_management_and_joblog_delete_helpers(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    db_path = tmp_path / "shadow" / "job_log.sqlite3"

    saved = browser_app_service.save_browser_profile(
        settings_path=settings_file,
        profile_payload={
            "first_name": "Test",
            "last_name": "Profile",
            "document_name_override": "Test Profile",
            "email": "test@example.com",
            "phone_number": "+351000000000",
            "postal_address": "Rua Exemplo",
            "iban": "PT50003506490000832760029",
            "iva_text": "23%",
            "irs_text": "Sem retenção",
            "travel_origin_label": "Beja",
            "travel_distances_by_city": {"Cuba": 26},
        },
        make_primary=True,
    )
    saved_profile = saved["normalized_payload"]["saved_profile"]
    assert saved["status"] == "ok"
    assert saved["normalized_payload"]["profile_summary"]["primary_profile_id"] == saved_profile["id"]

    promoted = browser_app_service.set_browser_primary_profile(
        settings_path=settings_file,
        profile_id="primary",
    )
    assert promoted["status"] == "ok"
    assert promoted["normalized_payload"]["profile_summary"]["primary_profile_id"] == "primary"

    interpretation_service.save_interpretation_row(
        settings_path=settings_file,
        job_log_db_path=db_path,
        form_values={
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
        service_same_checked=True,
        include_transport_sentence_in_honorarios_checked=True,
    )
    with closing(open_job_log(db_path)) as conn:
        row = list_job_runs(conn, limit=1)[0]
    deleted = browser_app_service.delete_browser_joblog_rows(db_path=db_path, row_ids=[int(row["id"])])
    assert deleted["status"] == "ok"
    assert deleted["normalized_payload"]["deleted_count"] == 1

    removed = browser_app_service.delete_browser_profile(
        settings_path=settings_file,
        profile_id=saved_profile["id"],
    )
    assert removed["status"] == "ok"
    assert removed["normalized_payload"]["deleted_profile_id"] == saved_profile["id"]


def test_translation_bootstrap_filters_interpretation_rows_and_keeps_active_jobs(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    db_path = tmp_path / "shadow" / "job_log.sqlite3"
    outputs_dir = tmp_path / "shadow" / "outputs"

    interpretation_service.save_interpretation_row(
        settings_path=settings_file,
        job_log_db_path=db_path,
        form_values={
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
        service_same_checked=True,
        include_transport_sentence_in_honorarios_checked=True,
    )
    translation_service.save_translation_row(
        settings_path=settings_file,
        job_log_db_path=db_path,
        form_values={
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
        },
    )

    response = translation_service.build_translation_bootstrap(
        settings_path=settings_file,
        job_log_db_path=db_path,
        outputs_dir=outputs_dir,
        active_jobs=[{"job_id": "tx-123", "status": "running"}],
        history_limit=20,
    )

    assert response["status"] == "ok"
    assert response["normalized_payload"]["active_jobs"] == [{"job_id": "tx-123", "status": "running"}]
    assert response["normalized_payload"]["defaults"]["output_dir"] == str(outputs_dir.resolve())
    assert len(response["normalized_payload"]["history"]) == 1
    assert response["normalized_payload"]["history"][0]["row"]["job_type"] == "Translation"
    assert response["normalized_payload"]["history"][0]["seed"]["run_id"] == "run-456"


def test_upload_translation_source_reports_saved_file_metadata(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.7\n%browser-stage-2\n")
    monkeypatch.setattr(translation_service, "get_source_page_count", lambda path: 4)

    response = translation_service.upload_translation_source(
        source_path=source_path,
        settings_path=settings_file,
    )

    assert response["status"] == "ok"
    assert response["normalized_payload"]["source_filename"] == "source.pdf"
    assert response["normalized_payload"]["source_type"] == "pdf"
    assert response["normalized_payload"]["page_count"] == 4
    assert response["normalized_payload"]["source_path"] == str(source_path.resolve())


def test_save_translation_row_accepts_partial_browser_seed_payload(tmp_path: Path) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    db_path = tmp_path / "shadow" / "job_log.sqlite3"

    response = translation_service.save_translation_row(
        settings_path=settings_file,
        job_log_db_path=db_path,
        form_values={
            "translation_date": "2026-03-18",
            "case_number": "456/26.0T8LSB",
            "case_entity": "Tribunal Base",
            "case_city": "Beja",
            "target_lang": "EN",
            "pages": "1",
            "word_count": "100",
            "rate_per_word": "0.08",
            "expected_total": "8",
            "amount_paid": "0",
            "api_cost": "0",
            "profit": "8",
        },
        seed_payload={
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
    )

    assert response["status"] == "ok"
    assert response["saved_result"]["row_id"] > 0
    assert response["normalized_payload"]["case_number"] == "456/26.0T8LSB"


def test_export_interpretation_honorarios_reports_local_only_when_pdf_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    outputs_dir = tmp_path / "shadow" / "outputs"

    def _fake_generate(draft, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"docx")
        return output_path

    monkeypatch.setattr(interpretation_service, "generate_honorarios_docx", _fake_generate)
    monkeypatch.setattr(
        interpretation_service,
        "_run_pdf_export_with_retry",
        lambda **kwargs: {
            "docx_path": str(kwargs["docx_path"]),
            "pdf_path": None,
            "ok": False,
            "failure_code": "timeout",
            "failure_message": "Word PDF export timed out.",
            "failure_details": "",
            "elapsed_ms": 45000,
        },
    )

    response = interpretation_service.export_interpretation_honorarios(
        settings_path=settings_file,
        outputs_dir=outputs_dir,
        form_values={
            "case_number": "1095/25.0T8BJA",
            "case_entity": "Tribunal do Trabalho",
            "case_city": "Beja",
            "service_entity": "Tribunal do Trabalho",
            "service_city": "Beja",
            "service_date": "2026-02-26",
            "travel_km_outbound": "39",
            "recipient_block": "",
            "include_transport_sentence_in_honorarios": True,
            "use_service_location_in_honorarios": False,
        },
    )

    assert response["status"] == "local_only"
    assert Path(response["normalized_payload"]["docx_path"]).exists()
    assert response["diagnostics"]["pdf_export"]["failure_code"] == "timeout"


def test_simulate_extension_handoff_requires_message_and_thread_ids(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    data_paths = shadow_runtime.BrowserDataPaths(
        mode="shadow",
        label="Isolated Test Data",
        app_data_dir=settings_file.parent,
        settings_path=settings_file,
        job_log_db_path=settings_file.with_name("job_log.sqlite3"),
        outputs_dir=settings_file.parent / "outputs",
        live_data=False,
        banner_text="",
    )
    monkeypatch.setattr(
        browser_app_service,
        "prepare_gmail_intake",
        lambda **kwargs: {"ok": False, "reason": "bridge_disabled", "bridgePort": None},
    )
    monkeypatch.setattr(
        browser_app_service,
        "build_edge_extension_report",
        lambda **kwargs: {"stable_extension_id": "abc", "active_extension_ids": [], "stale_extension_ids": []},
    )

    try:
        browser_app_service.simulate_extension_handoff(
            data_paths=data_paths,
            context_payload={"message_id": "m1", "thread_id": "", "subject": "hello"},
        )
    except ValueError as exc:
        assert "thread_id" in str(exc)
    else:
        raise AssertionError("simulate_extension_handoff should require thread_id")


def test_export_interpretation_honorarios_uses_case_location_when_service_same_checked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings_file = tmp_path / "shadow" / "settings.json"
    outputs_dir = tmp_path / "shadow" / "outputs"
    captured: dict[str, object] = {}

    def _fake_generate(draft, output_path: Path) -> Path:
        captured["draft"] = draft
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"docx")
        return output_path

    def _fake_pdf_export(**kwargs):
        pdf_path = kwargs["pdf_path"]
        pdf_path.write_bytes(b"pdf")
        return {
            "docx_path": str(kwargs["docx_path"]),
            "pdf_path": str(pdf_path),
            "ok": True,
            "failure_code": "",
            "failure_message": "",
            "failure_details": "",
            "elapsed_ms": 10,
        }

    monkeypatch.setattr(interpretation_service, "generate_honorarios_docx", _fake_generate)
    monkeypatch.setattr(interpretation_service, "_run_pdf_export_with_retry", _fake_pdf_export)

    response = interpretation_service.export_interpretation_honorarios(
        settings_path=settings_file,
        outputs_dir=outputs_dir,
        form_values={
            "case_number": "1095/25.0T8BJA",
            "case_entity": "Tribunal do Trabalho",
            "case_city": "Beja",
            "service_entity": "",
            "service_city": "",
            "service_date": "2026-02-26",
            "travel_km_outbound": "39",
            "recipient_block": "",
            "include_transport_sentence_in_honorarios": True,
            "use_service_location_in_honorarios": False,
        },
        service_same_checked=True,
    )

    assert response["status"] == "ok"
    draft = captured["draft"]
    assert draft.service_entity == "Tribunal do Trabalho"
    assert draft.service_city == "Beja"
