"""Secure API-key storage helpers backed by keyring."""

from __future__ import annotations

from typing import Protocol

SERVICE = "LegalPDFTranslate"
USER_OPENAI = "openai_api_key"
USER_OCR = "ocr_api_key"
_UNAVAILABLE_MESSAGE = "Secure credential storage is unavailable on this system."


class KeyringBackend(Protocol):
    def get_password(self, service_name: str, username: str) -> str | None:
        ...

    def set_password(self, service_name: str, username: str, password: str) -> None:
        ...

    def delete_password(self, service_name: str, username: str) -> None:
        ...


def _load_default_backend() -> KeyringBackend:
    try:
        import keyring  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_UNAVAILABLE_MESSAGE) from exc
    return keyring


def _resolve_backend(backend: KeyringBackend | None) -> KeyringBackend:
    return backend if backend is not None else _load_default_backend()


def _normalize_key(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _get_key(user: str, *, backend: KeyringBackend | None = None) -> str | None:
    keyring_backend = _resolve_backend(backend)
    try:
        value = keyring_backend.get_password(SERVICE, user)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_UNAVAILABLE_MESSAGE) from exc
    return _normalize_key(value)


def _set_key(user: str, key: str, *, backend: KeyringBackend | None = None) -> None:
    cleaned = _normalize_key(key)
    if cleaned is None:
        raise ValueError("API key cannot be empty.")
    keyring_backend = _resolve_backend(backend)
    try:
        keyring_backend.set_password(SERVICE, user, cleaned)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(_UNAVAILABLE_MESSAGE) from exc


def _delete_key(user: str, *, backend: KeyringBackend | None = None) -> None:
    keyring_backend = _resolve_backend(backend)
    try:
        keyring_backend.delete_password(SERVICE, user)
    except Exception as exc:  # noqa: BLE001
        exc_name = type(exc).__name__.lower()
        exc_text = str(exc).lower()
        if "passworddeleteerror" in exc_name or "not found" in exc_text or "no such password" in exc_text:
            return
        raise RuntimeError(_UNAVAILABLE_MESSAGE) from exc


def get_openai_key(*, backend: KeyringBackend | None = None) -> str | None:
    return _get_key(USER_OPENAI, backend=backend)


def set_openai_key(key: str, *, backend: KeyringBackend | None = None) -> None:
    _set_key(USER_OPENAI, key, backend=backend)


def delete_openai_key(*, backend: KeyringBackend | None = None) -> None:
    _delete_key(USER_OPENAI, backend=backend)


def get_ocr_key(*, backend: KeyringBackend | None = None) -> str | None:
    return _get_key(USER_OCR, backend=backend)


def set_ocr_key(key: str, *, backend: KeyringBackend | None = None) -> None:
    _set_key(USER_OCR, key, backend=backend)


def delete_ocr_key(*, backend: KeyringBackend | None = None) -> None:
    _delete_key(USER_OCR, backend=backend)
