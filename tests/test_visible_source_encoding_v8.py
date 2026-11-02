"""Versioned visible-source guidance; unchanged strict validators and history."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_target_ambiguity as ambiguity
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from tests.test_ordinary_semantic_review import pack, recipe, PDF
from tests.semantic_review_fakes import review_response
from tests.test_workflow_semantic_audit_integration import offline

V8 = "source_commitment_visual_v8"
KEY = "semantic_source_review_policy"
OPTIONS = {"semantic_unit_reference_policy": refs.POLICY,
    "source_inventory_max_output_tokens": 64000,
    "semantic_page_coverage_policy": "complete_selected_pages_v1"}


def prepared(selected=V8, *, off=False):
    pages=pack(count=1,off=off)
    settings=replace(recipe(),model="gpt-6-astra",configured_image_mode="off" if off else "auto")
    units=review.source_units(pages);options={**OPTIONS,KEY:selected}
    request=repair._request("source_inventory",pages,settings,PDF,units,options)
    raw=json.dumps(review_response(json.loads(request["prompt_text"]),unit_references=True))
    canonical,_=refs.hydrate(raw,"source_inventory",request,units)
    inventory=review.validate_source_inventory(review.audit._json(canonical),pages,units)
    candidate={p.page_number:p.primary_text for p in pages}
    requests={"source_inventory":request}
    for stage in ("correction","verification"):
        requests[stage]=repair._request(stage,pages,settings,PDF,units,options,
            inventory=inventory,**({"candidate":candidate} if stage=="verification" else {}))
    return pages,settings,units,inventory,candidate,requests


def test_exact_V8_additions_preserve_V7_inventory_and_every_historical_default():
    before,after=policy._suffixes(policy.POLICY_V7),policy._suffixes(V8)
    assert policy.POLICY_V8==V8
    assert after["source_inventory"]==before["source_inventory"]
    assert after["correction"]==before["correction"]+policy.V8_CORRECTION_ADDITION
    assert after["verification"]==before["verification"]+policy.V8_VERIFICATION_ADDITION
    assert hashlib.sha256(policy.V8_CORRECTION_ADDITION.encode()).hexdigest()=="9466b1f46b44e843eb45a029e9b906fe95c37847beb4e82243b56805c019410c"
    assert hashlib.sha256(policy.V8_VERIFICATION_ADDITION.encode()).hexdigest()=="7901a8599821022be7da245edfb217e614d06d27f7549232de3f33dab73568ca"
    assert policy.descriptor()==policy.descriptor(policy.POLICY)


@pytest.mark.parametrize("off",[False,True])
def test_exact_request_delta_is_instructions_and_bound_descriptor_not_source_schema_or_images(off):
    old,new=prepared(policy.POLICY_V7,off=off),prepared(V8,off=off)
    assert old[:5]==new[:5]
    for stage in review.STAGES:
        a,b=deepcopy(old[-1][stage]),deepcopy(new[-1][stage])
        assert a!=b
        ap,bp=json.loads(a.pop("prompt_text")),json.loads(b.pop("prompt_text"))
        assert ap.pop(KEY)==policy.descriptor(policy.POLICY_V7)
        assert bp.pop(KEY)==policy.descriptor(V8)
        assert ap==bp
        ai,bi=a.pop("instructions"),b.pop("instructions")
        assert bi==ai+(policy.V8_CORRECTION_ADDITION if stage=="correction"
            else policy.V8_VERIFICATION_ADDITION if stage=="verification" else "")
        assert a==b


@pytest.mark.parametrize("selected",[policy.POLICY_V7,V8])
def test_initial_ambiguity_binds_trusted_concrete_source_profile_and_keeps_old_default(selected):
    pages,_,units,inventory,candidate,requests=prepared(selected)
    request=ambiguity.adapt_request(requests["verification"],semantic_source_review_policy=selected)
    ambiguity.check_request(request,pages,units,inventory,candidate,semantic_source_review_policy=selected)
    assert json.loads(request["prompt_text"])[KEY]==policy.descriptor(selected)
    if selected==policy.POLICY_V7:
        assert request==ambiguity.adapt_request(requests["verification"])
        ambiguity.check_request(request,pages,units,inventory,candidate)
    else:
        with pytest.raises(review.SemanticAuditError,match="target_ambiguity_profile"):
            ambiguity.check_request(request,pages,units,inventory,candidate)


@pytest.mark.parametrize("fault",["trusted_profile","descriptor","instructions","schema","units","images","unknown"])
def test_V8_profile_mismatch_never_becomes_a_permissive_payload_declared_upgrade(fault):
    pages,_,units,inventory,candidate,requests=prepared()
    original=requests["verification"]
    if fault in {"trusted_profile","unknown"}:
        with pytest.raises(review.SemanticAuditError,match="target_ambiguity_profile"):
            ambiguity.adapt_request(original,semantic_source_review_policy=policy.POLICY_V7 if fault=="trusted_profile" else "unregistered")
        return
    request=ambiguity.adapt_request(original,semantic_source_review_policy=V8)
    payload=json.loads(request["prompt_text"])
    if fault=="descriptor":payload[KEY]=policy.descriptor(policy.POLICY_V7)
    elif fault=="instructions":request["instructions"]=request["instructions"].replace(policy.V8_VERIFICATION_ADDITION,"")
    elif fault=="schema":request["response_format"]["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"].remove(ambiguity.STATUS)
    elif fault=="units":payload["target_units"][0]["text"]+="changed"
    else:request["image_data_urls"]=()
    request["prompt_text"]=review._prompt_json(payload)
    with pytest.raises(review.SemanticAuditError,match="target_ambiguity_profile"):
        ambiguity.check_request(request,pages,units,inventory,candidate,semantic_source_review_policy=V8)


def test_V8_adapter_rejects_wrong_base_instructions_before_any_provider():
    *_,requests=prepared()
    request=deepcopy(requests["verification"]);request["instructions"]+="tampered"
    with pytest.raises(review.SemanticAuditError,match="target_ambiguity_profile"):
        ambiguity.adapt_request(request,semantic_source_review_policy=V8)


@pytest.mark.parametrize("selected",[policy.POLICY_V7,V8])
@pytest.mark.parametrize("controller",[repair.POLICY,repair.POLICY_V2,repair.POLICY_V3,repair.POLICY_V4])
def test_closed_existing_repair_pair_and_initial_profile_dependencies_precede_client(tmp_path,monkeypatch,selected,controller):
    class Prepared(Exception):pass
    monkeypatch.setattr(review,"_prepare",lambda *a,**k:(_ for _ in ()).throw(Prepared()))
    kwargs={"semantic_repair_policy":controller,"semantic_target_ambiguity_policy":ambiguity.POLICY,
        "stage_guard":lambda **_:pytest.fail("Prepared native dispatch")}
    if controller in {repair.POLICY_V3,repair.POLICY_V4}:kwargs["semantic_literal_authority_policy"]="source_literal_authority_v1"
    if controller==repair.POLICY_V4:kwargs["semantic_enclosure_authority_policy"]="source_enclosure_authority_v1"
    with pytest.raises(Prepared if controller==repair.POLICY_V4 else review.SemanticAuditError):
        repair.run_semantic_repair(pages=pack(count=1,off=True),recipe=replace(recipe(),model="gpt-6-astra",configured_image_mode="off"),
            pdf_sha256=PDF,evidence_dir=tmp_path/"audit",**OPTIONS,**{KEY:selected},**kwargs)
    assert not (tmp_path/"audit").exists()


def test_instructions_never_mechanically_strip_printed_symbols_or_relax_owned_literals():
    from legalpdf_translate.workflow_components.evaluation import evaluate_output
    from legalpdf_translate.types import TargetLang
    from tests.test_primary_literal_markup import token,case
    from legalpdf_translate import primary_literal_markup as markup
    value="CODE42/7";body="النص العربي محفوظ.\n%*"+token(value)+"*"
    source="Código %*[["+value+"]]*"
    evaluation=evaluate_output("```\n"+body+"\n```",TargetLang.AR,expected_ar_tokens=[value],
        ar_source_text=source,primary_normalized_text=body)
    assert evaluation.ok and "%*"+token(value)+"*" in evaluation.normalized_text
    bad=evaluate_output("```\n"+body.replace(value,value+"X")+"\n```",TargetLang.AR,
        expected_ar_tokens=[value],ar_source_text=source,primary_normalized_text=body)
    assert not bad.ok
    raw,original,required,options=case()
    _,result,groups=markup.evaluate_initial(raw,original,required,1,options)
    right=groups[0]["right"]
    with pytest.raises(markup.PrimaryMarkupError):
        markup.guard_group(result.normalized_text.replace("["+token(right)+"]",token(right),1),result.normalized_text,groups)


class MarkerScenario:
    def __init__(self,outcome="equivalent"):
        self.outcome,self.verifiers,self.payloads=outcome,0,[]

    def __call__(self,body,data):
        from tests.test_primary_literal_markup import token
        from tests.test_workflow_semantic_audit_integration import PRIMARY
        value="BAR42/7";baseline=PRIMARY+"\n%*"+token(value)+"*"
        if "text" not in body:
            data["output"][0]["content"][0]["text"]="```\n"+baseline+"\n```"
            return data
        payload=json.loads(body["input"][0]["content"][0]["text"]);self.payloads.append(deepcopy(payload))
        reply=json.loads(data["output"][0]["content"][0]["text"])
        if payload["stage"]=="correction":
            for row in reply["pages"]:
                if "prior_findings" in payload:
                    row.update(status="corrected",corrected_text=PRIMARY+"\n"+token(value),reason_codes=["visual_artifact"])
                else:row.update(status="no_change",corrected_text="",reason_codes=[])
        elif payload["stage"]=="verification":
            self.verifiers+=1
            if self.verifiers==1:reply["claim_results"][0]["status"]="unresolved" if self.outcome=="initial_unresolved" else "contradiction"
            elif self.outcome!="equivalent":reply["claim_results"][0]["status"]="unresolved"
        data["output"][0]["content"][0]["text"]=json.dumps(reply,ensure_ascii=False)
        return data


def marker_workflow(tmp_path,outcome="equivalent"):
    import fitz
    from legalpdf_translate.types import ImageMode
    from tests.test_semantic_review_model_integration import setup
    scenario=MarkerScenario(outcome)
    config,http,flow=setup(tmp_path,mutate=scenario)
    with fitz.open(config.pdf_path) as pdf:
        pdf[0].insert_text((50,300),"Codigo BAR42/7")
        pdf.saveIncr()
    return replace(config,image_mode=ImageMode.ALWAYS),http,flow,scenario


@pytest.mark.parametrize("outcome",["equivalent","unresolved","initial_unresolved"])
def test_fresh_V8_mocked_one_cycle_remains_blind_strict_and_zero_send_on_local_replay(tmp_path,outcome,record_property,monkeypatch):
    from legalpdf_translate import workflow_semantic_audit as glue
    fresh=glue.fresh_recipe
    def historical(*args,**kwargs):
        saved=fresh(*args,**kwargs)
        saved[KEY]=V8  # This saved instruction/replay oracle owns concrete V8.
        saved.pop("primary_page_evidence_policy", None)
        return saved
    monkeypatch.setattr(glue,'fresh_recipe',historical)
    from legalpdf_translate.workflow import TranslationWorkflow
    config,http,flow,scenario=marker_workflow(tmp_path,outcome)
    result=flow.run(config)
    assert result.success is (outcome=="equivalent"),result.error
    calls=4 if outcome=="initial_unresolved" else 6
    assert len(http.requests)==calls
    saved=flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved[KEY]==V8
    assert all(p[KEY]==policy.descriptor(V8) for p in scenario.payloads)
    record_property("visible_encoding_V8_specimen",json.dumps({"run_dir":str(result.run_dir),
        "source_pdf":str(config.pdf_path),"requests":http.requests,"outcome":outcome},ensure_ascii=False))
    if result.success:
        manifest=json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
        assert manifest["consumed_cycles"]==manifest["selected_attempt"]==1
        assert manifest["repair_trigger"]=="independent_verification"
        assert "%*" not in (result.run_dir/"semantic_audit/page_0001.txt").read_text(encoding="utf8")
        final=[r for r in http.requests if "text" in r and json.loads(r["input"][0]["content"][0]["text"])["stage"]=="verification"][-1]
        payload=json.loads(final["input"][0]["content"][0]["text"])
        assert not set(payload)&{ambiguity.KEY,"prior_findings","primary_pages","context_text"}
        assert final["instructions"].endswith(policy.V8_VERIFICATION_ADDITION)
        assert ambiguity.STATUS not in final["text"]["format"]["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"]
    else:assert not (result.run_dir/"semantic_audit/manifest.json").exists()
    before={p:p.read_bytes() for folder in ("primary_markup","semantic_source","semantic_audit","accounting")
        for p in (result.run_dir/folder).rglob("*") if p.is_file() and p.suffix!=".lock"}
    assert flow.run(replace(config,resume=True)).success is result.success
    assert TranslationWorkflow(client=http.client,gui_settings={}).run(replace(config,resume=True)).success is result.success
    if result.success:assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests)==calls and all(p.read_bytes()==raw for p,raw in before.items())
