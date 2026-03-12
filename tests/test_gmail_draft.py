from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from docx import Document

from legalpdf_translate.gmail_draft import (
    GmailPrereqStatus,
    build_gmail_batch_reply_request,
    build_honorarios_gmail_body,
    build_honorarios_gmail_request,
    build_honorarios_gmail_subject,
    build_manual_interpretation_gmail_request,
    build_manual_interpretation_honorarios_gmail_subject,
    build_interpretation_gmail_reply_request,
    build_interpretation_honorarios_gmail_body,
    create_gmail_draft_via_gog,
    assess_gmail_draft_prereqs,
    validate_translated_docx_artifacts_for_gmail_draft,
)
from legalpdf_translate.user_profile import default_primary_profile


def _profile(**overrides: str):
    profile = default_primary_profile(email="adel@example.com")
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


def _write_docx(path: Path, *paragraphs: str) -> None:
    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    document.save(path)


def test_build_honorarios_gmail_subject_uses_case_number() -> None:
    assert (
        build_honorarios_gmail_subject("109/26.0PBBJA")
        == "Traduções e requerimento de honorários - Processo 109/26.0PBBJA"
    )


def test_build_manual_interpretation_honorarios_gmail_subject_uses_case_number() -> None:
    assert (
        build_manual_interpretation_honorarios_gmail_subject("109/26.0PBBJA")
        == "Requerimento de honorários - Processo 109/26.0PBBJA"
    )


def test_build_honorarios_gmail_body_includes_phone_when_present() -> None:
    profile = _profile(phone_number="+351912345678")

    body = build_honorarios_gmail_body(profile)

    assert body.endswith(f"Atenciosamente,\n{profile.document_name}\n+351912345678\n")


def test_build_honorarios_gmail_body_omits_phone_when_blank() -> None:
    profile = _profile(phone_number="")

    body = build_honorarios_gmail_body(profile)

    assert body.endswith(f"Atenciosamente,\n{profile.document_name}\n")
    assert "+351" not in body


def test_build_honorarios_gmail_request_uses_exact_body_and_attachments(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.pdf"
    translated.write_bytes(b"a")
    honorarios.write_bytes(b"b")
    profile = _profile(phone_number="+351912345678")

    request = build_honorarios_gmail_request(
        gog_path=tmp_path / "gog.exe",
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        case_number="109/26.0PBBJA",
        translation_docx=translated,
        honorarios_pdf=honorarios,
        profile=profile,
    )

    assert request.account_email == "adel.belghali@gmail.com"
    assert request.to_email == "beja.judicial@tribunais.org.pt"
    assert request.subject == "Traduções e requerimento de honorários - Processo 109/26.0PBBJA"
    assert request.body == build_honorarios_gmail_body(profile)
    assert request.attachments == (translated.resolve(), honorarios.resolve())


def test_build_honorarios_gmail_request_requires_existing_attachments(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    translated.write_bytes(b"a")
    missing = tmp_path / "missing.pdf"

    with pytest.raises(ValueError, match="Honorários PDF not found"):
        build_honorarios_gmail_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            case_number="109/26.0PBBJA",
            translation_docx=translated,
            honorarios_pdf=missing,
            profile=_profile(),
        )


def test_build_honorarios_gmail_request_requires_pdf_attachment(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    wrong_honorarios = tmp_path / "honorarios.docx"
    translated.write_bytes(b"a")
    wrong_honorarios.write_bytes(b"b")

    with pytest.raises(ValueError, match=r"Honorários PDF must be a \.pdf file"):
        build_honorarios_gmail_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            case_number="109/26.0PBBJA",
            translation_docx=translated,
            honorarios_pdf=wrong_honorarios,
            profile=_profile(),
        )


def test_build_gmail_batch_reply_request_reuses_subject_reply_id_and_all_attachments(tmp_path: Path) -> None:
    translated_one = tmp_path / "translated-1.docx"
    translated_two = tmp_path / "translated-2.docx"
    honorarios = tmp_path / "honorarios.pdf"
    translated_one.write_bytes(b"a")
    translated_two.write_bytes(b"b")
    honorarios.write_bytes(b"c")
    profile = _profile(phone_number="+351912345678")

    request = build_gmail_batch_reply_request(
        gog_path=tmp_path / "gog.exe",
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        subject="Original Gmail subject",
        reply_to_message_id="msg-123",
        translated_docxs=(translated_one, translated_two),
        honorarios_pdf=honorarios,
        profile=profile,
    )

    assert request.subject == "Original Gmail subject"
    assert request.reply_to_message_id == "msg-123"
    assert request.body == build_honorarios_gmail_body(profile)
    assert request.attachments == (
        translated_one.resolve(),
        translated_two.resolve(),
        honorarios.resolve(),
    )


def test_build_interpretation_gmail_reply_request_attaches_only_honorarios(tmp_path: Path) -> None:
    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"%PDF-1.7")
    profile = _profile(phone_number="+351912345678")

    request = build_interpretation_gmail_reply_request(
        gog_path=tmp_path / "gog.exe",
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        subject="Original Gmail subject",
        reply_to_message_id="msg-123",
        honorarios_pdf=honorarios,
        profile=profile,
    )

    assert request.subject == "Original Gmail subject"
    assert request.reply_to_message_id == "msg-123"
    assert request.body == build_interpretation_honorarios_gmail_body(profile)
    assert request.attachments == (honorarios.resolve(),)
    assert "notificação" not in request.body.casefold()

def test_build_interpretation_gmail_reply_request_requires_honorarios_pdf(tmp_path: Path) -> None:
    missing = tmp_path / "honorarios.pdf"
    with pytest.raises(ValueError, match="Honorários PDF not found"):
        build_interpretation_gmail_reply_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            subject="Original Gmail subject",
            reply_to_message_id="msg-123",
            honorarios_pdf=missing,
            profile=_profile(),
        )


def test_build_manual_interpretation_gmail_request_uses_pdf_only(tmp_path: Path) -> None:
    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"%PDF-1.7")
    profile = _profile(phone_number="+351912345678")

    request = build_manual_interpretation_gmail_request(
        gog_path=tmp_path / "gog.exe",
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        case_number="109/26.0PBBJA",
        honorarios_pdf=honorarios,
        profile=profile,
    )

    assert request.subject == "Requerimento de honorários - Processo 109/26.0PBBJA"
    assert request.reply_to_message_id is None
    assert request.body == build_interpretation_honorarios_gmail_body(profile)
    assert request.attachments == (honorarios.resolve(),)


def test_build_gmail_batch_reply_request_requires_reply_id_and_translations(tmp_path: Path) -> None:
    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"c")

    with pytest.raises(ValueError, match="original Gmail message ID"):
        build_gmail_batch_reply_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            subject="Original Gmail subject",
            reply_to_message_id="",
            translated_docxs=(tmp_path / "translated-1.docx",),
            honorarios_pdf=honorarios,
            profile=_profile(),
        )

    with pytest.raises(ValueError, match="At least one translated DOCX"):
        build_gmail_batch_reply_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            subject="Original Gmail subject",
            reply_to_message_id="msg-123",
            translated_docxs=(),
            honorarios_pdf=honorarios,
            profile=_profile(),
        )


def test_build_gmail_batch_reply_request_rejects_duplicate_attachment_paths(tmp_path: Path) -> None:
    translated_one = tmp_path / "translated-1.docx"
    translated_two = tmp_path / "translated-2.docx"
    honorarios = tmp_path / "honorarios.pdf"
    translated_one.write_bytes(b"a")
    translated_two.write_bytes(b"b")
    honorarios.write_bytes(b"c")

    with pytest.raises(ValueError, match="Duplicate Gmail draft attachment paths"):
        build_gmail_batch_reply_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            subject="Original Gmail subject",
            reply_to_message_id="msg-123",
            translated_docxs=(translated_one, translated_two, translated_one),
            honorarios_pdf=honorarios,
            profile=_profile(),
        )


def test_validate_translated_docx_artifacts_rejects_honorarios_like_translation(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.pdf"
    _write_docx(
        translated,
        "Venho por este meio requerer o pagamento dos honorários devidos.",
        "O documento traduzido contém 264 palavras.",
        "O Pagamento deverá ser efetuado para o seguinte IBAN: PT50003506490000832760029",
    )
    honorarios.write_bytes(b"%PDF-1.7")

    with pytest.raises(ValueError, match="contaminated with honorários content"):
        validate_translated_docx_artifacts_for_gmail_draft(
            translated_docxs=(translated,),
            honorarios_pdf=honorarios,
        )


def test_validate_translated_docx_artifacts_requires_honorarios_pdf(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.docx"
    _write_docx(translated, "Documento traduzido em árabe.")
    honorarios.write_bytes(b"docx")

    with pytest.raises(ValueError, match=r"Honorários PDF must be a \.pdf file"):
        validate_translated_docx_artifacts_for_gmail_draft(
            translated_docxs=(translated,),
            honorarios_pdf=honorarios,
        )


def test_validate_translated_docx_artifacts_accepts_distinct_clean_files(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.pdf"
    _write_docx(translated, "هذه ترجمة عربية سليمة.")
    honorarios.write_bytes(b"%PDF-1.7")

    validated = validate_translated_docx_artifacts_for_gmail_draft(
        translated_docxs=(translated,),
        honorarios_pdf=honorarios,
    )

    assert validated == (translated.resolve(),)


def test_assess_gmail_prereqs_autodetects_single_account(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    def _fake_run(gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {
                "accounts": [
                    {"email": "adel.belghali@gmail.com", "services": ["gmail"]},
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_draft._is_windows", lambda: True)
    monkeypatch.setattr("legalpdf_translate.gmail_draft.resolve_gog_path", lambda configured_gog_path="": gog_path)
    monkeypatch.setattr("legalpdf_translate.gmail_draft._run_gog_json", _fake_run)

    status = assess_gmail_draft_prereqs()

    assert status.ready is True
    assert status.gog_path == gog_path
    assert status.account_email == "adel.belghali@gmail.com"


def test_assess_gmail_prereqs_requires_explicit_account_when_multiple(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    gog_path.write_bytes(b"")

    def _fake_run(gog: Path, args: list[str]):
        if args[:3] == ["auth", "credentials", "list"]:
            return {"clients": [{"client": "default"}]}
        if args[:2] == ["auth", "list"]:
            return {
                "accounts": [
                    {"email": "adel.belghali@gmail.com", "services": ["gmail"]},
                    {"email": "other@example.com", "services": ["gmail"]},
                ]
            }
        raise AssertionError(args)

    monkeypatch.setattr("legalpdf_translate.gmail_draft._is_windows", lambda: True)
    monkeypatch.setattr("legalpdf_translate.gmail_draft.resolve_gog_path", lambda configured_gog_path="": gog_path)
    monkeypatch.setattr("legalpdf_translate.gmail_draft._run_gog_json", _fake_run)

    status = assess_gmail_draft_prereqs()

    assert status.ready is False
    assert "Multiple Gmail accounts" in status.message
    assert status.accounts == ("adel.belghali@gmail.com", "other@example.com")


def test_create_gmail_draft_via_gog_builds_expected_command(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.pdf"
    translated.write_bytes(b"a")
    honorarios.write_bytes(b"b")

    captured: dict[str, object] = {}

    def _fake_run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        body_path = Path(cmd[cmd.index("--body-file") + 1])
        captured["body"] = body_path.read_text(encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, '{"draftId":"123"}', "")

    monkeypatch.setattr("legalpdf_translate.gmail_draft._run_capture", _fake_run_capture)

    request = build_honorarios_gmail_request(
        gog_path=gog_path,
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        case_number="109/26.0PBBJA",
        translation_docx=translated,
        honorarios_pdf=honorarios,
        profile=_profile(phone_number="+351912345678"),
    )
    result = create_gmail_draft_via_gog(request)

    assert result.ok is True
    assert result.payload == {"draftId": "123"}
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert cmd[:4] == [str(gog_path), "gmail", "drafts", "create"]
    assert "--account" in cmd
    assert "--to" in cmd
    assert "--subject" in cmd
    assert cmd.count("--attach") == 2
    assert captured["body"] == build_honorarios_gmail_body(_profile(phone_number="+351912345678"))


def test_create_gmail_draft_via_gog_includes_reply_to_message_id(monkeypatch, tmp_path: Path) -> None:
    gog_path = tmp_path / "gog.exe"
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.pdf"
    translated.write_bytes(b"a")
    honorarios.write_bytes(b"b")

    captured: dict[str, object] = {}

    def _fake_run_capture(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, '{"draftId":"123"}', "")

    monkeypatch.setattr("legalpdf_translate.gmail_draft._run_capture", _fake_run_capture)

    request = build_gmail_batch_reply_request(
        gog_path=gog_path,
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        subject="Original Gmail subject",
        reply_to_message_id="msg-123",
        translated_docxs=(translated,),
        honorarios_pdf=honorarios,
        profile=_profile(phone_number="+351912345678"),
    )
    result = create_gmail_draft_via_gog(request)

    assert result.ok is True
    cmd = captured["cmd"]
    assert isinstance(cmd, list)
    assert "--reply-to-message-id" in cmd
    assert cmd[cmd.index("--reply-to-message-id") + 1] == "msg-123"
