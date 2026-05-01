"""Windows Gmail draft creation via gog CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Any, Sequence
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from .user_profile import UserProfile

GMAIL_DRAFTS_URL = "https://mail.google.com/mail/u/0/#drafts"
WINDOWS_GOG_WINGET_GLOB = "steipete.gogcli*/gog.exe"
_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_HONORARIOS_SIGNATURE_MARKERS = (
    "Venho por este meio requerer o pagamento dos honorários",
    "O documento traduzido contém",
    "O Pagamento deverá ser efetuado para o seguinte IBAN",
)
_HONORARIOS_GMAIL_BODY_PREFIX = """Bom dia,

Segue em anexo as traduções conforme solicitadas, bem como o requerimento de honorários. 

Estou à disposição para quaisquer esclarecimentos adicionais que se façam necessários.

"""
_INTERPRETATION_HONORARIOS_GMAIL_BODY_PREFIX = """Bom dia,

Segue em anexo o requerimento de honorários referente ao serviço de interpretação.

Estou à disposição para quaisquer esclarecimentos adicionais que se façam necessários.

"""


@dataclass(slots=True)
class GmailDraftRequest:
    gog_path: Path
    account_email: str
    to_email: str
    subject: str
    body: str
    attachments: tuple[Path, ...]
    reply_to_message_id: str | None = None


@dataclass(slots=True)
class GmailDraftResult:
    ok: bool
    message: str
    stdout: str
    stderr: str
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class GmailPrereqStatus:
    ready: bool
    message: str
    gog_path: Path | None = None
    account_email: str | None = None
    accounts: tuple[str, ...] = ()


def build_honorarios_gmail_subject(case_number: str) -> str:
    return f"Traduções e requerimento de honorários - Processo {case_number.strip()}"


def build_manual_interpretation_honorarios_gmail_subject(case_number: str) -> str:
    return f"Requerimento de honorários - Processo {case_number.strip()}"


def build_honorarios_gmail_body(profile: UserProfile) -> str:
    signature_lines = ["Atenciosamente,", profile.document_name.strip()]
    phone_number = profile.phone_number.strip()
    if phone_number:
        signature_lines.append(phone_number)
    return _HONORARIOS_GMAIL_BODY_PREFIX + "\n".join(signature_lines) + "\n"


def build_interpretation_honorarios_gmail_body(profile: UserProfile) -> str:
    signature_lines = ["Atenciosamente,", profile.document_name.strip()]
    phone_number = profile.phone_number.strip()
    if phone_number:
        signature_lines.append(phone_number)
    return _INTERPRETATION_HONORARIOS_GMAIL_BODY_PREFIX + "\n".join(signature_lines) + "\n"


def build_honorarios_gmail_request(
    *,
    gog_path: Path,
    account_email: str,
    to_email: str,
    case_number: str,
    translation_docx: Path,
    honorarios_pdf: Path,
    profile: UserProfile,
) -> GmailDraftRequest:
    recipient = to_email.strip()
    process_number = case_number.strip()
    sender_account = account_email.strip()
    if not recipient:
        raise ValueError("Court Email is required to create a Gmail draft.")
    if not process_number:
        raise ValueError("Case number is required to create the Gmail draft subject.")
    if not sender_account:
        raise ValueError("A Gmail account is required to create the draft.")
    resolved_translation = translation_docx.expanduser().resolve()
    resolved_honorarios = _resolve_honorarios_pdf_attachment(honorarios_pdf)
    missing: list[str] = []
    if not resolved_translation.exists():
        missing.append(f"Translated DOCX not found: {resolved_translation}")
    if missing:
        raise ValueError("\n".join(missing))
    _require_distinct_attachment_paths((resolved_translation, resolved_honorarios))
    return GmailDraftRequest(
        gog_path=gog_path.expanduser().resolve(),
        account_email=sender_account,
        to_email=recipient,
        subject=build_honorarios_gmail_subject(process_number),
        body=build_honorarios_gmail_body(profile),
        attachments=(resolved_translation, resolved_honorarios),
    )


def build_gmail_batch_reply_request(
    *,
    gog_path: Path,
    account_email: str,
    to_email: str,
    subject: str,
    reply_to_message_id: str,
    translated_docxs: Sequence[Path],
    honorarios_pdf: Path,
    profile: UserProfile,
) -> GmailDraftRequest:
    sender_account = account_email.strip()
    recipient = to_email.strip()
    original_subject = subject.strip()
    reply_message_id = reply_to_message_id.strip()
    if not sender_account:
        raise ValueError("A Gmail account is required to create the draft.")
    if not recipient:
        raise ValueError("Court Email is required to create the Gmail draft.")
    if not original_subject:
        raise ValueError("The original Gmail subject is required to create the reply draft.")
    if not reply_message_id:
        raise ValueError("The original Gmail message ID is required to create the reply draft.")
    resolved_translations = tuple(path.expanduser().resolve() for path in translated_docxs)
    if not resolved_translations:
        raise ValueError("At least one translated DOCX is required to create the reply draft.")
    missing: list[str] = []
    for translation in resolved_translations:
        if not translation.exists():
            missing.append(f"Translated DOCX not found: {translation}")
    resolved_honorarios = _resolve_honorarios_pdf_attachment(honorarios_pdf)
    if missing:
        raise ValueError("\n".join(missing))
    _require_distinct_attachment_paths(resolved_translations + (resolved_honorarios,))
    return GmailDraftRequest(
        gog_path=gog_path.expanduser().resolve(),
        account_email=sender_account,
        to_email=recipient,
        subject=original_subject,
        body=build_honorarios_gmail_body(profile),
        attachments=resolved_translations + (resolved_honorarios,),
        reply_to_message_id=reply_message_id,
    )


def build_interpretation_gmail_reply_request(
    *,
    gog_path: Path,
    account_email: str,
    to_email: str,
    subject: str,
    reply_to_message_id: str,
    honorarios_pdf: Path,
    profile: UserProfile,
) -> GmailDraftRequest:
    sender_account = account_email.strip()
    recipient = to_email.strip()
    original_subject = subject.strip()
    reply_message_id = reply_to_message_id.strip()
    if not sender_account:
        raise ValueError("A Gmail account is required to create the draft.")
    if not recipient:
        raise ValueError("Court Email is required to create the Gmail draft.")
    if not original_subject:
        raise ValueError("The original Gmail subject is required to create the reply draft.")
    if not reply_message_id:
        raise ValueError("The original Gmail message ID is required to create the reply draft.")
    resolved_honorarios = _resolve_honorarios_pdf_attachment(honorarios_pdf)
    return GmailDraftRequest(
        gog_path=gog_path.expanduser().resolve(),
        account_email=sender_account,
        to_email=recipient,
        subject=original_subject,
        body=build_interpretation_honorarios_gmail_body(profile),
        attachments=(resolved_honorarios,),
        reply_to_message_id=reply_message_id,
    )


def build_manual_interpretation_gmail_request(
    *,
    gog_path: Path,
    account_email: str,
    to_email: str,
    case_number: str,
    honorarios_pdf: Path,
    profile: UserProfile,
) -> GmailDraftRequest:
    sender_account = account_email.strip()
    recipient = to_email.strip()
    process_number = case_number.strip()
    if not sender_account:
        raise ValueError("A Gmail account is required to create the draft.")
    if not recipient:
        raise ValueError("Court Email is required to create the Gmail draft.")
    if not process_number:
        raise ValueError("Case number is required to create the Gmail draft subject.")
    resolved_honorarios = _resolve_honorarios_pdf_attachment(honorarios_pdf)
    return GmailDraftRequest(
        gog_path=gog_path.expanduser().resolve(),
        account_email=sender_account,
        to_email=recipient,
        subject=build_manual_interpretation_honorarios_gmail_subject(process_number),
        body=build_interpretation_honorarios_gmail_body(profile),
        attachments=(resolved_honorarios,),
    )


def validate_translated_docx_artifacts_for_gmail_draft(
    *,
    translated_docxs: Sequence[Path],
    honorarios_pdf: Path,
) -> tuple[Path, ...]:
    resolved_translations = tuple(path.expanduser().resolve() for path in translated_docxs)
    resolved_honorarios = _resolve_honorarios_pdf_attachment(honorarios_pdf)
    missing: list[str] = []
    for translation in resolved_translations:
        if not translation.exists():
            missing.append(f"Translated DOCX not found: {translation}")
    if missing:
        raise ValueError("\n".join(missing))
    _require_distinct_attachment_paths(resolved_translations + (resolved_honorarios,))
    for translation in resolved_translations:
        if _docx_contains_honorarios_signature(translation):
            raise ValueError(
                "Translated DOCX is contaminated with honorários content and cannot be attached:\n"
                f"{translation}\n\n"
                "Rerun the translation to create a clean translated DOCX before creating the Gmail draft."
            )
    return resolved_translations


def assess_gmail_draft_prereqs(
    *,
    configured_gog_path: str = "",
    configured_account_email: str = "",
) -> GmailPrereqStatus:
    if not _is_windows():
        return GmailPrereqStatus(
            ready=False,
            message="Windows-only feature. Gmail draft integration is unavailable in this environment.",
        )
    gog_path = resolve_gog_path(configured_gog_path=configured_gog_path)
    if gog_path is None:
        return GmailPrereqStatus(
            ready=False,
            message=(
                "Windows gog.exe not found. Install gog on Windows or set the Gmail gog path in Settings."
            ),
        )
    clients_result = _run_gog_json(gog_path, ["auth", "credentials", "list", "--json", "--no-input"])
    if clients_result is None:
        return GmailPrereqStatus(
            ready=False,
            message=(
                "Unable to read gog OAuth credentials. Configure Google OAuth first with "
                "`gog auth credentials set <client_secret.json>`."
            ),
            gog_path=gog_path,
        )
    clients = clients_result.get("clients", [])
    if not isinstance(clients, list) or not clients:
        return GmailPrereqStatus(
            ready=False,
            message=(
                "No Google OAuth client credentials are configured for gog. Run "
                "`gog auth credentials set <client_secret.json>` first."
            ),
            gog_path=gog_path,
        )
    accounts_result = _run_gog_json(gog_path, ["auth", "list", "--json", "--no-input"])
    if accounts_result is None:
        return GmailPrereqStatus(
            ready=False,
            message=(
                "Unable to read gog authenticated accounts. Run "
                "`gog auth add <your@gmail.com> --services gmail` first."
            ),
            gog_path=gog_path,
        )
    accounts = _extract_gmail_accounts(accounts_result)
    if not accounts:
        return GmailPrereqStatus(
            ready=False,
            message=(
                "No Gmail account is authenticated in gog. Run "
                "`gog auth add <your@gmail.com> --services gmail` first."
            ),
            gog_path=gog_path,
        )
    configured_email = configured_account_email.strip()
    if configured_email:
        if configured_email not in accounts:
            return GmailPrereqStatus(
                ready=False,
                message=(
                    f"The configured Gmail account '{configured_email}' is not available in gog. "
                    "Use Settings to pick an authenticated Gmail account."
                ),
                gog_path=gog_path,
                accounts=tuple(accounts),
            )
        return GmailPrereqStatus(
            ready=True,
            message=f"Gmail draft prerequisites are ready for {configured_email}.",
            gog_path=gog_path,
            account_email=configured_email,
            accounts=tuple(accounts),
        )
    if len(accounts) == 1:
        return GmailPrereqStatus(
            ready=True,
            message=f"Gmail draft prerequisites are ready for {accounts[0]}.",
            gog_path=gog_path,
            account_email=accounts[0],
            accounts=tuple(accounts),
        )
    return GmailPrereqStatus(
        ready=False,
        message=(
            "Multiple Gmail accounts are authenticated in gog. Set the Gmail account in Settings "
            "before creating drafts."
        ),
        gog_path=gog_path,
        accounts=tuple(accounts),
    )


def create_gmail_draft_via_gog(request: GmailDraftRequest) -> GmailDraftResult:
    body_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            prefix="legalpdf_gmail_body_",
            suffix=".txt",
            delete=False,
        ) as handle:
            handle.write(request.body)
            body_path = Path(handle.name)
        cmd = [
            str(request.gog_path),
            "gmail",
            "drafts",
            "create",
            "--json",
            "--no-input",
            "--account",
            request.account_email,
            "--to",
            request.to_email,
            "--subject",
            request.subject,
            "--body-file",
            str(body_path),
        ]
        if request.reply_to_message_id:
            cmd.extend(["--reply-to-message-id", request.reply_to_message_id])
        for attachment in request.attachments:
            cmd.extend(["--attach", str(attachment)])
        completed = _run_capture(cmd)
        payload: dict[str, Any] | None = None
        stdout = completed.stdout.strip()
        if stdout:
            try:
                parsed = json.loads(stdout)
                if isinstance(parsed, dict):
                    payload = parsed
            except json.JSONDecodeError:
                payload = None
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            message = stderr or stdout or "Failed to create Gmail draft via gog."
            return GmailDraftResult(
                ok=False,
                message=message,
                stdout=stdout,
                stderr=stderr,
                payload=payload,
            )
        return GmailDraftResult(
            ok=True,
            message="Gmail draft created successfully.",
            stdout=stdout,
            stderr=completed.stderr.strip(),
            payload=payload,
        )
    finally:
        if body_path is not None:
            try:
                body_path.unlink(missing_ok=True)
            except OSError:
                pass


def resolve_gog_path(*, configured_gog_path: str = "") -> Path | None:
    configured = configured_gog_path.strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    candidate = _known_windows_gog_path()
    if candidate is not None:
        return candidate
    candidate = _gog_from_where()
    if candidate is not None:
        return candidate
    return None


def _extract_gmail_accounts(payload: dict[str, Any]) -> list[str]:
    raw_accounts = payload.get("accounts", [])
    if not isinstance(raw_accounts, list):
        return []
    accounts: list[str] = []
    for item in raw_accounts:
        if not isinstance(item, dict):
            continue
        email = str(item.get("email", "") or "").strip()
        services = item.get("services", [])
        if not email or not isinstance(services, list):
            continue
        if any(str(service).strip().lower() == "gmail" for service in services):
            accounts.append(email)
    return accounts


def _resolve_honorarios_pdf_attachment(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.suffix.casefold() != ".pdf":
        raise ValueError(f"Honorários PDF must be a .pdf file: {resolved}")
    if not resolved.exists():
        raise ValueError(f"Honorários PDF not found: {resolved}")
    return resolved


def _require_distinct_attachment_paths(paths: Sequence[Path]) -> None:
    duplicates: list[Path] = []
    seen: set[Path] = set()
    for candidate in paths:
        if candidate in seen and candidate not in duplicates:
            duplicates.append(candidate)
            continue
        seen.add(candidate)
    if duplicates:
        raise ValueError(
            "Duplicate Gmail draft attachment paths are not allowed:\n"
            + "\n".join(str(path) for path in duplicates)
        )


def _docx_contains_honorarios_signature(path: Path) -> bool:
    text = _read_docx_visible_text(path).casefold()
    matches = [marker for marker in _HONORARIOS_SIGNATURE_MARKERS if marker.casefold() in text]
    return (
        _HONORARIOS_SIGNATURE_MARKERS[0].casefold() in text
        or len(matches) >= 2
    )


def _read_docx_visible_text(path: Path) -> str:
    resolved = path.expanduser().resolve()
    try:
        with ZipFile(resolved, "r") as archive:
            raw_xml = archive.read("word/document.xml")
    except FileNotFoundError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Failed to inspect DOCX text for Gmail draft attachment: {resolved}") from exc
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise ValueError(f"Failed to parse DOCX text for Gmail draft attachment: {resolved}") from exc
    parts = [
        node.text.strip()
        for node in root.findall(".//w:t", _DOCX_NS)
        if isinstance(node.text, str) and node.text.strip()
    ]
    return " ".join(parts)


def _is_windows() -> bool:
    return os.name == "nt"


def _known_windows_gog_path() -> Path | None:
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_appdata:
        return None
    package_root = Path(local_appdata) / "Microsoft" / "WinGet" / "Packages"
    if not package_root.exists():
        return None
    candidates = sorted(package_root.glob(WINDOWS_GOG_WINGET_GLOB))
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _gog_from_where() -> Path | None:
    found = shutil.which("gog")
    if found:
        candidate = Path(found)
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    if not _is_windows():
        return None
    try:
        completed = _run_capture(["where", "gog"])
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    for line in completed.stdout.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        candidate = Path(cleaned)
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()
    return None


def _run_gog_json(gog_path: Path, args: list[str]) -> dict[str, Any] | None:
    completed = _run_capture([str(gog_path), *args])
    if completed.returncode != 0:
        return None
    stdout = completed.stdout.strip()
    if not stdout:
        return None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _run_capture(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        text=True,
        capture_output=True,
        check=False,
    )
