"""Google Photos Picker API client and safe metadata normalization."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PICKER_API_BASE_URL = "https://photospicker.googleapis.com/v1"
BASE_URL_REDACTION = "[redacted-google-photos-base-url]"
PICKER_URI_REDACTION = "[redacted-google-photos-picker-uri]"


class GooglePhotosPickerError(RuntimeError):
    """Raised when the Picker API returns an unusable response."""


@dataclass(frozen=True, slots=True)
class GooglePhotosPickerSession:
    session_id: str
    picker_uri: str
    expire_time: str
    media_items_set: bool
    raw_status: str
    poll_interval: str = ""
    timeout_in: str = ""

    @property
    def is_ready(self) -> bool:
        return self.media_items_set

    def to_payload(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "picker_uri": self.picker_uri,
            "expire_time": self.expire_time,
            "media_items_set": self.media_items_set,
            "is_ready": self.is_ready,
            "status": self.raw_status,
            "poll_interval": self.poll_interval,
            "timeout_in": self.timeout_in,
            "poll_interval_ms": _duration_to_milliseconds(self.poll_interval),
            "timeout_ms": _duration_to_milliseconds(self.timeout_in),
        }


@dataclass(frozen=True, slots=True)
class PickedMediaSummary:
    media_item_id: str
    selection_key: str
    source_filename: str
    mime_type: str
    create_time: str
    width: int | None
    height: int | None
    camera_make: str
    camera_model: str
    base_url: str

    def to_safe_payload(self) -> dict[str, Any]:
        dimensions: dict[str, int] = {}
        if self.width is not None:
            dimensions["width"] = self.width
        if self.height is not None:
            dimensions["height"] = self.height
        return {
            "selection_key": self.selection_key,
            "source_filename": self.source_filename,
            "mime_type": self.mime_type,
            "create_time": self.create_time,
            "photo_taken_at": self.create_time,
            "dimensions": dimensions,
            "camera": {
                "make": self.camera_make,
                "model": self.camera_model,
            },
            "location_status": "unavailable",
            "location_source": "not_available_from_picker",
        }


class GooglePhotosPickerClient:
    def __init__(self, *, base_url: str = PICKER_API_BASE_URL, timeout_seconds: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = float(timeout_seconds)

    def create_session(self, access_token: str) -> GooglePhotosPickerSession:
        payload = self._request_json(
            "POST",
            "/sessions",
            access_token=access_token,
            json_body={"pickingConfig": {"maxItemCount": "1"}},
        )
        return normalize_picker_session(payload)

    def get_session(self, access_token: str, session_id: str) -> GooglePhotosPickerSession:
        payload = self._request_json("GET", f"/sessions/{_path_component(session_id)}", access_token=access_token)
        return normalize_picker_session(payload)

    def delete_session(self, access_token: str, session_id: str) -> None:
        self._request_json("DELETE", f"/sessions/{_path_component(session_id)}", access_token=access_token)

    def list_media_items(self, access_token: str, session_id: str) -> list[PickedMediaSummary]:
        output: list[PickedMediaSummary] = []
        page_token = ""
        while True:
            params = {
                "sessionId": session_id,
                "pageSize": "50",
            }
            if page_token:
                params["pageToken"] = page_token
            payload = self._request_json(
                "GET",
                f"/mediaItems?{urlencode(params)}",
                access_token=access_token,
            )
            raw_items = payload.get("mediaItems") or payload.get("pickedMediaItems") or []
            if isinstance(raw_items, list):
                for raw_item in raw_items:
                    if isinstance(raw_item, Mapping):
                        output.append(normalize_picked_media(raw_item))
            page_token = str(payload.get("nextPageToken", "") or "").strip()
            if not page_token:
                break
        return output

    def download_media_bytes(self, access_token: str, media: PickedMediaSummary) -> bytes:
        if not media.base_url:
            raise GooglePhotosPickerError("Selected Google Photos item does not include a downloadable base URL.")
        request = Request(
            _download_url(media.base_url),
            headers={"Authorization": f"Bearer {access_token}"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            raise GooglePhotosPickerError(f"Google Photos media download failed with HTTP {exc.code}.") from exc
        except (URLError, OSError) as exc:
            raise GooglePhotosPickerError("Google Photos media download failed.") from exc

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        access_token: str,
        json_body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        body: bytes | None = None
        headers = {"Authorization": f"Bearer {access_token}"}
        if json_body is not None:
            body = json.dumps(dict(json_body)).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            raise GooglePhotosPickerError(f"Google Photos Picker API request failed with HTTP {exc.code}.") from exc
        except (URLError, OSError) as exc:
            raise GooglePhotosPickerError("Google Photos Picker API request failed.") from exc
        if not raw.strip():
            return {}
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GooglePhotosPickerError("Google Photos Picker API returned invalid JSON.") from exc
        if not isinstance(payload, dict):
            raise GooglePhotosPickerError("Google Photos Picker API returned a non-object response.")
        return payload


def normalize_picker_session(payload: Mapping[str, Any]) -> GooglePhotosPickerSession:
    polling_config = payload.get("pollingConfig") if isinstance(payload.get("pollingConfig"), Mapping) else {}
    media_items_set = bool(payload.get("mediaItemsSet") or payload.get("media_items_set") or payload.get("isReady"))
    raw_status = str(payload.get("state") or payload.get("status") or "").strip()
    if not media_items_set and raw_status.upper() in {"MEDIA_ITEMS_SET", "PICKED", "READY", "SUCCEEDED"}:
        media_items_set = True
    expire_time = str(payload.get("expireTime") or polling_config.get("timeoutIn") or "").strip()
    return GooglePhotosPickerSession(
        session_id=str(payload.get("id") or payload.get("sessionId") or "").strip(),
        picker_uri=str(payload.get("pickerUri") or payload.get("pickerURI") or "").strip(),
        expire_time=expire_time,
        media_items_set=media_items_set,
        raw_status=raw_status,
        poll_interval=str(polling_config.get("pollInterval") or "").strip(),
        timeout_in=str(polling_config.get("timeoutIn") or "").strip(),
    )


def normalize_picked_media(payload: Mapping[str, Any]) -> PickedMediaSummary:
    media_file = payload.get("mediaFile") if isinstance(payload.get("mediaFile"), Mapping) else {}
    metadata = media_file.get("mediaFileMetadata") if isinstance(media_file.get("mediaFileMetadata"), Mapping) else {}
    if not metadata and isinstance(payload.get("mediaFileMetadata"), Mapping):
        metadata = payload.get("mediaFileMetadata")  # type: ignore[assignment]
    photo_metadata = metadata.get("photoMetadata") if isinstance(metadata.get("photoMetadata"), Mapping) else {}
    if not photo_metadata and isinstance(payload.get("photoMetadata"), Mapping):
        photo_metadata = payload.get("photoMetadata")  # type: ignore[assignment]

    media_item_id = str(payload.get("id") or payload.get("mediaItemId") or "").strip()
    return PickedMediaSummary(
        media_item_id=media_item_id,
        selection_key=media_item_selection_key(media_item_id),
        source_filename=str(media_file.get("filename") or payload.get("filename") or "").strip(),
        mime_type=str(media_file.get("mimeType") or payload.get("mimeType") or "").strip(),
        create_time=str(payload.get("createTime") or media_file.get("createTime") or "").strip(),
        width=_coerce_optional_int(metadata.get("width") or media_file.get("width") or payload.get("width")),
        height=_coerce_optional_int(metadata.get("height") or media_file.get("height") or payload.get("height")),
        camera_make=str(
            metadata.get("cameraMake") or photo_metadata.get("cameraMake") or photo_metadata.get("make") or ""
        ).strip(),
        camera_model=str(
            metadata.get("cameraModel") or photo_metadata.get("cameraModel") or photo_metadata.get("model") or ""
        ).strip(),
        base_url=str(media_file.get("baseUrl") or payload.get("baseUrl") or "").strip(),
    )


def media_item_selection_key(media_item_id: str) -> str:
    cleaned = str(media_item_id or "").strip()
    if not cleaned:
        return ""
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:24]


def redact_google_photos_payload(value: Any) -> Any:
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            key_folded = key_text.casefold()
            if key_folded in {"baseurl", "base_url"}:
                output[key_text] = BASE_URL_REDACTION
            elif key_folded in {"pickeruri", "picker_uri"}:
                output[key_text] = PICKER_URI_REDACTION
            elif key_folded in {
                "access_token",
                "refresh_token",
                "id_token",
                "authorization",
                "client_secret",
            }:
                output[key_text] = "[redacted]"
            else:
                output[key_text] = redact_google_photos_payload(item)
        return output
    if isinstance(value, list):
        return [redact_google_photos_payload(item) for item in value]
    return value


def _download_url(base_url: str) -> str:
    cleaned = str(base_url or "").strip()
    if cleaned.endswith("=d"):
        return cleaned
    return f"{cleaned}=d"


def _path_component(value: str) -> str:
    return str(value or "").strip().replace("/", "")


def _coerce_optional_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _duration_to_milliseconds(value: str) -> int | None:
    cleaned = str(value or "").strip().lower()
    if not cleaned:
        return None
    multiplier = 1000.0
    number_text = cleaned
    if cleaned.endswith("ms"):
        multiplier = 1.0
        number_text = cleaned[:-2]
    elif cleaned.endswith("s"):
        multiplier = 1000.0
        number_text = cleaned[:-1]
    try:
        parsed = float(number_text)
    except ValueError:
        return None
    if parsed < 0:
        return None
    return int(parsed * multiplier)
