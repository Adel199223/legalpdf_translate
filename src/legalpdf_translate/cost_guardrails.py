"""Deterministic cost estimation and budget guardrail helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from statistics import median
from typing import Mapping, Sequence

from .types import BudgetExceedPolicy, EffortPolicy, ImageMode, OcrMode, TargetLang

_BUILT_IN_MODEL_RATES: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00, "reasoning": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60, "reasoning": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00, "reasoning": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60, "reasoning": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40, "reasoning": 0.40},
    "o3": {"input": 2.00, "output": 8.00, "reasoning": 8.00},
    "o3-mini": {"input": 1.10, "output": 4.40, "reasoning": 4.40},
    "o4-mini": {"input": 1.10, "output": 4.40, "reasoning": 4.40},
    "gpt-5.2": {"input": 2.00, "output": 8.00, "reasoning": 8.00},
}

_PROMPT_OVERHEAD_BY_LANG = {
    TargetLang.EN.value: 1500,
    TargetLang.FR.value: 1600,
    TargetLang.AR.value: 1700,
}

_OUTPUT_MULTIPLIER_BY_LANG = {
    TargetLang.EN.value: 0.45,
    TargetLang.FR.value: 0.60,
    TargetLang.AR.value: 0.70,
}

_REASONING_RATIO_BY_POLICY = {
    EffortPolicy.ADAPTIVE.value: 0.22,
    EffortPolicy.FIXED_HIGH.value: 0.22,
    EffortPolicy.FIXED_XHIGH.value: 0.45,
}

_IMAGE_MULTIPLIER_BY_MODE = {
    ImageMode.OFF.value: 1.00,
    ImageMode.AUTO.value: 1.05,
    ImageMode.ALWAYS.value: 1.20,
}

_OCR_MULTIPLIER_BY_MODE = {
    OcrMode.OFF.value: 1.00,
    OcrMode.AUTO.value: 1.00,
    OcrMode.ALWAYS.value: 1.10,
}


@dataclass(slots=True, frozen=True)
class CostRates:
    input_per_1m: float
    output_per_1m: float
    reasoning_per_1m: float
    source: str
    explanation: str


@dataclass(slots=True, frozen=True)
class PricingResolution:
    status: str
    reason: str
    rates: CostRates | None


@dataclass(slots=True, frozen=True)
class PreRunTokenEstimate:
    source_tokens_per_page: int
    prompt_overhead_tokens_per_page: int
    output_multiplier: float
    reasoning_ratio: float
    image_multiplier: float
    ocr_multiplier: float
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_reasoning_tokens: int
    estimated_total_tokens: int

    def to_dict(self) -> dict[str, float | int]:
        return {
            "source_tokens_per_page_estimate": int(self.source_tokens_per_page),
            "prompt_overhead_tokens_per_page": int(self.prompt_overhead_tokens_per_page),
            "output_multiplier": float(self.output_multiplier),
            "reasoning_ratio": float(self.reasoning_ratio),
            "image_multiplier": float(self.image_multiplier),
            "ocr_multiplier": float(self.ocr_multiplier),
            "estimated_input_tokens": int(self.estimated_input_tokens),
            "estimated_output_tokens": int(self.estimated_output_tokens),
            "estimated_reasoning_tokens": int(self.estimated_reasoning_tokens),
            "estimated_total_tokens": int(self.estimated_total_tokens),
        }


@dataclass(slots=True, frozen=True)
class BudgetDecision:
    decision: str
    reason: str
    cap_exceeded: bool | None


def normalize_cost_profile_id(value: str | None) -> str:
    return (value or "").strip() or "default_local"


def deterministic_sample_pages(selected_pages: Sequence[int], *, max_samples: int = 3) -> list[int]:
    if max_samples <= 0:
        return []
    if not selected_pages:
        return []
    first = int(selected_pages[0])
    middle = int(selected_pages[len(selected_pages) // 2])
    last = int(selected_pages[-1])
    sample: list[int] = []
    for page in (first, middle, last):
        if page not in sample:
            sample.append(page)
    return sample[:max_samples]


def resolve_pricing(model: str, *, env: Mapping[str, str] | None = None) -> PricingResolution:
    env_map = env if env is not None else os.environ
    raw_input = str(env_map.get("LEGALPDF_COST_INPUT_PER_1M", "") or "").strip()
    raw_output = str(env_map.get("LEGALPDF_COST_OUTPUT_PER_1M", "") or "").strip()
    raw_reasoning = str(env_map.get("LEGALPDF_COST_REASONING_PER_1M", "") or "").strip()

    env_values = [raw_input, raw_output, raw_reasoning]
    has_any_env_rate = any(value != "" for value in env_values)
    has_all_env_rates = all(value != "" for value in env_values)

    if has_any_env_rate and not has_all_env_rates:
        return PricingResolution(
            status="failed",
            reason="partial_env_rates",
            rates=None,
        )

    if has_all_env_rates:
        try:
            input_rate = float(raw_input)
            output_rate = float(raw_output)
            reasoning_rate = float(raw_reasoning)
        except ValueError:
            return PricingResolution(
                status="failed",
                reason="invalid_env_rate_value",
                rates=None,
            )
        if input_rate < 0.0 or output_rate < 0.0 or reasoning_rate < 0.0:
            return PricingResolution(
                status="failed",
                reason="negative_env_rate_value",
                rates=None,
            )
        return PricingResolution(
            status="available",
            reason="env_rates",
            rates=CostRates(
                input_per_1m=input_rate,
                output_per_1m=output_rate,
                reasoning_per_1m=reasoning_rate,
                source="env",
                explanation=f"env rates ({input_rate}/{output_rate}/{reasoning_rate} per 1M)",
            ),
        )

    built_in = _BUILT_IN_MODEL_RATES.get((model or "").strip())
    if built_in is None:
        return PricingResolution(
            status="unavailable",
            reason="unknown_model_without_env_rates",
            rates=None,
        )
    return PricingResolution(
        status="available",
        reason="built_in_model_table",
        rates=CostRates(
            input_per_1m=float(built_in["input"]),
            output_per_1m=float(built_in["output"]),
            reasoning_per_1m=float(built_in["reasoning"]),
            source="built_in",
            explanation=f"built-in table for {(model or '').strip()}",
        ),
    )


def estimate_pre_run_tokens(
    *,
    selected_pages_count: int,
    sampled_page_char_counts: Sequence[int],
    target_lang: str | TargetLang,
    effort_policy: str | EffortPolicy,
    image_mode: str | ImageMode,
    ocr_mode: str | OcrMode,
) -> PreRunTokenEstimate | None:
    if selected_pages_count <= 0:
        return None
    normalized_counts = [int(value) for value in sampled_page_char_counts if int(value) >= 0]
    if not normalized_counts:
        return None

    lang_key = _normalize_target_lang(target_lang)
    policy_key = _normalize_effort_policy(effort_policy)
    image_mode_key = _normalize_image_mode(image_mode)
    ocr_mode_key = _normalize_ocr_mode(ocr_mode)

    median_chars = float(median(normalized_counts))
    source_tokens_per_page = max(40, int(round(median_chars / 4.0)))
    prompt_overhead = int(_PROMPT_OVERHEAD_BY_LANG.get(lang_key, _PROMPT_OVERHEAD_BY_LANG[TargetLang.EN.value]))
    output_multiplier = float(_OUTPUT_MULTIPLIER_BY_LANG.get(lang_key, _OUTPUT_MULTIPLIER_BY_LANG[TargetLang.EN.value]))
    reasoning_ratio = float(_REASONING_RATIO_BY_POLICY.get(policy_key, _REASONING_RATIO_BY_POLICY[EffortPolicy.ADAPTIVE.value]))
    image_multiplier = float(_IMAGE_MULTIPLIER_BY_MODE.get(image_mode_key, 1.0))
    ocr_multiplier = float(_OCR_MULTIPLIER_BY_MODE.get(ocr_mode_key, 1.0))

    effective_input_per_page = int(round((source_tokens_per_page + prompt_overhead) * image_multiplier * ocr_multiplier))
    effective_output_per_page = int(round(source_tokens_per_page * output_multiplier * image_multiplier * ocr_multiplier))
    effective_reasoning_per_page = int(round(effective_output_per_page * reasoning_ratio))

    estimated_input_tokens = max(0, effective_input_per_page * int(selected_pages_count))
    estimated_output_tokens = max(0, effective_output_per_page * int(selected_pages_count))
    estimated_reasoning_tokens = max(0, effective_reasoning_per_page * int(selected_pages_count))
    estimated_total_tokens = estimated_input_tokens + estimated_output_tokens + estimated_reasoning_tokens

    return PreRunTokenEstimate(
        source_tokens_per_page=source_tokens_per_page,
        prompt_overhead_tokens_per_page=prompt_overhead,
        output_multiplier=output_multiplier,
        reasoning_ratio=reasoning_ratio,
        image_multiplier=image_multiplier,
        ocr_multiplier=ocr_multiplier,
        estimated_input_tokens=estimated_input_tokens,
        estimated_output_tokens=estimated_output_tokens,
        estimated_reasoning_tokens=estimated_reasoning_tokens,
        estimated_total_tokens=estimated_total_tokens,
    )


def estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    rates: CostRates,
) -> float:
    estimate = (
        (max(0, int(input_tokens)) / 1_000_000.0) * rates.input_per_1m
        + (max(0, int(output_tokens)) / 1_000_000.0) * rates.output_per_1m
        + (max(0, int(reasoning_tokens)) / 1_000_000.0) * rates.reasoning_per_1m
    )
    return round(float(estimate), 6)


def evaluate_budget_decision(
    *,
    budget_cap_usd: float | None,
    estimated_cost_usd: float | None,
    budget_on_exceed: str | BudgetExceedPolicy,
) -> BudgetDecision:
    policy = _normalize_budget_policy(budget_on_exceed)
    if budget_cap_usd is None:
        if estimated_cost_usd is None:
            return BudgetDecision(
                decision="n/a",
                reason="estimate_unavailable_no_budget_cap",
                cap_exceeded=None,
            )
        return BudgetDecision(
            decision="allow",
            reason="no_budget_cap_configured",
            cap_exceeded=None,
        )

    if estimated_cost_usd is None:
        return BudgetDecision(
            decision="n/a",
            reason="estimate_unavailable_with_budget_cap",
            cap_exceeded=None,
        )

    if estimated_cost_usd <= float(budget_cap_usd):
        return BudgetDecision(
            decision="allow",
            reason="estimate_within_budget_cap",
            cap_exceeded=False,
        )

    if policy == BudgetExceedPolicy.BLOCK.value:
        return BudgetDecision(
            decision="block",
            reason="estimate_exceeds_budget_cap",
            cap_exceeded=True,
        )

    return BudgetDecision(
        decision="warn",
        reason="estimate_exceeds_budget_cap",
        cap_exceeded=True,
    )


def _normalize_target_lang(value: str | TargetLang) -> str:
    if isinstance(value, TargetLang):
        return value.value
    return str(value or "").strip().upper() or TargetLang.EN.value


def _normalize_effort_policy(value: str | EffortPolicy) -> str:
    if isinstance(value, EffortPolicy):
        return value.value
    normalized = str(value or "").strip().lower()
    if normalized in _REASONING_RATIO_BY_POLICY:
        return normalized
    return EffortPolicy.ADAPTIVE.value


def _normalize_image_mode(value: str | ImageMode) -> str:
    if isinstance(value, ImageMode):
        return value.value
    normalized = str(value or "").strip().lower()
    if normalized in _IMAGE_MULTIPLIER_BY_MODE:
        return normalized
    return ImageMode.OFF.value


def _normalize_ocr_mode(value: str | OcrMode) -> str:
    if isinstance(value, OcrMode):
        return value.value
    normalized = str(value or "").strip().lower()
    if normalized in _OCR_MULTIPLIER_BY_MODE:
        return normalized
    return OcrMode.OFF.value


def _normalize_budget_policy(value: str | BudgetExceedPolicy) -> str:
    if isinstance(value, BudgetExceedPolicy):
        return value.value
    normalized = str(value or "").strip().lower()
    if normalized == BudgetExceedPolicy.BLOCK.value:
        return BudgetExceedPolicy.BLOCK.value
    return BudgetExceedPolicy.WARN.value

