"""Explicit local layout authorization sharing one overall run budget."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import threading

from .budget_reservations import ReservationBudget, money, atomic_json
from .ordinary_layout_contracts import LayoutSuggestionPolicy, fail, nonce, decode
from .usage_accounting import DispatchAccounting

PAGE_CEILING = Decimal("0.812")
MODEL = "gpt-5.2"
ACTUAL_MODEL = "gpt-5.2-2025-12-11"


def layout_accounting_policy():
    from .accounting_policy import OrdinaryAccountingPolicy
    source = "https://developers.openai.com/api/docs/models/gpt-5.2"
    rates = {"input_per_1m": 1.75, "cached_input_per_1m": .175, "output_per_1m": 14,
        "provider": "openai", "pricing_model": MODEL, "service_tier": "default",
        "billing_scope": "openai_public_api", "currency": "USD", "source_url": source}
    policy = OrdinaryAccountingPolicy.from_mapping(pricing={"snapshot_id": "layout_standard_2026_09_27",
        "verified_at": "2026-09-27", "source": source,
        "models": {f"openai:{name}|default|openai_public_api|USD": {**rates, "pricing_model": name}
                   for name in (MODEL, ACTUAL_MODEL)}},
        limits={f"openai:layout_suggestion:{MODEL}": {"requested_model": MODEL,
            "allowed_actual_models": [ACTUAL_MODEL], "requested_service_tier": "default",
            "allowed_actual_service_tiers": ["default"], "billing_scope": "openai_public_api", "currency": "USD",
            "allowed_base_urls": ["https://api.openai.com/v1"], "max_input_tokens": 400000,
            "max_image_input_tokens": 10000, "max_image_count": 1, "image_bound_verified": True,
            "image_bound_source_url": "https://developers.openai.com/api/docs/guides/images-vision",
            "image_bound_verified_at": "2026-09-27",
            "image_bound_basis": "GPT-5.2 high detail: at most 6144 patches x 1.2; rounded upward below 10000 tokens",
            "max_output_tokens": 8000, "bound_source_url": source, "bound_verified_at": "2026-09-27"}})
    return OrdinaryAccountingPolicy(policy._pricing_json, policy._limits_json, date(2026, 9, 27))


class OrdinaryLayoutAccounting:
    def __init__(self, jobs):
        self.jobs = jobs
        self._lock = threading.RLock()
        self._budgets = {}

    def _source(self, job):
        with self.jobs._lock:
            record = self.jobs._jobs.get(job.job_id)
            if record is None or record.status != "completed":
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
            base.update(translation_cost_usd=str(cost), minimum_cap_usd=str(cost + PAGE_CEILING),
                suggested_cap_usd=str(cost + PAGE_CEILING * len(job.selected_pages)),
                authorization_available=budget is None, authorized=budget is not None,
                shared_existing_cap=bool(accountant.hard_budget))
            if budget is not None:
                status = budget.status() if callable(getattr(budget, "status", None)) else {}
                base.update({k: status[k] for k in ("cap_usd", "remaining_usd", "blocked") if k in status})
                base["cap_usd"] = str(budget.cap_usd)
                if not accountant.hard_budget:
                    base["authorization_nonce"] = decode((folder / "authorization.json").read_bytes())["authorization_nonce"]
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

    def policy(self, job):
        accountant, folder, _ = self._source(job)
        with self._lock:
            budget = self._budget(job, accountant, folder)
        if budget is None or getattr(budget, "blocked", False):
            fail("budget_authorization_required", 409)
        if layout_accounting_policy().accounting_arguments()["pricing_snapshot"] is None:
            fail("pricing_reference_expired", 503)
        return LayoutSuggestionPolicy(MODEL, str(PAGE_CEILING), str(PAGE_CEILING * len(job.selected_pages)))

    def accountant(self, job, operation_nonce, operation_dir, policy):
        accountant, folder, _ = self._source(job)
        with self._lock:
            budget = self._budget(job, accountant, folder)
        if budget is None:
            fail("budget_authorization_required", 409)
        return DispatchAccounting(operation_dir / "accounting", run_identity={"job_id": job.job_id,
            "run_id": job.run_id, "operation_nonce": operation_nonce, "binding": dict(job.binding)},
            budget_context=budget, **layout_accounting_policy().accounting_arguments())

    @staticmethod
    def provider(job, policy):
        from .openai_client import OpenAIResponsesClient
        return OpenAIResponsesClient(model=policy.model, max_transport_retries=0)
