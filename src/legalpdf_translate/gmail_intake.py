"""Localhost Gmail intake bridge for exact message context handoff."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


@dataclass(frozen=True, slots=True)
class InboundMailContext:
    message_id: str
    thread_id: str
    subject: str
    account_email: str | None = None
    handoff_session_id: str | None = None
    source_gmail_url: str | None = None

    @classmethod
    def from_payload(cls, payload: object) -> InboundMailContext:
        if not isinstance(payload, dict):
            raise ValueError("JSON object expected.")

        allowed_keys = {
            "message_id",
            "thread_id",
            "subject",
            "account_email",
            "handoff_session_id",
            "source_gmail_url",
        }
        unknown_keys = sorted(str(key) for key in payload.keys() if key not in allowed_keys)
        if unknown_keys:
            raise ValueError(f"Unknown keys: {', '.join(unknown_keys)}")

        missing_keys = [
            key for key in ("message_id", "thread_id", "subject") if key not in payload
        ]
        if missing_keys:
            raise ValueError(f"Missing required keys: {', '.join(missing_keys)}")

        message_id = str(payload.get("message_id", "") or "").strip()
        thread_id = str(payload.get("thread_id", "") or "").strip()
        subject = str(payload.get("subject", "") or "").strip()
        account_email_raw = payload.get("account_email")
        account_email = str(account_email_raw or "").strip() or None
        handoff_session_id = str(payload.get("handoff_session_id", "") or "").strip() or None
        source_gmail_url = str(payload.get("source_gmail_url", "") or "").strip() or None

        if message_id == "":
            raise ValueError("message_id must be non-empty.")
        if thread_id == "":
            raise ValueError("thread_id must be non-empty.")

        return cls(
            message_id=message_id,
            thread_id=thread_id,
            subject=subject,
            account_email=account_email,
            handoff_session_id=handoff_session_id,
            source_gmail_url=source_gmail_url,
        )


class _BridgeHttpServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        bridge: LocalGmailIntakeBridge,
    ) -> None:
        self.bridge = bridge
        super().__init__(server_address, _BridgeRequestHandler)


class _BridgeRequestHandler(BaseHTTPRequestHandler):
    server_version = "LegalPDFTranslateGmailIntake/1.0"
    sys_version = ""

    def _send_json(self, status_code: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reject(self, status_code: int, code: str, message: str) -> None:
        self._send_json(
            status_code,
            {
                "status": "error",
                "code": code,
                "message": message,
            },
        )

    def _bridge(self) -> LocalGmailIntakeBridge:
        return self.server.bridge

    def _validate_path(self) -> bool:
        if self.path != "/gmail-intake":
            self._reject(404, "not_found", "Only /gmail-intake is supported.")
            return False
        return True

    def _validate_authorization(self) -> bool:
        expected = self._bridge().token.strip()
        header_value = str(self.headers.get("Authorization", "") or "").strip()
        if not header_value.startswith("Bearer "):
            self._reject(401, "invalid_token", "Bearer token is required.")
            return False
        provided = header_value[len("Bearer ") :].strip()
        if expected == "" or provided != expected:
            self._reject(401, "invalid_token", "Bearer token is invalid.")
            return False
        return True

    def do_POST(self) -> None:  # noqa: N802
        if not self._validate_path():
            return
        if not self._validate_authorization():
            return

        content_type = str(self.headers.get("Content-Type", "") or "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            self._reject(415, "invalid_content_type", "Content-Type must be application/json.")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            self._reject(400, "invalid_content_length", "Content-Length is invalid.")
            return
        if content_length <= 0:
            self._reject(400, "empty_body", "JSON body is required.")
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._reject(400, "invalid_json", "Request body must be valid JSON.")
            return

        try:
            context = InboundMailContext.from_payload(payload)
        except ValueError as exc:
            self._reject(400, "invalid_payload", str(exc))
            return

        self._bridge().emit(context)
        self._send_json(
            200,
            {
                "status": "accepted",
                "message": "Gmail intake accepted.",
            },
        )

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/gmail-intake":
            self._reject(405, "method_not_allowed", "Use POST /gmail-intake.")
            return
        self._reject(404, "not_found", "Only /gmail-intake is supported.")

    def do_PUT(self) -> None:  # noqa: N802
        self.do_GET()

    def do_DELETE(self) -> None:  # noqa: N802
        self.do_GET()

    def do_PATCH(self) -> None:  # noqa: N802
        self.do_GET()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.do_GET()

    def log_message(self, format: str, *args: object) -> None:
        return


class LocalGmailIntakeBridge:
    def __init__(
        self,
        *,
        port: int,
        token: str,
        on_context: Callable[[InboundMailContext], None],
        host: str = "127.0.0.1",
    ) -> None:
        self.host = host
        self.port = int(port)
        self.token = str(token or "").strip()
        self._on_context = on_context
        self._lock = threading.Lock()
        self._server: _BridgeHttpServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/gmail-intake"

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._server is not None and self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.host != "127.0.0.1":
            raise ValueError("LocalGmailIntakeBridge must bind to 127.0.0.1.")
        if self.port <= 0 or self.port > 65535:
            raise ValueError("Port must be between 1 and 65535.")
        if self.token == "":
            raise ValueError("Bridge token is required.")

        with self._lock:
            if self._server is not None:
                return
            server = _BridgeHttpServer((self.host, self.port), self)
            thread = threading.Thread(
                target=server.serve_forever,
                name=f"gmail-intake-{self.port}",
                daemon=True,
            )
            self._server = server
            self._thread = thread
            thread.start()

    def stop(self) -> None:
        with self._lock:
            server = self._server
            thread = self._thread
            self._server = None
            self._thread = None

        if server is None:
            return

        try:
            server.shutdown()
        finally:
            server.server_close()
            if thread is not None:
                thread.join(timeout=2.0)

    def emit(self, context: InboundMailContext) -> None:
        self._on_context(context)
