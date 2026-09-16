"""Sanitized, per-dispatch usage accounting with durable run journals."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import threading
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Sequence
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit

from .budget_reservations import atomic_json, fingerprint, locked, money
from .cost_guardrails import PricingSnapshot, estimate_cost_decimal


ACCOUNTING_SCHEMA_VERSION = 1
TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "reasoning_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
)
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.RLock] = {}


class DispatchAccountingError(RuntimeError):
    """A dispatch cannot be safely recorded or reconciled."""


@dataclass(slots=True, frozen=True)
class AccountingBinding:
    accountant: Any
    purpose: str | None = None
    page_number: int | None = None


@dataclass(slots=True, frozen=True)
class DispatchTicket:
    call_id: str
    provider: str
    requested_model: str
    purpose: str
    page_number: int | None
    request_hash: str
    attempt: int
    reservation_id: str | None = None


_CURRENT_ACCOUNTING: ContextVar[AccountingBinding | None] = ContextVar(
    "legalpdf_dispatch_accounting",
    default=None,
)


@contextmanager
def accounting_context(
    accountant: Any | None,
    *,
    purpose: str | None = None,
    page_number: int | None = None,
) -> Iterator[AccountingBinding | None]:
    """Bind accounting to one task; nested scopes inherit omitted fields."""

    previous = _CURRENT_ACCOUNTING.get()
    resolved_accountant = accountant if accountant is not None else (
        previous.accountant if previous is not None else None
    )
    if resolved_accountant is None:
        binding = None
    else:
        binding = AccountingBinding(
            accountant=resolved_accountant,
            purpose=purpose if purpose is not None else (
                previous.purpose if previous is not None else None
            ),
            page_number=page_number if page_number is not None else (
                previous.page_number if previous is not None else None
            ),
        )
    token = _CURRENT_ACCOUNTING.set(binding)
    try:
        yield binding
    finally:
        _CURRENT_ACCOUNTING.reset(token)


context_scope = accounting_context


def current_accounting_binding() -> AccountingBinding | None:
    return _CURRENT_ACCOUNTING.get()


def normalize_usage(usage: Any, *, provider: str = "openai") -> dict[str, Any]:
    """Normalize inclusive provider totals without retaining response content."""

    if provider.strip().lower() == "gemini":
        usage = _normalize_gemini_usage_input(usage)
    input_details = _field(usage, "input_tokens_details")
    output_details = _field(usage, "output_tokens_details")
    values = {
        "input_tokens": _field(usage, "input_tokens"),
        "output_tokens": _field(usage, "output_tokens"),
        "total_tokens": _field(usage, "total_tokens"),
        "reasoning_tokens": _field(
            usage,
            "reasoning_tokens",
            _field(output_details, "reasoning_tokens"),
        ),
        "cached_input_tokens": _field(
            usage,
            "cached_input_tokens",
            _field(input_details, "cached_tokens"),
        ),
        "cache_write_tokens": _field(
            usage,
            "cache_write_tokens",
            _field(input_details, "cache_write_tokens"),
        ),
    }
    missing = values["input_tokens"] is None or values["output_tokens"] is None
    invalid = any(value is not None and _token_count(value) is None for value in values.values())
    counts = {name: _token_count(value) for name, value in values.items()}
    for name in ("reasoning_tokens", "cached_input_tokens", "cache_write_tokens"):
        if counts[name] is None and values[name] is None:
            counts[name] = 0
    total_source = "provider"
    if counts["total_tokens"] is None and not missing and not invalid:
        counts["total_tokens"] = int(counts["input_tokens"] or 0) + int(counts["output_tokens"] or 0)
        total_source = "derived"
    if not missing and not invalid:
        invalid = bool(
            int(counts["reasoning_tokens"] or 0) > int(counts["output_tokens"] or 0)
            or int(counts["cached_input_tokens"] or 0)
            + int(counts["cache_write_tokens"] or 0)
            > int(counts["input_tokens"] or 0)
            or int(counts["total_tokens"] or 0)
            != int(counts["input_tokens"] or 0) + int(counts["output_tokens"] or 0)
        )
    status = "invalid" if invalid else "missing" if missing else "available"
    return {
        **counts,
        "usage_status": status,
        "total_tokens_source": total_source,
        "reasoning_included_in_output": True,
    }


class DispatchAccounting:
    """Append-only begin/finish journal for a single run generation."""

    hard_budget = False

    def __init__(
        self,
        run_dir: Path,
        *,
        run_identity: Mapping[str, Any],
        pricing_snapshot: PricingSnapshot | Mapping[str, Any] | None = None,
        budget_context: Any | None = None,
        dispatch_limits: Mapping[str, Mapping[str, Any]] | None = None,
        historical_incomplete: bool = False,
        journal_name: str = "dispatch_accounting.json",
        pricing_archives: Sequence[PricingSnapshot | Mapping[str, Any]] = (),
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.run_dir / journal_name
        self.lock_path = self.journal_path.with_suffix(self.journal_path.suffix + ".lock")
        self.run_identity = _safe_mapping(run_identity, "run_identity")
        self.run_identity_hash = _fingerprint(self.run_identity)
        self.pricing_snapshot = _coerce_snapshot(pricing_snapshot)
        self._pricing_metadata = self.pricing_snapshot.metadata() if self.pricing_snapshot else None
        self._pricing_context_missing = False
        self._pricing_archives = tuple(_coerce_snapshot(item) for item in pricing_archives)
        self.budget_context = budget_context
        self._bound_budget_context = budget_context
        self.hard_budget = bool(budget_context is not None and getattr(budget_context, "hard", True))
        self.budget_identity = _budget_identity(budget_context)
        self.dispatch_limits = _normalize_limits(dispatch_limits)
        self._amendment_bound_limits = False
        if budget_context is not None:
            from .acceptance_budget import LegacyAcceptanceBudget
            if isinstance(budget_context, LegacyAcceptanceBudget) and budget_context.dispatch_enabled:
                approved_limits = _normalize_limits(budget_context.dispatch_limits)
                if self.dispatch_limits != approved_limits:
                    raise DispatchAccountingError("Dispatch limits differ from the independently approved amendment.")
                self._amendment_bound_limits = True
        self.historical_incomplete = bool(historical_incomplete)
        self._instance_id = uuid4().hex
        self._recovered_in_flight = False
        self._persistence_failed = False
        with _locked_path(self.lock_path):
            if self.journal_path.exists():
                self._restore_saved_context()
                state = self._load_unlocked()
                self._recovered_in_flight = any(
                    event.get("event") == "begin"
                    and not _has_finish(state["events"], event.get("call_id"))
                    for event in state["events"]
                )
            else:
                now = _now()
                self._save_unlocked(
                    {
                        "schema_version": ACCOUNTING_SCHEMA_VERSION,
                        "run_identity": self.run_identity,
                        "run_identity_hash": self.run_identity_hash,
                        "historical_incomplete": self.historical_incomplete,
                        "pricing_snapshot": self._pricing_metadata,
                        "pricing_catalog": self.pricing_snapshot.to_mapping() if self.pricing_snapshot else None,
                        "dispatch_limits": {key: dict(value) for key, value in self.dispatch_limits.items()},
                        "budget_context": self.budget_identity,
                        "created_at": now,
                        "updated_at": now,
                        "events": [],
                    }
                )
        self._dispatch_limits_fingerprint = fingerprint(
            {key: dict(value) for key, value in self.dispatch_limits.items()}
        )

    @property
    def can_retry(self) -> bool:
        if self._recovered_in_flight or self._persistence_failed:
            return False
        if self.budget_context is None:
            return True
        try:
            status = self.budget_context.status()
        except Exception:
            return False
        return status.get("blocked_reason") is None

    def request_limits(
        self,
        provider: str,
        purpose: str,
        requested_model: str,
    ) -> Mapping[str, Any]:
        self._validate_pricing_context()
        if self._pricing_context_missing:
            raise DispatchAccountingError("Saved pricing catalog is unavailable; preserve history and supply its exact archive.")
        if fingerprint({key: dict(value) for key, value in self.dispatch_limits.items()}) != self._dispatch_limits_fingerprint:
            raise DispatchAccountingError("Immutable dispatch limits changed in memory.")
        key = f"{_identifier(provider, 'provider').lower()}:{_identifier(purpose, 'purpose')}"
        limits = next((self.dispatch_limits[candidate] for candidate in (
            f"{key}:{requested_model}", f"{provider.lower()}:*:{requested_model}", key,
        ) if candidate in self.dispatch_limits), None)
        if limits is None:
            if self.hard_budget:
                raise DispatchAccountingError(
                    f"Hard-budget dispatch limits are missing for {key}."
                )
            return MappingProxyType({})
        expected_model = limits.get("requested_model")
        if expected_model is not None and expected_model != requested_model:
            raise DispatchAccountingError("Dispatch-limit model identity mismatch.")
        if self.hard_budget:
            if self.pricing_snapshot is None:
                raise DispatchAccountingError(
                    "Hard-budget dispatch requires a verified pricing snapshot."
                )
            _required_hard_limits(limits)
            if not _reservation_resolutions(self.pricing_snapshot, provider, requested_model, limits):
                raise DispatchAccountingError("Hard-budget dispatch requires verified model, tier, scope and currency prices.")
        return MappingProxyType(_json_copy(dict(limits)))

    def verify_dispatch(self, **kwargs: Any) -> None:
        """Acceptance provenance belongs to the caller-owned budget, never this journal."""
        verifier = getattr(self.budget_context, "verify_dispatch", None)
        if verifier is None:
            return
        binding = current_accounting_binding()
        arguments = dict(kwargs)
        arguments.setdefault("page_number", binding.page_number if binding else None)
        verifier(**arguments)

    def recheck_dispatch(self, reservation_id: str | None, **kwargs: Any) -> None:
        """Recheck physical approval immediately before the already-reserved send."""
        verifier = getattr(self.budget_context, "recheck_dispatch", None)
        if verifier is None:
            return
        binding = current_accounting_binding()
        arguments = dict(kwargs)
        arguments.setdefault("page_number", binding.page_number if binding else None)
        verifier(reservation_id, **arguments)

    def begin(
        self,
        *,
        provider: str,
        requested_model: str,
        request_hash: str,
        effort: str | None = "",
        purpose: str | None = None,
        page_number: int | None = None,
        bounds: Mapping[str, Any] | None = None,
        attempt: int = 1,
        call_id: str | None = None,
        requested_service_tier: str | None = None,
        billing_scope: str | None = None,
        currency: str = "USD",
        route: str | None = None,
        base_url: str | None = None,
    ) -> DispatchTicket:
        binding = current_accounting_binding()
        resolved_purpose = purpose or (binding.purpose if binding is not None else None)
        resolved_page = page_number if page_number is not None else (
            binding.page_number if binding is not None else None
        )
        provider_id = _identifier(provider, "provider").lower()
        model_id = _identifier(requested_model, "requested_model")
        purpose_id = _identifier(resolved_purpose or "unknown", "purpose")
        if not isinstance(request_hash, str) or _SHA256.fullmatch(request_hash) is None:
            raise DispatchAccountingError("request_hash must be a lowercase SHA-256 digest.")
        if type(attempt) is not int or attempt <= 0:
            raise DispatchAccountingError("attempt must be a positive integer.")
        if resolved_page is not None and (type(resolved_page) is not int or resolved_page <= 0):
            raise DispatchAccountingError("page_number must be a positive integer.")
        safe_bounds = _safe_mapping(bounds or {}, "dispatch bounds")
        tier = _requested_tier(provider_id, requested_service_tier)
        scope = _identifier(billing_scope, "billing_scope") if billing_scope else None
        currency_id = _identifier(currency, "currency")
        identifier = _identifier(call_id or uuid4().hex, "call_id")
        if self._recovered_in_flight or self._persistence_failed:
            raise DispatchAccountingError(
                "Dispatch accounting is not safe for another provider attempt."
            )
        limits = self.request_limits(provider_id, purpose_id, model_id)
        if self.hard_budget:
            _validate_bounds_match_limits(safe_bounds, limits)
            if (tier != _requested_tier(provider_id, limits.get("requested_service_tier"))
                    or scope != limits.get("billing_scope") or currency_id != limits.get("currency", "USD")):
                raise DispatchAccountingError("Dispatch billing identity differs from configured limits.")
        ceiling = _ceiling_for(
            pricing_snapshot=self.pricing_snapshot,
            provider=provider_id,
            model=model_id,
            bounds=safe_bounds,
            hard=self.hard_budget,
        )
        event = {
            "event": "begin",
            "call_id": identifier,
            "provider": provider_id,
            "requested_model": model_id,
            "requested_service_tier": tier,
            "billing_scope": scope,
            "currency": currency_id,
            "route": _identifier(route, "route") if route else None,
            "base_url": _safe_endpoint(base_url),
            "authorization_sha256": getattr(self.budget_context, "expected_amendment_sha256", None),
            "effort": str(effort or ""),
            "purpose": purpose_id,
            "page_number": resolved_page,
            "request_hash": request_hash,
            "bounds": safe_bounds,
            "attempt": attempt,
            "ceiling_usd": _decimal_text(ceiling) if ceiling is not None else None,
            "instance_id": self._instance_id,
            "at": _now(),
        }
        reservation_id: str | None = None
        if self.hard_budget:
            if ceiling is None:
                raise DispatchAccountingError(
                    "Hard-budget dispatch has no conservative price ceiling."
                )
            reservation_id = identifier
            try:
                self.budget_context.reserve(identifier, ceiling, _reservation_metadata(event))
            except Exception as exc:
                raise DispatchAccountingError("Hard-budget reservation failed.") from exc
            event["reservation_id"] = reservation_id
        try:
            self._append_begin_event(event, identifier)
        except Exception:
            self._persistence_failed = True
            raise
        return DispatchTicket(
            call_id=identifier,
            provider=provider_id,
            requested_model=model_id,
            purpose=purpose_id,
            page_number=resolved_page,
            request_hash=request_hash,
            attempt=attempt,
            reservation_id=reservation_id,
        )

    def finish(
        self,
        ticket: DispatchTicket,
        *,
        outcome: str,
        usage: Any = None,
        response_id: str | None = None,
        actual_model: str | None = None,
        error_code: str | None = None,
        actual_service_tier: str | None = None,
        actual_billing_scope: str | None = None,
        currency: str | None = None,
    ) -> Mapping[str, Any]:
        try:
            return self._finish(
                ticket,
                outcome=outcome,
                usage=usage,
                response_id=response_id,
                actual_model=actual_model,
                error_code=error_code,
                actual_service_tier=actual_service_tier,
                actual_billing_scope=actual_billing_scope,
                currency=currency,
            )
        except BaseException:
            # The transport may already have dispatched.  Keep any reservation
            # held and refuse further attempts through this accountant.
            self._persistence_failed = True
            raise

    def _finish(
        self,
        ticket: DispatchTicket,
        *,
        outcome: str,
        usage: Any = None,
        response_id: str | None = None,
        actual_model: str | None = None,
        error_code: str | None = None,
        actual_service_tier: str | None = None,
        actual_billing_scope: str | None = None,
        currency: str | None = None,
    ) -> Mapping[str, Any]:
        if not isinstance(ticket, DispatchTicket):
            raise DispatchAccountingError("finish requires a DispatchTicket.")
        outcome_id = _identifier(outcome, "outcome")
        if outcome_id not in {
            "succeeded",
            "failed",
            "refused",
            "timeout",
            "cancelled",
            "not_dispatched",
        }:
            raise DispatchAccountingError("Unsupported dispatch outcome.")
        normalized = (
            _zero_usage()
            if outcome_id == "not_dispatched"
            else normalize_usage(usage, provider=ticket.provider)
        )
        actual_model_id = (
            _identifier(actual_model, "actual_model") if actual_model else None
        )
        response_id_value = (
            _bounded_text(response_id, "response_id") if response_id else None
        )
        error_value = _identifier(error_code, "error_code") if error_code else None
        if actual_service_tier:
            _identifier(actual_service_tier, "actual_service_tier")
        if actual_billing_scope:
            _identifier(actual_billing_scope, "actual_billing_scope")
        if currency:
            _identifier(currency, "currency")
        with _locked_path(self.lock_path):
            state = self._load_unlocked()
            begin_event = _find_begin(state["events"], ticket.call_id)
            if begin_event is None or begin_event.get("request_hash") != ticket.request_hash:
                raise DispatchAccountingError("Dispatch ticket does not belong to this journal.")
            allowed_actual_models = begin_event.get("bounds", {}).get("allowed_actual_models", [])
            if not isinstance(allowed_actual_models, list):
                allowed_actual_models = []
            cost, cost_status = self._price_usage(
                normalized,
                provider=ticket.provider,
                requested_model=ticket.requested_model,
                actual_model=actual_model_id,
                outcome=outcome_id,
                allowed_actual_models=allowed_actual_models,
                requested_service_tier=begin_event.get("requested_service_tier"),
                actual_service_tier=actual_service_tier,
                billing_scope=begin_event.get("billing_scope"),
                actual_billing_scope=actual_billing_scope,
                currency=begin_event.get("currency", "USD"),
                actual_currency=currency,
                allowed_actual_service_tiers=begin_event.get("bounds", {}).get("allowed_actual_service_tiers", []),
            )
            event = {
                "event": "finish",
                "call_id": ticket.call_id,
                "outcome": outcome_id,
                "usage": normalized,
                "response_id": response_id_value,
                "actual_model": actual_model_id,
                "actual_service_tier": _identifier(actual_service_tier, "actual_service_tier") if actual_service_tier else None,
                "actual_billing_scope": actual_billing_scope or begin_event.get("billing_scope"),
                "currency": currency or begin_event.get("currency", "USD"),
                "error_code": error_value,
                "cost_usd": _decimal_text(cost) if cost is not None else None,
                "cost_status": cost_status,
                "at": _now(),
            }
            existing = _find_finish(state["events"], ticket.call_id)
            if existing is not None:
                if _completion_equivalent(existing, event):
                    return _json_copy(existing)
                raise DispatchAccountingError("Dispatch was already finished differently.")
            if response_id_value and any(
                item.get("event") == "finish"
                and item.get("response_id") == response_id_value
                and item.get("call_id") != ticket.call_id
                for item in state["events"]
            ):
                raise DispatchAccountingError("Provider response_id is already bound to another call.")
            if self.hard_budget:
                block_reason = None if cost is not None else cost_status
                try:
                    budget_result = self.budget_context.finalize(
                        ticket.reservation_id,
                        cost,
                        {
                            "outcome": outcome_id,
                            "usage_status": normalized["usage_status"],
                            "actual_model": actual_model_id,
                            "actual_service_tier": event["actual_service_tier"],
                            "actual_billing_scope": event["actual_billing_scope"],
                            "currency": event["currency"],
                            "response_id_hash": (
                                hashlib.sha256(response_id_value.encode("utf-8")).hexdigest()
                                if response_id_value
                                else None
                            ),
                        },
                        block_reason=block_reason,
                    )
                    if not isinstance(budget_result, Mapping):
                        raise DispatchAccountingError(
                            "Hard-budget reconciliation returned no durable status."
                        )
                    event["budget_status"] = budget_result.get("status")
                    event["budget_blocked_reason"] = budget_result.get("blocked_reason")
                    if event["budget_status"] != "finalized":
                        self._persistence_failed = True
                except Exception as exc:
                    self._persistence_failed = True
                    raise DispatchAccountingError("Hard-budget reconciliation failed.") from exc
            state["events"].append(event)
            try:
                self._save_unlocked(state)
            except Exception:
                self._persistence_failed = True
                raise
        return _json_copy(event)

    def summary(self) -> dict[str, Any]:
        with _locked_path(self.lock_path):
            state = self._load_unlocked()
        return _summarize(
            state["events"],
            historical_incomplete=self.historical_incomplete,
            pricing_snapshot=state.get("pricing_snapshot"),
        )

    def _price_usage(
        self,
        usage: Mapping[str, Any],
        *,
        provider: str,
        requested_model: str,
        actual_model: str | None,
        outcome: str,
        allowed_actual_models: Sequence[str] = (),
        requested_service_tier: str | None = None,
        actual_service_tier: str | None = None,
        billing_scope: str | None = None,
        actual_billing_scope: str | None = None,
        currency: str = "USD",
        actual_currency: str | None = None,
        allowed_actual_service_tiers: Sequence[str] = (),
    ) -> tuple[Decimal | None, str]:
        if usage["usage_status"] != "available":
            return None, f"{usage['usage_status']}_usage"
        if outcome == "not_dispatched":
            return Decimal(0), "available"
        if actual_model is None:
            return None, "missing_actual_model"
        if actual_model != requested_model and actual_model not in allowed_actual_models:
            return None, "actual_model_mismatch"
        if self.pricing_snapshot is None:
            return None, "pricing_snapshot_unavailable"
        if not actual_service_tier or actual_service_tier == "auto":
            return None, "missing_actual_service_tier"
        allowed_tiers = set(allowed_actual_service_tiers or ())
        if requested_service_tier not in {None, "auto"}:
            allowed_tiers.add(requested_service_tier)
        if allowed_tiers and actual_service_tier not in allowed_tiers:
            return None, "actual_service_tier_mismatch"
        if not billing_scope:
            return None, "missing_billing_scope"
        if actual_billing_scope is not None and actual_billing_scope != billing_scope:
            return None, "billing_scope_mismatch"
        if currency != "USD" or (actual_currency is not None and actual_currency != currency):
            return None, "currency_mismatch"
        resolution = self.pricing_snapshot.resolve(provider, actual_model, service_tier=actual_service_tier,
            billing_scope=billing_scope, currency=currency)
        if resolution.status != "available" or resolution.rates is None:
            return None, "pricing_unavailable"
        try:
            cost = estimate_cost_decimal(
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                reasoning_tokens=usage["reasoning_tokens"],
                cached_input_tokens=usage["cached_input_tokens"],
                cache_write_tokens=usage["cache_write_tokens"],
                rates=resolution.rates,
            )
        except ValueError:
            return None, "pricing_breakdown_unavailable"
        return cost, "available"

    def _load_unlocked(self) -> dict[str, Any]:
        self._validate_pricing_context()
        try:
            state = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DispatchAccountingError("Dispatch journal is unreadable.") from exc
        if not isinstance(state, dict) or state.get("schema_version") != ACCOUNTING_SCHEMA_VERSION:
            raise DispatchAccountingError("Unsupported dispatch journal schema.")
        if (
            state.get("run_identity") != self.run_identity
            or state.get("run_identity_hash") != self.run_identity_hash
            or state.get("historical_incomplete") is not self.historical_incomplete
        ):
            raise DispatchAccountingError("Dispatch journal identity mismatch.")
        if state.get("pricing_snapshot") != self._pricing_metadata:
            raise DispatchAccountingError("Dispatch journal pricing identity mismatch.")
        if "pricing_catalog" in state:
            catalog = state["pricing_catalog"]
            try:
                actual_metadata = PricingSnapshot.from_mapping(catalog).metadata() if catalog is not None else None
            except (ValueError, TypeError, AttributeError) as exc:
                raise DispatchAccountingError("Saved pricing catalog is malformed.") from exc
            if actual_metadata != self._pricing_metadata:
                raise DispatchAccountingError("Saved pricing catalog identity mismatch.")
        if state.get("budget_context") != self.budget_identity:
            raise DispatchAccountingError("Dispatch journal hard-budget identity mismatch.")
        if state.get("fingerprint") != _state_fingerprint(state):
            raise DispatchAccountingError("Dispatch journal integrity check failed.")
        if not isinstance(state.get("events"), list):
            raise DispatchAccountingError("Dispatch journal events are malformed.")
        return state

    def _validate_pricing_context(self) -> None:
        if self.budget_context is not self._bound_budget_context:
            raise DispatchAccountingError("Immutable budget context changed in memory.")
        if self._pricing_context_missing and self.pricing_snapshot is None:
            return  # Historical metadata may be read; dispatch still requires its archive.
        current = self.pricing_snapshot.metadata() if self.pricing_snapshot else None
        if current != self._pricing_metadata:
            raise DispatchAccountingError("Immutable pricing context changed in memory.")

    def _append_begin_event(self, event: Mapping[str, Any], identifier: str) -> None:
        with _locked_path(self.lock_path):
            state = self._load_unlocked()
            if any(item.get("call_id") == identifier for item in state["events"]):
                raise DispatchAccountingError("Dispatch call_id already exists.")
            state["events"].append(dict(event))
            self._save_unlocked(state)

    def _save_unlocked(self, state: dict[str, Any]) -> None:
        if "pricing_catalog" not in state and not self._pricing_context_missing:
            state["pricing_catalog"] = self.pricing_snapshot.to_mapping() if self.pricing_snapshot else None
        state["updated_at"] = _now()
        state["fingerprint"] = _state_fingerprint(state)
        _atomic_json_write(self.journal_path, state)

    def _restore_saved_context(self) -> None:
        """Resume the run's frozen rates, never today's default price catalog."""
        try:
            state = json.loads(self.journal_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DispatchAccountingError("Dispatch journal is unreadable.") from exc
        if not isinstance(state, dict) or state.get("fingerprint") != _state_fingerprint(state):
            raise DispatchAccountingError("Dispatch journal integrity check failed.")
        saved = state.get("pricing_snapshot")
        candidates = (self.pricing_snapshot, *self._pricing_archives)
        self.pricing_snapshot = None
        self._pricing_metadata = saved
        if "pricing_catalog" in state:
            try:
                catalog = state["pricing_catalog"]
                self.pricing_snapshot = PricingSnapshot.from_mapping(catalog) if catalog is not None else None
            except (ValueError, TypeError, AttributeError) as exc:
                raise DispatchAccountingError("Saved pricing catalog is malformed.") from exc
            restored = self.pricing_snapshot.metadata() if self.pricing_snapshot else None
            if restored != saved:
                raise DispatchAccountingError("Saved pricing catalog identity mismatch.")
        elif saved is not None:
            self.pricing_snapshot = next((item for item in candidates if item is not None and item.metadata() == saved), None)
            self._pricing_context_missing = self.pricing_snapshot is None
        if "dispatch_limits" in state and not self._amendment_bound_limits:
            self.dispatch_limits = _normalize_limits(state["dispatch_limits"])


class MemoryDispatchAccounting:
    """Per-client fallback accounting for calls made outside a workflow run."""

    hard_budget = False
    can_retry = True

    def __init__(
        self,
        *,
        pricing_snapshot: PricingSnapshot | Mapping[str, Any] | None = None,
    ) -> None:
        self.pricing_snapshot = _coerce_snapshot(pricing_snapshot)
        self._records = DispatchAccounting.__new__(DispatchAccounting)
        self._events: list[dict[str, Any]] = []
        self._lock = threading.RLock()

    def request_limits(self, provider: str, purpose: str, requested_model: str) -> Mapping[str, Any]:
        del provider, purpose, requested_model
        return MappingProxyType({})

    def verify_dispatch(self, **kwargs: Any) -> None:
        del kwargs

    def recheck_dispatch(self, reservation_id: str | None, **kwargs: Any) -> None:
        del reservation_id, kwargs

    def begin(self, **kwargs: Any) -> DispatchTicket:
        binding = current_accounting_binding()
        purpose = kwargs.get("purpose") or (binding.purpose if binding else None) or "unknown"
        page = kwargs.get("page_number")
        if page is None and binding is not None:
            page = binding.page_number
        ticket = DispatchTicket(
            call_id=_identifier(kwargs.get("call_id") or uuid4().hex, "call_id"),
            provider=_identifier(kwargs.get("provider"), "provider").lower(),
            requested_model=_identifier(kwargs.get("requested_model"), "requested_model"),
            purpose=_identifier(purpose, "purpose"),
            page_number=page,
            request_hash=_request_hash(kwargs.get("request_hash")),
            attempt=_positive_int(kwargs.get("attempt", 1), "attempt"),
        )
        event = {
            "event": "begin",
            "call_id": ticket.call_id,
            "provider": ticket.provider,
            "requested_model": ticket.requested_model,
            "requested_service_tier": _requested_tier(ticket.provider, kwargs.get("requested_service_tier")),
            "billing_scope": kwargs.get("billing_scope"),
            "currency": kwargs.get("currency", "USD"),
            "effort": str(kwargs.get("effort") or ""),
            "purpose": ticket.purpose,
            "page_number": ticket.page_number,
            "request_hash": ticket.request_hash,
            "bounds": _safe_mapping(kwargs.get("bounds") or {}, "dispatch bounds"),
            "attempt": ticket.attempt,
            "ceiling_usd": None,
            "at": _now(),
        }
        with self._lock:
            if any(item.get("call_id") == ticket.call_id for item in self._events):
                raise DispatchAccountingError("Dispatch call_id already exists.")
            self._events.append(event)
        return ticket

    def finish(self, ticket: DispatchTicket, **kwargs: Any) -> Mapping[str, Any]:
        outcome = kwargs.get("outcome")
        usage = _zero_usage() if outcome == "not_dispatched" else normalize_usage(
            kwargs.get("usage"),
            provider=ticket.provider,
        )
        event = {
            "event": "finish",
            "call_id": ticket.call_id,
            "outcome": outcome,
            "usage": usage,
            "response_id": kwargs.get("response_id"),
            "actual_model": kwargs.get("actual_model"),
            "actual_service_tier": kwargs.get("actual_service_tier"),
            "actual_billing_scope": kwargs.get("actual_billing_scope"),
            "currency": kwargs.get("currency"),
            "error_code": kwargs.get("error_code"),
            "cost_usd": None,
            "cost_status": "not_dispatched" if outcome == "not_dispatched" else (
                f"{usage['usage_status']}_usage"
                if usage["usage_status"] != "available"
                else "pricing_snapshot_unavailable"
            ),
            "at": _now(),
        }
        with self._lock:
            if _find_begin(self._events, ticket.call_id) is None:
                raise DispatchAccountingError("Dispatch ticket is unknown.")
            existing = _find_finish(self._events, ticket.call_id)
            if existing is not None:
                return _json_copy(existing)
            self._events.append(event)
        return _json_copy(event)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return _summarize(
                list(self._events),
                historical_incomplete=False,
                pricing_snapshot=(
                    self.pricing_snapshot.metadata() if self.pricing_snapshot else None
                ),
            )


def _summarize(
    events: Sequence[Mapping[str, Any]],
    *,
    historical_incomplete: bool,
    pricing_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    begins: dict[str, Mapping[str, Any]] = {}
    finishes: dict[str, Mapping[str, Any]] = {}
    duplicate_count = 0
    conflict_count = 0
    for event in events:
        call_id = str(event.get("call_id") or "")
        target = begins if event.get("event") == "begin" else finishes
        if not call_id or event.get("event") not in {"begin", "finish"}:
            conflict_count += 1
            continue
        if call_id in target:
            duplicate_count += 1
            if dict(target[call_id]) != dict(event):
                conflict_count += 1
            continue
        target[call_id] = event
    unresolved = [call_id for call_id in begins if call_id not in finishes]
    orphan_finishes = [call_id for call_id in finishes if call_id not in begins]
    conflict_count += len(orphan_finishes)
    totals = {field: 0 for field in TOKEN_FIELDS}
    known_cost = Decimal(0)
    missing_usage_count = 0
    invalid_usage_count = 0
    unknown_cost_count = 0
    budget_incomplete_count = 0
    billing_identity_incomplete_count = 0
    not_dispatched_count = 0
    by_purpose: dict[str, dict[str, Any]] = {}
    by_outcome: dict[str, int] = {}
    for call_id, begin in begins.items():
        finish = finishes.get(call_id)
        purpose = str(begin.get("purpose") or "unknown")
        bucket = by_purpose.setdefault(
            purpose,
            {
                "attempt_count": 0,
                "provider_dispatch_count": 0,
                "known_cost_usd": Decimal(0),
                "unknown_cost_count": 0,
                "budget_incomplete_count": 0,
            },
        )
        bucket["attempt_count"] += 1
        if finish is None:
            bucket["unknown_cost_count"] += 1
            unknown_cost_count += 1
            continue
        outcome = str(finish.get("outcome") or "unknown")
        by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
        if outcome == "not_dispatched":
            not_dispatched_count += 1
        else:
            bucket["provider_dispatch_count"] += 1
        stored_usage = finish.get("usage")
        usage = (
            dict(stored_usage)
            if isinstance(stored_usage, Mapping)
            and stored_usage.get("usage_status") in {"available", "missing", "invalid"}
            else normalize_usage(
                stored_usage,
                provider=str(begin.get("provider") or "openai"),
            )
        )
        if usage["usage_status"] == "missing":
            missing_usage_count += 1
        elif usage["usage_status"] == "invalid":
            invalid_usage_count += 1
        else:
            for field in TOKEN_FIELDS:
                totals[field] += int(usage[field] or 0)
        cost = _optional_decimal(finish.get("cost_usd"))
        if cost is None:
            unknown_cost_count += 1
            bucket["unknown_cost_count"] += 1
        else:
            known_cost += cost
            bucket["known_cost_usd"] += cost
        if finish.get("budget_status") not in {None, "finalized"} or finish.get(
            "budget_blocked_reason"
        ):
            budget_incomplete_count += 1
            bucket["budget_incomplete_count"] += 1
        if outcome != "not_dispatched" and (
            not finish.get("actual_service_tier")
            or finish.get("actual_service_tier") == "auto"
            or not finish.get("actual_billing_scope")
            or finish.get("currency") != "USD"
        ):
            # Keep saved numeric evidence as recorded, without retroactively
            # certifying old model-only billing as complete or repricing it.
            billing_identity_incomplete_count += 1
    complete = (
        not historical_incomplete
        and not unresolved
        and not orphan_finishes
        and conflict_count == 0
        and unknown_cost_count == 0
        and budget_incomplete_count == 0
        and billing_identity_incomplete_count == 0
    )
    serialized_by_purpose: dict[str, dict[str, Any]] = {}
    for purpose, bucket in by_purpose.items():
        known = bucket["known_cost_usd"]
        serialized_by_purpose[purpose] = {
            "attempt_count": bucket["attempt_count"],
            "provider_dispatch_count": bucket["provider_dispatch_count"],
            "known_cost_usd": float(known),
            "cost_usd": float(known) if bucket["unknown_cost_count"] == 0 else None,
            "unknown_cost_count": bucket["unknown_cost_count"],
            "budget_incomplete_count": bucket["budget_incomplete_count"],
        }
    return {
        "accounting_version": ACCOUNTING_SCHEMA_VERSION,
        "pricing_snapshot": _json_copy(pricing_snapshot) if pricing_snapshot else None,
        "coverage_status": "complete" if complete else "incomplete",
        "historical_incomplete": historical_incomplete,
        "attempt_count": len(begins),
        "call_count": len(begins),
        "provider_dispatch_count": len(begins) - not_dispatched_count,
        "not_dispatched_count": not_dispatched_count,
        "in_flight_count": len(unresolved),
        "known_cost_usd": float(known_cost),
        "cost_usd": float(known_cost) if complete else None,
        "unknown_cost_count": unknown_cost_count,
        "budget_incomplete_count": budget_incomplete_count,
        "billing_identity_incomplete_count": billing_identity_incomplete_count,
        "missing_usage_count": missing_usage_count,
        "invalid_usage_count": invalid_usage_count,
        "duplicate_event_count": duplicate_count,
        "conflicting_event_count": conflict_count,
        "totals": totals,
        "by_purpose": serialized_by_purpose,
        "by_outcome": by_outcome,
    }


def _normalize_gemini_usage_input(usage: Any) -> Any:
    if usage is None:
        return None
    prompt = _first_field(usage, "promptTokenCount", "prompt_token_count")
    candidates = _first_field(usage, "candidatesTokenCount", "candidates_token_count")
    thoughts = _first_field(usage, "thoughtsTokenCount", "thoughts_token_count")
    cached = _first_field(usage, "cachedContentTokenCount", "cached_content_token_count")
    total = _first_field(usage, "totalTokenCount", "total_token_count")
    output = None
    if candidates is not None:
        if _token_count(candidates) is not None and (
            thoughts is None or _token_count(thoughts) is not None
        ):
            output = candidates + (thoughts or 0)
        else:
            output = candidates
    return {
        "input_tokens": prompt,
        "output_tokens": output,
        "total_tokens": total,
        "reasoning_tokens": thoughts,
        "cached_input_tokens": cached,
        "cache_write_tokens": 0,
    }


def _first_field(value: Any, *names: str) -> Any:
    for name in names:
        found = _field(value, name)
        if found is not None:
            return found
    return None


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default) if value is not None else default


def _token_count(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _zero_usage() -> dict[str, Any]:
    return {
        **{field: 0 for field in TOKEN_FIELDS},
        "usage_status": "available",
        "total_tokens_source": "proved_not_dispatched",
        "reasoning_included_in_output": True,
    }


def _coerce_snapshot(
    value: PricingSnapshot | Mapping[str, Any] | None,
) -> PricingSnapshot | None:
    if value is None or isinstance(value, PricingSnapshot):
        return value
    if isinstance(value, Mapping):
        return PricingSnapshot.from_mapping(value)
    raise DispatchAccountingError("pricing_snapshot must be a PricingSnapshot or mapping.")


def _normalize_limits(
    value: Mapping[str, Mapping[str, Any]] | None,
) -> Mapping[str, Mapping[str, Any]]:
    if value is None:
        return MappingProxyType({})
    normalized: dict[str, Mapping[str, Any]] = {}
    for raw_key, raw_limits in value.items():
        key = str(raw_key or "").strip()
        if ":" not in key:
            raise DispatchAccountingError("Dispatch-limit keys must use provider:purpose.")
        provider, purpose = key.split(":", 1)
        if purpose.startswith("*:"):
            purpose = f"*:{_identifier(purpose[2:], 'requested_model')}"
        else:
            purpose = _identifier(purpose, "purpose")
        safe_key = f"{_identifier(provider, 'provider').lower()}:{purpose}"
        normalized[safe_key] = MappingProxyType(
            _safe_mapping(dict(raw_limits), f"dispatch limits for {safe_key}")
        )
    return MappingProxyType(normalized)


def _required_hard_limits(limits: Mapping[str, Any]) -> None:
    for key in ("max_input_tokens", "max_output_tokens"):
        if type(limits.get(key)) is not int or limits[key] <= 0:
            raise DispatchAccountingError(
                f"Hard-budget dispatch requires a positive {key}."
            )
    if limits.get("image_bound_verified") is True:
        if type(limits.get("max_image_input_tokens")) is not int or limits[
            "max_image_input_tokens"
        ] <= 0:
            raise DispatchAccountingError("Verified image bounds require a positive token maximum.")
    if "ceiling_usd" in limits:
        _positive_decimal(limits["ceiling_usd"], "ceiling_usd")


def _validate_bounds_match_limits(
    bounds: Mapping[str, Any],
    limits: Mapping[str, Any],
) -> None:
    for key, configured in limits.items():
        observed = bounds.get(key)
        if key == "max_output_tokens":
            if type(observed) is not int or observed <= 0 or observed > configured:
                raise DispatchAccountingError(
                    "Dispatch bounds exceed the configured max_output_tokens."
                )
        elif observed != configured:
            raise DispatchAccountingError(
                f"Dispatch bounds differ from the configured {key}."
            )
    if bounds.get("image_count", 0):
        if limits.get("image_bound_verified") is not True:
            raise DispatchAccountingError("Image input has no verified hard-budget bound.")
        if bounds.get("max_image_input_tokens") != limits.get("max_image_input_tokens"):
            raise DispatchAccountingError("Image input bound differs from configured limits.")


def _ceiling_for(
    *,
    pricing_snapshot: PricingSnapshot | None,
    provider: str,
    model: str,
    bounds: Mapping[str, Any],
    hard: bool,
) -> Decimal | None:
    explicit = bounds.get("ceiling_usd")
    explicit_decimal = (
        _positive_decimal(explicit, "ceiling_usd") if explicit is not None else None
    )
    if pricing_snapshot is None:
        return explicit_decimal if not hard else None
    resolutions = _reservation_resolutions(pricing_snapshot, provider, model, bounds)
    if not resolutions:
        return explicit_decimal if not hard else None
    maximum_input = bounds.get("max_input_tokens")
    maximum_output = bounds.get("max_output_tokens")
    if type(maximum_input) is not int or maximum_input <= 0:
        return explicit_decimal if not hard else None
    if type(maximum_output) is not int or maximum_output <= 0:
        return explicit_decimal if not hard else None
    rates = [item.rates for item in resolutions if item.rates is not None]
    input_rates = [
        Decimal(str(rate))
        for item in rates
        for rate in (
            item.input_per_1m,
            item.cached_input_per_1m,
            item.cache_write_per_1m,
        )
        if rate is not None
    ]
    output_rates = [Decimal(str(item.output_per_1m)) for item in rates]
    calculated = (
        Decimal(maximum_input) * max(input_rates)
        + Decimal(maximum_output) * max(output_rates)
    ) / Decimal(1_000_000)
    calculated = calculated.quantize(Decimal("0.000000001"), rounding=ROUND_CEILING)
    if explicit_decimal is not None and explicit_decimal < calculated:
        raise DispatchAccountingError(
            "Declared dispatch ceiling is below the verified token-bound price."
        )
    return explicit_decimal if explicit_decimal is not None else calculated


def _requested_tier(provider: str, tier: str | None) -> str | None:
    if tier is not None:
        return _identifier(tier, "requested_service_tier")
    return "auto" if provider.lower() == "openai" else None


def _reservation_resolutions(
    snapshot: PricingSnapshot, provider: str, model: str, bounds: Mapping[str, Any],
) -> list[Any]:
    """The finite approved cross-product must be fully priced before a hold."""
    models = bounds.get("allowed_actual_models", [])
    tiers = bounds.get("allowed_actual_service_tiers", [])
    if not isinstance(models, list) or not isinstance(tiers, list):
        raise DispatchAccountingError("Allowed actual models and service tiers must be lists.")
    if len(models) > 32 or len(tiers) > 16 or len(set(models)) != len(models) or len(set(tiers)) != len(tiers):
        raise DispatchAccountingError("Approved billing identities must be finite and unique.")
    for value in models:
        _identifier(value, "allowed_actual_model")
    for value in tiers:
        _identifier(value, "allowed_actual_service_tier")
    requested = _requested_tier(provider, bounds.get("requested_service_tier"))
    if requested not in {None, "auto"}:
        tiers = list(dict.fromkeys([requested, *tiers]))
    scope = bounds.get("billing_scope")
    currency = bounds.get("currency", "USD")
    if not tiers or "auto" in tiers or not scope or currency != "USD":
        return []
    _identifier(scope, "billing_scope")
    resolutions = [snapshot.resolve(provider, identifier, service_tier=tier,
        billing_scope=scope, currency=currency)
        for identifier in dict.fromkeys([model, *models]) for tier in tiers]
    if any(item.status != "available" or item.rates is None for item in resolutions):
        return []
    return resolutions


def _budget_identity(budget: Any | None) -> dict[str, Any]:
    if budget is None:
        return {"hard": False}
    identity = getattr(budget, "binding_identity", None)
    if identity is None:
        raw_identity = getattr(budget, "identity", None)
        identity = {
            "kind": f"{type(budget).__module__}.{type(budget).__name__}",
            "cap_usd": str(getattr(budget, "cap_usd", "")),
            "identity_hash": fingerprint(raw_identity) if raw_identity is not None else None,
        }
    return {"hard": bool(getattr(budget, "hard", True)), **_safe_mapping(identity, "budget identity")}


def _reservation_metadata(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": event["provider"],
        "requested_model": event["requested_model"],
        "requested_service_tier": event["requested_service_tier"],
        "billing_scope": event["billing_scope"],
        "currency": event["currency"],
        "route": event["route"],
        "base_url": event["base_url"],
        "authorization_sha256": event["authorization_sha256"],
        "effort": event["effort"],
        "purpose": event["purpose"],
        "page_number": event["page_number"],
        "request_hash": event["request_hash"],
        "bounds": event["bounds"],
        "attempt": event["attempt"],
        "run_instance": event["instance_id"],
    }


def _find_begin(
    events: Sequence[Mapping[str, Any]],
    call_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (
            event
            for event in events
            if event.get("event") == "begin" and event.get("call_id") == call_id
        ),
        None,
    )


def _find_finish(
    events: Sequence[Mapping[str, Any]],
    call_id: str,
) -> Mapping[str, Any] | None:
    return next(
        (
            event
            for event in events
            if event.get("event") == "finish" and event.get("call_id") == call_id
        ),
        None,
    )


def _has_finish(events: Sequence[Mapping[str, Any]], call_id: Any) -> bool:
    return _find_finish(events, str(call_id or "")) is not None


def _completion_equivalent(
    existing: Mapping[str, Any],
    proposed: Mapping[str, Any],
) -> bool:
    ignored = {"at", "budget_status", "budget_blocked_reason"}
    return (
        {key: value for key, value in existing.items() if key not in ignored}
        == {key: value for key, value in proposed.items() if key not in ignored}
    )


def _request_hash(value: Any) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise DispatchAccountingError("request_hash must be a lowercase SHA-256 digest.")
    return value


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise DispatchAccountingError(f"{label} must be a positive integer.")
    return value


def _identifier(value: Any, label: str) -> str:
    candidate = str(value or "")
    if (
        not candidate
        or len(candidate) > 200
        or any(not (character.isalnum() or character in "._:-") for character in candidate)
    ):
        raise DispatchAccountingError(f"{label} must be a concise safe identifier.")
    return candidate


def _bounded_text(value: Any, label: str) -> str:
    candidate = str(value or "")
    if not candidate or len(candidate) > 512 or "\n" in candidate or "\r" in candidate:
        raise DispatchAccountingError(f"{label} must be concise single-line text.")
    return candidate


def _safe_endpoint(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"https", "http"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            return None
        return _bounded_text(urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")), "base_url")
    except (TypeError, ValueError):
        return None


def _safe_mapping(value: Mapping[str, Any], label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DispatchAccountingError(f"{label} must be a mapping.")
    try:
        result = _json_copy(value)
    except (TypeError, ValueError) as exc:
        raise DispatchAccountingError(f"{label} must contain finite JSON values.") from exc
    _validate_safe_json(result, label)
    return result


def _validate_safe_json(value: Any, label: str) -> None:
    forbidden = {"prompt", "source_text", "document_text", "api_key", "secret", "content"}
    if isinstance(value, dict):
        if len(value) > 100:
            raise DispatchAccountingError(f"{label} is too large.")
        for key, child in value.items():
            if not isinstance(key, str) or key.lower() in forbidden:
                raise DispatchAccountingError(f"{label} contains a forbidden field.")
            _validate_safe_json(child, label)
    elif isinstance(value, list):
        if len(value) > 100:
            raise DispatchAccountingError(f"{label} is too large.")
        for child in value:
            _validate_safe_json(child, label)
    elif isinstance(value, str):
        if len(value) > 512 or "\n" in value or "\r" in value:
            raise DispatchAccountingError(f"{label} contains unsafe text.")
    elif value is not None and not isinstance(value, (int, float, bool)):
        raise DispatchAccountingError(f"{label} contains unsupported values.")
    elif isinstance(value, float) and not math.isfinite(value):
        raise DispatchAccountingError(f"{label} contains nonfinite values.")


def _positive_decimal(value: Any, label: str) -> Decimal:
    try:
        result = money(value)
    except Exception as exc:
        raise DispatchAccountingError(f"{label} must be a nonnegative decimal.") from exc
    if result <= 0:
        raise DispatchAccountingError(f"{label} must be positive.")
    return result


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not result.is_finite() or result < 0:
        return None
    return result


def _decimal_text(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _state_fingerprint(state: Mapping[str, Any]) -> str:
    return fingerprint({key: value for key, value in state.items() if key != "fingerprint"})


def _fingerprint(value: Any) -> str:
    return fingerprint(value)


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_json(path, payload)


def _process_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _PROCESS_LOCKS_GUARD:
        return _PROCESS_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _locked_path(path: Path) -> Iterator[None]:
    with _process_lock(path):
        with locked(path):
            yield
