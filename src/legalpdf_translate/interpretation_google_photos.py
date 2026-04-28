"""Interpretation-only Google Photos Picker import orchestration."""

from __future__ import annotations

from datetime import datetime
import mimetypes
from pathlib import Path
import re
from typing import Any

from .google_photos_oauth import (
    build_google_photos_authorization_url,
    create_pending_google_photos_oauth_state,
    exchange_google_photos_authorization_code,
    get_valid_google_photos_access_token,
    google_photos_connection_status,
    load_google_photos_callback_diagnostic,
    load_google_photos_oauth_config,
    safe_google_photos_workspace_label,
)
from .google_photos_picker import (
    GooglePhotosPickerClient,
    GooglePhotosPickerError,
    PickedMediaSummary,
)
from .interpretation_service import autofill_interpretation_from_photo, build_interpretation_capability_flags
from .metadata_autofill import read_photo_exif_date

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def build_google_photos_status(
    *,
    settings_path: Path,
    redirect_uri: str = "",
    mode: str = "",
    workspace_id: str = "",
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    status = google_photos_connection_status(config)
    last_callback_diagnostic = load_google_photos_callback_diagnostic(config)
    if last_callback_diagnostic and workspace_id:
        last_callback_diagnostic = dict(last_callback_diagnostic)
        last_callback_diagnostic["status_workspace_id"] = safe_google_photos_workspace_label(workspace_id)
    status.update(
        {
            "api": "google_photos_picker",
            "location_metadata_available": False,
            "location_note": "Picker metadata and Picker downloads do not expose the Google Photos place label.",
            "last_callback_diagnostic": last_callback_diagnostic,
        }
    )
    return {
        "status": "ok",
        "normalized_payload": {"google_photos": status},
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def build_google_photos_connect_response(
    *,
    settings_path: Path,
    redirect_uri: str,
    mode: str,
    workspace_id: str,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    state = create_pending_google_photos_oauth_state(config, mode=mode, workspace_id=workspace_id)
    auth_url = build_google_photos_authorization_url(config, state=state)
    status = google_photos_connection_status(config)
    status["auth_url"] = auth_url
    return {
        "status": "ok",
        "normalized_payload": {"google_photos": status},
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def complete_google_photos_oauth(
    *,
    settings_path: Path,
    redirect_uri: str,
    code: str,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    status = exchange_google_photos_authorization_code(config, code=code)
    status.update(
        {
            "api": "google_photos_picker",
            "location_metadata_available": False,
        }
    )
    return {
        "status": "ok",
        "normalized_payload": {"google_photos": status},
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def create_google_photos_picker_session(
    *,
    settings_path: Path,
    redirect_uri: str = "",
    client: GooglePhotosPickerClient | None = None,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    access_token = get_valid_google_photos_access_token(config)
    picker = client or GooglePhotosPickerClient()
    session = picker.create_session(access_token)
    return {
        "status": "ok",
        "normalized_payload": {
            "google_photos": {
                "session": session.to_payload(),
                "location_metadata_available": False,
            }
        },
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def get_google_photos_picker_session(
    *,
    settings_path: Path,
    session_id: str,
    redirect_uri: str = "",
    client: GooglePhotosPickerClient | None = None,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    access_token = get_valid_google_photos_access_token(config)
    picker = client or GooglePhotosPickerClient()
    session = picker.get_session(access_token, _require_session_id(session_id))
    return {
        "status": "ok",
        "normalized_payload": {
            "google_photos": {
                "session": session.to_payload(),
                "location_metadata_available": False,
            }
        },
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def delete_google_photos_picker_session(
    *,
    settings_path: Path,
    session_id: str,
    redirect_uri: str = "",
    client: GooglePhotosPickerClient | None = None,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    access_token = get_valid_google_photos_access_token(config)
    picker = client or GooglePhotosPickerClient()
    picker.delete_session(access_token, _require_session_id(session_id))
    return {
        "status": "ok",
        "normalized_payload": {
            "google_photos": {
                "session_deleted": True,
                "location_metadata_available": False,
            }
        },
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def list_google_photos_picker_media(
    *,
    settings_path: Path,
    session_id: str,
    redirect_uri: str = "",
    client: GooglePhotosPickerClient | None = None,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    access_token = get_valid_google_photos_access_token(config)
    picker = client or GooglePhotosPickerClient()
    media = picker.list_media_items(access_token, _require_session_id(session_id))
    return {
        "status": "ok",
        "normalized_payload": {
            "google_photos": {
                "media_items": [item.to_safe_payload() for item in media],
                "multiple_selection_warning": _multiple_selection_warning(media),
                "location_metadata_available": False,
            }
        },
        "diagnostics": {},
        "capability_flags": build_interpretation_capability_flags(settings_path=settings_path),
    }


def import_google_photos_selection(
    *,
    settings_path: Path,
    uploads_dir: Path,
    session_id: str,
    selection_key: str = "",
    redirect_uri: str = "",
    client: GooglePhotosPickerClient | None = None,
) -> dict[str, Any]:
    config = load_google_photos_oauth_config(settings_path=settings_path, redirect_uri=redirect_uri)
    access_token = get_valid_google_photos_access_token(config)
    picker = client or GooglePhotosPickerClient()
    session_id = _require_session_id(session_id)
    media = picker.list_media_items(access_token, session_id)
    selected = _select_media(media, selection_key=selection_key)
    if not _is_image_media(selected):
        raise ValueError("Selected Google Photos media item is not an image and cannot be imported for Interpretation.")
    selection_warning = _multiple_selection_warning(media)
    image_bytes = picker.download_media_bytes(access_token, selected)
    image_path = _write_selected_photo(uploads_dir=uploads_dir, selected=selected, image_bytes=image_bytes)

    response = autofill_interpretation_from_photo(
        image_path=image_path,
        settings_path=settings_path,
        use_photo_date_as_service_date=False,
    )
    response.setdefault("diagnostics", {})
    metadata_extraction = response["diagnostics"].get("metadata_extraction")
    extracted_fields = (
        metadata_extraction.get("extracted_fields", [])
        if isinstance(metadata_extraction, dict)
        else []
    )
    response["diagnostics"]["google_photos"] = {
        "selected_photo": selected.to_safe_payload(),
        "downloaded_file": str(image_path),
        "downloaded_exif_date": read_photo_exif_date(image_path) or "",
        "location_status": "from_ocr" if _has_ocr_location(extracted_fields) else "unavailable",
        "location_source": "current_metadata_autofill_ocr" if _has_ocr_location(extracted_fields) else "not_available_from_picker",
        "service_date_policy": "Picker createTime and downloaded EXIF date are provenance only; review service_date before export.",
    }
    if selection_warning:
        response["diagnostics"]["google_photos"]["multiple_selection_warning"] = selection_warning
    response["diagnostics"]["metadata_extraction_source"] = "google_photos_picker"
    response["diagnostics"]["uploaded_file"] = str(image_path)
    try:
        picker.delete_session(access_token, session_id)
        response["diagnostics"]["google_photos"]["picker_session_deleted"] = True
    except GooglePhotosPickerError:
        response["diagnostics"]["google_photos"]["picker_session_deleted"] = False
        response["diagnostics"]["google_photos"]["picker_session_cleanup"] = "failed_sanitized"
    return response


def _select_media(media: list[PickedMediaSummary], *, selection_key: str) -> PickedMediaSummary:
    if not media:
        raise ValueError("No selected Google Photos media items are available yet.")
    cleaned_key = str(selection_key or "").strip()
    if not cleaned_key:
        return media[0]
    for item in media:
        if item.selection_key == cleaned_key:
            return item
    raise ValueError("The selected Google Photos media item is no longer available.")


def _multiple_selection_warning(media: list[PickedMediaSummary]) -> str:
    if len(media) <= 1:
        return ""
    return "Google Photos returned multiple selected items; LegalPDF imported one image deterministically."


def _is_image_media(media: PickedMediaSummary) -> bool:
    return str(media.mime_type or "").strip().casefold().startswith("image/")


def _require_session_id(session_id: str) -> str:
    cleaned = str(session_id or "").strip()
    if not cleaned:
        raise ValueError("Google Photos Picker session ID is required.")
    return cleaned


def _write_selected_photo(
    *,
    uploads_dir: Path,
    selected: PickedMediaSummary,
    image_bytes: bytes,
) -> Path:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(selected.source_filename)
    suffix = Path(filename).suffix
    if not suffix:
        suffix = mimetypes.guess_extension(selected.mime_type) or ".jpg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = (uploads_dir / f"{timestamp}_google_photos_{Path(filename).stem or 'photo'}{suffix}").resolve()
    target.write_bytes(image_bytes)
    return target


def _safe_filename(value: str) -> str:
    cleaned = _SAFE_FILENAME_RE.sub("_", str(value or "").strip()).strip("._")
    return cleaned or "photo.jpg"


def _has_ocr_location(extracted_fields: object) -> bool:
    if not isinstance(extracted_fields, list):
        return False
    return any(str(item) in {"case_city", "service_city"} for item in extracted_fields)
