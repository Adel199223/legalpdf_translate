"""Deterministic quality-risk scoring and review queue construction."""

from __future__ import annotations

from statistics import median
from typing import Any, Mapping, Sequence


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return default
        try:
            return int(cleaned)
        except ValueError:
            try:
                return int(float(cleaned))
            except ValueError:
                return default
    return default


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if cleaned == "":
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        return lowered in {"1", "true", "yes", "y", "on"}
    return False


def _to_text(value: object) -> str:
    return str(value or "").strip()


def _recommended_action(*, status: str, reasons: list[str]) -> str:
    reason_set = set(reasons)
    if status == "failed":
        return "rerun_page"
    if "ocr_required_not_used" in reason_set:
        return "rerun_with_ocr"
    if "rate_limit_hit" in reason_set or "transport_retries" in reason_set or "api_exception" in reason_set:
        return "check_api_reliability"
    if "validator_failed" in reason_set or "parser_failed" in reason_set or "outside_text_detected" in reason_set:
        return "manual_review"
    return "spot_check"


def build_quality_risk_summary(
    page_rows: Sequence[tuple[int, Mapping[str, Any]]],
) -> dict[str, Any]:
    """Return overall and per-page risk signals for run summary payloads."""
    if not page_rows:
        return {
            "quality_risk_score": 0.0,
            "review_queue_count": 0,
            "review_queue": [],
        }

    reasoning_values = [_to_int(page.get("reasoning_tokens", 0)) for _, page in page_rows]
    wall_values = [_to_float(page.get("wall_seconds", 0.0)) for _, page in page_rows]
    median_reasoning = median(reasoning_values) if reasoning_values else 0.0
    median_wall = median(wall_values) if wall_values else 0.0

    per_page_scores: list[float] = []
    review_queue: list[dict[str, Any]] = []

    for page_number, page in page_rows:
        status = _to_text(page.get("status", "")).lower()
        retry_reason = _to_text(page.get("retry_reason", "")).lower()
        transport_retries = max(0, _to_int(page.get("transport_retries_count", 0)))
        reasoning_tokens = max(0, _to_int(page.get("reasoning_tokens", 0)))
        wall_seconds = max(0.0, _to_float(page.get("wall_seconds", 0.0)))

        score = 0.0
        reasons: list[str] = []

        if status == "failed":
            score += 1.0
            reasons.append("page_failed")
        if _to_bool(page.get("retry_used", False)):
            score += 0.22
            reasons.append("retry_used")
        if _to_bool(page.get("validator_failed", False)):
            score += 0.34
            reasons.append("validator_failed")
        if _to_bool(page.get("parser_failed", False)):
            score += 0.32
            reasons.append("parser_failed")
        if _to_bool(page.get("compliance_defect_outside_text", False)):
            score += 0.24
            reasons.append("outside_text_detected")

        if transport_retries > 0:
            score += min(0.24, transport_retries * 0.06)
            reasons.append("transport_retries")
        if _to_bool(page.get("rate_limit_hit", False)):
            score += 0.16
            reasons.append("rate_limit_hit")

        source_route = _to_text(page.get("source_route", "")).lower()
        if source_route == "ocr":
            score += 0.10
            reasons.append("ocr_route_used")

        ocr_required = _to_text(page.get("ocr_request_reason", "")).lower() == "required"
        ocr_used = _to_bool(page.get("ocr_used", False)) or source_route == "ocr"
        if ocr_required and not ocr_used:
            score += 0.45
            reasons.append("ocr_required_not_used")

        if _to_bool(page.get("image_used", False)):
            score += 0.05
            reasons.append("image_attached")

        if reasoning_tokens > max(1200, int(float(median_reasoning) * 1.75)):
            score += 0.12
            reasons.append("high_reasoning_tokens")
        if wall_seconds > max(8.0, float(median_wall) * 1.8):
            score += 0.10
            reasons.append("slow_page")

        if retry_reason and retry_reason != "other":
            score += 0.10
            reasons.append(f"retry_reason:{retry_reason}")

        exception_class = _to_text(page.get("exception_class", ""))
        if exception_class:
            score += 0.24
            reasons.append("api_exception")

        score = min(1.0, round(score, 4))
        per_page_scores.append(score)

        include_in_queue = (
            score >= 0.35
            or status == "failed"
            or "validator_failed" in reasons
            or "parser_failed" in reasons
            or "outside_text_detected" in reasons
        )
        if not include_in_queue:
            continue

        review_queue.append(
            {
                "page_number": int(page_number),
                "score": score,
                "status": status or "unknown",
                "reasons": reasons,
                "recommended_action": _recommended_action(status=status, reasons=reasons),
                "retry_reason": retry_reason,
                "transport_retries_count": int(transport_retries),
                "rate_limit_hit": bool(_to_bool(page.get("rate_limit_hit", False))),
                "ocr_used": bool(ocr_used),
                "image_used": bool(_to_bool(page.get("image_used", False))),
            }
        )

    review_queue.sort(key=lambda item: (-_to_float(item.get("score", 0.0)), _to_int(item.get("page_number", 0))))

    worst = max(per_page_scores) if per_page_scores else 0.0
    mean_score = sum(per_page_scores) / float(len(per_page_scores) or 1)
    top_count = min(3, len(per_page_scores))
    top_avg = (
        sum(sorted(per_page_scores, reverse=True)[:top_count]) / float(top_count)
        if top_count > 0
        else 0.0
    )
    overall = min(1.0, (0.50 * worst) + (0.30 * top_avg) + (0.20 * mean_score))

    return {
        "quality_risk_score": round(overall, 4),
        "review_queue_count": int(len(review_queue)),
        "review_queue": review_queue,
    }
