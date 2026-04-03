from __future__ import annotations

import time
from pathlib import Path

import legalpdf_translate.browser_arabic_review as browser_arabic_review
from legalpdf_translate.browser_arabic_review import ArabicDocxReviewManager, job_requires_arabic_review
from legalpdf_translate.word_automation import WordAutomationResult


def _completed_ar_job(docx_path: Path, *, job_id: str = "tx-ar-001") -> dict[str, object]:
    return {
        "job_id": job_id,
        "job_kind": "translate",
        "status": "completed",
        "config": {
            "target_lang": "AR",
        },
        "result": {
            "save_seed": {
                "target_lang": "AR",
                "output_docx": str(docx_path),
            },
        },
    }


def test_arabic_review_state_requires_completed_ar_job_with_durable_docx(tmp_path: Path) -> None:
    docx_path = tmp_path / "translated_ar.docx"
    docx_path.write_bytes(b"docx")
    manager = ArabicDocxReviewManager()

    payload = manager.state_for_workspace(
        runtime_mode="live",
        workspace_id="gmail-intake",
        job=_completed_ar_job(docx_path),
    )

    assert payload["required"] is True
    assert payload["resolved"] is False
    assert payload["status"] == "required"
    assert payload["docx_path"] == str(docx_path.resolve())
    assert payload["job_id"] == "tx-ar-001"
    assert payload["completion_key"] == "job:tx-ar-001:translate"


def test_arabic_review_open_falls_back_to_default_windows_handler(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "translated_ar.docx"
    docx_path.write_bytes(b"docx")
    manager = ArabicDocxReviewManager()
    called: list[str] = []

    monkeypatch.setattr(
        browser_arabic_review,
        "open_docx_in_word",
        lambda path: WordAutomationResult(ok=False, action="open_docx", message="Word automation failed."),
    )
    monkeypatch.setattr(browser_arabic_review.os, "name", "nt", raising=False)
    monkeypatch.setattr(browser_arabic_review.os, "startfile", lambda path: called.append(str(path)), raising=False)

    payload, diagnostics = manager.open_review(
        runtime_mode="live",
        workspace_id="gmail-intake",
        job=_completed_ar_job(docx_path),
    )

    assert payload["required"] is True
    assert payload["resolved"] is False
    assert payload["fallback_used"] is True
    assert "default Windows handler" in payload["message"]
    assert called == [str(docx_path.resolve())]
    assert diagnostics["word_action"]["ok"] is False


def test_arabic_review_open_success_instructs_manual_word_save(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "translated_ar.docx"
    docx_path.write_bytes(b"docx")
    manager = ArabicDocxReviewManager()

    monkeypatch.setattr(
        browser_arabic_review,
        "open_docx_in_word",
        lambda path: WordAutomationResult(ok=True, action="open_docx", message="Word document opened."),
    )

    payload, diagnostics = manager.open_review(
        runtime_mode="live",
        workspace_id="gmail-intake",
        job=_completed_ar_job(docx_path),
    )

    assert payload["required"] is True
    assert payload["resolved"] is False
    assert payload["fallback_used"] is False
    assert "Align or edit it manually" in payload["message"]
    assert diagnostics["word_action"]["ok"] is True


def test_arabic_review_detects_manual_save_after_quiet_period(tmp_path: Path) -> None:
    docx_path = tmp_path / "translated_ar.docx"
    docx_path.write_bytes(b"docx")
    manager = ArabicDocxReviewManager()
    job = _completed_ar_job(docx_path)

    first = manager.state_for_workspace(runtime_mode="live", workspace_id="gmail-intake", job=job)
    assert first["resolved"] is False

    docx_path.write_bytes(b"docx-updated")
    second = manager.state_for_workspace(runtime_mode="live", workspace_id="gmail-intake", job=job)
    assert second["save_detected"] is True
    assert second["resolved"] is False

    session = next(iter(manager._sessions.values()))
    session.last_change_monotonic = time.monotonic() - 5.0

    third = manager.state_for_workspace(runtime_mode="live", workspace_id="gmail-intake", job=job)
    assert third["resolved"] is True
    assert third["resolution"] == "saved"
    assert third["fingerprint_changed"] is True


def test_job_requires_arabic_review_is_false_for_non_ar_job(tmp_path: Path) -> None:
    docx_path = tmp_path / "translated_en.docx"
    docx_path.write_bytes(b"docx")
    job = _completed_ar_job(docx_path)
    job["result"] = {
        "save_seed": {
            "target_lang": "EN",
            "output_docx": str(docx_path),
        },
    }

    assert job_requires_arabic_review(job) is False
