"""Strict adapter from dispatch accounting to the singular legacy acceptance ledger.

The adapter never creates, resets, replaces or releases an allowance.  It opens
an existing hash-pinned ledger only through an independently fingerprinted
amendment and appends sanitized reservations for that amendment.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Callable, Mapping

from .budget_reservations import BudgetError, atomic_json, fingerprint, locked, money
from .cost_guardrails import PricingSnapshot
from .acceptance_provenance import request_fingerprint, verify_physical_provenance, verify_pending_correction, verify_runtime_context


ACCEPTANCE_AMENDMENT_VERSION = 2
_SHA256 = re.compile(r"[a-f0-9]{64}\Z")
_STABLE_RUN_KEYS = (
    "source_sha256",
    "context_hash",
    "language",
    "protocol",
    "model",
    "protocol_identity",
    "selection",
)


class AcceptanceBudgetError(BudgetError):
    """The protected acceptance allowance cannot safely authorize a call."""


class LegacyAcceptanceBudget:
    """Append current reservations to one existing legacy budget ledger."""

    hard = True

    def __init__(
        self,
        ledger_path: Path,
        *,
        amendment_path: Path,
        expected_amendment_sha256: str,
        run_identity: Mapping[str, Any],
        execution_identity: Mapping[str, Any],
        pricing_snapshot: PricingSnapshot | Mapping[str, Any],
    ) -> None:
        self.path = Path(ledger_path).resolve()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.amendment_path = Path(amendment_path).resolve()
        if _SHA256.fullmatch(str(expected_amendment_sha256 or "")) is None:
            raise AcceptanceBudgetError("An externally approved amendment SHA-256 is required.")
        self.expected_amendment_sha256 = expected_amendment_sha256
        if not self.path.is_file():
            raise AcceptanceBudgetError(
                "The existing acceptance ledger is required; no allowance was created."
            )
        if not self.amendment_path.is_file():
            raise AcceptanceBudgetError("The approved acceptance amendment is required.")
        self.run_identity = _json_mapping(run_identity, "run identity")
        self.execution_identity = _json_mapping(execution_identity, "execution identity")
        self.pricing_snapshot = (
            pricing_snapshot
            if isinstance(pricing_snapshot, PricingSnapshot)
            else PricingSnapshot.from_mapping(pricing_snapshot)
        )
        self.amendment = self._load_amendment()
        self.dispatch_enabled = self.amendment["schema_version"] == 2
        self.amendment_fingerprint = self.amendment["fingerprint"]
        self.campaign_id = self.amendment["campaign_id"]
        self.cap_usd = money(self.amendment["ledger"]["cap_usd"])
        self.campaign_cap_usd = money(self.amendment["campaign_cap_usd"])
        self.case = self.amendment["case"]
        self.continuation_identity = fingerprint({
            "campaign_id": self.campaign_id, "case_id": self.case["case_id"],
            "source_sha256": self.run_identity["source_sha256"],
            "full_case_pages": list(range(self.run_identity["selection"][0], self.run_identity["selection"][1] + 1)),
        })
        self.dispatch_limits = MappingProxyType(
            {
                key: MappingProxyType(deepcopy(value))
                for key, value in self.amendment["dispatch_limits"].items()
            }
        )
        self._approved_state_fingerprint = fingerprint(self.amendment)
        self._approved_limits_fingerprint = fingerprint({key: dict(value) for key, value in self.dispatch_limits.items()})
        self.binding_identity = {
            "kind": "legacy_acceptance_v1",
            "benchmark_id": self.amendment["ledger"]["benchmark_id"],
            "manifest_fingerprint": self.amendment["ledger"]["manifest_fingerprint"],
            "cap_usd": str(self.cap_usd),
            "campaign_cap_usd": str(self.campaign_cap_usd),
            "campaign_id": self.campaign_id,
            "case_id": self.case["case_id"],
            "case_ceiling_usd": self.case["ceiling_usd"],
            "amendment_fingerprint": self.amendment_fingerprint,
            "stable_run_identity_hash": fingerprint(_stable_run_identity(self.run_identity)),
            "execution_identity_hash": fingerprint(self.execution_identity),
            "pricing_snapshot": self.pricing_snapshot.metadata(),
        }
        if self.dispatch_enabled:
            self.binding_identity.update(kind="legacy_acceptance_v2", case_max_calls=self.case["max_calls"])
            self.binding_identity.pop("amendment_fingerprint")
        self._verified_dispatch: dict[str, Any] | None = None
        self._owner = hashlib.sha256(
            f"{id(self)}:{self.amendment_fingerprint}".encode("utf-8")
        ).hexdigest()
        self._runtime_context: tuple[Any, Any] | None = None
        self._frozen_controls = fingerprint(self._control_identity())
        with locked(self.lock_path):
            self._load_ledger_unlocked()

    @property
    def blocked(self) -> bool:
        return self.status()["blocked_reason"] is not None

    @property
    def has_uncertain(self) -> bool:
        return money(self.status()["held_usd"]) > 0

    def reserve(
        self,
        reservation_id: str,
        ceiling_usd: Any,
        metadata: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        identifier = _identifier(reservation_id, "reservation_id")
        ceiling = money(ceiling_usd)
        details = _json_mapping(metadata, "reservation metadata")
        limit = self._validate_dispatch(details, ceiling)
        if not self.dispatch_enabled:
            raise AcceptanceBudgetError("Legacy amendments are read-only; physical v2 approval is required.")
        proof = self._verified_dispatch
        self._verified_dispatch = None
        if proof is None or any(details.get(key) != value for key, value in proof.items()):
            raise AcceptanceBudgetError("Final dispatch has no matching one-use physical provenance proof.")
        # Rehash again after the caller's check and immediately before reservation.
        self._verify_physical()
        with locked(self.lock_path):
            state = self._load_ledger_unlocked()
            if state.get("blocked_reason"):
                raise AcceptanceBudgetError(
                    "The acceptance ledger is blocked pending manual reconciliation."
                )
            if any(row.get("status") != "finalized" for row in state["reservations"].values()):
                raise AcceptanceBudgetError(
                    "An unresolved acceptance dispatch blocks another reservation."
                )
            if identifier in state["reservations"]:
                raise AcceptanceBudgetError(
                    "A duplicate reservation cannot authorize another dispatch."
                )
            if _committed(state) + ceiling > self.cap_usd:
                raise AcceptanceBudgetError(
                    "The original lifetime allowance cannot fit this dispatch ceiling."
                )
            if self._campaign_committed(state) + ceiling > self.campaign_cap_usd:
                raise AcceptanceBudgetError(
                    "The approved campaign ceiling cannot fit this dispatch."
                )
            current_rows = [
                row
                for row in state["reservations"].values()
                if _is_case_row(row, self.campaign_id, self.case["case_id"])
            ]
            if len(current_rows) >= self.case["max_calls"]:
                raise AcceptanceBudgetError("The approved case call limit is exhausted.")
            if self._case_committed(state) + ceiling > money(self.case["ceiling_usd"]):
                raise AcceptanceBudgetError("The approved per-case ceiling cannot fit this dispatch.")
            matching_purpose = [
                row
                for row in current_rows
                if row["execution"].get("provider") == details["provider"]
                and row["execution"].get("purpose") == details["purpose"]
            ]
            amendment_purpose = [row for row in matching_purpose if _is_current_row(row, self.amendment_fingerprint)]
            if len(amendment_purpose) >= limit["max_calls"]:
                raise AcceptanceBudgetError("The approved purpose call limit is exhausted.")
            matching_page = [
                row
                for row in matching_purpose
                if row["execution"].get("page_number") == details.get("page_number")
            ]
            if len(matching_page) >= limit["max_calls_per_page"]:
                raise AcceptanceBudgetError("The approved page call limit is exhausted.")
            if details["attempt"] != len(matching_page) + 1:
                raise AcceptanceBudgetError(
                    "Dispatch attempt is not the next approved page/purpose sequence."
                )
            now = datetime.now().astimezone().isoformat()
            execution = {
                "policy": "structured_activation_acceptance_v2",
                "campaign_id": self.campaign_id,
                "case_id": self.case["case_id"],
                "acceptance_amendment_fingerprint": self.amendment_fingerprint,
                "authorization_sha256": self.expected_amendment_sha256,
                "run_identity_hash": fingerprint(self.run_identity),
                "stable_run_identity_hash": fingerprint(_stable_run_identity(self.run_identity)),
                "execution_identity_hash": fingerprint(self.execution_identity),
                "provider": details["provider"],
                "requested_model": details["requested_model"],
                "effort": details.get("effort", ""),
                "purpose": details["purpose"],
                "page_number": details.get("page_number"),
                "request_hash": details["request_hash"],
                "attempt": details["attempt"],
                "limit_id": limit.get("limit_id"),
                "route": details.get("route"),
                "requested_service_tier": details.get("requested_service_tier"),
                "billing_scope": details.get("billing_scope"),
                "currency": details.get("currency"),
                "base_url": details.get("base_url"),
            }
            row = {
                "purpose": details["purpose"],
                "candidate_id": None,
                "execution": execution,
                "reserved_usd": str(ceiling),
                "actual_usd": None,
                "status": "reserved",
                "owner": self._owner,
                "created_at": now,
            }
            state["reservations"][identifier] = row
            self._append_authorization(state)
            self._save_ledger_unlocked(state)
            return {"reservation_id": identifier, **deepcopy(row)}

    def finalize(
        self,
        reservation_id: str,
        actual_usd: Any,
        metadata: Mapping[str, Any],
        block_reason: str | None = None,
    ) -> Mapping[str, Any]:
        identifier = _identifier(reservation_id, "reservation_id")
        actual = None if actual_usd is None else money(actual_usd)
        evidence = _json_mapping(metadata, "reconciliation metadata")
        reason = _identifier(block_reason, "block_reason") if block_reason else None
        with locked(self.lock_path):
            state = self._load_ledger_unlocked()
            row = state["reservations"].get(identifier)
            if (
                not isinstance(row, dict)
                or not _is_current_row(row, self.amendment_fingerprint)
                or row.get("status") != "reserved"
                or row.get("owner") != self._owner
            ):
                raise AcceptanceBudgetError(
                    "Only this adapter's unresolved reservation can be reconciled."
                )
            row["evidence"] = evidence
            ceiling = money(row["reserved_usd"])
            if actual is not None and actual > ceiling:
                row["observed_overage_usd"] = str(actual)
                reason = "reservation_ceiling_exceeded"
            if actual is None or reason:
                row["status"] = "uncertain"
                state["blocked_reason"] = reason or "unknown_provider_cost"
            else:
                row.update(
                    status="finalized",
                    actual_usd=str(actual),
                    finalized_at=datetime.now().astimezone().isoformat(),
                )
            self._save_ledger_unlocked(state)
            return {
                "reservation_id": identifier,
                **deepcopy(row),
                "blocked_reason": state.get("blocked_reason"),
            }

    def status(self) -> Mapping[str, Any]:
        with locked(self.lock_path):
            state = self._load_ledger_unlocked()
            known = sum(
                (
                    money(row["actual_usd"])
                    for row in state["reservations"].values()
                    if row["status"] == "finalized"
                ),
                Decimal(0),
            )
            committed = _committed(state)
            held = committed - known
            unresolved = any(
                row["status"] != "finalized" for row in state["reservations"].values()
            )
            blocked_reason = state.get("blocked_reason") or (
                "unresolved_dispatch" if unresolved else None
            )
            return {
                "benchmark_id": state["benchmark_id"],
                "cap_usd": str(self.cap_usd),
                "campaign_cap_usd": str(self.campaign_cap_usd),
                "known_spend_usd": str(known),
                "held_usd": str(held),
                "remaining_usd": str(
                    Decimal(0) if blocked_reason else self.cap_usd - committed
                ),
                "attempts": len(state["reservations"]),
                "blocked_reason": blocked_reason,
                "amendment_fingerprint": self.amendment_fingerprint,
            }

    def _load_amendment(self) -> dict[str, Any]:
        try:
            raw = self.amendment_path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != self.expected_amendment_sha256:
                raise AcceptanceBudgetError(
                    "Acceptance amendment differs from the externally approved SHA-256."
                )
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceBudgetError("Acceptance amendment is unreadable.") from exc
        if not isinstance(value, dict) or value.get("schema_version") not in {1, ACCEPTANCE_AMENDMENT_VERSION}:
            raise AcceptanceBudgetError("Unsupported acceptance amendment.")
        expected = fingerprint({key: item for key, item in value.items() if key != "fingerprint"})
        if value.get("fingerprint") != expected:
            raise AcceptanceBudgetError("Acceptance amendment integrity check failed.")
        ledger = value.get("ledger")
        limits = value.get("dispatch_limits")
        if not isinstance(ledger, dict) or not isinstance(limits, dict) or not limits:
            raise AcceptanceBudgetError("Acceptance amendment is incomplete.")
        for key in (
            "benchmark_id",
            "manifest_fingerprint",
            "cap_usd",
            "resolved_path",
            "initial_sha256",
            "base_reservations_fingerprint",
            "base_static_fingerprint",
        ):
            if not isinstance(ledger.get(key), str) or not ledger[key]:
                raise AcceptanceBudgetError(f"Acceptance amendment ledger.{key} is required.")
        for digest_key in (
            "manifest_fingerprint",
            "initial_sha256",
            "base_reservations_fingerprint",
            "base_static_fingerprint",
        ):
            if _SHA256.fullmatch(ledger[digest_key]) is None:
                raise AcceptanceBudgetError(
                    f"Acceptance amendment ledger.{digest_key} must be SHA-256."
                )
        if money(ledger["cap_usd"]) != Decimal("10"):
            raise AcceptanceBudgetError(
                "The amendment must preserve the original USD 10 lifetime cap."
            )
        if _normalized_path(ledger["resolved_path"]) != _normalized_path(str(self.path)):
            raise AcceptanceBudgetError(
                "Acceptance amendment is bound to a different ledger path."
            )
        campaign_cap = money(value.get("campaign_cap_usd"))
        if campaign_cap <= 0 or campaign_cap > money(ledger["cap_usd"]):
            raise AcceptanceBudgetError("Acceptance campaign cap is invalid.")
        value["campaign_id"] = _identifier(value.get("campaign_id"), "campaign_id")
        stable_identity = value.get("stable_run_identity")
        if stable_identity != _stable_run_identity(self.run_identity):
            raise AcceptanceBudgetError("Acceptance amendment belongs to another stable run identity.")
        if value.get("execution_identity") != self.execution_identity:
            raise AcceptanceBudgetError("Acceptance amendment execution identity mismatch.")
        for digest_key in ("code_manifest_sha256", "config_manifest_sha256", "preferences_sha256"):
            digest = self.execution_identity.get(digest_key)
            if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
                raise AcceptanceBudgetError(
                    f"Execution identity requires {digest_key}."
                )
        expected_pricing = value.get("pricing_snapshot")
        if expected_pricing != self.pricing_snapshot.metadata():
            raise AcceptanceBudgetError("Acceptance amendment pricing identity mismatch.")
        if value.get("protocol") != "legal_blocks_v2":
            raise AcceptanceBudgetError("Acceptance amendment must bind legal_blocks_v2.")
        case = value.get("case")
        if not isinstance(case, dict):
            raise AcceptanceBudgetError("Acceptance amendment case bounds are required.")
        case_id = _identifier(case.get("case_id"), "case_id")
        case_max_calls = case.get("max_calls")
        if type(case_max_calls) is not int or case_max_calls <= 0:
            raise AcceptanceBudgetError("Acceptance case max_calls must be positive.")
        case_ceiling = money(case.get("ceiling_usd"))
        if case_ceiling <= 0 or case_ceiling > campaign_cap:
            raise AcceptanceBudgetError("Acceptance per-case ceiling is invalid.")
        value["case"] = {
            "case_id": case_id,
            "max_calls": case_max_calls,
            "ceiling_usd": str(case_ceiling),
        }
        try:
            approved_at = datetime.fromisoformat(str(value.get("approved_at") or ""))
        except ValueError as exc:
            raise AcceptanceBudgetError("Acceptance amendment approval time is invalid.") from exc
        if approved_at.tzinfo is None:
            raise AcceptanceBudgetError("Acceptance amendment approval must include a timezone.")
        for field in ("approved_by", "approval_reference"):
            _single_line(value.get(field), field)
        normalized_limits: dict[str, dict[str, Any]] = {}
        for raw_key, raw_limit in limits.items():
            key = str(raw_key or "")
            provider, separator, purpose = key.partition(":")
            if not separator:
                raise AcceptanceBudgetError("Dispatch-limit keys must use provider:purpose.")
            provider = _identifier(provider, "provider").lower()
            purpose = _identifier(purpose, "purpose")
            limit = _json_mapping(raw_limit, f"dispatch limit {key}")
            requested_model = _identifier(limit.get("requested_model"), "requested_model")
            maximum_input = limit.get("max_input_tokens")
            maximum_output = limit.get("max_output_tokens")
            if type(maximum_input) is not int or maximum_input <= 0:
                raise AcceptanceBudgetError("Dispatch limit requires max_input_tokens.")
            if type(maximum_output) is not int or maximum_output <= 0:
                raise AcceptanceBudgetError("Dispatch limit requires max_output_tokens.")
            if money(limit.get("ceiling_usd")) <= 0:
                raise AcceptanceBudgetError("Dispatch limit requires a positive ceiling.")
            for count_key in ("max_calls", "max_calls_per_page", "max_attempts"):
                if type(limit.get(count_key)) is not int or limit[count_key] <= 0:
                    raise AcceptanceBudgetError(
                        f"Dispatch limit requires a positive {count_key}."
                    )
            required_effort = limit.get("required_effort")
            if not isinstance(required_effort, str) or len(required_effort) > 50:
                raise AcceptanceBudgetError("Dispatch limit requires exact effort binding.")
            allowed_efforts = {"high", "xhigh"} if value["schema_version"] == 2 else {"high"}
            if purpose != "ocr" and required_effort not in allowed_efforts:
                raise AcceptanceBudgetError(
                    "Protocol acceptance requires an explicitly supported effort."
                )
            if value["schema_version"] == 1 and self.pricing_snapshot.resolve(provider, requested_model).status != "available":
                raise AcceptanceBudgetError(
                    "Dispatch-limit model is absent from the pricing snapshot."
                )
            allowed = limit.get("allowed_actual_models", [])
            if not isinstance(allowed, list):
                raise AcceptanceBudgetError("allowed_actual_models must be a list.")
            for model in allowed:
                _identifier(model, "allowed_actual_model")
                if value["schema_version"] == 1 and self.pricing_snapshot.resolve(provider, model).status != "available":
                    raise AcceptanceBudgetError(
                        "Allowed actual model is absent from the pricing snapshot."
                    )
            allowed_pages = limit.get("allowed_pages")
            if (
                not isinstance(allowed_pages, list)
                or not allowed_pages
                or any(type(page) is not int or page <= 0 for page in allowed_pages)
                or len(set(allowed_pages)) != len(allowed_pages)
            ):
                raise AcceptanceBudgetError(
                    "Dispatch limit requires unique positive allowed_pages."
                )
            allowed_hashes = limit.get("allowed_request_hashes")
            if (
                not isinstance(allowed_hashes, list)
                or not allowed_hashes
                or any(not isinstance(item, str) or _SHA256.fullmatch(item) is None for item in allowed_hashes)
                or len(set(allowed_hashes)) != len(allowed_hashes)
            ):
                raise AcceptanceBudgetError(
                    "Dispatch limit requires unique approved request SHA-256 values."
                )
            approved_calls = limit.get("approved_calls")
            if approved_calls is None:
                # The original one-call manifest spelling remains accepted only
                # when it is unambiguous.  Multi-page or retry approval must bind
                # every page/attempt/hash tuple explicitly so hashes cannot be
                # cross-paired between otherwise approved calls.
                if (
                    len(allowed_pages) != 1
                    or len(allowed_hashes) != 1
                    or limit["max_calls"] != 1
                    or limit["max_calls_per_page"] != 1
                    or limit["max_attempts"] != 1
                ):
                    raise AcceptanceBudgetError(
                        "Multi-call dispatch limits require exact approved_calls tuples."
                    )
                approved_calls = [
                    {
                        "page_number": allowed_pages[0],
                        "attempt": 1,
                        "request_hash": allowed_hashes[0],
                    }
                ]
            if not isinstance(approved_calls, list) or not approved_calls:
                raise AcceptanceBudgetError("approved_calls must be a nonempty list.")
            normalized_calls: list[dict[str, Any]] = []
            seen_calls: set[tuple[int, int, str]] = set()
            for raw_call in approved_calls:
                call = _json_mapping(raw_call, "approved call")
                call_fields = {"page_number", "attempt", "request_hash"}
                if value["schema_version"] == 2 and purpose == "correction":
                    call_fields.add("pending_correction_sha256")
                if set(call) != call_fields:
                    raise AcceptanceBudgetError(
                        "Each approved call must bind exact page/attempt/request and correction evidence when applicable."
                    )
                page = call["page_number"]
                attempt = call["attempt"]
                request_hash = call["request_hash"]
                if type(page) is not int or page not in allowed_pages:
                    raise AcceptanceBudgetError("Approved call page is outside allowed_pages.")
                if type(attempt) is not int or not 0 < attempt <= limit["max_attempts"]:
                    raise AcceptanceBudgetError("Approved call attempt is outside max_attempts.")
                if not isinstance(request_hash, str) or request_hash not in allowed_hashes:
                    raise AcceptanceBudgetError(
                        "Approved call request hash is outside allowed_request_hashes."
                    )
                identity = (page, attempt, request_hash)
                if identity in seen_calls:
                    raise AcceptanceBudgetError("Approved call tuples must be unique.")
                seen_calls.add(identity)
                normalized_calls.append(call)
            calls_by_page: dict[int, list[int]] = {}
            for call in normalized_calls:
                calls_by_page.setdefault(call["page_number"], []).append(call["attempt"])
            if set(calls_by_page) != set(allowed_pages):
                raise AcceptanceBudgetError("Every allowed page must have an approved call.")
            if {call["request_hash"] for call in normalized_calls} != set(allowed_hashes):
                raise AcceptanceBudgetError("Every allowed request hash must bind an approved call.")
            if len(normalized_calls) != limit["max_calls"]:
                raise AcceptanceBudgetError("max_calls must equal the approved call count.")
            if max(len(attempts) for attempts in calls_by_page.values()) != limit[
                "max_calls_per_page"
            ]:
                raise AcceptanceBudgetError(
                    "max_calls_per_page must equal the largest approved page sequence."
                )
            for attempts in calls_by_page.values():
                ordered = sorted(attempts)
                if ordered != list(range(1, len(ordered) + 1)):
                    raise AcceptanceBudgetError(
                        "Approved attempts must be contiguous from one for each page."
                    )
            if max(call["attempt"] for call in normalized_calls) != limit["max_attempts"]:
                raise AcceptanceBudgetError(
                    "max_attempts must equal the largest approved attempt."
                )
            limit["approved_calls"] = normalized_calls
            normalized_limits[f"{provider}:{purpose}"] = limit
        value["dispatch_limits"] = normalized_limits
        if value["schema_version"] == 2:
            self._validate_v2_amendment(value)
        return value

    def _validate_v2_amendment(self, value: Mapping[str, Any]) -> None:
        if value.get("approval_status") != "approved":
            raise AcceptanceBudgetError("The acceptance amendment is revoked or not approved.")
        history = value.get("prior_amendments")
        if not isinstance(history, list) or len(history) > 100:
            raise AcceptanceBudgetError("An append-only prior amendment list is required.")
        seen: set[str] = set()
        for row in history:
            if not isinstance(row, dict) or set(row) != {"sha256", "fingerprint"}:
                raise AcceptanceBudgetError("Prior amendment identity is malformed.")
            for digest in row.values():
                if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    raise AcceptanceBudgetError("Prior amendment requires SHA-256 identities.")
            if row["sha256"] in seen or row["sha256"] == self.expected_amendment_sha256:
                raise AcceptanceBudgetError("Duplicate approval cannot extend a campaign.")
            seen.add(row["sha256"])
        prior_rows = value.get("prior_reservations_fingerprint")
        if not isinstance(prior_rows, str) or not _SHA256.fullmatch(prior_rows):
            raise AcceptanceBudgetError("Prior campaign charges must be hash-pinned.")
        verify_physical_provenance(value.get("provenance"),
            source_sha256=self.run_identity["source_sha256"], execution_identity=self.execution_identity)
        for key, limit in value["dispatch_limits"].items():
            provider = key.split(":", 1)[0]
            if provider != "openai" or limit.get("route") != "responses.create":
                raise AcceptanceBudgetError("Acceptance transport is outside the implemented route allowlist.")
            urls = limit.get("allowed_base_urls")
            if not isinstance(urls, list) or not urls or any(not isinstance(url, str) or not url.startswith("https://") for url in urls):
                raise AcceptanceBudgetError("Acceptance requires a finite approved HTTPS transport endpoint list.")
            if limit.get("requested_service_tier") not in {"auto", "default", "priority", "flex", "fast"}:
                raise AcceptanceBudgetError("Acceptance requires an exact requested service tier.")
            _identifier(limit.get("billing_scope"), "billing_scope")
            if limit.get("currency") != "USD":
                raise AcceptanceBudgetError("Acceptance must preserve the USD lifetime allowance.")
            tiers = limit.get("allowed_actual_service_tiers")
            if not isinstance(tiers, list) or not tiers or "auto" in tiers:
                raise AcceptanceBudgetError("Acceptance requires a finite actual service tier allowlist.")
            required_tiers = set(tiers)
            if limit["requested_service_tier"] != "auto":
                required_tiers.add(limit["requested_service_tier"])
            for model in {limit["requested_model"], *limit.get("allowed_actual_models", [])}:
                for tier in required_tiers:
                    if self.pricing_snapshot.resolve(provider, model, service_tier=tier,
                            billing_scope=limit["billing_scope"], currency=limit["currency"]).status != "available":
                        raise AcceptanceBudgetError("Acceptance model/tier/scope has no verified price.")
            if key.split(":", 1)[1] in {"translation", "correction"} and limit["max_calls_per_page"] != 1:
                raise AcceptanceBudgetError("Acceptance permits at most one primary and one correction per page.")
            if key.split(":", 1)[1] == "correction":
                evidence = limit.get("pending_correction_files")
                if not isinstance(evidence, dict) or set(evidence) != {call["pending_correction_sha256"] for call in limit["approved_calls"]}:
                    raise AcceptanceBudgetError("Correction requires exact private pending-evidence files.")
                for digest, entry in evidence.items():
                    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                        raise AcceptanceBudgetError("Pending correction fingerprint must be SHA-256.")
                    verify_pending_correction(entry, digest)

    def _control_identity(self) -> dict[str, Any]:
        return {"ledger_path": str(self.path), "lock_path": str(self.lock_path),
            "amendment_path": str(self.amendment_path), "expected_amendment_sha256": self.expected_amendment_sha256,
            "amendment_fingerprint": self.amendment_fingerprint, "hard": self.hard,
            "cap_usd": str(self.cap_usd), "campaign_cap_usd": str(self.campaign_cap_usd),
            "campaign_id": self.campaign_id, "case": dict(self.case),
            "run_identity": self.run_identity, "execution_identity": self.execution_identity,
            "pricing_snapshot": self.pricing_snapshot.metadata(), "binding_identity": self.binding_identity,
            "dispatch_enabled": self.dispatch_enabled, "continuation_identity": self.continuation_identity}

    @property
    def runtime_context_bound(self) -> bool:
        return self._runtime_context is not None

    def bind_runtime_context(self, *,
                             config: Mapping[str, Any] | Callable[[], Mapping[str, Any]],
                             preferences: Mapping[str, Any] | Callable[[], Mapping[str, Any]]) -> None:
        """Bind actual effective workflow values; reevaluate them before each send."""
        if not self.dispatch_enabled:
            raise AcceptanceBudgetError("Legacy amendments cannot bind executable runtime authority.")
        self._verify_physical(require_runtime=False)
        verify_runtime_context(self.amendment["provenance"], config=config, preferences=preferences)
        self._runtime_context = (config, preferences)

    def _verify_physical(self, *, require_runtime: bool = True) -> None:
        if fingerprint(self._control_identity()) != self._frozen_controls:
            raise AcceptanceBudgetError("Immutable external approval identity or budget controls changed.")
        if (fingerprint(self.amendment) != self._approved_state_fingerprint
                or fingerprint({key: dict(value) for key, value in self.dispatch_limits.items()}) != self._approved_limits_fingerprint):
            raise AcceptanceBudgetError("In-memory acceptance approval changed after verification.")
        try:
            if hashlib.sha256(self.amendment_path.read_bytes()).hexdigest() != self.expected_amendment_sha256:
                raise AcceptanceBudgetError("Acceptance amendment changed or was revoked after approval.")
        except OSError as exc:
            raise AcceptanceBudgetError("Approved amendment is unavailable.") from exc
        verify_physical_provenance(self.amendment["provenance"],
            source_sha256=self.run_identity["source_sha256"], execution_identity=self.execution_identity)
        for limit in self.dispatch_limits.values():
            for digest, entry in limit.get("pending_correction_files", {}).items():
                verify_pending_correction(entry, digest)
        if require_runtime:
            if self._runtime_context is None:
                raise AcceptanceBudgetError("Actual effective runtime context must be bound before dispatch.")
            config, preferences = self._runtime_context
            verify_runtime_context(self.amendment["provenance"], config=config, preferences=preferences)

    def permits_dispatch(self, *, request_hash: str, provider: str, purpose: str,
                         page_number: int, attempt: int, requested_model: str, effort: str,
                         requested_service_tier: str, billing_scope: str, currency: str,
                         route: str, base_url: str | None = None,
                         pending_correction_sha256: str | None = None) -> bool:
        """Read-only permission query; this creates neither a proof nor a reservation."""
        if not self.dispatch_enabled:
            return False
        limit = self.dispatch_limits.get(f"{provider}:{purpose}")
        if limit is None:
            return False
        if pending_correction_sha256 is not None and not any(
                call.get("pending_correction_sha256") == pending_correction_sha256
                and call["request_hash"] == request_hash and call["page_number"] == page_number
                and call["attempt"] == attempt for call in limit["approved_calls"]):
            return False
        details = dict(provider=provider, purpose=purpose, page_number=page_number,
            attempt=attempt, request_hash=request_hash, requested_model=requested_model,
            effort=effort, requested_service_tier=requested_service_tier,
            billing_scope=billing_scope, currency=currency, route=route,
            base_url=base_url or limit["allowed_base_urls"][0], bounds=dict(limit))
        try:
            self._verify_physical()
            self._validate_dispatch(details, money(limit["ceiling_usd"]))
            with locked(self.lock_path):
                state = self._load_ledger_unlocked()
                if state.get("blocked_reason") or any(row["status"] != "finalized" for row in state["reservations"].values()):
                    return False
            return True
        except (BudgetError, OSError, ValueError):
            return False

    def verify_dispatch(self, *, request: Mapping[str, Any], provider: str, purpose: str,
                        page_number: int, attempt: int, route: str,
                        requested_service_tier: str | None = None,
                        billing_scope: str | None = None, currency: str = "USD",
                        base_url: str | None = None) -> None:
        """Authorize only the actual bounded request, after physical byte checks."""
        self._verified_dispatch = None
        requested_tier = request.get("service_tier", "auto")
        if requested_service_tier not in {None, requested_tier}:
            raise AcceptanceBudgetError("Request and accounting service tiers differ.")
        reasoning = request.get("reasoning", {})
        details = dict(provider=provider, purpose=purpose, page_number=page_number,
            attempt=attempt, route=route, requested_model=request.get("model"),
            effort=reasoning.get("effort", "") if isinstance(reasoning, Mapping) else "",
            request_hash=request_fingerprint(request), requested_service_tier=requested_tier,
            billing_scope=billing_scope, currency=currency, base_url=base_url)
        if base_url is None:
            raise AcceptanceBudgetError("Observed provider endpoint is required at dispatch.")
        if not self.permits_dispatch(**details):
            raise AcceptanceBudgetError("Final request is not covered by current external acceptance approval.")
        limit = self.dispatch_limits[f"{provider}:{purpose}"]
        if request.get("max_output_tokens") != limit["max_output_tokens"]:
            raise AcceptanceBudgetError("Final request output bound differs from the approved request.")
        self._verified_dispatch = details

    def recheck_dispatch(self, reservation_id: str, *, request: Mapping[str, Any],
                         provider: str, purpose: str, page_number: int, attempt: int,
                         route: str, requested_service_tier: str | None = None,
                         billing_scope: str | None = None, currency: str = "USD",
                         base_url: str | None = None) -> None:
        """After reservation, verify this exact owned request without new authority."""
        self._verify_physical()
        tier = request.get("service_tier", "auto")
        if requested_service_tier not in {None, tier}:
            raise AcceptanceBudgetError("Request and accounting service tiers differ.")
        reasoning = request.get("reasoning", {})
        details = dict(provider=provider, purpose=purpose, page_number=page_number,
            attempt=attempt, route=route, requested_model=request.get("model"),
            effort=reasoning.get("effort", "") if isinstance(reasoning, Mapping) else "",
            request_hash=request_fingerprint(request), requested_service_tier=tier,
            billing_scope=billing_scope, currency=currency, base_url=base_url)
        with locked(self.lock_path):
            state = self._load_ledger_unlocked()
            row = state["reservations"].get(reservation_id)
            if state.get("blocked_reason") or any(
                    key != reservation_id and other["status"] != "finalized"
                    for key, other in state["reservations"].items()):
                raise AcceptanceBudgetError("Acceptance became blocked before provider contact.")
            if not isinstance(row, dict) or row.get("status") != "reserved" or row.get("owner") != self._owner:
                raise AcceptanceBudgetError("Only this adapter's owned reserved dispatch can be rechecked.")
            if not _is_current_row(row, self.amendment_fingerprint) or any(row["execution"].get(key) != value for key, value in details.items()):
                raise AcceptanceBudgetError("Reserved request changed before provider contact.")

    def _campaign_binding(self) -> dict[str, Any]:
        return {"campaign_id": self.campaign_id, "campaign_cap_usd": str(self.campaign_cap_usd),
            "ledger_path": str(self.path), "benchmark_id": self.amendment["ledger"]["benchmark_id"],
            "manifest_fingerprint": self.amendment["ledger"]["manifest_fingerprint"],
            "cap_usd": str(self.cap_usd)}

    def _append_authorization(self, state: dict[str, Any]) -> None:
        campaigns = state.setdefault("acceptance_campaigns", {})
        campaign = campaigns.setdefault(self.campaign_id, {
            "identity": self._campaign_binding(), "amendments": [], "cases": {}})
        current = {"sha256": self.expected_amendment_sha256, "fingerprint": self.amendment_fingerprint}
        if current not in campaign["amendments"]:
            campaign["amendments"].append(current)
        campaign["cases"].setdefault(self.case["case_id"], self.binding_identity)

    def _validate_campaign_history(self, state: Mapping[str, Any], current_rows: Mapping[str, Any]) -> None:
        campaigns = state.get("acceptance_campaigns", {})
        if not isinstance(campaigns, dict):
            raise AcceptanceBudgetError("Acceptance campaign registry is malformed.")
        campaign = campaigns.get(self.campaign_id)
        history = self.amendment["prior_amendments"]
        expected = {"sha256": self.expected_amendment_sha256, "fingerprint": self.amendment_fingerprint}
        if campaign is None:
            if history or current_rows:
                raise AcceptanceBudgetError("An earlier campaign authorization is missing.")
        else:
            if campaign.get("identity") != self._campaign_binding():
                raise AcceptanceBudgetError("Campaign identity or aggregate ceiling changed.")
            saved = campaign.get("amendments")
            if saved not in (history, [*history, expected]):
                raise AcceptanceBudgetError("Approval chain is duplicated, superseded, or mismatched.")
            prior_binding = campaign.get("cases", {}).get(self.case["case_id"])
            if prior_binding is not None and prior_binding != self.binding_identity:
                raise AcceptanceBudgetError("Stable case identity or aggregate case bounds changed.")
        prior_rows = {key: row for key, row in state["reservations"].items()
            if _is_campaign_row(row, self.campaign_id) and key not in current_rows}
        if fingerprint(prior_rows) != self.amendment["prior_reservations_fingerprint"]:
            raise AcceptanceBudgetError("Previously charged campaign history differs from approval.")

    def _load_ledger_unlocked(self) -> dict[str, Any]:
        try:
            raw = self.path.read_bytes()
            state = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AcceptanceBudgetError("Acceptance ledger is unreadable.") from exc
        if not isinstance(state, dict) or state.get("schema_version") != 1:
            raise AcceptanceBudgetError("Unsupported acceptance ledger.")
        digest = state.get("fingerprint")
        if digest != fingerprint({key: value for key, value in state.items() if key != "fingerprint"}):
            raise AcceptanceBudgetError("Acceptance ledger integrity check failed.")
        pinned = self.amendment["ledger"]
        if (
            state.get("benchmark_id") != pinned["benchmark_id"]
            or state.get("manifest_fingerprint") != pinned["manifest_fingerprint"]
            or money(state.get("cap_usd")) != money(pinned["cap_usd"])
            or not isinstance(state.get("reservations"), dict)
        ):
            raise AcceptanceBudgetError("Acceptance ledger identity or cap changed.")
        current_rows = {
            key: row
            for key, row in state["reservations"].items()
            if _is_current_row(row, self.amendment_fingerprint)
        }
        if self.dispatch_enabled:
            self._validate_campaign_history(state, current_rows)
        base_rows = {
            key: row
            for key, row in state["reservations"].items()
            if not (_is_campaign_row(row, self.campaign_id) if self.dispatch_enabled else key in current_rows)
        }
        if fingerprint(base_rows) != pinned["base_reservations_fingerprint"]:
            raise AcceptanceBudgetError("Acceptance ledger history differs from the pinned base.")
        static = {
            key: value
            for key, value in state.items()
            if key not in {"reservations", "updated_at", "fingerprint", "blocked_reason", "acceptance_campaigns"}
        }
        if fingerprint(static) != pinned["base_static_fingerprint"]:
            raise AcceptanceBudgetError("Acceptance ledger static identity differs from the pin.")
        no_campaign = not self.dispatch_enabled or self.campaign_id not in state.get("acceptance_campaigns", {})
        if not current_rows and no_campaign and hashlib.sha256(raw).hexdigest() != pinned["initial_sha256"]:
            raise AcceptanceBudgetError("Acceptance ledger initial hash differs from the pin.")
        for identifier, row in state["reservations"].items():
            _identifier(identifier, "reservation_id")
            if not isinstance(row, dict) or row.get("status") not in {
                "reserved",
                "uncertain",
                "finalized",
            }:
                raise AcceptanceBudgetError("Acceptance reservation is malformed.")
            ceiling = money(row.get("reserved_usd"))
            if ceiling <= 0:
                raise AcceptanceBudgetError("Acceptance reservation ceiling is invalid.")
            if row["status"] == "finalized":
                if row.get("actual_usd") is None or money(row["actual_usd"]) > ceiling:
                    raise AcceptanceBudgetError("Finalized acceptance reservation is invalid.")
            elif row.get("actual_usd") is not None:
                raise AcceptanceBudgetError("Unsettled acceptance reservation has actual cost.")
        if _committed(state) > self.cap_usd:
            raise AcceptanceBudgetError("Acceptance commitments exceed the lifetime cap.")
        return state

    def _save_ledger_unlocked(self, state: dict[str, Any]) -> None:
        state["updated_at"] = datetime.now().astimezone().isoformat()
        state["fingerprint"] = fingerprint(
            {key: value for key, value in state.items() if key != "fingerprint"}
        )
        atomic_json(self.path, state)

    def _campaign_committed(self, state: Mapping[str, Any]) -> Decimal:
        return sum(
            (
                money(
                    row["actual_usd"]
                    if row["status"] == "finalized"
                    else row["reserved_usd"]
                )
                for row in state["reservations"].values()
                if _is_campaign_row(row, self.campaign_id)
            ),
            Decimal(0),
        )

    def _case_committed(self, state: Mapping[str, Any]) -> Decimal:
        return sum(
            (
                money(
                    row["actual_usd"]
                    if row["status"] == "finalized"
                    else row["reserved_usd"]
                )
                for row in state["reservations"].values()
                if _is_case_row(row, self.campaign_id, self.case["case_id"])
            ),
            Decimal(0),
        )

    def _validate_dispatch(
        self,
        metadata: Mapping[str, Any],
        ceiling: Decimal,
    ) -> Mapping[str, Any]:
        provider = _identifier(metadata.get("provider"), "provider").lower()
        purpose = _identifier(metadata.get("purpose"), "purpose")
        requested_model = _identifier(metadata.get("requested_model"), "requested_model")
        request_hash = metadata.get("request_hash")
        if not isinstance(request_hash, str) or _SHA256.fullmatch(request_hash) is None:
            raise AcceptanceBudgetError("Dispatch request_hash must be SHA-256.")
        if type(metadata.get("attempt")) is not int or metadata["attempt"] <= 0:
            raise AcceptanceBudgetError("Dispatch attempt must be positive.")
        limit = self.dispatch_limits.get(f"{provider}:{purpose}")
        if limit is None:
            raise AcceptanceBudgetError("Dispatch purpose is absent from the amendment.")
        if requested_model != limit["requested_model"]:
            raise AcceptanceBudgetError("Dispatch model differs from the amendment.")
        approved_call = {
            "page_number": metadata.get("page_number"),
            "attempt": metadata["attempt"],
            "request_hash": request_hash,
        }
        if not any(all(call.get(key) == value for key, value in approved_call.items()) for call in limit["approved_calls"]):
            raise AcceptanceBudgetError(
                "Dispatch page, attempt or request differs from the approved call tuple."
            )
        if metadata.get("effort", "") != limit["required_effort"]:
            raise AcceptanceBudgetError("Dispatch effort differs from the amendment.")
        if self.dispatch_enabled:
            for field in ("route", "requested_service_tier", "billing_scope", "currency"):
                if metadata.get(field) != limit[field]:
                    raise AcceptanceBudgetError(f"Dispatch {field} differs from the amendment.")
            if metadata.get("base_url") not in limit["allowed_base_urls"]:
                raise AcceptanceBudgetError("Dispatch endpoint differs from the amendment.")
        if metadata["attempt"] > limit["max_attempts"]:
            raise AcceptanceBudgetError("Dispatch attempt exceeds the amendment.")
        if ceiling != money(limit["ceiling_usd"]):
            raise AcceptanceBudgetError("Dispatch ceiling differs from the amendment.")
        bounds = metadata.get("bounds")
        if not isinstance(bounds, Mapping):
            raise AcceptanceBudgetError("Dispatch bounds are missing.")
        for key in ("max_input_tokens", "max_image_input_tokens", "image_bound_verified"):
            if key in limit and bounds.get(key) != limit[key]:
                raise AcceptanceBudgetError(f"Dispatch {key} differs from the amendment.")
        observed_output = bounds.get("max_output_tokens")
        if type(observed_output) is not int or not 0 < observed_output <= limit["max_output_tokens"]:
            raise AcceptanceBudgetError("Dispatch max_output_tokens exceeds the amendment.")
        allowed_pages = limit.get("allowed_pages")
        if allowed_pages is not None:
            page = metadata.get("page_number")
            if not isinstance(allowed_pages, list) or page not in allowed_pages:
                raise AcceptanceBudgetError("Dispatch page is outside the approved amendment.")
        return limit


def _is_current_row(row: Any, amendment_fingerprint: str) -> bool:
    return bool(
        isinstance(row, Mapping)
        and isinstance(row.get("execution"), Mapping)
        and row["execution"].get("acceptance_amendment_fingerprint")
        == amendment_fingerprint
    )


def _is_campaign_row(row: Any, campaign_id: str) -> bool:
    return bool(
        isinstance(row, Mapping)
        and isinstance(row.get("execution"), Mapping)
        and row["execution"].get("campaign_id") == campaign_id
    )


def _is_case_row(row: Any, campaign_id: str, case_id: str) -> bool:
    return bool(
        _is_campaign_row(row, campaign_id)
        and row["execution"].get("case_id") == case_id
    )


def _committed(state: Mapping[str, Any]) -> Decimal:
    return sum(
        (
            money(
                row["actual_usd"]
                if row["status"] == "finalized"
                else row["reserved_usd"]
            )
            for row in state["reservations"].values()
        ),
        Decimal(0),
    )


def _json_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise AcceptanceBudgetError(f"{label} must be a mapping.")
    try:
        result = json.loads(
            json.dumps(dict(value), ensure_ascii=False, allow_nan=False)
        )
    except (TypeError, ValueError) as exc:
        raise AcceptanceBudgetError(f"{label} must contain finite JSON values.") from exc
    _validate_safe_json(result, label)
    return result


def _validate_safe_json(value: Any, label: str) -> None:
    forbidden = {"prompt", "source_text", "document_text", "api_key", "secret", "content"}
    if isinstance(value, dict):
        if len(value) > 100:
            raise AcceptanceBudgetError(f"{label} is too large.")
        for key, child in value.items():
            if not isinstance(key, str) or key.lower() in forbidden:
                raise AcceptanceBudgetError(f"{label} contains a forbidden field.")
            _validate_safe_json(child, label)
    elif isinstance(value, list):
        if len(value) > 100:
            raise AcceptanceBudgetError(f"{label} is too large.")
        for child in value:
            _validate_safe_json(child, label)
    elif isinstance(value, str):
        if len(value) > 512 or "\n" in value or "\r" in value:
            raise AcceptanceBudgetError(f"{label} contains unsafe text.")
    elif value is not None and not isinstance(value, (str, int, float, bool)):
        raise AcceptanceBudgetError(f"{label} contains unsupported values.")


def _identifier(value: Any, label: str) -> str:
    candidate = str(value or "")
    if (
        not candidate
        or len(candidate) > 200
        or any(not (character.isalnum() or character in "._:-") for character in candidate)
    ):
        raise AcceptanceBudgetError(f"{label} must be a concise safe identifier.")
    return candidate


def _single_line(value: Any, label: str) -> str:
    candidate = str(value or "").strip()
    if not candidate or len(candidate) > 500 or "\n" in candidate or "\r" in candidate:
        raise AcceptanceBudgetError(f"{label} must be concise single-line text.")
    return candidate


def _normalized_path(value: str) -> str:
    return os.path.normcase(str(Path(value).resolve()))


def stable_acceptance_run_identity(run_identity: Mapping[str, Any]) -> dict[str, Any]:
    """Return the pre-approvable run identity, excluding generated timestamps/IDs."""

    return _stable_run_identity(_json_mapping(run_identity, "run identity"))


def _stable_run_identity(run_identity: Mapping[str, Any]) -> dict[str, Any]:
    missing = [key for key in _STABLE_RUN_KEYS if key not in run_identity]
    if missing:
        raise AcceptanceBudgetError(
            "Stable run identity is missing: " + ", ".join(missing)
        )
    stable = {key: deepcopy(run_identity[key]) for key in _STABLE_RUN_KEYS}
    if not isinstance(stable["source_sha256"], str) or _SHA256.fullmatch(
        stable["source_sha256"]
    ) is None:
        raise AcceptanceBudgetError("Stable source identity must be lowercase SHA-256.")
    context_hash = stable["context_hash"]
    if context_hash != "NO_CONTEXT" and (
        not isinstance(context_hash, str) or _SHA256.fullmatch(context_hash) is None
    ):
        raise AcceptanceBudgetError(
            "Stable context identity must be lowercase SHA-256 or NO_CONTEXT."
        )
    if stable["protocol"] != "legal_blocks_v2":
        raise AcceptanceBudgetError("Stable protocol must be legal_blocks_v2.")
    if not isinstance(stable["protocol_identity"], dict):
        raise AcceptanceBudgetError("Stable protocol identity must be a mapping.")
    if stable["protocol_identity"].get("protocol") != stable["protocol"]:
        raise AcceptanceBudgetError("Stable protocol identities contradict one another.")
    protocol_fingerprint = stable["protocol_identity"].get("fingerprint")
    if not isinstance(protocol_fingerprint, str) or _SHA256.fullmatch(
        protocol_fingerprint
    ) is None:
        raise AcceptanceBudgetError("Stable protocol identity fingerprint is invalid.")
    _identifier(stable["model"], "model")
    if stable["language"] not in {"EN", "FR", "AR"}:
        raise AcceptanceBudgetError("Stable language must be EN, FR or AR.")
    selection = stable["selection"]
    if (
        not isinstance(selection, list)
        or len(selection) != 2
        or any(type(page) is not int or page <= 0 for page in selection)
        or selection[0] > selection[1]
    ):
        raise AcceptanceBudgetError("Stable page selection is invalid.")
    return stable
