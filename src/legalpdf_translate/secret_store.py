"""API key retrieval helpers with optional Windows Credential Manager support."""

from __future__ import annotations

import os


def _read_from_env(env_name: str) -> str | None:
    value = os.getenv(env_name, "").strip()
    return value if value else None


def _read_from_credman(target: str) -> str | None:
    try:
        import keyring  # type: ignore
    except Exception:
        return None
    try:
        # service=target, username fixed to avoid leaking key intent via user IDs
        value = keyring.get_password(target, "api_key")
    except Exception:
        return None
    if not value:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def get_api_key(
    source: str,
    env_name: str,
    credman_target: str,
    inline_value: str | None = None,
) -> str | None:
    source_clean = (source or "env").strip().lower()
    if source_clean == "inline":
        if inline_value is None:
            return None
        cleaned = inline_value.strip()
        return cleaned if cleaned else None
    if source_clean == "credman":
        return _read_from_credman(credman_target)
    return _read_from_env(env_name)


def set_api_key_credman(target: str, key_value: str) -> bool:
    try:
        import keyring  # type: ignore
    except Exception:
        return False
    cleaned = key_value.strip()
    if cleaned == "":
        return False
    try:
        keyring.set_password(target, "api_key", cleaned)
    except Exception:
        return False
    return True
