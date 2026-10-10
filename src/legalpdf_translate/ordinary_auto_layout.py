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
from decimal import Decimal

from .ordinary_layout_contracts import encode, fail
from .run_workspace_lock import run_workspace_slot
from . import saved_docx_layout_service as storage
from .translation_policy import ORDINARY_AUTO_LAYOUT_POLICY

_POLICY_RE = re.compile(r"source_image_unreviewed_v1:([a-f0-9]{64})\Z")


def frozen_automatic_layout_policy() -> str:
    """Freeze local price, request and validation versions before translation."""
    from .ordinary_layout_accounting import layout_accounting_policy
    from .ordinary_layout_contracts import PROPOSAL_VERSION_V3
    from .ordinary_layout_manager import INSTRUCTIONS

    accounting = layout_accounting_policy()
    identity = {"version": ORDINARY_AUTO_LAYOUT_POLICY,
        "proposal_version": PROPOSAL_VERSION_V3,
        "automatic_writer_version": "saved_docx_layout_writer_source_layout_v7",
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


def _recovery_folder(root: Path) -> Path:
    """One explicit successor for this checkpoint, independent of job IDs."""
    return storage._mkdir(root / "recoveries" / "layout_capacity_v2")


def _direct_revalidation(root: Path, result: dict, policy: dict) -> bool:
    """Choose the durable lineage before admitting a fresh direct successor."""
    capacity = root / "recoveries" / "layout_capacity_v2"
    direct = root / "recoveries" / "layout_direct_revalidation_v1"
    markers = ("intent.json", "operation.json", "candidate.json")
    has_capacity = any((capacity / name).exists() for name in markers)
    has_direct = any((direct / name).exists() for name in markers)
    if has_capacity and has_direct:
        fail("automatic_recovery_predecessor_changed", 409)
    return has_direct or (not has_capacity
        and result.get("error_code") in {"ordinary_layout_page_break_requires_flow",
                                       "ordinary_layout_proposal_coverage",
                                       "ordinary_layout_invalid_proposal_decisions"}
        and policy.get("max_output_tokens") == 32000
        and policy.get("timeout_seconds") == 480.0)


def _failed_predecessor(manager, root: Path, identity: dict, old_policy: str, *, expected_identity=None, completed_marker=None) -> dict:
    """Prove the old dispatch is final and billed before a new paid operation."""
    if not valid_automatic_layout_policy(old_policy):
        fail("automatic_recovery_predecessor_invalid", 409)
    intent_path, pointer_path = root / "intent.json", root / "operation.json"
    if not intent_path.is_file() or not pointer_path.is_file() or (root / "candidate.json").exists():
        fail("automatic_recovery_predecessor_unavailable", 409)
    old_intent = _read_record(intent_path)
    expected = expected_identity or dict(identity, policy_fingerprint=old_policy.split(":", 1)[1])
    if old_intent != expected:
        fail("automatic_recovery_predecessor_changed", 409)
    pointer = _read_record(pointer_path)
    if (pointer.get("identity_sha256") != hashlib.sha256(encode(old_intent)).hexdigest()
            or pointer.get("selected_pages") != identity["selected_pages"]):
        fail("automatic_recovery_predecessor_changed", 409)
    from .ordinary_layout_contracts import identifier, nonce
    from .ordinary_layout_service import _read as verified_record
    origin = identifier(pointer.get("origin_job_id"))
    baseline_id = nonce(pointer.get("baseline_id"))
    operation_nonce = nonce(pointer.get("operation_nonce"))
    origin_folder = manager.service.root / origin
    operation = origin_folder / "baselines" / baseline_id / "suggestions" / operation_nonce
    result_path, summary_path = operation / "result.json", operation / "accounting_summary.json"
    completed_marker = completed_marker or root / "recoveries" / "layout_direct_revalidation_v1" / "candidate.json"
    if not completed_marker.is_file():
        completed_marker = root / "recoveries" / "layout_revalidation_v1" / "candidate.json"
    if not completed_marker.is_file():
        completed_marker = root / "recoveries" / "layout_capacity_v2" / "candidate.json"
    completed = _read_record(completed_marker) if completed_marker.is_file() else None
    if not result_path.is_file() or not summary_path.is_file():
        fail("automatic_recovery_predecessor_unsettled", 409)
    with manager.service.scope(origin) as scoped:
        selections = manager.service._selections(scoped)
        if completed is None and ((scoped / "automatic.json").exists()
                or (scoped / "frozen.json").exists() or selections):
            fail("automatic_recovery_predecessor_selected", 409)
        if completed is not None and ((scoped / "automatic.json").exists()
                or (scoped / "frozen.json").exists() or selections):
            if (completed.get("origin_job_id") != origin
                    or not (scoped / "automatic.json").exists()):
                fail("automatic_recovery_predecessor_selected", 409)
            automatic = verified_record(scoped / "automatic.json")
            if automatic.get("candidate_id") != completed.get("candidate_id"):
                fail("automatic_recovery_predecessor_selected", 409)
    operation_intent = verified_record(operation / "intent.json")
    result, summary = verified_record(result_path), verified_record(summary_path)
    from .ordinary_layout_contracts import decode
    from .usage_accounting import _state_fingerprint, _summarize
    journal_path = operation / "accounting" / "dispatch_accounting.json"
    journal = decode(storage._read(journal_path, 8 * 1024 * 1024))
    if (type(journal) is not dict or journal.get("fingerprint") != _state_fingerprint(journal)
            or journal.get("run_identity", {}).get("job_id") != origin
            or journal.get("run_identity", {}).get("operation_nonce") != operation_nonce
            or journal.get("run_identity", {}).get("binding", {}).get("source_sha256") != identity["source_pdf_sha256"]
            or journal.get("run_identity", {}).get("binding", {}).get("original_sha256") != identity["raw_docx_sha256"]
            or not isinstance(journal.get("events"), list)
            or _summarize(journal["events"], historical_incomplete=journal.get("historical_incomplete", False),
                pricing_snapshot=journal.get("pricing_snapshot")) != summary):
        fail("automatic_recovery_predecessor_unsettled", 409)
    binding = operation_intent.get("identity", {}).get("binding", {})
    if (operation_intent.get("operation_nonce") != operation_nonce
            or operation_intent.get("baseline_id") != baseline_id
            or operation_intent.get("review_id") != pointer.get("review_id")
            or operation_intent.get("request", {}).get("expected_generation") != pointer.get("initial_generation")
            or operation_intent.get("request", {}).get("page_numbers") != identity["selected_pages"]
            or operation_intent.get("identity", {}).get("run_id") != identity["run_id"]
            or operation_intent.get("identity", {}).get("mode") != identity["runtime_mode"]
            or operation_intent.get("identity", {}).get("workspace_id") != identity["workspace_id"]
            or binding.get("source_sha256") != identity["source_pdf_sha256"]
            or binding.get("original_sha256") != identity["raw_docx_sha256"]
            or (operation_intent.get("request", {}).get("policy", {}).get("max_output_tokens"),
                operation_intent.get("request", {}).get("policy", {}).get("timeout_seconds"))
                not in {(8000, 240.0), (32000, 480.0)}):
        fail("automatic_recovery_predecessor_changed", 409)
    if (result.get("status") != "failed" or result.get("applied_unreviewed")
            or result.get("retry_dispatch_allowed") is not False
            or result.get("accounting", {}).get("cost_usd") != summary.get("cost_usd")
            or result.get("accounting", {}).get("known_cost_usd") != summary.get("known_cost_usd")
            or summary.get("coverage_status") != "complete"
            or summary.get("cost_usd") is None or summary.get("unknown_cost_count") != 0
            or summary.get("in_flight_count") != 0
            or type(summary.get("provider_dispatch_count")) is not int
            or summary["provider_dispatch_count"] < 1):
        fail("automatic_recovery_predecessor_unsettled", 409)
    try:
        cost = Decimal(str(summary["cost_usd"]))
        if not cost.is_finite() or cost < 0 or cost != Decimal(str(summary["known_cost_usd"])):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        fail("automatic_recovery_predecessor_unsettled", 409)
    return {"intent_sha256": hashlib.sha256(storage._read(intent_path, 8 * 1024 * 1024)).hexdigest(),
        "pointer_sha256": hashlib.sha256(storage._read(pointer_path, 8 * 1024 * 1024)).hexdigest(),
        "result_sha256": hashlib.sha256(storage._read(result_path, 8 * 1024 * 1024)).hexdigest(),
        "accounting_summary_sha256": hashlib.sha256(storage._read(summary_path, 8 * 1024 * 1024)).hexdigest(),
        "accounting_journal_sha256": hashlib.sha256(storage._read(journal_path, 8 * 1024 * 1024)).hexdigest(),
        "known_cost_usd": str(cost), "origin_job_id": origin,
        "baseline_id": baseline_id, "operation_nonce": operation_nonce}


def _retained_continuation(manager, root: Path, identity: dict, predecessor: dict, *, direct=False,
                           parent_direct=False, inherited=None):
    """Admit a settled normalization failure; never reuse a partial SDK response."""
    prior_root = root if direct else root / "recoveries" / ("layout_direct_revalidation_v1" if parent_direct else "layout_capacity_v2")
    prior_identity = _read_record(prior_root / "intent.json")
    expected = dict(identity, policy_fingerprint=prior_identity.get("policy_fingerprint"))
    if not direct:
        expected["recovery_predecessor"] = predecessor
    if parent_direct:
        expected["retained_pages"] = {str(p): r["origin"] for p, r in inherited.items()}
    if prior_identity != expected:
        fail("automatic_recovery_predecessor_changed", 409)
    prior = _failed_predecessor(manager, prior_root, identity,
        ORDINARY_AUTO_LAYOUT_POLICY + ":" + prior_identity["policy_fingerprint"],
        expected_identity=expected,
        completed_marker=root / "recoveries" / ("layout_direct_revalidation_v1" if direct else "layout_revalidation_v1") / "candidate.json")
    if direct and prior != predecessor:
        fail("automatic_recovery_predecessor_changed", 409)
    from .ordinary_layout_service import _read as verified_record
    from .ordinary_layout_contracts import decode, normalize_proposals
    from .saved_docx_layout import inspect_docx
    operation = manager.service.root / prior["origin_job_id"] / "baselines" / prior["baseline_id"] / "suggestions" / prior["operation_nonce"]
    result = verified_record(operation / "result.json")
    policy = verified_record(operation / "intent.json")["request"]["policy"]
    allowed_errors = {"ordinary_layout_proposal_coverage", "ordinary_layout_invalid_proposal_decisions"} if parent_direct else {"ordinary_layout_page_break_requires_flow"}
    if direct:
        allowed_errors.add("ordinary_layout_proposal_coverage")
        allowed_errors.add("ordinary_layout_invalid_proposal_decisions")
    if (result.get("error_code") not in allowed_errors or policy.get("max_output_tokens") != 32000
            or direct and policy.get("timeout_seconds") != 480.0):
        fail("automatic_retained_response_unavailable", 409)
    journal = _read_record(operation / "accounting" / "dispatch_accounting.json")
    begins = [e for e in journal["events"] if e.get("event") == "begin"]
    finishes = [e for e in journal["events"] if e.get("event") == "finish"]
    if (not begins or len(begins) != len(finishes)
            or len({e.get("page_number") for e in begins}) != len(begins)):
        fail("automatic_retained_response_unsettled", 409)
    view = manager.service.state(prior["origin_job_id"])["review"]
    # The origin may have retired after Resume. Read its immutable reviewed
    # baseline, whose source/raw ownership was verified above.
    reviewed = storage._read(operation.parent.parent / "reviewed.docx", storage.DOCX_MAX_BYTES)
    snapshot = inspect_docx(reviewed, identity["target_lang"])
    retained = dict(inherited or {})
    if parent_direct:
        # Inherited pages are not new journal calls. Prove their exact copied
        # bytes and origin markers against the independently revalidated parent.
        for page, record in retained.items():
            if (storage._read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024) != record["raw"]
                    or verified_record(operation / f"page-{page:04d}.retained.json") != record["origin"]):
                fail("automatic_retained_response_changed", 409)
    for begin in begins:
        page = begin.get("page_number")
        finish = next((e for e in finishes if e.get("call_id") == begin.get("call_id")), None)
        if (page in retained or page not in identity["selected_pages"] or begin.get("purpose") != "layout_suggestion"
                or begin.get("attempt") != 1 or begin.get("bounds", {}).get("max_output_tokens") != 32000
                or not finish or finish.get("outcome") != "succeeded"
                or finish.get("cost_status") != "available" or finish.get("cost_usd") is None
                or not finish.get("response_id") or finish.get("error_code") is not None):
            fail("automatic_retained_response_unsettled", 409)
        raw = storage._read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024)
        proposal = decode(raw)
        if type(proposal) is not dict or proposal.get("page_number") != page:
            fail("automatic_retained_response_invalid", 409)
        normalize_proposals(snapshot, view, [proposal])
        retained[page] = {"raw": raw, "origin": {"version": "ordinary_retained_proposal_v1",
            "source_page_number": page, "response_sha256": hashlib.sha256(raw).hexdigest(),
            "predecessor": prior, "original_policy_fingerprint": prior_identity["policy_fingerprint"],
            "provider_call_id": begin["call_id"], "locally_revalidated": True}}
    # Missing means genuinely never sent, not a lost or unusable response.
    if any((operation / f"page-{p:04d}.response.json").exists() for p in identity["selected_pages"] if p not in retained):
        fail("automatic_retained_response_changed", 409)
    return prior, retained


def _read_record(path: Path) -> dict:
    from .ordinary_layout_contracts import decode
    value = decode(storage._read(path, 8 * 1024 * 1024))
    if type(value) is not dict:
        fail("automatic_record_changed", 409)
    return value


def _operation_costs(manager, origin: str, identity: dict) -> dict:
    costs = manager.layout_costs(origin)
    if not costs["complete"]:
        fail("accounting_unsettled", 409)
    predecessors = [identity[k] for k in ("recovery_predecessor", "revalidation_predecessor") if k in identity]
    inherited = [p for p in predecessors if p["origin_job_id"] != origin]
    if inherited:
        prior = sum((Decimal(p["known_cost_usd"]) for p in inherited), Decimal(0))
        new = Decimal(costs["known_cost_usd"])
        costs = {"cost_usd": str(prior + new), "known_cost_usd": str(prior + new),
            "complete": True, "operations": costs["operations"] + len(inherited),
            "predecessor_cost_usd": str(prior), "recovery_cost_usd": str(new)}
    return costs


def _reused_candidate(manager, folder: Path, identity: dict, record: dict, job) -> dict:
    if identity.get("retained_pages"):
        pointer = _read_record(folder / "operation.json")
        if pointer.get("retained_pages") != identity["retained_pages"] or pointer.get("identity_sha256") != hashlib.sha256(encode(identity)).hexdigest():
            fail("automatic_retained_response_changed", 409)
        operation = manager.service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
        _verified_retained_pages(operation, identity["retained_pages"])
    if (record.get("identity") != identity or type(record.get("review_id")) is not str
            or type(record.get("candidate_id")) is not str
            or type(record.get("origin_job_id")) is not str):
        fail("automatic_candidate_changed", 409)
    if record.get("layout_costs") != _operation_costs(manager, record["origin_job_id"], identity):
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
        "reused_durable_candidate": True, "layout_costs": record["layout_costs"],
        **({"recovery_predecessor": identity["recovery_predecessor"]}
           if "recovery_predecessor" in identity else {}),
        **({"revalidation_predecessor": identity["revalidation_predecessor"]}
           if "revalidation_predecessor" in identity else {})}


def _verified_retained_pages(operation: Path, expected: dict) -> None:
    """Copied responses remain bound to their immutable prior operation."""
    from .ordinary_layout_service import _read as verified_record
    names = {f"page-{int(p):04d}.retained.json" for p in expected}
    if {p.name for p in operation.glob("*.retained.json")} != names:
        fail("automatic_retained_response_changed", 409)
    for page, origin in expected.items():
        if (verified_record(operation / f"page-{int(page):04d}.retained.json") != origin
                or hashlib.sha256(storage._read(operation / f"page-{int(page):04d}.response.json", 2 * 1024 * 1024)).hexdigest() != origin["response_sha256"]):
            fail("automatic_retained_response_changed", 409)


def _proposal_evidence(manager, job_id: str, baseline_id: str, review_id: str, operation_nonce: str,
                       selected_pages: tuple[int, ...], policy: str, *, retained_pages=None) -> dict:
    """Record hashes and settled usage, never private source/target text."""
    from .saved_docx_layout_service import _read as bounded_read
    from .ordinary_layout_contracts import decode
    image_hashes = {page: hashlib.sha256(manager.service.saved.image(review_id, page)).hexdigest()
                    for page in selected_pages}
    pages, response_versions, source_evidence = [], set(), []
    with manager.service.scope(job_id) as folder:
        operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
        _verified_retained_pages(operation, retained_pages or {})
        intent = bounded_read(operation / "intent.json", 8 * 1024 * 1024)
        summary = bounded_read(operation / "accounting_summary.json", 8 * 1024 * 1024)
        from .ordinary_layout_service import _read as verified_record
        request_policy = verified_record(operation / "intent.json")["request"]["policy"]
        for page in selected_pages:
            response = bounded_read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024)
            row = {"source_page_number": page,
                "source_image_sha256": image_hashes[page],
                "response_sha256": hashlib.sha256(response).hexdigest()}
            retained_path = operation / f"page-{page:04d}.retained.json"
            if retained_path.exists():
                row["retained_origin"] = verified_record(retained_path)
            proposal = decode(response)
            response_version = proposal.get("version")
            if response_version == "ordinary_layout_proposal_v3":
                # The signed sidecar was validated against the immutable initial
                # generation, before uncertain proposed regions were applied.
                sidecar = verified_record(operation / "source_evidence.json")
                records = [item for item in sidecar["pages"] if item.get("page_number") == page]
                if len(records) != 1 or records[0].get("response_sha256") != row["response_sha256"]:
                    fail("source_evidence_response_changed", 409)
                source_evidence.append(records[0])
            if response_version != "ordinary_layout_proposal_v1":
                row["proposal_schema_version"] = response_version
            response_versions.add(response_version)
            pages.append(row)
    schema_version = next(iter(response_versions)) if len(response_versions) == 1 else "mixed_retained_proposals"
    return {"version": "ordinary_auto_layout_evidence_v1", "document_reviewed": False,
        "rendered_layout_acceptance": "not_evaluated", "policy_fingerprint": policy.split(":", 1)[1],
        "operation_nonce": operation_nonce, "intent_sha256": hashlib.sha256(intent).hexdigest(),
        "accounting_summary_sha256": hashlib.sha256(summary).hexdigest(),
        "requested_model": request_policy["model"], "effort": request_policy["effort"],
        "proposal_schema_version": schema_version, "pages": pages,
        **({"source_evidence": {"version": "ordinary_source_evidence_v1", "pages": source_evidence}} if source_evidence else {})}


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
        _verified_retained_pages(operation, pointer.get("retained_pages", {}))
        if (intent.get("baseline_id") != baseline_id or intent.get("review_id") != pointer["review_id"]
                or intent.get("operation_nonce") != operation_nonce
                or intent.get("request", {}).get("expected_generation") != initial
                or intent.get("request", {}).get("page_numbers") != selected_pages
                or summary.get("coverage_status") != "complete"
                or summary.get("cost_usd") is None
                or summary.get("unknown_cost_count") != 0
                or summary.get("in_flight_count") != 0
                or summary.get("provider_dispatch_count") != len(selected_pages) - len(pointer.get("retained_pages", {}))
                or summary.get("attempt_count") != summary.get("provider_dispatch_count")):
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
    source_result_fields = {}
    with manager.service.scope(origin) as folder:
        sidecar_path = folder / "baselines" / baseline_id / "suggestions" / operation_nonce / "source_evidence.json"
        if sidecar_path.exists():
            records = verified_record(sidecar_path)["pages"]
            source_result_fields = {"source_coverage_findings": [f for page in records for f in page["findings"]],
                "source_layout_evidence_sha256": hashlib.sha256(encode(records)).hexdigest()}
    evidence_view = current["review"]
    if any(p.get("version") == "ordinary_layout_proposal_v3" for p in proposals):
        with manager.service.scope(origin) as folder:
            operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
            initial_path = operation / "proposal_initial_view.json"
            if not initial_path.exists():
                fail("source_evidence_initial_view_missing", 409)
            initial_record = verified_record(initial_path)
            if initial_record.get("review_id") != pointer["review_id"] or initial_record.get("generation") != initial:
                fail("source_evidence_initial_view_changed", 409)
            evidence_view = initial_record["view"]
            from .ordinary_layout_contracts import proposal_source_evidence
            source_records = [proposal_source_evidence(inspect_docx(reviewed, evidence_view["target_lang"]), evidence_view, p) for p in proposals]
            for record, proposal in zip(source_records, proposals):
                record["response_sha256"] = hashlib.sha256(storage._read(operation / f"page-{proposal['page_number']:04d}.response.json", 2 * 1024 * 1024)).hexdigest()
            expected_sidecar = {"version": "ordinary_source_evidence_v1", "pages": source_records}
            sidecar = operation / "source_evidence.json"
            if sidecar.exists() and verified_record(sidecar) != expected_sidecar:
                fail("source_evidence_response_changed", 409)
            if not sidecar.exists(): verified_write(sidecar, expected_sidecar)
            source_result_fields = {"source_coverage_findings": [f for page in source_records for f in page["findings"]],
                "source_layout_evidence_sha256": hashlib.sha256(encode(source_records)).hexdigest()}
    try:
        decisions = normalize_proposals(inspect_docx(reviewed, current["review"]["target_lang"]),
            evidence_view, proposals)
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
    result.update(source_result_fields)
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
            or pointer.get("selected_pages") != identity["selected_pages"]
            or pointer.get("retained_pages", {}) != identity.get("retained_pages", {})):
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
        tuple(identity["selected_pages"]), frozen_policy, retained_pages=identity.get("retained_pages", {}))
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
    costs = _operation_costs(manager, origin, identity)
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
        "delivery_kind": artifact.kind, "reviewed": False, "layout_costs": costs,
        **({"recovery_predecessor": identity["recovery_predecessor"]}
           if "recovery_predecessor" in identity else {}),
        **({"revalidation_predecessor": identity["revalidation_predecessor"]}
           if "revalidation_predecessor" in identity else {})}


def run_automatic_layout(manager, accounting, job_id: str, frozen_policy: str,
                         *, cancel_requested=None, begin_publication=None,
                         recovery_old_policy: str | None = None) -> dict:
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
    root = _durable_folder(baseline)
    retained = {}
    direct = False
    if recovery_old_policy is not None:
        if frozen_policy != frozen_automatic_layout_policy():
            fail("automatic_policy_changed", 409)
        predecessor = _failed_predecessor(manager, root, identity, recovery_old_policy)
        from .ordinary_layout_service import _read as verified_record
        predecessor_operation = manager.service.root / predecessor["origin_job_id"] / "baselines" / predecessor["baseline_id"] / "suggestions" / predecessor["operation_nonce"]
        predecessor_result = verified_record(predecessor_operation / "result.json")
        predecessor_policy = verified_record(predecessor_operation / "intent.json")["request"]["policy"]
        # Existing durable lineage wins over a newly eligible normalization
        # failure. Historical 8k operations retain their explicit capacity
        # recovery; they cannot be silently relabeled as 32k retained inputs.
        direct = _direct_revalidation(root, predecessor_result, predecessor_policy)
        if direct:
            _, retained = _retained_continuation(manager, root, identity, predecessor, direct=True)
            identity["retained_pages"] = {str(p): r["origin"] for p, r in retained.items()}
            folder = storage._mkdir(root / "recoveries" / "layout_direct_revalidation_v1")
        else:
            folder = _recovery_folder(root)
        if (folder / "operation.json").exists() and not (folder / "candidate.json").exists():
            pointer = _read_record(folder / "operation.json")
            old_operation = manager.service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
            if (old_operation / "result.json").exists():
                from .ordinary_layout_service import _read as verified_record
                failed = verified_record(old_operation / "result.json")
                errors = {"ordinary_layout_proposal_coverage", "ordinary_layout_invalid_proposal_decisions"} if direct else {"ordinary_layout_page_break_requires_flow"}
                if failed.get("status") == "failed" and failed.get("error_code") in errors:
                    # The existing second successor now also admits one failed
                    # direct child. Preserve original origins and charge each
                    # predecessor once; no recursive recovery chain is created.
                    original_retained = retained
                    parent_identity = dict(identity)
                    parent_identity.pop("retained_pages", None)
                    prior, retained = _retained_continuation(manager, root, parent_identity, predecessor,
                        parent_direct=direct, inherited=original_retained if direct else None)
                    identity["revalidation_predecessor"] = prior
                    identity["retained_pages"] = {str(p): r["origin"] for p, r in retained.items()}
                    folder = storage._mkdir(root / "recoveries" / "layout_revalidation_v1")
        identity["recovery_predecessor"] = predecessor
        if (not (folder / "candidate.json").is_file()
                and (manager.service.root / job_id).is_dir()):
            # A resumed job may have acquired its own delivery selection even
            # though the failed origin remains unselected. Never buy layout
            # pages for an output the operator has already selected.
            with manager.service.scope(job_id) as current_folder:
                if (manager.service._selections(current_folder)
                        or (current_folder / "frozen.json").exists()
                        or (current_folder / "automatic.json").exists()):
                    fail("automatic_recovery_predecessor_selected", 409)
    else:
        folder = root
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
    if recovery_old_policy is None:
        accounting.authorize_automatic(job, policy_hash)
    else:
        prior_cost = Decimal(identity["recovery_predecessor"]["known_cost_usd"])
        if "revalidation_predecessor" in identity:
            prior_cost += Decimal(identity["revalidation_predecessor"]["known_cost_usd"])
        accounting.authorize_recovery(job, policy_hash, str(prior_cost),
            missing_pages=[p for p in job.selected_pages if p not in retained] if retained else None,
            **({"direct_continuation_identity_sha256": hashlib.sha256(encode(identity)).hexdigest()}
               if direct and "revalidation_predecessor" in identity else {}))
    prepare_nonce = _nonce("automatic_revalidation_prepare" if retained else "automatic_recovery_prepare" if recovery_old_policy is not None else "automatic_prepare",
        {"job_id": job_id, "raw_snapshot": mapped.fingerprint, "policy": policy_hash,
         **({"direct_predecessor": identity["revalidation_predecessor"]["result_sha256"]}
            if direct and "revalidation_predecessor" in identity else {}),
         **({"predecessor": identity["recovery_predecessor"]["result_sha256"]}
            if recovery_old_policy is not None else {})})
    prepared = manager.prepare(job_id, prepare_nonce)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    baseline_id = prepared["baseline_id"]
    generation = prepared["generation"]
    operation_nonce = _nonce("automatic_revalidation_suggest" if retained else "automatic_recovery_suggest" if recovery_old_policy is not None else "automatic_suggest", {"job_id": job_id,
        "baseline_id": baseline_id, "generation": generation,
        "raw_snapshot": mapped.fingerprint, "policy": policy_hash,
        **({"direct_predecessor": identity["revalidation_predecessor"]["result_sha256"]}
           if direct and "revalidation_predecessor" in identity else {}),
        **({"predecessor": identity["recovery_predecessor"]["result_sha256"]}
           if recovery_old_policy is not None else {})})
    pointer = {"identity_sha256": hashlib.sha256(encode(identity)).hexdigest(),
        "origin_job_id": job_id, "baseline_id": baseline_id,
        "review_id": prepared["review"]["review_id"], "initial_generation": generation,
        "operation_nonce": operation_nonce, "selected_pages": list(job.selected_pages)}
    if retained:
        pointer["retained_pages"] = identity["retained_pages"]
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
        expected_baseline_id=baseline_id, external_cancel_requested=cancel_requested,
        retained_proposals=retained)
    if (outcome.get("status") != "applied_unreviewed"
            or outcome.get("completed_pages") != list(job.selected_pages)
            or not outcome.get("accounting", {}).get("complete")):
        fail("automatic_proposal_incomplete", 409)
    return _finish_saved_proposals(manager, folder, identity, pointer, raw_map, frozen_policy, job,
        cancel_requested, begin_publication)


def cancel_automatic_layout(manager, accounting, job_id: str, *, recovery: bool = False) -> None:
    """Bridge an active browser Cancel to the durable page-boundary marker."""
    baseline = accounting.jobs.trusted_ordinary_baseline_identity(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    root = _durable_folder(baseline)
    folder = _recovery_folder(root) if recovery else root
    if recovery and (root / "recoveries" / "layout_direct_revalidation_v1" / "operation.json").exists():
        folder = root / "recoveries" / "layout_direct_revalidation_v1"
    if recovery and (root / "recoveries" / "layout_revalidation_v1" / "operation.json").exists():
        folder = root / "recoveries" / "layout_revalidation_v1"
    pointer_path = folder / "operation.json"
    if not pointer_path.exists():
        return
    pointer = _read_record(pointer_path)
    if pointer.get("origin_job_id") != job_id:
        return  # A reused operation has no new page dispatch to cancel.
    manager.service.cancel_suggestion(job_id, pointer["operation_nonce"],
        pointer["initial_generation"], expected_baseline_id=pointer["baseline_id"])


def verified_recovery_layout_costs(manager, job: dict, current: dict) -> dict:
    """Add a failed predecessor's known charge once, from immutable files."""
    automatic = job.get("result", {}).get("automatic_layout", {})
    predecessor = automatic.get("recovery_predecessor")
    if type(predecessor) is not dict or not current.get("complete"):
        fail("automatic_recovery_accounting_unsettled", 409)
    from .ordinary_layout_contracts import identifier, nonce
    origin = identifier(predecessor.get("origin_job_id"))
    baseline_id = nonce(predecessor.get("baseline_id"))
    operation_nonce = nonce(predecessor.get("operation_nonce"))
    trusted = manager._job(job["job_id"])
    root = Path(job["result"]["run_dir"]).expanduser().resolve() / "ordinary_auto_layout"
    recovery = root / "recoveries" / "layout_capacity_v2"
    if (root / "recoveries" / "layout_direct_revalidation_v1" / "intent.json").exists():
        recovery = root / "recoveries" / "layout_direct_revalidation_v1"
    if automatic.get("revalidation_predecessor"):
        recovery = root / "recoveries" / "layout_revalidation_v1"
    marker = _read_record(recovery / "candidate.json")
    identity = marker.get("identity")
    if (type(identity) is not dict or identity.get("recovery_predecessor") != predecessor
            or identity.get("source_pdf_sha256") != trusted.binding["source_sha256"]
            or identity.get("raw_docx_sha256") != hashlib.sha256(trusted.original_docx).hexdigest()
            or identity.get("raw_source_map_sha256") != trusted.binding["raw_source_map_sha256"]
            or identity.get("run_id") != trusted.run_id
            or identity.get("target_lang") != trusted.target_lang
            or identity.get("selected_pages") != list(trusted.selected_pages)
            or identity.get("runtime_mode") != trusted.mode
            or identity.get("workspace_id") != trusted.workspace_id
            or (marker.get("origin_job_id") != job["job_id"]
                and not (manager.service.state(job["job_id"]).get("automatic_alias")
                    and manager.service.state(job["job_id"]).get("delivery", {}).get("artifact_id")
                        == marker.get("candidate_id")))):
        fail("automatic_recovery_identity_changed", 409)
    operation = manager.service.root / origin / "baselines" / baseline_id / "suggestions" / operation_nonce
    paths = {"intent_sha256": root / "intent.json", "pointer_sha256": root / "operation.json",
        "result_sha256": operation / "result.json",
        "accounting_summary_sha256": operation / "accounting_summary.json",
        "accounting_journal_sha256": operation / "accounting" / "dispatch_accounting.json"}
    if any(hashlib.sha256(storage._read(path, 8 * 1024 * 1024)).hexdigest() != predecessor[key]
           for key, path in paths.items()):
        fail("automatic_recovery_predecessor_changed", 409)
    from .ordinary_layout_service import _read as verified_record
    summary = verified_record(paths["accounting_summary_sha256"])
    if (summary.get("coverage_status") != "complete" or summary.get("unknown_cost_count") != 0
            or summary.get("in_flight_count") != 0
            or str(summary.get("cost_usd")) != predecessor.get("known_cost_usd")):
        fail("automatic_recovery_predecessor_unsettled", 409)
    try:
        prior = Decimal(predecessor["known_cost_usd"])
        present = Decimal(current["known_cost_usd"])
        if not prior.is_finite() or not present.is_finite() or prior < 0 or present < 0:
            raise ValueError
    except (ValueError, KeyError):
        fail("automatic_recovery_accounting_changed", 409)
    predecessors = [predecessor]
    extra = automatic.get("revalidation_predecessor")
    if extra:
        if identity.get("revalidation_predecessor") != extra:
            fail("automatic_recovery_identity_changed", 409)
        extra_origin = identifier(extra.get("origin_job_id"))
        extra_operation = manager.service.root / extra_origin / "baselines" / nonce(extra.get("baseline_id")) / "suggestions" / nonce(extra.get("operation_nonce"))
        extra_root = root / "recoveries" / "layout_capacity_v2"
        direct_root = root / "recoveries" / "layout_direct_revalidation_v1"
        if (direct_root / "intent.json").is_file() and hashlib.sha256(storage._read(direct_root / "intent.json", 8 * 1024 * 1024)).hexdigest() == extra["intent_sha256"]:
            extra_root = direct_root
        extra_paths = {"intent_sha256": extra_root / "intent.json", "pointer_sha256": extra_root / "operation.json",
            "result_sha256": extra_operation / "result.json",
            "accounting_summary_sha256": extra_operation / "accounting_summary.json",
            "accounting_journal_sha256": extra_operation / "accounting" / "dispatch_accounting.json"}
        if any(hashlib.sha256(storage._read(p, 8 * 1024 * 1024)).hexdigest() != extra[k] for k, p in extra_paths.items()):
            fail("automatic_recovery_predecessor_changed", 409)
        extra_summary = verified_record(extra_paths["accounting_summary_sha256"])
        if (extra_summary.get("coverage_status") != "complete" or extra_summary.get("unknown_cost_count") != 0
                or extra_summary.get("in_flight_count") != 0 or str(extra_summary.get("cost_usd")) != extra.get("known_cost_usd")):
            fail("automatic_recovery_predecessor_unsettled", 409)
        predecessors.append(extra)
    inherited = [p for p in predecessors if p["origin_job_id"] != marker["origin_job_id"]]
    inherited_cost = sum((Decimal(p["known_cost_usd"]) for p in inherited), Decimal(0))
    included_cost = sum((Decimal(p["known_cost_usd"]) for p in predecessors if p not in inherited), Decimal(0))
    if present < included_cost:
        fail("automatic_recovery_accounting_changed", 409)
    total = inherited_cost + present
    if marker.get("layout_costs", {}).get("cost_usd") != str(total):
        fail("automatic_recovery_accounting_changed", 409)
    return {"cost_usd": str(total), "known_cost_usd": str(total), "complete": True,
        "operations": current["operations"] + len(inherited),
        "predecessor_cost_usd": str(inherited_cost + included_cost),
        "recovery_cost_usd": str(present - included_cost)}
