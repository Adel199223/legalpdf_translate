"""Completed paid proposals are revalidated locally; only unsent pages dispatch."""
from decimal import Decimal
import json
from pathlib import Path
from types import SimpleNamespace
from threading import Event

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_layout_manager as manager_module
from legalpdf_translate.ordinary_layout_contracts import fail
from legalpdf_translate.ordinary_layout_service import _read
from legalpdf_translate.openai_client import OpenAIResponsesClient
from tests.test_ordinary_auto_layout_recovery import offline
from tests.test_ordinary_auto_layout_workflow import _app, _source, _start, _wait, _proposal


@pytest.mark.parametrize("resume,cancel", [(False,False), (True,False), (False,True)])
def test_retained_page_continuation_single_missing_request_download_save_and_reentry(tmp_path, monkeypatch, resume, cancel):
    source, output = tmp_path / 'source.pdf', tmp_path / 'output'
    output.mkdir()
    _source(source, ('digital', 'digital'))
    app, jobs, translations, initial_requests = _app(tmp_path, monkeypatch,
        ('French first page.', 'French second page.'), (1, 2), failed_page=1, failure='incomplete')
    scope = '?mode=shadow&workspace=fictional'
    paid = []
    entered, release = Event(), Event()
    with TestClient(app) as client:
        original = _start(client, source, output, 'FR', start=1, end=2, image_mode='off', page_breaks=True)
        first = _wait(jobs, original)
        assert first['diagnostics']['layout_recovery_quote']['max_page_cost_usd'] == '1.148'
        listed = jobs.list_jobs(runtime_mode='shadow',workspace_id='fictional')[0]
        assert listed['diagnostics']['layout_recovery_quote']['available']
        with monkeypatch.context() as expired:
            from legalpdf_translate import ordinary_layout_accounting
            expired.setattr(ordinary_layout_accounting, 'verified_page_ceiling', lambda: fail('pricing_reference_expired'))
            assert jobs.get_job(original)['diagnostics']['layout_recovery_quote']['available'] is False
        run = Path(first['result']['run_dir'])
        manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, 'shadow', 'fictional')
        def provider(job, policy):
            def create(**request):
                page = json.loads(request['input'][0]['content'][0]['text'])['page_number']
                paid.append(page)
                if page == 2 and cancel:
                    entered.set()
                    assert release.wait(20)
                view = manager.service.state(job.job_id)['review']
                proposal = _proposal(view, page)
                breaks = {p['id'] for p in view['paragraphs'] if p['has_page_break']}
                for p in proposal['paragraphs']:
                    if p['paragraph_id'] in breaks:
                        p.update(role='body', heading_level=0, heading_size_pt=None, bold=False,
                            italic=False, underline=False, emphasis=[], alignment='inherit',
                            space_before_pt=0, space_after_pt=0)
                for b in proposal['bands']:
                    for g in b.get('groups', []):
                        if set(g['paragraph_ids']) & breaks:
                            g['panel'] = False
                return SimpleNamespace(id=f'fictional-retained-{page}', model=policy.model,
                    status='completed', service_tier='default', output=[], output_text=json.dumps(proposal),
                    usage={'input_tokens':80,'output_tokens':60,'total_tokens':140,
                        'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}})
            return OpenAIResponsesClient(model=policy.model, sdk_client=SimpleNamespace(
                base_url='https://api.openai.com/v1/', responses=SimpleNamespace(create=create)),
                max_transport_retries=0, pre_call_jitter_seconds=0)
        manager.provider_factory = provider
        normalize = manager_module.normalize_proposals
        def old_spacing_guard(snapshot, view, proposals):
            if proposals[0]['page_number'] == 1:
                fail('page_break_requires_flow')
            return normalize(snapshot, view, proposals)
        with monkeypatch.context() as old:
            old.setattr(manager_module, 'normalize_proposals', old_spacing_guard)
            assert client.post(f'/api/translation/jobs/{original}/layout/recover'+scope).status_code == 200
            failed = _wait(jobs, original)
        assert failed['result']['automatic_layout']['status'] == 'raw_fallback'
        assert paid == [1]
        prior_root = run / 'ordinary_auto_layout/recoveries/layout_capacity_v2'
        pointer = json.loads((prior_root/'operation.json').read_bytes())
        prior_op = manager.service.root / pointer['origin_job_id'] / 'baselines' / pointer['baseline_id'] / 'suggestions' / pointer['operation_nonce']
        protected = {p:p.read_bytes() for p in prior_op.rglob('*') if p.is_file() and p.suffix != '.lock'}
        prior_cost = Decimal(str(_read(prior_op/'accounting_summary.json')['cost_usd']))
        if not resume:
            # A lost/changed response and unknown billing both stop before a
            # new operation or send, even after a valid SDK-completed page.
            for changed_path, invalid in ((prior_op/'page-0001.response.json', b'{}'),
                (prior_op/'accounting_summary.json', b'{}')):
                original_bytes = changed_path.read_bytes()
                changed_path.write_bytes(invalid)
                assert client.post(f'/api/translation/jobs/{original}/layout/recover'+scope).status_code == 200
                held = _wait(jobs, original)
                assert held['result']['automatic_layout']['status'] == 'raw_fallback'
                assert paid == [1]
                changed_path.write_bytes(original_bytes)
        old_pointer = json.loads((run/'ordinary_auto_layout/operation.json').read_bytes())
        old_op = manager.service.root / old_pointer['origin_job_id'] / 'baselines' / old_pointer['baseline_id'] / 'suggestions' / old_pointer['operation_nonce']
        old_cost = Decimal(str(_read(old_op/'accounting_summary.json')['cost_usd']))
        job_id = original
        if resume:
            job_id = _start(client, source, output, 'FR', start=1, end=2, image_mode='off', page_breaks=True, resume=True)
            _wait(jobs, job_id)
        assert len(translations.requests) == 2
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        if cancel:
            assert entered.wait(20)
            assert client.post(f'/api/translation/jobs/{job_id}/cancel'+scope).status_code == 200
            release.set()
            result = _wait(jobs,job_id)
            assert result['result']['automatic_layout']['status'] == 'raw_fallback'
            assert paid == [1,2]
            assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
            _wait(jobs,job_id)
            assert paid == [1,2] and len(translations.requests) == 2
            assert all(p.read_bytes() == raw for p,raw in protected.items())
            return
        result = _wait(jobs, job_id)
        assert result['result']['automatic_layout']['status'] == 'automatic_unreviewed', result['result']['automatic_layout']
        assert paid == [1, 2] and len(translations.requests) == 2
        new_root = run/'ordinary_auto_layout/recoveries/layout_revalidation_v1'
        new_pointer = json.loads((new_root/'operation.json').read_bytes())
        new_op = manager.service.root / new_pointer['origin_job_id'] / 'baselines' / new_pointer['baseline_id'] / 'suggestions' / new_pointer['operation_nonce']
        assert (new_op/'page-0001.response.json').read_bytes() == protected[prior_op/'page-0001.response.json']
        assert _read(new_op/'page-0001.retained.json')['locally_revalidated']
        assert _read(new_op/'accounting_summary.json')['provider_dispatch_count'] == 1
        from legalpdf_translate.ordinary_auto_layout import _verified_retained_pages
        from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError
        retained_origins = json.loads((new_root/'intent.json').read_bytes())['retained_pages']
        retained_marker = new_op/'page-0001.retained.json'
        marker_bytes = retained_marker.read_bytes()
        retained_marker.write_bytes(b'{}')
        with pytest.raises(OrdinaryLayoutError): _verified_retained_pages(new_op,retained_origins)
        retained_marker.write_bytes(marker_bytes)
        extra = new_op/'page-0002.retained.json';extra.write_bytes(marker_bytes)
        with pytest.raises(OrdinaryLayoutError): _verified_retained_pages(new_op,retained_origins)
        extra.unlink()
        # Lost final result after all paid requests settle reconstructs locally
        # from bound retained provenance plus the one new-page event.
        from legalpdf_translate.ordinary_auto_layout import _recover_settled_result
        settled_result = _read(new_op/'result.json')
        (new_op/'result.json').unlink()
        _recover_settled_result(manager,new_pointer,[1,2])
        assert _read(new_op/'result.json') == settled_result
        assert paid == [1,2]
        new_cost = Decimal(str(_read(new_op/'accounting_summary.json')['cost_usd']))
        shown = client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        assert Decimal(shown['layout_costs']['cost_usd']) == old_cost + prior_cost + new_cost
        downloaded = client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert downloaded.status_code == 200
        saved = client.post('/api/translation/save-row',json={'mode':'shadow','workspace_id':'fictional','job_id':job_id,
            'baseline_id':shown['ordinary_layout']['baseline_id'],'expected_delivery_generation':shown['delivery']['generation'],
            'form_values':{**shown['result']['save_seed'],'rate_per_word':'.027','expected_total_mode':'auto'}})
        assert saved.status_code == 200, saved.text
        translation_cost = Decimal(str(jobs.get_job(job_id)['result']['save_seed']['api_cost']))
        assert Decimal(str(saved.json()['normalized_payload']['api_cost'])) == translation_cost + old_cost + prior_cost + new_cost
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        assert paid == [1, 2]
        assert all(p.read_bytes() == raw for p,raw in protected.items())
