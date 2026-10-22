"""Fictional saved capability routing and genuine pre-change V3 byte replay."""
from dataclasses import asdict,fields,replace
import hashlib,json,shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate import ordinary_semantic_review as engine
from legalpdf_translate.ordinary_semantic_audit import SemanticAuditRecipe
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe,SemanticAuditRecipeError,save_run_state_atomic
from legalpdf_translate.types import TargetLang,ImageMode,OcrEnginePolicy,OcrApiProvider
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_workflow_semantic_review_integration import saved_recipe,setup_review
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_ordinary_semantic_review import Client
from tests.semantic_review_fakes import UNIT_REF_VERSIONS


POLICIES={'semantic_unit_reference_policy':'caller_unit_refs_v1',
    'source_question_row_policy':'baseline_boolean_question_v1'}
FIXTURE=Path(__file__).parent/'fixtures/source_question_unit_refs_prechange_v3'


def test_fresh_v3_saves_both_separate_capabilities(tmp_path):
    _,recipe,settings=saved_recipe(tmp_path)
    assert all(recipe[k]==v for k,v in POLICIES.items())
    assert ordinary_semantic_audit_recipe(settings)==recipe


@pytest.mark.parametrize('key',POLICIES)
@pytest.mark.parametrize('value',[None,'','unknown',False,[],{}])
def test_unknown_or_null_policy_is_not_historical_absence(tmp_path,key,value):
    _,recipe,settings=saved_recipe(tmp_path);recipe[key]=value
    with pytest.raises(SemanticAuditRecipeError,match=key):ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize('key',POLICIES)
@pytest.mark.parametrize('version',['ordinary_semantic_audit_v1','ordinary_semantic_audit_v2'])
def test_legacy_recipe_key_sets_do_not_accept_either_new_capability(tmp_path,key,version):
    _,recipe,settings=saved_recipe(tmp_path)
    recipe['version']=version;recipe.pop('review_protocol');recipe.pop('primary_literal_packaging_version')
    recipe.pop('source_inventory_max_output_tokens')
    recipe.pop("semantic_source_review_policy")
    recipe.pop("semantic_page_coverage_policy")
    recipe.pop("semantic_review_model_policy")
    for other in POLICIES:
        if other!=key:recipe.pop(other)
    if version.endswith('v1'):
        for name in ('context_sha256','context_binding_version','terminology_policy','source_field_policy'):recipe.pop(name)
    with pytest.raises(SemanticAuditRecipeError):ordinary_semantic_audit_recipe(settings)


def test_absent_v3_fields_remain_absent_without_default_insertion(tmp_path):
    _,recipe,settings=saved_recipe(tmp_path)
    for key in POLICIES:recipe.pop(key)
    recipe.pop('source_inventory_max_output_tokens')
    recipe.pop("semantic_source_review_policy")
    recipe.pop("semantic_page_coverage_policy")
    recipe.pop("semantic_review_model_policy")
    before=json.dumps(settings,sort_keys=True)
    assert ordinary_semantic_audit_recipe(settings)==recipe
    assert json.dumps(settings,sort_keys=True)==before


def test_extraction_only_question_option_and_review_only_unit_refs_are_routed_separately(tmp_path,monkeypatch):
    config,sdk,workflow=setup_review(tmp_path)
    extraction,tokenization,evaluation,review_calls=[],[],[],[]
    extract=workflow_module.extract_ordered_page_text
    tokenize=workflow_module.pretokenize_arabic_source
    evaluate=workflow._evaluate_output
    review=engine.run_semantic_review
    def observe_extract(*args,**kwargs):extraction.append(kwargs);return extract(*args,**kwargs)
    def observe_tokenize(*args,**kwargs):tokenization.append(kwargs);return tokenize(*args,**kwargs)
    def observe_evaluate(*args,**kwargs):evaluation.append(kwargs);return evaluate(*args,**kwargs)
    def observe_review(**kwargs):review_calls.append(kwargs);return review(**kwargs)
    monkeypatch.setattr(workflow_module,'extract_ordered_page_text',observe_extract)
    monkeypatch.setattr(workflow_module,'pretokenize_arabic_source',observe_tokenize)
    monkeypatch.setattr(workflow,'_evaluate_output',observe_evaluate)
    monkeypatch.setattr(engine,'run_semantic_review',observe_review)
    result=workflow.run(config)
    assert result.success,result.error
    assert {'source_field_policy':'baseline_label_value_v1','source_question_row_policy':POLICIES['source_question_row_policy']} in extraction
    assert tokenization and evaluation and review_calls
    assert all('source_question_row_policy' not in k and 'semantic_unit_reference_policy' not in k for k in tokenization+evaluation)
    assert review_calls[0]['semantic_unit_reference_policy']==POLICIES['semantic_unit_reference_policy']
    assert 'source_question_row_policy' not in review_calls[0]
    assert [r['text']['format']['name'] for r in sdk.requests[1:]]==list(UNIT_REF_VERSIONS.values())


@pytest.mark.parametrize('enabled',[False,True])
def test_saved_v3_presence_controls_run_load_and_completed_replay_without_new_dispatch(tmp_path,monkeypatch,enabled):
    if not enabled:
        fresh=glue.fresh_recipe
        def historical(*args,**kwargs):
            recipe=fresh(*args,**kwargs)
            for key in POLICIES:recipe.pop(key)
            recipe.pop('source_inventory_max_output_tokens')
            recipe.pop("semantic_source_review_policy")
            recipe.pop("semantic_page_coverage_policy")
            recipe.pop("semantic_review_model_policy")
            return recipe
        monkeypatch.setattr(glue,'fresh_recipe',historical)
    config,sdk,workflow=setup_review(tmp_path)
    seen=[];run=engine.run_semantic_review;load=engine.load_semantic_review
    def observe_run(**kwargs):seen.append(('run',kwargs));return run(**kwargs)
    def observe_load(**kwargs):seen.append(('load',kwargs));return load(**kwargs)
    monkeypatch.setattr(engine,'run_semantic_review',observe_run)
    monkeypatch.setattr(engine,'load_semantic_review',observe_load)
    result=workflow.run(config)
    assert result.success,result.error
    protected={p:p.read_bytes() for name in ('semantic_audit','semantic_source') for p in (result.run_dir/name).rglob('*') if p.is_file()}
    protected[result.run_dir/'semantic_context.json']=(result.run_dir/'semantic_context.json').read_bytes()
    assert workflow.run(replace(config,resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(sdk.requests)==4 and all(p.read_bytes()==raw for p,raw in protected.items())
    assert any(kind=='load' for kind,_ in seen)
    assert all(('semantic_unit_reference_policy' in args) is enabled for _,args in seen)
    assert all('source_question_row_policy' not in args for _,args in seen)


@pytest.mark.parametrize('key',POLICIES)
@pytest.mark.parametrize('mutation',['remove','unknown'])
def test_saved_policy_mutation_cannot_reinterpret_completed_source_or_audit(tmp_path,key,mutation):
    config,sdk,workflow=setup_review(tmp_path);result=workflow.run(config)
    assert result.success,result.error
    recipe=workflow._last_state.settings['ordinary_semantic_audit_recipe']
    if mutation=='remove':recipe.pop(key)
    else:recipe[key]='unknown'
    save_run_state_atomic(workflow._last_paths.run_state_path,workflow._last_state)
    with pytest.raises(ValueError):workflow.run(replace(config,resume=True))
    assert len(sdk.requests)==4


def test_genuine_old_v3_recipe_context_source_requests_raw_and_manifest_replay_exactly(tmp_path):
    inputs=json.loads((FIXTURE/'inputs.json').read_bytes())
    receipt=json.loads((FIXTURE/'generation_receipt.json').read_bytes())
    assert receipt['generator_engine_sha256']=='89a8e76903d9ea3a4a5f5902028f509a3b5cad148e16ca95ce8930bc71ecbe09'
    assert receipt['generator_glue_sha256']=='ac4ae1957f9bf1d63c2e587c6dbdfe4cfc1107c44bea71f3d5f6cc7d81707a16'
    for name,digest in receipt['fixture_files'].items():assert hashlib.sha256((FIXTURE/name).read_bytes()).hexdigest()==digest
    run_dir=tmp_path/'saved';shutil.copytree(FIXTURE/'run',run_dir)
    source=tmp_path/'source_stub.txt';source.write_bytes((FIXTURE/'source_stub.txt').read_bytes())
    settings=inputs['settings'];saved=settings['ordinary_semantic_audit_recipe']
    assert all(key not in ordinary_semantic_audit_recipe(settings) for key in POLICIES)
    config=SimpleNamespace(pdf_path=source,target_lang=TargetLang.AR,image_mode=ImageMode.OFF,
        ocr_engine=OcrEnginePolicy.LOCAL,ocr_api_provider=OcrApiProvider.OPENAI,
        effort=SimpleNamespace(value=saved['reasoning_effort']),effort_policy=SimpleNamespace(value=saved['effort_policy']))
    fresh=glue.fresh_recipe(config,saved['model'],settings['ordinary_auto_layout_policy'],context_text=inputs['context_text'],context_hash=inputs['context_hash'])
    for key in POLICIES:fresh.pop(key)
    fresh.pop('source_inventory_max_output_tokens')
    fresh.pop("semantic_source_review_policy")
    fresh.pop("semantic_page_coverage_policy")
    fresh.pop("semantic_review_model_policy")
    assert fresh["primary_literal_packaging_version"] == "lossless_source_components_v2"
    assert saved["primary_literal_packaging_version"] == "lossless_source_components_v1"
    # Compare the historical policy projection; the saved fixture is never upgraded.
    fresh["primary_literal_packaging_version"] = saved["primary_literal_packaging_version"]
    assert fresh==saved
    state=SimpleNamespace(settings=settings,context_hash=inputs['context_hash'],pdf_fingerprint=inputs['pdf_sha256'],
        pages={'1':inputs['page_record']},selection_page_count=1,selection_start_page=1,selection_end_page=1)
    before={p.relative_to(run_dir).as_posix():p.read_bytes() for p in run_dir.rglob('*') if p.is_file()}
    glue.capture_context(state=state,run_dir=run_dir,context_text=inputs['context_text'],context_hash=inputs['context_hash'])
    glue.capture_source(state=state,run_dir=run_dir,**inputs['source_args'])
    pages,_,context=glue._pages(state=state,config=config,run_dir=run_dir,pages_dir=run_dir/'pages')
    assert json.loads(json.dumps([asdict(p) for p in pages]))==inputs['engine_pages']
    recipe=SemanticAuditRecipe(**{f.name:saved[f.name] for f in fields(SemanticAuditRecipe) if f.name in saved},context_text=context)
    assert asdict(recipe)==inputs['engine_recipe']
    loaded=engine.load_semantic_review(pages=pages,recipe=recipe,pdf_sha256=inputs['pdf_sha256'],evidence_dir=run_dir/'semantic_audit')
    assert loaded.reused and loaded.binding_sha256==receipt['binding_sha256']
    assert before=={p.relative_to(run_dir).as_posix():p.read_bytes() for p in run_dir.rglob('*') if p.is_file()}
    client=Client();client.model=saved['model']
    fresh_result=engine.run_semantic_review(pages=pages,recipe=recipe,pdf_sha256=inputs['pdf_sha256'],evidence_dir=tmp_path/'fresh_audit',client=client)
    assert fresh_result.binding_sha256==receipt['binding_sha256']
    assert json.loads(json.dumps(client.requests))==inputs['requests']
    assert len(client.requests)==3
