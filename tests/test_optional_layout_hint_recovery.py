"""Unsupported optional column decoration retains text and review evidence."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from legalpdf_translate.ordinary_layout_contracts import proposal_source_evidence, OrdinaryLayoutError
from legalpdf_translate.ordinary_auto_layout import _source_layout_review
from tests.test_ordinary_source_evidence import fixture


def column_rule():
    s, v, p = fixture()
    s['paragraphs'][0]['tokens'] = [{'kind': 't', 'text': '____'}]
    p['bands'] = [{'kind': 'columns', 'cells': [
        {'groups': [{'paragraph_ids': ['p000001'], 'panel': False}]}]}]
    p['source_layout_evidence'] = [{'kind': 'decorative_rule',
        'paragraph_ids': ['p000001'], 'bbox': [.1, .4, .9, .41]}]
    return s, v, p


def test_only_column_eligibility_is_quarantined_with_durable_review():
    s, v, p = column_rule()
    before = deepcopy((s, v, p))
    evidence = proposal_source_evidence(s, v, p)
    assert (s, v, p) == before
    assert evidence['layout'] == []
    assert evidence['normalization']['rejected_hints'] == [{
        'index': 0, 'kind': 'decorative_rule', 'paragraph_ids': ['p000001'],
        'reason': 'decorative_rule_requires_plain_flow'}]
    candidate = SimpleNamespace(source_map={'source_evidence': {'pages': [evidence]}})
    review = _source_layout_review(candidate)
    assert review['source_layout_review_required'] is True
    assert review['source_layout_rejected_hints'][0]['page_number'] == 1
    assert _source_layout_review(SimpleNamespace(source_map={})) == {}


@pytest.mark.parametrize('unsafe', ['control', 'numbering', 'field', 'mixed', 'signature', 'panel', 'partition', 'bbox', 'id'])
def test_column_membership_does_not_hide_fatal_defects(unsafe):
    s, v, p = column_rule()
    raw = s['paragraphs'][0]
    if unsafe == 'control': raw['tokens'].append({'kind': 'tab', 'text': '\t'})
    elif unsafe == 'numbering': raw['has_numbering'] = True
    elif unsafe == 'field': raw['has_field'] = True
    elif unsafe == 'mixed': raw['tokens'][0]['text'] = 'name ____'
    elif unsafe == 'signature': p['paragraphs'][0]['role'] = 'signature'
    elif unsafe == 'panel': p['bands'][0]['cells'][0]['groups'][0]['panel'] = True
    elif unsafe == 'partition': p['paragraph_partitions'] = [{'paragraph_id': 'p000001'}]
    elif unsafe == 'bbox': p['source_layout_evidence'][0]['bbox'][0] = True
    else: p['source_layout_evidence'][0]['paragraph_ids'] = ['p999999']
    with pytest.raises(OrdinaryLayoutError): proposal_source_evidence(s, v, p)


def test_valid_terminal_footer_remains_accepted_after_rejected_rule():
    s, v, p = column_rule()
    s['paragraphs'].append({'id': 'p000002', 'tokens': [{'kind': 't', 'text': 'Page 1'}]})
    v['paragraphs'].append({'id': 'p000002', 'text': 'Page 1'})
    v['decisions']['paragraphs'].append({'paragraph_id': 'p000002', 'regions': [{'page_number': 1, 'bbox_px': [1, 80, 20, 90]}]})
    p['paragraphs'].append({'paragraph_id': 'p000002', 'role': 'source_folio'})
    p['bands'].append({'kind': 'flow', 'groups': [{'paragraph_ids': ['p000002'], 'panel': False}]})
    footer = {'kind': 'source_footer', 'paragraph_ids': ['p000002'], 'bbox': [.1, .9, .9, .98]}
    p['source_layout_evidence'].append(footer)
    assert proposal_source_evidence(s, v, p)['layout'] == [footer]


def test_settled_invalid_hint_recovers_without_dispatch_and_reuses_warning(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from tests import test_ordinary_auto_layout_workflow as flow
    from legalpdf_translate import ordinary_layout_manager as module
    from legalpdf_translate.ordinary_layout_contracts import PROPOSAL_VERSION_V3, fail
    original = flow._proposal
    def proposal(view, page, columns=0):
        p = original(view, page, columns)
        ids = [row['paragraph_id'] for row in p['paragraphs']]
        p['paragraphs'][0].update(role='body', heading_level=0, heading_size_pt=None)
        p.update(version=PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[],
                 source_layout_evidence=[{'kind':'decorative_rule','paragraph_ids':[ids[0]],'bbox':[.1,.4,.9,.41]}])
        p['bands'] = [{'kind':'columns','widths_pct':[50,50],'gutter_pt':12,'cells':[
            {'groups':[{'paragraph_ids':[ids[0]],'panel':False}]},
            {'groups':[{'paragraph_ids':ids[1:],'panel':False}]}]}]
        return p
    monkeypatch.setattr(flow, '_proposal', proposal)
    source = tmp_path/'source.pdf'; flow._source(source, ('digital',))
    output = tmp_path/'output'; output.mkdir()
    app, jobs, sdk, requests = flow._app(tmp_path, monkeypatch, ('____\nA fictional body paragraph.',), (1,))
    scope = '?mode=shadow&workspace=fictional'
    with TestClient(app) as client:
        with monkeypatch.context() as old:
            old.setattr(module, 'normalize_proposals', lambda *args: fail('invalid_source_layout_evidence'))
            job_id = flow._start(client, source, output, 'EN', start=1, end=1, image_mode='off')
            first = flow._wait(jobs, job_id)
        assert first['result']['automatic_layout']['status'] == 'raw_fallback'
        assert len(requests) == len(sdk.requests) == 1
        layout = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        settled_cost = layout.layout_costs(job_id)['known_cost_usd']
        provider = layout.provider_factory
        def denied(*args):
            result = provider(*args)
            result._client.responses.create = lambda **kwargs: pytest.fail('retained recovery dispatched a provider')
            return result
        layout.provider_factory = denied
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        final = flow._wait(jobs, job_id)['result']['automatic_layout']
        assert final['status'] == 'automatic_unreviewed', final
        assert final['source_layout_review_required'] is True
        assert len(final['source_layout_rejected_hints']) == 1
        from pathlib import Path
        from legalpdf_translate.ordinary_auto_layout import _read_record, _recover_settled_result, frozen_automatic_layout_policy
        from legalpdf_translate.ordinary_layout_service import _read
        run = Path(flow._wait(jobs, job_id)['result']['run_dir'])
        pointer = _read_record(run/'ordinary_auto_layout/recoveries/layout_direct_revalidation_v1/operation.json')
        operation = layout.service.root/pointer['origin_job_id']/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        original_result = _read(operation/'result.json')
        (operation/'result.json').unlink()
        (operation/'source_evidence.json').unlink()
        with pytest.raises(OrdinaryLayoutError, match='optional_hint_recovery_requires_current_policy'):
            _recover_settled_result(layout, pointer, [1], policy_fingerprint='0'*64)
        assert not (operation/'result.json').exists()
        _recover_settled_result(layout, pointer, [1], policy_fingerprint=frozen_automatic_layout_policy().split(':')[1])
        assert _read(operation/'result.json') == original_result
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        repeated = flow._wait(jobs, job_id)['result']['automatic_layout']
        assert repeated['sha256'] == final['sha256']
        assert repeated['source_layout_rejected_hints'] == final['source_layout_rejected_hints']
        assert repeated['layout_costs'] == final['layout_costs']
        from decimal import Decimal
        assert Decimal(final['layout_costs']['known_cost_usd']) == Decimal(settled_cost)
        assert final['layout_costs']['complete'] is True
        assert len(requests) == len(sdk.requests) == 1
