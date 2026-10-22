"""Caller-owned, offline pricing policy; never credentials or remote discovery.

Public references checked 2026-10-15:
https://developers.openai.com/api/docs/pricing
https://developers.openai.com/api/docs/models/gpt-5.2
https://developers.openai.com/api/docs/models/gpt-4o-mini
Only public standard USD pricing is represented. Auto-tier hard caps deliberately
remain unavailable until a finite verified tier policy is explicitly supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class OrdinaryAccountingPolicy:
    """Immutable serialized snapshot, copied into each run's own accountant."""

    _pricing_json: str
    _limits_json: str
    reference_verified_on: date | None = None

    @classmethod
    def from_mapping(cls, *, pricing: Mapping[str, Any], limits: Mapping[str, Any]) -> "OrdinaryAccountingPolicy":
        from .cost_guardrails import PricingSnapshot
        # Validate before retaining the caller's values; JSON breaks nested aliases.
        frozen_pricing = json.dumps(dict(pricing), sort_keys=True, allow_nan=False)
        frozen_limits = json.dumps(dict(limits), sort_keys=True, allow_nan=False)
        PricingSnapshot.from_mapping(json.loads(frozen_pricing))
        return cls(frozen_pricing, frozen_limits)

    def accounting_arguments(self, *, today: date | None = None) -> dict[str, Any]:
        prices = json.loads(self._pricing_json)
        if self.reference_verified_on is not None:
            age = ((today or date.today()) - self.reference_verified_on).days
            if not 0 <= age <= 30:
                prices = None
        return {"pricing_snapshot": prices,
                "dispatch_limits": json.loads(self._limits_json)}


def ordinary_accounting_policy() -> OrdinaryAccountingPolicy:
    """Construct without reading settings, environment, credentials or the network.

    This is public-price attribution, not invoice reconciliation. Unsupported
    returned models/tiers/endpoints remain incomplete; no product tier is pinned.
    Model-capacity bounds are intentionally conservative, not an economical
    acceptance ceiling. They never reduce ordinary no-cap/WARN generation.
    """
    source = "https://developers.openai.com/api/docs/models/gpt-5.2"
    models = {}
    for model in ("gpt-5.2", "gpt-5.2-2025-12-11"):
        models[f"openai:{model}|default|openai_public_api|USD"] = {
            "input_per_1m": 1.75, "cached_input_per_1m": 0.175, "output_per_1m": 14,
            "provider": "openai", "pricing_model": model, "service_tier": "default",
            "billing_scope": "openai_public_api", "currency": "USD", "source_url": source,
        }
    ocr_source = "https://developers.openai.com/api/docs/models/gpt-4o-mini"
    pricing_source = "https://developers.openai.com/api/docs/pricing"
    for model in ("gpt-4o-mini", "gpt-4o-mini-2024-07-18"):
        models[f"openai:{model}|default|openai_public_api|USD"] = {
            "input_per_1m": .15, "cached_input_per_1m": .075, "output_per_1m": .60,
            "provider": "openai", "pricing_model": model, "service_tier": "default",
            "billing_scope": "openai_public_api", "currency": "USD", "source_url": pricing_source,
        }
    policy = OrdinaryAccountingPolicy.from_mapping(pricing={
        "snapshot_id": "openai_public_standard_2026_10_15",
        "verified_at": "2026-10-15", "source": pricing_source, "models": models,
    }, limits={"openai:*:gpt-5.2": {
        "requested_model": "gpt-5.2", "allowed_actual_models": ["gpt-5.2-2025-12-11"],
        "billing_scope": "openai_public_api", "currency": "USD",
        "allowed_base_urls": ["https://api.openai.com/v1"],
        "max_input_tokens": 400000, "max_output_tokens": 128000,
        "apply_output_bound_only_when_hard": True,
        "bound_source_url": source, "bound_verified_at": "2026-10-15",
        # No allowed_actual_service_tiers: project auto policy has not been verified.
    }, "openai:ocr:gpt-4o-mini": {
        "requested_model": "gpt-4o-mini", "allowed_actual_models": ["gpt-4o-mini-2024-07-18"],
        "billing_scope": "openai_public_api", "currency": "USD",
        "allowed_base_urls": ["https://api.openai.com/v1"],
        "max_input_tokens": 128000, "max_output_tokens": 16384,
        "apply_output_bound_only_when_hard": True,
        "bound_source_url": ocr_source, "bound_verified_at": "2026-10-15",
        # No image token bound or verified auto-tier policy: hard OCR stays gated.
    }})
    # Only the bundled public reference has this local freshness window. No
    # remote refresh or silent new approval; saved runs retain their own catalog.
    return OrdinaryAccountingPolicy(policy._pricing_json, policy._limits_json, date(2026, 10, 15))


def with_semantic_review_policy(policy: OrdinaryAccountingPolicy, saved_policy) -> OrdinaryAccountingPolicy:
    """Extend only a new explicit semantic role; old catalogs remain byte exact."""
    from .semantic_review_model_policy import validate_policy, MODEL
    from .semantic_review_billing import FRESH_POLICY
    validate_policy(saved_policy)
    pricing = json.loads(policy._pricing_json)
    limits = json.loads(policy._limits_json)
    pricing["snapshot_id"] += "_semantic_astra_2026_10_20"
    pricing["verified_at"] = "2026-10-20"
    source = "https://developers.openai.com/api/docs/models/gpt-6-astra"
    pricing["models"][f"openai:{MODEL}|default|openai_public_api|USD"] = {
        "input_per_1m": 10, "cached_input_per_1m": 1, "cache_write_per_1m": 12.5, "output_per_1m": 50,
        "provider": "openai", "pricing_model": MODEL, "service_tier": "default",
        "billing_scope": "openai_public_api", "currency": "USD", "source_url": source,
    }
    limits[f"openai:semantic_audit:{MODEL}"] = {
        "requested_model": MODEL, "allowed_actual_models": [], "allowed_actual_service_tiers": ["default"],
        "billing_scope": "openai_public_api", "currency": "USD",
        "allowed_base_urls": ["https://api.openai.com/v1"],
        "max_input_tokens": 272000, "max_output_tokens": 64000,
        "apply_output_bound_only_when_hard": True,
        "semantic_review_billing_policy": FRESH_POLICY,
        "bound_source_url": source, "bound_verified_at": "2026-10-20",
    }
    extended = OrdinaryAccountingPolicy.from_mapping(pricing=pricing, limits=limits)
    # Keep the earlier bundled primary/OCR freshness window; no implied reverification.
    return OrdinaryAccountingPolicy(extended._pricing_json, extended._limits_json, policy.reference_verified_on)
