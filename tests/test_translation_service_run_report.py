from __future__ import annotations

import json
from pathlib import Path

import pytest

import legalpdf_translate.translation_service as translation_service_module
from legalpdf_translate.translation_service import TranslationJobManager, _ManagedTranslationJob


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_translation_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "sample_AR_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("sample page", encoding="utf-8")
    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260405_130851",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-04-05T13:11:16+00:00",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "AR",
            "total_pages": 1,
            "max_pages_effective": 1,
            "selection_start_page": 1,
            "selection_end_page": 1,
            "settings": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "keep_intermediates": False,
                "resume": True,
            },
            "pages": {
                "1": {
                    "status": "done",
                    "source_route": "ocr",
                    "source_route_reason": "ocr_success",
                    "image_used": False,
                    "image_decision_reason": "ocr_success_text_sufficient",
                    "ocr_requested": True,
                    "ocr_request_reason": "required",
                    "ocr_used": True,
                    "ocr_provider_configured": True,
                    "ocr_engine_used": "api",
                    "ocr_failed_reason": "",
                    "wall_seconds": 10.5,
                    "extract_seconds": 0.1,
                    "ocr_seconds": 3.2,
                    "translate_seconds": 7.0,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 100,
                    "output_tokens": 120,
                    "reasoning_tokens": 30,
                    "total_tokens": 250,
                    "estimated_cost": 0.01,
                    "exception_class": "",
                    "error": "",
                    "retry_reason": "",
                }
            },
        },
    )
    _write_json(
        run_dir / "run_summary.json",
        {
            "run_id": "20260405_130851",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "AR",
            "run_status": "completed",
            "halt_reason": "",
            "image_mode": "auto",
            "pipeline": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "ocr_requested": True,
                "ocr_used": True,
                "ocr_provider_configured": True,
                "ocr_requested_pages": 1,
                "ocr_used_pages": 1,
                "ocr_required_pages": 1,
                "ocr_helpful_pages": 0,
                "ocr_preflight_checked": True,
            },
            "totals": {
                "total_wall_seconds": 10.5,
                "total_cost_estimate_if_available": 0.01,
                "total_input_tokens": 100,
                "total_output_tokens": 120,
                "total_reasoning_tokens": 30,
                "total_tokens": 250,
            },
            "counts": {
                "pages_with_images": 0,
                "pages_with_retries": 0,
                "pages_failed": 0,
                "rate_limit_hits": 0,
                "transport_retries_total": 0,
            },
            "quality_risk_score": 0.2,
            "review_queue_count": 0,
            "review_queue": [],
        },
    )
    (run_dir / "run_events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-05T12:08:51+00:00",
                        "event_type": "run_started",
                        "stage": "run",
                        "page_index": None,
                        "duration_ms": None,
                        "counters": {},
                        "decisions": {},
                        "warning": None,
                        "error": None,
                        "details": {},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-05T12:11:16+00:00",
                        "event_type": "run_completed",
                        "stage": "run",
                        "page_index": None,
                        "duration_ms": None,
                        "counters": {},
                        "decisions": {},
                        "warning": None,
                        "error": None,
                        "details": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return run_dir


def test_translation_job_manager_generates_stable_run_report_artifact(tmp_path: Path) -> None:
    run_dir = _seed_translation_run_dir(tmp_path)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    manager = TranslationJobManager()
    manager._jobs["tx-1"] = _ManagedTranslationJob(
        job_id="tx-1",
        job_kind="translate",
        runtime_mode="live",
        workspace_id="gmail-intake",
        created_at="2026-04-05T13:08:51+00:00",
        updated_at="2026-04-05T13:11:16+00:00",
        status="completed",
        status_text="Translation complete",
        config_payload={},
        progress_payload={},
        diagnostics_payload={"kind": "translate"},
        result_payload={"artifacts": {"run_dir": str(run_dir), "run_report_path": None}},
        artifacts_payload={"run_dir": str(run_dir)},
    )

    first = manager.generate_run_report(job_id="tx-1", settings_path=settings_path)
    second = manager.generate_run_report(job_id="tx-1", settings_path=settings_path)

    report_path = run_dir / "run_report.md"
    assert report_path.exists()
    assert first["normalized_payload"]["report_path"] == str(report_path.resolve())
    assert second["normalized_payload"]["report_path"] == str(report_path.resolve())
    assert first["normalized_payload"]["job"]["actions"]["download_run_report"] is True
    assert first["normalized_payload"]["job"]["artifacts"]["run_report_path"] == str(report_path.resolve())
    assert (
        first["normalized_payload"]["job"]["result"]["artifacts"]["run_report_path"]
        == str(report_path.resolve())
    )
    assert (
        second["normalized_payload"]["job"]["result"]["artifacts"]["run_report_path"]
        == str(report_path.resolve())
    )
    report_text = report_path.read_text(encoding="utf-8")
    assert "## Summary" in report_text
    assert "## Timeline" in report_text


def test_translation_job_manager_creates_nested_run_report_artifact_when_missing(tmp_path: Path) -> None:
    run_dir = _seed_translation_run_dir(tmp_path)
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    manager = TranslationJobManager()
    manager._jobs["tx-missing-artifacts"] = _ManagedTranslationJob(
        job_id="tx-missing-artifacts",
        job_kind="translate",
        runtime_mode="live",
        workspace_id="gmail-intake",
        created_at="2026-04-05T13:08:51+00:00",
        updated_at="2026-04-05T13:11:16+00:00",
        status="completed",
        status_text="Translation complete",
        config_payload={},
        progress_payload={},
        diagnostics_payload={"kind": "translate"},
        result_payload={},
        artifacts_payload={"run_dir": str(run_dir)},
    )

    response = manager.generate_run_report(job_id="tx-missing-artifacts", settings_path=settings_path)

    report_path = str((run_dir / "run_report.md").resolve())
    job = response["normalized_payload"]["job"]
    assert job["artifacts"]["run_report_path"] == report_path
    assert job["result"]["artifacts"]["run_report_path"] == report_path


def test_translation_job_artifact_path_supports_run_report(tmp_path: Path) -> None:
    report_path = tmp_path / "sample_run" / "run_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# Run Report\n", encoding="utf-8")
    manager = TranslationJobManager()
    manager._jobs["tx-2"] = _ManagedTranslationJob(
        job_id="tx-2",
        job_kind="translate",
        runtime_mode="live",
        workspace_id="gmail-intake",
        created_at="2026-04-05T13:08:51+00:00",
        updated_at="2026-04-05T13:11:16+00:00",
        status="completed",
        status_text="Translation complete",
        config_payload={},
        progress_payload={},
        diagnostics_payload={"kind": "translate"},
        result_payload={},
        artifacts_payload={"run_report_path": str(report_path)},
    )

    resolved = manager.job_artifact_path(job_id="tx-2", artifact_kind="run_report")

    assert resolved == report_path.resolve()


def test_translation_job_manager_scopes_gmail_run_reservations_by_attachment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeThread:
        def __init__(self, *, target, name, daemon) -> None:  # type: ignore[no-untyped-def]
            self.target = target
            self.name = name
            self.daemon = daemon

        def start(self) -> None:
            return None

    monkeypatch.setattr(translation_service_module.threading, "Thread", _FakeThread)

    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    pdf_path = tmp_path / "Auto.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\n")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    manager = TranslationJobManager()

    base_values = {
        "source_path": str(pdf_path),
        "output_dir": str(output_dir),
        "target_lang": "FR",
        "image_mode": "auto",
        "ocr_mode": "auto",
        "ocr_engine": "local_then_api",
        "resume": False,
        "keep_intermediates": True,
        "start_page": 1,
    }

    first = manager.start_translate(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        form_values={
            **base_values,
            "gmail_batch_context": {
                "source": "gmail_intake",
                "session_id": "gmail_batch_a",
                "message_id": "msg-1",
                "thread_id": "thr-1",
                "attachment_id": "att-1",
                "selected_attachment_filename": "Auto.pdf",
                "selected_attachment_count": 1,
                "selected_target_lang": "FR",
                "selected_start_page": 1,
                "gmail_batch_session_report_path": str(tmp_path / "gmail_batch_a.json"),
            },
        },
    )

    second = manager.start_translate(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        form_values={
            **base_values,
            "gmail_batch_context": {
                "source": "gmail_intake",
                "session_id": "gmail_batch_a",
                "message_id": "msg-1",
                "thread_id": "thr-1",
                "attachment_id": "att-2",
                "selected_attachment_filename": "Auto.pdf",
                "selected_attachment_count": 1,
                "selected_target_lang": "FR",
                "selected_start_page": 1,
                "gmail_batch_session_report_path": str(tmp_path / "gmail_batch_a.json"),
            },
        },
    )

    assert first["status"] == "queued"
    assert second["status"] == "queued"
    assert first["job_id"] != second["job_id"]
    assert len(manager._reservations) == 2

    with pytest.raises(ValueError, match="already active for this run folder"):
        manager.start_translate(
            runtime_mode="live",
            workspace_id="gmail-intake",
            settings_path=settings_path,
            form_values={
                **base_values,
                "gmail_batch_context": {
                    "source": "gmail_intake",
                    "session_id": "gmail_batch_a",
                    "message_id": "msg-1",
                    "thread_id": "thr-1",
                    "attachment_id": "att-1",
                    "selected_attachment_filename": "Auto.pdf",
                    "selected_attachment_count": 1,
                    "selected_target_lang": "FR",
                    "selected_start_page": 1,
                    "gmail_batch_session_report_path": str(tmp_path / "gmail_batch_a.json"),
                },
            },
        )
