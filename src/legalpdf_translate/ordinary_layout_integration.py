"""Owned ordinary layout and immutable delivery boundaries for browser consumers."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
from pathlib import Path
import threading

from .ordinary_layout_contracts import fail, generation, nonce
from .ordinary_layout_manager import OrdinaryLayoutManager


class BrowserOrdinaryLayouts:
    def __init__(self, *, context_for):
        self.context_for = context_for
        self._managers = {}
        self._accounting = None
        self._lock = threading.RLock()

    def manager_for(self, request, mode, workspace_id):
        context = self.context_for(request)
        key = (mode, workspace_id)
        with self._lock:
            if key not in self._managers:
                services = context.services
                root_factory = services.ordinary_layout_root or services.saved_docx_layout_root
                if not callable(root_factory):
                    fail("disabled", 503)
                root = root_factory(mode=mode, repo=context.repo_root, identity=context.build_identity)

                def resolve(job_id):
                    job = context.translation_jobs.get_job(job_id)
                    if (not job or job.get("runtime_mode") != mode or job.get("workspace_id") != workspace_id):
                        fail("job_unavailable", 404)
                    from .browser_arabic_review import job_requires_arabic_review
                    existing = self._managers.get(key)
                    frozen = existing is not None and existing.service.state(job_id).get("frozen")
                    if job_requires_arabic_review(job) and not frozen:
                        context.arabic_reviews.require_resolved(runtime_mode=mode, workspace_id=workspace_id, job=job)
                    return context.translation_jobs.trusted_ordinary_layout_job(job_id,
                        runtime_mode=mode, workspace_id=workspace_id)

                factory = services.ordinary_layout_factory or OrdinaryLayoutManager
                from .ordinary_layout_accounting import OrdinaryLayoutAccounting
                if self._accounting is None:
                    self._accounting = OrdinaryLayoutAccounting(context.translation_jobs)
                accounting = self._accounting
                manager = factory(root, mode=mode, workspace_id=workspace_id,
                    job_resolver=resolve, provider_factory=services.ordinary_layout_provider_factory or accounting.provider,
                    accounting_factory=services.ordinary_layout_accounting_factory or accounting.accountant,
                    suggestion_policy=services.ordinary_layout_policy or accounting.policy,
                    budget_state=accounting.state,
                    output_review_guard=lambda job_id, artifact_id, generation, baseline_id: verify_open_review_copy(
                        self._managers[key], job_id, artifact_id, generation, baseline_id))
                self._managers[key] = manager
            return self._managers[key]

    def authorize(self, manager, job_id, data):
        generation(data["expected_generation"])
        nonce(data["baseline_id"])
        if type(data["cap_usd"]) is not str:
            fail("invalid_budget_cap")
        job = manager._job(job_id)
        state = manager.service.assert_current(job)
        if state["baseline_id"] != data["baseline_id"] or state["generation"] != data["expected_generation"]:
            fail("baseline_stale", 409)
        if state.get("frozen"):
            fail("delivery_frozen", 409)
        self._accounting.authorize(job, data["authorization_nonce"], data["cap_usd"])
        return manager.state(job_id)


def delivery_job_snapshot(manager, job, *, mutation=False, baseline_id=None,
                          expected_delivery_generation=None, freeze_nonce=None):
    """Copy the seed; the provider completion and original save seed remain intact."""
    snapshot = deepcopy(job)
    state = manager.state(job["job_id"])
    snapshot["ordinary_layout"] = state
    if state["status"] == "unprepared":
        if baseline_id is not None or expected_delivery_generation is not None or freeze_nonce:
            fail("delivery_unprepared", 409)
        return snapshot, None
    if mutation and (baseline_id != state.get("baseline_id") or type(expected_delivery_generation) is not int):
        fail("delivery_precondition_required", 409)
    expected = expected_delivery_generation if mutation else state.get("delivery_generation")
    artifact = manager.resolve_delivery(job["job_id"], expected, freeze_nonce, require_settled=mutation)
    from .saved_docx_layout_service import _read, DOCX_MAX_BYTES
    raw = _read(artifact.path, DOCX_MAX_BYTES)
    if hashlib.sha256(raw).hexdigest() != artifact.sha256:
        fail("delivery_changed", 409)
    seed = snapshot.get("result", {}).get("save_seed")
    if not isinstance(seed, dict) or str(seed.get("run_id", "")) != artifact.run_id:
        fail("delivery_run_mismatch", 409)
    seed.update(output_docx=str(artifact.path), partial_docx=None, word_count=artifact.word_count, profit=None)
    snapshot["artifacts"]["output_docx"] = str(artifact.path)
    snapshot["delivery"] = {"generation": artifact.generation, "selection_id": artifact.selection_id,
        "sha256": artifact.sha256, "word_count": artifact.word_count, "kind": artifact.kind, "frozen": artifact.frozen}
    costs = manager.layout_costs(job["job_id"])
    snapshot["layout_costs"] = costs
    if costs["operations"]:
        original_cost = seed.get("estimated_api_cost")
        seed["estimated_api_cost"] = (float(Decimal(str(original_cost)) + Decimal(costs["cost_usd"]))
            if original_cost is not None and costs["complete"] else None)
        seed["api_cost"] = float(Decimal(str(seed.get("api_cost") or 0)) + Decimal(costs["known_cost_usd"]))
    return snapshot, artifact


def owned_form_values(job, form_values):
    """User-entered fee/case fields cannot replace server-owned run/accounting identity."""
    result = dict(form_values)
    seed = job["result"]["save_seed"]
    for key in ("run_id", "target_lang", "lang", "pages"):
        if key in seed:
            result[key] = seed[key]
    if job.get("layout_costs", {}).get("operations"):
        for key in ("api_cost", "estimated_api_cost"):
            result[key] = seed.get(key) if seed.get(key) is not None else ""
    return result


def open_layout_artifact(manager, job_id, data):
    """Explicit Word action against a verified owned copy; no arbitrary path input."""
    artifact = manager.review_artifact(job_id, data["artifact_id"], data["expected_generation"],
        expected_baseline_id=data["baseline_id"])
    from . import saved_docx_layout_service as storage
    folder = storage._mkdir(manager.service.root / "native_review" / job_id / data["baseline_id"] / artifact.artifact_id)
    path = folder / "review.docx"
    if path.exists():
        if storage._read(path, storage.DOCX_MAX_BYTES) != artifact.docx_bytes:
            fail("review_copy_changed", 409)
    else:
        storage._atomic(path, artifact.docx_bytes)
    from .word_automation import open_docx_in_word
    result = open_docx_in_word(path)
    result = {"ok": bool(result.ok), "action": str(result.action), "message": str(result.message),
              "failure_code": str(result.failure_code), "failure_phase": str(result.failure_phase)}
    return {"artifact_id": artifact.artifact_id, "generation": artifact.generation,
        "sha256": hashlib.sha256(artifact.docx_bytes).hexdigest(), "open_result": result}


def verify_open_review_copy(manager, job_id, artifact_id, generation, baseline_id):
    from . import saved_docx_layout_service as storage
    artifact = manager.review_artifact(job_id, artifact_id, generation, expected_baseline_id=baseline_id)
    path = manager.service.root / "native_review" / job_id / baseline_id / artifact_id / "review.docx"
    if path.exists() and storage._read(path, storage.DOCX_MAX_BYTES) != artifact.docx_bytes:
        fail("review_copy_changed", 409)
