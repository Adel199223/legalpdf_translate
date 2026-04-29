from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import legalpdf_translate.google_photos_oauth as oauth
from legalpdf_translate.google_photos_oauth import (
    create_pending_google_photos_oauth_state,
    google_photos_connection_status,
    load_google_photos_oauth_config,
    verify_pending_google_photos_oauth_state,
    consume_pending_google_photos_oauth_state,
)
from legalpdf_translate.google_photos_picker import (
    BASE_URL_REDACTION,
    PICKER_URI_REDACTION,
    GooglePhotosPickerClient,
    media_item_selection_key,
    normalize_picked_media,
    normalize_picker_session,
    redact_google_photos_payload,
)


def _write_google_photos_settings(settings_path: Path, *, client_id: str = "test-client-id") -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps({"google_photos_client_id": client_id}), encoding="utf-8")


def _block_windows_user_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oauth, "_should_read_windows_user_env", lambda: False)
    monkeypatch.setattr(oauth, "_read_windows_user_environment_var", lambda name: "")


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_oauth_config_detects_process_env_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _block_windows_user_env(monkeypatch)
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", "process-client.apps.googleusercontent.com")
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "process-secret-value-12345")
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path, client_id="")

    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    status = google_photos_connection_status(config)

    assert status["client_id_configured"] is True
    assert status["client_id_source"] == "process_env"
    assert status["client_secret_env_configured"] is True
    assert status["client_secret_source"] == "process_env"
    assert status["configured"] is True
    safe_status = json.dumps(status)
    assert "process-client.apps.googleusercontent.com" not in safe_status
    assert "process-secret-value-12345" not in safe_status


def test_oauth_config_settings_client_id_overrides_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _block_windows_user_env(monkeypatch)
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", "env-client.apps.googleusercontent.com")
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "process-secret-value-12345")
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path, client_id="settings-client-id")

    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    status = google_photos_connection_status(config)

    assert config.client_id == "settings-client-id"
    assert status["client_id_source"] == "settings"
    assert status["client_secret_source"] == "process_env"
    safe_status = json.dumps(status)
    assert "settings-client-id" not in safe_status
    assert "env-client.apps.googleusercontent.com" not in safe_status
    assert "process-secret-value-12345" not in safe_status


def test_oauth_config_detects_windows_user_env_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", raising=False)
    monkeypatch.delenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(oauth, "_should_read_windows_user_env", lambda: True)
    windows_values = {
        "LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID": "windows-client.apps.googleusercontent.com",
        "LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET": "windows-secret-value-12345",
    }
    monkeypatch.setattr(oauth, "_read_windows_user_environment_var", lambda name: windows_values.get(name, ""))
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path, client_id="")

    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    status = google_photos_connection_status(config)

    assert status["client_id_configured"] is True
    assert status["client_id_source"] == "windows_user_env"
    assert status["client_secret_env_configured"] is True
    assert status["client_secret_source"] == "windows_user_env"
    assert config.client_secret() == "windows-secret-value-12345"
    safe_status = json.dumps(status)
    assert "windows-client.apps.googleusercontent.com" not in safe_status
    assert "windows-secret-value-12345" not in safe_status


def test_oauth_config_ignores_too_short_process_secret_and_falls_back_to_windows_user_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", "process-client.apps.googleusercontent.com")
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "x")
    monkeypatch.setattr(oauth, "_should_read_windows_user_env", lambda: True)
    windows_values = {
        "LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID": "windows-client.apps.googleusercontent.com",
        "LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET": "windows-secret-value-12345",
    }
    monkeypatch.setattr(oauth, "_read_windows_user_environment_var", lambda name: windows_values.get(name, ""))
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path, client_id="")

    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    status = google_photos_connection_status(config)

    assert status["client_id_source"] == "process_env"
    assert status["client_secret_env_configured"] is True
    assert status["client_secret_source"] == "windows_user_env"
    assert config.client_secret() == "windows-secret-value-12345"
    serialized = json.dumps(status)
    assert "x" not in serialized
    assert "windows-secret-value-12345" not in serialized


def test_oauth_config_rejects_too_short_client_secret_in_all_env_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", "process-client.apps.googleusercontent.com")
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "x")
    monkeypatch.setattr(oauth, "_should_read_windows_user_env", lambda: True)
    windows_values = {
        "LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID": "windows-client.apps.googleusercontent.com",
        "LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET": "y",
    }
    monkeypatch.setattr(oauth, "_read_windows_user_environment_var", lambda name: windows_values.get(name, ""))
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path, client_id="")

    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    status = google_photos_connection_status(config)

    assert status["configured"] is False
    assert status["client_id_configured"] is True
    assert status["client_secret_env_configured"] is False
    assert status["client_secret_source"] == "empty"
    assert status["reason"] == "client_secret_env_missing"
    assert config.client_secret() == ""


def test_oauth_config_empty_and_placeholder_values_are_not_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", "PASTE_CLIENT_ID_HERE")
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "PASTE_CLIENT_SECRET_HERE")
    monkeypatch.setattr(oauth, "_should_read_windows_user_env", lambda: True)
    monkeypatch.setattr(oauth, "_read_windows_user_environment_var", lambda name: "")
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path, client_id="PASTE_CLIENT_ID_HERE")

    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    status = google_photos_connection_status(config)

    assert status["configured"] is False
    assert status["client_id_configured"] is False
    assert status["client_id_source"] == "empty"
    assert status["client_secret_env_configured"] is False
    assert status["client_secret_source"] == "empty"
    assert status["reason"] == "client_id_missing"


def test_oauth_config_non_windows_path_does_not_read_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID", raising=False)
    monkeypatch.setattr(oauth, "_should_read_windows_user_env", lambda: False)

    def fail_if_called(name: str) -> str:
        raise AssertionError("Windows registry fallback should not be read")

    monkeypatch.setattr(oauth, "_read_windows_user_environment_var", fail_if_called)

    resolved = oauth._read_google_photos_env_var("LEGALPDF_GOOGLE_PHOTOS_CLIENT_ID")

    assert resolved.value == ""
    assert resolved.source == "empty"


def test_normalize_picker_session_marks_media_items_ready() -> None:
    session = normalize_picker_session(
        {
            "id": "session-123",
            "pickerUri": "https://picker.example.invalid/session-123",
            "mediaItemsSet": True,
            "expireTime": "2026-04-27T12:00:00Z",
            "pollingConfig": {
                "pollInterval": "3s",
                "timeoutIn": "120s",
            },
        }
    )

    assert session.session_id == "session-123"
    assert session.picker_uri.endswith("session-123")
    assert session.is_ready is True
    assert session.to_payload()["media_items_set"] is True
    assert session.to_payload()["poll_interval_ms"] == 3000
    assert session.to_payload()["timeout_ms"] == 120000


def test_normalize_picked_media_exposes_safe_metadata_without_base_url() -> None:
    media = normalize_picked_media(
        {
            "id": "media-secret-id",
            "createTime": "2026-04-26T10:20:30Z",
            "mediaFile": {
                "baseUrl": "https://example.invalid/redacted-base-url",
                "mimeType": "image/jpeg",
                "filename": "IMG_0001.JPG",
                "mediaFileMetadata": {
                    "width": "4032",
                    "height": "3024",
                    "cameraMake": "Canon",
                    "cameraModel": "R6",
                },
            },
        }
    )

    payload = media.to_safe_payload()
    assert media.selection_key == media_item_selection_key("media-secret-id")
    assert payload["source_filename"] == "IMG_0001.JPG"
    assert payload["photo_taken_at"] == "2026-04-26T10:20:30Z"
    assert payload["dimensions"] == {"width": 4032, "height": 3024}
    assert payload["camera"] == {"make": "Canon", "model": "R6"}
    assert payload["location_status"] == "unavailable"
    assert payload["location_message"] == "Google Photos location: unavailable from Picker API"
    assert "baseUrl" not in payload
    assert "media-secret-id" not in str(payload)


def test_normalize_picked_media_reads_nested_picker_create_time() -> None:
    media = normalize_picked_media(
        {
            "id": "media-secret-id",
            "mediaFile": {
                "mimeType": "image/jpeg",
                "filename": "IMG_0002.JPG",
                "mediaFileMetadata": {
                    "createTime": "2026-04-25T13:46:37Z",
                    "width": "4032",
                    "height": "3024",
                },
            },
        }
    )

    payload = media.to_safe_payload()
    assert media.create_time == "2026-04-25T13:46:37Z"
    assert payload["photo_taken_at"] == "2026-04-25T13:46:37Z"
    assert payload["location_status"] == "unavailable"
    assert "media-secret-id" not in str(payload)


def test_create_session_sends_single_item_picking_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.headers.get("Authorization")
        return _FakeResponse(
            {
                "id": "session-123",
                "pickerUri": "https://picker.example.invalid/session-123",
                "mediaItemsSet": False,
            }
        )

    monkeypatch.setattr("legalpdf_translate.google_photos_picker.urlopen", fake_urlopen)

    session = GooglePhotosPickerClient().create_session("access-token")

    assert session.session_id == "session-123"
    assert captured["body"] == {"pickingConfig": {"maxItemCount": "1"}}
    assert captured["authorization"] == "Bearer access-token"


def test_redact_google_photos_payload_removes_tokens_and_base_urls() -> None:
    redacted = redact_google_photos_payload(
        {
            "access_token": "REDACT_ME_ACCESS_TOKEN",
            "Refresh_Token": "REDACT_ME_REFRESH_TOKEN",
            "id_token": "REDACT_ME_ID_TOKEN",
            "Authorization": "REDACT_ME_AUTHORIZATION",
            "client_secret": "REDACT_ME_CLIENT_SECRET",
            "pickerUri": "https://example.invalid/redacted-picker-uri",
            "mediaFile": {
                "baseUrl": "https://example.invalid/redacted-base-url",
                "base_url": "https://example.invalid/redacted-base-url-2",
            },
        }
    )

    assert redacted["access_token"] == "[redacted]"
    assert redacted["Refresh_Token"] == "[redacted]"
    assert redacted["id_token"] == "[redacted]"
    assert redacted["Authorization"] == "[redacted]"
    assert redacted["client_secret"] == "[redacted]"
    assert redacted["pickerUri"] == PICKER_URI_REDACTION
    assert redacted["mediaFile"]["baseUrl"] == BASE_URL_REDACTION
    assert redacted["mediaFile"]["base_url"] == BASE_URL_REDACTION


def test_pending_oauth_state_verifies_and_replay_is_rejected(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path)
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")

    state = create_pending_google_photos_oauth_state(
        config,
        mode="shadow",
        workspace_id="google-photos-review",
        now=1000,
        ttl_seconds=300,
    )
    stored = json.loads(config.pending_state_path.read_text(encoding="utf-8"))

    assert state not in str(stored)
    assert "access_token" not in str(stored)
    assert "refresh_token" not in str(stored)
    assert set(stored["states"][0]) == {"state_hash", "nonce_hash", "mode", "workspace_id", "created_at", "expires_at"}

    verified = verify_pending_google_photos_oauth_state(config, state=state, now=1010)
    assert verified == {"mode": "shadow", "workspace_id": "google-photos-review"}

    consume_pending_google_photos_oauth_state(config, state=state)
    with pytest.raises(ValueError, match="invalid or already used"):
        verify_pending_google_photos_oauth_state(config, state=state, now=1020)


def test_pending_oauth_state_rejects_missing_invalid_and_expired(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path)
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")

    with pytest.raises(ValueError, match="missing"):
        verify_pending_google_photos_oauth_state(config, state="", now=1000)
    with pytest.raises(ValueError, match="invalid"):
        verify_pending_google_photos_oauth_state(config, state="not-a-real-state", now=1000)

    state = create_pending_google_photos_oauth_state(
        config,
        mode="shadow",
        workspace_id="workspace",
        now=1000,
        ttl_seconds=60,
    )
    with pytest.raises(ValueError, match="expired"):
        verify_pending_google_photos_oauth_state(config, state=state, now=2000)


def test_expired_access_token_without_refresh_requires_reconnect(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LEGALPDF_GOOGLE_PHOTOS_CLIENT_SECRET", "configured-secret-value-12345")
    settings_path = tmp_path / "settings.json"
    _write_google_photos_settings(settings_path)
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri="http://test/callback")
    config.token_path.parent.mkdir(parents=True, exist_ok=True)
    config.token_path.write_text(
        json.dumps({"access_token": "expired-access-token", "expires_at": 1}),
        encoding="utf-8",
    )

    status = google_photos_connection_status(config)

    assert status["connected"] is False
    assert status["reason"] == "token_expired_reconnect_required"


def test_oauth_http_error_maps_to_safe_exchange_category(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(*args, **kwargs):
        raise HTTPError(
            url="https://oauth2.googleapis.com/token",
            code=400,
            msg="Bad Request",
            hdrs={},
            fp=BytesIO(b'{"error":"invalid_grant","error_description":"raw google details"}'),
        )

    monkeypatch.setattr(oauth, "urlopen", fake_urlopen)

    with pytest.raises(oauth.GooglePhotosOAuthTokenExchangeError) as exc_info:
        oauth._oauth_token_request({"client_id": "secret-client-id", "client_secret": "secret-value"})

    assert exc_info.value.safe_category == "token_exchange_invalid_grant"
    assert "raw google details" not in str(exc_info.value)
    assert "secret-client-id" not in str(exc_info.value)
