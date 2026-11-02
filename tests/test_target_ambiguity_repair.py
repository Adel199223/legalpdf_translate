"""Fictional initial-only diagnosis and unchanged strict final verification."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_target_ambiguity as ambiguity
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from tests.test_ordinary_semantic_review import pack, recipe, PDF
from tests.test_ordinary_semantic_unit_refs import response
from tests.test_ordinary_layout_reproposal import isolate_provider
from tests.test_workflow_semantic_audit_integration import offline

OPTIONS = {"semantic_unit_reference_policy": refs.POLICY,
    "source_inventory_max_output_tokens": 64000,
    "semantic_source_review_policy": "source_commitment_visual_v7",
    "semantic_page_coverage_policy": "complete_selected_pages_v1"}


@pytest.fixture(autouse=True)
def no_live_provider(monkeypatch):
    isolate_provider(monkeypatch)


def case(*, count=2, off=False):
    pages = pack(count=count, off=off)
    settings = recipe(configured_image_mode="off" if off else "auto")
    units = review.source_units(pages)
    request = repair._request("source_inventory", pages, settings, PDF, units, OPTIONS)
    raw = json.dumps(response("source_inventory", json.loads(request["prompt_text"])))
    canonical, _ = refs.hydrate(raw, "source_inventory", request, units)
    inventory = review.validate_source_inventory(review.audit._json(canonical), pages, units)
    candidate = {page.page_number: page.primary_text for page in pages}
    request = repair._request("verification", pages, settings, PDF, units, OPTIONS, inventory=inventory, candidate=candidate)
    data = response("verification", json.loads(request["prompt_text"]))
    return pages, units, inventory, candidate, request, data


def diagnose(value, *, profile=True):
    pages, units, inventory, candidate, request, data = value
    if profile: request = ambiguity.adapt_request(request)
    return repair.diagnose(review.audit._json(data), request, pages, units, inventory, candidate,
        **({ambiguity.KEY: ambiguity.POLICY} if profile else {}))


@pytest.mark.parametrize("affected", [(0,), (0, 1)])
def test_positive_target_only_diagnostic_is_failed_but_licenses_only_repair(affected):
    value = case()
    for index in affected: value[-1]["claim_results"][index]["status"] = ambiguity.STATUS
    result = diagnose(value)
    assert result["failed"] and result["eligible"] and not result["hard_stop"]
    assert not result["inventory_repair"] and len(result["findings"]) == len(affected)
    # The existing strict final hydrator never learns this new status.
    with pytest.raises(review.SemanticAuditError):
        canonical, _ = refs.hydrate(review.audit._json(value[-1]), "verification", value[-2], value[1])
        review.validate_candidate_verification(review.audit._json(canonical), value[0], value[2], value[3],
            review.source_units(value[0], candidate=value[3]))


def test_profile_only_initial_request_delta_and_exact_adopted_instruction_hash():
    value = case()
    original = deepcopy(value[-2])
    profiled = ambiguity.adapt_request(original)
    assert original == value[-2]
    payload = json.loads(profiled["prompt_text"])
    assert payload.pop(ambiguity.KEY) == ambiguity.descriptor()
    assert review.audit._json(payload) == value[-2]["prompt_text"]
    assert profiled["instructions"] == original["instructions"] + ambiguity.INSTRUCTIONS
    assert hashlib.sha256(ambiguity.INSTRUCTIONS.encode()).hexdigest() == "d2c7967e9fcdfe3a533beda8321092f0d81d099d4ba71b08d5d1fcf5db69a976"
    form = deepcopy(profiled["response_format"])
    form["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"].remove(ambiguity.STATUS)
    assert form == original["response_format"]
    assert {k:v for k,v in original.items() if k not in {"prompt_text","instructions","response_format"}} == {
        k:v for k,v in profiled.items() if k not in {"prompt_text","instructions","response_format"}}


def test_old_absence_generic_unresolved_and_all_equivalent_keep_their_meaning():
    value = case()
    assert not diagnose(value)["failed"]
    value[-1]["claim_results"][0]["status"] = "unresolved"
    for profile in (False, True):
        result = diagnose(value, profile=profile)
        assert result["failed"] and result["hard_stop"] and not result["eligible"]
    value[-1]["claim_results"][0]["status"] = ambiguity.STATUS
    with pytest.raises(review.SemanticAuditError, match="diagnostic_status"):
        diagnose(value, profile=False)


@pytest.mark.parametrize("defect", ["mixed_missing", "mixed_contradiction", "mixed_unresolved", "boundary",
    "inventory_error", "unsupported", "image_off", "image_only", "no_text_quote"])
def test_new_branch_closes_on_mixed_failures_or_missing_positive_evidence(defect):
    value = list(case(off=defect == "image_off"))
    data, inventory = value[-1], value[2]
    data["claim_results"][0]["status"] = ambiguity.STATUS
    if defect.startswith("mixed_"): data["claim_results"][1]["status"] = defect.removeprefix("mixed_")
    elif defect == "boundary": data["boundary_results"][0]["status"] = "contradiction"
    elif defect == "inventory_error": data["inventory_errors"] = [{"source_unit_ids":["S001"],"reason":"Fictional source qualifier."}]
    elif defect == "unsupported": data["unsupported_additions"] = [{"target_unit_ids":["T001"],"reason":"Fictional unsupported assertion."}]
    elif defect in {"image_only", "no_text_quote"}:
        inventory["claims"][0]["source_evidence"] = [{"kind":"image","page":1,"bbox":[.1,.1,.9,.9]}]
        if defect == "image_only":
            inventory["unit_coverage"][0]["claim_ids"] = [inventory["claims"][1]["claim_id"]]
            inventory["claims"][1]["source_unit_ids"].append(inventory["claims"][0]["source_unit_ids"][0])
            inventory["claims"][1]["source_evidence"].append({"kind":"image","page":1,"bbox":[.1,.1,.9,.9]})
            inventory["claims"][0]["source_unit_ids"] = []
            data["claim_results"][1]["target_unit_ids"] = ["T001", "T002"]
    # Mutated inventories are intentionally rebound into the synthetic request;
    # public diagnose still applies the full strict inventory validator.
    value[-2] = repair._request("verification", value[0], recipe(configured_image_mode="off" if defect=="image_off" else "auto"),
        PDF, value[1], OPTIONS, inventory=inventory, candidate=value[3])
    result = diagnose(value)
    assert result["hard_stop"] and not result["eligible"]


@pytest.mark.parametrize("defect", ["unrelated_unresolved", "unrelated_uncertain", "source_boundary", "bad_quote", "visual"])
def test_entire_inventory_and_exact_source_reading_are_revalidated(defect):
    value = list(case())
    value[-1]["claim_results"][0]["status"] = ambiguity.STATUS
    inventory = value[2]
    if defect == "unrelated_unresolved": inventory["claims"][1]["unresolved"] = True
    elif defect == "unrelated_uncertain": inventory["claims"][1]["axes"]["temporal_state"] = "uncertain"
    elif defect == "source_boundary": inventory["boundaries"][0]["relation"] = "uncertain"
    elif defect == "bad_quote": inventory["claims"][0]["source_evidence"][0]["quote"] += " altered"
    else: inventory["page_visual_coverage"][0]["status"] = "text_only"
    value[-2] = repair._request("verification", value[0], recipe(), PDF, value[1], OPTIONS, inventory=inventory, candidate=value[3])
    with pytest.raises(review.SemanticAuditError): diagnose(value)


@pytest.mark.parametrize("fault", ["marker", "schema", "instruction", "missing_image", "wrong_image", "extra_image",
    "image_position", "source", "candidate", "inventory", "literal_protocol", "unexpected_context"])
def test_initial_profile_and_trusted_context_cannot_be_swapped(fault):
    pages, units, inventory, candidate, request, data = case()
    request = ambiguity.adapt_request(request)
    payload = json.loads(request["prompt_text"])
    if fault == "marker": payload[ambiguity.KEY]["policy"] = "unknown"
    elif fault == "schema": request["response_format"]["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"].remove(ambiguity.STATUS)
    elif fault == "instruction": request["instructions"] = "altered\n" + request["instructions"]
    elif fault == "missing_image": request.pop("image_data_urls")
    elif fault == "wrong_image": request["image_data_urls"] = ("data:image/png;base64,Yg==", *request["image_data_urls"][1:])
    elif fault == "extra_image": request["image_data_urls"] += request["image_data_urls"][:1]
    elif fault == "image_position": payload["source_pages"][0]["image_position"] = 2
    elif fault == "source": payload["source_pages"][0]["original_source_text"] += " changed"
    elif fault == "candidate": payload["candidate_pages"][0]["text"] += " تغير"
    elif fault == "inventory": payload["source_inventory"]["claims"][0]["proposition"] += " changed"
    elif fault == "literal_protocol": payload["literal_protocol"][0]["expected_ar_tokens"] = ["invented"]
    else: payload["prior_findings"] = {"preferred_verdict":"equivalent"}
    request["prompt_text"] = review._prompt_json(payload)
    with pytest.raises(review.SemanticAuditError, match="target_ambiguity_profile"):
        repair.diagnose(review.audit._json(data), request, pages, units, inventory, candidate,
            semantic_target_ambiguity_policy=ambiguity.POLICY)


def test_unrelated_resolved_image_only_claim_is_not_a_new_global_restriction():
    pages, units, inventory, candidate, _, data = case()
    extra = deepcopy(inventory["claims"][0])
    extra.update(claim_id="extra_image", source_unit_ids=[], source_evidence=[{"kind":"image","page":1,"bbox":[.1,.1,.9,.9]}])
    inventory["claims"].append(extra)
    data["claim_results"].append({"claim_id":"extra_image","status":"equivalent","target_unit_ids":["T001"]})
    data["claim_results"][0]["status"] = ambiguity.STATUS
    request = repair._request("verification", pages, recipe(), PDF, units, OPTIONS, inventory=inventory, candidate=candidate)
    assert diagnose((pages, units, inventory, candidate, request, data))["eligible"]


def test_each_affected_owner_page_image_is_decoded_once_across_shared_claims(monkeypatch):
    pages, units, inventory, candidate, _, data = case()
    for name in ("also_first", "another_first"):
        claim = deepcopy(inventory["claims"][0])
        claim["claim_id"] = name
        inventory["claims"].append(claim)
        inventory["unit_coverage"][0]["claim_ids"].append(name)
        data["claim_results"].append({"claim_id":name,"status":ambiguity.STATUS,"target_unit_ids":["T001"]})
    for row in data["claim_results"]: row["status"] = ambiguity.STATUS
    calls, original = [], ambiguity._image
    def counted(value): calls.append(value); return original(value)
    monkeypatch.setattr(ambiguity,"_image",counted)
    request = repair._request("verification",pages,recipe(),PDF,units,OPTIONS,inventory=inventory,candidate=candidate)
    assert diagnose((pages,units,inventory,candidate,request,data))["eligible"]
    assert len(calls) == 2  # Three affected claims on page1, one on page2.


@pytest.mark.parametrize("defect", ["unknown", "null", "old_source", "old_repair", "refs", "pages", "budget", "model", "absent"])
def test_saved_optional_capability_is_validated_from_a_complete_fresh_baseline(tmp_path, defect):
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
    from tests.test_workflow_semantic_review_integration import saved_recipe
    _, saved, settings = saved_recipe(tmp_path)
    settings["ocr_engine"] = "api"
    assert saved[ambiguity.KEY] == ambiguity.POLICY and ordinary_semantic_audit_recipe(settings) == saved
    if defect == "unknown": saved[ambiguity.KEY] = "unknown"
    elif defect == "null": saved[ambiguity.KEY] = None
    elif defect == "old_source": saved["semantic_source_review_policy"] = "source_commitment_visual_v6"
    elif defect == "old_repair": saved["semantic_repair_policy"] = repair.POLICY_V3
    elif defect == "refs": saved.pop("semantic_unit_reference_policy")
    elif defect == "pages": saved.pop("semantic_page_coverage_policy")
    elif defect == "budget": saved["source_inventory_max_output_tokens"] = 32000
    elif defect == "model": saved.pop("semantic_review_model_policy")
    else: saved.pop(ambiguity.KEY)
    if defect == "absent": assert ambiguity.KEY not in ordinary_semantic_audit_recipe(settings)
    else:
        with pytest.raises(SemanticAuditRecipeError): ordinary_semantic_audit_recipe(settings)


REPAIRED = "طلب المدعى عليه جوابا مفصلا."


class TargetScenario:
    def __init__(self, outcome="equivalent"):
        self.outcome, self.verifiers, self.payloads = outcome, 0, []
    def __call__(self, body, data):
        if "text" not in body: return data
        payload = json.loads(body["input"][0]["content"][0]["text"])
        self.payloads.append(deepcopy(payload))
        value = json.loads(data["output"][0]["content"][0]["text"])
        if payload["stage"] == "verification":
            self.verifiers += 1
            status = ambiguity.STATUS if self.verifiers == 1 else "contradiction" if self.outcome in {"payer_invention","modality_change"} else self.outcome
            value["claim_results"][0]["status"] = status
        if payload["stage"] == "correction" and "prior_findings" in payload:
            for row in value["pages"]:
                row.update(status="no_change" if self.outcome == "noop" else "corrected",
                    corrected_text="" if self.outcome == "noop" else "not Arabic" if self.outcome == "invalid"
                        else "دفع مقدم الطلب المال." if self.outcome == "payer_invention"
                        else "أوجب المدعى عليه الجواب." if self.outcome == "modality_change" else REPAIRED,
                    reason_codes=[] if self.outcome == "noop" else ["material_meaning"])
        data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data


def workflow_case(tmp_path, *, outcome="equivalent", mutate=None):
    from legalpdf_translate.types import ImageMode
    from tests.test_semantic_review_model_integration import setup
    scenario = TargetScenario(outcome)
    def respond(body, data):
        data = scenario(body, data)
        return mutate(body, data, scenario) if mutate is not None else data
    config, http, flow = setup(tmp_path, mutate=respond)
    config = replace(config, image_mode=ImageMode.ALWAYS)
    return config, http, flow, scenario


def test_native_one_cycle_final_blindness_and_zero_call_same_and_new_workflow_replay(tmp_path, monkeypatch, record_property):
    from legalpdf_translate import workflow_semantic_audit as glue
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_semantic_review_model_integration import immutable
    config, http, flow, scenario = workflow_case(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    record_property("target_ambiguity_specimen", json.dumps({"run_dir":str(result.run_dir),
        "source_pdf":str(config.pdf_path),"requests":http.requests},ensure_ascii=False))
    assert len(http.requests) == 6 and scenario.verifiers == 2
    manifest = json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
    assert manifest["consumed_cycles"] == manifest["semantic_repair_policy"]["max_cycles"] == 1
    assert manifest["repair_trigger"] == "independent_verification" and manifest["selected_attempt"] == 1
    assert manifest["semantic_repair_policy"][ambiguity.KEY] == ambiguity.descriptor()
    assert flow._last_state.settings["ordinary_semantic_audit_recipe"][ambiguity.KEY] == ambiguity.POLICY
    initial, final = [r for r in http.requests if "text" in r and json.loads(r["input"][0]["content"][0]["text"])["stage"] == "verification"]
    assert ambiguity.KEY in json.loads(initial["input"][0]["content"][0]["text"])
    payload = json.loads(final["input"][0]["content"][0]["text"])
    assert ambiguity.KEY not in payload and "prior_findings" not in payload and "context_text" not in payload
    assert ambiguity.STATUS not in final["text"]["format"]["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"]
    assert not final["instructions"].endswith(ambiguity.INSTRUCTIONS)
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    call_ids = {row["call_id"] for row in journal["events"] if row["event"] == "begin" and row["purpose"] == "semantic_audit"}
    events = [row for row in journal["events"] if row["call_id"] in call_ids]
    assert len(events) == 10 and len({row["call_id"] for row in events if row["event"] == "begin"}) == 5
    before, requests = immutable(result.run_dir), deepcopy(http.requests)
    monkeypatch.setattr(glue,"fresh_recipe",lambda *a,**k:pytest.fail("Saved replay consulted a fresh recipe"))
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(client=http.client,gui_settings={}).run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert http.requests == requests and immutable(result.run_dir) == before


@pytest.mark.parametrize("outcome", ["noop", "invalid", "unresolved", "contradiction", ambiguity.STATUS,
    "payer_invention", "modality_change"])
def test_failed_revision_or_final_verdict_never_buys_another_cycle(tmp_path,outcome):
    config, http, flow, scenario = workflow_case(tmp_path,outcome=outcome)
    result = flow.run(config)
    assert not result.success
    assert scenario.verifiers == (1 if outcome in {"noop","invalid"} else 2)
    assert len(http.requests) == (5 if outcome in {"noop","invalid"} else 6)
    assert not (result.run_dir/"semantic_audit/manifest.json").exists()
    before = list(http.bodies)
    assert not flow.run(replace(config,resume=True)).success
    assert http.bodies == before


@pytest.mark.parametrize("first_status", ["equivalent","missing"])
def test_new_capability_does_not_restrict_old_nonambiguity_routes_to_image_backing(tmp_path,first_status):
    from tests.test_semantic_review_model_integration import setup
    scenario = TargetScenario()
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == "verification" and scenario.verifiers == 1:
                value = json.loads(data["output"][0]["content"][0]["text"])
                value["claim_results"][0]["status"] = first_status
                data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow = setup(tmp_path,mutate=mutate)  # Explicit configured Image Off.
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == (4 if first_status=="equivalent" else 6)
    manifest = json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
    assert manifest["consumed_cycles"] == int(first_status=="missing")


def test_unknown_initial_verifier_charge_never_dispatches_repair_or_rebuys(tmp_path):
    def unknown(body,data,scenario):
        if "text" in body and json.loads(body["input"][0]["content"][0]["text"])["stage"] == "verification":
            data["usage"]["input_tokens_details"].pop("cache_write_tokens")
        return data
    config,http,flow,_ = workflow_case(tmp_path,mutate=unknown)
    result = flow.run(config)
    assert not result.success and len(http.requests)==4
    assert not (result.run_dir/"semantic_audit/attempt_01").exists()
    before=list(http.bodies)
    assert not flow.run(replace(config,resume=True)).success and http.bodies==before


def test_cancelled_settled_initial_diagnostic_replays_without_repurchase_or_second_cycle(tmp_path):
    holder={}
    def cancel(body,data,scenario):
        if "text" in body and json.loads(body["input"][0]["content"][0]["text"])["stage"]=="verification" and scenario.verifiers==1:
            holder["flow"].cancel()
        return data
    config,http,flow,scenario=workflow_case(tmp_path,mutate=cancel)
    holder["flow"]=flow
    result=flow.run(config)
    assert not result.success and len(http.requests)==4
    bodies=list(http.bodies)
    resumed=flow.run(replace(config,resume=True))
    assert resumed.success,resumed.error
    assert len(http.requests)==6 and http.bodies[:len(bodies)]==bodies and scenario.verifiers==2
    manifest=json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
    assert manifest["consumed_cycles"]==1


def test_authority_consumed_cycle_never_profiles_or_repairs_the_final_new_status(tmp_path):
    from tests.test_source_enclosure_authority_workflow import EnclosureScenario,start
    class FinalAmbiguity(EnclosureScenario):
        def __call__(self,body,data):
            data=super().__call__(body,data)
            if "text" in body:
                payload=json.loads(body["input"][0]["content"][0]["text"])
                if payload["stage"]=="verification":
                    assert ambiguity.KEY not in payload
                    assert ambiguity.STATUS not in body["text"]["format"]["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"]
                    value=json.loads(data["output"][0]["content"][0]["text"])
                    value["claim_results"][0]["status"]=ambiguity.STATUS
                    data["output"][0]["content"][0]["text"]=json.dumps(value,ensure_ascii=False)
            return data
    scenario=FinalAmbiguity()
    config,http,flow=start(tmp_path,scenario)
    result=flow.run(config)
    assert not result.success and "diagnostic_status" in result.error and len(http.requests)==5
    before=list(http.bodies)
    assert not flow.run(replace(config,resume=True)).success and http.bodies==before
    assert not (result.run_dir/"semantic_audit/manifest.json").exists()
