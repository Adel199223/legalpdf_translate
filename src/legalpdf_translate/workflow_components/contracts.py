"""Typed internal contracts for workflow evaluation and summary components."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class OutputEvaluation:
    ok: bool
    normalized_text: str | None
    defect_reason: str | None
    parser_failed: bool = False
    validator_failed: bool = False
    outside_text: bool = False
    block_count: int = 0
    ar_autofix_applied_count: int = 0
    ar_token_details: dict[str, int] | None = None


@dataclass(slots=True)
class SummarySignalInputs:
    selected_pages_count: int
    pages_with_images: int
    avg_image_bytes: float
    total_reasoning_tokens: int
    total_tokens: int
    effort_policy: str
    pages_with_retries: int
    rate_limit_hits: int
    transport_retries_total: int


@dataclass(slots=True)
class CostEstimateInputs:
    total_input_tokens: int
    total_output_tokens: int
    total_reasoning_tokens: int
    input_rate: float | None
    output_rate: float | None
    reasoning_rate: float | None
