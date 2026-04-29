"""Google Photos Picker OAuth helpers for the local browser app."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .user_settings import app_data_dir_from_settings_path, load_settings_from_path

GOOGLE_PHOTOS_PICKER_SCOPE = "https://www.googleapis.com/auth/photospicker.mediaitems.readonly"
GOOGLE_OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_CLIENT_ID_ENV_NAME = "LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID"
DEFAULT_CLIENT_SECRET_ENV_NAME = "LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET"
DEFAULT_TOKEN_FILENAME = "google_photos_picker_token.json"
DEFAULT_PENDING_STATE_FILENAME = "google_photos_picker_pending_oauth_states.json"
DEFAULT_CALLBACK_DIAGNOSTIC_FILENAME = "google_photos_picker_last_callback_diagnostic.json"
OAUTH_STATE_TTL_SECONDS = 10 * 60
MIN_GOOGLE_PHOTOS_CLIENT_SECRET_LENGTH = 20
GOOGLE_PHOTOS_CALLBACK_FAILURE_CATEGORIES = {
    "state_missing",
    "state_invalid_or_expired",
    "oauth_error_param_present",
    "code_missing",
    "token_exchange_invalid_client",
    "token_exchange_invalid_grant",
    "token_exchange_redirect_uri_mismatch",
    "token_exchange_scope_or_access_denied",
    "token_exchange_http_error",
    "token_exchange_network_error",
    "token_exchange_unknown_error",
    "token_save_failed",
    "token_saved_but_status_empty",
    "token_path_mismatch",
    "connected",
    "unknown",
}
GOOGLE_PHOTOS_CALLBACK_BOOL_FIELDS = (
    "callback_received",
    "state_present",
    "state_verified",
    "oauth_error_param_present",
    "code_present",
    "token_exchange_attempted",
    "token_exchange_succeeded",
    "token_save_attempted",
    "token_save_succeeded",
    "token_path_exists_after_callback",
    "token_path_parent_exists",
    "token_path_same_for_callback_and_status",
)
GOOGLE_PHOTOS_CALLBACK_LABEL_FIELDS = (
    "safe_failure_category",
    "token_status_after_callback",
    "connect_workspace_id",
    "callback_workspace_id",
    "status_workspace_id",
)
_PLACEHOLDER_ENV_VALUES = {
    "PASTE_CLIENT_ID_HERE",
    "PASTE_CLIENT_SECRET_HERE",
    "HERE",
    "TODO",
    "CHANGEME",
    "CHANGE_ME",
    "PLACEHOLDER",
}


@dataclass(frozen=True, slots=True)
class ResolvedEnvValue:
    value: str = field(repr=False)
    source: str


class GooglePhotosOAuthTokenExchangeError(ValueError):
    """Safe OAuth token-exchange failure with a whitelisted category only."""

    def __init__(self, safe_category: str) -> None:
        self.safe_category = _safe_callback_failure_category(safe_category)
        super().__init__(f"Google Photos OAuth token exchange failed: {self.safe_category}.")


class GooglePhotosOAuthTokenSaveError(ValueError):
    """Safe token-save failure."""

    safe_category = "token_save_failed"

    def __init__(self) -> None:
        super().__init__("Google Photos OAuth token save failed: token_save_failed.")


def _read_google_photos_env_var(name: str, *, value_kind: str = "generic") -> ResolvedEnvValue:
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        return ResolvedEnvValue(value="", source="empty")
    process_value = _clean_google_photos_env_value(os.environ.get(cleaned_name, ""), value_kind=value_kind)
    if process_value:
        return ResolvedEnvValue(value=process_value, source="process_env")
    if _should_read_windows_user_env():
        windows_value = _clean_google_photos_env_value(
            _read_windows_user_environment_var(cleaned_name),
            value_kind=value_kind,
        )
        if windows_value:
            return ResolvedEnvValue(value=windows_value, source="windows_user_env")
    return ResolvedEnvValue(value="", source="empty")


def _should_read_windows_user_env() -> bool:
    return os.name == "nt"


def _read_windows_user_environment_var(name: str) -> str:
    if not _should_read_windows_user_env():
        return ""
    try:
        import winreg
    except ImportError:
        return ""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _value_type = winreg.QueryValueEx(key, str(name or "").strip())
    except OSError:
        return ""
    return str(value or "").strip()


def _clean_google_photos_env_value(value: object, *, value_kind: str = "generic") -> str:
    cleaned = str(value or "").strip()
    if not cleaned or _is_placeholder_env_value(cleaned):
        return ""
    if value_kind == "client_secret" and not _looks_like_google_photos_client_secret(cleaned):
        return ""
    return cleaned


def _is_placeholder_env_value(value: object) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned:
        return False
    upper = cleaned.upper()
    return upper in _PLACEHOLDER_ENV_VALUES or "PASTE_" in upper or upper.endswith("_HERE")


def _looks_like_google_photos_client_secret(value: object) -> bool:
    cleaned = str(value or "").strip()
    if not cleaned or _is_placeholder_env_value(cleaned):
        return False
    if cleaned.endswith(".apps.googleusercontent.com"):
        return False
    return len(cleaned) >= MIN_GOOGLE_PHOTOS_CLIENT_SECRET_LENGTH


@dataclass(frozen=True, slots=True)
class GooglePhotosOAuthConfig:
    settings_path: Path
    client_id: str = field(repr=False)
    client_id_source: str
    client_id_env_name: str
    client_secret_env_name: str
    client_secret_value: str = field(repr=False)
    client_secret_source: str
    redirect_uri: str
    token_path: Path
    pending_state_path: Path
    callback_diagnostic_path: Path
    scope: str = GOOGLE_PHOTOS_PICKER_SCOPE

    @property
    def client_secret_configured(self) -> bool:
        return bool(self.client_secret_value.strip())

    @property
    def configured(self) -> bool:
        return bool(self.client_id.strip()) and self.client_secret_configured

    def client_secret(self) -> str:
        return self.client_secret_value


def load_google_photos_oauth_config(
    *,
    settings_path: Path,
    redirect_uri: str = "",
) -> GooglePhotosOAuthConfig:
    settings = load_settings_from_path(settings_path)
    client_id_env_name = str(
        settings.get("google_photos_client_id_env_name", DEFAULT_CLIENT_ID_ENV_NAME) or DEFAULT_CLIENT_ID_ENV_NAME
    ).strip()
    client_secret_env_name = str(
        settings.get("google_photos_client_secret_env_name", DEFAULT_CLIENT_SECRET_ENV_NAME)
        or DEFAULT_CLIENT_SECRET_ENV_NAME
    ).strip()
    settings_client_id = _clean_google_photos_env_value(settings.get("google_photos_client_id", ""))
    if settings_client_id:
        client_id = settings_client_id
        client_id_source = "settings"
    elif client_id_env_name:
        resolved_client_id = _read_google_photos_env_var(client_id_env_name)
        client_id = resolved_client_id.value
        client_id_source = resolved_client_id.source
    else:
        client_id = ""
        client_id_source = "empty"
    resolved_client_secret = _read_google_photos_env_var(client_secret_env_name, value_kind="client_secret")

    raw_token_path = str(settings.get("google_photos_token_path", "") or "").strip()
    if raw_token_path:
        token_path = Path(raw_token_path).expanduser()
    else:
        token_path = app_data_dir_from_settings_path(settings_path) / DEFAULT_TOKEN_FILENAME

    app_data_dir = app_data_dir_from_settings_path(settings_path)
    return GooglePhotosOAuthConfig(
        settings_path=settings_path.expanduser().resolve(),
        client_id=client_id,
        client_id_source=client_id_source,
        client_id_env_name=client_id_env_name or DEFAULT_CLIENT_ID_ENV_NAME,
        client_secret_env_name=client_secret_env_name or DEFAULT_CLIENT_SECRET_ENV_NAME,
        client_secret_value=resolved_client_secret.value,
        client_secret_source=resolved_client_secret.source,
        redirect_uri=str(redirect_uri or "").strip(),
        token_path=token_path.expanduser().resolve(),
        pending_state_path=(app_data_dir / DEFAULT_PENDING_STATE_FILENAME).expanduser().resolve(),
        callback_diagnostic_path=(app_data_dir / DEFAULT_CALLBACK_DIAGNOSTIC_FILENAME).expanduser().resolve(),
    )


def load_google_photos_token(config: GooglePhotosOAuthConfig) -> dict[str, Any]:
    try:
        raw = config.token_path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_google_photos_token(config: GooglePhotosOAuthConfig, token_payload: Mapping[str, Any]) -> None:
    existing = load_google_photos_token(config)
    merged = dict(existing)
    for key in ("access_token", "refresh_token", "token_type", "scope", "expires_at"):
        if key in token_payload and token_payload[key] not in (None, ""):
            merged[key] = token_payload[key]
    expires_in = token_payload.get("expires_in")
    if isinstance(expires_in, (int, float)) and expires_in > 0:
        merged["expires_at"] = time.time() + float(expires_in)
    merged["scope"] = str(merged.get("scope", config.scope) or config.scope)
    config.token_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config.token_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    temp_path.replace(config.token_path)


def delete_google_photos_token(config: GooglePhotosOAuthConfig) -> None:
    try:
        config.token_path.unlink()
    except FileNotFoundError:
        return


def clear_google_photos_callback_diagnostic(config: GooglePhotosOAuthConfig) -> None:
    try:
        config.callback_diagnostic_path.unlink()
    except FileNotFoundError:
        return


def google_photos_connection_status(config: GooglePhotosOAuthConfig) -> dict[str, Any]:
    token = load_google_photos_token(config)
    has_access_token = bool(str(token.get("access_token", "") or "").strip())
    has_refresh_token = bool(str(token.get("refresh_token", "") or "").strip())
    expires_at = _coerce_float(token.get("expires_at"), default=0.0)
    access_token_current = has_access_token and expires_at > time.time() + 60
    connected = access_token_current or has_refresh_token
    token_present = has_access_token or has_refresh_token
    if not config.client_id.strip():
        reason = "client_id_missing"
    elif not config.client_secret_configured:
        reason = "client_secret_env_missing"
    elif has_access_token and not has_refresh_token and not access_token_current:
        reason = "token_expired_reconnect_required"
    elif not connected:
        reason = "not_connected"
    else:
        reason = "connected"
    return {
        "configured": config.configured,
        "connected": connected,
        "client_id_configured": bool(config.client_id.strip()),
        "client_secret_env_configured": config.client_secret_configured,
        "client_id_source": config.client_id_source if config.client_id.strip() else "empty",
        "client_secret_source": config.client_secret_source if config.client_secret_configured else "empty",
        "client_secret_env_name": config.client_secret_env_name,
        "scope": config.scope,
        "reason": reason,
        "token_store": "present" if token_present else "empty",
    }


def new_google_photos_callback_diagnostic(**updates: Any) -> dict[str, Any]:
    diagnostic: dict[str, Any] = {
        "callback_received": False,
        "state_present": False,
        "state_verified": False,
        "oauth_error_param_present": False,
        "code_present": False,
        "token_exchange_attempted": False,
        "token_exchange_succeeded": False,
        "token_save_attempted": False,
        "token_save_succeeded": False,
        "token_status_after_callback": "empty",
        "token_path_exists_after_callback": False,
        "token_path_parent_exists": False,
        "connect_workspace_id": "",
        "callback_workspace_id": "",
        "status_workspace_id": "",
        "token_path_same_for_callback_and_status": False,
        "safe_failure_category": "unknown",
    }
    diagnostic.update(updates)
    return sanitize_google_photos_callback_diagnostic(diagnostic)


def sanitize_google_photos_callback_diagnostic(payload: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key in GOOGLE_PHOTOS_CALLBACK_BOOL_FIELDS:
        sanitized[key] = bool(payload.get(key, False))
    sanitized["safe_failure_category"] = _safe_callback_failure_category(payload.get("safe_failure_category"))
    sanitized["token_status_after_callback"] = _safe_token_status_label(payload.get("token_status_after_callback"))
    for key in ("connect_workspace_id", "callback_workspace_id", "status_workspace_id"):
        sanitized[key] = safe_google_photos_workspace_label(payload.get(key, ""))
    return sanitized


def save_google_photos_callback_diagnostic(
    config: GooglePhotosOAuthConfig,
    diagnostic: Mapping[str, Any],
) -> dict[str, Any]:
    sanitized = sanitize_google_photos_callback_diagnostic(diagnostic)
    config.callback_diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config.callback_diagnostic_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(sanitized, indent=2, sort_keys=True), encoding="utf-8")
    temp_path.replace(config.callback_diagnostic_path)
    return sanitized


def load_google_photos_callback_diagnostic(config: GooglePhotosOAuthConfig) -> dict[str, Any]:
    try:
        payload = json.loads(config.callback_diagnostic_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return sanitize_google_photos_callback_diagnostic(payload)


def google_photos_callback_token_path_diagnostics(
    config: GooglePhotosOAuthConfig,
    *,
    status_config: GooglePhotosOAuthConfig | None = None,
) -> dict[str, bool]:
    comparison_config = status_config or config
    return {
        "token_path_exists_after_callback": config.token_path.exists(),
        "token_path_parent_exists": config.token_path.parent.exists(),
        "token_path_same_for_callback_and_status": config.token_path == comparison_config.token_path,
    }


def safe_google_photos_workspace_label(value: object) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        return ""
    safe = "".join(ch if ch.isalnum() or ch in "._:-" else "-" for ch in cleaned)
    return safe[:80]


def build_google_photos_authorization_url(
    config: GooglePhotosOAuthConfig,
    *,
    state: str,
) -> str:
    _require_configured(config)
    if not config.redirect_uri:
        raise ValueError("Google Photos OAuth redirect URI is not available.")
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": config.scope,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_OAUTH_AUTH_URL}?{urlencode(params)}"


def exchange_google_photos_authorization_code(
    config: GooglePhotosOAuthConfig,
    *,
    code: str,
) -> dict[str, Any]:
    payload = request_google_photos_authorization_token(config, code=code)
    try:
        save_google_photos_token(config, payload)
    except OSError as exc:
        raise GooglePhotosOAuthTokenSaveError() from exc
    return google_photos_connection_status(config)


def request_google_photos_authorization_token(
    config: GooglePhotosOAuthConfig,
    *,
    code: str,
) -> dict[str, Any]:
    _require_configured(config)
    cleaned_code = str(code or "").strip()
    if not cleaned_code:
        raise ValueError("Google Photos OAuth callback did not include a code.")
    return _oauth_token_request(
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret(),
            "code": cleaned_code,
            "grant_type": "authorization_code",
            "redirect_uri": config.redirect_uri,
        }
    )


def get_valid_google_photos_access_token(config: GooglePhotosOAuthConfig) -> str:
    _require_configured(config)
    token = load_google_photos_token(config)
    access_token = str(token.get("access_token", "") or "").strip()
    expires_at = _coerce_float(token.get("expires_at"), default=0.0)
    if access_token and expires_at > time.time() + 60:
        return access_token
    refresh_token = str(token.get("refresh_token", "") or "").strip()
    if not refresh_token:
        raise ValueError("Google Photos is not connected. Connect Google Photos before choosing a photo.")
    payload = _oauth_token_request(
        {
            "client_id": config.client_id,
            "client_secret": config.client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    )
    payload.setdefault("refresh_token", refresh_token)
    save_google_photos_token(config, payload)
    refreshed = load_google_photos_token(config)
    refreshed_access_token = str(refreshed.get("access_token", "") or "").strip()
    if not refreshed_access_token:
        raise ValueError("Google Photos token refresh did not return an access token.")
    return refreshed_access_token


def create_pending_google_photos_oauth_state(
    config: GooglePhotosOAuthConfig,
    *,
    mode: str,
    workspace_id: str,
    now: float | None = None,
    ttl_seconds: int = OAUTH_STATE_TTL_SECONDS,
) -> str:
    _require_configured(config)
    issued_at = float(time.time() if now is None else now)
    normalized_mode = str(mode or "live").strip() or "live"
    normalized_workspace_id = str(workspace_id or "workspace-1").strip() or "workspace-1"
    nonce = secrets.token_urlsafe(18)
    verifier = secrets.token_urlsafe(32)
    raw_state = _encode_oauth_state_payload(
        {
            "mode": normalized_mode,
            "workspace_id": normalized_workspace_id,
            "nonce": nonce,
            "verifier": verifier,
        }
    )
    records = _load_pending_oauth_states(config, now=issued_at, prune_expired=True)
    records.append(
        {
            "state_hash": _hash_oauth_state(raw_state),
            "nonce_hash": _hash_oauth_state(nonce),
            "mode": normalized_mode,
            "workspace_id": normalized_workspace_id,
            "created_at": issued_at,
            "expires_at": issued_at + max(60, int(ttl_seconds)),
        }
    )
    _save_pending_oauth_states(config, records)
    return raw_state


def decode_google_photos_oauth_state_hint(state: str) -> dict[str, str]:
    payload = _decode_oauth_state_payload(state)
    if not payload:
        return {}
    return {
        "mode": str(payload.get("mode", "") or "").strip(),
        "workspace_id": str(payload.get("workspace_id", "") or "").strip(),
    }


def verify_pending_google_photos_oauth_state(
    config: GooglePhotosOAuthConfig,
    *,
    state: str,
    now: float | None = None,
) -> dict[str, str]:
    cleaned = str(state or "").strip()
    if not cleaned:
        raise ValueError("Google Photos OAuth state is missing. Start the connection again from LegalPDF.")
    checked_at = float(time.time() if now is None else now)
    state_hash = _hash_oauth_state(cleaned)
    records = _load_pending_oauth_states(config, now=checked_at, prune_expired=False)
    for record in records:
        if str(record.get("state_hash", "") or "") != state_hash:
            continue
        expires_at = _coerce_float(record.get("expires_at"), default=0.0)
        if expires_at <= checked_at:
            _save_pending_oauth_states(config, [item for item in records if item is not record])
            raise ValueError("Google Photos OAuth state expired. Start the connection again from LegalPDF.")
        payload = _decode_oauth_state_payload(cleaned)
        nonce = str(payload.get("nonce", "") or "").strip() if payload else ""
        if str(record.get("nonce_hash", "") or "") != _hash_oauth_state(nonce):
            raise ValueError("Google Photos OAuth state is invalid. Start the connection again from LegalPDF.")
        return {
            "mode": str(record.get("mode", "") or "").strip() or "live",
            "workspace_id": str(record.get("workspace_id", "") or "").strip() or "workspace-1",
        }
    raise ValueError("Google Photos OAuth state is invalid or already used. Start the connection again from LegalPDF.")


def consume_pending_google_photos_oauth_state(config: GooglePhotosOAuthConfig, *, state: str) -> None:
    cleaned = str(state or "").strip()
    if not cleaned:
        return
    state_hash = _hash_oauth_state(cleaned)
    records = _load_pending_oauth_states(config, prune_expired=True)
    _save_pending_oauth_states(
        config,
        [record for record in records if str(record.get("state_hash", "") or "") != state_hash],
    )


def _require_configured(config: GooglePhotosOAuthConfig) -> None:
    if not config.client_id.strip():
        raise ValueError("Google Photos OAuth client ID is not configured.")
    if not config.client_secret_configured:
        raise ValueError(
            f"Google Photos OAuth client secret env var is not configured: {config.client_secret_env_name}."
        )


def _load_pending_oauth_states(
    config: GooglePhotosOAuthConfig,
    *,
    now: float | None = None,
    prune_expired: bool = True,
) -> list[dict[str, Any]]:
    checked_at = float(time.time() if now is None else now)
    try:
        payload = json.loads(config.pending_state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_records = payload.get("states") if isinstance(payload, dict) else payload
    if not isinstance(raw_records, list):
        return []
    records: list[dict[str, Any]] = []
    for record in raw_records:
        if not isinstance(record, dict):
            continue
        expires_at = _coerce_float(record.get("expires_at"), default=0.0)
        if prune_expired and expires_at <= checked_at:
            continue
        state_hash = str(record.get("state_hash", "") or "").strip()
        nonce_hash = str(record.get("nonce_hash", "") or "").strip()
        if state_hash and nonce_hash:
            records.append(dict(record))
    if prune_expired and len(records) != len(raw_records):
        _save_pending_oauth_states(config, records)
    return records


def _save_pending_oauth_states(config: GooglePhotosOAuthConfig, records: list[dict[str, Any]]) -> None:
    config.pending_state_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = config.pending_state_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps({"states": records}, indent=2), encoding="utf-8")
    temp_path.replace(config.pending_state_path)


def _hash_oauth_state(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _encode_oauth_state_payload(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_oauth_state_payload(state: str) -> dict[str, Any]:
    cleaned = str(state or "").strip()
    if not cleaned:
        return {}
    padded = cleaned + ("=" * (-len(cleaned) % 4))
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _oauth_token_request(form_values: Mapping[str, Any]) -> dict[str, Any]:
    body = urlencode({key: str(value) for key, value in form_values.items()}).encode("utf-8")
    request = Request(
        GOOGLE_OAUTH_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise GooglePhotosOAuthTokenExchangeError(_token_exchange_category_from_http_error(exc)) from exc
    except (URLError, OSError) as exc:
        raise GooglePhotosOAuthTokenExchangeError("token_exchange_network_error") from exc
    except json.JSONDecodeError as exc:
        raise GooglePhotosOAuthTokenExchangeError("token_exchange_unknown_error") from exc
    if not isinstance(payload, dict):
        raise GooglePhotosOAuthTokenExchangeError("token_exchange_unknown_error")
    return payload


def _token_exchange_category_from_http_error(exc: HTTPError) -> str:
    google_error = ""
    try:
        raw = exc.read()
    except OSError:
        raw = b""
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    if isinstance(payload, dict):
        google_error = str(payload.get("error", "") or "").strip()
    return _token_exchange_category_from_google_error(google_error)


def _token_exchange_category_from_google_error(error: str) -> str:
    cleaned = str(error or "").strip().lower()
    if cleaned == "invalid_client":
        return "token_exchange_invalid_client"
    if cleaned == "invalid_grant":
        return "token_exchange_invalid_grant"
    if cleaned == "redirect_uri_mismatch":
        return "token_exchange_redirect_uri_mismatch"
    if cleaned in {"access_denied", "invalid_scope", "insufficient_scope", "scope_not_granted"}:
        return "token_exchange_scope_or_access_denied"
    return "token_exchange_http_error"


def _safe_callback_failure_category(value: object) -> str:
    cleaned = str(value or "").strip()
    return cleaned if cleaned in GOOGLE_PHOTOS_CALLBACK_FAILURE_CATEGORIES else "unknown"


def _safe_token_status_label(value: object) -> str:
    cleaned = str(value or "").strip()
    if cleaned in {"connected", "not_connected", "token_expired_reconnect_required", "empty"}:
        return cleaned
    return "empty"


def google_photos_callback_token_status_label(status: Mapping[str, Any]) -> str:
    if bool(status.get("connected", False)):
        return "connected"
    reason = str(status.get("reason", "") or "").strip()
    if reason == "token_expired_reconnect_required":
        return "token_expired_reconnect_required"
    if str(status.get("token_store", "") or "").strip() == "empty":
        return "empty"
    return "not_connected"


def _coerce_float(value: object, *, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value or "").strip())
    except ValueError:
        return default
