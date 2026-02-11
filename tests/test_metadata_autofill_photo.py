from __future__ import annotations

from legalpdf_translate.metadata_autofill import extract_from_photo_ocr_text


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
