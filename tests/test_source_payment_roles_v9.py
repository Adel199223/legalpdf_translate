"""Versioned source-relative participant direction; no new semantic authority."""
from copy import deepcopy
import hashlib,json
import pytest
from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate import ordinary_semantic_target_ambiguity as ambiguity
from legalpdf_translate import ordinary_semantic_review as review
from tests.test_visible_source_encoding_v8 import prepared
from tests.test_workflow_semantic_audit_integration import offline
V9='source_commitment_visual_v9'
KEY='semantic_source_review_policy'


def test_V9_inherits_V8_inventory_and_adds_only_two_bound_instruction_paragraphs():
    old,new=policy._suffixes(policy.POLICY_V8),policy._suffixes(V9)
    assert new['source_inventory']==old['source_inventory']
    assert new['correction']==old['correction']+policy.V9_CORRECTION_ADDITION
    assert new['verification']==old['verification']+policy.V9_VERIFICATION_ADDITION
    assert policy.descriptor()==policy.descriptor(policy.POLICY)
    assert policy.descriptor(V9)['policy']==V9 and policy.descriptor(V9)!=policy.descriptor(policy.POLICY_V8)


@pytest.mark.parametrize('off',[False,True])
def test_V9_request_delta_and_initial_trusted_profile_keep_schema_images_and_old_V7_default(off):
    old,new=prepared(policy.POLICY_V8,off=off),prepared(V9,off=off)
    assert old[:5]==new[:5]
    for stage in review.STAGES:
        a,b=deepcopy(old[-1][stage]),deepcopy(new[-1][stage])
        ap,bp=json.loads(a.pop('prompt_text')),json.loads(b.pop('prompt_text'))
        assert ap.pop(KEY)==policy.descriptor(policy.POLICY_V8) and bp.pop(KEY)==policy.descriptor(V9)
        assert ap==bp
        before,after=a.pop('instructions'),b.pop('instructions')
        assert after==before+('' if stage=='source_inventory' else policy.V9_CORRECTION_ADDITION if stage=='correction' else policy.V9_VERIFICATION_ADDITION)
        assert a==b
    pages,_,units,inventory,candidate,requests=new
    initial=ambiguity.adapt_request(requests['verification'],semantic_source_review_policy=V9)
    ambiguity.check_request(initial,pages,units,inventory,candidate,semantic_source_review_policy=V9)
    with pytest.raises(review.SemanticAuditError,match='target_ambiguity_profile'):
        ambiguity.check_request(initial,pages,units,inventory,candidate)
@pytest.mark.parametrize('fault',['trusted_version','descriptor','base_instruction','initial_suffix','schema','source_owner','target_owner','images'])
def test_V9_initial_profile_rejects_mixed_or_unbound_context(fault):
    pages,_,units,inventory,candidate,requests=prepared(V9)
    request=ambiguity.adapt_request(requests['verification'],semantic_source_review_policy=V9)
    if fault=='trusted_version':
        with pytest.raises(review.SemanticAuditError,match='target_ambiguity_profile'):
            ambiguity.check_request(request,pages,units,inventory,candidate,semantic_source_review_policy=policy.POLICY_V8)
        return
    payload=json.loads(request['prompt_text'])
    if fault=='descriptor':payload[KEY]=policy.descriptor(policy.POLICY_V8)
    elif fault=='base_instruction':request['instructions']=request['instructions'].replace(policy.V9_VERIFICATION_ADDITION,'')
    elif fault=='initial_suffix':request['instructions']=request['instructions'].replace(ambiguity.INSTRUCTIONS,'')
    elif fault=='schema':request['response_format']['schema']['properties']['claim_results']['items']['properties']['status']['enum'].remove(ambiguity.STATUS)
    elif fault=='source_owner':payload['source_units'][0]['text']+='changed'
    elif fault=='target_owner':payload['target_units'][0]['text']+='changed'
    else:request['image_data_urls']=()
    request['prompt_text']=review._prompt_json(payload)
    with pytest.raises(review.SemanticAuditError,match='target_ambiguity_profile'):
        ambiguity.check_request(request,pages,units,inventory,candidate,semantic_source_review_policy=V9)


@pytest.mark.parametrize('fault',['null','unknown','old_repair','missing_refs','missing_pages','bad_markup'])
def test_saved_V9_requires_existing_closed_dependencies_without_new_fields(tmp_path,fault):
    from tests.test_workflow_semantic_review_integration import saved_recipe
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe,SemanticAuditRecipeError
    from legalpdf_translate import primary_literal_markup as markup
    _,saved,settings=saved_recipe(tmp_path)
    settings["ocr_engine"]="api"  # Match the saved fresh OCR transport dependency before fault injection.
    assert saved[KEY]==V9 and ordinary_semantic_audit_recipe(settings)==saved
    if fault=='null':saved[KEY]=None
    elif fault=='unknown':saved[KEY]='source_commitment_visual_unregistered'
    elif fault=='old_repair':saved['semantic_repair_policy']='source_grounded_repair_once_v3'
    elif fault=='missing_refs':saved.pop('semantic_unit_reference_policy')
    elif fault=='missing_pages':saved.pop('semantic_page_coverage_policy')
    else:
        saved[markup.KEY]=markup.POLICY
        settings['strip_bidi_controls']=False
    with pytest.raises(SemanticAuditRecipeError):ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize('outcome',['equivalent','unresolved','payer_invention'])
def test_genuine_V9_one_existing_cycle_blind_final_and_saved_replay(tmp_path,monkeypatch,outcome):
    from dataclasses import replace
    from pathlib import Path
    import os
    from legalpdf_translate.workflow import TranslationWorkflow
    from legalpdf_translate import workflow_semantic_audit as glue
    from tests.test_target_ambiguity_repair import workflow_case
    config,http,flow,scenario=workflow_case(tmp_path,outcome=outcome)
    result=flow.run(config)
    assert result.success is (outcome=='equivalent'),result.error
    assert len(http.requests)==6 and scenario.verifiers==2
    saved=flow._last_state.settings['ordinary_semantic_audit_recipe']
    assert saved[KEY]==V9
    semantic=[r for r in http.requests if 'text' in r]
    assert all(json.loads(r['input'][0]['content'][0]['text'])[KEY]==policy.descriptor(V9) for r in semantic)
    initial,final=[r for r in semantic if json.loads(r['input'][0]['content'][0]['text'])['stage']=='verification']
    assert ambiguity.KEY in json.loads(initial['input'][0]['content'][0]['text'])
    final_payload=json.loads(final['input'][0]['content'][0]['text'])
    assert not set(final_payload)&{ambiguity.KEY,'prior_findings','primary_pages','context_text'}
    assert final['instructions'].endswith(policy.V9_VERIFICATION_ADDITION)
    assert ambiguity.STATUS not in final['text']['format']['schema']['properties']['claim_results']['items']['properties']['status']['enum']
    if result.success:
        manifest=json.loads((result.run_dir/'semantic_audit/manifest.json').read_bytes())
        assert manifest['consumed_cycles']==manifest['selected_attempt']==1
        before={p:p.read_bytes() for folder in ('primary_markup','semantic_source','semantic_audit','accounting') for p in (result.run_dir/folder).rglob('*') if p.is_file() and p.suffix!='.lock'}
        requests=deepcopy(http.requests)
        monkeypatch.setattr(glue,'fresh_recipe',lambda *a,**k:pytest.fail('Saved replay consulted fresh recipe'))
        assert flow.run(replace(config,resume=True)).success
        assert TranslationWorkflow(client=http.client,gui_settings={}).run(replace(config,resume=True)).success
        assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
        assert http.requests==requests and all(p.read_bytes()==raw for p,raw in before.items())
        index=os.environ.get('SOURCE_V9_SPECIMEN_INDEX')
        if index:Path(index).write_text(json.dumps({'run_dir':str(result.run_dir),'source_pdf':str(config.pdf_path),'requests':http.requests,'qualification':'genuine mocked V9 workflow/current renderV17, initial target ambiguity one cycle; not semantic model compliance'},ensure_ascii=False,indent=2),encoding='utf8')
    else:
        assert not (result.run_dir/'semantic_audit/manifest.json').exists()
        assert not flow.run(replace(config,resume=True)).success and len(http.requests)==6


@pytest.mark.parametrize('final_status',['equivalent',ambiguity.STATUS])
def test_authority_consumed_cycle_uses_V9_strict_final_without_initial_profile_or_extra_call(tmp_path,final_status):
    from tests.test_source_enclosure_authority_workflow import EnclosureScenario,start
    class Scenario(EnclosureScenario):
        def __call__(self,body,data):
            data=super().__call__(body,data)
            if 'text' in body:
                payload=json.loads(body['input'][0]['content'][0]['text'])
                if payload['stage']=='verification':
                    assert payload[KEY]==policy.descriptor(V9) and ambiguity.KEY not in payload
                    assert ambiguity.STATUS not in body['text']['format']['schema']['properties']['claim_results']['items']['properties']['status']['enum']
                    value=json.loads(data['output'][0]['content'][0]['text']);value['claim_results'][0]['status']=final_status
                    data['output'][0]['content'][0]['text']=json.dumps(value,ensure_ascii=False)
            return data
    scenario=Scenario();config,http,flow=start(tmp_path,scenario);result=flow.run(config)
    assert result.success is (final_status=='equivalent'),result.error
    assert len(http.requests)==5
    assert [p['stage'] for p in scenario.payloads]==['source_inventory','correction','source_literal_authority','verification']