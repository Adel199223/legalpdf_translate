from __future__ import annotations

from pathlib import Path

import pytest

import legalpdf_translate.interpretation_google_photos as google_photos_service
import legalpdf_translate.interpretation_service as interpretation_service
from legalpdf_translate.google_photos_picker import PickedMediaSummary
from legalpdf_translate.metadata_autofill import MetadataSuggestion


class FakePickerClient:
    def __init__(self) -> None:
        self.deleted_sessions: list[str] = []
        self.download_called = False
        self.media_items = [
            PickedMediaSummary(
                media_item_id="raw-media-id",
                selection_key="selected-key",
                source_filename="notice.jpg",
                mime_type="image/jpeg",
                create_time="2026-04-26T10:20:30Z",
                width=100,
                height=80,
                camera_make="Canon",
                camera_model="R6",
                base_url="https://example.invalid/redacted-base-url",
            )
        ]

    def list_media_items(self, access_token: str, session_id: str) -> list[PickedMediaSummary]:
        assert access_token == "access-token"
        assert session_id == "session-1"
        return list(self.media_items)

    def download_media_bytes(self, access_token: str, media: PickedMediaSummary) -> bytes:
        assert access_token == "access-token"
        assert media.selection_key == "selected-key"
        self.download_called = True
        return b"not-a-real-photo"

    def delete_session(self, access_token: str, session_id: str) -> None:
        assert access_token == "access-token"
        self.deleted_sessions.append(session_id)


def test_import_google_photos_selection_uses_photo_date_fallback_when_ocr_date_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_access_token(config) -> str:
        return "access-token"

    def fake_extract(image_path, *, vocab_cities, config, use_exif_date_as_service_date=True):
        captured["image_path"] = image_path
        captured["use_exif_date_as_service_date"] = use_exif_date_as_service_date
        return MetadataSuggestion(
            case_entity="Ministerio Publico de Moura",
            case_city="Moura",
            case_number="69/26.8PBBBJA",
            service_date="",
            confidence={"case_city": 0.9},
        )

    monkeypatch.setattr(google_photos_service, "get_valid_google_photos_access_token", fake_access_token)
    monkeypatch.setattr(interpretation_service, "extract_interpretation_photo_metadata_from_image", fake_extract)

    client = FakePickerClient()
    response = google_photos_service.import_google_photos_selection(
        settings_path=tmp_path / "settings.json",
        uploads_dir=tmp_path / "uploads",
        session_id="session-1",
        selection_key="selected-key",
        client=client,
    )

    assert response["status"] == "ok"
    assert response["normalized_payload"]["case_city"] == "Moura"
    assert response["normalized_payload"]["service_city"] == ""
    assert response["normalized_payload"]["service_date"] == "2026-04-26"
    assert captured["use_exif_date_as_service_date"] is False
    assert Path(str(captured["image_path"])).exists()
    assert client.deleted_sessions == ["session-1"]
    google_diagnostics = response["diagnostics"]["google_photos"]
    assert google_diagnostics["selected_photo"]["photo_taken_at"] == "2026-04-26T10:20:30Z"
    assert google_diagnostics["location_status"] == "unavailable"
    assert google_diagnostics["location_message"] == "Google Photos location: unavailable from Picker API"
    assert google_diagnostics["service_city_source"] == "not_available"
    assert google_diagnostics["photo_taken_date_policy"] == "Photo taken date: fallback when OCR service date is missing"
    assert google_diagnostics["service_date_source"] == "photo_taken_fallback"
    assert google_diagnostics["photo_taken_date_available"] is True
    assert google_diagnostics["downloaded_exif_date_available"] is False
    assert "example.invalid" not in str(google_diagnostics)
    assert "raw-media-id" not in str(google_diagnostics)


def test_import_google_photos_selection_keeps_ocr_service_date_over_photo_date(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_access_token(config) -> str:
        return "access-token"

    def fake_extract(image_path, *, vocab_cities, config, use_exif_date_as_service_date=True):
        return MetadataSuggestion(
            case_entity="Ministerio Publico de Beja",
            case_city="Beja",
            case_number="69/26.8PBBBJA",
            service_date="2026-04-25",
            confidence={"case_city": 0.9, "service_date": 0.9},
        )

    monkeypatch.setattr(google_photos_service, "get_valid_google_photos_access_token", fake_access_token)
    monkeypatch.setattr(interpretation_service, "extract_interpretation_photo_metadata_from_image", fake_extract)

    response = google_photos_service.import_google_photos_selection(
        settings_path=tmp_path / "settings.json",
        uploads_dir=tmp_path / "uploads",
        session_id="session-1",
        selection_key="selected-key",
        client=FakePickerClient(),
    )

    assert response["normalized_payload"]["service_date"] == "2026-04-25"
    assert response["diagnostics"]["google_photos"]["service_date_source"] == "ocr"
    assert response["diagnostics"]["google_photos"]["photo_taken_date_available"] is True


def test_import_google_photos_selection_preserves_ocr_service_city(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_access_token(config) -> str:
        return "access-token"

    def fake_extract(image_path, *, vocab_cities, config, use_exif_date_as_service_date=True):
        return MetadataSuggestion(
            case_entity="Ministerio Publico de Beja",
            case_city="Beja",
            case_number="69/26.8PBBBJA",
            service_entity="GNR",
            service_city="Moura",
            service_date="",
            confidence={"case_city": 0.9, "service_city": 0.9},
            safe_diagnostics={
                "placeholder_values_rejected": True,
                "field_sources": {
                    "case_city": "official_header",
                    "service_city": "ocr_service_location",
                },
            },
        )

    monkeypatch.setattr(google_photos_service, "get_valid_google_photos_access_token", fake_access_token)
    monkeypatch.setattr(interpretation_service, "extract_interpretation_photo_metadata_from_image", fake_extract)

    response = google_photos_service.import_google_photos_selection(
        settings_path=tmp_path / "settings.json",
        uploads_dir=tmp_path / "uploads",
        session_id="session-1",
        selection_key="selected-key",
        client=FakePickerClient(),
    )

    assert response["normalized_payload"]["case_city"] == "Beja"
    assert response["normalized_payload"]["service_entity"] == "GNR"
    assert response["normalized_payload"]["service_city"] == "Moura"
    assert response["diagnostics"]["metadata_extraction"]["extracted_fields"] == [
        "case_entity",
        "case_city",
        "case_number",
        "service_entity",
        "service_city",
    ]
    assert response["diagnostics"]["google_photos"]["service_city_source"] == "ocr"
    assert response["diagnostics"]["google_photos"]["location_source"] == "not_available_from_picker"
    assert response["diagnostics"]["metadata_extraction"]["safe_diagnostics"] == {
        "placeholder_values_rejected": True,
        "field_sources": {
            "case_city": "official_header",
            "service_city": "ocr_service_location",
        },
    }


def test_import_google_photos_selection_rejects_video_before_download(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_access_token(config) -> str:
        return "access-token"

    monkeypatch.setattr(google_photos_service, "get_valid_google_photos_access_token", fake_access_token)
    client = FakePickerClient()
    client.media_items = [
        PickedMediaSummary(
            media_item_id="video-media-id",
            selection_key="selected-key",
            source_filename="clip.mp4",
            mime_type="video/mp4",
            create_time="2026-04-26T10:20:30Z",
            width=1920,
            height=1080,
            camera_make="",
            camera_model="",
            base_url="https://example.invalid/redacted-video-base-url",
        )
    ]

    with pytest.raises(ValueError, match="not an image"):
        google_photos_service.import_google_photos_selection(
            settings_path=tmp_path / "settings.json",
            uploads_dir=tmp_path / "uploads",
            session_id="session-1",
            selection_key="selected-key",
            client=client,
        )

    assert client.download_called is False


def test_import_google_photos_selection_records_multiple_selection_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_access_token(config) -> str:
        return "access-token"

    def fake_extract(image_path, *, vocab_cities, config, use_exif_date_as_service_date=True):
        return MetadataSuggestion(case_city="Moura", confidence={"case_city": 0.9})

    monkeypatch.setattr(google_photos_service, "get_valid_google_photos_access_token", fake_access_token)
    monkeypatch.setattr(interpretation_service, "extract_interpretation_photo_metadata_from_image", fake_extract)
    client = FakePickerClient()
    client.media_items.append(
        PickedMediaSummary(
            media_item_id="second-media-id",
            selection_key="second-key",
            source_filename="second.jpg",
            mime_type="image/jpeg",
            create_time="2026-04-26T11:20:30Z",
            width=100,
            height=80,
            camera_make="",
            camera_model="",
            base_url="https://example.invalid/redacted-second-base-url",
        )
    )

    response = google_photos_service.import_google_photos_selection(
        settings_path=tmp_path / "settings.json",
        uploads_dir=tmp_path / "uploads",
        session_id="session-1",
        selection_key="selected-key",
        client=client,
    )

    diagnostics = response["diagnostics"]["google_photos"]
    assert diagnostics["selected_photo"]["selection_key"] == "selected-key"
    assert diagnostics["multiple_selection_warning"].startswith("Google Photos returned multiple selected items")
