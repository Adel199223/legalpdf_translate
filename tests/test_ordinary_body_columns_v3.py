"""Fictional, exact-order generated body-column fallback and legacy replay."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate.ordinary_layout_manager import INSTRUCTIONS
from tests.test_saved_docx_layout import document_bytes
from tests.test_ordinary_layout_columns_rows import grid


def body_case(columns=2, mixed=False):
    snapshot = model.inspect_docx(document_bytes(tuple(f'Fictional item {i} tail' for i in range(10))), 'EN')
    pages = [{'page_number':1,'width_px':100,'height_px':100,'image_sha256':'a'*64}]
    decisions = model.default_decisions(snapshot, pages)
    for row in decisions['paragraphs']:
        row['regions'] = [{'page_number':1,'bbox_px':[5,5,95,95]}]
    view = {'paragraphs':snapshot['paragraphs'],'pages':pages,'decisions':decisions}
    choices = [{k:deepcopy(v) for k,v in row.items() if k not in {'regions','unmapped_reason'}}
               | {'bbox':[.1,.1,.9,.9]} for row in decisions['paragraphs']]
    ids = [row['paragraph_id'] for row in choices]
    if mixed:
        choices[2]['role'] = 'reference'
    groups = ([ids[1:9][i] for i in (0,2,4,5,6,7)], [ids[1:9][i] for i in (1,3)]) if columns == 2 else [ids[1:9][i::columns] for i in range(columns)]
    band = {'kind':'columns','widths_pct':[65,35] if columns == 2 else [34,33,33], 'gutter_pt':12,
            'cells':[{'groups':[{'paragraph_ids':owned, 'panel':False}]} for owned in groups]}
    proposal = {'version':c.PROPOSAL_VERSION_V3,'page_number':1,'paragraphs':choices,
        'bands':[{'kind':'flow','groups':[{'paragraph_ids':ids[:1],'panel':False}]}, band,
                 {'kind':'flow','groups':[{'paragraph_ids':ids[9:],'panel':False}]}],
        'paragraph_partitions':[], 'source_coverage_findings':[], 'source_layout_evidence':[]}
    return snapshot, view, proposal


@pytest.mark.parametrize('columns,mixed', [(2,False),(2,True),(3,False),(3,True)])
def test_v3_restores_only_safe_band_and_preserves_every_choice_and_input(columns, mixed):
    snapshot, view, proposal = body_case(columns, mixed)
    before = c.encode([snapshot,view,proposal])
    result = c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)
    ids = c.page_ids(view,1)
    expected = deepcopy(view['decisions'])
    expected['bands'] = deepcopy(proposal['bands'])
    expected['bands'][1] = {'kind':'flow','groups':[{'paragraph_ids':ids[1:9],'panel':False}]}
    assert result['bands'] == expected['bands']
    # Source boxes and all optional paragraph styles survive the fallback.
    for choice, row in zip(proposal['paragraphs'], result['paragraphs']):
        assert {k:v for k,v in row.items() if k not in {'regions','unmapped_reason'}} == {k:v for k,v in choice.items() if k != 'bbox'}
        assert row['regions'] == [{'page_number':1,'bbox_px':[10.,10.,90.,90.]}]
    model.validate_decisions(snapshot,view['pages'],result)
    evidence = c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V3)
    assert evidence['metadata_band_normalization']['rejected_bands'] == [{'index':1,'paragraph_ids':ids[1:9],
        'reason':'generated_plain_columns_restored_to_text_order'}]
    assert evidence['metadata_band_normalization']['canonical_proposal_sha256'] == c.digest(c.encode(proposal))
    assert evidence['source_coverage_verified'] is False
    assert c.source_evidence_review_fields([evidence])['source_layout_review_required'] is True
    assert c.encode(c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)) == c.encode(result)
    assert c.encode([snapshot,view,proposal]) == before


@pytest.mark.parametrize('version', [None,c.BAND_NORMALIZATION_V1,c.BAND_NORMALIZATION_V2])
def test_body_interleave_keeps_historical_failure(version):
    snapshot, view, proposal = body_case()
    with pytest.raises(c.OrdinaryLayoutError, match='proposal_coverage'):
        c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=version)


@pytest.mark.parametrize('fault', ['missing','extra','duplicate','choices_order','choice_key','band_key',
    'cell_key','group_key','empty','panel','width_boolean','width_nan','width_sum','gutter_nan','gutter_range',
    'other_role','partition','field','numbering','numPr','break','tab','line_break','control','cross_interval',
    'finding','footer'])
def test_v3_does_not_rescue_unsafe_or_unrelated_malformed_proposals(fault):
    snapshot, view, proposal = body_case()
    band = proposal['bands'][1]
    group = band['cells'][0]['groups'][0]
    row = snapshot['paragraphs'][1]
    if fault == 'missing': group['paragraph_ids'].pop()
    elif fault == 'extra': group['paragraph_ids'].append('p999999')
    elif fault == 'duplicate': group['paragraph_ids'][1] = group['paragraph_ids'][0]
    elif fault == 'choices_order': proposal['paragraphs'][1:3] = proposal['paragraphs'][1:3][::-1]
    elif fault == 'choice_key': proposal['paragraphs'][1]['invented'] = True
    elif fault == 'band_key': band['invented'] = True
    elif fault == 'cell_key': band['cells'][0]['invented'] = True
    elif fault == 'group_key': group['invented'] = True
    elif fault == 'empty': group['paragraph_ids'] = []
    elif fault == 'panel': group['panel'] = True
    elif fault == 'width_boolean': band['widths_pct'][0] = True
    elif fault == 'width_nan': band['widths_pct'][0] = float('nan')
    elif fault == 'width_sum': band['widths_pct'] = [40,40]
    elif fault == 'gutter_nan': band['gutter_pt'] = float('nan')
    elif fault == 'gutter_range': band['gutter_pt'] = 37
    elif fault == 'other_role': proposal['paragraphs'][1]['role'] = 'signature'
    elif fault == 'partition': proposal['paragraph_partitions'] = [{'paragraph_id':row['id'],'split_before':['tail']}]
    elif fault == 'field': row['has_field'] = True
    elif fault == 'numbering': row['has_numbering'] = True
    elif fault == 'numPr': row['ppr_xml'] = '<w:numPr/>'
    elif fault == 'break': row['has_page_break'] = True
    elif fault == 'tab': row['tokens'].append({'kind':'tab','text':'\t'})
    elif fault == 'line_break': row['tokens'].append({'kind':'line_break','text':'\n'})
    elif fault == 'control': row['tokens'][0]['text'] += '\u202e'
    elif fault == 'cross_interval':
        group['paragraph_ids'][0],proposal['bands'][0]['groups'][0]['paragraph_ids'][0] = (
            proposal['bands'][0]['groups'][0]['paragraph_ids'][0],group['paragraph_ids'][0])
    elif fault == 'finding': proposal['source_coverage_findings'] = [{'invalid':True}]
    elif fault == 'footer': proposal['source_layout_evidence'] = [{'kind':'source_footer','paragraph_ids':[row['id']], 'bbox':[.1,.9,.9,.99]}]
    with pytest.raises(c.OrdinaryLayoutError):
        c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)


def test_ordered_columns_and_existing_geometric_rows_keep_exact_derived_bands():
    snapshot,view,proposal = body_case()
    ids = c.page_ids(view,1)[1:9]
    proposal['bands'][1]['cells'][0]['groups'][0]['paragraph_ids'] = ids[:4]
    proposal['bands'][1]['cells'][1]['groups'][0]['paragraph_ids'] = ids[4:]
    for version in [c.BAND_NORMALIZATION_V2,c.BAND_NORMALIZATION_V3]:
        assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=version)['bands'] == proposal['bands']
    _, bands, boxes = grid(2,2)
    # The grid owns the first eight immutable IDs, followed by untouched flow.
    proposal['bands'] = bands + [{'kind':'flow','groups':[{'paragraph_ids':c.page_ids(view,1)[8:],'panel':False}]}]
    for choice,box in zip(proposal['paragraphs'],boxes): choice['bbox'] = box['bbox']
    old = c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V2)
    fresh = c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)
    assert fresh == old and len(fresh['bands']) == 3


def test_v3_inherits_reversed_flow_and_terminal_footer_hint_rules():
    snapshot,view,proposal = body_case()
    ids = c.page_ids(view,1)
    proposal['bands'] = [{'kind':'flow','groups':[{'paragraph_ids':ids[::-1],'panel':False}]}]
    proposal['source_layout_evidence'] = [{'kind':'source_footer','paragraph_ids':ids[::-1],'bbox':[.1,.9,.9,.99]}]
    old = c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V2)
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3) == old
    evidence = c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V3)
    assert evidence['normalization']['rejected_hints'][0]['reason'] == 'reordered_source_footer_hint_kept_in_flow'
    assert evidence['metadata_band_normalization']['rejected_bands'][0]['reason'] == 'generated_plain_flow_restored_to_text_order'


def test_existing_metadata_fallback_reason_stays_exact_and_source_findings_survive():
    snapshot,view,proposal = body_case()
    for choice in proposal['paragraphs'][1:9]: choice['role']='reference'
    proposal['source_coverage_findings']=[{'kind':'missing_readable_literal','literal':'F',
        'source_bbox':[.1,.1,.2,.2],'insertion_context':{'paragraph_id':proposal['paragraphs'][1]['paragraph_id'],'position':'before'}}]
    before=c.encode(proposal)
    old=c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V2)
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)==old
    old_evidence=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V2)
    fresh=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V3)
    assert fresh['findings']==old_evidence['findings'] and len(fresh['findings'])==1
    assert fresh['metadata_band_normalization']['rejected_bands']==old_evidence['metadata_band_normalization']['rejected_bands']
    assert fresh['metadata_band_normalization']['rejected_bands'][0]['reason']=='metadata_columns_reordered_as_flow'
    assert c.encode(proposal)==before


def test_genuine_nine_prechange_policy_maps_requests_decisions_and_evidence_replay_exact():
    history = json.loads((Path(__file__).parent/'fixtures/layout_body_columns_prechange_0af.json').read_bytes())
    for item,result in zip(history['maps'],history['results']):
        policy, fp = item['policy'],item['policy'].split(':',1)[1]
        assert auto._band_normalization_version(fp) == item['band_normalization_version']
        assert auto._source_normalization_version(fp) == item['source_hint_normalization_version']
        assert (policy in auto._metadata_normalization_policies()) == item['metadata_and_emphasis_policy_member']
        assert (policy in auto._source_folio_policies()) == item['source_folio_policy_member']
        assert (policy in {auto.frozen_automatic_layout_policy(),auto._body_columns_v3_policy(),auto._source_bound_v4_policy()}) == item['numeric_run_ltr_v3_evidence_emitted_when_source_evidence_present']
        assert INSTRUCTIONS == history['request']['instructions']
        assert c.proposal_schema(1,c.page_ids(history['view'],1)) == history['request']['schema']
        assert sha256(c.encode(history['request'])).hexdigest() == result['request_sha256']
        assert c.digest(c.encode(c.normalize_proposals(history['snapshot'],history['view'],[history['proposal']],**result['kwargs']))) == result['derived_sha256']
        assert c.digest(c.encode(c.proposal_source_evidence(history['snapshot'],history['view'],history['proposal'],**result['kwargs']))) == result['evidence_sha256']
    assert len(history['maps']) == 9
    assert auto._source_bound_v4_policy() == 'source_image_unreviewed_v1:bb15bab385eb54f074c00da06fdadfe607c48e2d1933532f590160d80f54ae01'
    assert auto._body_columns_v3_policy() == 'source_image_unreviewed_v1:1e4a11e243d8a6a27dd7fa30c54e4475dfae4a3f74a68e789eef1be15362ab4b'
    assert auto._clock_direction_policy() == 'source_image_unreviewed_v1:d3c89ef63893696d339f350c00500a4cd865f594ce56ed9a45472bb350b5e0b7'
    assert auto._band_normalization_version(auto._clock_direction_policy().split(':',1)[1]) == c.BAND_NORMALIZATION_V3
    assert auto._heading_columns_v4_policy() == 'source_image_unreviewed_v1:a1f0b680bfd07d5c2ca3a7d11d47939c96f8639271a38764897fdeabd346f81a'
    assert auto._band_normalization_version(auto._heading_columns_v4_policy().split(':',1)[1]) == c.BAND_NORMALIZATION_V4
