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

GMAIL_DRAFTS_URL = "https://mail.google.com/mail/u/0/#drafts"
WINDOWS_GOG_WINGET_GLOB = "steipete.gogcli*/gog.exe"
HONORARIOS_GMAIL_BODY = """Bom dia,

Segue em anexo as traduções conforme solicitadas, bem como o requerimento de honorários. 

Estou à disposição para quaisquer esclarecimentos adicionais que se façam necessários.

Atenciosamente,
Adel Belghali
"""


@dataclass(slots=True)
class GmailDraftRequest:
    gog_path: Path
    account_email: str
    to_email: str
    subject: str
    body: str
    attachments: tuple[Path, ...]


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


def build_honorarios_gmail_request(
    *,
    gog_path: Path,
    account_email: str,
    to_email: str,
    case_number: str,
    translation_docx: Path,
    honorarios_docx: Path,
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
    resolved_honorarios = honorarios_docx.expanduser().resolve()
    missing: list[str] = []
    if not resolved_translation.exists():
        missing.append(f"Translated DOCX not found: {resolved_translation}")
    if not resolved_honorarios.exists():
        missing.append(f"Honorários DOCX not found: {resolved_honorarios}")
    if missing:
        raise ValueError("\n".join(missing))
    return GmailDraftRequest(
        gog_path=gog_path.expanduser().resolve(),
        account_email=sender_account,
        to_email=recipient,
        subject=build_honorarios_gmail_subject(process_number),
        body=HONORARIOS_GMAIL_BODY,
        attachments=(resolved_translation, resolved_honorarios),
    )


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
