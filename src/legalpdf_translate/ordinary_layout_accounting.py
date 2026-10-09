"""Explicit local layout authorization sharing one overall run budget."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import threading

from .budget_reservations import ReservationBudget, money, atomic_json
from .ordinary_layout_contracts import LayoutSuggestionPolicy, fail, nonce, decode
from .usage_accounting import DispatchAccounting

PAGE_CEILING = Decimal("1.148")
MODEL = "gpt-5.2"
ACTUAL_MODEL = "gpt-5.2-2025-12-11"


def verified_page_ceiling() -> Decimal:
    """Recompute the hard reservation from the fresh published price and bounds."""
    args = layout_accounting_policy().accounting_arguments()
    pricing = args["pricing_snapshot"]
    if pricing is None:
        fail("pricing_reference_expired", 503)
    limit = args["dispatch_limits"][f"openai:layout_suggestion:{MODEL}"]
    rate = pricing["models"][f"openai:{MODEL}|default|openai_public_api|USD"]
    amount = (Decimal(str(limit["max_input_tokens"])) * Decimal(str(rate["input_per_1m"]))
              + Decimal(str(limit["max_output_tokens"])) * Decimal(str(rate["output_per_1m"]))) / Decimal(1_000_000)
    if amount != PAGE_CEILING:
        fail("paid_policy_bound_mismatch", 503)
    return amount


def layout_accounting_policy():
    from .accounting_policy import OrdinaryAccountingPolicy
    source = "https://developers.openai.com/api/docs/models/gpt-5.2"
    rates = {"input_per_1m": 1.75, "cached_input_per_1m": .175, "output_per_1m": 14,
        "provider": "openai", "pricing_model": MODEL, "service_tier": "default",
        "billing_scope": "openai_public_api", "currency": "USD", "source_url": source}
    policy = OrdinaryAccountingPolicy.from_mapping(pricing={"snapshot_id": "layout_standard_2026_10_09",
        "verified_at": "2026-10-09", "source": source,
        "models": {f"openai:{name}|default|openai_public_api|USD": {**rates, "pricing_model": name}
                   for name in (MODEL, ACTUAL_MODEL)}},
        limits={f"openai:layout_suggestion:{MODEL}": {"requested_model": MODEL,
            "allowed_actual_models": [ACTUAL_MODEL], "requested_service_tier": "default",
            "allowed_actual_service_tiers": ["default"], "billing_scope": "openai_public_api", "currency": "USD",
            "allowed_base_urls": ["https://api.openai.com/v1"], "max_input_tokens": 400000,
            "max_image_input_tokens": 10000, "max_image_count": 1, "image_bound_verified": True,
            "image_bound_source_url": "https://developers.openai.com/api/docs/guides/images-vision",
            "image_bound_verified_at": "2026-10-09",
            "image_bound_basis": "GPT-5.2 high detail: at most 6144 patches x 1.2; rounded upward below 10000 tokens",
            "max_output_tokens": 32000, "bound_source_url": source, "bound_verified_at": "2026-10-09"}})
    return OrdinaryAccountingPolicy(policy._pricing_json, policy._limits_json, date(2026, 10, 9))


class OrdinaryLayoutAccounting:
    def __init__(self, jobs):
        self.jobs = jobs
        self._lock = threading.RLock()
        self._budgets = {}

    def _source(self, job):
        with self.jobs._lock:
            record = self.jobs._jobs.get(job.job_id)
            if record is None or record.status not in {"completed", "formatting"}:
                fail("accounting_unavailable", 409)
            accountant = record._completed_accountant
            folder = Path(record.result_payload["run_dir"]) / "ordinary_layout_budget" / job.job_id
        if not isinstance(accountant, DispatchAccounting):
            fail("accounting_unavailable", 409)
        summary = accountant.summary()
        if summary.get("cost_usd") is None or not accountant.can_retry:
            fail("translation_accounting_incomplete", 409)
        return accountant, folder, money(summary["cost_usd"])

    def _budget(self, job, accountant, folder):
        if accountant.hard_budget:
            return accountant.budget_context
        recovery = folder / "revalidation_capacity_v2"
        if not (recovery / "authorization.json").is_file():
            recovery = folder / "revalidation_capacity_v1"
        if not (recovery / "authorization.json").is_file():
            recovery = folder / "recovery_capacity_v2"
        recovery_receipt = recovery / "authorization.json"
        if recovery_receipt.is_file():
            record = decode(recovery_receipt.read_bytes())
            if record["binding"] != dict(job.binding):
                fail("budget_binding_changed", 409)
            if recovery.name == "revalidation_capacity_v2":
                digest = record.get("direct_continuation_identity_sha256")
                missing = record.get("missing_pages")
                if (type(digest) is not str or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)
                        or record["identity"].get("direct_continuation_identity_sha256") != digest
                        or type(missing) is not list or any(type(page) is not int for page in missing)
                        or sorted(set(missing)) != missing or not set(missing) <= set(job.selected_pages)
                        or record["identity"].get("missing_pages") != missing
                        or record["identity"].get("prior_layout_cost_usd") != record.get("prior_layout_cost_usd")
                        or money(record["cap_usd"]) != money(record["translation_cost_usd"])
                           + money(record["prior_layout_cost_usd"]) + PAGE_CEILING * len(missing)):
                    fail("budget_binding_changed", 409)
            key = (job.job_id, recovery.name)
            if key not in self._budgets:
                self._budgets[key] = ReservationBudget(recovery / "budget.json",
                    cap_usd=record["cap_usd"], identity=record["identity"], create=False)
            if recovery.name == "revalidation_capacity_v2" and (
                    self._budgets[key].identity != record["identity"]
                    or self._budgets[key].cap_usd != money(record["cap_usd"])):
                fail("budget_binding_changed", 409)
            return self._budgets[key]
        if job.job_id in self._budgets:
            return self._budgets[job.job_id]
        receipt = folder / "authorization.json"
        if not receipt.is_file():
            return None
        record = decode(receipt.read_bytes())
        if record["binding"] != dict(job.binding):
            fail("budget_binding_changed", 409)
        budget = ReservationBudget(folder / "budget.json", cap_usd=record["cap_usd"],
            identity=record["identity"], create=False)
        self._budgets[job.job_id] = budget
        return budget

    def state(self, job):
        base = {"authorization_available": False, "authorized": False, "shared_existing_cap": False,
                "max_page_cost_usd": str(PAGE_CEILING)}
        try:
            accountant, folder, cost = self._source(job)
            with self._lock:
                budget = self._budget(job, accountant, folder)
            recovery_receipt = folder / "recovery_capacity_v2" / "authorization.json"
            if (folder / "revalidation_capacity_v1" / "authorization.json").is_file():
                recovery_receipt = folder / "revalidation_capacity_v1" / "authorization.json"
            if (folder / "revalidation_capacity_v2" / "authorization.json").is_file():
                recovery_receipt = folder / "revalidation_capacity_v2" / "authorization.json"
            recovery_record = decode(recovery_receipt.read_bytes()) if recovery_receipt.is_file() else None
            prior = money(recovery_record["prior_layout_cost_usd"]) if recovery_record else Decimal(0)
            base.update(translation_cost_usd=str(cost), minimum_cap_usd=str(cost + prior + PAGE_CEILING),
                suggested_cap_usd=str(cost + prior + PAGE_CEILING * len(job.selected_pages)),
                authorization_available=budget is None, authorized=budget is not None,
                shared_existing_cap=bool(accountant.hard_budget))
            if recovery_record:
                base["prior_layout_cost_usd"] = str(prior)
            if budget is not None:
                status = budget.status() if callable(getattr(budget, "status", None)) else {}
                base.update({k: status[k] for k in ("cap_usd", "remaining_usd", "blocked") if k in status})
                base["cap_usd"] = str(budget.cap_usd)
                if not accountant.hard_budget:
                    receipt = recovery_receipt if recovery_record else folder / "authorization.json"
                    base["authorization_nonce"] = decode(receipt.read_bytes())["authorization_nonce"]
            return base
        except Exception as exc:
            return {**base, "reason": getattr(exc, "code", "ordinary_layout_accounting_unavailable")}

    def authorize(self, job, authorization_nonce, cap_usd):
        nonce(authorization_nonce)
        cap = money(cap_usd)
        accountant, folder, cost = self._source(job)
        if accountant.hard_budget:
            fail("shared_budget_already_configured", 409)
        identity = {"job_id": job.job_id, "run_id": job.run_id, "binding": dict(job.binding),
            "original_accounting_identity": accountant.run_identity}
        record = {"authorization_nonce": authorization_nonce, "cap_usd": str(cap), "translation_cost_usd": str(cost),
                  "binding": dict(job.binding), "identity": identity}
        with self._lock:
            if (folder / "authorization.json").exists():
                if decode((folder / "authorization.json").read_bytes()) != record:
                    fail("budget_already_authorized", 409)
                return self.state(job)
            if cap < cost + PAGE_CEILING:
                fail("budget_below_one_page_bound", 409)
            # Exclusive directory retains an interrupted authorization instead of
            # silently recreating a ledger or releasing its committed spend.
            try:
                folder.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                fail("budget_authorization_incomplete", 409)
            budget = ReservationBudget(folder / "budget.json", cap_usd=cap, identity=identity)
            budget.reserve("translation-settled", cost, {"kind": "prior_completed_translation"})
            budget.finalize("translation-settled", cost, {"cost_usd": str(cost)})
            atomic_json(folder / "authorization.json", record)
            self._budgets[job.job_id] = budget
        return self.state(job)

    def authorize_automatic(self, job, policy_fingerprint: str):
        """Bound the fresh job's included layout stage without claiming user review."""
        ceiling = verified_page_ceiling()
        accountant, folder, cost = self._source(job)
        if accountant.hard_budget:
            if accountant.budget_context is None:
                fail("durable_accounting_required", 503)
            return self.state(job)
        cap = cost + ceiling * len(job.selected_pages)
        identity = {"job_id": job.job_id, "run_id": job.run_id, "binding": dict(job.binding),
            "original_accounting_identity": accountant.run_identity,
            "automatic_policy_fingerprint": policy_fingerprint}
        record = {"authorization_nonce": "automatic_source_layout_v1", "cap_usd": str(cap),
            "translation_cost_usd": str(cost), "binding": dict(job.binding), "identity": identity,
            "authorization_kind": "server_owned_fresh_job_ceiling"}
        with self._lock:
            receipt = folder / "authorization.json"
            if receipt.exists():
                if decode(receipt.read_bytes()) != record:
                    fail("budget_already_authorized", 409)
                return self.state(job)
            try:
                folder.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                fail("budget_authorization_incomplete", 409)
            budget = ReservationBudget(folder / "budget.json", cap_usd=cap, identity=identity)
            budget.reserve("translation-settled", cost, {"kind": "prior_completed_translation"})
            budget.finalize("translation-settled", cost, {"cost_usd": str(cost)})
            atomic_json(receipt, record)
            self._budgets[job.job_id] = budget
        return self.state(job)

    def authorize_recovery(self, job, policy_fingerprint: str, prior_layout_cost_usd: str, *, missing_pages=None,
                           direct_continuation_identity_sha256=None):
        """Reserve a new explicit operation while retaining known predecessor spend."""
        ceiling = verified_page_ceiling()
        prior = money(prior_layout_cost_usd)
        if direct_continuation_identity_sha256 is not None and (missing_pages is None
                or type(direct_continuation_identity_sha256) is not str
                or len(direct_continuation_identity_sha256) != 64
                or any(c not in '0123456789abcdef' for c in direct_continuation_identity_sha256)):
            fail("budget_binding_changed", 409)
        accountant, folder, cost = self._source(job)
        if accountant.hard_budget:
            if accountant.budget_context is None:
                fail("durable_accounting_required", 503)
            return self.state(job)
        if missing_pages is not None and (type(missing_pages) is not list or not set(missing_pages) <= set(job.selected_pages)
                or sorted(set(missing_pages)) != missing_pages):
            fail("invalid_page_selection", 409)
        folder = folder / ("revalidation_capacity_v2" if direct_continuation_identity_sha256 is not None
                           else "revalidation_capacity_v1" if missing_pages is not None else "recovery_capacity_v2")
        cap = cost + prior + ceiling * len(missing_pages if missing_pages is not None else job.selected_pages)
        identity = {"job_id": job.job_id, "run_id": job.run_id, "binding": dict(job.binding),
            "original_accounting_identity": accountant.run_identity,
            "automatic_recovery_policy_fingerprint": policy_fingerprint,
            "prior_layout_cost_usd": str(prior)}
        record = {"authorization_nonce": "explicit_layout_capacity_recovery_v1",
            "cap_usd": str(cap), "translation_cost_usd": str(cost),
            "prior_layout_cost_usd": str(prior), "binding": dict(job.binding),
            "identity": identity, "authorization_kind": "server_owned_explicit_recovery_ceiling"}
        if missing_pages is not None:
            identity["missing_pages"] = missing_pages
            record["missing_pages"] = missing_pages
        if direct_continuation_identity_sha256 is not None:
            identity["direct_continuation_identity_sha256"] = direct_continuation_identity_sha256
            record["direct_continuation_identity_sha256"] = direct_continuation_identity_sha256
        with self._lock:
            receipt = folder / "authorization.json"
            if receipt.exists():
                if decode(receipt.read_bytes()) != record:
                    fail("budget_already_authorized", 409)
                return self.state(job)
            try:
                folder.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                fail("budget_authorization_incomplete", 409)
            budget = ReservationBudget(folder / "budget.json", cap_usd=cap, identity=identity)
            budget.reserve("translation-settled", cost, {"kind": "prior_completed_translation"})
            budget.finalize("translation-settled", cost, {"cost_usd": str(cost)})
            budget.reserve("layout-predecessor-settled", prior, {"kind": "prior_completed_layout"})
            budget.finalize("layout-predecessor-settled", prior, {"cost_usd": str(prior)})
            atomic_json(receipt, record)
            self._budgets[(job.job_id, folder.name)] = budget
        return self.state(job)

    def policy(self, job):
        accountant, folder, _ = self._source(job)
        with self._lock:
            budget = self._budget(job, accountant, folder)
        if budget is None or getattr(budget, "blocked", False):
            fail("budget_authorization_required", 409)
        ceiling = verified_page_ceiling()
        return LayoutSuggestionPolicy(MODEL, str(ceiling), str(ceiling * len(job.selected_pages)))

    def accountant(self, job, operation_nonce, operation_dir, policy):
        accountant, folder, _ = self._source(job)
        with self._lock:
            budget = self._budget(job, accountant, folder)
        if budget is None:
            fail("budget_authorization_required", 409)
        arguments = layout_accounting_policy().accounting_arguments()
        # A caller-pinned 8k manual policy retains its smaller request bound;
        # a fresh included operation uses the 32k default. Saved operations
        # return before this factory is consulted.
        arguments["dispatch_limits"][f"openai:layout_suggestion:{MODEL}"]["max_output_tokens"] = policy.max_output_tokens
        return DispatchAccounting(operation_dir / "accounting", run_identity={"job_id": job.job_id,
            "run_id": job.run_id, "operation_nonce": operation_nonce, "binding": dict(job.binding)},
            budget_context=budget, **arguments)

    @staticmethod
    def provider(job, policy):
        from .openai_client import OpenAIResponsesClient
        return OpenAIResponsesClient(model=policy.model, max_transport_retries=0)
