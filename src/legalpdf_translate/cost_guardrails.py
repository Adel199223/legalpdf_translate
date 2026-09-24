"""Deterministic cost estimation and budget guardrail helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
import math
from statistics import median
from types import MappingProxyType
from typing import Any, Mapping, Sequence

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
    "gpt-5.2": {"input": 1.75, "output": 14.00, "reasoning": 14.00},
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
    cached_input_per_1m: float | None = None
    cache_write_per_1m: float | None = None
    verified_at: str | None = None
    source_url: str | None = None
    pricing_version: str = "legacy_unverified"
    pricing_model: str | None = None
    provider: str = "openai"
    service_tier: str | None = None
    billing_scope: str | None = None
    currency: str = "USD"


@dataclass(slots=True, frozen=True)
class PricingResolution:
    status: str
    reason: str
    rates: CostRates | None


@dataclass(slots=True, frozen=True)
class PricingSnapshot:
    """A caller-supplied, dated price table suitable for measured accounting.

    The application deliberately does not turn its legacy forecast table into
    billing evidence.  Acceptance code must inject a snapshot whose identity,
    verification date and source were frozen before dispatch.
    """

    snapshot_id: str
    verified_at: str
    source: str
    models: Mapping[str, CostRates]

    def __post_init__(self) -> None:
        if not _safe_identifier(self.snapshot_id):
            raise ValueError("Pricing snapshot_id must be a concise identifier.")
        raw_verified_at = str(self.verified_at or "")
        try:
            parsed_verified_at = date.fromisoformat(raw_verified_at)
        except ValueError as exc:
            raise ValueError("Pricing snapshot requires an ISO YYYY-MM-DD verification date.") from exc
        if parsed_verified_at.isoformat() != raw_verified_at:
            raise ValueError("Pricing snapshot requires an ISO YYYY-MM-DD verification date.")
        if not str(self.source or "").strip():
            raise ValueError("Pricing snapshot requires a source description.")
        normalized: dict[str, CostRates] = {}
        for key, rates in dict(self.models).items():
            provider_model = str(key or "").strip()
            if ":" not in provider_model or not isinstance(rates, CostRates):
                raise ValueError("Pricing keys must use provider:model and CostRates values.")
            _validate_rates(rates)
            if rates.pricing_version in {"", "legacy_unverified"}:
                raise ValueError("Snapshot rates must have a verified pricing version.")
            if not rates.verified_at:
                raise ValueError("Snapshot rates must record their verification date.")
            identity, *billing = provider_model.split("|")
            provider, model = identity.split(":", 1)
            if billing and (
                len(billing) != 3
                or billing != [rates.service_tier, rates.billing_scope, rates.currency]
            ):
                raise ValueError("Pricing key and billing identity differ.")
            if (rates.service_tier is None) != (rates.billing_scope is None):
                raise ValueError("Verified billing identity requires both tier and scope.")
            if rates.service_tier is not None and (
                not _safe_identifier(rates.service_tier)
                or rates.service_tier == "auto"
                or not _safe_identifier(rates.billing_scope or "")
            ):
                raise ValueError("Rates require an explicit actual service tier and billing scope.")
            if rates.currency != "USD":
                raise ValueError("Only USD rates are supported; no currency conversion is inferred.")
            if (
                rates.verified_at != self.verified_at
                or rates.provider.lower() != provider.lower()
                or rates.pricing_model != model
            ):
                raise ValueError("Snapshot rate identity/date does not match its provider:model key.")
            normalized[provider_model] = rates
        object.__setattr__(self, "models", MappingProxyType(normalized))

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "PricingSnapshot":
        raw_models = value.get("models")
        if not isinstance(raw_models, Mapping):
            raise ValueError("Pricing snapshot models must be a mapping.")
        snapshot_id = str(value.get("snapshot_id") or "").strip()
        verified_at = str(value.get("verified_at") or "").strip()
        source = str(value.get("source") or "").strip()
        models: dict[str, CostRates] = {}
        for key, raw in raw_models.items():
            if not isinstance(raw, Mapping):
                raise ValueError("Each pricing model entry must be a mapping.")
            identity, *billing = str(key or "").split("|")
            provider, separator, model = identity.partition(":")
            if not separator or not provider or not model:
                raise ValueError("Pricing keys must use provider:model.")
            models[str(key)] = CostRates(
                input_per_1m=_finite_rate(raw.get("input_per_1m")),
                output_per_1m=_finite_rate(raw.get("output_per_1m")),
                # Kept for serialized compatibility; output totals are inclusive.
                reasoning_per_1m=_finite_rate(
                    raw.get("reasoning_per_1m", raw.get("output_per_1m"))
                ),
                cached_input_per_1m=_optional_finite_rate(raw.get("cached_input_per_1m")),
                cache_write_per_1m=_optional_finite_rate(raw.get("cache_write_per_1m")),
                source=str(raw.get("source") or source),
                explanation=str(raw.get("explanation") or f"{snapshot_id}:{key}"),
                verified_at=str(raw.get("verified_at") or verified_at),
                source_url=(str(raw.get("source_url")) if raw.get("source_url") else None),
                pricing_version=str(raw.get("pricing_version") or snapshot_id),
                pricing_model=str(raw.get("pricing_model") or model),
                provider=str(raw.get("provider") or provider),
                service_tier=(str(raw["service_tier"]) if raw.get("service_tier") else None),
                billing_scope=(str(raw["billing_scope"]) if raw.get("billing_scope") else None),
                currency=str(raw.get("currency", "USD")),
            )
        return cls(
            snapshot_id=snapshot_id,
            verified_at=verified_at,
            source=source,
            models=models,
        )

    def resolve(
        self, provider: str, model: str, *, service_tier: str | None = None,
        billing_scope: str | None = None, currency: str = "USD",
    ) -> PricingResolution:
        provider_key = str(provider or "").strip().lower()
        model_key = str(model or "").strip()
        key = f"{provider_key}:{model_key}"
        explicit = service_tier is not None or billing_scope is not None
        if explicit:
            if not service_tier or not billing_scope or service_tier == "auto" or currency != "USD":
                return PricingResolution("unavailable", "billing_identity_unavailable", None)
            rates = self.models.get(f"{key}|{service_tier}|{billing_scope}|{currency}")
            if rates is None:
                # A single explicitly scoped row may retain the old key shape.
                # An unscoped historical row never supplies missing billing evidence.
                rates = self.models.get(key)
            if rates is not None and (
                rates.service_tier != service_tier or rates.billing_scope != billing_scope
                or rates.currency != currency
            ):
                rates = None
        else:
            rates = self.models.get(key)
        if rates is None:
            return PricingResolution(
                status="unavailable",
                reason="model_not_in_pricing_snapshot",
                rates=None,
            )
        if rates.provider.lower() != provider_key or rates.pricing_model != model_key:
            return PricingResolution(
                status="failed",
                reason="pricing_identity_mismatch",
                rates=None,
            )
        return PricingResolution(status="available", reason="verified_snapshot", rates=rates)

    def metadata(self) -> dict[str, str]:
        serialized_rates = {
            key: {
                # Normalize numeric representation so a snapshot assembled in
                # memory and the same snapshot loaded from JSON have one rate
                # identity (JSON loading commonly turns fixture integers into
                # floats through ``from_mapping``).
                "input_per_1m": float(rates.input_per_1m),
                "output_per_1m": float(rates.output_per_1m),
                "reasoning_per_1m": float(rates.reasoning_per_1m),
                "cached_input_per_1m": (
                    None
                    if rates.cached_input_per_1m is None
                    else float(rates.cached_input_per_1m)
                ),
                "cache_write_per_1m": (
                    None
                    if rates.cache_write_per_1m is None
                    else float(rates.cache_write_per_1m)
                ),
                "verified_at": rates.verified_at,
                "source_url": rates.source_url,
                "pricing_version": rates.pricing_version,
                "pricing_model": rates.pricing_model,
                "provider": rates.provider,
                **({
                    "service_tier": rates.service_tier,
                    "billing_scope": rates.billing_scope,
                    "currency": rates.currency,
                } if rates.service_tier is not None else {}),
            }
            for key, rates in sorted(self.models.items())
        }
        rates_sha256 = hashlib.sha256(
            json.dumps(
                serialized_rates,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        return {
            "snapshot_id": self.snapshot_id,
            "verified_at": self.verified_at,
            "source": self.source,
            "rates_sha256": rates_sha256,
        }

    def to_mapping(self) -> dict[str, Any]:
        """Complete immutable rate context; metadata alone cannot restore prices."""
        from dataclasses import asdict

        return {
            "snapshot_id": self.snapshot_id,
            "verified_at": self.verified_at,
            "source": self.source,
            "models": {key: asdict(rates) for key, rates in self.models.items()},
        }


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
    estimated_reasoning_tokens = max(0, effective_reasoning_per_page * int(selected_pages_count))
    # Responses-style output totals already include reasoning tokens.  Keep the
    # reasoning estimate as a breakdown, not a second billed/output quantity.
    estimated_output_tokens = (
        max(0, effective_output_per_page * int(selected_pages_count))
        + estimated_reasoning_tokens
    )
    estimated_total_tokens = estimated_input_tokens + estimated_output_tokens

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
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Price inclusive totals without adding reasoning a second time.

    ``reasoning_per_1m`` remains on ``CostRates`` for saved/configuration
    compatibility.  Provider output totals include that reasoning, so it is a
    validated breakdown only.  Cache categories likewise replace regular input
    tokens instead of being added to the inclusive input total.
    """

    estimate = estimate_cost_decimal(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        cached_input_tokens=cached_input_tokens,
        cache_write_tokens=cache_write_tokens,
        rates=rates,
    )
    return round(float(estimate), 9)


def estimate_cost_decimal(
    *,
    input_tokens: int,
    output_tokens: int,
    reasoning_tokens: int,
    rates: CostRates,
    cached_input_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> Decimal:
    counts = (
        input_tokens,
        output_tokens,
        reasoning_tokens,
        cached_input_tokens,
        cache_write_tokens,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts):
        raise ValueError("Token counts must be nonnegative integers.")
    if reasoning_tokens > output_tokens:
        raise ValueError("Reasoning tokens exceed the inclusive output total.")
    if cached_input_tokens + cache_write_tokens > input_tokens:
        raise ValueError("Cache token breakdown exceeds the inclusive input total.")
    _validate_rates(rates)
    if cached_input_tokens and rates.cached_input_per_1m is None:
        raise ValueError("Cached-input pricing is unavailable.")
    if cache_write_tokens and rates.cache_write_per_1m is None:
        raise ValueError("Cache-write pricing is unavailable.")

    regular_input = input_tokens - cached_input_tokens - cache_write_tokens
    million = Decimal(1_000_000)
    total = (
        Decimal(regular_input) * _decimal_rate(rates.input_per_1m)
        + Decimal(cached_input_tokens) * _decimal_rate(rates.cached_input_per_1m or 0)
        + Decimal(cache_write_tokens) * _decimal_rate(rates.cache_write_per_1m or 0)
        + Decimal(output_tokens) * _decimal_rate(rates.output_per_1m)
    ) / million
    return total.quantize(Decimal("0.000000000001"), rounding=ROUND_CEILING)


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


def _safe_identifier(value: str) -> bool:
    candidate = str(value or "").strip()
    return bool(candidate) and len(candidate) <= 200 and all(
        character.isalnum() or character in "._:-" for character in candidate
    )


def _finite_rate(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Pricing rates must be finite nonnegative numbers.") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError("Pricing rates must be finite nonnegative numbers.")
    return result


def _optional_finite_rate(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _finite_rate(value)


def _decimal_rate(value: float | int) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Pricing rates must be decimal-compatible.") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("Pricing rates must be finite nonnegative numbers.")
    return result


def _validate_rates(rates: CostRates) -> None:
    for value in (
        rates.input_per_1m,
        rates.output_per_1m,
        rates.reasoning_per_1m,
        rates.cached_input_per_1m,
        rates.cache_write_per_1m,
    ):
        if value is not None:
            _finite_rate(value)
