"""Bounded source-image layout stage for fresh ordinary browser translations.

Translation remains the existing ordinary protocol. This stage keeps its raw
DOCX and writer map, makes at most one proposal request per selected source
page, and publishes only a separately verified unreviewed candidate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .ordinary_layout_contracts import encode, fail
from .run_workspace_lock import run_workspace_slot
from . import saved_docx_layout_service as storage
from .translation_policy import ORDINARY_AUTO_LAYOUT_POLICY

_POLICY_RE = re.compile(r"source_image_unreviewed_v1:([a-f0-9]{64})\Z")


def frozen_automatic_layout_policy() -> str:
    """Freeze local price, request and validation versions before translation."""
    from .ordinary_layout_accounting import layout_accounting_policy
    from .ordinary_layout_contracts import PROPOSAL_VERSION
    from .ordinary_layout_manager import INSTRUCTIONS

    accounting = layout_accounting_policy()
    identity = {"version": ORDINARY_AUTO_LAYOUT_POLICY,
        "proposal_version": PROPOSAL_VERSION,
        "instructions_sha256": hashlib.sha256(INSTRUCTIONS.encode("utf-8")).hexdigest(),
        "pricing_catalog": json.loads(accounting._pricing_json),
        "dispatch_limits": json.loads(accounting._limits_json)}
    return ORDINARY_AUTO_LAYOUT_POLICY + ":" + hashlib.sha256(encode(identity)).hexdigest()


def valid_automatic_layout_policy(value: str) -> bool:
    return type(value) is str and _POLICY_RE.fullmatch(value) is not None


def _nonce(kind: str, payload: dict) -> str:
    return hashlib.sha256(kind.encode("ascii") + b":" + encode(payload)).hexdigest()[:32]


def _durable_folder(identity: dict) -> Path:
    run_dir = Path(identity["run_dir"]).expanduser().resolve()
    return storage._mkdir(run_dir / "ordinary_auto_layout")


def _read_record(path: Path) -> dict:
    from .ordinary_layout_contracts import decode
    value = decode(storage._read(path, 8 * 1024 * 1024))
    if type(value) is not dict:
        fail("automatic_record_changed", 409)
    return value


def _reused_candidate(manager, folder: Path, identity: dict, record: dict, job) -> dict:
    if (record.get("identity") != identity or type(record.get("review_id")) is not str
            or type(record.get("candidate_id")) is not str
            or type(record.get("origin_job_id")) is not str):
        fail("automatic_candidate_changed", 409)
    candidate = manager.service.saved.verified_unreviewed_candidate(
        record["review_id"], record["candidate_id"])
    if (candidate.docx_sha256 != record.get("sha256")
            or candidate.source_map_sha256 != record.get("source_map_sha256")
            or hashlib.sha256(encode(candidate.receipt)).hexdigest() != record.get("receipt_sha256")
            or candidate.generation != record.get("generation")
            or candidate.current_generation != candidate.generation
            or candidate.source_pdf_sha256 != identity["source_pdf_sha256"]
            or candidate.raw_docx_sha256 != identity["raw_docx_sha256"]
            or candidate.raw_source_map_sha256 != identity["raw_source_map_sha256"]
            or list(candidate.selected_pages) != identity["selected_pages"]
            or candidate.policy_fingerprint != identity["policy_fingerprint"]
            or candidate.receipt.get("document_reviewed") is not False):
        fail("automatic_candidate_changed", 409)
    copy_path = folder / "output.docx"
    path = manager.service.root / record["origin_job_id"] / "automatic" / "output.docx"
    if (storage._read(copy_path, storage.DOCX_MAX_BYTES) != candidate.docx_bytes
            or storage._read(path, storage.DOCX_MAX_BYTES) != candidate.docx_bytes):
        fail("automatic_candidate_changed", 409)
    if job.job_id != record["origin_job_id"]:
        manager.service.adopt_automatic_alias(job, record["origin_job_id"], record["candidate_id"])
    from .joblog_flow import count_words_from_docx
    count = count_words_from_docx(path)
    return {"output_path": str(path),
        "review_copy_path": str(manager.service.automatic_review_copy(job.job_id)),
        "sha256": candidate.docx_sha256,
        "word_count": count, "candidate_id": candidate.candidate_id,
        "source_map_sha256": candidate.source_map_sha256,
        "policy_fingerprint": candidate.policy_fingerprint,
        "delivery_kind": "automatic_unreviewed", "reviewed": False,
        "reused_durable_candidate": True, "layout_costs": record["layout_costs"]}


def _proposal_evidence(manager, job_id: str, baseline_id: str, review_id: str, operation_nonce: str,
                       selected_pages: tuple[int, ...], policy: str) -> dict:
    """Record hashes and settled usage, never private source/target text."""
    from .saved_docx_layout_service import _read as bounded_read
    image_hashes = {page: hashlib.sha256(manager.service.saved.image(review_id, page)).hexdigest()
                    for page in selected_pages}
    pages = []
    with manager.service.scope(job_id) as folder:
        operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
        intent = bounded_read(operation / "intent.json", 8 * 1024 * 1024)
        summary = bounded_read(operation / "accounting_summary.json", 8 * 1024 * 1024)
        from .ordinary_layout_service import _read as verified_record
        request_policy = verified_record(operation / "intent.json")["request"]["policy"]
        for page in selected_pages:
            response = bounded_read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024)
            pages.append({"source_page_number": page,
                "source_image_sha256": image_hashes[page],
                "response_sha256": hashlib.sha256(response).hexdigest()})
    return {"version": "ordinary_auto_layout_evidence_v1", "document_reviewed": False,
        "rendered_layout_acceptance": "not_evaluated", "policy_fingerprint": policy.split(":", 1)[1],
        "operation_nonce": operation_nonce, "intent_sha256": hashlib.sha256(intent).hexdigest(),
        "accounting_summary_sha256": hashlib.sha256(summary).hexdigest(),
        "requested_model": request_policy["model"], "effort": request_policy["effort"],
        "proposal_schema_version": "ordinary_layout_proposal_v1", "pages": pages}


def _recover_settled_result(manager, pointer: dict, selected_pages: list[int]) -> None:
    """Complete a saved, fully accounted operation locally after a crash."""
    from .ordinary_layout_contracts import decode, normalize_proposals, OrdinaryLayoutError
    from .ordinary_layout_service import _read as verified_record, _write as verified_write
    from .saved_docx_layout import inspect_docx
    origin, baseline_id = pointer["origin_job_id"], pointer["baseline_id"]
    operation_nonce, initial = pointer["operation_nonce"], pointer["initial_generation"]
    with manager.service.scope(origin) as folder:
        operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
        if (operation / "result.json").exists():
            return
        if (operation / "cancel.json").exists() or not (operation / "accounting_summary.json").exists():
            return
        intent = verified_record(operation / "intent.json")
        summary = verified_record(operation / "accounting_summary.json")
        if (intent.get("baseline_id") != baseline_id or intent.get("review_id") != pointer["review_id"]
                or intent.get("operation_nonce") != operation_nonce
                or intent.get("request", {}).get("expected_generation") != initial
                or intent.get("request", {}).get("page_numbers") != selected_pages
                or summary.get("coverage_status") != "complete"
                or summary.get("cost_usd") is None
                or summary.get("unknown_cost_count") != 0
                or summary.get("in_flight_count") != 0
                or summary.get("provider_dispatch_count") != len(selected_pages)
                or summary.get("attempt_count") != len(selected_pages)):
            return
        proposals = []
        for page in selected_pages:
            path = operation / f"page-{page:04d}.response.json"
            if not path.exists():
                return
            raw = storage._read(path, 2 * 1024 * 1024)
            try:
                proposal = decode(raw)
            except ValueError:
                return
            if type(proposal) is not dict or proposal.get("page_number") != page:
                return
            proposals.append(proposal)
        reviewed = storage._read(folder / "baselines" / baseline_id / "reviewed.docx", storage.DOCX_MAX_BYTES)
        stored_decisions = (verified_record(operation / "proposed_decisions.json")
            if (operation / "proposed_decisions.json").exists() else None)
    current = manager.service.state(origin)
    if (current["baseline_id"] != baseline_id or current["review"]["review_id"] != pointer["review_id"]
            or current["generation"] not in {initial, initial + 1}):
        fail("automatic_generation_changed", 409)
    try:
        decisions = normalize_proposals(inspect_docx(reviewed, current["review"]["target_lang"]),
            current["review"], proposals)
    except (OrdinaryLayoutError, ValueError):
        return
    if stored_decisions is not None and stored_decisions != decisions:
        return
    if current["generation"] == initial:
        with manager.service.scope(origin) as folder:
            operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
            if not (operation / "proposed_decisions.json").exists():
                verified_write(operation / "proposed_decisions.json", decisions)
        applied = manager.service.apply_suggestion(origin, operation_nonce, initial, decisions,
            baseline_id=baseline_id)
        completed_generation = applied["generation"]
    else:
        if stored_decisions is None or current["review"]["decisions"] != decisions:
            return
        completed_generation = current["generation"]
    result = {"operation_nonce": operation_nonce, "baseline_id": baseline_id,
        "generation": completed_generation, "status": "applied_unreviewed",
        "completed_pages": selected_pages, "retry_dispatch_allowed": False,
        "applied_unreviewed": True,
        "accounting": {"cost_usd": summary.get("cost_usd"),
            "known_cost_usd": summary.get("known_cost_usd"),
            "unknown_cost_count": summary.get("unknown_cost_count"), "complete": True}}
    manager.service.finish_suggestion(origin, operation_nonce, result, baseline_id=baseline_id)


def _finish_saved_proposals(manager, folder: Path, identity: dict, pointer: dict,
                            raw_map: dict, frozen_policy: str, job,
                            cancel_requested, begin_publication) -> dict:
    """Rebuild and verify only from an already-settled, saved operation."""
    origin = pointer["origin_job_id"]
    baseline_id = pointer["baseline_id"]
    operation_nonce = pointer["operation_nonce"]
    review_id = pointer["review_id"]
    policy_hash = identity["policy_fingerprint"]
    if (pointer.get("identity_sha256") != hashlib.sha256(encode(identity)).hexdigest()
            or pointer.get("selected_pages") != identity["selected_pages"]):
        fail("automatic_operation_identity_changed", 409)
    if cancel_requested(job.job_id):
        fail("automatic_layout_cancelled", 409)
    _recover_settled_result(manager, pointer, identity["selected_pages"])
    outcome = manager.service.suggestion(origin, operation_nonce,
        expected_baseline_id=baseline_id, expected_generation=pointer["initial_generation"],
        page_numbers=identity["selected_pages"])
    if (outcome.get("status") != "applied_unreviewed"
            or outcome.get("completed_pages") != identity["selected_pages"]
            or not outcome.get("accounting", {}).get("complete")):
        fail("automatic_operation_pending_or_uncertain", 409)
    current = manager.service.state(origin)
    review = current["review"]
    if (current["baseline_id"] != baseline_id or review["review_id"] != review_id
            or review["generation"] != outcome["generation"]):
        fail("automatic_generation_changed", 409)
    evidence = _proposal_evidence(manager, origin, baseline_id, review_id, operation_nonce,
        tuple(identity["selected_pages"]), frozen_policy)
    manager.service.saved.attach_ordinary_binding(review_id, raw_map,
        tuple(identity["selected_pages"]), policy_hash, evidence,
        expected_generation=review["generation"])
    build_nonce = _nonce("automatic_build", {"operation_nonce": operation_nonce,
        "generation": review["generation"], "policy": policy_hash})
    built = manager.service.saved.build_unreviewed_candidate(review_id,
        review["generation"], build_nonce)
    if cancel_requested(job.job_id) or not begin_publication(job.job_id):
        fail("automatic_layout_cancelled", 409)
    manager.service.publish_automatic_candidate(origin, expected_baseline_id=baseline_id,
        operation_nonce=operation_nonce, candidate_id=built["candidate_id"],
        expected_generation=review["generation"], policy_fingerprint=policy_hash)
    artifact = manager.service.resolve_delivery(origin, 0)
    candidate = manager.service.saved.verified_unreviewed_candidate(review_id, built["candidate_id"])
    costs = manager.layout_costs(origin)
    if not costs["complete"]:
        fail("accounting_unsettled", 409)
    with run_workspace_slot(folder):
        copy_path = folder / "output.docx"
        if copy_path.exists():
            if storage._read(copy_path, storage.DOCX_MAX_BYTES) != candidate.docx_bytes:
                fail("automatic_candidate_changed", 409)
        else:
            storage._atomic(copy_path, candidate.docx_bytes)
        record = {"identity": identity, "origin_job_id": origin,
            "review_id": review_id, "candidate_id": built["candidate_id"],
            "generation": candidate.generation, "sha256": candidate.docx_sha256,
            "source_map_sha256": candidate.source_map_sha256,
            "receipt_sha256": hashlib.sha256(encode(candidate.receipt)).hexdigest(),
            "layout_costs": costs}
        marker = folder / "candidate.json"
        if marker.exists():
            if _read_record(marker) != record:
                fail("automatic_candidate_changed", 409)
        else:
            storage._atomic(marker, encode(record))
    if job.job_id != origin:
        manager.service.adopt_automatic_alias(job, origin, built["candidate_id"])
    return {"output_path": str(artifact.path),
        "review_copy_path": str(manager.service.automatic_review_copy(job.job_id)),
        "sha256": artifact.sha256,
        "word_count": artifact.word_count, "candidate_id": built["candidate_id"],
        "source_map_sha256": built["source_map_sha256"], "policy_fingerprint": policy_hash,
        "delivery_kind": artifact.kind, "reviewed": False, "layout_costs": costs}


def run_automatic_layout(manager, accounting, job_id: str, frozen_policy: str,
                         *, cancel_requested=None, begin_publication=None) -> dict:
    """Run the included bounded layout stage against a pinned ordinary job."""
    if not valid_automatic_layout_policy(frozen_policy):
        fail("automatic_policy_invalid", 409)
    cancel_requested = cancel_requested or (lambda _job_id: False)
    begin_publication = begin_publication or (lambda _job_id: True)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    policy_hash = frozen_policy.split(":", 1)[1]
    job = manager._job(job_id)
    if not job.page_groups or tuple(sorted(job.page_groups)) != job.selected_pages:
        fail("page_mapping_required", 409)
    raw_map = accounting.jobs.trusted_ordinary_raw_map(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    from .ordinary_auto_layout_artifacts import bind_raw_page_map
    mapped = bind_raw_page_map(job.original_docx, raw_map,
        source_pdf_sha256=job.binding["source_sha256"],
        selected_pages=job.selected_pages, target_lang=job.target_lang)
    if mapped.page_ids != {p: tuple(ids) for p, ids in job.page_groups.items()}:
        fail("page_mapping_changed", 409)
    baseline = accounting.jobs.trusted_ordinary_baseline_identity(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    identity = {key: baseline[key] for key in ("run_id", "source_pdf_sha256", "raw_docx_sha256",
        "raw_source_map_bytes_sha256", "selected_pages", "target_lang", "runtime_mode", "workspace_id")}
    identity.update(raw_source_map_sha256=mapped.raw_source_map_sha256,
                    raw_snapshot_fingerprint=mapped.fingerprint, policy_fingerprint=policy_hash)
    folder = _durable_folder(baseline)
    recover_pointer = None
    with run_workspace_slot(folder):
        intent_path = folder / "intent.json"
        if intent_path.exists():
            if _read_record(intent_path) != identity:
                fail("automatic_operation_identity_changed", 409)
            candidate_path = folder / "candidate.json"
            if candidate_path.exists():
                if cancel_requested(job_id) or not begin_publication(job_id):
                    fail("automatic_layout_cancelled", 409)
                return _reused_candidate(manager, folder, identity, _read_record(candidate_path), job)
            pointer_path = folder / "operation.json"
            if pointer_path.exists():
                recover_pointer = _read_record(pointer_path)
        else:
            storage._atomic(intent_path, encode(identity))
    if recover_pointer is not None:
        # Paid operation exists. Only local assembly of a settled saved result
        # may continue; pending/unknown results never trigger another request.
        return _finish_saved_proposals(manager, folder, identity, recover_pointer, raw_map, frozen_policy, job,
            cancel_requested, begin_publication)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    if frozen_policy != frozen_automatic_layout_policy():
        fail("automatic_policy_changed", 409)
    accounting.authorize_automatic(job, policy_hash)
    prepare_nonce = _nonce("automatic_prepare", {"job_id": job_id,
        "raw_snapshot": mapped.fingerprint, "policy": policy_hash})
    prepared = manager.prepare(job_id, prepare_nonce)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    baseline_id = prepared["baseline_id"]
    generation = prepared["generation"]
    operation_nonce = _nonce("automatic_suggest", {"job_id": job_id,
        "baseline_id": baseline_id, "generation": generation,
        "raw_snapshot": mapped.fingerprint, "policy": policy_hash})
    pointer = {"identity_sha256": hashlib.sha256(encode(identity)).hexdigest(),
        "origin_job_id": job_id, "baseline_id": baseline_id,
        "review_id": prepared["review"]["review_id"], "initial_generation": generation,
        "operation_nonce": operation_nonce, "selected_pages": list(job.selected_pages)}
    with run_workspace_slot(folder):
        pointer_path = folder / "operation.json"
        if pointer_path.exists():
            if _read_record(pointer_path) != pointer:
                fail("automatic_operation_identity_changed", 409)
        else:
            storage._atomic(pointer_path, encode(pointer))
    if cancel_requested(job_id):
        manager.service.cancel_suggestion(job_id, operation_nonce, generation,
            expected_baseline_id=baseline_id)
        fail("automatic_layout_cancelled", 409)
    outcome = manager.suggest(job_id, generation, operation_nonce, list(job.selected_pages),
        expected_baseline_id=baseline_id, external_cancel_requested=cancel_requested)
    if (outcome.get("status") != "applied_unreviewed"
            or outcome.get("completed_pages") != list(job.selected_pages)
            or not outcome.get("accounting", {}).get("complete")):
        fail("automatic_proposal_incomplete", 409)
    return _finish_saved_proposals(manager, folder, identity, pointer, raw_map, frozen_policy, job,
        cancel_requested, begin_publication)


def cancel_automatic_layout(manager, accounting, job_id: str) -> None:
    """Bridge an active browser Cancel to the durable page-boundary marker."""
    baseline = accounting.jobs.trusted_ordinary_baseline_identity(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    pointer_path = _durable_folder(baseline) / "operation.json"
    if not pointer_path.exists():
        return
    pointer = _read_record(pointer_path)
    if pointer.get("origin_job_id") != job_id:
        return  # A reused operation has no new page dispatch to cancel.
    manager.service.cancel_suggestion(job_id, pointer["operation_nonce"],
        pointer["initial_generation"], expected_baseline_id=pointer["baseline_id"])
