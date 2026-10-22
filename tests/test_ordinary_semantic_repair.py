"""Real workflow/native journal around fictional HTTP; no model-quality oracle."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_semantic_review_model_integration import setup, immutable
from tests.test_workflow_semantic_audit_integration import offline, CORRECTED
from tests.test_workflow_semantic_review_integration import saved_recipe
from tests.test_ordinary_semantic_unit_refs import Client


REPAIRED = "طلب المدعى عليه جوابا مفصلا."


@pytest.fixture(autouse=True)
def saved_v1_repair_policy(monkeypatch):
    """Historical once-v1 must retain its own exact controller semantics."""
    fresh = glue.fresh_recipe
    def v1(*args, **kwargs):
        saved = fresh(*args, **kwargs)
        saved["semantic_repair_policy"] = repair.POLICY
        saved.pop("semantic_literal_authority_policy", None)
        saved.pop("semantic_enclosure_authority_policy", None)
        return saved
    monkeypatch.setattr(glue, "fresh_recipe", v1)


class Scenario:
    def __init__(self, *, joint=False, noop=False, exhaust=False, malformed=False, duplicate_claim=False):
        self.joint, self.noop, self.exhaust, self.malformed = joint, noop, exhaust, malformed
        self.duplicate_claim = duplicate_claim
        self.payloads, self.verifiers = [], 0
    def __call__(self, body, data):
        if "text" not in body: return data
        payload = json.loads(body["input"][0]["content"][0]["text"])
        self.payloads.append(deepcopy(payload))
        value = json.loads(data["output"][0]["content"][0]["text"])
        stage = payload["stage"]
        if stage == "source_inventory" and self.duplicate_claim:
            value["claims"].append({**deepcopy(value["claims"][0]), "claim_id": "second_claim"})
        if stage == "source_inventory" and "prior_source_inventory" in payload:
            for index, claim in enumerate(value["claims"], 1):
                claim["claim_id"] = f"revised_{index}"
                if not self.noop: claim["proposition"] += " A source-supported qualifier is retained."
        if stage == "correction" and "prior_findings" in payload:
            for row in value["pages"]:
                row.update(status="no_change" if self.noop else "corrected",
                    corrected_text="" if self.noop else REPAIRED,
                    reason_codes=[] if self.noop else ["material_meaning"])
        if stage == "verification":
            self.verifiers += 1
            if self.verifiers == 1 or self.exhaust:
                value["claim_results"][0]["status"] = "missing"
                if self.duplicate_claim: value["claim_results"][0]["target_unit_ids"] = []
                if self.joint:
                    value["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": "UNTRUSTED_TARGET_REASON_SENTINEL"}]
                if self.malformed: value["unsupported_additions"] = [{}]
        data["output"][0]["content"][0]["text"] = json.dumps(value, ensure_ascii=False)
        return data


def audit_files(run_dir):
    directory = run_dir / "semantic_audit"
    return {path.relative_to(directory).as_posix(): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def test_additional_genuine_v5_prechange_history_and_zero_call_replay_exact(tmp_path):
    entry = json.loads((Path(__file__).parent / "fixtures/semantic_repair_prechange_baa2.json").read_bytes())["case"]
    pages = tuple(review.SemanticAuditPage(**page) for page in entry["pages"])
    settings = review.SemanticAuditRecipe(**entry["recipe"])
    arguments = dict(pages=pages, recipe=settings, pdf_sha256=entry["pdf_sha256"],
        evidence_dir=tmp_path / "audit", **entry["options"])
    client = Client()
    review.run_semantic_review(**arguments, client=client)
    assert review.audit._json(client.requests) == review.audit._json(entry["requests"])
    before = {path.relative_to(arguments["evidence_dir"]).as_posix(): path.read_bytes() for path in arguments["evidence_dir"].rglob("*") if path.is_file()}
    assert before == {path: value.encode("utf-8") for path, value in entry["evidence"].items()}
    assert review.semantic_review_source_fingerprint(pages, settings, entry["pdf_sha256"], **entry["options"]) == entry["fingerprint"]
    assert review.load_semantic_review(**arguments).reused and review.run_semantic_review(**arguments, client=client).reused
    assert len(client.requests) == 3


def test_initial_pass_has_zero_repair_and_native_links_cover_every_sdk_stage(tmp_path):
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == 4
    manifest = json.loads((result.run_dir / "semantic_audit/manifest.json").read_bytes())
    assert manifest["selected_attempt"] == 0 and len(manifest["stages"]) == 3
    assert not (result.run_dir / "semantic_audit/attempt_01").exists()
    assert flow._last_state.settings["ordinary_semantic_audit_recipe"]["semantic_repair_policy"] == repair.POLICY
    links = [json.loads((result.run_dir / "semantic_audit" / row["native_settlement_path"]).read_bytes()) for row in manifest["stages"]]
    calls = [call for row in links for call in row["call_ids"]]
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    assert set(calls) == {event["call_id"] for event in journal["events"] if event["event"] == "begin" and event["purpose"] == "semantic_audit"}
    assert len(calls) == len(set(calls)) == 3


@pytest.mark.parametrize("joint,expected", [(False, 6), (True, 7)])
def test_one_global_cycle_native_settlement_input_separation_and_offline_replay(tmp_path, monkeypatch, joint, expected):
    scenario = Scenario(joint=joint)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == expected and scenario.verifiers == 2
    manifest = json.loads((result.run_dir / "semantic_audit/manifest.json").read_bytes())
    assert manifest["selected_attempt"] == 1 and len(manifest["stages"]) == expected - 1
    correction = next(payload for payload in scenario.payloads if "prior_findings" in payload)
    assert correction["primary_pages"][0]["text"] == CORRECTED
    assert all("claim_id" not in row for row in correction["prior_findings"]["claim_locations"])
    assert correction["prior_findings"]["claim_locations"][0]["source_unit_ids"] == ["S001"]
    if joint:
        inventory = next(payload for payload in scenario.payloads if "prior_source_inventory" in payload)
        serialized = json.dumps(inventory, ensure_ascii=False)
        assert inventory["source_unit_focus"] == ["S001"]
        for forbidden in (CORRECTED, "UNTRUSTED_TARGET_REASON_SENTINEL", config.context_text): assert forbidden not in serialized
        assert not set(inventory) & {"primary_pages", "candidate_pages", "target_units", "context_text", "prior_findings"}
        assert correction["source_inventory"]["claims"][0]["claim_id"].startswith("revised_")
    final = scenario.payloads[-1]
    assert final["stage"] == "verification" and final["candidate_pages"][0]["text"] == REPAIRED
    assert not set(final) & {"prior_findings", "primary_pages", "prior_source_inventory", "source_unit_focus", "context_text"}
    baseline_row = next(row for row in manifest["stages"] if "working_baseline_path" in row)
    baseline = json.loads((result.run_dir / "semantic_audit" / baseline_row["working_baseline_path"]).read_bytes())
    assert baseline["working_candidate"][0]["sha256"] == review.audit._sha(CORRECTED)
    assert baseline["original_primary"][0]["sha256"] != baseline["working_candidate"][0]["sha256"]
    requests, before = deepcopy(http.requests), immutable(result.run_dir)
    monkeypatch.setattr(glue, "fresh_recipe", lambda *a, **k: pytest.fail("Resume reset the saved cycle"))
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert http.requests == requests and immutable(result.run_dir) == before


@pytest.mark.parametrize("joint", [False, True])
def test_false_allegation_or_claim_renumber_only_stops_without_second_verifier(tmp_path, joint):
    scenario = Scenario(joint=joint, noop=True)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert not result.success and "repair_no_op" in result.error
    assert scenario.verifiers == 1 and len(http.requests) == (6 if joint else 5)
    before, count = audit_files(result.run_dir), len(http.requests)
    assert "manifest.json" not in before
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == count and audit_files(result.run_dir) == before


def test_joint_inventory_change_with_unchanged_target_permits_final_verification(tmp_path):
    scenario = Scenario(joint=True)
    def mutate(body, data):
        data = scenario(body, data)
        if "text" in body:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if "prior_findings" in payload:
                value = json.loads(data["output"][0]["content"][0]["text"])
                for row in value["pages"]: row.update(status="no_change", corrected_text="", reason_codes=[])
                data["output"][0]["content"][0]["text"] = json.dumps(value)
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == 7 and scenario.verifiers == 2
    assert (result.run_dir / "semantic_audit/page_0001.txt").read_text(encoding="utf-8") == CORRECTED


@pytest.mark.parametrize("malformed", [False, True])
def test_exhaustion_or_malformed_tail_never_dispatches_another_cycle(tmp_path, malformed):
    scenario = Scenario(exhaust=True, malformed=malformed)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert not result.success
    assert len(http.requests) == (4 if malformed else 6)
    before, count = audit_files(result.run_dir), len(http.requests)
    assert "manifest.json" not in before
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == count and audit_files(result.run_dir) == before


def test_fresh_missing_empty_reference_routes_to_repair_without_changing_acceptance(tmp_path):
    scenario = Scenario(duplicate_claim=True)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == 6 and scenario.verifiers == 2


@pytest.mark.parametrize("value", [None, "", "unknown", True, 1, [], {}], ids=["none", "empty", "unknown", "boolean", "integer", "list", "mapping"])
def test_explicit_invalid_repair_policy_never_becomes_historical_absence(tmp_path, value):
    _, saved, settings = saved_recipe(tmp_path)
    saved["semantic_repair_policy"] = value
    with pytest.raises(SemanticAuditRecipeError, match="semantic_repair_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("dependency", ["semantic_review_model_policy", "semantic_unit_reference_policy", "semantic_source_review_policy", "semantic_page_coverage_policy", "source_inventory_max_output_tokens"])
def test_saved_repair_dependencies_are_strict(tmp_path, dependency):
    _, saved, settings = saved_recipe(tmp_path)
    saved.pop(dependency)
    with pytest.raises(SemanticAuditRecipeError): ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("phase", [1, 2, 3, 4, 5, 6])
def test_unknown_native_cost_at_each_stage_stops_every_later_dispatch_and_resume(tmp_path, phase):
    scenario = Scenario(joint=True)
    def mutate(body, data):
        data = scenario(body, data)
        if "text" in body and len(scenario.payloads) == phase:
            data["usage"].pop("input_tokens_details", None)
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    result = flow.run(config)
    assert not result.success and "usage_unknown_or_unsettled" in result.error
    assert len(http.requests) == phase + 1
    before, count = audit_files(result.run_dir), len(http.requests)
    assert "manifest.json" not in before
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == count and audit_files(result.run_dir) == before


@pytest.mark.parametrize("phase", [1, 2, 3, 4, 5, 6])
@pytest.mark.parametrize("kind", ["refused", "incomplete"])
def test_refusal_and_incomplete_at_each_stage_retain_native_settlement_without_retry(tmp_path, phase, kind):
    scenario = Scenario(joint=True)
    def mutate(body, data):
        data = scenario(body, data)
        if "text" in body and len(scenario.payloads) == phase:
            if kind == "refused": data["output"][0]["content"] = [{"type": "refusal", "refusal": "Fictional refusal."}]
            else:
                data["status"] = "incomplete"
                data["incomplete_details"] = {"reason": "max_output_tokens"}
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    result = flow.run(config)
    assert not result.success and len(http.requests) == phase + 1
    before = audit_files(result.run_dir)
    links = [key for key in before if key.endswith("_native/native_settlement.json")]
    assert len(links) == phase and "manifest.json" not in before
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == phase + 1 and audit_files(result.run_dir) == before


@pytest.mark.parametrize("phase", [1, 2, 3, 4, 5, 6])
def test_cancel_after_settlement_resumes_without_repurchasing_or_resetting_cycle(tmp_path, phase):
    scenario = Scenario(joint=True)
    holder = {}
    def mutate(body, data):
        data = scenario(body, data)
        if "text" in body and len(scenario.payloads) == phase: holder["flow"].cancel()
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    holder["flow"] = flow
    result = flow.run(config)
    assert not result.success and len(http.requests) == phase + 1
    old_bodies = list(http.bodies)
    resumed = flow.run(replace(config, resume=True))
    assert resumed.success, resumed.error
    assert len(http.requests) == 7 and http.bodies[:len(old_bodies)] == old_bodies
    assert scenario.verifiers == 2
    manifest = json.loads((result.run_dir / "semantic_audit/manifest.json").read_bytes())
    assert len(manifest["stages"]) == 6 and manifest["selected_attempt"] == 1


def test_cancel_after_native_preproof_before_engine_intent_recovers_only_empty_slot(tmp_path, monkeypatch):
    original = glue.repair_stage_guard
    holder, stopped = {}, []
    def guarded(**kwargs):
        actual = original(**kwargs)
        def guard(**stage):
            result = actual(**stage)
            if stage["action"] == "prepare" and not stopped:
                stopped.append(True)
                holder["flow"].cancel()
            return result
        return guard
    monkeypatch.setattr(glue, "repair_stage_guard", guarded)
    config, http, flow = setup(tmp_path)
    holder["flow"] = flow
    result = flow.run(config)
    assert not result.success and len(http.requests) == 1
    assert (result.run_dir / "semantic_audit/attempt_00/source_inventory_native/native_intent.json").is_file()
    assert not (result.run_dir / "semantic_audit/attempt_00/source_inventory/intent.json").exists()
    assert flow.run(replace(config, resume=True)).success
    assert len(http.requests) == 4


@pytest.mark.parametrize("tamper", ["stage_record", "missing_stage_record", "baseline", "native_prefix", "native_response", "final_manifest"])
def test_selected_evidence_tampering_blocks_provider_free_rebuild_without_calls(tmp_path, tamper):
    scenario = Scenario(joint=True)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert result.success, result.error
    directory = result.run_dir / "semantic_audit"
    if tamper in {"stage_record", "missing_stage_record"}:
        file = directory / "attempt_01/correction/stage_record.json"
        if tamper == "missing_stage_record": file.unlink()
        else:
            data = json.loads(file.read_bytes()); data["attempt"] = 0; file.write_text(json.dumps(data), encoding="utf-8")
    elif tamper == "baseline":
        file = directory / "attempt_01/correction_baseline.json"
        data = json.loads(file.read_bytes()); data["working_candidate"][0]["sha256"] = "f" * 64; file.write_text(json.dumps(data), encoding="utf-8")
    elif tamper == "native_prefix":
        file = directory / "attempt_01/correction_native/native_intent.json"
        data = json.loads(file.read_bytes()); data["before_event_count"] -= 2; file.write_text(json.dumps(data), encoding="utf-8")
    elif tamper == "native_response":
        file = next((flow._dispatch_accounting.journal_path.parent / "provider_responses").glob("*.json"))
        data = json.loads(file.read_bytes()); data["id"] = "changed"; file.write_text(json.dumps(data), encoding="utf-8")
    else:
        file = directory / "manifest.json"
        data = json.loads(file.read_bytes()); data["selected_attempt"] = 0; file.write_text(json.dumps(data), encoding="utf-8")
    requests = deepcopy(http.requests)
    with pytest.raises(Exception): TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert http.requests == requests


def test_failed_validated_stage_record_has_explicit_baseline_and_zero_call_recovery(tmp_path):
    scenario = Scenario(joint=True, noop=True)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert not result.success
    file = result.run_dir / "semantic_audit/attempt_01/correction/stage_record.json"
    record = json.loads(file.read_bytes())
    assert record["working_baseline_path"] == "attempt_01/correction_baseline.json"
    original = file.read_bytes()
    file.unlink()
    count = len(http.requests)
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == count and file.read_bytes() == original


@pytest.mark.parametrize("kind", ["refusal", "incomplete_message", "incomplete_details"])
def test_rewritten_stage_envelope_cannot_hide_native_body_hard_stop(tmp_path, kind):
    from legalpdf_translate.usage_accounting import _state_fingerprint
    from legalpdf_translate.semantic_review_billing import response_billing_evidence
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    directory = result.run_dir / "semantic_audit"
    journal_path = flow._dispatch_accounting.journal_path
    journal = json.loads(journal_path.read_bytes())
    begin = next(row for row in journal["events"] if row["event"] == "begin" and row["purpose"] == "semantic_audit")
    finish = next(row for row in journal["events"] if row["event"] == "finish" and row["call_id"] == begin["call_id"])
    proof = finish["semantic_review_billing_evidence"]["response"]
    body_path = journal_path.parent / proof["path"]
    body = json.loads(body_path.read_bytes())
    if kind == "refusal": body["output"][0]["content"].append({"type": "refusal", "refusal": "Fictional refusal."})
    elif kind == "incomplete_message": body["output"][0]["status"] = "incomplete"
    else: body["incomplete_details"] = {"reason": "max_output_tokens"}
    raw_body = json.dumps(body).encode("utf-8")
    body_path.write_bytes(raw_body)
    proof.update(sha256=review.audit._sha(raw_body), bytes=len(raw_body))
    _, finish["semantic_review_billing_evidence"] = response_billing_evidence(journal_path.parent, proof,
        max_output_tokens=begin["bounds"]["max_output_tokens"], response_id=finish["response_id"],
        actual_model=finish["actual_model"], actual_service_tier=finish["actual_service_tier"],
        policy=begin["bounds"]["semantic_review_billing_policy"])
    journal["fingerprint"] = _state_fingerprint(journal)
    journal_path.write_text(json.dumps(journal), encoding="utf-8")
    stage = directory / "attempt_00/source_inventory"
    envelope = json.loads((stage / "raw_response.json").read_bytes())
    envelope.update(refused=False, response_status="completed", incomplete_reason=None)
    raw_envelope = json.dumps(envelope).encode("utf-8")
    (stage / "raw_response.json").write_bytes(raw_envelope)
    receipt = json.loads((stage / "raw_receipt.json").read_bytes())
    receipt["raw_sha256"] = review.audit._sha(raw_envelope)
    (stage / "raw_receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    post = directory / "attempt_00/source_inventory_native/native_settlement.json"
    post_before = post.read_bytes()
    (directory / "manifest.json").unlink()
    count = len(http.requests)
    resumed = flow.run(replace(config, resume=True))
    assert not resumed.success and "repair_native_response" in resumed.error
    assert len(http.requests) == count and post.read_bytes() == post_before


def test_native_transport_attempts_and_token_totals_all_belong_to_the_same_stage(tmp_path):
    import httpx
    config, http, flow = setup(tmp_path)
    http.client._max_transport_retries = 1
    http.client._base_backoff_seconds = 0
    original = http.http._transport.handler
    injected = []
    def handler(request):
        response = original(request)
        body = json.loads(request.content)
        if body["model"] == "gpt-6-astra" and not injected:
            injected.append(True)
            data = json.loads(response.content)
            data["status"] = "failed"
            return httpx.Response(429, json=data, headers={"content-type": "application/json"})
        return response
    http.http._transport.handler = handler
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == 5
    directory = result.run_dir / "semantic_audit"
    manifest = json.loads((directory / "manifest.json").read_bytes())
    inventory = manifest["stages"][0]
    proof = json.loads((directory / inventory["native_settlement_path"]).read_bytes())
    assert len(proof["call_ids"]) == 2
    assert inventory["usage"]["input_tokens"] == 200 and inventory["usage"]["total_tokens"] == 320
    assert manifest["usage"]["input_tokens"] == 400 and manifest["usage"]["total_tokens"] == 640
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    attempts = [row for row in journal["events"] if row["event"] == "begin" and row["call_id"] in proof["call_ids"]]
    assert [row["attempt"] for row in attempts] == [1, 2]
    assert len({row["request_hash"] for row in attempts}) == 1
    before, requests = immutable(result.run_dir), deepcopy(http.requests)
    assert flow.run(replace(config, resume=True)).success
    assert http.requests == requests and immutable(result.run_dir) == before


def test_existing_native_dispatch_cap_denies_next_stage_without_reset_or_retry(tmp_path, monkeypatch):
    original = glue.repair_stage_guard
    def guarded(**kwargs):
        actual = original(**kwargs)
        def guard(**stage):
            result = actual(**stage)
            if stage["action"] == "prepare" and stage["stage_id"] == "attempt_01/correction":
                def denied(**_): raise ValueError("Fictional existing dispatch allowance exhausted.")
                monkeypatch.setattr(kwargs["accountant"], "verify_dispatch", denied)
            return result
        return guard
    monkeypatch.setattr(glue, "repair_stage_guard", guarded)
    scenario = Scenario()
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert not result.success and len(http.requests) == 4
    before = audit_files(result.run_dir)
    assert "manifest.json" not in before
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == 4 and audit_files(result.run_dir) == before


def test_valid_ineligible_boundary_diagnostic_still_has_immutable_stage_record(tmp_path):
    import fitz
    def mutate(body, data):
        if "text" in body:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == "verification":
                value = json.loads(data["output"][0]["content"][0]["text"])
                value["boundary_results"][0]["status"] = "unresolved"
                data["output"][0]["content"][0]["text"] = json.dumps(value)
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    with fitz.open(config.pdf_path) as pdf:
        pdf.new_page().insert_text((50, 80), "Another fictional source page.")
        pdf.saveIncr()
    result = flow.run(config)
    assert not result.success and "repair_diagnostic_ineligible" in result.error
    stage = result.run_dir / "semantic_audit/attempt_00/verification"
    assert (stage / "stage_record.json").is_file()
    assert json.loads((stage / "diagnostic.json").read_bytes())["hard_stop"]
    assert len(http.requests) == 5 and not (result.run_dir / "semantic_audit/attempt_01").exists()


def test_cancellation_at_final_selection_replays_records_without_new_calls(tmp_path, monkeypatch):
    original = glue.repair_stage_guard
    stopped, holder = [], {}
    def guarded(**kwargs):
        actual = original(**kwargs)
        def guard(**stage):
            result = actual(**stage)
            if stage["action"] == "final" and not stopped:
                stopped.append(True)
                holder["flow"].cancel()
            return result
        return guard
    monkeypatch.setattr(glue, "repair_stage_guard", guarded)
    scenario = Scenario(joint=True)
    config, http, flow = setup(tmp_path, mutate=scenario)
    holder["flow"] = flow
    result = flow.run(config)
    assert not result.success and len(http.requests) == 7
    before = audit_files(result.run_dir)
    assert "manifest.json" not in before and not any(key.startswith("page_") for key in before)
    assert flow.run(replace(config, resume=True)).success
    assert len(http.requests) == 7
    after = audit_files(result.run_dir)
    assert all(after[key] == value for key, value in before.items())
