"""Fictional normal-Start page replacements through real SDK/accounting seams."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import httpx
from fastapi.testclient import TestClient
import pytest
from docx import Document

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_reproposal as proof
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.ordinary_layout_accounting import ACTUAL_MODEL
from legalpdf_translate.ordinary_layout_contracts import PROPOSAL_VERSION_V3, decode, encode, digest, OrdinaryLayoutError
from legalpdf_translate.saved_docx_layout import inspect_docx, default_decisions
from tests.test_ordinary_auto_layout_workflow import (_app, _source, _start, _wait, _proposal, _offline)


def isolate_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail("Unexpected external HTTP transport")
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    from legalpdf_translate import workflow as workflow_module
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test", forbidden)
    monkeypatch.setattr(workflow_module, "resolve_openai_key_with_source", forbidden)


@pytest.fixture(autouse=True)
def no_live_provider(monkeypatch):
    isolate_provider(monkeypatch)
    # These historical global-one oracles exercise their concrete saved V11.
    monkeypatch.setattr(auto, "frozen_automatic_layout_policy", auto._bounded_page_reproposal_v11_policy)


def normal_start(tmp_path, monkeypatch, *, damage=None, saved_policy=None, page_count=3):
    source, output = tmp_path / "fictional.pdf", tmp_path / "output"
    output.mkdir()
    _source(source, ("digital",) * page_count)
    app, jobs, translation, _ = _app(tmp_path, monkeypatch,
        ("English alpha 42", "English beta 73", "English gamma 84")[:page_count], tuple(range(1, page_count + 1)))
    manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, "shadow", "fictional")
    calls = []
    accountants = []
    accounting_factory = manager.accounting_factory
    def track_accounting(*args, **kwargs):
        accountant = accounting_factory(*args, **kwargs)
        accountants.append(accountant)
        return accountant
    manager.accounting_factory = track_accounting
    manager._test_accountants = accountants
    def provider(job, policy):
        def create(**request):
            payload = json.loads(request["input"][0]["content"][0]["text"])
            page = payload["page_number"]
            ordinal = sum(p == page for p, _ in calls)
            calls.append((page, request))
            proposal = _proposal(manager.service.state(job.job_id)["review"], page)
            proposal.update(version=PROPOSAL_VERSION_V3, paragraph_partitions=[],
                source_coverage_findings=[], source_layout_evidence=[])
            changes = damage(page, ordinal, proposal, request, manager, job) if damage is not None else None
            response = SimpleNamespace(id=f"fictional-layout-{len(calls)}", model=ACTUAL_MODEL,
                status="completed", service_tier="default", output=[], output_text=json.dumps(proposal),
                usage={"input_tokens": 80, "output_tokens": 60, "total_tokens": 140,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0}})
            for key, value in (changes or {}).items(): setattr(response, key, value)
            return response
        return OpenAIResponsesClient(model=policy.model, max_transport_retries=0, pre_call_jitter_seconds=0,
            sdk_client=SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create)))
    manager.provider_factory = provider
    with TestClient(app) as client:
        with monkeypatch.context() as recipe:
            if saved_policy is not None:
                recipe.setattr(auto, "frozen_automatic_layout_policy", lambda: saved_policy)
            job_id = _start(client, source, output, "EN", start=1, end=page_count, image_mode="off")
            result = _wait(jobs, job_id, timeout_seconds=90)
    baseline = jobs.trusted_ordinary_baseline_identity(job_id, runtime_mode="shadow", workspace_id="fictional")
    pointer = decode((Path(baseline["run_dir"]) / "ordinary_auto_layout/operation.json").read_bytes())
    operation = manager.service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
    return SimpleNamespace(app=app, jobs=jobs, manager=manager, calls=calls, job=result,
        operation=operation, pointer=pointer, baseline=baseline, translation=translation, accountants=accountants)


def invalid_decision(proposal):
    proposal["paragraphs"][0]["role"] = "body"  # its existing heading level now violates strict presentation


@pytest.fixture(scope="module")
def successful_repair(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    isolate_provider(patch)
    def damage(page, ordinal, proposal, *_):
        if page == 2 and ordinal == 0:
            invalid_decision(proposal)
    case = normal_start(tmp_path_factory.mktemp("reproposal_success"), patch, damage=damage,
        saved_policy=auto._bounded_page_reproposal_v11_policy())
    yield case
    patch.undo()


def test_normal_start_replaces_invalid_page_two_once_then_dispatches_page_three_and_strict_builds(successful_repair):
    case = successful_repair
    assert [p for p, _ in case.calls] == [1, 2, 2, 3], case.job["result"]["automatic_layout"]
    result = case.job["result"]["automatic_layout"]
    assert result["status"] == "automatic_unreviewed", (result, case.job["diagnostics"])
    assert Path(result["output_path"]).is_file()
    first, second = [request for page, request in case.calls if page == 2]
    a, b = deepcopy(first), deepcopy(second)
    payload = json.loads(b["input"][0]["content"][0]["text"])
    feedback = payload.pop("proposal_repair")
    assert feedback["error_code"] == "ordinary_layout_invalid_proposal_decisions"
    assert feedback["previous_proposal"]["paragraphs"][0]["role"] == "body"
    assert b.pop("instructions") == a["instructions"] + proof.INSTRUCTIONS
    a.pop("instructions")
    # The client passes its finite remaining request deadline to the SDK.
    assert 0 < a.pop("timeout") <= 480 and 0 < b.pop("timeout") <= 480
    b["input"][0]["content"][0]["text"] = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert a == b
    ledger = decode((case.operation / "proposal_repair_ledger.json").read_bytes())
    assert len(ledger["journal"]["events"]) == 8
    raw = (case.operation / "page-0002.response.json").read_bytes()
    assert raw == (case.operation / "attempts/page-0002/attempt-01.response.json").read_bytes()
    assert raw != (case.operation / "attempts/page-0002/attempt-00.response.json").read_bytes()
    assert decode((case.operation / "attempts/page-0002/selection.json").read_bytes())["ordinal"] == 1
    assert result["layout_costs"]["complete"] is True
    before = len(case.calls)
    again = auto.run_automatic_layout(case.manager, case.app.state.ordinary_layouts._accounting,
        case.job["job_id"], auto.frozen_automatic_layout_policy())
    assert again["reused_durable_candidate"] and len(case.calls) == before


def synthetic():
    doc = Document()
    for text in ("Fictional first paragraph.", "Fictional second paragraph.", "Fictional terminal text."):
        doc.add_paragraph(text)
    raw = BytesIO(); doc.save(raw)
    snapshot = inspect_docx(raw.getvalue(), "EN")
    frames = [{"page_number": 1, "width_px": 1000, "height_px": 1400, "image_sha256": "0" * 64}]
    choices = default_decisions(snapshot, frames)
    for row in choices["paragraphs"]:
        row["regions"] = [{"page_number": 1, "bbox_px": [0, 0, 1000, 1400]}]
    view = {"target_lang": "EN", "paragraphs": [{k: r[k] for k in ("id", "ordinal", "text", "has_page_break")}
        for r in snapshot["paragraphs"]], "pages": frames, "decisions": choices}
    proposal = _proposal(view, 1)
    proposal.update(version=PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[], source_layout_evidence=[])
    return snapshot, view, proposal, proof.expected_policy(1)


@pytest.mark.parametrize("code", sorted(proof.ELIGIBLE))
def test_only_reproduced_three_codes_with_complete_ownership_are_eligible(code):
    snapshot, view, proposal, policy = synthetic()
    if code.endswith("proposal_coverage"):
        proposal["bands"][0]["groups"].pop()
    elif code.endswith("invalid_proposal_decisions"):
        invalid_decision(proposal)
    else:
        proposal["source_layout_evidence"] = [{"kind": "source_footer", "paragraph_ids": [proposal["paragraphs"][-1]["paragraph_id"]],
            "bbox": [.1, .7, .9, .95]}]
    assert proof.validation(snapshot, view, proposal, policy) == {"valid": False, "error_code": code}
    assert proof.eligible(snapshot, view, proposal, policy, code)
    assert not proof.eligible(snapshot, view, proposal, policy, "ordinary_layout_invalid_source_layout_evidence")


@pytest.mark.parametrize("fault", ["wrong_version", "bool_page", "wrong_page", "missing_choice", "duplicate_choice",
    "reordered_choices", "foreign_band", "foreign_partition", "foreign_evidence", "duplicate_evidence",
    "findings_missing", "findings_null", "findings_bool", "findings_nonempty"])
def test_ownership_and_findings_never_receive_reproposal_authority(fault):
    snapshot, view, proposal, policy = synthetic()
    invalid_decision(proposal)
    if fault == "wrong_version": proposal["version"] = "ordinary_layout_proposal_v2"
    elif fault == "bool_page": proposal["page_number"] = True
    elif fault == "wrong_page": proposal["page_number"] = 2
    elif fault == "missing_choice": proposal["paragraphs"].pop()
    elif fault == "duplicate_choice": proposal["paragraphs"][-1] = deepcopy(proposal["paragraphs"][0])
    elif fault == "reordered_choices": proposal["paragraphs"].reverse()
    elif fault == "foreign_band": proposal["bands"][0]["groups"][0]["paragraph_ids"] = ["foreign-page-id"]
    elif fault == "foreign_partition": proposal["paragraph_partitions"] = [{"paragraph_id": "foreign-page-id", "split_before": ["Fictional"]}]
    elif fault in {"foreign_evidence", "duplicate_evidence"}:
        pid = "foreign-page-id" if fault == "foreign_evidence" else proposal["paragraphs"][-1]["paragraph_id"]
        row = {"kind": "source_footer", "paragraph_ids": [pid], "bbox": [.1, .9, .9, .99]}
        proposal["source_layout_evidence"] = [row] if fault == "foreign_evidence" else [row, deepcopy(row)]
    elif fault == "findings_missing": proposal.pop("source_coverage_findings")
    else: proposal["source_coverage_findings"] = {"findings_null": None, "findings_bool": False,
        "findings_nonempty": [{"kind": "missing_readable_literal", "literal": "X"}]}[fault]
    assert not proof.eligible(snapshot, view, proposal, policy, "ordinary_layout_invalid_proposal_decisions")


def witness_context(case):
    job = case.manager._job(case.job["job_id"])
    witness = decode((case.operation / "proposal_repair_ledger.json").read_bytes())
    kwargs = dict(snapshot=inspect_docx(job.reviewed_docx, job.target_lang),
        frames=witness["manifest"]["initial_view"]["pages"], source_pdf=job.source_pdf,
        page_groups=job.page_groups, selected_pages=job.selected_pages)
    return witness, kwargs


@pytest.mark.parametrize("fault", ["version", "missing_manifest", "source", "page_mapping", "policy", "extra_attempt",
    "missing_selection", "choose_failed", "request", "raw", "validation", "slot_page", "slot_hash",
    "native_missing", "native_duplicate", "native_cost", "native_request", "native_response_id"])
def test_rehashed_attempt_and_selection_forgery_is_rejected(successful_repair, fault):
    from legalpdf_translate.usage_accounting import _state_fingerprint
    witness, kwargs = witness_context(successful_repair)
    records = witness["records"]
    if fault == "version": witness["version"] = "unknown"
    elif fault == "missing_manifest": witness["manifest"].pop("snapshot_sha256")
    elif fault == "source": witness["manifest"]["identity"]["source_sha256"] = "0" * 64
    elif fault == "page_mapping": witness["manifest"]["identity"]["page_groups"][0][1][0] = "foreign-page-id"
    elif fault == "policy": witness["manifest"]["policy"]["max_operation_cost_usd"] = "1000"
    elif fault == "extra_attempt": records["page-0002/attempt-02.intent.json"] = records["page-0002/attempt-01.intent.json"]
    elif fault == "missing_selection": records.pop("page-0002/selection.json")
    elif fault in {"choose_failed", "request", "validation", "slot_page", "slot_hash"}:
        name = {"choose_failed": "page-0002/selection.json", "request": "page-0002/attempt-01.intent.json",
            "validation": "page-0002/attempt-00.validation.json", "slot_page": "repair_slot.json", "slot_hash": "repair_slot.json"}[fault]
        value = decode(records[name])
        if fault == "choose_failed": value["ordinal"] = 0
        elif fault == "request": value["request"]["prompt_text"] += " "
        elif fault == "validation": value = {"valid": True, "error_code": None}
        elif fault == "slot_page": value["page_number"] = 3
        else: value["repair_intent_sha256"] = "0" * 64
        records[name] = encode(value).decode()
    elif fault == "raw": records["page-0002/attempt-01.response.json"] += " "
    else:
        events = witness["journal"]["events"]
        if fault == "native_missing": events.pop()
        elif fault == "native_duplicate": events.extend(deepcopy(events[-2:]))
        elif fault == "native_cost": events[-1]["cost_usd"] = "0"
        elif fault == "native_request": events[-2]["request_hash"] = "0" * 64
        else: events[-1]["response_id"] = "foreign-response"
        witness["journal"]["fingerprint"] = _state_fingerprint(witness["journal"])
    with pytest.raises((OrdinaryLayoutError, ValueError, KeyError, TypeError)):
        proof.verify_witness(witness, **kwargs)


@pytest.mark.parametrize("fault", ["alias", "missing_ledger", "missing_no_repair_ledger", "extra_file", "unfinished_last_page",
    "selection_alias_boundary", "validation_selection_alias_boundary"])
def test_local_crash_reconstruction_is_settled_only_and_never_dispatches(successful_repair, tmp_path, fault):
    case = successful_repair
    operation = tmp_path / "operation"
    shutil.copytree(case.operation, operation)
    witness, kwargs = witness_context(case)
    before = len(case.calls)
    if fault == "alias": (operation / "page-0002.response.json").write_bytes(b"{}")
    elif fault in {"missing_ledger", "missing_no_repair_ledger"}:
        (operation / "proposal_repair_ledger.json").unlink()
        if fault == "missing_no_repair_ledger":
            target = (operation / "attempts").resolve()
            assert target.is_relative_to(tmp_path.resolve())
            shutil.rmtree(target)
    elif fault == "extra_file": (operation / "attempts/unrecorded.json").write_bytes(b"{}")
    elif fault == "unfinished_last_page": (operation / "attempts/page-0003/attempt-00.response.json").unlink()
    else:
        (operation / "page-0003.response.json").unlink()
        if fault == "validation_selection_alias_boundary":
            (operation / "attempts/page-0003/attempt-00.validation.json").unlink()
            (operation / "attempts/page-0003/selection.json").unlink()
    if fault in {"selection_alias_boundary", "validation_selection_alias_boundary"}:
        restored, _, _ = proof.operation_witness(operation, **kwargs, restore_aliases=True, seal=True)
        assert restored == witness
        assert (operation / "page-0003.response.json").read_bytes() == (case.operation / "page-0003.response.json").read_bytes()
    else:
        with pytest.raises((OrdinaryLayoutError, ValueError, FileNotFoundError)):
            proof.operation_witness(operation, **kwargs)
    assert len(case.calls) == before


def test_valid_first_proposals_use_no_repair_but_require_complete_attempt_witness(tmp_path, monkeypatch):
    case = normal_start(tmp_path, monkeypatch)
    assert [page for page, _ in case.calls] == [1, 2, 3]
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    witness, kwargs = witness_context(case)
    assert "repair_slot.json" not in witness["records"]
    assert proof.verify_witness(witness, **kwargs)[1]["provider_dispatch_count"] == 3
    assert not (case.operation / "attempts/repair_slot.json").exists()


@pytest.mark.parametrize("failure", ["invalid_replacement", "second_invalid_page", "unowned_first", "nonempty_findings"])
def test_invalid_or_ineligible_replacement_stops_without_third_attempt_or_unstarted_page(tmp_path, monkeypatch, failure):
    def damage(page, ordinal, proposal, *_):
        if page == 2:
            invalid_decision(proposal)
            if failure == "unowned_first": proposal["paragraphs"].pop()
            if failure == "nonempty_findings":
                proposal["source_coverage_findings"] = [{"kind": "missing_readable_literal", "literal": "R",
                    "source_bbox": [.1, .1, .2, .2], "insertion_context": {"paragraph_id": proposal["paragraphs"][0]["paragraph_id"], "position": "before"}}]
        if failure == "second_invalid_page" and page == 1 and ordinal == 0:
            invalid_decision(proposal)
    case = normal_start(tmp_path, monkeypatch, damage=damage)
    expected = [1, 2, 2] if failure == "invalid_replacement" else [1, 1, 2] if failure == "second_invalid_page" else [1, 2]
    assert [page for page, _ in case.calls] == expected
    assert case.job["result"]["automatic_layout"]["status"] == "raw_fallback"
    assert not (case.operation / "page-0002.response.json").exists()
    assert not (case.operation / "attempts/page-0003").exists()
    assert case.job["actions"]["recover_layout"] is False
    before = len(case.calls)
    with TestClient(case.app) as client:
        denied = client.post(f"/api/translation/jobs/{case.job['job_id']}/layout/recover?mode=shadow&workspace=fictional")
        assert denied.status_code == 422
    with pytest.raises(OrdinaryLayoutError):
        auto.run_automatic_layout(case.manager, case.app.state.ordinary_layouts._accounting,
            case.job["job_id"], auto.frozen_automatic_layout_policy())
    with pytest.raises(OrdinaryLayoutError, match="unsupported_policy"):
        auto.run_automatic_layout(case.manager, case.app.state.ordinary_layouts._accounting,
            case.job["job_id"], auto.manual_automatic_layout_policy(), recovery_old_policy=auto.frozen_automatic_layout_policy())
    assert len(case.calls) == before


@pytest.mark.parametrize("restart", [False, True], ids=["saved_v10_resume", "saved_v10_new_manager_resume"])
def test_saved_v10_real_evidence_attachment_and_replay_remain_exact_under_v11(tmp_path, monkeypatch, restart):
    from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
    case = normal_start(tmp_path, monkeypatch, saved_policy=auto._protected_folio_bridges_v10_policy())
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    assert auto.frozen_automatic_layout_policy() == auto._bounded_page_reproposal_v11_policy()
    assert not (case.operation / "attempts").exists()
    before = {path: path.read_bytes() for path in case.operation.rglob("*") if path.is_file() and path.suffix != ".lock"}
    def forbidden(*args, **kwargs): pytest.fail("Saved V10 attempted a new purchase")
    manager = (OrdinaryLayoutManager(case.manager.service.root.parents[2], mode="shadow", workspace_id="fictional",
        job_resolver=case.manager.job_resolver, provider_factory=forbidden, accounting_factory=forbidden,
        suggestion_policy=forbidden) if restart else case.manager)
    result = auto.run_automatic_layout(manager, case.app.state.ordinary_layouts._accounting,
        case.job["job_id"], auto._protected_folio_bridges_v10_policy())
    assert result["reused_durable_candidate"] and len(case.calls) == 3
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_completed_v11_rebuild_reuses_verified_same_policy_candidate_without_new_capacity(successful_repair):
    case = successful_repair
    before = len(case.calls)
    result = auto.run_completed_unreviewed_rebuild(case.manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert result["reused_durable_candidate"] and len(case.calls) == before
    assert result["sha256"] == case.job["result"]["automatic_layout"]["sha256"]


def test_adopted_instruction_bytes_and_conditional_guidance_are_fingerprinted():
    assert digest(proof.FOOTER_CONSTRAINT_INSTRUCTIONS.encode()) == "b54c42775fd99b803c885412d7cdc5e51acde356154d32879cb778d5763b7b16"
    snapshot, view, proposal, policy = synthetic()
    request = proof.page_request(view, 1, policy)
    assert "BOUNDED SAME-PAGE" not in request["instructions"]
    prior = {"intent": {"request_sha256": "1" * 64}, "raw": encode(proposal).decode(),
        "validation": {"error_code": "ordinary_layout_invalid_source_footer_evidence"}}
    repaired = proof.page_request(view, 1, policy, prior=prior)
    assert repaired["instructions"] == request["instructions"] + proof.INSTRUCTIONS + proof.FOOTER_CONSTRAINT_INSTRUCTIONS
    prior["validation"]["error_code"] = "ordinary_layout_proposal_coverage"
    assert proof.page_request(view, 1, policy, prior=prior)["instructions"] == request["instructions"] + proof.INSTRUCTIONS


@pytest.mark.parametrize("kind", ["connection", "incomplete", "refusal", "unknown_usage", "cancel", "stale", "reserved_capacity"])
def test_transport_cancel_staleness_and_unavailable_capacity_never_buy_replacement(tmp_path, monkeypatch, kind):
    from decimal import Decimal
    from legalpdf_translate.openai_client import APIConnectionError
    observed = {}
    def damage(page, ordinal, proposal, request, manager, job):
        if page != 2: return
        if kind == "connection": raise APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        if kind == "incomplete": return {"status": "incomplete", "incomplete_details": SimpleNamespace(reason="max_output_tokens")}
        if kind == "refusal": return {"refusal": "Fictional refusal."}
        if kind == "unknown_usage": return {"usage": None}
        if kind == "cancel":
            view = manager.service.state(job.job_id)
            operation = next((manager.service.root / job.job_id / "baselines" / view["baseline_id"] / "suggestions").iterdir())
            manager.service.cancel_suggestion(job.job_id, operation.name, view["generation"], expected_baseline_id=view["baseline_id"])
        elif kind == "stale":
            view = manager.service.state(job.job_id)["review"]
            choices = deepcopy(view["decisions"])
            choices["paragraphs"][0]["alignment"] = "right"
            manager.service.saved.save_decisions(view["review_id"], view["generation"], "a" * 32, choices)
        else:
            budget = manager._test_accountants[-1].budget_context
            observed["cap"] = budget.cap_usd
            remaining = Decimal(str(budget.status()["remaining_usd"]))
            budget.reserve("fictional-other-child", remaining, {"kind": "other approved work"})
            invalid_decision(proposal)
    case = normal_start(tmp_path, monkeypatch, damage=damage)
    assert [page for page, _ in case.calls] == [1, 2]
    assert case.job["result"]["automatic_layout"]["status"] == "raw_fallback"
    assert not (case.operation / "page-0002.response.json").exists()
    assert not (case.operation / "attempts/page-0003").exists()
    if kind == "reserved_capacity": assert case.accountants[-1].budget_context.cap_usd == observed["cap"]
    if kind in {"connection", "unknown_usage"}: assert case.accountants[-1].summary()["unknown_cost_count"] > 0


def test_between_call_deadline_stops_before_native_layout_dispatch(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_layout_manager as module
    calls = iter([0])
    def now():
        return next(calls, (3 + 1) * 480 + 31)
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=now))
    case = normal_start(tmp_path, monkeypatch)
    assert case.calls == []
    assert case.job["result"]["automatic_layout"]["status"] == "raw_fallback"


def rebind_manifest(witness):
    records = witness["records"]
    for name, raw in list(records.items()):
        if name.endswith(".intent.json"):
            intent = decode(raw)
            intent["manifest_sha256"] = digest(encode(witness["manifest"]))
            records[name] = encode(intent).decode()
    if "repair_slot.json" in records:
        slot = decode(records["repair_slot.json"])
        page = slot["page_number"]
        for key, ordinal in (("original_intent_sha256", 0), ("repair_intent_sha256", 1)):
            slot[key] = digest(encode(decode(records[f"page-{page:04d}/attempt-{ordinal:02d}.intent.json"])))
        records["repair_slot.json"] = encode(slot).decode()


@pytest.mark.parametrize("fault", ["target_language", "negative_generation", "boolean_generation", "generation_disagrees_with_view"])
def test_coherently_rebound_identity_cannot_contradict_trusted_snapshot_and_initial_view(successful_repair, fault):
    witness, kwargs = witness_context(successful_repair)
    identity = witness["manifest"]["identity"]
    if fault == "target_language": identity["target_lang"] = "AR"
    elif fault == "negative_generation": identity["initial_generation"] = -1
    elif fault == "boolean_generation": identity["initial_generation"] = True
    else: identity["initial_generation"] += 1
    rebind_manifest(witness)
    with pytest.raises(OrdinaryLayoutError, match="context_changed"):
        proof.verify_witness(witness, **kwargs)


def saved_evidence(case):
    from legalpdf_translate.ordinary_layout_service import _read
    current = case.manager.service.state(case.job["job_id"])["review"]
    service = case.manager.service.saved
    folder = service._folder(current["review_id"])
    path = folder / "ordinary_proposals" / f"{current['generation']:06d}.json"
    value = decode(path.read_bytes())
    return service, folder, path, value, current


@pytest.mark.parametrize("inner", ["downgrade", "absent", "null"])
def test_trusted_v11_policy_always_requires_matching_inner_policy_and_witness(successful_repair, inner):
    case = successful_repair
    _, kwargs = witness_context(case)
    _, _, _, saved, _ = saved_evidence(case)
    value = deepcopy(saved["proposal_evidence"])
    value.pop(proof.EVIDENCE_KEY)
    if inner == "downgrade": value["policy_fingerprint"] = auto._protected_folio_bridges_v10_policy().split(":")[1]
    elif inner == "absent": value.pop("policy_fingerprint")
    else: value["policy_fingerprint"] = None
    with pytest.raises(OrdinaryLayoutError, match="proposal_repair_(policy_changed|evidence_missing)"):
        proof.verify_evidence(value, **kwargs, expected_policy_fingerprint=saved["policy_fingerprint"])


def test_concrete_old_policy_retains_absent_inner_field_contract(successful_repair):
    _, kwargs = witness_context(successful_repair)
    proof.verify_evidence({"document_reviewed": False, "rendered_layout_acceptance": "not_evaluated"}, **kwargs,
        expected_policy_fingerprint=auto._protected_folio_bridges_v10_policy().split(":")[1])


def test_actual_saved_reader_public_build_and_standalone_checks_reject_nested_policy_downgrade(successful_repair):
    from legalpdf_translate import ordinary_auto_layout_artifacts as core
    from legalpdf_translate import saved_docx_layout_service as storage
    case = successful_repair
    service, folder, path, saved, view = saved_evidence(case)
    manifest, snapshot, frames = service._load(folder)
    base, _, mapped = service._ordinary_binding(folder, manifest, snapshot, view["generation"])
    evidence = deepcopy(saved["proposal_evidence"])
    evidence["policy_fingerprint"] = auto._protected_folio_bridges_v10_policy().split(":")[1]
    evidence.pop(proof.EVIDENCE_KEY)
    raw, source = (folder / "original.docx").read_bytes(), (folder / "source.pdf").read_bytes()
    # Historical standalone calls with an explicitly old recipe retain their contract.
    legacy = core.build_unreviewed_candidate(raw, mapped, frames, view["decisions"],
        proposal_evidence=evidence, source_pdf_bytes=source)
    for operation in (lambda: core.build_unreviewed_candidate(raw, mapped, frames, view["decisions"],
            proposal_evidence=evidence, source_pdf_bytes=source, policy_fingerprint=base["policy_fingerprint"]),
        lambda: core.verify_unreviewed_candidate(raw, mapped, frames, view["decisions"], legacy,
            proposal_evidence=evidence, source_pdf_bytes=source, policy_fingerprint=base["policy_fingerprint"]),
        lambda: service.attach_ordinary_binding(view["review_id"], decode((folder / "ordinary_raw_source_map.json").read_bytes()),
            tuple(base["selected_pages"]), base["policy_fingerprint"], evidence, expected_generation=view["generation"])):
        with pytest.raises(ValueError, match="proposal_repair_policy_changed"):
            operation()
    before, requests = path.read_bytes(), len(case.calls)
    forged = deepcopy(saved)
    forged["proposal_evidence"] = evidence
    forged["proposal_evidence_sha256"] = digest(storage._encode(evidence))
    try:
        path.write_bytes(storage._encode(forged))
        with pytest.raises(ValueError, match="proposal_repair_policy_changed"):
            service._ordinary_binding(folder, manifest, snapshot, view["generation"])
        with pytest.raises(ValueError, match="proposal_repair_policy_changed"):
            service.build_unreviewed_candidate(view["review_id"], view["generation"], "e" * 32)
    finally:
        path.write_bytes(before)
    assert len(case.calls) == requests and path.read_bytes() == before
