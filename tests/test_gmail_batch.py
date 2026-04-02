from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from legalpdf_translate.gmail_batch import (
    DownloadedGmailAttachment,
    FetchedGmailMessage,
    GmailAttachmentCandidate,
    GmailAttachmentSelection,
    GmailBatchConfirmedItem,
    GmailInterpretationSession,
    GmailBatchSession,
    build_gmail_interpretation_session_payload,
    GmailMessageLoadResult,
    build_gmail_batch_session_payload,
    gmail_batch_consistency_signature,
    load_gmail_message_from_intake,
    prepare_gmail_batch_session,
    prepare_gmail_interpretation_session,
    stage_gmail_batch_translated_docx,
    write_gmail_batch_session_report,
    write_gmail_interpretation_session_report,
)
from legalpdf_translate.gmail_intake import InboundMailContext


def _message_payload(parts: list[dict[str, object]]) -> dict[str, object]:
    return {
        "id": "msg-123",
        "threadId": "thread-456",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Urgent filing"},
                {"name": "From", "value": "Tribunal <court@example.com>"},
            ],
            "parts": parts,
        },
    }


def test_load_gmail_message_from_intake_is_unavailable_outside_windows(monkeypatch) -> None:
    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: False)

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
    )

    assert result.ok is False
    assert result.classification == "unavailable"
    assert "Windows-only feature" in result.status_message


def test_load_gmail_message_from_intake_prefers_configured_account(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: True)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.resolve_gog_path",
        lambda configured_gog_path="": gog_path,
    )

    def _fake_run_gog_json(_gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {
                "accounts": [
                    {"email": "configured@example.com", "services": ["gmail"]},
                    {"email": "intake@example.com", "services": ["gmail"]},
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_gog_json", _fake_run_gog_json)

    def _fake_run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        assert "--results-only" not in cmd
        assert cmd[-1] == "configured@example.com"
        return subprocess.CompletedProcess(
            cmd,
            0,
            json.dumps(_message_payload(parts=[])),
            "",
        )

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_capture", _fake_run_capture)

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
            account_email="intake@example.com",
        ),
        configured_account_email="configured@example.com",
    )

    assert result.ok is True
    assert result.account_email == "configured@example.com"


def test_load_gmail_message_from_intake_uses_authenticated_intake_account(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: True)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.resolve_gog_path",
        lambda configured_gog_path="": gog_path,
    )

    def _fake_run_gog_json(_gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {
                "accounts": [
                    {"email": "intake@example.com", "services": ["gmail"]},
                    {"email": "other@example.com", "services": ["gmail"]},
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_gog_json", _fake_run_gog_json)

    def _fake_run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        assert cmd[-1] == "intake@example.com"
        return subprocess.CompletedProcess(
            cmd,
            0,
            json.dumps(_message_payload(parts=[])),
            "",
        )

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_capture", _fake_run_capture)

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
            account_email="intake@example.com",
        ),
    )

    assert result.ok is True
    assert result.account_email == "intake@example.com"


def test_load_gmail_message_from_intake_filters_supported_non_inline_attachments(
    monkeypatch,
    tmp_path: Path,
) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: True)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.resolve_gog_path",
        lambda configured_gog_path="": gog_path,
    )

    def _fake_run_gog_json(_gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {"accounts": [{"email": "only@example.com", "services": ["gmail"]}]}
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_gog_json", _fake_run_gog_json)

    payload = _message_payload(
        parts=[
            {
                "filename": "court.pdf",
                "mimeType": "application/pdf",
                "body": {"attachmentId": "att-pdf", "size": 4096},
                "headers": [{"name": "Content-Disposition", "value": "attachment"}],
            },
            {
                "filename": "image001.png",
                "mimeType": "image/png",
                "body": {"attachmentId": "att-inline", "size": 1024},
                "headers": [{"name": "Content-Disposition", "value": "inline"}],
            },
            {
                "filename": "notes.docx",
                "mimeType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "body": {"attachmentId": "att-docx", "size": 2048},
                "headers": [{"name": "Content-Disposition", "value": "attachment"}],
            },
            {
                "mimeType": "multipart/mixed",
                "parts": [
                    {
                        "filename": "scene.jpg",
                        "mimeType": "image/jpeg",
                        "body": {"attachmentId": "att-jpg", "size": 3072},
                        "headers": [{"name": "Content-Disposition", "value": "attachment"}],
                    }
                ],
            },
        ]
    )

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch._run_capture",
        lambda cmd: subprocess.CompletedProcess(cmd, 0, json.dumps(payload), ""),
    )

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
    )

    assert result.ok is True
    assert result.message is not None
    assert result.message.from_header == "Tribunal <court@example.com>"
    assert [attachment.filename for attachment in result.message.attachments] == [
        "court.pdf",
        "scene.jpg",
    ]


def test_load_gmail_message_from_intake_accepts_gog_full_envelope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: True)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.resolve_gog_path",
        lambda configured_gog_path="": gog_path,
    )

    def _fake_run_gog_json(_gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {"accounts": [{"email": "only@example.com", "services": ["gmail"]}]}
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_gog_json", _fake_run_gog_json)

    envelope = {
        "attachments": [
            {
                "attachmentId": "att-pdf",
                "filename": "court.pdf",
                "mimeType": "application/pdf",
                "size": 4096,
            }
        ],
        "body": "Com os melhores cumprimentos",
        "headers": {
            "from": "Tribunal <court@example.com>",
            "subject": "Urgent filing",
        },
        "message": _message_payload(
            parts=[
                {
                    "filename": "court.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "att-pdf", "size": 4096},
                    "headers": [{"name": "Content-Disposition", "value": "attachment"}],
                }
            ]
        ),
    }

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch._run_capture",
        lambda cmd: subprocess.CompletedProcess(cmd, 0, json.dumps(envelope), ""),
    )

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
    )

    assert result.ok is True
    assert result.message is not None
    assert result.message.subject == "Urgent filing"
    assert [attachment.filename for attachment in result.message.attachments] == ["court.pdf"]


def test_load_gmail_message_from_intake_reports_attachment_list_shape(
    monkeypatch,
    tmp_path: Path,
) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: True)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.resolve_gog_path",
        lambda configured_gog_path="": gog_path,
    )

    def _fake_run_gog_json(_gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {"accounts": [{"email": "only@example.com", "services": ["gmail"]}]}
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_gog_json", _fake_run_gog_json)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch._run_capture",
        lambda cmd: subprocess.CompletedProcess(
            cmd,
            0,
            json.dumps(
                [
                    {
                        "attachmentId": "att-pdf",
                        "filename": "court.pdf",
                        "mimeType": "application/pdf",
                        "size": 4096,
                    }
                ]
            ),
            "",
        ),
    )

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
    )

    assert result.ok is False
    assert result.classification == "failed"
    assert "attachment list instead of Gmail message metadata" in result.status_message


def test_load_gmail_message_from_intake_marks_fetch_failures_as_failed(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    monkeypatch.setattr("legalpdf_translate.gmail_batch._is_windows", lambda: True)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.resolve_gog_path",
        lambda configured_gog_path="": gog_path,
    )

    def _fake_run_gog_json(_gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {"accounts": [{"email": "only@example.com", "services": ["gmail"]}]}
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_batch._run_gog_json", _fake_run_gog_json)
    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch._run_capture",
        lambda cmd: subprocess.CompletedProcess(cmd, 1, "", "boom"),
    )

    result = load_gmail_message_from_intake(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
    )

    assert result.ok is False
    assert result.classification == "failed"
    assert result.status_message == "boom"


def test_prepare_gmail_batch_session_downloads_selected_attachments_with_unique_names(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_filenames: list[str] = []

    def _fake_download(request):
        captured_filenames.append(request.filename)
        saved_path = request.output_dir / request.filename
        saved_path.write_text("ok", encoding="utf-8")
        return SimpleDownloadResult(saved_path=saved_path)

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.download_gmail_attachment_via_gog",
        _fake_download,
    )
    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", lambda _path: 6)

    attachment_one = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    attachment_two = GmailAttachmentCandidate(
        attachment_id="att-2",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment_one, attachment_two),
    )

    session = prepare_gmail_batch_session(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=message,
        gog_path=tmp_path / "gog.exe",
        account_email="only@example.com",
        selected_attachments=(
            GmailAttachmentSelection(candidate=attachment_one, start_page=2),
            GmailAttachmentSelection(candidate=attachment_two, start_page=4),
        ),
        selected_target_lang="AR",
        effective_output_dir=tmp_path / "output",
    )
    try:
        assert len(session.downloaded_attachments) == 2
        assert captured_filenames == ["court.pdf", "court (2).pdf"]
        assert all(item.saved_path.exists() for item in session.downloaded_attachments)
        assert [item.start_page for item in session.downloaded_attachments] == [2, 4]
        assert [item.page_count for item in session.downloaded_attachments] == [6, 6]
        assert session.selected_target_lang == "AR"
        assert session.session_report_path is not None
        assert session.session_report_path.exists()
        payload = json.loads(session.session_report_path.read_text(encoding="utf-8"))
        assert payload["intake_context"]["selected_attachment_filenames"] == ["court.pdf", "court.pdf"]
        assert payload["intake_context"]["selected_target_lang"] == "AR"
        assert payload["intake_context"]["selected_attachments"] == [
            {"filename": "court.pdf", "start_page": 2, "page_count": 6},
            {"filename": "court.pdf", "start_page": 4, "page_count": 6},
        ]
    finally:
        session.cleanup()


def test_prepare_gmail_batch_session_reuses_preview_cache_without_redownloading(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cached_preview = tmp_path / "preview.pdf"
    cached_preview.write_text("cached-preview", encoding="utf-8")
    download_calls: list[object] = []
    logs: list[str] = []

    def _fail_download(request):
        download_calls.append(request)
        raise AssertionError("fresh Gmail download should not be used for cached preview reuse")

    def _fake_page_count(path: Path) -> int:
        return 5 if path.name == "court.pdf" else 0

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.download_gmail_attachment_via_gog",
        _fail_download,
    )
    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", _fake_page_count)

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment,),
    )

    session = prepare_gmail_batch_session(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=message,
        gog_path=tmp_path / "gog.exe",
        account_email="only@example.com",
        selected_attachments=(GmailAttachmentSelection(candidate=attachment, start_page=3),),
        selected_target_lang="AR",
        effective_output_dir=tmp_path / "output",
        cached_preview_paths={attachment.attachment_id: cached_preview},
        cached_preview_page_counts={attachment.attachment_id: 9},
        log_callback=logs.append,
    )
    try:
        downloaded = session.downloaded_attachments[0]
        assert download_calls == []
        assert downloaded.saved_path.exists()
        assert downloaded.saved_path != cached_preview
        assert downloaded.saved_path.read_text(encoding="utf-8") == "cached-preview"
        assert downloaded.page_count == 5
        assert any("reusing preview cache" in entry for entry in logs)
        assert any("page-count mismatch" in entry for entry in logs)
    finally:
        session.cleanup()


def test_prepare_gmail_interpretation_session_reuses_preview_cache_for_single_notice(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cached_preview = tmp_path / "notice-preview.pdf"
    cached_preview.write_text("cached-preview", encoding="utf-8")
    download_calls: list[object] = []
    logs: list[str] = []

    def _fail_download(request):
        download_calls.append(request)
        raise AssertionError("fresh Gmail download should not be used for cached preview reuse")

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.download_gmail_attachment_via_gog",
        _fail_download,
    )
    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", lambda _path: 7)

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="notice.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment,),
    )

    session = prepare_gmail_interpretation_session(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=message,
        gog_path=tmp_path / "gog.exe",
        account_email="only@example.com",
        selected_attachment=GmailAttachmentSelection(candidate=attachment, start_page=1),
        effective_output_dir=tmp_path / "output",
        cached_preview_paths={attachment.attachment_id: cached_preview},
        cached_preview_page_counts={attachment.attachment_id: 7},
        log_callback=logs.append,
    )
    try:
        assert isinstance(session, GmailInterpretationSession)
        assert download_calls == []
        assert session.downloaded_attachment.saved_path.exists()
        assert session.downloaded_attachment.saved_path.read_text(encoding="utf-8") == "cached-preview"
        assert session.downloaded_attachment.page_count == 7
        assert any("reusing preview cache" in entry for entry in logs)
    finally:
        session.cleanup()


def test_prepare_gmail_batch_session_falls_back_to_download_when_preview_cache_missing(
    monkeypatch,
    tmp_path: Path,
) -> None:
    download_calls: list[str] = []
    logs: list[str] = []

    def _fake_download(request):
        download_calls.append(request.filename)
        saved_path = request.output_dir / request.filename
        saved_path.write_text("downloaded", encoding="utf-8")
        return SimpleDownloadResult(saved_path=saved_path)

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.download_gmail_attachment_via_gog",
        _fake_download,
    )
    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", lambda _path: 4)

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment,),
    )

    session = prepare_gmail_batch_session(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=message,
        gog_path=tmp_path / "gog.exe",
        account_email="only@example.com",
        selected_attachments=(GmailAttachmentSelection(candidate=attachment, start_page=2),),
        selected_target_lang="AR",
        effective_output_dir=tmp_path / "output",
        cached_preview_paths={attachment.attachment_id: tmp_path / "missing-preview.pdf"},
        cached_preview_page_counts={attachment.attachment_id: 4},
        log_callback=logs.append,
    )
    try:
        downloaded = session.downloaded_attachments[0]
        assert download_calls == ["court.pdf"]
        assert downloaded.saved_path.exists()
        assert downloaded.saved_path.read_text(encoding="utf-8") == "downloaded"
        assert any("preview cache missing" in entry for entry in logs)
        assert any("downloaded fresh Gmail copy" in entry for entry in logs)
    finally:
        session.cleanup()


def test_prepare_gmail_batch_session_rejects_start_page_beyond_page_count(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def _fake_download(request):
        saved_path = request.output_dir / request.filename
        saved_path.write_bytes(b"%PDF-1.4\n")
        return SimpleDownloadResult(saved_path=saved_path)

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.download_gmail_attachment_via_gog",
        _fake_download,
    )
    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", lambda _path: 2)

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment,),
    )

    with pytest.raises(ValueError, match="Start page 4 exceeds page count 2"):
        prepare_gmail_batch_session(
            intake_context=InboundMailContext(
                message_id="msg-123",
                thread_id="thread-456",
                subject="Urgent filing",
            ),
            message=message,
            gog_path=tmp_path / "gog.exe",
            account_email="only@example.com",
            selected_attachments=(GmailAttachmentSelection(candidate=attachment, start_page=4),),
            selected_target_lang="EN",
            effective_output_dir=tmp_path / "output",
        )


def test_prepare_gmail_batch_session_rejects_image_start_page_above_one(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def _fake_download(request):
        saved_path = request.output_dir / request.filename
        saved_path.write_bytes(b"image-bytes")
        return SimpleDownloadResult(saved_path=saved_path)

    monkeypatch.setattr(
        "legalpdf_translate.gmail_batch.download_gmail_attachment_via_gog",
        _fake_download,
    )
    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", lambda _path: 1)

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="photo.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment,),
    )

    with pytest.raises(ValueError, match="Start page 2 exceeds page count 1"):
        prepare_gmail_batch_session(
            intake_context=InboundMailContext(
                message_id="msg-123",
                thread_id="thread-456",
                subject="Urgent filing",
            ),
            message=message,
            gog_path=tmp_path / "gog.exe",
            account_email="only@example.com",
            selected_attachments=(GmailAttachmentSelection(candidate=attachment, start_page=2),),
            selected_target_lang="EN",
            effective_output_dir=tmp_path / "output",
        )


class SimpleDownloadResult:
    def __init__(self, *, saved_path: Path) -> None:
        self.ok = True
        self.message = "Attachment downloaded successfully."
        self.stdout = ""
        self.stderr = ""
        self.saved_path = saved_path


def test_gmail_batch_consistency_signature_is_exact() -> None:
    signature = gmail_batch_consistency_signature(
        case_number=" 123/26.0 ",
        case_entity=" Tribunal ",
        case_city=" Beja ",
        court_email=" court@example.com ",
    )

    assert signature == ("123/26.0", "Tribunal", "Beja", "court@example.com")


def test_gmail_batch_confirmed_item_exposes_consistency_signature(tmp_path: Path) -> None:
    candidate = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    confirmed = GmailBatchConfirmedItem(
        downloaded_attachment=DownloadedGmailAttachment(
            candidate=candidate,
            saved_path=tmp_path / "court.pdf",
        ),
        translated_docx_path=tmp_path / "court_FR.docx",
        staged_translated_docx_path=tmp_path / "court_FR.docx",
        run_dir=tmp_path / "court_FR_run",
        translated_word_count=240,
        joblog_row_id=11,
        run_id="run-1",
        case_number="123/26.0",
        case_entity="Tribunal",
        case_city="Beja",
        court_email="court@example.com",
    )

    assert confirmed.consistency_signature == (
        "123/26.0",
        "Tribunal",
        "Beja",
        "court@example.com",
    )


def test_stage_gmail_batch_translated_docx_copies_into_batch_temp_dir(tmp_path: Path) -> None:
    session = GmailBatchSession(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=FetchedGmailMessage(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(),
        ),
        gog_path=tmp_path / "gog.exe",
        account_email="court@example.com",
        downloaded_attachments=(),
        download_dir=tmp_path / "batch",
    )
    translated = tmp_path / "translated.docx"
    translated.write_bytes(b"translated-bytes")

    staged = stage_gmail_batch_translated_docx(
        session=session,
        translated_docx_path=translated,
    )

    assert staged.exists()
    assert staged != translated.resolve()
    assert staged.parent == session.download_dir / "_draft_attachments"
    assert staged.name == translated.name
    assert staged.read_bytes() == b"translated-bytes"


def test_build_gmail_batch_session_payload_includes_run_linkage_and_finalization(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    translated.write_bytes(b"translated")
    session = GmailBatchSession(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=FetchedGmailMessage(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(),
        ),
        gog_path=tmp_path / "gog.exe",
        account_email="court@example.com",
        downloaded_attachments=(
            DownloadedGmailAttachment(
                candidate=GmailAttachmentCandidate(
                    attachment_id="att-1",
                    filename="court.pdf",
                    mime_type="application/pdf",
                    size_bytes=1024,
                    source_message_id="msg-123",
                ),
                saved_path=tmp_path / "court.pdf",
            ),
        ),
        download_dir=tmp_path / "batch",
        selected_target_lang="AR",
        effective_output_dir=tmp_path / "output",
        session_report_path=tmp_path / "gmail_batch_session.json",
    )
    session.confirmed_items.append(
        GmailBatchConfirmedItem(
            downloaded_attachment=session.downloaded_attachments[0],
            translated_docx_path=translated,
            staged_translated_docx_path=translated,
            run_dir=tmp_path / "translated_run",
            translated_word_count=264,
            joblog_row_id=77,
            run_id="run-77",
            case_number="21/25.0FBPTM",
            case_entity="Tribunal Judicial da Comarca de Beja",
            case_city="Beja",
            court_email="court@example.com",
        )
    )
    session.honorarios_requested = True
    session.requested_honorarios_path = tmp_path / "21-25_AR_20260308.docx"
    session.requested_honorarios_pdf_path = tmp_path / "21-25_AR_20260308.pdf"
    session.actual_honorarios_path = tmp_path / "Requerimento_Honorarios_21-25.docx"
    session.actual_honorarios_pdf_path = tmp_path / "Requerimento_Honorarios_21-25.pdf"
    session.honorarios_auto_renamed = True
    session.draft_preflight_result = "passed"
    session.draft_created = True
    session.final_attachment_basenames = (
        "21-25_AR_20260308.docx",
        "Requerimento_Honorarios_21-25.pdf",
    )
    session.finalization_report_context = {
        "kind": "gmail_finalization_report",
        "status": "ok",
        "finalization_state": "draft_ready",
        "session": {
            "session_id": session.session_id,
            "message_id": session.message.message_id,
            "thread_id": session.message.thread_id,
        },
    }

    payload = build_gmail_batch_session_payload(session)

    assert payload["session_id"] == session.session_id
    assert payload["intake_context"]["selected_target_lang"] == "AR"
    assert payload["intake_context"]["selected_attachments"] == [
        {"filename": "court.pdf", "start_page": 1, "page_count": 1}
    ]
    assert payload["runs"][0]["run_id"] == "run-77"
    assert payload["runs"][0]["joblog_row_id"] == 77
    assert payload["runs"][0]["durable_translated_docx_path"].endswith("translated.docx")
    assert payload["runs"][0]["translated_docx_basename"] == "translated.docx"
    assert payload["runs"][0]["staged_translated_docx_path"].endswith("translated.docx")
    assert payload["finalization"]["requested_pdf_save_path"].endswith("21-25_AR_20260308.pdf")
    assert payload["finalization"]["actual_saved_path"].endswith("Requerimento_Honorarios_21-25.docx")
    assert payload["finalization"]["actual_pdf_saved_path"].endswith("Requerimento_Honorarios_21-25.pdf")
    assert payload["finalization"]["auto_renamed"] is True
    assert payload["finalization"]["draft_created"] is True
    assert payload["finalization"]["final_attachment_basenames"] == [
        "21-25_AR_20260308.docx",
        "Requerimento_Honorarios_21-25.pdf",
    ]
    assert payload["finalization_report_context"]["status"] == "ok"
    assert payload["finalization_report_context"]["finalization_state"] == "draft_ready"


def test_write_gmail_batch_session_report_persists_json(tmp_path: Path) -> None:
    session = GmailBatchSession(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=FetchedGmailMessage(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(),
        ),
        gog_path=tmp_path / "gog.exe",
        account_email="court@example.com",
        downloaded_attachments=(),
        download_dir=tmp_path / "batch",
        session_report_path=tmp_path / "gmail_batch_session.json",
    )

    report_path = write_gmail_batch_session_report(session)

    assert report_path == tmp_path / "gmail_batch_session.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["session_id"] == session.session_id


def test_prepare_gmail_interpretation_session_creates_initial_report(
    monkeypatch,
    tmp_path: Path,
) -> None:
    cached_preview = tmp_path / "notice-preview.pdf"
    cached_preview.write_text("cached-preview", encoding="utf-8")
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="notice.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        source_message_id="msg-123",
    )
    message = FetchedGmailMessage(
        message_id="msg-123",
        thread_id="thread-456",
        subject="Urgent filing",
        from_header="Tribunal <court@example.com>",
        account_email="only@example.com",
        attachments=(attachment,),
    )

    monkeypatch.setattr("legalpdf_translate.gmail_batch.get_source_page_count", lambda _path: 7)

    session = prepare_gmail_interpretation_session(
        intake_context=InboundMailContext(
            message_id="msg-123",
            thread_id="thread-456",
            subject="Urgent filing",
        ),
        message=message,
        gog_path=tmp_path / "gog.exe",
        account_email="only@example.com",
        selected_attachment=GmailAttachmentSelection(candidate=attachment, start_page=1),
        effective_output_dir=tmp_path / "output",
        cached_preview_paths={attachment.attachment_id: cached_preview},
        cached_preview_page_counts={attachment.attachment_id: 7},
    )
    try:
        assert session.session_report_path is not None
        assert session.session_report_path.exists()
        payload = json.loads(session.session_report_path.read_text(encoding="utf-8"))
        assert payload["status"] == "prepared"
        assert payload["intake_context"]["selected_attachment_filename"] == "notice.pdf"
        assert payload["downloaded_notice"]["saved_path"].endswith("notice.pdf")
    finally:
        session.cleanup()


def test_build_gmail_interpretation_session_payload_includes_pdf_paths(tmp_path: Path) -> None:
    notice_path = tmp_path / "notice.pdf"
    notice_path.write_bytes(b"%PDF-1.4\n")
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="notice.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    session = GmailInterpretationSession(
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        downloaded_attachment=DownloadedGmailAttachment(
            candidate=attachment,
            saved_path=notice_path,
            start_page=1,
            page_count=4,
        ),
        download_dir=tmp_path / "downloads",
        effective_output_dir=tmp_path / "output",
        session_report_path=tmp_path / "gmail_interpretation_session.json",
    )
    session.status = "draft_ready"
    session.honorarios_requested = True
    session.requested_honorarios_path = tmp_path / "interpretation_honorarios.docx"
    session.requested_honorarios_pdf_path = tmp_path / "interpretation_honorarios.pdf"
    session.actual_honorarios_path = tmp_path / "Requerimento_Honorarios_109-26.docx"
    session.actual_honorarios_pdf_path = tmp_path / "Requerimento_Honorarios_109-26.pdf"
    session.honorarios_auto_renamed = True
    session.draft_created = True
    session.final_attachment_basenames = ("Requerimento_Honorarios_109-26.pdf",)

    payload = build_gmail_interpretation_session_payload(session)

    assert payload["status"] == "draft_ready"
    assert payload["intake_context"]["selected_attachment"]["page_count"] == 4
    assert payload["downloaded_notice"]["saved_path"].endswith("notice.pdf")
    assert payload["finalization"]["requested_save_path"].endswith("interpretation_honorarios.docx")
    assert payload["finalization"]["requested_pdf_save_path"].endswith("interpretation_honorarios.pdf")
    assert payload["finalization"]["actual_saved_path"].endswith("Requerimento_Honorarios_109-26.docx")
    assert payload["finalization"]["actual_pdf_saved_path"].endswith("Requerimento_Honorarios_109-26.pdf")
    assert payload["finalization"]["final_attachment_basenames"] == ["Requerimento_Honorarios_109-26.pdf"]


def test_write_gmail_interpretation_session_report_persists_json(tmp_path: Path) -> None:
    notice_path = tmp_path / "notice.pdf"
    notice_path.write_bytes(b"%PDF-1.4\n")
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="notice.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    session = GmailInterpretationSession(
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        downloaded_attachment=DownloadedGmailAttachment(
            candidate=attachment,
            saved_path=notice_path,
            start_page=1,
            page_count=4,
        ),
        download_dir=tmp_path / "downloads",
        session_report_path=tmp_path / "gmail_interpretation_session.json",
    )

    report_path = write_gmail_interpretation_session_report(session)

    assert report_path == tmp_path / "gmail_interpretation_session.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["session_id"] == session.session_id
    assert payload["downloaded_notice"]["filename"] == "notice.pdf"
