"""Saved V3 adds one source-qualified raw locative; historical contracts stay closed."""
from dataclasses import asdict, replace
import json

import pytest

from legalpdf_translate import ar_source_fields as fields
from legalpdf_translate import ordinary_semantic_audit as audit
from legalpdf_translate import workflow_semantic_audit as integration
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from tests import test_source_locative_house_join as old
from tests.test_workflow_semantic_audit_integration import offline

V3 = "source_locative_house_join_v3"
KEY = "source_inline_address_join_policy"


def canonical(text=None, source=old.SOURCE, required=None, version=V3):
    return fields.canonicalize_source_address_literals(old.target("، في رقم ") if text is None else text,
        source, ["27"] if required is None else required, **({KEY:version} if version is not None else {}))


def test_new_permission_owns_complete_source_relation_and_changes_no_raw_byte():
    text=old.target("، في رقم ")
    assert fields.SOURCE_INLINE_ADDRESS_JOIN_POLICY_V3==V3
    assert canonical(text)==(text,["27"],0,None)
    assert old.target("، عند رقم ")==canonical(old.target("، عند رقم "))[0]


@pytest.mark.parametrize("version",[None,old.POLICY,old.V2])
def test_historical_versions_still_refuse_fi_raqm(version):
    assert canonical(version=version)[3]=="source_address_coverage_mismatch"


def test_full_primary_and_identical_compliance_evaluator_keep_ordinary_normalization():
    text=old.target("، في رقم ");raw="```\n"+text+"\n```"
    options=dict(expected_ar_tokens=["27"],ar_source_text=old.SOURCE,**{KEY:V3})
    primary=evaluate_output(raw,TargetLang.AR,**options)
    assert primary.ok and primary.normalized_text==text
    final=evaluate_output(raw,TargetLang.AR,primary_normalized_text=primary.normalized_text,**options)
    assert final.ok and final.normalized_text==text


@pytest.mark.parametrize("gap",[" في رقم ",", في رقم ","، في رقم ","\tفي\tرقم\t","،\tفي رقم "])
def test_finite_new_raw_gaps_need_same_complete_component_proof(gap):
    text=old.target(gap)
    assert canonical(text)==(text,["27"],0,None)


@pytest.mark.parametrize("gap",[" في بالرقم "," وليس رقم "," و في رقم "," في رقم\n","، في\rرقم ",
    "، في\u2066 رقم ","، في رقم \u2069","، في رقم \u200e","، في\u200f رقم "," في\u00a0رقم "," فِي رقم "])
def test_new_raw_gap_never_accepts_other_words_normalized_controls_or_space(gap):
    assert canonical(old.target(gap))[3] is not None


@pytest.mark.parametrize("source,required",[
    (old.SOURCE.replace("no nº","nº"),["27"]),
    (old.SOURCE.replace("no nº","[[no]] nº"),["no","27"]),
    (old.SOURCE.replace("nº","[[nº]]"),["nº","27"]),
    (old.SOURCE.replace("no nº","no\u2066\u2069 nº"),["27"]),
    (old.SOURCE.replace("[[27]].","[[27]], em Vale Claro."),["27"]),
])
def test_source_qualification_cannot_be_invented_or_change_locality(source,required):
    assert canonical(source=source,required=required)[3] is not None


@pytest.mark.parametrize("source",[old.SOURCE.replace("no nº","em nº"),old.SOURCE.replace("no nº","")])
def test_unrecognized_source_field_keeps_historical_noop_instead_of_new_authority(source):
    assert canonical(source=source)==canonical(source=source,version=old.V2)


@pytest.mark.parametrize("damage",["house","street","duplicate_house","duplicate_street","unwrapped_street","split_street",
    "whole_prose_owner","decimal","compound","prefix","other_house_first"])
def test_source_owners_next_carrier_and_multiplicity_still_refuse(damage):
    text=old.target("، في رقم ")
    if damage=="house":text=old.target("، في رقم ",number="28")
    elif damage=="street":text=old.target("، في رقم ",street="Rua do Freixo")
    elif damage=="duplicate_house":text+=" "+old.token("27")
    elif damage=="duplicate_street":text+=" "+old.token(old.STREET)
    elif damage=="unwrapped_street":text=text.replace(old.token(old.STREET),old.STREET)
    elif damage=="split_street":text=text.replace(old.token(old.STREET),old.token("Rua do")+" "+old.token("Cedro"))
    elif damage=="whole_prose_owner":text=old.token("يقيم في "+old.STREET+"، في رقم 27")
    elif damage=="decimal":text=text.replace(old.token("27"),old.token("27")+".5")
    elif damage=="compound":text=text.replace(old.token("27"),old.token("27")+"-A")
    elif damage=="prefix":text=text.replace(old.token("27"),"1"+old.token("27"))
    else:text=text.replace(old.token("27"),old.token("28")+" "+old.token("27"))
    assert canonical(text)[3] is not None


def test_multiple_fields_require_source_order_and_exact_association_even_equal_house_values():
    source=old.SOURCE+"\n"+old.SOURCE.replace(old.STREET,"Rua do Freixo")
    first=old.target("، في رقم ");second=old.target("، في رقم ",street="Rua do Freixo")
    text=first+"\n"+second
    assert canonical(text,source,["27","27"])==(text,["27","27"],0,None)
    assert canonical(second+"\n"+first,source,["27","27"])[3]=="source_address_association_mismatch"


@pytest.mark.parametrize("packing",[lambda:old.token(old.ALT),lambda:old.token(old.STREET)+", "+old.token("nº")+" "+old.token("27"),
    lambda:old.token("Rua do")+" "+old.token("Cedro")+", "+old.token("nº 27")])
def test_complete_V2_alternative_is_inherited_exactly_including_wrapper_normalization(packing):
    text="يقيم في "+packing()+"."
    assert canonical(text)==old.v2_canonical(text)


def test_V2_alternative_competition_and_source_target_bounds_are_inherited():
    text=old.token("Rua do Cedro, no nº 27")+" و "+old.token(old.ALT)
    assert canonical(text)[3]==old.v2_canonical(text)[3]=="source_address_association_mismatch"
    assert canonical(source="x"*120001)[3]==canonical(source="x"*120001,version=old.V2)[3]


def test_local_recipe_binding_changes_but_identical_input_provider_request_and_final_guard_do_not():
    page=replace(old.page(),primary_text=old.target("، في رقم "))
    before=replace(old.recipe(),**{KEY:old.V2});after=replace(before,**{KEY:V3})
    assert audit.build_semantic_audit_request([page],before,"a"*64)==audit.build_semantic_audit_request([page],after,"a"*64)
    request=audit.build_semantic_audit_request([page],before,"a"*64)
    assert audit._binding([page],before,"a"*64,request)["recipe_sha256"]!=audit._binding([page],after,"a"*64,request)["recipe_sha256"]
    raw=audit._json({"version":audit.AUDIT_VERSION,"pages":[{"page_number":1,"status":"corrected","corrected_text":page.primary_text,"reason_codes":["material_meaning"]}]})
    with pytest.raises(audit.SemanticAuditError):audit.validate_semantic_audit_response(raw,[page],**audit._validation_options(before))
    assert audit.validate_semantic_audit_response(raw,[page],**audit._validation_options(after))[0][1]==page.primary_text
    from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals
    assert not correction_preserves_additional_literals(page.primary_text+" "+old.token("RETAIN42/7"),page.primary_text,["27"],old.SOURCE,**{KEY:V3})


def test_valid_new_join_cannot_remove_an_owned_converted_enclosure():
    from legalpdf_translate import primary_literal_markup as markup
    from tests.test_primary_literal_markup import case,token,RIGHT
    raw,source,required,recipe=case();recipe[KEY]=V3
    raw=raw.replace("\n```","\n"+old.target("، في رقم ")+"\n```")
    source+="\n"+old.SOURCE;required.append("27")
    initial,result,groups=markup.evaluate_initial(raw,source,required,1,recipe)
    assert result.ok and len(groups)==1
    damaged="```\n"+result.normalized_text.replace("["+token(RIGHT)+"]",token(RIGHT),1)+"\n```"
    with pytest.raises(markup.PrimaryMarkupError):markup.evaluate_compliance(damaged,result,initial,groups,source,required,recipe)


class Scenario:
    def __init__(self,retry):self.retry,self.primaries,self.verifiers,self.payloads=retry,0,0,[]
    def __call__(self,body,data):
        from tests.test_workflow_semantic_audit_integration import PRIMARY,CORRECTED
        if "text" not in body:
            self.primaries+=1
            value="not fenced" if self.retry and self.primaries==1 else "```\n"+old.target("، في رقم ",number="4273")+"\n"+PRIMARY+"\n```"
            data["output"][0]["content"][0]["text"]=value
            return data
        payload=json.loads(body["input"][0]["content"][0]["text"]);self.payloads.append(payload)
        reply=json.loads(data["output"][0]["content"][0]["text"])
        if payload["stage"]=="correction":
            for row in reply["pages"]:
                if "prior_findings" in payload:row.update(status="corrected",corrected_text=old.target("، في رقم ",number="4273")+"\n"+CORRECTED,reason_codes=["material_meaning"])
                else:row.update(status="no_change",corrected_text="",reason_codes=[])
        elif payload["stage"]=="verification":
            self.verifiers+=1
            if self.verifiers==1:reply["claim_results"][0]["status"]="missing"
        data["output"][0]["content"][0]["text"]=json.dumps(reply,ensure_ascii=False)
        return data


@pytest.mark.parametrize("retry",[False,True],ids=["initial_selected","compliance_selected"])
def test_current_fresh_workflow_binds_V3_one_cycle_pruned_same_new_manager_and_no_send(tmp_path,record_property,monkeypatch,retry):
    import fitz
    from legalpdf_translate import primary_literal_markup as markup
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_semantic_review_model_integration import setup
    from legalpdf_translate import ordinary_semantic_repair as repair
    recipes=[];original=repair.run_semantic_repair
    def observe(**kwargs):
        recipes.append(kwargs["recipe"])
        return original(**kwargs)
    monkeypatch.setattr(repair,"run_semantic_repair",observe)
    scenario=Scenario(retry);config,http,flow=setup(tmp_path,mutate=scenario)
    with fitz.open(config.pdf_path) as pdf:
        # The ordinary tokenizer protects this four-digit house without a fake source override.
        pdf[0].insert_text((50,300),old.SOURCE.replace("27","4273").replace("[[","").replace("]]","").removesuffix("."));pdf.saveIncr()
    result=flow.run(config)
    assert result.success,result.error
    count=7 if retry else 6
    assert len(http.requests)==count
    saved=flow._last_state.settings["ordinary_semantic_audit_recipe"];assert saved[KEY]==V3
    context=markup.load_context(state=flow._last_state,run_dir=result.run_dir)
    assert not context.groups[1]
    source=json.loads((result.run_dir/"semantic_source/page_0001.json").read_bytes())
    assert "4273" in source["expected_ar_tokens"]
    primary_text=(result.run_dir/"pages/page_0001.txt").read_text(encoding="utf8")
    historical=evaluate_output("```\n"+primary_text+"\n```",TargetLang.AR,
        expected_ar_tokens=source["expected_ar_tokens"],ar_source_text=source["source_text"],
        source_field_policy=saved["source_field_policy"],literal_wrapper_policy=saved["primary_literal_packaging_version"],**{KEY:old.V2})
    assert not historical.ok and historical.ar_token_details["source_address_violation"]=="source_address_coverage_mismatch"
    manifest=json.loads((result.run_dir/"semantic_audit/manifest.json").read_bytes())
    assert manifest["consumed_cycles"]==manifest["selected_attempt"]==1
    engine_recipe=recipes[0]
    assert engine_recipe.source_inline_address_join_policy==V3
    assert manifest["binding"]["recipe_sha256"]==audit._binding([old.page()],engine_recipe,"a"*64,{})["recipe_sha256"]
    assert manifest["binding"]["recipe_sha256"]!=audit._binding([old.page()],replace(engine_recipe,**{KEY:old.V2}),"a"*64,{})["recipe_sha256"]
    final=scenario.payloads[-1];assert final["stage"]=="verification" and not set(final)&{"prior_findings","primary_pages","primary_literal_markup_policy"}
    record_property("locative_V3_specimen",json.dumps({"run_dir":str(result.run_dir),"source_pdf":str(config.pdf_path),"requests":http.requests,"retry":retry},ensure_ascii=False))
    before={p:p.read_bytes() for folder in ("primary_markup","semantic_source","semantic_audit","accounting") for p in (result.run_dir/folder).rglob("*") if p.is_file() and p.suffix!=".lock"}
    (result.run_dir/"pages/page_0001.txt").unlink()
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(client=http.client,gui_settings={}).run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests)==count and all(p.read_bytes()==raw for p,raw in before.items())
    assert not (result.run_dir/"pages/page_0001.txt").exists()
