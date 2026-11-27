"""Fictional strict pins and all-three-retained V4 recovery, without providers."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate.ordinary_layout_service import _read
from tests.test_ordinary_auto_layout_recovery import offline
from tests import test_ordinary_auto_layout_workflow as flow
from tests import test_ordinary_layout_manager as manager_fixture
from tests.test_ordinary_body_columns_workflow import operation,protected
from tests.test_ordinary_clock_workflow import LINES,install_fictional_split_assembly,candidate
from tests.test_ordinary_layout_service import make_case,nonce


@pytest.mark.parametrize('schema',[c.PROPOSAL_VERSION,c.PROPOSAL_VERSION_V2,c.PROPOSAL_VERSION_V3])
@pytest.mark.parametrize('damage',['none','request_version','initial_version','initial_missing','review_id','generation'])
@pytest.mark.parametrize('mode',['evidence','crash_recovery'])
@pytest.mark.parametrize('band',[c.BAND_NORMALIZATION_V4,c.BAND_NORMALIZATION_V5])
def test_saved_band_exact_initial_view_pins_apply_across_all_response_schemas(tmp_path,monkeypatch,schema,damage,mode,band):
    case=make_case(tmp_path,monkeypatch);original=manager_fixture.proposal
    def proposal(view):
        value=original(view);value['version']=schema
        if schema in {c.PROPOSAL_VERSION_V2,c.PROPOSAL_VERSION_V3}:value['paragraph_partitions']=[]
        if schema==c.PROPOSAL_VERSION_V3:value.update(source_coverage_findings=[],source_layout_evidence=[])
        return value
    monkeypatch.setattr(manager_fixture,'proposal',proposal)
    paid=manager_fixture.enable_paid(case);operation_nonce=nonce()
    result=case.manager.suggest(case.job.job_id,case.view['generation'],operation_nonce,[1],expected_baseline_id=case.view['baseline_id'],band_normalization_version=band)
    assert result['status']=='applied_unreviewed'
    pointer={'origin_job_id':case.job.job_id,'baseline_id':case.view['baseline_id'],'review_id':case.view['review']['review_id'],
        'operation_nonce':operation_nonce,'initial_generation':case.view['generation']}
    # This fixture seeds legacy default-V1 emphasis intent bytes explicitly.
    op=operation(case.manager,pointer);policy=auto._heading_columns_v4_policy() if band==c.BAND_NORMALIZATION_V4 else auto._inline_folio_direction_policy()
    def evidence():return auto._proposal_evidence(case.manager,case.job.job_id,pointer['baseline_id'],pointer['review_id'],operation_nonce,(1,),policy)
    assert evidence()['document_reviewed'] is False
    if damage=='initial_missing':(op/'proposal_initial_view.json').unlink()
    elif damage!='none':
        path=op/('intent.json' if damage=='request_version' else 'proposal_initial_view.json');value=_read(path)
        if damage=='request_version':value['request']['policy']['band_normalization_version']=c.BAND_NORMALIZATION_V3
        elif damage=='initial_version':value['band_normalization_version']=c.BAND_NORMALIZATION_V3
        elif damage=='review_id':value['review_id']='f'*32
        elif damage=='generation':value['generation']+=1
        path.write_bytes(c.encode({'payload':value,'sha256':c.digest(c.encode(value))}))
    def run():
        if mode=='evidence':return evidence()
        (op/'result.json').unlink()
        auto._recover_settled_result(case.manager,pointer,[1],policy_fingerprint=policy.split(':',1)[1])
        return _read(op/'result.json')
    if damage=='none':
        value=run()
        assert (value['document_reviewed'] is False if mode=='evidence' else value['status']=='applied_unreviewed')
    else:
        with pytest.raises(c.OrdinaryLayoutError,match='source_evidence_'):run()
    assert len(paid.calls)==1


def install_heading_proposals(monkeypatch):
    original=flow._proposal
    def proposal(review,page,columns=0):
        value=original(review,page,columns)
        value.update(version=c.PROPOSAL_VERSION_V3,paragraph_partitions=[],source_coverage_findings=[],source_layout_evidence=[])
        for row in value['paragraphs']:row.update(role='body',heading_level=0,heading_size_pt=None,bold=False)
        if page in {2,3}:
            breaks={row['id'] for row in review['paragraphs'] if row['has_page_break']}
            ids=[row['paragraph_id'] for row in value['paragraphs'] if row['paragraph_id'] not in breaks]
            assert len(ids)>=4
            value['bands']=[{'kind':'columns','widths_pct':[65,35],'gutter_pt':12,'cells':[
                {'groups':[{'paragraph_ids':ids[::2],'panel':False}]},
                {'groups':[{'paragraph_ids':ids[1::2],'panel':False}]}]}]
            rest=[row['paragraph_id'] for row in value['paragraphs'] if row['paragraph_id'] in breaks]
            if rest:value['bands'].append({'kind':'flow','groups':[{'paragraph_ids':rest,'panel':False}]})
            if page==3:
                for row in value['paragraphs']:
                    if row['paragraph_id'] in ids:row.update(role='reference')
                row=next(row for row in value['paragraphs'] if row['paragraph_id']==ids[-1])
                row.update(role='heading',heading_level=2,heading_size_pt=17,bold=True,italic=True)
        return value
    monkeypatch.setattr(flow,'_proposal',proposal)


def test_all_three_retained_successor_preserves_strict_history_costs_clock_and_review_gates(tmp_path,monkeypatch):
    monkeypatch.setattr(auto,'frozen_automatic_layout_policy',auto._heading_columns_v4_policy)
    monkeypatch.setattr(auto,'manual_automatic_layout_policy',auto._heading_columns_v4_policy)
    install_heading_proposals(monkeypatch);install_fictional_split_assembly(monkeypatch)
    source,output=tmp_path/'source.pdf',tmp_path/'output';output.mkdir();flow._source(source,('digital',)*3)
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,(LINES,)*3,(1,2,3));scope='?mode=shadow&workspace=fictional'
    with TestClient(app) as client:
        with monkeypatch.context() as former:
            former.setattr(auto,'frozen_automatic_layout_policy',auto._source_bound_v4_policy)
            job_id=flow._start(client,source,output,'AR',start=1,end=3,image_mode='off',page_breaks=True)
            first=flow._wait(jobs,job_id)
        assert first['result']['automatic_layout']['status']=='raw_fallback'
        assert len(sdk.requests)==len(sdk.semantic_requests)==3 and len(requests)==2
        run=Path(first['result']['run_dir']);root=run/'ordinary_auto_layout'
        pointer=json.loads((root/'operation.json').read_bytes());layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        original=operation(layout,pointer);old_files=protected(original);semantic=protected(run/'semantic_audit')
        assert (run/'semantic_audit/manifest.json').is_file()
        old_cost=Decimal(str(_read(original/'accounting_summary.json')['cost_usd']))
        with monkeypatch.context() as old_clock:
            old_clock.setattr(auto,'frozen_automatic_layout_policy',auto._clock_direction_policy)
            old_clock.setattr(auto,'manual_automatic_layout_policy',auto._clock_direction_policy)
            assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
            second=flow._wait(jobs,job_id)
        assert second['result']['automatic_layout']['status']=='raw_fallback'
        assert len(sdk.requests)==len(sdk.semantic_requests)==len(requests)==3
        direct=root/'recoveries/layout_direct_revalidation_v1';direct_pointer=json.loads((direct/'operation.json').read_bytes())
        direct_op=operation(layout,direct_pointer);direct_before=protected(direct_op)
        assert _read(direct_op/'result.json')['error_code']=='ordinary_layout_proposal_coverage'
        assert set(json.loads((direct/'intent.json').read_bytes())['retained_pages'])=={'1','2'}
        direct_cost=Decimal(str(_read(direct_op/'accounting_summary.json')['cost_usd']))
        requests_before=deepcopy(requests);sdk_before=deepcopy(sdk.requests);semantic_requests=deepcopy(sdk.semantic_requests)
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        final=flow._wait(jobs,job_id)
        assert final['result']['automatic_layout']['status']=='automatic_unreviewed',final
        assert requests==requests_before and sdk.requests==sdk_before and sdk.semantic_requests==semantic_requests
        child=root/'recoveries/layout_revalidation_v1';identity=json.loads((child/'intent.json').read_bytes())
        assert set(identity['retained_pages'])=={'1','2','3'}
        next_pointer=json.loads((child/'operation.json').read_bytes());next_op=operation(layout,next_pointer)
        for page,origin in [(1,original),(2,original),(3,direct_op)]:
            assert (next_op/f'page-{page:04d}.response.json').read_bytes()==(origin/f'page-{page:04d}.response.json').read_bytes()
        summary=_read(next_op/'accounting_summary.json')
        assert summary['provider_dispatch_count']==summary['attempt_count']==0
        assert Decimal(str(summary['cost_usd']))==0 and summary['in_flight_count']==summary['unknown_cost_count']==0
        shown=client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        assert Decimal(shown['layout_costs']['cost_usd'])==old_cost+direct_cost
        assert shown['layout_costs']['operations']==3
        marker,value=candidate(layout,child,next_pointer)
        assert _read(next_op/'result.json')['source_layout_review_required'] is True
        pages=value.source_map['source_evidence']['pages']
        assert {page['page_number'] for page in pages if page.get('metadata_band_normalization',{}).get('rejected_bands',[])}=={2,3}
        view=layout.service.state(job_id)['review']
        headings=[row for row in view['decisions']['paragraphs'] if row['role']=='heading']
        assert len(headings)==1 and headings[0]['heading_level']==2 and headings[0]['heading_size_pt']==17
        assert headings[0]['bold'] is True and headings[0]['italic'] is True
        download=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        raw=jobs.trusted_ordinary_layout_job(job_id,runtime_mode='shadow',workspace_id='fictional')
        assert download.status_code==200 and download.content==value.docx_bytes
        assert flow._docx_text(download.content)==flow._docx_text(raw.original_docx)
        with pytest.raises(c.OrdinaryLayoutError,match='output_review_required'):
            layout.service.accept_output(job_id,marker['candidate_id'],view['generation'],nonce(),False,expected_baseline_id=next_pointer['baseline_id'])
        from legalpdf_translate.saved_docx_layout_service import SavedDocxLayoutServiceError
        with pytest.raises(SavedDocxLayoutServiceError):layout.service.saved.build(view['review_id'],view['generation'],nonce(),True)
        assert all(path.read_bytes()==data for path,data in (old_files|direct_before).items())
        assert protected(run/'semantic_audit')==semantic
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        assert flow._wait(jobs,job_id)['result']['automatic_layout']['status']=='automatic_unreviewed'
        assert requests==requests_before and sdk.requests==sdk_before and sdk.semantic_requests==semantic_requests


def test_old_d3_actual_binding_retains_exact_clock_and_numeric_capabilities(tmp_path,monkeypatch):
    from tests.test_ordinary_body_columns_workflow import test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims
    monkeypatch.setattr(auto,'frozen_automatic_layout_policy',auto._clock_direction_policy)
    test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims(tmp_path,monkeypatch,'fresh')
