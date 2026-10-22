"""Fictional browser/native-accounting coverage for the saved V3 presentation policy."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import workflow_semantic_audit as semantic_glue
from legalpdf_translate.ordinary_layout_service import _read
from tests.test_ordinary_auto_layout_recovery import offline
from tests import test_ordinary_auto_layout_workflow as flow
from tests import test_ordinary_layout_manager as manager_fixture
from tests.test_ordinary_layout_service import make_case, nonce


def install_body_proposal(monkeypatch):
    original = flow._proposal
    def proposal(review,page,columns=0):
        # Keep this local adapter explicit, avoiding recursion through monkeypatch.
        value = original(review,page,columns)
        value.update(version=c.PROPOSAL_VERSION_V3,paragraph_partitions=[],source_coverage_findings=[],source_layout_evidence=[])
        for row in value['paragraphs']:
            row.update(role='body',heading_level=0,heading_size_pt=None,bold=False)
        if page == 2 or len(review['pages']) == 1:
            break_ids={row['id'] for row in review['paragraphs'] if row['has_page_break']}
            ids=[row['paragraph_id'] for row in value['paragraphs'] if row['paragraph_id'] not in break_ids]
            assert len(ids) >= 4
            value['bands']=[{'kind':'columns','widths_pct':[65,35],'gutter_pt':12,'cells':[
                {'groups':[{'paragraph_ids':ids[::2],'panel':False}]},
                {'groups':[{'paragraph_ids':ids[1::2],'panel':False}]}]}]
            rest=[row['paragraph_id'] for row in value['paragraphs'] if row['paragraph_id'] in break_ids]
            if rest: value['bands'].append({'kind':'flow','groups':[{'paragraph_ids':rest,'panel':False}]})
        return value
    monkeypatch.setattr(flow,'_proposal',proposal)


def operation(layout,pointer):
    return layout.service.root/pointer['origin_job_id']/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']


def protected(directory):
    return {p:p.read_bytes() for p in directory.rglob('*') if p.is_file() and p.suffix != '.lock'}


def test_fresh_automatic_body_fallback_downloads_exact_content_with_honest_warning_and_review_gates(tmp_path,monkeypatch):
    install_body_proposal(monkeypatch)
    source,output=tmp_path/'source.pdf',tmp_path/'output'; output.mkdir()
    flow._source(source,('digital',))
    text='Fictional prompt one\nFictional answer one\nFictional prompt two\nFictional answer two\nFictional continuation'
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,(text,),(1,))
    scope='?mode=shadow&workspace=fictional'
    with TestClient(app) as client:
        job_id=flow._start(client,source,output,'EN',start=1,end=1,image_mode='off')
        job=flow._wait(jobs,job_id)
        assert job['result']['automatic_layout']['status']=='automatic_unreviewed',job['result']['automatic_layout']
        assert len(sdk.requests)==len(requests)==1
        shown=client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        download=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert download.status_code==200 and sha256(download.content).hexdigest()==shown['delivery']['sha256']
        raw=jobs.trusted_ordinary_layout_job(job_id,runtime_mode='shadow',workspace_id='fictional')
        assert flow._docx_text(download.content)==flow._docx_text(raw.original_docx)
        root=Path(job['result']['run_dir'])/'ordinary_auto_layout'
        pointer=json.loads((root/'operation.json').read_bytes())
        layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        evidence=auto._proposal_evidence(layout,job_id,pointer['baseline_id'],pointer['review_id'],pointer['operation_nonce'],(1,),auto.frozen_automatic_layout_policy())
        assert evidence['document_reviewed'] is False and evidence['rendered_layout_acceptance']=='not_evaluated'
        page=evidence['source_evidence']['pages'][0]
        assert page['source_coverage_verified'] is False
        assert page['metadata_band_normalization']['rejected_bands'][0]['reason']=='generated_plain_columns_restored_to_text_order'
        op=operation(layout,pointer)
        assert _read(op/'result.json')['source_layout_review_required'] is True
        assert _read(op/'intent.json')['request']['policy']['band_normalization_version']==c.BAND_NORMALIZATION_V5
        assert _read(op/'proposal_initial_view.json')['band_normalization_version']==c.BAND_NORMALIZATION_V5
        view=layout.service.state(job_id)['review']
        assert view['decisions']['review']['document_reviewed'] is False
        # A generated warning must not turn into operator review or permit a false reviewed receipt.
        marker=json.loads((root/'candidate.json').read_bytes())
        candidate=layout.service.saved.verified_unreviewed_candidate(pointer['review_id'],marker['candidate_id'])
        assert candidate.receipt['document_reviewed'] is False
        assert candidate.source_map['source_evidence']==evidence['source_evidence']
        from legalpdf_translate.saved_docx_layout_service import SavedDocxLayoutServiceError
        with pytest.raises(SavedDocxLayoutServiceError):
            layout.service.saved.build(view['review_id'],view['generation'],nonce(),True)
        with pytest.raises(SavedDocxLayoutServiceError,match='invalid_ordinary_binding'):
            layout.service.saved.attach_ordinary_binding(view['review_id'],{},(1,),evidence['policy_fingerprint'],
                {**evidence,'document_reviewed':True},expected_generation=view['generation'])
        with pytest.raises(c.OrdinaryLayoutError,match='output_review_required'):
            layout.service.accept_output(job_id,marker['candidate_id'],view['generation'],nonce(),False,expected_baseline_id=pointer['baseline_id'])


@pytest.mark.parametrize('strict', [False,True])
def test_direct_successor_reuses_two_settled_pages_only_sends_third_and_reuses_strict_semantics(tmp_path,monkeypatch,strict):
    install_body_proposal(monkeypatch)
    source,output=tmp_path/'source.pdf',tmp_path/'output'; output.mkdir()
    flow._source(source,('digital',)*3)
    lines=('بيان خيالي أول\nجواب خيالي أول\nبيان خيالي ثان\nجواب خيالي ثان\nبيان خيالي أخير'
           if strict else 'Fictional prompt one\nFictional answer one\nFictional prompt two\nFictional answer two\nFictional continuation')
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,(lines,lines,lines),(1,2,3))
    scope='?mode=shadow&workspace=fictional'
    old=auto._source_bound_v4_policy(); old_mapper=auto._band_normalization_version
    with TestClient(app) as client:
        with monkeypatch.context() as previous:
            previous.setattr(auto,'frozen_automatic_layout_policy',lambda:old)
            previous.setattr(auto,'_band_normalization_version',lambda fp: c.BAND_NORMALIZATION_V2 if fp==old.split(':',1)[1] else old_mapper(fp))
            if strict:
                # Seed the historical semantic policy explicitly, alongside the
                # old layout policy; recovery must preserve both saved histories.
                fresh=semantic_glue.fresh_recipe
                def historical_recipe(*args,**kwargs):
                    recipe=fresh(*args,**kwargs)
                    recipe['semantic_repair_policy']='source_grounded_repair_once_v3'
                    recipe.pop('semantic_enclosure_authority_policy',None)
                    return recipe
                previous.setattr(semantic_glue,'fresh_recipe',historical_recipe)
            job_id=flow._start(client,source,output,'AR' if strict else 'EN',start=1,end=3,image_mode='off',page_breaks=True)
            initial=flow._wait(jobs,job_id)
        assert initial['result']['automatic_layout']['status']=='raw_fallback',initial
        assert len(sdk.requests)==3 and len(requests)==2
        semantic_calls=len(sdk.semantic_requests)
        assert semantic_calls==(3 if strict else 0)
        root=Path(initial['result']['run_dir'])/'ordinary_auto_layout'
        layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        pointer=json.loads((root/'operation.json').read_bytes()); op=operation(layout,pointer)
        before=protected(op)
        semantic_before=protected(Path(initial['result']['run_dir'])/'semantic_audit')
        if strict:
            assert (Path(initial['result']['run_dir'])/'semantic_audit/manifest.json').is_file()
            assert json.loads((Path(initial['result']['run_dir'])/'run_state.json').read_bytes())['settings']['ordinary_semantic_audit_recipe']['semantic_repair_policy']=='source_grounded_repair_once_v3'
        oldcost=Decimal(str(_read(op/'accounting_summary.json')['cost_usd']))
        # Existing dedicated recovery does not execute primary or semantic stages.
        response=client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope)
        assert response.status_code==200,response.text
        recovered=flow._wait(jobs,job_id)
        assert recovered['result']['automatic_layout']['status']=='automatic_unreviewed',recovered['result']['automatic_layout']
        assert len(sdk.requests)==3 and len(sdk.semantic_requests)==semantic_calls and len(requests)==3
        assert json.loads(requests[-1]['input'][0]['content'][0]['text'])['page_number']==3
        child=root/'recoveries/layout_direct_revalidation_v1'
        identity=json.loads((child/'intent.json').read_bytes())
        assert set(identity['retained_pages'])=={'1','2'}
        nextop=operation(layout,json.loads((child/'operation.json').read_bytes()))
        assert all(p.read_bytes()==raw for p,raw in before.items())
        for page in [1,2]: assert (nextop/f'page-{page:04d}.response.json').read_bytes()==(op/f'page-{page:04d}.response.json').read_bytes()
        assert protected(Path(initial['result']['run_dir'])/'semantic_audit')==semantic_before
        summary=_read(nextop/'accounting_summary.json')
        assert summary['provider_dispatch_count']==1 and summary['in_flight_count']==0
        shown=client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        assert shown['layout_costs']['operations']==2
        assert Decimal(shown['layout_costs']['cost_usd'])==oldcost+Decimal(str(summary['cost_usd']))
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        assert len(requests)==3
        resumed_id=flow._start(client,source,output,'AR' if strict else 'EN',start=1,end=3,image_mode='off',page_breaks=True,resume=True)
        flow._wait(jobs,resumed_id)
        assert len(sdk.requests)==3 and len(sdk.semantic_requests)==semantic_calls
        assert client.post(f'/api/translation/jobs/{resumed_id}/layout/recover'+scope).status_code==200
        terminal=flow._wait(jobs,resumed_id)
        assert terminal['result']['automatic_layout']['status']=='automatic_unreviewed'
        assert len(requests)==3 and all(p.read_bytes()==raw for p,raw in before.items())
        assert protected(Path(initial['result']['run_dir'])/'semantic_audit')==semantic_before


@pytest.mark.parametrize('policy_kind', ['former','fresh'])
def test_old_and_fresh_numeric_run_evidence_stays_exact_and_replays_without_dispatch(tmp_path,monkeypatch,policy_kind):
    case=make_case(tmp_path,monkeypatch)
    original=manager_fixture.proposal
    def proposal(view):
        value=original(view);value.update(version=c.PROPOSAL_VERSION_V3,paragraph_partitions=[],source_coverage_findings=[],source_layout_evidence=[])
        return value
    monkeypatch.setattr(manager_fixture,'proposal',proposal)
    paid=manager_fixture.enable_paid(case)
    policy=auto._source_bound_v4_policy() if policy_kind=='former' else auto.frozen_automatic_layout_policy()
    operation_nonce=nonce()
    result=case.manager.suggest(case.job.job_id,case.view['generation'],operation_nonce,[1],expected_baseline_id=case.view['baseline_id'],band_normalization_version=auto._band_normalization_version(policy.split(':',1)[1]),emphasis_normalization_version=auto._emphasis_normalization_version(policy.split(':',1)[1]))
    assert result['status']=='applied_unreviewed'
    kwargs=(case.manager,case.job.job_id,case.view['baseline_id'],case.view['review']['review_id'],operation_nonce,(1,),policy)
    first=auto._proposal_evidence(*kwargs)
    assert first['source_folio_direction_version']=='numeric_run_ltr_v3'
    assert auto._proposal_evidence(*kwargs)==first and len(paid.calls)==1


@pytest.mark.parametrize('schema', [c.PROPOSAL_VERSION,c.PROPOSAL_VERSION_V2,c.PROPOSAL_VERSION_V3])
@pytest.mark.parametrize('damage', ['request_version','initial_version','initial_missing'])
@pytest.mark.parametrize('mode', ['evidence','crash_recovery'])
def test_saved_v3_requires_its_exact_request_and_initial_view_version_before_any_replay(tmp_path,monkeypatch,damage,mode,schema):
    case=make_case(tmp_path,monkeypatch)
    original=manager_fixture.proposal
    def proposal(view):
        value=original(view);value['version']=schema
        if schema in {c.PROPOSAL_VERSION_V2,c.PROPOSAL_VERSION_V3}: value['paragraph_partitions']=[]
        if schema==c.PROPOSAL_VERSION_V3: value.update(source_coverage_findings=[],source_layout_evidence=[])
        return value
    monkeypatch.setattr(manager_fixture,'proposal',proposal)
    paid=manager_fixture.enable_paid(case); operation_nonce=nonce()
    case.manager.suggest(case.job.job_id,case.view['generation'],operation_nonce,[1],expected_baseline_id=case.view['baseline_id'],band_normalization_version=c.BAND_NORMALIZATION_V3)
    pointer={'origin_job_id':case.job.job_id,'baseline_id':case.view['baseline_id'],'review_id':case.view['review']['review_id'], 'operation_nonce':operation_nonce,'initial_generation':case.view['generation']}
    op=operation(case.manager,pointer)
    if damage=='request_version':
        path=op/'intent.json'; value=_read(path); value['request']['policy']['band_normalization_version']=c.BAND_NORMALIZATION_V2
        path.write_bytes(c.encode({'payload':value,'sha256':c.digest(c.encode(value))}))
    elif damage=='initial_version':
        path=op/'proposal_initial_view.json'; value=_read(path);value['band_normalization_version']=c.BAND_NORMALIZATION_V2
        path.write_bytes(c.encode({'payload':value,'sha256':c.digest(c.encode(value))}))
    else: (op/'proposal_initial_view.json').unlink()
    with pytest.raises(c.OrdinaryLayoutError,match='source_evidence_'):
        if mode=='evidence':
            auto._proposal_evidence(case.manager,case.job.job_id,case.view['baseline_id'],case.view['review']['review_id'],operation_nonce,(1,),auto._clock_direction_policy())
        else:
            (op/'result.json').unlink()
            auto._recover_settled_result(case.manager,pointer,[1],policy_fingerprint=auto._clock_direction_policy().split(':',1)[1])
    assert len(paid.calls)==1


@pytest.mark.parametrize('policy_kind', ['former','fresh'])
def test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims(tmp_path,monkeypatch,policy_kind):
    from legalpdf_translate.saved_docx_layout_service import SavedDocxLayoutServiceError
    original=flow._proposal
    def proposal(review,page,columns=0):
        value=original(review,page,columns)
        value.update(version=c.PROPOSAL_VERSION_V3,paragraph_partitions=[],source_coverage_findings=[],source_layout_evidence=[])
        return value
    monkeypatch.setattr(flow,'_proposal',proposal)
    source,output=tmp_path/'source.pdf',tmp_path/'output';output.mkdir();flow._source(source,('digital',))
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,('Fictional body paragraph',),(1,))
    policy=auto._source_bound_v4_policy() if policy_kind=='former' else auto.frozen_automatic_layout_policy()
    mapper=auto._band_normalization_version
    with TestClient(app) as client:
        with monkeypatch.context() as previous:
            if policy_kind=='former':
                previous.setattr(auto,'frozen_automatic_layout_policy',lambda:policy)
                previous.setattr(auto,'_band_normalization_version',lambda fp:c.BAND_NORMALIZATION_V2 if fp==policy.split(':',1)[1] else mapper(fp))
            job_id=flow._start(client,source,output,'EN',start=1,end=1,image_mode='off')
            job=flow._wait(jobs,job_id)
        assert job['result']['automatic_layout']['status']=='automatic_unreviewed'
        run=Path(job['result']['run_dir']); root=run/'ordinary_auto_layout'
        pointer=json.loads((root/'operation.json').read_bytes())
        layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        evidence=auto._proposal_evidence(layout,job_id,pointer['baseline_id'],pointer['review_id'],pointer['operation_nonce'],(1,),policy)
        raw_map=json.loads(next(run.rglob('provider.source_map.json')).read_bytes())
        view=layout.service.state(job_id)['review']
        def attach(fp,value):
            return layout.service.saved.attach_ordinary_binding(view['review_id'],raw_map,(1,),fp,value,expected_generation=view['generation'])
        # This call runs with today's fresh helper even for the retained former policy.
        before=protected(operation(layout,pointer))
        attach(policy.split(':',1)[1],evidence)
        missing={k:v for k,v in evidence.items() if k!='source_folio_direction_version'}
        no_source={k:v for k,v in evidence.items() if k!='source_evidence'}
        for fp,value in [(policy.split(':',1)[1],missing),
            (policy.split(':',1)[1],{**evidence,'source_folio_direction_version':'numeric_run_ltr_v2'}),
            (policy.split(':',1)[1],no_source),
            (auto._source_bound_v3_policy().split(':',1)[1],evidence),('f'*64,evidence)]:
            with pytest.raises(SavedDocxLayoutServiceError,match='ordinary_source_folio_direction_changed'):
                attach(fp,value)
        assert protected(operation(layout,pointer))==before
        assert len(sdk.requests)==len(requests)==1
