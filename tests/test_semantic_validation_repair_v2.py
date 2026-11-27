"""Prospective strict local-quality repair; fictional native SDK, no provider."""
from copy import deepcopy
from dataclasses import replace
import json

import fitz
import pytest

from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_ordinary_semantic_audit import page, token
from tests.test_semantic_review_model_integration import setup, immutable
from tests.test_workflow_semantic_audit_integration import offline, CORRECTED, PRIMARY


def canonical(pages, texts):
    return {"version": review.CORRECTION_VERSION, "pages": [
        {"page_number": p.page_number, "status": "corrected", "corrected_text": text,
         "reason_codes": ["material_meaning"]} for p, text in zip(pages, texts)],
        "claim_coverage": [{"claim_id": "fictional", "status": "preserved"}]}


INVENTORY = {"claims": [{"claim_id": "fictional"}]}
RECIPE = review.SemanticAuditRecipe("gpt-6-astra", "high")


@pytest.fixture(autouse=True)
def saved_v2_repair_policy(monkeypatch):
    """Keep the genuine historical v2 suite on its exact saved semantics."""
    fresh = glue.fresh_recipe
    def v2(*args, **kwargs):
        saved = fresh(*args, **kwargs)
        saved["semantic_repair_policy"] = repair.POLICY_V2
        saved["semantic_source_review_policy"] = "source_commitment_visual_v5"
        saved.pop("semantic_literal_authority_policy", None)
        saved.pop("semantic_enclosure_authority_policy", None)
        saved.pop("source_enclosure_identity_policy", None)
        saved.pop("semantic_target_ambiguity_policy", None)
        saved.pop("semantic_enclosure_sequence_repair_policy", None)
        saved.pop("primary_page_evidence_policy", None)
        saved.pop("primary_literal_markup_policy", None)
        return saved
    monkeypatch.setattr(glue, "fresh_recipe", v2)


def diagnose(pages, data, recipe=RECIPE):
    return repair.correction_validation_diagnostic(review.audit._json(data), pages, INVENTORY, recipe)


def numbered(number=1):
    return page(number, source_text="A fictional office issued notice 17.",
        original_source_text="A fictional office issued notice 17.", expected_ar_tokens=("17",),
        primary_text="أصدر المكتب إشعارا " + token("17") + ".")


def test_classifier_records_repeated_number_and_new_bracket_without_weakening_strict_validator():
    pages = [numbered()]
    data = canonical(pages, [pages[0].primary_text + " (17)"])
    with pytest.raises(review.SemanticAuditError, match="new_actionable_quality_failure"):
        review.validate_source_correction(review.audit._json(data), pages, INVENTORY, RECIPE)
    rejected = diagnose(pages, data)
    diagnostic = rejected["correction_validation_diagnostic"]["pages"][0]
    assert diagnostic["regressed_fields"] == ["numeric_mismatches_count"]
    assert diagnostic["new_extra_anchors"]["brackets"]
    assert rejected["rejected_proposal"]["untrusted"]
    assert rejected["rejected_proposal"]["pages"][0]["text"].endswith("(" + token("17") + ")")


def test_equal_counts_cannot_hide_changed_bracket_identity_and_supported_repetitions_stay():
    original = page(source_text="17 and (23).", expected_ar_tokens=("17", "23"),
        primary_text="القيمة " + token("17") + " و(" + token("23") + ").")
    diagnostic = diagnose([original], canonical([original], ["القيمة (" + token("17") + ") و" + token("23") + "."]))
    row = diagnostic["correction_validation_diagnostic"]["pages"][0]
    assert not row["regressed_fields"]
    assert row["new_missing_anchors"]["brackets"] and row["new_extra_anchors"]["brackets"]
    repeated = page(source_text="17 then 17.", expected_ar_tokens=("17", "17"),
        primary_text="القيمة " + token("17") + " ثم " + token("17") + ".")
    assert diagnose([repeated], canonical([repeated], [repeated.primary_text])) is None
    with pytest.raises(review.SemanticAuditError):
        diagnose([repeated], canonical([repeated], ["القيمة " + token("17") + "."]))


@pytest.mark.parametrize("defect", ["missing_page", "reordered", "duplicate_page", "unknown_field",
    "unresolved", "wrong_claim", "missing_claim", "literal_loss", "added_primary_literal_loss", "language"])
def test_early_quality_failure_never_hides_later_shape_coverage_or_evaluator_failure(defect):
    pages = [numbered(), numbered(2)]
    data = canonical(pages, [pages[0].primary_text + " (17)", pages[1].primary_text])
    if defect == "missing_page": data["pages"].pop()
    elif defect == "reordered": data["pages"].reverse()
    elif defect == "duplicate_page": data["pages"][1]["page_number"] = 1
    elif defect == "unknown_field": data["pages"][1]["extra"] = True
    elif defect == "unresolved": data["pages"][1]["status"] = "unresolved"
    elif defect == "wrong_claim": data["claim_coverage"][0]["claim_id"] = "unknown"
    elif defect == "missing_claim": data["claim_coverage"] = []
    elif defect == "literal_loss":
        pages[1] = replace(pages[1], expected_ar_tokens=("Required",),
            source_text="Required", primary_text="نص " + token("Required"))
    elif defect == "added_primary_literal_loss":
        pages[1] = replace(pages[1], primary_text=pages[1].primary_text + " " + token("Extra"))
    else: data["pages"][1]["corrected_text"] = "O documento apresenta todos os factos do processo."
    with pytest.raises(review.SemanticAuditError) as caught:
        diagnose(pages, data)
    assert caught.value.code != "new_actionable_quality_failure"


class ValidationScenario:
    def __init__(self, *, fail_verifier=False, replacement=None, joint=False):
        self.payloads = []
        self.fail_verifier, self.replacement, self.joint = fail_verifier, replacement, joint
    def __call__(self, body, data):
        if "text" not in body: return data
        payload = json.loads(body["input"][0]["content"][0]["text"])
        self.payloads.append(deepcopy(payload))
        value = json.loads(data["output"][0]["content"][0]["text"])
        if payload["stage"] == "correction":
            for row in value["pages"]:
                row.update(status="corrected", reason_codes=["material_meaning"])
                row["corrected_text"] = (self.replacement or CORRECTED) if "rejected_proposal" in payload else CORRECTED + " (12345)"
        elif payload["stage"] == "verification" and self.fail_verifier:
            value["claim_results"][0]["status"] = "missing"
            if self.joint:
                value["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": "Fictional finding."}]
        data["output"][0]["content"][0]["text"] = json.dumps(value, ensure_ascii=False)
        return data


def read(directory, path):
    return json.loads((directory/path).read_bytes())


def test_fresh_native_replacement_original_baseline_blind_verifier_accounting_and_zero_call_replay(tmp_path, monkeypatch):
    scenario = ValidationScenario()
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert result.success, result.error
    assert len(http.requests) == 5
    assert [p["stage"] for p in scenario.payloads] == ["source_inventory", "correction", "correction", "verification"]
    assert flow._last_state.settings["ordinary_semantic_audit_recipe"]["semantic_repair_policy"] == repair.POLICY_V2
    first, replacement, verifier = scenario.payloads[1:]
    assert replacement["primary_pages"] == first["primary_pages"]
    assert replacement["primary_pages"][0]["text"] == PRIMARY
    assert replacement["source_inventory"] == first["source_inventory"]
    assert replacement["rejected_proposal"]["untrusted"] is True
    assert replacement["rejected_proposal"]["pages"][0]["text"] == CORRECTED + " (" + token("12345") + ")"
    assert not set(verifier) & {"rejected_proposal", "correction_validation_diagnostic", "prior_findings", "primary_pages", "context_text"}
    assert verifier["candidate_pages"][0]["text"] == CORRECTED
    directory = result.run_dir/"semantic_audit"
    manifest = read(directory, "manifest.json")
    assert manifest["selected_attempt"] == 1 and manifest["consumed_cycles"] == 1
    assert manifest["repair_trigger"] == "correction_validation"
    assert manifest["semantic_repair_policy"]["policy"] == repair.POLICY_V2
    assert [r["stage_id"] for r in manifest["stages"]] == ["attempt_00/source_inventory", "attempt_00/correction", "attempt_01/correction", "attempt_01/verification"]
    rejected = manifest["stages"][1]
    assert rejected["outcome"] == "rejected_quality" and rejected["diagnostic_sha256"] and rejected["rejected_proposal_sha256"]
    eligibility = read(directory, "eligibility.json")
    assert eligibility["trigger"] == "correction_validation" and eligibility["consumed_cycles"] == 1
    baseline = read(directory, "attempt_01/correction_baseline.json")
    assert baseline["working_candidate"] == baseline["original_primary"]
    assert baseline["rejected_proposal_untrusted"]
    assert not (directory/"attempt_00/pair.json").exists()
    assert not (directory/"attempt_00/verification").exists()
    proofs = [read(directory, r["native_settlement_path"]) for r in manifest["stages"]]
    calls = [call for proof in proofs for call in proof["call_ids"]]
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    native = [row["call_id"] for row in journal["events"] if row["event"]=="begin" and row["purpose"]=="semantic_audit"]
    assert len(calls) == len(set(calls)) == 4 and set(calls) == set(native)
    assert manifest["usage"]["input_tokens"] == 400 and manifest["usage"]["total_tokens"] == 640
    before = immutable(result.run_dir)
    requests = deepcopy(http.requests)
    monkeypatch.setattr(glue, "fresh_recipe", lambda *a, **k: pytest.fail("saved replay consulted fresh policy"))
    assert flow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert http.requests == requests and immutable(result.run_dir) == before


@pytest.mark.parametrize("joint", [False, True])
def test_validation_repair_consumes_global_cycle_even_if_verifier_finding_is_repairable(tmp_path, joint):
    scenario = ValidationScenario(fail_verifier=True, joint=joint)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert not result.success and "repair_exhausted" in result.error
    assert len(http.requests) == 5
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 5 and immutable(result.run_dir) == before
    assert not (result.run_dir/"semantic_audit/attempt_01/source_inventory").exists()


@pytest.mark.parametrize("replacement", [CORRECTED+" (12345)", CORRECTED+" (12345)\n", "O documento apresenta os factos do processo."])
def test_invalid_or_unchanged_replacement_never_reaches_verifier(tmp_path, replacement):
    scenario = ValidationScenario(replacement=replacement)
    config, http, flow = setup(tmp_path, mutate=scenario)
    result = flow.run(config)
    assert not result.success and len(http.requests) == 4
    assert not any(p["stage"]=="verification" for p in scenario.payloads)
    before = immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests) == 4 and immutable(result.run_dir) == before


@pytest.mark.parametrize("phase", [1,2,3,4])
@pytest.mark.parametrize("kind", ["unknown_usage", "refused", "incomplete"])
def test_native_hard_stops_at_every_stage_never_license_repair_or_repurchase(tmp_path, phase, kind):
    scenario = ValidationScenario()
    def mutate(body,data):
        data = scenario(body,data)
        if "text" in body and len(scenario.payloads)==phase:
            if kind=="unknown_usage": data["usage"]["input_tokens_details"].pop("cache_write_tokens")
            elif kind=="refused": data["output"][0]["content"]=[{"type":"refusal","refusal":"Fictional refusal."}]
            else: data.update(status="incomplete",incomplete_details={"reason":"max_output_tokens"})
        return data
    config,http,flow=setup(tmp_path,mutate=mutate)
    result=flow.run(config)
    assert not result.success and len(http.requests)==phase+1
    before=immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests)==phase+1 and immutable(result.run_dir)==before


@pytest.mark.parametrize("phase", [1,2,3,4])
def test_cancel_after_native_settlement_replays_without_repurchasing_or_resetting_cycle(tmp_path,phase):
    scenario=ValidationScenario()
    holder={}
    def mutate(body,data):
        data=scenario(body,data)
        if "text" in body and len(scenario.payloads)==phase: holder["flow"].cancel()
        return data
    config,http,flow=setup(tmp_path,mutate=mutate)
    holder["flow"]=flow
    result=flow.run(config)
    assert not result.success and len(http.requests)==phase+1
    bodies=list(http.bodies)
    result=flow.run(replace(config,resume=True))
    assert result.success,result.error
    assert len(http.requests)==5 and http.bodies[:len(bodies)]==bodies
    assert read(result.run_dir/"semantic_audit","manifest.json")["consumed_cycles"]==1


@pytest.mark.parametrize("path", ["attempt_00/correction/stage_record.json", "eligibility.json",
    "attempt_01/correction_baseline.json", "attempt_01/correction/stage_record.json", "attempt_01/verification/stage_record.json"])
@pytest.mark.parametrize("when", ["before", "after"])
def test_reconstructs_only_exact_settled_postprocessing_across_restart(tmp_path,monkeypatch,path,when):
    scenario=ValidationScenario()
    config,http,flow=setup(tmp_path,mutate=scenario)
    original=repair._persist
    stopped=[]
    def persist(file,value,**options):
        hit=file.as_posix().endswith('/semantic_audit/'+path) and not stopped
        if hit and when=="before":
            stopped.append(True)
            review._fail("operation_cancelled")
        original(file,value,**options)
        if hit and when=="after":
            stopped.append(True)
            flow.cancel()
    monkeypatch.setattr(repair,"_persist",persist)
    result=flow.run(config)
    assert not result.success and stopped
    bodies=list(http.bodies)
    result=flow.run(replace(config,resume=True))
    assert result.success,result.error
    assert len(http.requests)==5 and http.bodies[:len(bodies)]==bodies


@pytest.mark.parametrize("path", ["attempt_00/correction/stage_record.json", "attempt_00/correction/diagnostic.json",
    "attempt_00/correction/rejected_proposal.json", "eligibility.json", "attempt_01/correction_baseline.json",
    "attempt_01/pair.json", "manifest.json"])
def test_tampered_rejection_or_cycle_evidence_blocks_resume_and_offline_selection(tmp_path,path):
    config,http,flow=setup(tmp_path,mutate=ValidationScenario())
    result=flow.run(config)
    assert result.success,result.error
    file=result.run_dir/'semantic_audit'/path
    file.write_bytes(file.read_bytes()+b' ')
    count=len(http.requests)
    assert not flow.run(replace(config,resume=True)).success
    with pytest.raises(Exception): TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(http.requests)==count


def test_late_page_literal_failure_stops_before_any_replacement_dispatch(tmp_path):
    scenario=ValidationScenario()
    def mutate(body,data):
        data=scenario(body,data)
        if "text" in body and scenario.payloads[-1]["stage"]=="correction":
            value=json.loads(data['output'][0]['content'][0]['text'])
            value['pages'][-1]['corrected_text']='O documento apresenta os factos do processo.'
            data['output'][0]['content'][0]['text']=json.dumps(value)
        return data
    config,http,flow=setup(tmp_path,mutate=mutate)
    with fitz.open(config.pdf_path) as document:
        document.new_page().insert_text((50,80),'Another fictional source page.')
        document.saveIncr()
    result=flow.run(config)
    assert not result.success and len(http.requests)==4
    assert not (result.run_dir/'semantic_audit/attempt_01').exists()


def test_late_page_source_field_failure_stays_ineligible():
    from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
    from tests.test_ar_field_label_boundaries import prepared
    source = prepared("Morada:\nAvenida Clara, 10, 1.º Andar\nCódigo Postal:1234 567 Cidade")
    primary = "العنوان: " + token("Avenida Clara, 10, 1.º Andar") + "\nالرمز البريدي: " + token("1234 567 Cidade")
    pages = [numbered(), page(2, source_text=source, source_text_kind="pretokenized",
        expected_ar_tokens=tuple(extract_locked_tokens(source)), primary_text=primary)]
    data = canonical(pages, [pages[0].primary_text + " (17)", primary.replace("10", "11")])
    with pytest.raises(review.SemanticAuditError, match="correction_literal_or_language_failure"):
        diagnose(pages, data, replace(RECIPE, source_field_policy="baseline_label_value_v1"))


def test_multpage_replacement_retains_adequate_earlier_correction_and_no_change_means_original(tmp_path):
    payloads=[]
    def mutate(body,data):
        if "text" not in body: return data
        payload=json.loads(body['input'][0]['content'][0]['text'])
        payloads.append(deepcopy(payload))
        value=json.loads(data['output'][0]['content'][0]['text'])
        if payload['stage']=='correction' and 'rejected_proposal' not in payload:
            value['pages'][-1]['corrected_text'] += ' (12345)'
        data['output'][0]['content'][0]['text']=json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow=setup(tmp_path,mutate=mutate)
    with fitz.open(config.pdf_path) as document:
        document.new_page().insert_text((50,80),'A second fictional source page.')
        document.saveIncr()
    result=flow.run(config)
    assert result.success,result.error
    replacement=next(p for p in payloads if 'rejected_proposal' in p)
    assert replacement['primary_pages'][0]['text']==PRIMARY
    assert replacement['rejected_proposal']['pages'][0]['text']==CORRECTED
    assert (result.run_dir/'semantic_audit/page_0001.txt').read_text(encoding='utf-8')==CORRECTED
    assert len(http.requests)==6


def test_verifier_triggered_repair_quality_failure_cannot_start_validation_cycle(tmp_path):
    from tests.test_ordinary_semantic_repair import Scenario
    scenario=Scenario()
    def mutate(body,data):
        data=scenario(body,data)
        if 'text' in body and 'prior_findings' in scenario.payloads[-1]:
            value=json.loads(data['output'][0]['content'][0]['text'])
            value['pages'][0]['corrected_text'] += ' (12345)'
            data['output'][0]['content'][0]['text']=json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow=setup(tmp_path,mutate=mutate)
    result=flow.run(config)
    assert not result.success and 'new_actionable_quality_failure' in result.error
    assert len(http.requests)==5 and scenario.verifiers==1
    before=immutable(result.run_dir)
    assert not flow.run(replace(config,resume=True)).success
    assert len(http.requests)==5 and immutable(result.run_dir)==before


def test_native_transport_retries_on_rejected_correction_remain_in_single_stage(tmp_path):
    import httpx
    config,http,flow=setup(tmp_path,mutate=ValidationScenario())
    http.client._max_transport_retries=1
    http.client._base_backoff_seconds=0
    original=http.http._transport.handler
    injected=[]
    def handler(request):
        response=original(request)
        body=json.loads(request.content)
        if 'text' in body:
            payload=json.loads(body['input'][0]['content'][0]['text'])
            if payload['stage']=='correction' and 'rejected_proposal' not in payload and not injected:
                injected.append(True)
                value=json.loads(response.content)
                value['status']='failed'
                return httpx.Response(429,json=value,headers={'content-type':'application/json'})
        return response
    http.http._transport.handler=handler
    result=flow.run(config)
    assert result.success,result.error
    manifest=read(result.run_dir/'semantic_audit','manifest.json')
    rejected=manifest['stages'][1]
    proof=read(result.run_dir/'semantic_audit',rejected['native_settlement_path'])
    assert rejected['outcome']=='rejected_quality' and len(proof['call_ids'])==2
    assert rejected['usage']['input_tokens']==200
    assert manifest['usage']['input_tokens']==500 and len(http.requests)==6


def test_initial_pass_does_not_consume_cycle_or_add_auxiliary_context(tmp_path):
    config,http,flow=setup(tmp_path)
    result=flow.run(config)
    assert result.success,result.error
    manifest=read(result.run_dir/'semantic_audit','manifest.json')
    assert manifest['consumed_cycles']==0 and manifest['repair_trigger'] is None
    assert len(http.requests)==4 and not (result.run_dir/'semantic_audit/eligibility.json').exists()


@pytest.mark.parametrize("dependency", ["semantic_review_model_policy", "semantic_unit_reference_policy",
    "semantic_source_review_policy", "semantic_page_coverage_policy", "source_inventory_max_output_tokens"])
def test_v2_requires_every_saved_strict_dependency(tmp_path, dependency):
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
    from tests.test_workflow_semantic_review_integration import saved_recipe
    _, saved, settings = saved_recipe(tmp_path)
    assert saved["semantic_repair_policy"] == repair.POLICY_V2
    saved.pop(dependency)
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)
