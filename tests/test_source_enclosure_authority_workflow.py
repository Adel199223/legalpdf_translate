"""Fresh ordinary native SDK/journal with fictional enclosure source assertions."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_enclosure_authority as enclosure
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.types import ImageMode
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_ordinary_semantic_audit import token
from tests.test_semantic_review_model_integration import setup, immutable
from tests.test_workflow_semantic_audit_integration import PRIMARY, CORRECTED
from tests.test_source_enclosure_authority import VALUE


class EnclosureScenario:
    def __init__(self, *, quality=False, mixed=False, no_change=False, reject=False):
        self.payloads = []
        self.quality, self.mixed, self.no_change, self.reject = quality, mixed, no_change, reject

    def tail(self, *, original=False):
        first = token(VALUE) if original else "["+token(VALUE)+"]"
        result = " المرجع "+first+" ثم "+token("AB45")+" ثم "+token(VALUE)
        if self.mixed:
            result += " "+token("ZX1207" if original else "ZX1208")
        return result

    def __call__(self,body,data):
        if "text" not in body:
            data["output"][0]["content"][0]["text"] = "```\n"+PRIMARY+self.tail(original=True)+"\n```"
            return data
        payload = json.loads(body["input"][0]["content"][0]["text"])
        self.payloads.append(deepcopy(payload))
        stage = payload["stage"]
        if stage == "source_literal_authority":
            literals = []
            for old in payload["old_occurrence_lookups"]:
                source = next(p for p in payload["source_pages"] if p["page"] == old["page"])
                literals.append({"occurrence_id":old["occurrence_id"],"status":"replace","exact_reading":"ZX1208",
                    "ownership":"owned","raw_span":None,"source_image":{"page":old["page"],
                        "image_sha256":source["image"]["sha256"],"bbox":[1,1,25,25]}})
            observations = []
            for i,old in enumerate(payload["old_enclosure_lookups"]):
                source = next(p for p in payload["source_pages"] if p["page"] == old["page"])
                observations.append({"occurrence_id":old["occurrence_id"],"exact_reading":old["value"],
                    "ownership":"owned","enclosure":"square" if i == 0 else "none",
                    "source_image":{"page":old["page"],"image_sha256":source["image"]["sha256"],
                        "bbox":[1+i*30,50,25+i*30,75]}})
            value = {"version":enclosure.RESPONSE,"literal_decisions":literals,"enclosure_observations":observations}
        else:
            value = json.loads(data["output"][0]["content"][0]["text"])
            if stage == "correction":
                for row in value["pages"]:
                    row.update(status="corrected",reason_codes=["material_meaning"],corrected_text=CORRECTED+self.tail())
                    if self.quality and "source_literal_certificate" not in payload:
                        # Separate unsupported prose pair: eligible quality
                        # rejection, never an enclosing/nested token pair.
                        row["corrected_text"] += " (إضافة)"
                    if self.no_change and "source_literal_certificate" in payload:
                        row.update(status="no_change",corrected_text="",reason_codes=[])
            elif stage == "verification" and self.reject:
                value["claim_results"][0]["status"] = "missing"
        data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data


def start(tmp_path,scenario):
    config,http,flow = setup(tmp_path,mutate=scenario)
    return replace(config,image_mode=ImageMode.ALWAYS),http,flow


class UnisolatedEnclosureScenario(EnclosureScenario):
    def __call__(self,body,data):
        data = super().__call__(body,data)
        if "text" in body:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == "correction":
                value = json.loads(data["output"][0]["content"][0]["text"])
                for row in value["pages"]:
                    row["corrected_text"] = row["corrected_text"].replace("\u2066","").replace("\u2069","")
                data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data


@pytest.mark.parametrize("quality,reject,calls", [(False,False,5),(True,False,6),(False,True,5)])
def test_unisolated_enclosure_full_native_flow_keeps_blind_verifier_and_one_cycle(tmp_path,quality,reject,calls):
    scenario = UnisolatedEnclosureScenario(quality=quality,reject=reject)
    config,http,flow = start(tmp_path,scenario)
    result = flow.run(config)
    assert result.success is not reject, result.error
    assert len(http.requests) == calls
    stages = [row["stage"] for row in scenario.payloads]
    assert stages.count("source_literal_authority") == 1 and stages.count("verification") == 1
    assert stages.count("correction") == (2 if quality else 1)
    verifier = scenario.payloads[-1]
    assert verifier["stage"] == "verification"
    assert not set(verifier) & {"primary_pages","source_literal_certificate","rejected_proposal","prior_findings"}
    audit = result.run_dir/"semantic_audit"
    eligibility = json.loads((audit/"eligibility.json").read_bytes())
    assert eligibility["consumed_cycles"] == 1
    raw = json.loads((audit/"attempt_00/correction/raw_response.json").read_bytes())["raw_output"]
    assert "[[[" in raw and "\u2066" not in raw and "\u2069" not in raw
    if result.success:
        manifest = json.loads((audit/"manifest.json").read_bytes())
        assert manifest["automated_semantic_verified"] and manifest["consumed_cycles"] == 1
    else:
        assert not (audit/"manifest.json").exists()


class CarriedScenario(EnclosureScenario):
    def __init__(self, *, pair="round", pure=False, quality=False, no_change=False):
        super().__init__(mixed=True,quality=quality,no_change=no_change)
        self.pair,self.pure=pair,pure

    def tail(self, *, original=False):
        a,b=enclosure._PAIRS[self.pair]
        value=token("ZX1207" if original else "ZX1208")
        return ((" المرجع "+a+value+b) if self.pure else super().tail(original=original).replace(value,a+value+b))


class CertifiedDisagreementScenario(CarriedScenario):
    def __init__(self, *, final_damage=None):
        super().__init__()
        self.final_damage=final_damage

    def __call__(self,body,data):
        data=super().__call__(body,data)
        if "text" not in body:return data
        payload=json.loads(body["input"][0]["content"][0]["text"])
        value=json.loads(data["output"][0]["content"][0]["text"])
        if payload["stage"]=="source_literal_authority":
            value["literal_decisions"][0]["exact_reading"]="ZX1209"
        elif payload["stage"]=="correction" and "source_literal_certificate" in payload:
            for row in value["pages"]:
                row["corrected_text"]=row["corrected_text"].replace("ZX1208","ZX1209")
                if self.final_damage=="sequence":row["corrected_text"]+=" "+token("EXTRA9")
                elif self.final_damage=="pair":row["corrected_text"]=row["corrected_text"].replace("("+token("ZX1209")+")",token("ZX1209"))
                elif self.final_damage=="no_change":row.update(status="no_change",corrected_text="",reason_codes=[])
        data["output"][0]["content"][0]["text"]=json.dumps(value,ensure_ascii=False)
        return data


def test_native_initial_certified_sequence_disagreement_single_replacement_and_replay(tmp_path):
    scenario=CertifiedDisagreementScenario()
    config,http,flow=start(tmp_path,scenario)
    result=flow.run(config);assert result.success,result.error
    assert len(http.requests)==6
    assert [p["stage"] for p in scenario.payloads]==["source_inventory","correction","source_literal_authority","correction","verification"]
    audit=result.run_dir/"semantic_audit"
    manifest=json.loads((audit/"manifest.json").read_bytes())
    assert manifest["consumed_cycles"]==1
    assert json.loads((audit/"candidate_origin.json").read_bytes())["origin"]=="single_full_replacement"
    resolver=scenario.payloads[2]
    assert "ZX1208" not in review.audit._json(resolver) and "ZX1209" not in review.audit._json(resolver)
    before=immutable(result.run_dir)
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests)==6 and immutable(result.run_dir)==before


@pytest.mark.parametrize("damage",["sequence","pair","no_change"])
def test_native_certified_initial_mismatch_never_relaxes_replacement_final_guard(tmp_path,damage):
    scenario=CertifiedDisagreementScenario(final_damage=damage)
    config,http,flow=start(tmp_path,scenario)
    result=flow.run(config)
    assert not result.success and len(http.requests)==5
    assert not any(p["stage"]=="verification" for p in scenario.payloads)
    before=immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests)==5 and immutable(result.run_dir)==before


@pytest.mark.parametrize("path",["source_literal_validation_context.json","attempt_01/correction_baseline.json","candidate_origin.json"])
@pytest.mark.parametrize("when",["before","after"])
def test_certified_initial_transition_restarts_without_repeating_settled_calls(tmp_path,monkeypatch,path,when):
    scenario=CertifiedDisagreementScenario();config,http,flow=start(tmp_path,scenario)
    original=repair._persist;stopped=[]
    def persist(file,value,**options):
        hit=file.as_posix().endswith("/semantic_audit/"+path) and not stopped
        if hit and when=="before":stopped.append(True);review._fail("operation_cancelled")
        original(file,value,**options)
        if hit and when=="after":stopped.append(True);flow.cancel()
    monkeypatch.setattr(repair,"_persist",persist)
    result=flow.run(config);assert not result.success and stopped
    bodies=list(http.bodies)
    result=flow.run(replace(config,resume=True));assert result.success,result.error
    assert len(http.requests)==6 and http.bodies[:len(bodies)]==bodies
    assert [p["stage"] for p in scenario.payloads].count("source_literal_authority")==1


@pytest.mark.parametrize("pair,pure,quality,calls",[("round",True,False,5),("square",True,False,5),
    ("curly",True,False,5),("round",False,False,5),("round",False,True,6)])
def test_native_carried_existing_pair_single_certificate_blindness_replay_and_docx(tmp_path,pair,pure,quality,calls):
    scenario=CarriedScenario(pair=pair,pure=pure,quality=quality)
    config,http,flow=start(tmp_path,scenario)
    result=flow.run(config)
    assert result.success,result.error
    assert len(http.requests)==calls
    audit=result.run_dir/"semantic_audit"
    cert=json.loads((audit/"source_literal_certificate.json").read_bytes())
    assert len(cert["carried_original_pairs"])==1
    context=json.loads((audit/"source_literal_validation_context.json").read_bytes())
    assert any(o.get("basis")=="unchanged_original_primary_pair_v1" for p in context["enclosure_obligations"] for o in p["occurrences"])
    resolver=next(p for p in scenario.payloads if p["stage"]=="source_literal_authority")
    assert "carried_original_pairs" not in resolver and "ZX1208" not in review.audit._json(resolver)
    verifier=scenario.payloads[-1]
    assert verifier["stage"]=="verification" and not any(o["bare_reading"]=="ZX1208" for o in verifier.get("source_enclosure_observations",[]))
    manifest=json.loads((audit/"manifest.json").read_bytes())
    assert manifest["consumed_cycles"]==1 and manifest["repair_trigger"]=="source_literal_authority"
    before=immutable(result.run_dir)
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests)==calls and immutable(result.run_dir)==before


def test_native_carried_replacement_no_change_still_uses_actual_old_primary_and_stops(tmp_path):
    scenario=CarriedScenario(quality=True,no_change=True)
    config,http,flow=start(tmp_path,scenario)
    result=flow.run(config)
    assert not result.success and "final_sequence_mismatch" in result.error
    assert len(http.requests)==5 and not any(p["stage"]=="verification" for p in scenario.payloads)
    before=immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests)==5 and immutable(result.run_dir)==before


def test_native_carried_metadata_tamper_stops_without_repurchase(tmp_path):
    scenario=CarriedScenario(pure=True)
    config,http,flow=start(tmp_path,scenario)
    result=flow.run(config);assert result.success,result.error
    path=result.run_dir/"semantic_audit/source_literal_certificate.json"
    value=json.loads(path.read_bytes());value.pop("carried_original_pairs")
    path.write_bytes(review.audit._json(value).encode())
    assert not flow.run(replace(config,resume=True)).success
    with pytest.raises((ValueError,RuntimeError)):TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(http.requests)==5


@pytest.mark.parametrize("quality,mixed,calls", [(False,False,5),(True,False,6),(False,True,5),(True,True,6)])
def test_pure_and_mixed_enclosure_native_request_projection_diagnostic_replay_and_docx(tmp_path,monkeypatch,quality,mixed,calls):
    scenario = EnclosureScenario(quality=quality,mixed=mixed)
    config,http,flow = start(tmp_path,scenario)
    result = flow.run(config)
    assert result.success,result.error
    assert len(http.requests) == calls
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved["semantic_repair_policy"] == repair.POLICY_V4
    assert saved["semantic_enclosure_authority_policy"] == enclosure.POLICY
    resolver = next(p for p in scenario.payloads if p["stage"] == "source_literal_authority")
    assert len(resolver["old_enclosure_lookups"]) == 2
    assert not set(resolver) & {"primary_pages","candidate_pages","rejected_proposal","source_inventory","context_text","prior_findings"}
    assert "enclosure" not in review.audit._json(resolver["old_enclosure_lookups"])
    verifier = scenario.payloads[-1]
    assert verifier["stage"] == "verification" and len(verifier["source_enclosure_observations"]) == 2
    assert not set(verifier) & {"primary_pages","source_literal_certificate","rejected_proposal","correction_validation_diagnostic","prior_findings"}
    audit = result.run_dir/"semantic_audit"
    cert = json.loads((audit/"source_literal_certificate.json").read_bytes())
    assert cert["version"] == enclosure.CERTIFICATE
    context = json.loads((audit/"source_literal_validation_context.json").read_bytes())
    assert context["version"] == enclosure.CONTEXT
    manifest = json.loads((audit/"manifest.json").read_bytes())
    assert manifest["consumed_cycles"] == 1
    if quality:
        request = [p for p in scenario.payloads if p["stage"] == "correction"][-1]
        assert request["rejected_proposal"]["untrusted"]
        assert request["correction_validation_diagnostic"]["trigger"] == "new_actionable_quality_failure"
        assert "[["+VALUE+"]]" in request["primary_pages"][0]["text"]
        assert "[ [["+VALUE+"]] ]" not in request["primary_pages"][0]["text"]
    stage_proofs = [json.loads((audit/r["native_settlement_path"]).read_bytes()) for r in manifest["stages"]]
    actual = [e["call_id"] for e in json.loads(flow._dispatch_accounting.journal_path.read_bytes())["events"]
        if e["event"] == "begin" and e["purpose"] == "semantic_audit"]
    allocated = [v for proof in stage_proofs for v in proof["call_ids"]]
    assert len(allocated) == len(set(allocated)) == calls-1 and set(allocated) == set(actual)
    before = immutable(result.run_dir)
    monkeypatch.setattr(glue,"fresh_recipe",lambda *a,**k: pytest.fail("saved replay selected fresh policy"))
    assert flow.run(replace(config,resume=True)).success
    docx = TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    from docx import Document
    assert VALUE in "\n".join(p.text for p in Document(docx).paragraphs)
    assert len(http.requests) == calls and immutable(result.run_dir) == before


@pytest.mark.parametrize("stage", ["source_literal_authority","replacement","verification"])
@pytest.mark.parametrize("failure", ["unknown_usage","refused","incomplete"])
def test_native_enclosure_hard_stop_no_repurchase(tmp_path,stage,failure):
    scenario = EnclosureScenario(quality=True)
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
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    result = flow.run(config)
    assert not result.success and len(http.requests) == {"source_literal_authority":4,"replacement":5,"verification":6}[stage]
    before = immutable(result.run_dir); count = len(http.requests)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == count and immutable(result.run_dir) == before


@pytest.mark.parametrize("phase", [1,2,3,4,5])
def test_cancellation_every_semantic_boundary_reuses_native_evidence(tmp_path,phase):
    scenario = EnclosureScenario(quality=True); holder = {}
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body and len(scenario.payloads) == phase: holder["flow"].cancel()
        return data
    config,http,flow = start(tmp_path,scenario); holder["flow"] = flow; http.mutate = mutate
    result = flow.run(config)
    assert not result.success and len(http.requests) == phase+1
    bodies = list(http.bodies)
    result = flow.run(replace(config,resume=True))
    assert result.success,result.error
    assert len(http.requests) == 6 and http.bodies[:len(bodies)] == bodies


@pytest.mark.parametrize("artifact", ["source_literal_registry.json","eligibility.json","source_literal_certificate.json",
    "source_literal_validation_context.json","candidate_origin.json","attempt_01/source_literal_authority/stage_record.json"])
def test_enclosure_tamper_replay_and_offline_stop_without_calls(tmp_path,artifact):
    config,http,flow = start(tmp_path,EnclosureScenario(quality=True))
    result = flow.run(config)
    assert result.success,result.error
    file = result.run_dir/"semantic_audit"/artifact; file.write_bytes(file.read_bytes()+b" ")
    count = len(http.requests)
    assert not flow.run(replace(config,resume=True)).success
    with pytest.raises(Exception): TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(http.requests) == count


@pytest.mark.parametrize("no_change,reject", [(True,False),(False,True)])
def test_shared_cycle_exhaustion_and_original_no_change_are_terminal(tmp_path,no_change,reject):
    config,http,flow = start(tmp_path,EnclosureScenario(quality=True,no_change=no_change,reject=reject))
    result = flow.run(config)
    assert not result.success and len(http.requests) == (5 if no_change else 6)
    count = len(http.requests)
    assert not flow.run(replace(config,resume=True)).success and len(http.requests) == count


@pytest.mark.parametrize("index", [0,1])
def test_genuine_pre_enclosure_v3_success_and_failed_native_histories_exact_replay(tmp_path,monkeypatch,index):
    fixture = json.loads((Path(__file__).parent/"fixtures/source_enclosure_prechange_v3_native.json").read_bytes())
    assert fixture["fictional_only"] and fixture["baseline_runtime_sha256"] == "ff57c72a09f9107022ed61e341f26aff5091402b55207080d73e767b47601eb0"
    case = fixture["cases"][index]
    directory = tmp_path/"audit"; directory.mkdir()
    for name,value in case["evidence"].items():
        file = directory/name; file.parent.mkdir(parents=True,exist_ok=True); file.write_bytes(value.encode("utf-8"))
    before = {p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob("*") if p.is_file()}
    requests = []; original = review._stage
    def observe(*args,**kwargs):
        requests.append(args[1]); return original(*args,**kwargs)
    monkeypatch.setattr(review,"_stage",observe)
    def guard(**stage):
        if stage["action"] == "final": return {"native_calls":len(case["proofs"])}
        proof = case["proofs"][stage["stage_id"]]
        assert proof["request_sha256"] == review.audit._sha(review.audit._json(stage["request"]))
        return proof
    arguments = dict(pages=[review.SemanticAuditPage(**p) for p in case["pages"]],
        recipe=review.SemanticAuditRecipe(**case["recipe"]),pdf_sha256=case["pdf_sha256"],evidence_dir=directory,
        source_origins=case["source_origins"],stage_guard=guard,**case["options"])
    if case["failed"]:
        with pytest.raises(review.SemanticAuditError,match=case["expected_error"]): repair.load_semantic_repair(**arguments)
    else: assert repair.load_semantic_repair(**arguments).reused
    assert review.audit._json(requests) == review.audit._json(case["requests"])
    assert {p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("stage", ["source_literal_authority","replacement","verification"])
@pytest.mark.parametrize("artifact,when,recovers", [
    ("intent.json","before",True),("intent.json","after",False),
    ("raw_response.json","before",False),("raw_response.json","after",False),
    ("raw_receipt.json","before",False),("raw_receipt.json","after",True),
    ("native_settlement.json","before",True),("native_settlement.json","after",True)])
def test_paid_boundary_crash_never_repeats_a_native_enclosure_dispatch(tmp_path,monkeypatch,stage,artifact,when,recovers):
    scenario = EnclosureScenario(quality=True)
    config,http,flow = start(tmp_path,scenario)
    original = review.audit._write_new; stopped = []
    def write(path,value):
        # prepare intent precedes the outgoing HTTP body; derive that boundary
        # from its exact attempt/stage directory instead of the prior payload.
        directory = path.parent.name
        expected = "correction" if stage == "replacement" else stage
        correct_path = directory in {expected,expected+"_native"} and "attempt_01" in path.as_posix()
        hit = path.name == artifact and correct_path and not stopped
        if hit and when == "before": stopped.append(True); review._fail("operation_cancelled")
        original(path,value)
        if hit and when == "after": stopped.append(True); review._fail("operation_cancelled")
    monkeypatch.setattr(review.audit,"_write_new",write)
    result = flow.run(config)
    assert not result.success and stopped
    bodies = list(http.bodies); count = len(http.requests)
    resumed = flow.run(replace(config,resume=True))
    assert resumed.success is recovers,resumed.error
    assert http.bodies[:len(bodies)] == bodies
    assert len(http.requests) == (6 if recovers else count)


@pytest.mark.parametrize("path", ["eligibility.json","source_literal_certificate.json","source_literal_validation_context.json",
    "candidate_origin.json","attempt_01/correction_baseline.json","attempt_01/source_literal_authority/stage_record.json"])
@pytest.mark.parametrize("when", ["before","after"])
def test_enclosure_settled_derivations_reconstruct_exactly_after_crash(tmp_path,monkeypatch,path,when):
    scenario = EnclosureScenario(quality=True); config,http,flow = start(tmp_path,scenario)
    original = repair._persist; stopped = []
    def persist(file,value,**options):
        hit = file.as_posix().endswith("/semantic_audit/"+path) and not stopped
        if hit and when == "before": stopped.append(True); review._fail("operation_cancelled")
        original(file,value,**options)
        if hit and when == "after": stopped.append(True); flow.cancel()
    monkeypatch.setattr(repair,"_persist",persist)
    result = flow.run(config)
    assert not result.success and stopped
    bodies = list(http.bodies)
    result = flow.run(replace(config,resume=True))
    assert result.success,result.error
    assert len(http.requests) == 6 and http.bodies[:len(bodies)] == bodies


@pytest.mark.parametrize("artifact", ["source_literal_registry.json","eligibility.json","source_literal_certificate.json",
    "source_literal_validation_context.json","candidate_origin.json"])
def test_later_paid_boundary_missing_enclosure_evidence_never_reconstructed(tmp_path,artifact):
    config,http,flow = start(tmp_path,EnclosureScenario(quality=True))
    result = flow.run(config); assert result.success,result.error
    file = result.run_dir/"semantic_audit"/artifact; file.unlink()
    count = len(http.requests)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == count and not file.exists()


@pytest.mark.parametrize("defect", ["unresolved","incomplete","reuse","wrong_reading"])
def test_native_enclosure_certificate_failure_spends_cycle_and_never_buys_replacement(tmp_path,defect):
    scenario = EnclosureScenario()
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body and scenario.payloads[-1]["stage"] == "source_literal_authority":
            value = json.loads(data["output"][0]["content"][0]["text"])
            rows = value["enclosure_observations"]
            if defect == "unresolved": rows[0]["ownership"] = "unresolved"
            elif defect == "incomplete": rows.pop()
            elif defect == "reuse": rows[1]["source_image"] = deepcopy(rows[0]["source_image"])
            else: rows[0]["exact_reading"] += "1"
            data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    result = flow.run(config)
    assert not result.success and len(http.requests) == 4
    eligibility = json.loads((result.run_dir/"semantic_audit/eligibility.json").read_bytes())
    assert eligibility["consumed_cycles"] == 1
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 4 and immutable(result.run_dir) == before


@pytest.mark.parametrize("image_off,conflict", [(False,False),(True,False),(False,True),(True,True)])
def test_native_unavailable_registry_preserves_ordinary_strict_path_and_denies_pure_enclosure(tmp_path,image_off,conflict):
    scenario = EnclosureScenario(); long_value = "https://fictional.example/"+"segment"*80
    def mutate(body,data):
        data = scenario(body,data)
        text = data["output"][0]["content"][0]["text"]
        if "text" not in body: text = text.replace("\n```"," "+token(long_value)+"\n```")
        elif scenario.payloads[-1]["stage"] == "correction":
            value = json.loads(text)
            for row in value["pages"]:
                row["corrected_text"] = CORRECTED+scenario.tail(original=not conflict)+" "+token(long_value)
            text = json.dumps(value,ensure_ascii=False)
        data["output"][0]["content"][0]["text"] = text
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    if image_off: config = replace(config,image_mode=ImageMode.OFF)
    result = flow.run(config)
    assert result.success is (not conflict),result.error
    assert len(http.requests) == (3 if conflict else 4)
    assert not any(p["stage"] == "source_literal_authority" for p in scenario.payloads)
    file = result.run_dir/"semantic_audit/source_literal_registry.json"
    assert json.loads(file.read_bytes())["availability"] == "ineligible_capacity"
    before = immutable(result.run_dir)
    assert flow.run(replace(config,resume=True)).success is (not conflict)
    assert len(http.requests) == (3 if conflict else 4) and immutable(result.run_dir) == before
    file.write_bytes(file.read_bytes()+b" ")
    assert not flow.run(replace(config,resume=True)).success and len(http.requests) == (3 if conflict else 4)


@pytest.mark.parametrize("damage", ["missing","wrong","old_v3","literal_missing","repair_missing"])
def test_saved_fresh_capabilities_require_exact_pair(tmp_path,damage):
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
    config,http,flow = start(tmp_path,EnclosureScenario())
    result = flow.run(config); assert result.success,result.error
    settings = deepcopy(flow._last_state.settings); saved = settings["ordinary_semantic_audit_recipe"]
    if damage == "missing": saved.pop("semantic_enclosure_authority_policy")
    elif damage == "wrong": saved["semantic_enclosure_authority_policy"] = "source_enclosure_authority_v99"
    elif damage == "old_v3": saved["semantic_repair_policy"] = repair.POLICY_V3
    elif damage == "literal_missing": saved.pop("semantic_literal_authority_policy")
    else: saved.pop("semantic_repair_policy")
    with pytest.raises(SemanticAuditRecipeError): ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("outer", [("(",")"),("[","]")])
def test_native_larger_prose_pair_around_certifiable_token_is_hard_stop_before_resolver(tmp_path,outer):
    scenario = EnclosureScenario()
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body and scenario.payloads[-1]["stage"] == "correction":
            value = json.loads(data["output"][0]["content"][0]["text"])
            for row in value["pages"]: row["corrected_text"] = outer[0]+row["corrected_text"]+outer[1]
            data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    result = flow.run(config)
    assert not result.success and ("nested_or_larger_enclosure" in result.error or "ineligible_strict_failure" in result.error)
    assert len(http.requests) == 3 and not any(p["stage"] == "source_literal_authority" for p in scenario.payloads)
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 3 and immutable(result.run_dir) == before


def test_native_ambiguous_existing_pair_migration_stops_after_resolver_before_replacement(tmp_path):
    scenario = EnclosureScenario()
    def tail(index): return " المرجع "+" ثم ".join(("["+token(VALUE)+"]") if i == index else token(VALUE) for i in range(5))
    def mutate(body,data):
        data = scenario(body,data)
        if "text" not in body:
            data["output"][0]["content"][0]["text"] = "```\n"+PRIMARY+tail(2)+"\n```"
        else:
            payload = scenario.payloads[-1]; value = json.loads(data["output"][0]["content"][0]["text"])
            if payload["stage"] == "correction":
                value["pages"][0]["corrected_text"] = CORRECTED+tail(3)
            elif payload["stage"] == "source_literal_authority":
                assert len(value["enclosure_observations"]) == 5
                for i,row in enumerate(value["enclosure_observations"]): row["enclosure"] = "square" if i == 2 else "none"
            data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    result = flow.run(config)
    assert not result.success and "ambiguous_neighborhood" in result.error and len(http.requests) == 4
    assert [p["stage"] for p in scenario.payloads] == ["source_inventory","correction","source_literal_authority"]
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 4 and immutable(result.run_dir) == before


def test_native_unambiguous_migration_source_proof_single_replacement_no_change_keeps_original(tmp_path):
    scenario = EnclosureScenario()
    original_tail = scenario.tail()
    moved_tail = scenario.tail(original=True)
    index = moved_tail.rfind(token(VALUE))
    moved_tail = moved_tail[:index]+"["+token(VALUE)+"]"+moved_tail[index+len(token(VALUE)):]
    def mutate(body,data):
        data = scenario(body,data)
        if "text" not in body:
            data["output"][0]["content"][0]["text"] = "```\n"+PRIMARY+original_tail+"\n```"
        elif scenario.payloads[-1]["stage"] == "correction":
            value = json.loads(data["output"][0]["content"][0]["text"])
            row = value["pages"][0]
            if "source_literal_certificate" in scenario.payloads[-1]: row.update(status="no_change",corrected_text="",reason_codes=[])
            else: row["corrected_text"] = CORRECTED+moved_tail
            data["output"][0]["content"][0]["text"] = json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow = start(tmp_path,scenario); http.mutate = mutate
    result = flow.run(config)
    assert result.success,result.error
    assert len(http.requests) == 6
    assert (result.run_dir/"semantic_audit/page_0001.txt").read_bytes().decode() == PRIMARY+original_tail
    manifest = json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
    assert manifest["consumed_cycles"] == 1
    before = immutable(result.run_dir)
    assert flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 6 and immutable(result.run_dir) == before
