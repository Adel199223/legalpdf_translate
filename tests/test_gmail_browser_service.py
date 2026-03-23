from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import fitz
from PIL import Image

from legalpdf_translate.gmail_browser_service import GmailBrowserSessionManager
from legalpdf_translate.gmail_batch import (
    DownloadedGmailAttachment,
    FetchedGmailMessage,
    GmailAttachmentCandidate,
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


def _write_pdf(path: Path, *, page_count: int) -> None:
    doc = fitz.open()
    try:
        for index in range(page_count):
            page = doc.new_page()
            page.insert_text((72, 72), f"Preview page {index + 1}")
        doc.save(path)
    finally:
        doc.close()


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


def test_preview_attachment_reuses_cached_pdf_and_renders_requested_page(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    load_result = _load_result(
        message_id="msg-1",
        thread_id="thr-1",
        subject="Court notice",
        account_email="adel@example.com",
        attachment_ids=("att-1",),
    )
    preview_pdf = tmp_path / "preview.pdf"
    _write_pdf(preview_pdf, page_count=3)

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
    manager._store_loaded_result(runtime_mode="live", workspace_id="gmail-intake", result=load_result)
    workspace = manager._workspace(runtime_mode="live", workspace_id="gmail-intake")
    workspace.preview_paths["att-1"] = preview_pdf
    workspace.preview_page_counts["att-1"] = 3

    payload = manager.preview_attachment(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        attachment_id="att-1",
    )

    assert payload["diagnostics"]["reused_preview_cache"] is True
    assert payload["normalized_payload"]["page_count"] == 3
    assert len(payload["normalized_payload"]["page_sizes"]) == 3

    rendered = manager.render_attachment_preview_page(
        runtime_mode="live",
        workspace_id="gmail-intake",
        attachment_id="att-1",
        page_number=99,
    )

    assert rendered["page_number"] == 3
    assert rendered["page_count"] == 3
    assert rendered["media_type"] == "image/jpeg"
    assert rendered["width_px"] > 0
    assert rendered["height_px"] > 0
    assert rendered["image_bytes"]


def test_preview_attachment_download_uses_unique_preview_filename(tmp_path: Path, monkeypatch) -> None:
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{}", encoding="utf-8")
    load_result = _load_result(
        message_id="msg-1",
        thread_id="thr-1",
        subject="Court notice",
        account_email="adel@example.com",
        attachment_ids=("att-123456789",),
    )
    saved_pdf = tmp_path / "downloaded.pdf"
    _write_pdf(saved_pdf, page_count=2)
    captured: dict[str, object] = {}

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

    def _download(request):
        captured["filename"] = request.filename
        return SimpleNamespace(ok=True, saved_path=saved_pdf, message="ok", stdout="", stderr="", payload={})

    monkeypatch.setattr("legalpdf_translate.gmail_browser_service.download_gmail_attachment_via_gog", _download)

    manager = GmailBrowserSessionManager()
    manager._store_loaded_result(runtime_mode="live", workspace_id="gmail-intake", result=load_result)

    payload = manager.preview_attachment(
        runtime_mode="live",
        workspace_id="gmail-intake",
        settings_path=settings_path,
        attachment_id="att-123456789",
    )

    assert captured["filename"] == "att-123456789_att-1234.pdf"
    assert payload["normalized_payload"]["page_count"] == 2
    assert len(payload["normalized_payload"]["page_sizes"]) == 2


def test_render_attachment_preview_page_clamps_image_to_page_one(tmp_path: Path) -> None:
    image_path = tmp_path / "notice.png"
    Image.new("RGB", (320, 240), color="white").save(image_path)
    attachment = GmailAttachmentCandidate(
        attachment_id="img-1",
        filename="notice.png",
        mime_type="image/png",
        size_bytes=1024,
        source_message_id="msg-1",
    )
    load_result = GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="Loaded exact Gmail message.",
        intake_context=InboundMailContext(
            message_id="msg-1",
            thread_id="thr-1",
            subject="Court image",
            account_email="adel@example.com",
        ),
        gog_path=Path("C:/tmp/gog.exe"),
        account_email="adel@example.com",
        accounts=("adel@example.com",),
        stdout="",
        message=FetchedGmailMessage(
            message_id="msg-1",
            thread_id="thr-1",
            subject="Court image",
            from_header="Court <court@example.com>",
            account_email="adel@example.com",
            attachments=(attachment,),
        ),
    )

    manager = GmailBrowserSessionManager()
    manager._store_loaded_result(runtime_mode="live", workspace_id="gmail-intake", result=load_result)
    workspace = manager._workspace(runtime_mode="live", workspace_id="gmail-intake")
    workspace.preview_paths["img-1"] = image_path
    workspace.preview_page_counts["img-1"] = 1

    rendered = manager.render_attachment_preview_page(
        runtime_mode="live",
        workspace_id="gmail-intake",
        attachment_id="img-1",
        page_number=8,
    )

    assert rendered["page_number"] == 1
    assert rendered["page_count"] == 1
    assert rendered["media_type"] == "image/jpeg"
    assert rendered["image_bytes"]
