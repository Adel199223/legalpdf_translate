"""Delegated summary and cost-estimate logic for the translation workflow."""

from __future__ import annotations

import math

from .contracts import CostEstimateInputs, SummarySignalInputs


def classify_suspected_cause(inputs: SummarySignalInputs) -> tuple[str, list[str]]:
    evidence: list[str] = []
    selected = max(1, inputs.selected_pages_count)
    images_ratio = inputs.pages_with_images / float(selected)
    retries_ratio = inputs.pages_with_retries / float(selected)
    reasoning_ratio = inputs.total_reasoning_tokens / float(max(1, inputs.total_tokens))
    transport_threshold = max(3, int(math.ceil(0.5 * selected)))

    if images_ratio >= 0.30 and inputs.avg_image_bytes >= 1_048_576:
        evidence.append(
            f'images_ratio={images_ratio:.3f}>=0.300 and avg_image_bytes={int(inputs.avg_image_bytes)}>=1048576'
        )
        return 'image_auto_triggering', evidence
    if reasoning_ratio >= 0.60 and inputs.effort_policy == 'fixed_xhigh':
        evidence.append(
            f'reasoning_ratio={reasoning_ratio:.3f}>=0.600 and effort_policy=fixed_xhigh'
        )
        return 'xhigh_reasoning_tokens', evidence
    if retries_ratio >= 0.20:
        evidence.append(f'retries_ratio={retries_ratio:.3f}>=0.200')
        return 'compliance_retries', evidence
    if inputs.rate_limit_hits > 0:
        evidence.append(
            'rate_limit_hits='
            f'{inputs.rate_limit_hits}, transport_retries_total={inputs.transport_retries_total}, '
            f'threshold={transport_threshold}'
        )
        return 'rate_limiting', evidence
    if inputs.transport_retries_total >= transport_threshold:
        evidence.append(
            'transport_retries_total='
            f'{inputs.transport_retries_total}>=threshold={transport_threshold} with rate_limit_hits=0'
        )
        return 'transport_instability', evidence
    evidence.append('no primary threshold fired')
    return 'mixed_or_unknown', evidence


def estimate_cost_if_available(inputs: CostEstimateInputs) -> float | None:
    if (
        inputs.input_rate is None
        or inputs.output_rate is None
        or inputs.reasoning_rate is None
    ):
        return None
    estimate = (
        (inputs.total_input_tokens / 1_000_000.0) * inputs.input_rate
        + (inputs.total_output_tokens / 1_000_000.0) * inputs.output_rate
        + (inputs.total_reasoning_tokens / 1_000_000.0) * inputs.reasoning_rate
    )
    return round(estimate, 6)
