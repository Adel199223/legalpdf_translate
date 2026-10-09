"""Generated geometric column rows preserve complete immutable paragraph order."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_layout_manager as manager_module
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate.ordinary_layout_contracts import (
    _canonical_columns_rows, normalize_proposals, encode, fail, PROPOSAL_VERSION_V2,
)
from legalpdf_translate.ordinary_layout_service import _read
from legalpdf_translate.openai_client import OpenAIResponsesClient
from tests.test_saved_docx_layout import document_bytes
from tests.test_ordinary_auto_layout_recovery import offline
from tests.test_ordinary_auto_layout_workflow import _app, _source, _start, _wait, _proposal


def grid(columns=2, rows=2):
    ids = [f'p{i:06d}' for i in range(1, columns * rows * 2 + 1)]
    cells = [{'groups': []} for _ in range(columns)]
    choices = []
    for row in range(rows):
        for column in range(columns):
            start = (row * columns + column) * 2
            owned = ids[start:start + 2]
            cells[column]['groups'].append({'paragraph_ids': owned, 'panel': row == rows-1})
            for pid in owned:
                choices.append({'paragraph_id': pid,
                    'bbox': [.05 + column/columns, .05 + row/rows,
                             .05 + (column+.7)/columns, .05 + (row+.4)/rows]})
    widths = [50, 50] if columns == 2 else [34, 33, 33]
    return ids, [{'kind': 'columns', 'widths_pct': widths, 'gutter_pt': 12, 'cells': cells}], choices


@pytest.mark.parametrize('columns,rows', [(2,2),(2,3),(3,2),(3,3)])
def test_whole_geometric_rows_copy_groups_panels_widths_and_order(columns, rows):
    ids, bands, choices = grid(columns, rows)
    original = deepcopy(bands)
    result = _canonical_columns_rows(bands, ids, choices)
    assert len(result) == rows
    assert bands == original
    assert [pid for band in result for cell in band['cells']
            for group in cell['groups'] for pid in group['paragraph_ids']] == ids
    for column in range(columns):
        assert [band['cells'][column]['groups'][0] for band in result] == original[0]['cells'][column]['groups']
    assert all(band['widths_pct'] == original[0]['widths_pct']
               and band['gutter_pt'] == original[0]['gutter_pt'] for band in result)
    assert _canonical_columns_rows(result, ids, choices) is result
    assert encode(_canonical_columns_rows(result, ids, choices)) == encode(result)


def test_touching_row_envelopes_do_not_overlap():
    ids, bands, choices = grid()
    choices[0]['bbox'][3] = choices[4]['bbox'][1]
    assert len(_canonical_columns_rows(bands, ids, choices)) == 2


@pytest.mark.parametrize('fault', ['null','overlap','reversed_rows','nonfinite','boolean',
    'reversed_box','ragged','empty','reversed_group','noncontiguous','duplicate','foreign','nonhashable'])
def test_ambiguous_or_incomplete_rows_are_not_repaired(fault):
    ids, bands, choices = grid()
    groups = bands[0]['cells'][0]['groups']
    if fault == 'null': choices[0]['bbox'] = None
    elif fault == 'overlap': choices[0]['bbox'][3] = .8
    elif fault == 'reversed_rows':
        for choice in choices: choice['bbox'][1], choice['bbox'][3] = 1-choice['bbox'][3], 1-choice['bbox'][1]
    elif fault == 'nonfinite': choices[0]['bbox'][1] = float('nan')
    elif fault == 'boolean': choices[0]['bbox'][1] = False
    elif fault == 'reversed_box': choices[0]['bbox'][2] = choices[0]['bbox'][0]
    elif fault == 'ragged': bands[0]['cells'][1]['groups'][0]['paragraph_ids'] += bands[0]['cells'][1]['groups'].pop()['paragraph_ids']
    elif fault == 'empty': groups[0]['paragraph_ids'] = []
    elif fault == 'reversed_group': groups[0]['paragraph_ids'].reverse()
    elif fault == 'noncontiguous': groups[0]['paragraph_ids'][1], groups[1]['paragraph_ids'][0] = groups[1]['paragraph_ids'][0], groups[0]['paragraph_ids'][1]
    elif fault == 'duplicate': groups[1]['paragraph_ids'][0] = groups[0]['paragraph_ids'][0]
    elif fault == 'foreign': groups[0]['paragraph_ids'][0] = 'p999999'
    elif fault == 'nonhashable': groups[0]['paragraph_ids'][0] = ['p000001']
    assert _canonical_columns_rows(bands, ids, choices) is bands


def test_generated_normalization_accepts_rows_but_manual_decisions_stay_strict():
    ids, bands, boxes = grid()
    snapshot = model.inspect_docx(document_bytes(tuple(f'Body paragraph {i}' for i in range(8))), 'EN')
    pages = [{'page_number':1, 'width_px':100, 'height_px':100, 'image_sha256':'a'*64}]
    decisions = model.default_decisions(snapshot, pages)
    for choice in decisions['paragraphs']:
        choice['regions'] = [{'page_number':1, 'bbox_px':[5,5,95,95]}]
    view = {'paragraphs':snapshot['paragraphs'], 'pages':pages, 'decisions':decisions}
    choices = [{k:v for k,v in choice.items() if k not in {'regions','unmapped_reason'}}
               | {'bbox':box['bbox']} for choice,box in zip(decisions['paragraphs'], boxes)]
    proposal = {'version':PROPOSAL_VERSION_V2, 'page_number':1,
                'paragraphs':choices, 'bands':bands, 'paragraph_partitions':[]}
    manual = deepcopy(decisions); manual['bands'] = deepcopy(bands)
    with pytest.raises(model.SavedDocxLayoutError): model.validate_decisions(snapshot, pages, manual)
    result = normalize_proposals(snapshot, view, [proposal])
    assert len(result['bands']) == 2
    assert proposal['bands'] == bands
    # Already ordered model replies keep their decisions byte-for-byte.
    ordered = deepcopy(proposal); ordered['bands'] = deepcopy(result['bands'])
    assert encode(normalize_proposals(snapshot, view, [ordered])) == encode(result)


def test_direct_coverage_eligibility_keeps_exact_policy_and_existing_lineage(tmp_path):
    from legalpdf_translate.ordinary_auto_layout import _direct_revalidation
    result = {'error_code':'ordinary_layout_proposal_coverage'}
    policy = {'max_output_tokens':32000, 'timeout_seconds':480.0}
    assert _direct_revalidation(tmp_path, result, policy)
    assert not _direct_revalidation(tmp_path, result, dict(policy, max_output_tokens=8000))
    assert not _direct_revalidation(tmp_path, result, dict(policy, timeout_seconds=479.0))
    assert not _direct_revalidation(tmp_path, {'error_code':'ordinary_layout_invalid_proposal'}, policy)
    capacity = tmp_path/'recoveries/layout_capacity_v2'
    capacity.mkdir(parents=True); (capacity/'candidate.json').write_text('{}')
    assert not _direct_revalidation(tmp_path, result, policy)


@pytest.mark.parametrize('resume', [None, False, True])
def test_settled_coverage_failure_retains_L1_and_sends_only_L2_then_Save(tmp_path, monkeypatch, resume):
    source, output = tmp_path/'source.pdf', tmp_path/'output'
    output.mkdir(); _source(source, ('digital','digital'))
    app, jobs, translation_sdk, _ = _app(tmp_path, monkeypatch,
        ('Title\nLeft first\nLeft second\nRight first\nRight second\nLeft lower\nPanel lower\nFooter',
         'Second page body\nSecond page footer'), (1,2))
    scope = '?mode=shadow&workspace=fictional'
    sent = []
    with TestClient(app) as client:
        manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        def provider(job, policy):
            def create(**request):
                page = json.loads(request['input'][0]['content'][0]['text'])['page_number']
                sent.append(page)
                value = _proposal(manager.service.state(job.job_id)['review'], page)
                value.update(version=PROPOSAL_VERSION_V2, paragraph_partitions=[])
                if page == 1:
                    choices = value['paragraphs']; ids = [p['paragraph_id'] for p in choices]
                    assert len(ids) == 8
                    for index, choice in enumerate(choices):
                        choice.update(bbox=[.1,.05,.9,.1] if index == 0 else [.1,.9,.9,.95])
                    for indices, box in [((1,2),[.1,.2,.4,.35]),((3,4),[.6,.2,.9,.35]),
                                         ((5,),[.1,.6,.4,.75]),((6,),[.6,.6,.9,.75])]:
                        for index in indices: choices[index]['bbox'] = box
                    value['bands'] = [
                        {'kind':'flow','groups':[{'paragraph_ids':ids[:1],'panel':False}]},
                        {'kind':'columns','widths_pct':[50,50],'gutter_pt':12,'cells':[
                            {'groups':[{'paragraph_ids':ids[1:3],'panel':False},{'paragraph_ids':ids[5:6],'panel':False}]},
                            {'groups':[{'paragraph_ids':ids[3:5],'panel':False},{'paragraph_ids':ids[6:7],'panel':True}]}]},
                        {'kind':'flow','groups':[{'paragraph_ids':ids[7:],'panel':False}]}]
                return SimpleNamespace(id=f'offline-column-{page}',model=policy.model,status='completed',
                    service_tier='default',output=[],output_text=json.dumps(value),usage={'input_tokens':80,
                    'output_tokens':60,'total_tokens':140,'input_tokens_details':{'cached_tokens':0},
                    'output_tokens_details':{'reasoning_tokens':0}})
            return OpenAIResponsesClient(model=policy.model,sdk_client=SimpleNamespace(
                base_url='https://api.openai.com/v1/',responses=SimpleNamespace(create=create)),
                max_transport_retries=0,pre_call_jitter_seconds=0)
        manager.provider_factory = provider
        normalize = manager_module.normalize_proposals
        def previous_guard(snapshot,view,proposals):
            if proposals[0]['page_number'] == 1: fail('proposal_coverage')
            return normalize(snapshot,view,proposals)
        if resume is None:
            # Fresh SDK completion also exercises the new generated-response
            # path, without a retained-replay-only success standing in for it.
            job_id = _start(client,source,output,'EN',start=1,end=2,image_mode='off',page_breaks=True)
            result = _wait(jobs,job_id)
            assert result['result']['automatic_layout']['status'] == 'automatic_unreviewed'
            assert sent == [1,2] and len(translation_sdk.requests) == 2
            shown = client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
            assert shown['layout_costs']['operations'] == 1
            download = client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
            assert sha256(download.content).hexdigest() == shown['delivery']['sha256']
            save = client.post('/api/translation/save-row',json={'job_id':job_id,
                'baseline_id':shown['ordinary_layout']['baseline_id'],'expected_delivery_generation':shown['delivery']['generation'],
                'form_values':{**shown['result']['save_seed'],'rate_per_word':'.027','expected_total_mode':'auto'}},
                headers={'X-LegalPDF-Runtime-Mode':'shadow','X-LegalPDF-Workspace-Id':'fictional'})
            assert save.status_code == 200, save.text
            assert Decimal(str(save.json()['normalized_payload']['api_cost'])) == Decimal(str(result['result']['save_seed']['api_cost'])) + Decimal(shown['layout_costs']['cost_usd'])
            return
        with monkeypatch.context() as previous:
            previous.setattr(manager_module,'normalize_proposals',previous_guard)
            original = _start(client,source,output,'EN',start=1,end=2,image_mode='off',page_breaks=True)
            first = _wait(jobs,original)
        assert first['result']['automatic_layout']['status'] == 'raw_fallback'
        assert sent == [1] and len(translation_sdk.requests) == 2
        root = Path(first['result']['run_dir'])/'ordinary_auto_layout'
        pointer = json.loads((root/'operation.json').read_bytes())
        old_op = manager.service.root/original/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        old_cost = Decimal(str(_read(old_op/'accounting_summary.json')['cost_usd']))
        protected = {p:p.read_bytes() for p in old_op.rglob('*') if p.is_file() and p.suffix != '.lock'}
        job_id = original
        if resume:
            job_id = _start(client,source,output,'EN',start=1,end=2,image_mode='off',page_breaks=True,resume=True)
            _wait(jobs,job_id)
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        result = _wait(jobs,job_id)
        assert result['result']['automatic_layout']['status'] == 'automatic_unreviewed', result['result']['automatic_layout']
        assert sent == [1,2] and len(translation_sdk.requests) == 2
        folder = root/'recoveries/layout_direct_revalidation_v1'
        identity = json.loads((folder/'intent.json').read_bytes())
        assert set(identity['retained_pages']) == {'1'} and 'revalidation_predecessor' not in identity
        pointer = json.loads((folder/'operation.json').read_bytes())
        new_op = manager.service.root/job_id/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        assert (new_op/'page-0001.response.json').read_bytes() == protected[old_op/'page-0001.response.json']
        summary = _read(new_op/'accounting_summary.json')
        assert summary['provider_dispatch_count'] == 1 and summary['in_flight_count'] == 0
        shown = client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        assert shown['layout_costs']['operations'] == 2
        layout_cost = old_cost + Decimal(str(summary['cost_usd']))
        assert Decimal(shown['layout_costs']['cost_usd']) == layout_cost
        download = client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert download.status_code == 200 and sha256(download.content).hexdigest() == shown['delivery']['sha256']
        save = client.post('/api/translation/save-row',json={'job_id':job_id,
            'baseline_id':shown['ordinary_layout']['baseline_id'],'expected_delivery_generation':shown['delivery']['generation'],
            'form_values':{**shown['result']['save_seed'],'rate_per_word':'.027','expected_total_mode':'auto'}},
            headers={'X-LegalPDF-Runtime-Mode':'shadow','X-LegalPDF-Workspace-Id':'fictional'})
        assert save.status_code == 200, save.text
        assert Decimal(str(save.json()['normalized_payload']['api_cost'])) == Decimal(str(result['result']['save_seed']['api_cost'])) + layout_cost
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code == 200
        assert sent == [1,2] and all(p.read_bytes() == data for p,data in protected.items())
