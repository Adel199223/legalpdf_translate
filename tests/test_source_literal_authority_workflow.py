"""Actual ordinary SDK and native journal with fictional local HTTP responses."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.types import ImageMode
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_ordinary_semantic_audit import token
from tests.test_semantic_review_model_integration import setup, immutable
from tests.test_workflow_semantic_audit_integration import offline, PRIMARY, CORRECTED

OLD, NEW = "ZX1207", "ZX1208"


@pytest.fixture(autouse=True)
def retained_v3(monkeypatch):
    """This suite remains the exact saved literal-v1 / once-v3 contract."""
    fresh = glue.fresh_recipe
    def historical(*args, **kwargs):
        saved = fresh(*args, **kwargs)
        saved["semantic_repair_policy"] = repair.POLICY_V3
        saved["semantic_source_review_policy"] = "source_commitment_visual_v5"
        saved.pop("semantic_enclosure_authority_policy", None)
        saved.pop("source_enclosure_identity_policy", None)
        saved.pop("semantic_target_ambiguity_policy", None)
        saved.pop("semantic_enclosure_sequence_repair_policy", None)
        saved.pop("primary_page_evidence_policy", None)
        saved.pop("primary_literal_markup_policy", None)
        return saved
    monkeypatch.setattr(glue, "fresh_recipe", historical)


class AuthorityScenario:
    def __init__(self, *, quality=False, reject=False, noop=False):
        self.payloads = []
        self.quality, self.reject, self.noop = quality, reject, noop

    def __call__(self, body, data):
        if "text" not in body:
            data["output"][0]["content"][0]["text"] = "```\n"+PRIMARY+" "+token(OLD)+"\n```"
            return data
        payload = json.loads(body["input"][0]["content"][0]["text"])
        self.payloads.append(deepcopy(payload))
        stage = payload["stage"]
        if stage == "source_literal_authority":
            rows = []
            for old in payload["old_occurrence_lookups"]:
                source = next(p for p in payload["source_pages"] if p["page"] == old["page"])
                rows.append({"occurrence_id": old["occurrence_id"], "status": "replace", "exact_reading": NEW,
                    "ownership": "owned", "raw_span": None, "source_image": {"page": old["page"],
                        "image_sha256": source["image"]["sha256"], "bbox": [1,1,30,30]}})
            value = {"version": "source_literal_resolution_v1", "decisions": rows}
        else:
            value = json.loads(data["output"][0]["content"][0]["text"])
            if stage == "correction":
                for row in value["pages"]:
                    row.update(status="corrected", reason_codes=["material_meaning"],
                        corrected_text=CORRECTED+" "+token(NEW))
                    if self.quality and ("source_literal_certificate" not in payload or self.noop):
                        row["corrected_text"] = "("+row["corrected_text"]+")"
            elif stage == "verification" and self.reject:
                value["claim_results"][0]["status"] = "missing"
        data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data


def start(tmp_path, scenario):
    config,http,flow = setup(tmp_path,mutate=scenario)
    return replace(config,image_mode=ImageMode.ALWAYS),http,flow


def read(run,path):
    return json.loads((run/"semantic_audit"/path).read_bytes())


@pytest.mark.parametrize("quality,calls", [(False,5),(True,6)])
def test_native_authority_optional_replacement_blindness_settlement_and_replay(tmp_path,monkeypatch,quality,calls):
    scenario = AuthorityScenario(quality=quality)
    config,http,flow = start(tmp_path,scenario)
    result = flow.run(config)
    assert result.success,result.error
    assert len(http.requests) == calls
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved["semantic_repair_policy"] == repair.POLICY_V3
    assert saved["semantic_literal_authority_policy"] == "source_literal_authority_v1"
    resolver = next(p for p in scenario.payloads if p["stage"] == "source_literal_authority")
    assert NEW not in json.dumps(resolver)
    assert not set(resolver) & {"candidate_pages","primary_pages","source_inventory","context_text","rejected_proposal","prior_findings"}
    verifier = scenario.payloads[-1]
    assert verifier["stage"] == "verification"
    assert not set(verifier) & {"primary_pages","source_literal_certificate","rejected_proposal","prior_findings","context_text"}
    assert verifier["source_literal_assertions"][0]["visible_reading"] == NEW
    assert OLD not in json.dumps(verifier)
    manifest = read(result.run_dir,"manifest.json")
    assert manifest["consumed_cycles"] == 1 and manifest["repair_trigger"] == "source_literal_authority"
    assert manifest["stages"][1]["outcome"] == "rejected_literal_authority"
    assert read(result.run_dir,"candidate_origin.json")["origin"] == ("single_full_replacement" if quality else "initial_correction_revalidated")
    if quality:
        replacement = [p for p in scenario.payloads if p["stage"] == "correction"][-1]
        assert replacement["primary_pages"][0]["text"] == PRIMARY+" [["+OLD+"]]"
        assert replacement["rejected_proposal"]["untrusted"]
    else:
        assert not (result.run_dir/"semantic_audit/attempt_01/correction").exists()
    proofs = [read(result.run_dir,row["native_settlement_path"]) for row in manifest["stages"]]
    assigned = [key for proof in proofs for key in proof["call_ids"]]
    actual = [row["call_id"] for row in json.loads(flow._dispatch_accounting.journal_path.read_bytes())["events"]
        if row["event"] == "begin" and row["purpose"] == "semantic_audit"]
    assert len(assigned) == len(set(assigned)) == calls-1 and set(assigned) == set(actual)
    before = immutable(result.run_dir)
    monkeypatch.setattr(glue,"fresh_recipe",lambda *a,**k: pytest.fail("replay selected fresh semantics"))
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == calls and immutable(result.run_dir) == before


@pytest.mark.parametrize("quality,reject,noop,calls", [(False,True,False,5),(True,False,True,5)])
def test_consumed_authority_cycle_never_repairs_verifier_or_repeats_noop(tmp_path,quality,reject,noop,calls):
    scenario = AuthorityScenario(quality=quality,reject=reject,noop=noop)
    config,http,flow = start(tmp_path,scenario)
    result = flow.run(config)
    assert not result.success and len(http.requests) == calls
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert immutable(result.run_dir) == before and len(http.requests) == calls


@pytest.mark.parametrize("stage", ["source_literal_authority","replacement","verification"])
@pytest.mark.parametrize("failure", ["unknown_usage","refused","incomplete"])
def test_native_hard_stop_never_rebuys_resolver_or_followup(tmp_path,stage,failure):
    scenario = AuthorityScenario(quality=True)
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body:
            payload = scenario.payloads[-1]
            actual = "replacement" if payload["stage"] == "correction" and "source_literal_certificate" in payload else payload["stage"]
            if actual == stage:
                if failure == "unknown_usage": data["usage"]["input_tokens_details"].pop("cache_write_tokens")
                elif failure == "refused": data["output"][0]["content"] = [{"type":"refusal","refusal":"Fictional refusal."}]
                else: data.update(status="incomplete",incomplete_details={"reason":"max_output_tokens"})
        return data
    config,http,flow = start(tmp_path,scenario)
    http.mutate = mutate
    result = flow.run(config)
    assert not result.success
    count = len(http.requests)
    assert count == {"source_literal_authority":4,"replacement":5,"verification":6}[stage]
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == count and immutable(result.run_dir) == before


@pytest.mark.parametrize("phase", [1,2,3,4,5])
def test_cancellation_after_each_semantic_response_reuses_exact_settled_boundaries(tmp_path,phase):
    scenario = AuthorityScenario(quality=True)
    holder = {}
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body and len(scenario.payloads) == phase:
            holder["flow"].cancel()
        return data
    config,http,flow = start(tmp_path,scenario)
    http.mutate = mutate; holder["flow"] = flow
    result = flow.run(config)
    assert not result.success and len(http.requests) == phase+1
    bodies = list(http.bodies)
    result = flow.run(replace(config,resume=True))
    assert result.success,result.error
    assert len(http.requests) == 6 and http.bodies[:len(bodies)] == bodies


@pytest.mark.parametrize("path", ["source_literal_registry.json","eligibility.json","source_literal_certificate.json",
    "source_literal_validation_context.json","candidate_origin.json","attempt_01/source_literal_authority/stage_record.json"])
def test_exact_projection_and_certificate_tamper_stops_resume_and_offline_selection(tmp_path,path):
    config,http,flow = start(tmp_path,AuthorityScenario(quality=True))
    result = flow.run(config)
    assert result.success,result.error
    file = result.run_dir/"semantic_audit"/path
    file.write_bytes(file.read_bytes()+b" ")
    count = len(http.requests)
    assert not flow.run(replace(config,resume=True)).success
    with pytest.raises(Exception):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(http.requests) == count


@pytest.mark.parametrize("path", ["eligibility.json","source_literal_certificate.json","source_literal_validation_context.json",
    "candidate_origin.json","attempt_01/source_literal_authority/stage_record.json","attempt_01/correction_baseline.json"])
@pytest.mark.parametrize("when", ["before","after"])
def test_restart_reconstructs_only_exact_settled_postprocessing(tmp_path,monkeypatch,path,when):
    scenario = AuthorityScenario(quality=True)
    config,http,flow = start(tmp_path,scenario)
    original = repair._persist
    stopped = []
    def persist(file,value,**options):
        hit = file.as_posix().endswith("/semantic_audit/"+path) and not stopped
        if hit and when == "before":
            stopped.append(True); review._fail("operation_cancelled")
        original(file,value,**options)
        if hit and when == "after":
            stopped.append(True); flow.cancel()
    monkeypatch.setattr(repair,"_persist",persist)
    result = flow.run(config)
    assert not result.success and stopped
    bodies = list(http.bodies)
    result = flow.run(replace(config,resume=True))
    assert result.success,result.error
    assert len(http.requests) == 6 and http.bodies[:len(bodies)] == bodies


@pytest.mark.parametrize("artifact", ["source_literal_registry.json","eligibility.json","source_literal_certificate.json",
    "source_literal_validation_context.json","candidate_origin.json"])
def test_missing_evidence_after_later_paid_boundary_never_reconstructs_or_rebuys(tmp_path,artifact):
    config,http,flow = start(tmp_path,AuthorityScenario(quality=True))
    result = flow.run(config)
    assert result.success,result.error
    (result.run_dir/"semantic_audit"/artifact).unlink()
    count = len(http.requests)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == count
    assert not (result.run_dir/"semantic_audit"/artifact).exists()


@pytest.mark.parametrize("artifact,when,recovers", [
    ("intent.json","before",True),("intent.json","after",False),
    ("raw_response.json","before",False),("raw_response.json","after",False),
    ("raw_receipt.json","before",False),("raw_receipt.json","after",True),
    ("native_settlement.json","before",True),("native_settlement.json","after",True)])
def test_resolver_paid_boundary_crash_never_duplicates_a_dispatch(tmp_path,monkeypatch,artifact,when,recovers):
    scenario = AuthorityScenario(quality=True)
    config,http,flow = start(tmp_path,scenario)
    original = review.audit._write_new
    stopped = []
    def write(path,value):
        hit = path.name == artifact and "source_literal_authority" in path.parent.name and not stopped
        if hit and when == "before":
            stopped.append(True); review._fail("operation_cancelled")
        original(path,value)
        if hit and when == "after":
            stopped.append(True); review._fail("operation_cancelled")
    monkeypatch.setattr(review.audit,"_write_new",write)
    result = flow.run(config)
    assert not result.success and stopped
    bodies = list(http.bodies)
    count = len(http.requests)
    resumed = flow.run(replace(config,resume=True))
    assert resumed.success is recovers,resumed.error
    assert http.bodies[:len(bodies)] == bodies
    assert len(http.requests) == (6 if recovers else count)


@pytest.mark.parametrize("damage", ["missing_capability","missing_repair","unknown_capability","old_repair_with_capability"])
def test_saved_authority_capability_requires_exact_fresh_pair(tmp_path,damage):
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
    from tests.test_workflow_semantic_review_integration import saved_recipe
    _,saved,settings = saved_recipe(tmp_path)
    assert saved["semantic_repair_policy"] == repair.POLICY_V3
    if damage == "missing_capability": saved.pop("semantic_literal_authority_policy")
    elif damage == "missing_repair": saved.pop("semantic_repair_policy")
    elif damage == "unknown_capability": saved["semantic_literal_authority_policy"] = "source_literal_authority_v99"
    else: saved["semantic_repair_policy"] = repair.POLICY_V2
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("index", [0,1])
def test_genuine_prechange_native_v1_v2_requests_artifacts_and_zero_call_replay(tmp_path,monkeypatch,index):
    fixture = json.loads((Path(__file__).parent/"fixtures/source_literal_authority_prechange_native.json").read_bytes())
    assert fixture["fake_sdk_only"] is True
    assert fixture["generator_sha256"] == "0719f79816f5c47000e36e4826640a4390e87ee70fbf10556776a7f7da18aa38"
    assert fixture["glue_sha256"] == "d146acfe103e5f431f1b3f9fa9275be645c51701d46b4d6aa7d82af9ea75ccf4"
    case = fixture["cases"][index]
    directory = tmp_path/"audit"; directory.mkdir()
    for name,value in case["evidence"].items():
        path = directory/name; path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(value.encode("utf-8"))
    before = {p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    requests = []
    original = repair._request
    def request(*args,**kwargs):
        result = original(*args,**kwargs); requests.append(result); return result
    monkeypatch.setattr(repair,"_request",request)
    def guard(**stage):
        if stage["action"] == "final": return {"native_calls":len(case["proofs"])}
        proof = case["proofs"][stage["stage_id"]]
        assert proof["request_sha256"] == review.audit._sha(review.audit._json(stage["request"]))
        return proof
    result = repair.load_semantic_repair(pages=[review.SemanticAuditPage(**p) for p in case["pages"]],
        recipe=review.SemanticAuditRecipe(**case["recipe"]),pdf_sha256=case["pdf_sha256"],evidence_dir=directory,
        semantic_repair_policy=case["policy"],stage_guard=guard,**case["options"])
    assert result.reused
    assert review.audit._json(requests) == review.audit._json(case["requests"])
    assert {p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("decision", ["unchanged","unresolved"])
def test_resolver_no_source_correction_is_terminal_and_does_not_become_generic_retry(tmp_path,decision):
    scenario = AuthorityScenario()
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body and scenario.payloads[-1]["stage"] == "source_literal_authority":
            value = json.loads(data["output"][0]["content"][0]["text"])
            value["decisions"][0].update(status=decision,exact_reading=OLD)
            data["output"][0]["content"][0]["text"] = json.dumps(value)
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    result = flow.run(config)
    assert not result.success and len(http.requests) == 4
    assert read(result.run_dir,"eligibility.json")["consumed_cycles"] == 1
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 4 and immutable(result.run_dir) == before


def test_resolver_transport_retry_is_one_settled_stage_and_every_actual_call_is_counted(tmp_path):
    import httpx
    config,http,flow = start(tmp_path,AuthorityScenario(quality=True))
    http.client._max_transport_retries = 1
    http.client._base_backoff_seconds = 0
    original = http.http._transport.handler
    injected = []
    def handler(request):
        response = original(request)
        body = json.loads(request.content)
        if "text" in body:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == "source_literal_authority" and not injected:
                injected.append(True)
                value = json.loads(response.content); value["status"] = "failed"
                return httpx.Response(429,json=value,headers={"content-type":"application/json"})
        return response
    http.http._transport.handler = handler
    result = flow.run(config)
    assert result.success,result.error
    assert len(http.requests) == 7
    manifest = read(result.run_dir,"manifest.json")
    resolver = next(r for r in manifest["stages"] if r["stage"] == "source_literal_authority")
    proof = read(result.run_dir,resolver["native_settlement_path"])
    assert len(proof["call_ids"]) == 2 and resolver["usage"]["input_tokens"] == 200
    assert manifest["usage"]["input_tokens"] == 600


@pytest.mark.parametrize("image_off,conflict", [(False,False),(True,False),(False,True),(True,True)])
def test_unavailable_registry_normal_native_path_replay_and_conflict_never_dispatches_resolver(tmp_path,image_off,conflict):
    value = "https://fictional.example/"+"segment"*80
    scenario = AuthorityScenario()
    def mutate(body,data):
        data = scenario(body,data)
        text = data["output"][0]["content"][0]["text"]
        if "text" not in body:
            text = text.replace(OLD,value)
        elif scenario.payloads[-1]["stage"] == "correction":
            parsed = json.loads(text)
            for row in parsed["pages"]:
                row["corrected_text"] = CORRECTED+" "+token("DIFFERENT" if conflict else value)
            text = json.dumps(parsed,ensure_ascii=False)
        data["output"][0]["content"][0]["text"] = text
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    if image_off: config = replace(config,image_mode=ImageMode.OFF)
    result = flow.run(config)
    assert result.success is (not conflict),result.error
    assert len(http.requests) == (3 if conflict else 4)
    assert not any(p["stage"] == "source_literal_authority" for p in scenario.payloads)
    assert read(result.run_dir,"source_literal_registry.json")["availability"] == "ineligible_capacity"
    before = immutable(result.run_dir)
    assert flow.run(replace(config,resume=True)).success is (not conflict)
    assert len(http.requests) == (3 if conflict else 4) and immutable(result.run_dir) == before
    file = result.run_dir/"semantic_audit/source_literal_registry.json"
    file.write_bytes(file.read_bytes()+b" ")
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == (3 if conflict else 4)


def test_sole_ocr_required_url_autorestoration_activates_authority_before_first_verifier(tmp_path,monkeypatch):
    from legalpdf_translate import workflow as workflow_module
    from legalpdf_translate.ocr_engine import OcrResult
    from legalpdf_translate.types import OcrMode, OcrEnginePolicy
    old,new = "https://tribuna1.example","https://tribunal.example"
    payloads = []
    def mutate(body,data):
        if "text" not in body:
            text = "```\n"+PRIMARY+" "+token(old)+"\n```"
        else:
            payload = json.loads(body["input"][0]["content"][0]["text"]); payloads.append(payload)
            if payload["stage"] == "source_literal_authority":
                lookup = payload["old_occurrence_lookups"][0]
                assert len(payload["old_occurrence_lookups"]) == 1 and lookup["required_index"] == 0
                assert new not in json.dumps(payload)
                value = {"version":"source_literal_resolution_v1","decisions":[{
                    "occurrence_id":lookup["occurrence_id"],"status":"replace","exact_reading":new,"ownership":"owned",
                    "raw_span":{"start":0,"end":len(old)},"source_image":{"page":1,
                        "image_sha256":payload["source_pages"][0]["image"]["sha256"],"bbox":[1,1,200,30]}}]}
            else:
                value = json.loads(data["output"][0]["content"][0]["text"])
                if payload["stage"] == "correction":
                    value["pages"][0].update(status="corrected",corrected_text=CORRECTED+" "+token(new),reason_codes=["material_meaning"])
            text = json.dumps(value,ensure_ascii=False)
        data["output"][0]["content"][0]["text"] = text
        return data
    config,http,flow = setup(tmp_path,mutate=mutate)
    config = replace(config,image_mode=ImageMode.ALWAYS,ocr_mode=OcrMode.ALWAYS,ocr_engine=OcrEnginePolicy.LOCAL)
    flow._ocr_engine_factory = lambda _: object()
    monkeypatch.setattr(workflow_module,"ocr_pdf_page_text",lambda *a,**k: OcrResult(
        text=old,engine="local",failed_reason=None,chars=len(old),quality_score=.9,selected_pass="fictional"))
    result = flow.run(config)
    assert result.success,result.error
    assert [p["stage"] for p in payloads] == ["source_inventory","correction","source_literal_authority","verification"]
    assert len(http.requests) == 5
    original = flow._last_paths.pages_dir.joinpath("page_0001.txt").read_text(encoding="utf-8")
    assert old in original and new not in original
    source = json.loads((result.run_dir/"semantic_source/page_0001.json").read_bytes())
    assert source["expected_ar_tokens"] == [old]
    historical = review.audit.evaluate_output("```\n"+CORRECTED+" "+token(new)+"\n```",review.audit.TargetLang.AR,
        expected_ar_tokens=[old],ar_source_text=source["source_text"],primary_normalized_text=original,
        source_field_policy="baseline_label_value_v1")
    assert historical.ok and old in historical.normalized_text
    assert new in (result.run_dir/"semantic_audit/page_0001.txt").read_text(encoding="utf-8")
    before = immutable(result.run_dir)
    assert flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 5 and immutable(result.run_dir) == before
