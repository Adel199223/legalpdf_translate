"""Optional reference footer quarantine; no actual sources, SDK or native app."""
from copy import deepcopy
from decimal import Decimal
import hashlib
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_auto_layout as automatic
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate.ordinary_layout_service import _read
from tests.test_ordinary_auto_layout_recovery import offline
from tests import test_ordinary_auto_layout_workflow as flow


def fixture(roles=("reference", "source_folio", "reference")):
    ids=[f'p{i:06d}' for i in (1,2,3)]
    rows=[{'id':pid,'text':f'Fictional line {i}', 'tokens':[{'kind':'t','text':f'Fictional line {i}'}],
        'has_page_break':False,'ppr_xml':'<w:pPr/>'} for i,pid in enumerate(ids)]
    snapshot={'paragraphs':rows}
    view={'paragraphs':deepcopy(rows),'decisions':{'paragraphs':[{'paragraph_id':pid,
        'regions':[{'page_number':1,'bbox_px':[1,1,20,20]}]} for pid in ids]}}
    proposal={'version':c.PROPOSAL_VERSION_V3,'page_number':1,
        'paragraphs':[{'paragraph_id':pid,'role':role,'bold':i==0,'space_after_pt':i+1} for i,(pid,role) in enumerate(zip(ids,roles))],
        'bands':[{'kind':'flow','groups':[{'paragraph_ids':ids,'panel':False}]}],
        'paragraph_partitions':[], 'source_layout_evidence':[{'kind':'source_footer','paragraph_ids':ids,'bbox':[.1,.9,.9,.98]}],
        'source_coverage_findings':[{'kind':'missing_readable_literal','literal':'Q','source_bbox':[.1,.1,.2,.2],
            'insertion_context':{'paragraph_id':ids[0],'position':'before'}}]}
    return snapshot,view,proposal


@pytest.mark.parametrize('roles',[("reference","source_folio","reference"),("reference","body","institution"),
    ("body","reference","body"),("reference",)*3])
def test_v5_quarantines_only_hint_preserving_exact_choices_bands_findings_and_warning(roles):
    args=fixture(roles)
    before=deepcopy(args)
    result=c.proposal_source_evidence(*args,band_normalization_version=c.BAND_NORMALIZATION_V5)
    assert args==before
    assert result['layout']==[] and not result['source_coverage_verified']
    assert result['findings'][0]['literal']=='Q' and result['findings'][0]['review_status']=='unresolved'
    normalization=result['normalization']
    assert normalization['version']==c.OPTIONAL_HINT_NORMALIZATION_V3
    assert normalization['band_normalization_version']==c.BAND_NORMALIZATION_V5
    assert normalization['review_required']
    assert normalization['rejected_hints']==[{'index':0,'kind':'source_footer',
        'paragraph_ids':['p000001','p000002','p000003'],'reason':'source_footer_reference_kept_in_flow'}]
    fields=c.source_evidence_review_fields([result])
    assert fields['source_layout_review_required']
    assert fields['source_layout_rejected_hints'][0]['reason']=='source_footer_reference_kept_in_flow'


@pytest.mark.parametrize('version',[None,c.BAND_NORMALIZATION_V1,c.BAND_NORMALIZATION_V2,c.BAND_NORMALIZATION_V3,c.BAND_NORMALIZATION_V4])
def test_historical_versions_never_gain_reference_quarantine(version):
    with pytest.raises(c.OrdinaryLayoutError):
        c.proposal_source_evidence(*fixture(),band_normalization_version=version)


@pytest.mark.parametrize('optional',[c.OPTIONAL_HINT_NORMALIZATION_V1,c.OPTIONAL_HINT_NORMALIZATION_V2])
def test_v5_requires_optional_v3_for_reference_quarantine(optional):
    with pytest.raises(c.OrdinaryLayoutError):
        c.proposal_source_evidence(*fixture(),band_normalization_version=c.BAND_NORMALIZATION_V5,normalization_version=optional)


@pytest.mark.parametrize('defect',['extra_key','unknown_id','duplicate_id','reordered','nonterminal','midpage','nan',
    'blank','empty_tokens','unknown_role','signature','column','panel','partition','field','numbering','numPr','tab','page_break','interior_break'])
def test_v5_never_rescues_unsafe_reference_hint(defect):
    snapshot,view,proposal=fixture()
    evidence=proposal['source_layout_evidence'][0]
    row=snapshot['paragraphs'][0]
    if defect=='extra_key':evidence['extra']=True
    elif defect=='unknown_id':evidence['paragraph_ids'][0]='unknown'
    elif defect=='duplicate_id':evidence['paragraph_ids'][1]=evidence['paragraph_ids'][0]
    elif defect=='reordered':evidence['paragraph_ids'].reverse()
    elif defect=='nonterminal':evidence['paragraph_ids'].pop()
    elif defect=='midpage':evidence['bbox'][1]=.5
    elif defect=='nan':evidence['bbox'][0]=float('nan')
    elif defect=='blank':row['tokens'][0]['text']=' '
    elif defect=='empty_tokens':row['tokens']=[]
    elif defect in {'unknown_role','signature'}:proposal['paragraphs'][0]['role']='unrecognized' if defect=='unknown_role' else 'signature'
    elif defect=='column':proposal['bands']=[{'kind':'columns','cells':[{'groups':[{'paragraph_ids':evidence['paragraph_ids'],'panel':False}]}]}]
    elif defect=='panel':proposal['bands'][0]['groups'][0]['panel']=True
    elif defect=='partition':proposal['paragraph_partitions']=[{'paragraph_id':row['id']}]
    elif defect=='field':row['has_field']=True
    elif defect=='numbering':row['has_numbering']=True
    elif defect=='numPr':row['ppr_xml']='<w:numPr/>'
    elif defect=='tab':row['tokens'].append({'kind':'tab','text':'\t'})
    else:
        target=snapshot['paragraphs'][-1] if defect=='page_break' else row
        target['has_page_break']=True
        target['tokens'].append({'kind':'page_break','text':''})
    with pytest.raises(c.OrdinaryLayoutError):
        c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V5)


def test_genuine_prechange_policy_identities_and_requests_stay_exact():
    from legalpdf_translate.ordinary_layout_manager import INSTRUCTIONS
    baseline=json.loads((Path(__file__).parent/'fixtures/reference_footer_v5_prechange_policies.json').read_bytes())
    for name,row in baseline['policies'].items():
        policy=(automatic._optional_hint_policy(getattr(c,'OPTIONAL_HINT_NORMALIZATION_'+name[-2:].upper()))
            if name.startswith('optional_') else getattr(automatic,name)())
        assert policy==row['policy']
        fp=policy.split(':',1)[1]
        assert automatic._band_normalization_version(fp)==row['band']
        assert automatic._source_normalization_version(fp)==row['source']
        assert automatic._clock_direction_version(fp)==row['clock']
        assert (policy in automatic._source_folio_policies())==row['folio']
        assert (policy in automatic._metadata_normalization_policies())==row['metadata']
    assert hashlib.sha256(INSTRUCTIONS.encode()).hexdigest()==baseline['instructions_sha256']
    assert hashlib.sha256(c.encode(c.proposal_schema(3,['p000001']))).hexdigest()==baseline['proposal_schema_sha256']
    assert automatic._reference_footer_v5_policy()=='source_image_unreviewed_v1:5737c26b2a9de209b945de79eb74813e7b98e772214082e54d198494a58e6f15'


def test_v5_inherits_v4_heading_and_flow_decisions_without_new_hint(tmp_path):
    from tests.test_ordinary_heading_columns_v4 import heading_case
    snapshot,view,proposal=heading_case()
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V5)==c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V4)


@pytest.mark.parametrize('restart,target_version',[(False,7),(True,7),(False,8)],
    ids=['same_process_saved_v7','capsule_restart_saved_v7','fresh_v8'])
def test_normal_retained_recover_reuses_every_paid_response_and_preserves_old_evidence(tmp_path,monkeypatch,restart,target_version):
    # Historical V7 retains its recipe; V8 exercises a separate fresh successor.
    target_policy=(automatic._terminal_footer_membership_v7_policy if target_version==7
        else automatic._in_body_terminal_closing_v8_policy)
    monkeypatch.setattr(automatic,'frozen_automatic_layout_policy',target_policy)
    monkeypatch.setattr(automatic,'manual_automatic_layout_policy',target_policy)
    source,output=tmp_path/'fictional.pdf',tmp_path/'outputs'
    output.mkdir()
    flow._source(source,('digital',)*3)
    original=flow._proposal
    def proposal(view,page,columns=0):
        result=original(view,page,columns)
        for row in result['paragraphs']:row.update(role='body',heading_level=0,heading_size_pt=None,bold=False)
        ids=[row['paragraph_id'] for row in result['paragraphs']]
        result.update(version=c.PROPOSAL_VERSION_V3,paragraph_partitions=[],source_coverage_findings=[],
            source_layout_evidence=[{'kind':'source_footer','paragraph_ids':ids[-3:],'bbox':[.06,.935,.94,.995]}])
        result['bands']=[{'kind':'flow','groups':[{'paragraph_ids':ids,'panel':False}]}]
        for row,role in zip(result['paragraphs'][-3:],['reference','source_folio','reference'] if page==3 else ['body','source_folio','body']):row['role']=role
        return result
    monkeypatch.setattr(flow,'_proposal',proposal)
    outputs=tuple(f'Fictional body {p}.\nFictional address.\nPage {p} of 3\nFictional contact.' for p in (1,2,3))
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,outputs,(1,2,3))
    from tests.test_terminal_accounting_restore import gmail_fixture,restart_into_app
    loaded,session,gmail_context=gmail_fixture(source,output)
    scope='?mode=shadow&workspace=fictional'
    old_policy=automatic._heading_columns_v4_policy()
    with TestClient(app) as client:
        with monkeypatch.context() as old:
            old.setattr(automatic,'frozen_automatic_layout_policy',lambda:old_policy)
            response=client.post('/api/translation/jobs/translate',json={'mode':'shadow','workspace_id':'fictional',
                'form_values':{'source_path':str(source),'output_dir':str(output),'target_lang':'EN','start_page':1,'end_page':3,
                    'image_mode':'off','ocr_mode':'off','workers':1,'gmail_batch_context':gmail_context}})
            assert response.status_code==200,response.text
            job_id=response.json()['normalized_payload']['job']['job_id']
            failed=flow._wait(jobs,job_id)
        assert failed['result']['automatic_layout']['status']=='raw_fallback'
        assert len(sdk.requests)==len(requests)==3
        run=Path(failed['result']['run_dir'])
        pointer=json.loads((run/'ordinary_auto_layout/operation.json').read_bytes())
        manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        operation=manager.service.root/job_id/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        assert _read(operation/'result.json')['error_code']=='ordinary_layout_invalid_source_footer_evidence'
        before={p:p.read_bytes() for p in operation.rglob('*') if p.is_file() and p.suffix!='.lock'}
        cost=Decimal(str(_read(operation/'accounting_summary.json')['cost_usd']))
        if restart:
            app,jobs=restart_into_app(tmp_path,app,jobs,job_id,loaded,session)
            client=TestClient(app)
            manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        # The ordinary saved-checkpoint Resume remains old V4 and costs zero.
        response=client.post('/api/translation/jobs/translate',json={'mode':'shadow','workspace_id':'fictional',
            'form_values':{'source_path':str(source),'output_dir':str(output),'target_lang':'EN','start_page':1,'end_page':3,
                'image_mode':'off','ocr_mode':'off','workers':1,'resume':True,'gmail_batch_context':gmail_context}})
        assert response.status_code==200,response.text
        job_id=response.json()['normalized_payload']['job']['job_id']
        resumed=flow._wait(jobs,job_id)
        assert resumed['result']['automatic_layout']['status']=='raw_fallback',resumed
        assert len(sdk.requests)==len(requests)==3
        provider=manager.provider_factory
        def no_dispatch(*args):
            bound=provider(*args)
            bound._client.responses.create=lambda **kwargs:pytest.fail('Retained recovery dispatched')
            return bound
        manager.provider_factory=no_dispatch
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        final=flow._wait(jobs,job_id)
        result=final['result']['automatic_layout']
        assert result['status']=='automatic_unreviewed',result
        assert result['source_layout_review_required']
        assert result['source_layout_rejected_hints'][0]['reason']=='source_footer_reference_kept_in_flow'
        assert len(sdk.requests)==len(requests)==3
        direct=run/'ordinary_auto_layout/recoveries/layout_direct_revalidation_v1'
        identity=json.loads((direct/'intent.json').read_bytes())
        assert set(identity['retained_pages'])=={'1','2','3'}
        pointer=json.loads((direct/'operation.json').read_bytes())
        current=manager.service.root/job_id/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        summary=_read(current/'accounting_summary.json')
        assert summary['provider_dispatch_count']==summary['attempt_count']==0
        assert Decimal(str(summary['cost_usd']))==0
        assert Decimal(result['layout_costs']['known_cost_usd'])==cost
        evidence=_read(current/'source_evidence.json')['pages'][-1]
        assert evidence['normalization']['band_normalization_version']==(c.BAND_NORMALIZATION_V7 if target_version==7 else c.BAND_NORMALIZATION_V8)
        # Saved V7 must retain numeric identity after the fresh default advances.
        with monkeypatch.context() as fresh_default:
            fresh_default.setattr(automatic,'frozen_automatic_layout_policy',automatic._in_body_terminal_closing_v8_policy)
            saved=automatic._proposal_evidence(manager,job_id,pointer['baseline_id'],pointer['review_id'],
                pointer['operation_nonce'],(1,2,3),target_policy(),retained_pages=pointer['retained_pages'])
        assert saved['source_folio_direction_version']=='numeric_run_ltr_v3'
        assert evidence['layout']==[] and evidence['source_coverage_verified'] is False
        for page in (1,2,3):assert (current/f'page-{page:04d}.response.json').read_bytes()==before[operation/f'page-{page:04d}.response.json']
        downloaded=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert downloaded.status_code==200
        text=flow._docx_text(downloaded.content)
        assert text.count('Fictional address.')==text.count('Fictional contact.')==3
        raw=jobs.trusted_ordinary_layout_job(job_id,runtime_mode='shadow',workspace_id='fictional')
        assert text==flow._docx_text(raw.original_docx)
        decisions={row['paragraph_id']:row for row in manager.service.state(job_id)['review']['decisions']['paragraphs']}
        for page in (1,2,3):
            for choice in json.loads((current/f'page-{page:04d}.response.json').read_bytes())['paragraphs']:
                assert {key:value for key,value in decisions[choice['paragraph_id']].items() if key not in {'regions','unmapped_reason'}}=={key:value for key,value in choice.items() if key!='bbox'}
        with ZipFile(BytesIO(downloaded.content)) as archive:
            assert all(b'Fictional address.' not in archive.read(name) for name in archive.namelist() if name.startswith('word/footer') and name.endswith('.xml'))
        assert all(p.read_bytes()==raw for p,raw in before.items())
        # Both saved readers require the bound V5 policy and immutable initial view.
        with pytest.raises(c.OrdinaryLayoutError):
            automatic._proposal_evidence(manager,job_id,pointer['baseline_id'],pointer['review_id'],pointer['operation_nonce'],(1,2,3),old_policy,retained_pages=pointer['retained_pages'])
        for key,value in [('band_normalization_version',c.BAND_NORMALIZATION_V4),('review_id','f'*32),('generation',999)]:
            path=current/'proposal_initial_view.json'
            initial=_read(path)
            changed=deepcopy(initial);changed[key]=value
            path.write_bytes(c.encode({'payload':changed,'sha256':c.digest(c.encode(changed))}))
            with pytest.raises(c.OrdinaryLayoutError):automatic._proposal_evidence(manager,job_id,pointer['baseline_id'],pointer['review_id'],pointer['operation_nonce'],(1,2,3),automatic.frozen_automatic_layout_policy(),retained_pages=pointer['retained_pages'])
            path.write_bytes(c.encode({'payload':initial,'sha256':c.digest(c.encode(initial))}))


def test_old_heading_v4_actual_binding_keeps_numeric_and_clock_identity(tmp_path,monkeypatch):
    from tests.test_ordinary_body_columns_workflow import test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims
    monkeypatch.setattr(automatic,'frozen_automatic_layout_policy',automatic._heading_columns_v4_policy)
    test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims(tmp_path,monkeypatch,'fresh')
