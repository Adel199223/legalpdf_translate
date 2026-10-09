"""Real browser flow retains two settled responses and buys only unsent pages."""
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_layout_manager as manager_module
from legalpdf_translate.ordinary_layout_contracts import PROPOSAL_VERSION_V2, fail
from legalpdf_translate.ordinary_layout_service import _read
from legalpdf_translate.openai_client import OpenAIResponsesClient
from tests.test_ordinary_auto_layout_recovery import offline
from tests.test_ordinary_auto_layout_workflow import _app, _source, _start, _wait


@pytest.mark.parametrize('resume,cancel,select_raw', [(False,False,False),(True,False,False),(False,True,False),(True,False,True)])
def test_direct_failed_layout_reuses_two_responses_with_one_predecessor(tmp_path, monkeypatch, resume, cancel,select_raw):
    source,output=tmp_path/'source.pdf',tmp_path/'output'
    output.mkdir(); _source(source,('digital',)*7)
    pages=(3,4,5,6,7)
    app,jobs,translation_sdk,_=_app(tmp_path,monkeypatch,
        tuple(f'English source page {p}.\nFooter contact page {p}.' for p in pages),pages)
    scope='?mode=shadow&workspace=fictional'
    sent=[]; entered,release=Event(),Event()
    with TestClient(app) as client:
        manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        def provider(job,policy):
            def create(**request):
                page=json.loads(request['input'][0]['content'][0]['text'])['page_number']
                sent.append(page)
                if page==5 and cancel:
                    entered.set(); assert release.wait(20)
                view=manager.service.state(job.job_id)['review']
                choices=[]
                for choice in view['decisions']['paragraphs']:
                    if {r['page_number'] for r in choice['regions']}!={page}: continue
                    row={k:v for k,v in choice.items() if k not in {'regions','unmapped_reason'}}
                    row.update(bbox=[.1,.1,.9,.9],alignment='left')
                    choices.append(row)
                assert choices
                proposal={'version':PROPOSAL_VERSION_V2,'page_number':page,'paragraphs':choices,
                    'bands':[{'kind':'flow','groups':[{'paragraph_ids':[p['paragraph_id'] for p in choices],'panel':False}]}],
                    'paragraph_partitions':[]}
                return SimpleNamespace(id=f'fictional-direct-{page}',model=policy.model,status='completed',
                    service_tier='default',output=[],output_text=json.dumps(proposal),usage={'input_tokens':80,
                    'output_tokens':60,'total_tokens':140,'input_tokens_details':{'cached_tokens':0},
                    'output_tokens_details':{'reasoning_tokens':0}})
            return OpenAIResponsesClient(model=policy.model,sdk_client=SimpleNamespace(
                base_url='https://api.openai.com/v1/',responses=SimpleNamespace(create=create)),
                max_transport_retries=0,pre_call_jitter_seconds=0)
        manager.provider_factory=provider
        normalize=manager_module.normalize_proposals
        def previous_break_guard(snapshot,view,proposals):
            if proposals[0]['page_number']==4: fail('page_break_requires_flow')
            return normalize(snapshot,view,proposals)
        with monkeypatch.context() as old:
            old.setattr(manager_module,'normalize_proposals',previous_break_guard)
            original=_start(client,source,output,'EN',start=3,end=7,image_mode='off',page_breaks=True)
            first=_wait(jobs,original)
        assert first['result']['automatic_layout']['status']=='raw_fallback'
        assert sent==[3,4] and len(translation_sdk.requests)==5
        run=Path(first['result']['run_dir']); root=run/'ordinary_auto_layout'
        old_pointer=json.loads((root/'operation.json').read_bytes())
        old_op=manager.service.root/original/'baselines'/old_pointer['baseline_id']/'suggestions'/old_pointer['operation_nonce']
        assert _read(old_op/'result.json')['error_code']=='ordinary_layout_page_break_requires_flow'
        old_cost=Decimal(str(_read(old_op/'accounting_summary.json')['cost_usd']))
        protected={p:p.read_bytes() for p in old_op.rglob('*') if p.is_file() and p.suffix!='.lock'}
        protected.update({p:p.read_bytes() for p in (root/'intent.json',root/'operation.json')})
        if not resume:
            # Lost/invalid retained bytes, orphan response, or unverified usage
            # stop before an authorization or new request, never repurchasing.
            orphan=old_op/'page-0005.response.json'
            mutations=[(old_op/'page-0004.response.json',b'{}'),(old_op/'accounting_summary.json',b'{}'),
                (orphan,(old_op/'page-0003.response.json').read_bytes())]
            for path,bad in mutations:
                before=path.read_bytes() if path.exists() else None
                path.write_bytes(bad)
                assert client.post(f'/api/translation/jobs/{original}/layout/recover'+scope).status_code==200
                held=_wait(jobs,original)
                assert held['result']['automatic_layout']['status']=='raw_fallback'
                assert sent==[3,4]
                if before is None: path.unlink()
                else: path.write_bytes(before)
        job_id=original
        if resume:
            job_id=_start(client,source,output,'EN',start=3,end=7,image_mode='off',page_breaks=True,resume=True)
            _wait(jobs,job_id)
        if select_raw:
            from tests.test_ordinary_layout_service import nonce
            prepared=manager.prepare(job_id,nonce())
            manager.select_delivery(job_id,0,nonce(),'original',
                keep_ordinary_confirmed=True,expected_baseline_id=prepared['baseline_id'])
            assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
            held=_wait(jobs,job_id)
            assert held['result']['automatic_layout']['status']=='raw_fallback'
            assert sent==[3,4] and len(translation_sdk.requests)==5
            assert not (root/'recoveries/layout_direct_revalidation_v1/operation.json').exists()
            assert all(p.read_bytes()==data for p,data in protected.items())
            return
        assert len(translation_sdk.requests)==5
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        if cancel:
            assert entered.wait(20)
            assert client.post(f'/api/translation/jobs/{job_id}/cancel'+scope).status_code==200
            release.set(); _wait(jobs,job_id)
            assert sent==[3,4,5]
            assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
            _wait(jobs,job_id)
            assert sent==[3,4,5]
            assert all(p.read_bytes()==data for p,data in protected.items())
            return
        result=_wait(jobs,job_id)
        assert result['result']['automatic_layout']['status']=='automatic_unreviewed',result['result']['automatic_layout']
        assert sent==[3,4,5,6,7] and len(translation_sdk.requests)==5
        folder=root/'recoveries/layout_direct_revalidation_v1'
        identity=json.loads((folder/'intent.json').read_bytes())
        assert 'recovery_predecessor' in identity and 'revalidation_predecessor' not in identity
        assert set(identity['retained_pages'])=={'3','4'}
        pointer=json.loads((folder/'operation.json').read_bytes())
        new_op=manager.service.root/job_id/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        for page in (3,4):
            assert (new_op/f'page-{page:04d}.response.json').read_bytes()==protected[old_op/f'page-{page:04d}.response.json']
            assert _read(new_op/f'page-{page:04d}.retained.json')['predecessor']==identity['recovery_predecessor']
        summary=_read(new_op/'accounting_summary.json')
        assert summary['provider_dispatch_count']==3 and summary['in_flight_count']==0
        new_cost=Decimal(str(summary['cost_usd']))
        shown=client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        budget=shown['ordinary_layout']['budget']
        authorization=json.loads((run/'ordinary_layout_budget'/job_id/'revalidation_capacity_v1/authorization.json').read_bytes())
        assert authorization['missing_pages']==[5,6,7]
        assert Decimal(budget['cap_usd'])-Decimal(budget['translation_cost_usd'])-Decimal(budget['prior_layout_cost_usd'])==Decimal('3.444')
        assert Decimal(shown['layout_costs']['cost_usd'])==old_cost+new_cost
        assert shown['layout_costs']['operations']==2
        download=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert download.status_code==200 and sha256(download.content).hexdigest()==shown['delivery']['sha256']
        saved=client.post('/api/translation/save-row',json={'mode':'shadow','workspace_id':'fictional','job_id':job_id,
            'baseline_id':shown['ordinary_layout']['baseline_id'],'expected_delivery_generation':shown['delivery']['generation'],
            'form_values':{**shown['result']['save_seed'],'rate_per_word':'.027','expected_total_mode':'auto'}})
        assert saved.status_code==200,saved.text
        translation_cost=Decimal(str(jobs.get_job(job_id)['result']['save_seed']['api_cost']))
        assert Decimal(str(saved.json()['normalized_payload']['api_cost']))==translation_cost+old_cost+new_cost
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        assert sent==[3,4,5,6,7]
        after_id=_start(client,source,output,'EN',start=3,end=7,image_mode='off',page_breaks=True,resume=True)
        _wait(jobs,after_id)
        assert client.post(f'/api/translation/jobs/{after_id}/layout/recover'+scope).status_code==200
        after=_wait(jobs,after_id)
        assert after['result']['automatic_layout']['reused_durable_candidate']
        assert client.get(f'/api/translation/jobs/{after_id}/artifact/output_docx'+scope).content==download.content
        assert sent==[3,4,5,6,7] and len(translation_sdk.requests)==5
        assert all(p.read_bytes()==data for p,data in protected.items())


@pytest.mark.parametrize('original_tokens', [8000,32000])
def test_completed_historical_capacity_lineage_precedes_new_direct_eligibility(tmp_path,monkeypatch,original_tokens):
    from datetime import date
    from legalpdf_translate import ordinary_auto_layout as automatic
    from legalpdf_translate import ordinary_layout_accounting as accounting
    from legalpdf_translate.accounting_policy import OrdinaryAccountingPolicy
    from legalpdf_translate.ordinary_layout_contracts import LayoutSuggestionPolicy
    from tests.test_ordinary_auto_layout_recovery import _success_layout_provider
    source,output=tmp_path/'source.pdf',tmp_path/'output'
    output.mkdir(); _source(source,('digital',)*2)
    app,jobs,translations,requests=_app(tmp_path,monkeypatch,
        ('English first body.\nFooter contact.','English second body.\nFinal unchanged.'),(1,2))
    scope='?mode=shadow&workspace=fictional'
    with TestClient(app) as client:
        with monkeypatch.context() as old:
            normalize=manager_module.normalize_proposals
            old.setattr(manager_module,'normalize_proposals',lambda *args: fail('page_break_requires_flow'))
            if original_tokens==8000:
                args=accounting.layout_accounting_policy().accounting_arguments(today=date(2026,10,9))
                args['dispatch_limits']['openai:layout_suggestion:gpt-5.2']['max_output_tokens']=8000
                catalog=OrdinaryAccountingPolicy.from_mapping(pricing=args['pricing_snapshot'],limits=args['dispatch_limits'])
                catalog=OrdinaryAccountingPolicy(catalog._pricing_json,catalog._limits_json,date(2026,10,9))
                old.setattr(accounting,'layout_accounting_policy',lambda: catalog)
                old.setattr(accounting,'PAGE_CEILING',Decimal('.812'))
                old.setattr(accounting.OrdinaryLayoutAccounting,'policy',lambda self,job: LayoutSuggestionPolicy(
                    'gpt-5.2','.812','1.624',max_output_tokens=8000,timeout_seconds=240.0))
                existing=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
                existing.suggestion_policy=lambda job: LayoutSuggestionPolicy(
                    'gpt-5.2','.812','1.624',max_output_tokens=8000,timeout_seconds=240.0)
            original=_start(client,source,output,'EN',start=1,end=2,image_mode='off',page_breaks=True)
            first=_wait(jobs,original)
        assert first['result']['automatic_layout']['status']=='raw_fallback'
        assert len(requests)==1 and requests[0]['max_output_tokens']==original_tokens,first['result']['automatic_layout']
        run=Path(first['result']['run_dir']); root=run/'ordinary_auto_layout'
        manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        manager.suggestion_policy=app.state.ordinary_layouts._accounting.policy
        manager.provider_factory=_success_layout_provider(app,requests)
        # Produce an authentic pre-existing capacity candidate with the old
        # selector, then exercise the new selector without changing evidence.
        with monkeypatch.context() as legacy:
            if original_tokens==32000:
                legacy.setattr(automatic,'_direct_revalidation',lambda *args: False)
            assert client.post(f'/api/translation/jobs/{original}/layout/recover'+scope).status_code==200
            completed=_wait(jobs,original)
        assert completed['result']['automatic_layout']['status']=='automatic_unreviewed',completed['result']['automatic_layout']
        capacity=root/'recoveries/layout_capacity_v2'
        candidate=(capacity/'candidate.json').read_bytes()
        assert not (root/'recoveries/layout_direct_revalidation_v1/intent.json').exists()
        downloaded=client.get(f'/api/translation/jobs/{original}/artifact/output_docx'+scope).content
        after=_start(client,source,output,'EN',start=1,end=2,image_mode='off',page_breaks=True,resume=True)
        _wait(jobs,after)
        assert client.post(f'/api/translation/jobs/{after}/layout/recover'+scope).status_code==200
        reused=_wait(jobs,after)
        assert reused['result']['automatic_layout']['reused_durable_candidate']
        assert client.get(f'/api/translation/jobs/{after}/artifact/output_docx'+scope).content==downloaded
        assert (capacity/'candidate.json').read_bytes()==candidate
        assert len(requests)==3 and len(translations.requests)==2
        assert not (root/'recoveries/layout_direct_revalidation_v1/intent.json').exists()
