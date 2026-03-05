from __future__ import annotations

from legalpdf_translate.workflow_components.quality_risk import build_quality_risk_summary


def test_quality_risk_scoring_is_deterministic() -> None:
    page_rows = [
        (
            1,
            {
                "status": "done",
                "retry_used": False,
                "validator_failed": False,
                "parser_failed": False,
                "transport_retries_count": 0,
                "rate_limit_hit": False,
                "source_route": "direct_text",
                "ocr_request_reason": "not_requested",
                "ocr_used": False,
                "image_used": False,
                "reasoning_tokens": 120,
                "wall_seconds": 2.4,
                "retry_reason": "",
                "exception_class": "",
            },
        ),
        (
            2,
            {
                "status": "done",
                "retry_used": True,
                "validator_failed": True,
                "parser_failed": False,
                "transport_retries_count": 2,
                "rate_limit_hit": True,
                "source_route": "direct_text",
                "ocr_request_reason": "required",
                "ocr_used": False,
                "image_used": True,
                "reasoning_tokens": 2200,
                "wall_seconds": 11.5,
                "retry_reason": "outside_text",
                "exception_class": "RateLimitError",
            },
        ),
    ]

    first = build_quality_risk_summary(page_rows)
    second = build_quality_risk_summary(page_rows)

    assert first == second
    assert first["review_queue_count"] == 1
    queue_entry = first["review_queue"][0]
    assert queue_entry["page_number"] == 2
    assert queue_entry["recommended_action"] == "rerun_with_ocr"
    assert "validator_failed" in queue_entry["reasons"]
    assert "ocr_required_not_used" in queue_entry["reasons"]


def test_quality_risk_flags_failed_pages_for_rerun() -> None:
    summary = build_quality_risk_summary(
        [
            (
                7,
                {
                    "status": "failed",
                    "retry_used": True,
                    "retry_reason": "pt_language_leak",
                    "transport_retries_count": 1,
                    "rate_limit_hit": False,
                    "reasoning_tokens": 100,
                    "wall_seconds": 1.0,
                },
            )
        ]
    )

    assert summary["quality_risk_score"] >= 0.9
    assert summary["review_queue_count"] == 1
    queue_entry = summary["review_queue"][0]
    assert queue_entry["page_number"] == 7
    assert queue_entry["status"] == "failed"
    assert queue_entry["recommended_action"] == "rerun_page"
    assert "page_failed" in queue_entry["reasons"]


def test_quality_risk_empty_input_returns_zero_payload() -> None:
    summary = build_quality_risk_summary([])

    assert summary["quality_risk_score"] == 0.0
    assert summary["review_queue_count"] == 0
    assert summary["review_queue"] == []
