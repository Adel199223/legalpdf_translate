from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from legalpdf_translate.gmail_draft import (
    HONORARIOS_GMAIL_BODY,
    GmailPrereqStatus,
    build_honorarios_gmail_request,
    build_honorarios_gmail_subject,
    create_gmail_draft_via_gog,
    assess_gmail_draft_prereqs,
)


def test_build_honorarios_gmail_subject_uses_case_number() -> None:
    assert (
        build_honorarios_gmail_subject("109/26.0PBBJA")
        == "Traduções e requerimento de honorários - Processo 109/26.0PBBJA"
    )


def test_build_honorarios_gmail_request_uses_exact_body_and_attachments(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    honorarios = tmp_path / "honorarios.docx"
    translated.write_bytes(b"a")
    honorarios.write_bytes(b"b")

    request = build_honorarios_gmail_request(
        gog_path=tmp_path / "gog.exe",
        account_email="adel.belghali@gmail.com",
        to_email="beja.judicial@tribunais.org.pt",
        case_number="109/26.0PBBJA",
        translation_docx=translated,
        honorarios_docx=honorarios,
    )

    assert request.account_email == "adel.belghali@gmail.com"
    assert request.to_email == "beja.judicial@tribunais.org.pt"
    assert request.subject == "Traduções e requerimento de honorários - Processo 109/26.0PBBJA"
    assert request.body == HONORARIOS_GMAIL_BODY
    assert request.attachments == (translated.resolve(), honorarios.resolve())


def test_build_honorarios_gmail_request_requires_existing_attachments(tmp_path: Path) -> None:
    translated = tmp_path / "translated.docx"
    translated.write_bytes(b"a")
    missing = tmp_path / "missing.docx"

    with pytest.raises(ValueError, match="Honorários DOCX not found"):
        build_honorarios_gmail_request(
            gog_path=tmp_path / "gog.exe",
            account_email="adel.belghali@gmail.com",
            to_email="beja.judicial@tribunais.org.pt",
            case_number="109/26.0PBBJA",
            translation_docx=translated,
            honorarios_docx=missing,
        )


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
    honorarios = tmp_path / "honorarios.docx"
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
        honorarios_docx=honorarios,
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
    assert captured["body"] == HONORARIOS_GMAIL_BODY
