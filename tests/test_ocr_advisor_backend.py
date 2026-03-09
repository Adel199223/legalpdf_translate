from __future__ import annotations

from legalpdf_translate.workflow_components.ocr_advisor import build_ocr_image_advisor


def test_ocr_advisor_is_deterministic_for_same_rows() -> None:
    rows = [
        {
            "extracted_text_chars": 28,
            "newline_to_char_ratio": 0.31,
            "two_column_detected": True,
            "would_attach_image": True,
            "ocr_request_reason": "required",
            "ocr_failed_reason": "required_unavailable",
        },
        {
            "extracted_text_chars": 44,
            "newline_to_char_ratio": 0.27,
            "two_column_detected": False,
            "would_attach_image": True,
            "ocr_request_reason": "helpful",
            "ocr_failed_reason": "",
        },
    ]

    first = build_ocr_image_advisor(
        rows=rows,
        target_lang="EN",
        current_ocr_mode="auto",
        current_image_mode="auto",
        source="unit_test",
    )
    second = build_ocr_image_advisor(
        rows=rows,
        target_lang="EN",
        current_ocr_mode="auto",
        current_image_mode="auto",
        source="unit_test",
    )

    assert first == second
    assert first["advisor_track"] == "enfr"
    assert first["recommended_ocr_mode"] in {"auto", "always"}
    assert "ocr_environment_unavailable_observed" in first["recommendation_reasons"]


def test_ocr_advisor_ar_track_can_recommend_always() -> None:
    rows = [
        {
            "extracted_text_chars": 12,
            "newline_to_char_ratio": 0.12,
            "two_column_detected": False,
            "would_attach_image": True,
            "ocr_request_reason": "required",
        },
        {
            "extracted_text_chars": 20,
            "newline_to_char_ratio": 0.08,
            "two_column_detected": False,
            "would_attach_image": True,
            "ocr_request_reason": "required",
        },
    ]

    payload = build_ocr_image_advisor(
        rows=rows,
        target_lang="AR",
        current_ocr_mode="off",
        current_image_mode="off",
        source="unit_test",
    )

    assert payload["advisor_track"] == "ar"
    assert payload["recommended_ocr_mode"] == "always"
    assert payload["recommended_image_mode"] in {"auto", "always"}


def test_ocr_advisor_empty_rows_returns_safe_packet() -> None:
    payload = build_ocr_image_advisor(
        rows=[],
        target_lang="FR",
        current_ocr_mode="auto",
        current_image_mode="off",
        source="unit_test",
    )

    assert payload["recommended_ocr_mode"] == "auto"
    assert payload["recommended_image_mode"] == "off"
    assert payload["advisor_track"] == "enfr"
    assert payload["recommendation_reasons"] == ["insufficient_signal_no_pages"]
