"""Runtime health helpers for launch preflight and degraded-session warnings."""

from __future__ import annotations

import os


CRITICAL_RUNTIME_IMPORTS: tuple[str, ...] = (
    "ctypes",
    "socket",
    "ssl",
    "sqlite3",
    "PySide6.QtCore",
    "openai",
    "fitz",
    "lxml.etree",
    "PIL._imaging",
)
CRITICAL_APP_IMPORTS: tuple[str, ...] = (
    "legalpdf_translate.qt_app",
    "legalpdf_translate.qt_gui.app_window",
)
DEGRADED_RUNTIME_REASON_ENV = "LEGALPDF_DEGRADED_RUNTIME_REASON"


def degraded_runtime_reason_from_env() -> str:
    return str(os.getenv(DEGRADED_RUNTIME_REASON_ENV, "") or "").strip()


def degraded_runtime_dialog_text(reason: str | None = None) -> str:
    resolved_reason = (reason or degraded_runtime_reason_from_env()).strip()
    if not resolved_reason:
        return ""
    return (
        "This app session is running in a degraded compatibility mode.\n\n"
        "OpenAI- and OCR-backed features may be unavailable in this session.\n\n"
        f"Details: {resolved_reason}"
    )
