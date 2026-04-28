from __future__ import annotations

from PIL import Image

from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    OcrMode,
    extract_from_photo_ocr_text,
    extract_photo_metadata_from_image,
    extract_interpretation_photo_metadata_from_ocr_text,
)


def test_extract_photo_metadata_from_screenshot_like_ocr_text() -> None:
    ocr_text = """
    Monday, February 2, 2026 • 4:20 PM
    Rua da Liberdade, Beja, Portugal
    69/26.8PBBBJA
    """
    suggestion = extract_from_photo_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )
    assert suggestion.service_city == "Beja"
    assert suggestion.service_date == "2026-02-02"
    assert suggestion.case_number == "69/26.8PBBBJA"


def test_extract_photo_city_prefers_vocab_match() -> None:
    ocr_text = """
    Monday, February 10, 2026 • 11:15 AM
    Meeting notes near Tribunal, Moura district office
    """
    suggestion = extract_from_photo_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Cuba"],
        ai_enabled=False,
    )
    assert suggestion.service_city == "Moura"
    assert suggestion.service_date == "2026-02-10"


def test_extract_interpretation_photo_metadata_defaults_case_fields_from_service_city() -> None:
    ocr_text = """
    Monday, February 2, 2026 • 4:20 PM
    Rua da Liberdade, Beja, Portugal
    69/26.8PBBBJA
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "69/26.8PBBBJA"
    assert suggestion.service_city is None
    assert suggestion.service_date == "2026-02-02"


def test_extract_photo_metadata_can_keep_exif_date_as_provenance_only(tmp_path) -> None:
    image_path = tmp_path / "photo.jpg"
    image = Image.new("RGB", (10, 10), color="white")
    exif = Image.Exif()
    exif[36867] = "2026:02:03 12:00:00"
    image.save(image_path, exif=exif)

    suggestion = extract_photo_metadata_from_image(
        image_path,
        vocab_cities=["Beja", "Moura"],
        config=MetadataAutofillConfig(ocr_mode=OcrMode.OFF),
        use_exif_date_as_service_date=False,
    )

    assert suggestion.service_date is None
    assert suggestion.confidence == {"service_city": 0.0, "service_date": 0.0, "case_number": 0.0, "photo_taken_date": 0.99}
