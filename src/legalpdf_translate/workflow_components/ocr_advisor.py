"""Deterministic OCR/image advisor for analyze and run-summary flows."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return default
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return default
    return default


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", ".")
        if text == "":
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _track_for_lang(target_lang: str) -> str:
    return "ar" if str(target_lang or "").strip().upper() == "AR" else "enfr"


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def build_ocr_image_advisor(
    *,
    rows: Sequence[Mapping[str, Any]],
    target_lang: str,
    current_ocr_mode: str,
    current_image_mode: str,
    source: str,
) -> dict[str, Any]:
    """Build deterministic recommendation packet from page-level signals."""
    track = _track_for_lang(target_lang)
    total_pages = len(rows)
    if total_pages <= 0:
        return {
            "recommended_ocr_mode": str(current_ocr_mode or "auto"),
            "recommended_image_mode": str(current_image_mode or "auto"),
            "recommendation_reasons": ["insufficient_signal_no_pages"],
            "confidence": 0.5,
            "advisor_track": track,
            "source": source,
            "signal_packet": {
                "pages": 0,
                "low_text_ratio": 0.0,
                "very_low_text_ratio": 0.0,
                "fragmented_layout_ratio": 0.0,
                "image_candidate_ratio": 0.0,
                "ocr_required_ratio": 0.0,
                "ocr_helpful_ratio": 0.0,
                "ocr_unavailable_ratio": 0.0,
            },
        }

    low_text_pages = 0
    very_low_text_pages = 0
    fragmented_layout_pages = 0
    image_candidate_pages = 0
    ocr_required_pages = 0
    ocr_helpful_pages = 0
    ocr_unavailable_pages = 0

    for row in rows:
        extracted_chars = _to_int(row.get("extracted_text_chars", row.get("chars", 0)))
        if extracted_chars < 90:
            low_text_pages += 1
        if extracted_chars < 45:
            very_low_text_pages += 1

        newline_ratio = _to_float(row.get("newline_to_char_ratio", 0.0))
        two_column_detected = _to_bool(row.get("two_column_detected", False))
        reason = str(row.get("reason", row.get("source_route_reason", "")) or "").strip().lower()
        if newline_ratio >= 0.22 or two_column_detected or "fragmented" in reason:
            fragmented_layout_pages += 1

        would_attach_image = _to_bool(row.get("would_attach_image", row.get("image_used", False)))
        if would_attach_image:
            image_candidate_pages += 1

        ocr_request_reason = str(row.get("ocr_request_reason", "") or "").strip().lower()
        if ocr_request_reason == "required":
            ocr_required_pages += 1
        if ocr_request_reason == "helpful":
            ocr_helpful_pages += 1

        ocr_failed_reason = str(row.get("ocr_failed_reason", "") or "").strip().lower()
        if "unavailable" in ocr_failed_reason:
            ocr_unavailable_pages += 1

    low_text_ratio = _safe_ratio(low_text_pages, total_pages)
    very_low_text_ratio = _safe_ratio(very_low_text_pages, total_pages)
    fragmented_layout_ratio = _safe_ratio(fragmented_layout_pages, total_pages)
    image_candidate_ratio = _safe_ratio(image_candidate_pages, total_pages)
    ocr_required_ratio = _safe_ratio(ocr_required_pages, total_pages)
    ocr_helpful_ratio = _safe_ratio(ocr_helpful_pages, total_pages)
    ocr_unavailable_ratio = _safe_ratio(ocr_unavailable_pages, total_pages)

    recommended_ocr_mode = "off"
    recommended_image_mode = "off"
    reasons: list[str] = []

    if track == "ar":
        if very_low_text_ratio >= 0.45 or ocr_required_ratio >= 0.35:
            recommended_ocr_mode = "always"
            reasons.append("ar_high_required_or_very_low_text")
        elif low_text_ratio >= 0.18 or fragmented_layout_ratio >= 0.20 or ocr_helpful_ratio >= 0.15:
            recommended_ocr_mode = "auto"
            reasons.append("ar_layout_or_text_quality_requires_ocr")
    else:
        if very_low_text_ratio >= 0.52 or ocr_required_ratio >= 0.50:
            recommended_ocr_mode = "always"
            reasons.append("enfr_high_required_or_very_low_text")
        elif low_text_ratio >= 0.24 or fragmented_layout_ratio >= 0.24 or ocr_helpful_ratio >= 0.20:
            recommended_ocr_mode = "auto"
            reasons.append("enfr_layout_or_text_quality_requires_ocr")

    if image_candidate_ratio >= 0.85 or (track == "ar" and fragmented_layout_ratio >= 0.45):
        recommended_image_mode = "always"
        reasons.append("image_heavy_or_complex_layout")
    elif image_candidate_ratio >= 0.35 or fragmented_layout_ratio >= 0.20:
        recommended_image_mode = "auto"
        reasons.append("mixed_layout_image_attach_recommended")

    if ocr_unavailable_ratio > 0:
        reasons.append("ocr_environment_unavailable_observed")

    if not reasons:
        reasons.append("current_configuration_is_stable")

    signal_strength = max(
        low_text_ratio,
        very_low_text_ratio,
        fragmented_layout_ratio,
        image_candidate_ratio,
        ocr_required_ratio,
        ocr_helpful_ratio,
    )
    confidence = 0.55 + (0.35 * signal_strength) + (0.10 * min(1.0, total_pages / 5.0))
    confidence = round(max(0.5, min(0.99, confidence)), 4)

    return {
        "recommended_ocr_mode": recommended_ocr_mode,
        "recommended_image_mode": recommended_image_mode,
        "recommendation_reasons": reasons,
        "confidence": confidence,
        "advisor_track": track,
        "source": source,
        "signal_packet": {
            "pages": int(total_pages),
            "low_text_ratio": round(low_text_ratio, 4),
            "very_low_text_ratio": round(very_low_text_ratio, 4),
            "fragmented_layout_ratio": round(fragmented_layout_ratio, 4),
            "image_candidate_ratio": round(image_candidate_ratio, 4),
            "ocr_required_ratio": round(ocr_required_ratio, 4),
            "ocr_helpful_ratio": round(ocr_helpful_ratio, 4),
            "ocr_unavailable_ratio": round(ocr_unavailable_ratio, 4),
        },
    }
