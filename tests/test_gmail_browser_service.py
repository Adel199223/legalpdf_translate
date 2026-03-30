from __future__ import annotations

from pathlib import Path
import threading
from types import SimpleNamespace

from legalpdf_translate.gmail_browser_service import GmailBrowserSessionManager
from legalpdf_translate.gmail_batch import (
    DownloadedGmailAttachment,
    FetchedGmailMessage,
    GmailAttachmentCandidate,
    GmailBatchConfirmedItem,
    GmailBatchSession,
    GmailInterpretationSession,
    GmailMessageLoadResult,
)
from legalpdf_translate.gmail_intake import InboundMailContext
from legalpdf_translate.interpretation_service import InterpretationValidationError


def _load_result(
    *,
    message_id: str,
    thread_id: str,
    subject: str,
    account_email: str,
    attachment_ids: tuple[str, ...],
    stdout: str = "",
) -> GmailMessageLoadResult:
    attachments = tuple(
        GmailAttachmentCandidate(
            attachment_id=attachment_id,
            filename=f"{attachment_id}.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            source_message_id=message_id,
        )
        for attachment_id in attachment_ids
    )
    return GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="Loaded exact Gmail message.",
        intake_context=InboundMailContext(
            message_id=message_id,
            thread_id=thread_id,
            subject=subject,
            account_email=account_email,
        ),
        gog_path=Path("C:/tmp/gog.exe"),
        account_email=account_email,
        accounts=(account_email,),
        stdout=stdout,
        message=FetchedGmailMessage(
            message_id=message_id,
            thread_id=thread_id,
            subject=subject,
            from_header="Court <court@example.com>",
            account_email=account_email,
            attachments=attachments,
        ),
    )


def _translation_batch_session(tmp_path: Path) -> GmailBatchSession:
    load_result = _load_result(
        message_id="msg-1",
        thread_id="thr-1",
        subject="Court notice",
        account_email="adel@example.com",
        attachment_ids=("att-1",),
    )
    attachment = load_result.message.attachments[0]
    saved_pdf = tmp_path / "sentenca.pdf"
    saved_pdf.write_bytes(b"%PDF-1.7\n")
    translated_docx = tmp_path / "sentenca_EN.docx"
    translated_docx.write_text("docx", encoding="utf-8")
    run_dir = tmp_path / "sentenca_EN_run"
    run_dir.mkdir()
    downloaded = DownloadedGmailAttachment(
        candidate=attachment,
        saved_path=saved_pdf,
        start_page=1,
        page_count=5,
    )
    confirmed = GmailBatchConfirmedItem(
        downloaded_attachment=downloaded,
        translated_docx_path=translated_docx,
        run_dir=run_dir,
        translated_word_count=1269,
        joblog_row_id=73,
        run_id="20260328_223622",
        case_number="305/23.2GCBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="beja.judicial@tribunais.org.pt",
    )
    return GmailBatchSession(
        intake_context=load_result.intake_context,
        message=load_result.message,
        gog_path=Path("C:/tmp/gog.exe"),
        account_email="adel@example.com",
        downloaded_attachments=(downloaded,),
        download_dir=tmp_path,
        selected_target_lang="EN",
        effective_output_dir=tmp_path / "outputs",
        confirmed_items=[confirmed],
        consistency_signature=confirmed.consistency_signature,
        session_report_path=tmp_path / "gmail_batch_session.json",
    )


def test_gmail_browser_bootstrap_review_metadata_defaults(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=False,
            message="not configured",
            gog_path=None,
            account_email="",
            accounts=(),
        ),
    )

    manager = GmailBrowserSessionManager()
    payload = manager.build_bootstrap(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        outputs_dir=outputs_dir,
    )

    assert payload["status"] == "ok"
    assert payload["normalized_payload"]["review_event_id"] == 0
    assert payload["normalized_payload"]["message_signature"] == ""


def test_gmail_browser_review_event_increments_for_manual_and_bridge_loads(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    results = iter(
        (
            _load_result(
                message_id="msg-1",
                thread_id="thr-1",
                subject="Court notice",
                account_email="adel@example.com",
                attachment_ids=("att-1",),
            ),
            _load_result(
                message_id="msg-2",
                thread_id="thr-2",
                subject="Second notice",
                account_email="adel@example.com",
                attachment_ids=("att-2", "att-3"),
            ),
        )
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.load_gmail_message_from_intake",
        lambda **_kwargs: next(results),
    )

    manager = GmailBrowserSessionManager()
    manual_payload = manager.load_message(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        context_payload={
            "message_id": "msg-1",
            "thread_id": "thr-1",
            "subject": "Court notice",
            "account_email": "adel@example.com",
        },
    )

    assert manual_payload["normalized_payload"]["review_event_id"] == 1
    first_signature = manual_payload["normalized_payload"]["message_signature"]
    assert first_signature != ""

    first_bootstrap = manager.build_bootstrap(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        outputs_dir=outputs_dir,
    )
    assert first_bootstrap["normalized_payload"]["review_event_id"] == 1
    assert first_bootstrap["normalized_payload"]["message_signature"] == first_signature

    bridge_payload = manager.accept_bridge_intake(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        context=InboundMailContext(
            message_id="msg-2",
            thread_id="thr-2",
            subject="Second notice",
            account_email="adel@example.com",
        ),
    )

    assert bridge_payload["normalized_payload"]["review_event_id"] == 2
    assert bridge_payload["normalized_payload"]["message_signature"] != first_signature

    second_bootstrap = manager.build_bootstrap(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        outputs_dir=outputs_dir,
    )
    assert second_bootstrap["normalized_payload"]["review_event_id"] == 2
    assert second_bootstrap["normalized_payload"]["message_signature"] == bridge_payload["normalized_payload"]["message_signature"]


def test_gmail_browser_bootstrap_exposes_pending_bridge_warmup_state(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    load_started = threading.Event()
    allow_finish = threading.Event()

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )

    def _blocking_load(**_kwargs):
        load_started.set()
        assert allow_finish.wait(timeout=2.0)
        return _load_result(
            message_id="msg-bridge",
            thread_id="thr-bridge",
            subject="Bridge warmup",
            account_email="adel@example.com",
            attachment_ids=("att-1",),
        )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.load_gmail_message_from_intake",
        _blocking_load,
    )

    manager = GmailBrowserSessionManager()
    worker = threading.Thread(
        target=lambda: manager.accept_bridge_intake(
            runtime_mode="live",
            workspace_id="gmail-intake",
            settings_path=settings_path,
            context=InboundMailContext(
                message_id="msg-bridge",
                thread_id="thr-bridge",
                subject="Bridge warmup",
                account_email="adel@example.com",
            ),
        ),
        daemon=True,
    )
    worker.start()
    assert load_started.wait(timeout=2.0)

    pending_bootstrap = manager.build_bootstrap(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        outputs_dir=outputs_dir,
    )
    assert pending_bootstrap["normalized_payload"]["pending_status"] == "warming"
    assert pending_bootstrap["normalized_payload"]["pending_intake_context"] == {
        "message_id": "msg-bridge",
        "thread_id": "thr-bridge",
        "subject": "Bridge warmup",
        "account_email": "adel@example.com",
    }
    assert pending_bootstrap["normalized_payload"]["pending_review_open"] is True

    allow_finish.set()
    worker.join(timeout=2.0)
    assert not worker.is_alive()

    completed_bootstrap = manager.build_bootstrap(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        outputs_dir=outputs_dir,
    )
    assert completed_bootstrap["normalized_payload"]["pending_status"] == ""
    assert completed_bootstrap["normalized_payload"]["pending_intake_context"] == {}
    assert completed_bootstrap["normalized_payload"]["pending_review_open"] is False
    assert completed_bootstrap["normalized_payload"]["load_result"]["ok"] is True


def test_accept_bridge_intake_reuses_same_context_while_pending(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    load_started = threading.Event()
    allow_finish = threading.Event()
    load_calls = {"count": 0}

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )

    def _blocking_load(**_kwargs):
        load_calls["count"] += 1
        load_started.set()
        assert allow_finish.wait(timeout=2.0)
        return _load_result(
            message_id="msg-bridge",
            thread_id="thr-bridge",
            subject="Bridge warmup",
            account_email="adel@example.com",
            attachment_ids=("att-1",),
        )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.load_gmail_message_from_intake",
        _blocking_load,
    )

    manager = GmailBrowserSessionManager()
    worker = threading.Thread(
        target=lambda: manager.accept_bridge_intake(
            runtime_mode="live",
            workspace_id="gmail-intake",
            settings_path=settings_path,
            context=InboundMailContext(
                message_id="msg-bridge",
                thread_id="thr-bridge",
                subject="Bridge warmup",
                account_email="adel@example.com",
            ),
        ),
        daemon=True,
    )
    worker.start()
    assert load_started.wait(timeout=2.0)

    reused = manager.accept_bridge_intake(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        context=InboundMailContext(
            message_id="msg-bridge",
            thread_id="thr-bridge",
            subject="Bridge warmup",
            account_email="adel@example.com",
        ),
    )

    assert reused["status"] == "warming"
    assert reused["normalized_payload"]["handoff_state"] == "pending_reused"
    assert reused["normalized_payload"]["pending_status"] == "warming"
    assert reused["diagnostics"]["handoff_reused"] is True
    assert load_calls["count"] == 1

    allow_finish.set()
    worker.join(timeout=2.0)
    assert not worker.is_alive()


def test_accept_bridge_intake_reuses_same_loaded_message_without_new_review_event(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    load_calls = {"count": 0}

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )

    def _load(**_kwargs):
        load_calls["count"] += 1
        return _load_result(
            message_id="msg-bridge",
            thread_id="thr-bridge",
            subject="Bridge warmup",
            account_email="adel@example.com",
            attachment_ids=("att-1",),
        )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.load_gmail_message_from_intake",
        _load,
    )

    manager = GmailBrowserSessionManager()
    first = manager.accept_bridge_intake(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        context=InboundMailContext(
            message_id="msg-bridge",
            thread_id="thr-bridge",
            subject="Bridge warmup",
            account_email="adel@example.com",
        ),
    )
    reused = manager.accept_bridge_intake(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        context=InboundMailContext(
            message_id="msg-bridge",
            thread_id="thr-bridge",
            subject="Bridge warmup",
            account_email="adel@example.com",
        ),
    )

    assert first["normalized_payload"]["review_event_id"] == 1
    assert reused["normalized_payload"]["review_event_id"] == 1
    assert reused["normalized_payload"]["message_signature"] == first["normalized_payload"]["message_signature"]
    assert reused["normalized_payload"]["handoff_state"] == "loaded_reused"
    assert reused["diagnostics"]["handoff_reused"] is True
    assert load_calls["count"] == 1


def test_prepare_interpretation_session_prefers_explicit_gmail_reply_address(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    load_result = _load_result(
        message_id="msg-1",
        thread_id="thr-1",
        subject="Court notice",
        account_email="adel@example.com",
        attachment_ids=("att-1",),
        stdout=(
            '{"body":"Nota: Qualquer tipo de resposta deverá ser remetida exclusivamente '
            'para o seguinte endereço: beja.judicial@tribunais.org.pt"}'
        ),
    )
    attachment = load_result.message.attachments[0]
    saved_pdf = tmp_path / "notice.pdf"
    saved_pdf.write_bytes(b"%PDF-1.7\n")
    session = GmailInterpretationSession(
        intake_context=load_result.intake_context,
        message=load_result.message,
        gog_path=load_result.gog_path,
        account_email=load_result.account_email or "",
        downloaded_attachment=DownloadedGmailAttachment(
            candidate=attachment,
            saved_path=saved_pdf,
            start_page=1,
            page_count=1,
        ),
        download_dir=tmp_path,
        effective_output_dir=outputs_dir,
    )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.prepare_gmail_interpretation_session",
        lambda **_kwargs: session,
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.autofill_interpretation_from_notification_pdf",
        lambda **_kwargs: {
            "status": "ok",
            "normalized_payload": {
                "case_number": "305/23.2GCBJA",
                "court_email": "camoes.ministeriopublico@tribunais.org.pt",
            },
            "diagnostics": {"metadata_extraction": {}},
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.write_gmail_interpretation_session_report",
        lambda _session: None,
    )

    manager = GmailBrowserSessionManager()
    manager._store_loaded_result(runtime_mode="live", workspace_id="gmail-intake", result=load_result)
    payload = manager.prepare_session(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        outputs_dir=outputs_dir,
        workflow_kind="interpretation",
        target_lang="",
        output_dir_text=str(outputs_dir),
        selections_payload=[{"attachment_id": "att-1", "start_page": 1}],
    )

    assert payload["normalized_payload"]["interpretation_seed"]["court_email"] == "beja.judicial@tribunais.org.pt"


def test_finalize_interpretation_prefers_explicit_gmail_reply_address(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    load_result = _load_result(
        message_id="msg-1",
        thread_id="thr-1",
        subject="Court notice",
        account_email="adel@example.com",
        attachment_ids=("att-1",),
        stdout=(
            '{"body":"Nota: Qualquer tipo de resposta deverá ser remetida exclusivamente '
            'para o seguinte endereço: beja.judicial@tribunais.org.pt"}'
        ),
    )
    attachment = load_result.message.attachments[0]
    saved_pdf = tmp_path / "notice.pdf"
    saved_pdf.write_bytes(b"%PDF-1.7\n")
    exported_docx = outputs_dir / "honorarios.docx"
    exported_pdf = outputs_dir / "honorarios.pdf"
    exported_docx.write_text("docx placeholder", encoding="utf-8")
    exported_pdf.write_bytes(b"%PDF-1.7\n")
    session = GmailInterpretationSession(
        intake_context=load_result.intake_context,
        message=load_result.message,
        gog_path=load_result.gog_path,
        account_email=load_result.account_email or "",
        downloaded_attachment=DownloadedGmailAttachment(
            candidate=attachment,
            saved_path=saved_pdf,
            start_page=1,
            page_count=1,
        ),
        download_dir=tmp_path,
        effective_output_dir=outputs_dir,
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.export_interpretation_honorarios",
        lambda **_kwargs: {
            "status": "ok",
            "normalized_payload": {
                "docx_path": str(exported_docx),
                "pdf_path": str(exported_pdf),
            },
            "diagnostics": {
                "pdf_export": {
                    "ok": True,
                    "pdf_path": str(exported_pdf),
                    "failure_message": "",
                }
            },
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service._current_profile",
        lambda **_kwargs: ([], "primary", SimpleNamespace(display_name="Adel")),
    )
    def _build_request(**kwargs):
        captured["request"] = dict(kwargs)
        return SimpleNamespace(
            gog_path=kwargs["gog_path"],
            account_email=kwargs["account_email"],
            to_email=kwargs["to_email"],
            subject=kwargs["subject"],
            body="reply body",
            attachments=(kwargs["honorarios_pdf"],),
            reply_to_message_id=kwargs["reply_to_message_id"],
        )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.build_interpretation_gmail_reply_request",
        _build_request,
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.create_gmail_draft_via_gog",
        lambda _request: SimpleNamespace(ok=True, message="ok", stdout='{"draftId":"123"}', stderr="", payload={"draftId": "123"}),
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.write_gmail_interpretation_session_report",
        lambda _session: None,
    )

    manager = GmailBrowserSessionManager()
    manager._store_loaded_result(runtime_mode="live", workspace_id="gmail-intake", result=load_result)
    workspace = manager._workspace(runtime_mode="live", workspace_id="gmail-intake")
    workspace.interpretation_session = session

    payload = manager.finalize_interpretation(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        form_values={"court_email": "camoes.ministeriopublico@tribunais.org.pt"},
        profile_id=None,
        service_same_checked=True,
        output_filename="",
    )

    assert captured["request"]["to_email"] == "beja.judicial@tribunais.org.pt"
    assert payload["normalized_payload"]["gmail_draft_request"]["to_email"] == "beja.judicial@tribunais.org.pt"


def test_preflight_batch_finalization_blocks_when_word_export_canary_fails(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    session = _translation_batch_session(tmp_path)
    session.effective_output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_word_pdf_export_readiness",
        lambda **_kwargs: {
            "ok": False,
            "finalization_ready": False,
            "message": "Word PDF export canary timed out.",
            "details": "Timed out while exporting the canary document.",
            "failure_phase": "export_pdf",
            "launch_preflight": {"ok": True, "message": "Word launched."},
            "export_canary": {"ok": False, "message": "Timed out.", "failure_phase": "export_pdf"},
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.write_gmail_batch_session_report",
        lambda _session: None,
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )

    manager = GmailBrowserSessionManager()
    workspace = manager._workspace(runtime_mode="live", workspace_id="gmail-intake")
    workspace.batch_session = session

    payload = manager.preflight_batch_finalization(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        force_refresh=True,
    )

    assert payload["status"] == "blocked_word_pdf_export"
    assert payload["normalized_payload"]["finalization_state"] == "blocked_word_pdf_export"
    assert payload["normalized_payload"]["finalization_preflight"]["failure_phase"] == "export_pdf"
    assert session.finalization_state == "blocked_word_pdf_export"
    assert session.draft_failure_reason == "Word PDF export canary timed out."


def test_finalize_batch_returns_retryable_local_only_after_export_failure(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    session = _translation_batch_session(tmp_path)
    session.effective_output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = session.effective_output_dir / "Requerimento_Honorarios_305_23.2GCBJA_20260330.docx"
    docx_path.write_text("honorarios", encoding="utf-8")
    cleared_prefixes: list[str | None] = []

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_word_pdf_export_readiness",
        lambda **_kwargs: {
            "ok": True,
            "finalization_ready": True,
            "message": "Word export canary passed.",
            "details": "PDF header verified as %PDF-.",
            "launch_preflight": {"ok": True, "message": "Word launched."},
            "export_canary": {"ok": True, "message": "Canary passed."},
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.write_gmail_batch_session_report",
        lambda _session: None,
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.clear_word_pdf_export_readiness_cache",
        lambda *, scope_prefix=None: cleared_prefixes.append(str(scope_prefix) if scope_prefix is not None else None) or 1,
    )
    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.assess_gmail_draft_prereqs",
        lambda **_kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path("C:/tmp/gog.exe"),
            account_email="adel@example.com",
            accounts=("adel@example.com",),
        ),
    )
    monkeypatch.setattr(
        "legalpdf_translate.honorarios_docx.default_honorarios_filename",
        lambda *_args, **_kwargs: "Requerimento_Honorarios_305_23.2GCBJA_20260330.docx",
    )
    monkeypatch.setattr(
        "legalpdf_translate.honorarios_docx.generate_honorarios_docx",
        lambda _draft, _path: docx_path,
    )
    monkeypatch.setattr(
        "legalpdf_translate.interpretation_service._current_profile",
        lambda **_kwargs: ([], "primary", SimpleNamespace(display_name="Adel")),
    )
    monkeypatch.setattr(
        "legalpdf_translate.interpretation_service._profile_missing_fields",
        lambda _profile: [],
    )
    monkeypatch.setattr(
        "legalpdf_translate.interpretation_service.serialize_honorarios_draft",
        lambda _draft: {"case_number": "305/23.2GCBJA"},
    )
    monkeypatch.setattr(
        "legalpdf_translate.honorarios_docx.build_honorarios_draft",
        lambda **_kwargs: SimpleNamespace(case_number="305/23.2GCBJA"),
    )
    monkeypatch.setattr(
        "legalpdf_translate.interpretation_service._run_pdf_export_with_retry",
        lambda **_kwargs: {
            "docx_path": str(docx_path),
            "pdf_path": None,
            "ok": False,
            "failure_code": "timeout",
            "failure_message": "Word PDF export timed out.",
            "failure_details": "Failure code: timeout",
            "elapsed_ms": 45028,
        },
    )

    manager = GmailBrowserSessionManager()
    workspace = manager._workspace(runtime_mode="live", workspace_id="gmail-intake")
    workspace.batch_session = session

    payload = manager.finalize_batch(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        output_filename="",
        profile_id=None,
    )

    assert payload["status"] == "local_only"
    assert payload["normalized_payload"]["retry_available"] is True
    assert payload["normalized_payload"]["finalization_state"] == "local_artifacts_ready"
    assert payload["diagnostics"]["word_pdf_export"]["finalization_ready"] is True
    assert payload["diagnostics"]["pdf_export"]["failure_code"] == "timeout"
    assert payload["normalized_payload"]["active_session"]["actual_honorarios_path"] == str(docx_path)
    assert session.finalization_state == "local_artifacts_ready"
    assert session.draft_failure_reason == "Word PDF export timed out."
    resolved = str(settings_path.expanduser().resolve())
    assert cleared_prefixes == [
        f"gmail_batch_finalization::{resolved}::{session.session_id}",
        f"provider_state::{resolved}",
    ]


def test_finalize_interpretation_propagates_structured_validation_errors(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir()
    load_result = _load_result(
        message_id="msg-1",
        thread_id="thr-1",
        subject="Court notice",
        account_email="adel@example.com",
        attachment_ids=("att-1",),
    )
    attachment = load_result.message.attachments[0]
    saved_pdf = tmp_path / "notice.pdf"
    saved_pdf.write_bytes(b"%PDF-1.7\n")
    session = GmailInterpretationSession(
        intake_context=load_result.intake_context,
        message=load_result.message,
        gog_path=load_result.gog_path,
        account_email=load_result.account_email or "",
        downloaded_attachment=DownloadedGmailAttachment(
            candidate=attachment,
            saved_path=saved_pdf,
            start_page=1,
            page_count=1,
        ),
        download_dir=tmp_path,
        effective_output_dir=outputs_dir,
    )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_browser_service.export_interpretation_honorarios",
        lambda **_kwargs: (_ for _ in ()).throw(
            InterpretationValidationError(
                code="distance_required",
                message="One-way distance from Marmelar to Beja is required.",
                field="travel_km_outbound",
                city="Beja",
                travel_origin_label="Marmelar",
            )
        ),
    )

    manager = GmailBrowserSessionManager()
    workspace = manager._workspace(runtime_mode="live", workspace_id="gmail-intake")
    workspace.interpretation_session = session

    try:
        manager.finalize_interpretation(
            runtime_mode="live",
            workspace_id="gmail-intake",
            settings_path=settings_path,
            form_values={"case_city": "Beja", "service_city": "Beja"},
            profile_id=None,
            service_same_checked=True,
            output_filename="",
        )
    except InterpretationValidationError as exc:
        assert exc.code == "distance_required"
        assert exc.city == "Beja"
    else:
        raise AssertionError("Expected structured interpretation validation error")
