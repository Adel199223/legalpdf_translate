"""Fictional heading extension, strict exclusions and genuine D3 history."""
import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_auto_layout_artifacts as artifacts
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate.ordinary_layout_manager import INSTRUCTIONS
from tests.test_ordinary_body_columns_v3 import body_case

HISTORY=Path(__file__).parent/'fixtures/layout_heading_columns_prechange_edc.json'
OLD='source_image_unreviewed_v1:d3c89ef63893696d339f350c00500a4cd865f594ce56ed9a45472bb350b5e0b7'
FRESH='source_image_unreviewed_v1:a1f0b680bfd07d5c2ca3a7d11d47939c96f8639271a38764897fdeabd346f81a'


def heading_case(columns=2):
    snapshot,view,proposal=body_case(columns,mixed=True)
    proposal['paragraphs'][1]['role']='institution'
    proposal['paragraphs'][8].update(role='heading',heading_level=2,heading_size_pt=17,bold=True,italic=True)
    return snapshot,view,proposal


@pytest.mark.parametrize('columns',[2,3])
def test_v4_restores_mixed_heading_band_without_changing_choices_or_source(columns):
    snapshot,view,proposal=heading_case(columns);before=c.encode([snapshot,view,proposal])
    with pytest.raises(c.OrdinaryLayoutError,match='proposal_coverage'):
        c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)
    result=c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V4)
    expected=deepcopy(proposal['bands']);ids=c.page_ids(view,1)[1:9]
    expected[1]={'kind':'flow','groups':[{'paragraph_ids':ids,'panel':False}]}
    assert result['bands']==expected
    for choice,row in zip(proposal['paragraphs'],result['paragraphs']):
        assert {k:v for k,v in row.items() if k not in {'regions','unmapped_reason'}}=={k:v for k,v in choice.items() if k!='bbox'}
    assert result['paragraphs'][8]['role']=='heading' and result['paragraphs'][8]['heading_level']==2
    model.validate_decisions(snapshot,view['pages'],result)
    evidence=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V4)
    assert evidence['metadata_band_normalization']['rejected_bands']==[{'index':1,'paragraph_ids':ids,'reason':'generated_plain_columns_restored_to_text_order'}]
    assert evidence['source_coverage_verified'] is False
    assert c.source_evidence_review_fields([evidence])['source_layout_review_required'] is True
    assert c.encode([snapshot,view,proposal])==before


@pytest.mark.parametrize('fault',['missing','extra','duplicate','choices_order','choice_key','band_key','cell_key',
    'group_key','empty','one_cell','four_cells','panel','width_boolean','width_nan','width_sum','width_count',
    'gutter_nan','gutter_range','list_role','signature_role','folio_role','partition','field','numbering','numPr',
    'break','tab','line_break','control','cross_interval'])
def test_v4_heading_does_not_rescue_unsafe_or_unsupported_band(fault):
    snapshot,view,proposal=heading_case();band=proposal['bands'][1];group=band['cells'][0]['groups'][0];row=snapshot['paragraphs'][1]
    if fault=='missing': group['paragraph_ids'].pop()
    elif fault=='extra': group['paragraph_ids'].append('p999999')
    elif fault=='duplicate': group['paragraph_ids'][1]=group['paragraph_ids'][0]
    elif fault=='choices_order': proposal['paragraphs'][1:3]=proposal['paragraphs'][1:3][::-1]
    elif fault=='choice_key': proposal['paragraphs'][1]['invented']=True
    elif fault=='band_key': band['invented']=True
    elif fault=='cell_key': band['cells'][0]['invented']=True
    elif fault=='group_key': group['invented']=True
    elif fault=='empty': group['paragraph_ids']=[]
    elif fault=='one_cell': band['cells']=[{'groups':[{'paragraph_ids':sum([cell['groups'][0]['paragraph_ids'] for cell in band['cells']],[]),'panel':False}]}];band['widths_pct']=[100]
    elif fault=='four_cells': band['cells']=[{'groups':[{'paragraph_ids':c.page_ids(view,1)[1:9][i::4],'panel':False}]} for i in range(4)];band['widths_pct']=[25]*4
    elif fault=='panel': group['panel']=True
    elif fault=='width_boolean': band['widths_pct'][0]=True
    elif fault=='width_nan': band['widths_pct'][0]=float('nan')
    elif fault=='width_sum': band['widths_pct']=[40,40]
    elif fault=='width_count': band['widths_pct']=[100]
    elif fault=='gutter_nan': band['gutter_pt']=float('nan')
    elif fault=='gutter_range': band['gutter_pt']=37
    elif fault.endswith('_role'): proposal['paragraphs'][1]['role']={'list_role':'list','signature_role':'signature','folio_role':'source_folio'}[fault]
    elif fault=='partition': proposal['paragraph_partitions']=[{'paragraph_id':row['id'],'split_before':['tail']}]
    elif fault=='field': row['has_field']=True
    elif fault=='numbering': row['has_numbering']=True
    elif fault=='numPr': row['ppr_xml']='<w:numPr/>'
    elif fault=='break': row['has_page_break']=True
    elif fault=='tab': row['tokens'].append({'kind':'tab','text':'\t'})
    elif fault=='line_break': row['tokens'].append({'kind':'line_break','text':'\n'})
    elif fault=='control': row['tokens'][0]['text']+='\u202e'
    elif fault=='cross_interval': group['paragraph_ids'][0],proposal['bands'][0]['groups'][0]['paragraph_ids'][0]=proposal['bands'][0]['groups'][0]['paragraph_ids'][0],group['paragraph_ids'][0]
    with pytest.raises(c.OrdinaryLayoutError):
        c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V4)


def test_v4_inherits_body_flow_footer_and_metadata_behavior_and_keeps_ordered_heading_columns():
    snapshot,view,proposal=body_case()
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V4)==c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)
    ids=c.page_ids(view,1)
    proposal['bands']=[{'kind':'flow','groups':[{'paragraph_ids':ids[::-1],'panel':False}]}]
    proposal['source_layout_evidence']=[{'kind':'source_footer','paragraph_ids':ids[::-1],'bbox':[.1,.9,.9,.99]}]
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V4)==c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)
    evidence=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V4)
    assert evidence['normalization']['rejected_hints'][0]['reason']=='reordered_source_footer_hint_kept_in_flow'
    assert evidence['metadata_band_normalization']['rejected_bands'][0]['reason']=='generated_plain_flow_restored_to_text_order'
    snapshot,view,proposal=heading_case();ids=c.page_ids(view,1)[1:9]
    proposal['bands'][1]['cells'][0]['groups'][0]['paragraph_ids']=ids[:4]
    proposal['bands'][1]['cells'][1]['groups'][0]['paragraph_ids']=ids[4:]
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V4)==c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V3)
    for row in proposal['paragraphs']: row.update(role='reference',heading_level=0,heading_size_pt=None)
    proposal['bands'][1]['cells'][0]['groups'][0]['paragraph_ids']=ids[::2]
    proposal['bands'][1]['cells'][1]['groups'][0]['paragraph_ids']=ids[1::2]
    old=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V3)
    fresh=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V4)
    assert fresh['metadata_band_normalization']['rejected_bands']==old['metadata_band_normalization']['rejected_bands']
    assert fresh['metadata_band_normalization']['rejected_bands'][0]['reason']=='metadata_columns_reordered_as_flow'


def test_eleven_historical_maps_and_request_bytes_remain_exact_with_version_only_fresh_policy():
    history=json.loads(HISTORY.read_bytes());assert len(history['maps'])==11
    assert auto._clock_direction_policy()==OLD and auto._heading_columns_v4_policy()==FRESH
    for row in history['maps']:
        policy=row['policy'];fp=policy.split(':',1)[1]
        assert auto._band_normalization_version(fp)==row['band_normalization_version']
        assert auto._source_normalization_version(fp)==row['source_hint_normalization_version']
        assert auto._clock_direction_version(fp)==row['clock_direction_version']
        assert (policy in auto._metadata_normalization_policies())==row['metadata_and_emphasis_policy_member']
        assert (policy in auto._source_folio_policies())==row['source_folio_policy_member']
        assert (policy in {FRESH,OLD,auto._body_columns_v3_policy(),auto._source_bound_v4_policy()})==row['numeric_run_ltr_v3_evidence_emitted_when_source_evidence_present']
    snapshot,view,_=body_case()
    request={'instructions':INSTRUCTIONS,'schema':c.proposal_schema(1,c.page_ids(view,1))}
    assert request==history['request'] and sha256(c.encode(request)).hexdigest()==history['request_sha256']
    assert auto._band_normalization_version(FRESH.split(':',1)[1])==c.BAND_NORMALIZATION_V4
    assert auto._clock_direction_version(FRESH.split(':',1)[1])=='clock_h_colon_ltr_v1'
    for arbitrary in ['0'*64,'f'*64]:
        assert auto._clock_direction_version(arbitrary) is None
        assert auto._band_normalization_version(arbitrary) is None
        assert 'source_image_unreviewed_v1:'+arbitrary not in auto._source_folio_policies()


@pytest.mark.parametrize('index',range(4))
def test_genuine_old_clock_candidate_docx_map_and_receipt_replay_exact(index):
    history=json.loads(HISTORY.read_bytes());original=Path(__file__).parent/'fixtures/clock_direction_prechange_v3.json'
    assert sha256(original.read_bytes()).hexdigest()==history['fixture_input_sha256']
    fixture=json.loads(original.read_bytes());case=fixture['cases'][index];expected=history['cases'][index]
    raw=base64.b64decode(case['raw_base64']);pdf=base64.b64decode(case['source_pdf_base64'])
    snapshot=artifacts.bind_raw_page_map(raw,case['raw_source_map'],source_pdf_sha256=sha256(pdf).hexdigest(),selected_pages=(1,),target_lang=case['lang'])
    result=artifacts.build_unreviewed_candidate(raw,snapshot,case['frames'],case['decisions'],proposal_evidence=expected['evidence'],source_pdf_bytes=pdf)
    artifacts.verify_unreviewed_candidate(raw,snapshot,case['frames'],case['decisions'],result,proposal_evidence=expected['evidence'],source_pdf_bytes=pdf)
    assert (result.docx_sha256,result.source_map_sha256,result.receipt_sha256)==tuple(expected[k] for k in ['candidate_docx_sha256','candidate_map_sha256','candidate_receipt_sha256'])
