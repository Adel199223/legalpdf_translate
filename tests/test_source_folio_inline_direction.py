"""Source-proven separator-only RTL delta; fictional inputs, no providers."""
from copy import deepcopy
import base64
from hashlib import sha256
import json
from pathlib import Path
import re

from lxml import etree
import pytest

from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_auto_layout_artifacts as artifacts

W=model.W
OLD='source_image_unreviewed_v1:5737c26b2a9de209b945de79eb74813e7b98e772214082e54d198494a58e6f15'
FRESH='source_image_unreviewed_v1:7c54ccb193b2fb707fc8164f591f5cb9769e6ab800300be8bda227307dcbf2dd'
MODE='source_bound_folio_separator_ltr_v1'


def test_all_thirteen_genuine_historical_capability_maps_and_request_pins_remain_exact():
    from legalpdf_translate.ordinary_layout_manager import INSTRUCTIONS
    from legalpdf_translate import ordinary_layout_contracts as contracts
    old=json.loads((Path(__file__).parent/'fixtures/source_folio_inline_prechange_v5.json').read_bytes())
    assert len(old['maps'])==13
    for expected in old['maps']:
        policy=expected['policy'];fp=policy.split(':',1)[1]
        assert {'policy':policy,'band':auto._band_normalization_version(fp),
            'optional':auto._source_normalization_version(fp),'clock':auto._clock_direction_version(fp),
            'local_source_folio_proof':policy in auto._source_folio_policies(),
            'metadata':policy in auto._metadata_normalization_policies()}==expected
    assert sha256(INSTRUCTIONS.encode()).hexdigest()==old['instructions_sha256']
    assert sha256(contracts.encode(contracts.proposal_schema(3,['p000001']))).hexdigest()==old['proposal_schema_sha256']


def paragraph(text='بيان خيالي contact@example.test 2 / 3', *, terminal_break=False, rtl='1'):
    body=etree.Element(W+'body',nsmap={'w':W[1:-1]})
    node=etree.SubElement(body,W+'p')
    etree.SubElement(etree.SubElement(node,W+'pPr'),W+'bidi').set(W+'val','1')
    for value in re.split(r'(:| */ *)',text):
        if not value:continue
        run=etree.SubElement(node,W+'r');props=etree.SubElement(run,W+'rPr')
        etree.SubElement(props,W+'rFonts').set(W+'ascii','Arial')
        etree.SubElement(props,W+'rtl').set(W+'val',rtl if re.fullmatch(r' */ *|:',value) else '0')
        etree.SubElement(run,W+'t').text=value
    tokens=[{'kind':'t','text':text}]
    if terminal_break:
        etree.SubElement(etree.SubElement(node,W+'r'),W+'br').set(W+'type','page')
        tokens.append({'kind':'page_break','text':'\f'})
    row={'id':'p000001','text':text+('\f' if terminal_break else ''),'tokens':tokens,
        'has_field':False,'has_numbering':False,'has_page_break':terminal_break,'ppr_xml':''}
    return node,row


@pytest.mark.parametrize('literal',['2 / 3','2/3','\u200e2\u200e / \u200e3\u200e','٢ / ٣'])
@pytest.mark.parametrize('terminal_break',[False,True])
def test_plain_separator_only_attribute_change_keeps_exact_terminal_break_and_characters(literal,terminal_break):
    prefix='بيان خيالي contact@example.test '
    node,row=paragraph(prefix+literal,terminal_break=terminal_break);baseline=deepcopy(node)
    start=len(prefix)+int(literal.startswith('\u200e'))
    end=len(prefix)+len(literal)-int(literal.endswith('\u200e'))
    span={'paragraph_id':row['id'],'source_page_number':2,'start':start,'end':end,
        'literal_sha256':sha256(row['text'][start:end].encode()).hexdigest()}
    inventory=source._inline_folio_run_inventory(node,row)
    separator=source._inline_folio_separator(*inventory,span)
    assert separator is not None
    index,left,right,direction=separator;direction.set(W+'val','0')
    span['separator_runs']=[{'run_index':index,'start':left,'end':right,'before_rtl':1,'after_rtl':0}]
    restored=source._verified_inline_folio_copy(node,baseline,row,[span])
    assert model._c14n(restored)==model._c14n(baseline)
    assert ''.join(node.itertext())==''.join(baseline.itertext())


@pytest.mark.parametrize('index',range(3))
def test_genuine_prechange_v5_ar_en_fr_artifacts_replay_exact(index):
    root=Path(__file__).parent/'fixtures'
    golden=json.loads((root/'source_folio_inline_prechange_v5.json').read_bytes())
    fixture_path=root/'clock_direction_prechange_v3.json'
    assert sha256(fixture_path.read_bytes()).hexdigest()==golden['fixture_input_sha256']
    expected=golden['cases'][index];case=json.loads(fixture_path.read_bytes())['cases'][expected['fixture_case_index']]
    raw=base64.b64decode(case['raw_base64']);pdf=base64.b64decode(case['source_pdf_base64'])
    mapped=artifacts.bind_raw_page_map(raw,case['raw_source_map'],source_pdf_sha256=sha256(pdf).hexdigest(),selected_pages=(1,),target_lang=case['lang'])
    built=artifacts.build_unreviewed_candidate(raw,mapped,case['frames'],case['decisions'],proposal_evidence=expected['evidence'],source_pdf_bytes=pdf)
    assert (built.docx_sha256,built.source_map_sha256,built.receipt_sha256)==tuple(expected[k] for k in
        ('candidate_docx_sha256','candidate_map_sha256','candidate_receipt_sha256'))
    evidence={**expected['evidence'],'policy_fingerprint':FRESH.split(':',1)[1],'source_folio_inline_direction_version':MODE}
    fresh=artifacts.build_unreviewed_candidate(raw,mapped,case['frames'],case['decisions'],proposal_evidence=evidence,source_pdf_bytes=pdf)
    assert fresh.docx_bytes==built.docx_bytes
    assert fresh.source_map['source_layout_plan']['inline_folio_ltr_spans']==[]
    assert auto._inline_folio_direction_policy()==FRESH and auto._reference_footer_v5_policy()==OLD
    assert auto.frozen_automatic_layout_policy()!=FRESH


@pytest.mark.parametrize('defect', ['field','numbering','numPr','section','no_bidi','duplicate_bidi','ltr_paragraph',
    'hidden','web_hidden','revision','wrapper','tab','line_break','nonterminal_break','extra_break','token_text',
    'unrepresented_break','rtl_control','isolate','null'])
def test_unsafe_paragraph_inventory_never_qualifies(defect):
    node,row=paragraph(terminal_break=True)
    runs=node.findall(W+'r');props=node.find(W+'pPr')
    if defect=='field':row['has_field']=True
    elif defect=='numbering':row['has_numbering']=True
    elif defect in {'numPr','section'}:etree.SubElement(props,W+('numPr' if defect=='numPr' else 'sectPr'))
    elif defect=='no_bidi':props.remove(props.find(W+'bidi'))
    elif defect=='duplicate_bidi':etree.SubElement(props,W+'bidi').set(W+'val','1')
    elif defect=='ltr_paragraph':props.find(W+'bidi').set(W+'val','0')
    elif defect in {'hidden','web_hidden','revision'}:etree.SubElement(runs[0].find(W+'rPr'),W+{'hidden':'vanish','web_hidden':'webHidden','revision':'rPrChange'}[defect])
    elif defect=='wrapper':
        node.remove(runs[0]);etree.SubElement(node,W+'hyperlink').append(runs[0])
    elif defect in {'tab','line_break'}:etree.SubElement(runs[0],W+('tab' if defect=='tab' else 'br'))
    elif defect=='nonterminal_break':
        last=runs[-1];node.remove(last);node.insert(1,last)
    elif defect=='extra_break':etree.SubElement(runs[-1],W+'br').set(W+'type','page')
    elif defect=='token_text':row['text']='changed'
    elif defect=='unrepresented_break':row['has_page_break']=False
    else:
        mark={'rtl_control':'\u200f','isolate':'\u2066','null':'\x00'}[defect]
        # NUL cannot be XML text at all; its declared source token must decline.
        row['tokens'][0]['text']+=mark;row['text']=row['tokens'][0]['text']+'\f'
        if defect!='null':runs[0].find(W+'t').text+=mark
    assert source._inline_folio_run_inventory(node,row) is None


@pytest.mark.parametrize('defect',['digit_rtl','digit_missing','separator_missing','separator_mixed','two_slashes','unicode_space','long_number','suffix','extra_lrm','hash'])
def test_separator_requires_closed_grammar_and_explicit_existing_directions(defect):
    text='بيان خيالي contact@example.test 2 / 3'
    if defect=='two_slashes':text=text.replace(' / ',' // ')
    elif defect=='unicode_space':text=text.replace(' / ','\u00a0/ ')
    elif defect=='long_number':text=text.replace('2 /','12345 /')
    elif defect=='suffix':text+=' extra'
    elif defect=='extra_lrm':text=text.replace('2 /','\u200e\u200e2 /')
    node,row=paragraph(text)
    runs=node.findall(W+'r')
    if defect in {'digit_rtl','digit_missing'}:
        rtl=runs[-1].find(W+'rPr').find(W+'rtl')
        if defect=='digit_rtl':rtl.set(W+'val','1')
        else:rtl.getparent().remove(rtl)
    elif defect=='separator_missing':
        rtl=runs[1].find(W+'rPr').find(W+'rtl');rtl.getparent().remove(rtl)
    elif defect=='separator_mixed':
        runs[0].find(W+'t').text+=runs[1].find(W+'t').text
        node.remove(runs[1])
    inventory=source._inline_folio_run_inventory(node,row)
    start=text.index('12345') if defect=='long_number' else text.index('2')
    span={'start':start,'end':len(text),'literal_sha256':sha256(text[start:].encode()).hexdigest()}
    if defect=='hash':span['literal_sha256']='f'*64
    assert inventory is None or source._inline_folio_separator(*inventory,span) is None


@pytest.mark.parametrize('defect',['missing_version','old_context','extra_span','owner','duplicate','boolean_offset','delta_direction','delta_index','literal_hash','changed_text','changed_font','unlisted_delta'])
def test_plan_and_independent_undo_reject_unproven_or_extra_deltas(defect):
    node,row=paragraph();baseline=deepcopy(node)
    text=row['text'];start=text.index('2');end=len(text)
    span={'paragraph_id':row['id'],'source_page_number':2,'start':start,'end':end,'literal_sha256':sha256(text[start:end].encode()).hexdigest()}
    separator=source._inline_folio_separator(*source._inline_folio_run_inventory(node,row),span)
    index,left,right,rtl=separator;rtl.set(W+'val','0')
    span['separator_runs']=[{'run_index':index,'start':left,'end':right,'before_rtl':1,'after_rtl':0}]
    plan={'inline_folio_direction_version':MODE,'inline_folio_ltr_spans':[span]}
    if defect=='missing_version':plan.pop('inline_folio_direction_version')
    elif defect=='extra_span':span['extra']=True
    elif defect=='owner':span['source_page_number']=1
    elif defect=='duplicate':plan['inline_folio_ltr_spans'].append(deepcopy(span))
    elif defect=='boolean_offset':span['start']=True
    elif defect=='delta_direction':span['separator_runs'][0]['after_rtl']=1
    elif defect=='delta_index':span['separator_runs'][0]['run_index']+=1
    elif defect=='literal_hash':span['literal_sha256']='f'*64
    elif defect=='changed_text':node.findall(W+'r')[0].find(W+'t').text+=' edit'
    elif defect=='changed_font':node.findall(W+'r')[0].find(W+'rPr').find(W+'rFonts').set(W+'ascii','Other')
    elif defect=='unlisted_delta':node.findall(W+'r')[0].find(W+'rPr').find(W+'rtl').set(W+'val','1')
    with pytest.raises(model.SavedDocxLayoutError):
        checked=source._checked_inline_folio_plan(plan,None if defect=='old_context' else MODE,{row['id']:row},{2:[row['id']]},[2])
        restored=source._verified_inline_folio_copy(node,baseline,row,checked[row['id']])
        if model._c14n(restored)!=model._c14n(baseline):model._fail('source_inline_folio_direction_delta')


@pytest.mark.parametrize('defect',['source_missing','role','geometry','panel','partition','control','wrong_fraction'])
def test_partial_direction_qualification_retains_strict_per_page_checks_and_all_page_suppression(defect,tmp_path):
    from tests.test_source_folio_span_proof import fixture
    from legalpdf_translate.ordinary_source_folio_proof import KEY,target_spans,direction_target_spans
    _,mapped,frames,decisions,evidence,_,_=fixture(tmp_path,labels=('Contact. 1/3','Contact. 2/3','Contact. 3/3'))
    context={'selected_pages':[1,2,3],'page_groups':[[p,list(ids)] for p,ids in mapped.page_groups],KEY:evidence[KEY]}
    snapshot=mapped.saved_snapshot
    choice=next(c for c in decisions['paragraphs'] if c['role']=='source_folio')
    pid=choice['paragraph_id']
    if defect=='source_missing':evidence[KEY]['folios'][0]['fraction']=None
    elif defect=='role':choice['role']='body'
    elif defect=='geometry':choice['regions'][0]['bbox_px']=[50,1290,100,1350]
    elif defect=='partition':decisions['paragraph_partitions']=[{'paragraph_id':pid,'offsets':[8]}]
    elif defect=='control':next(r for r in snapshot['paragraphs'] if r['id']==pid)['tokens'].insert(0,{'kind':'tab'})
    elif defect=='wrong_fraction':evidence[KEY]['folios'][0]['fraction']['numerator']=2
    else:
        for band in decisions['bands']:
            groups=[]
            for group in band.get('groups',[]):
                if pid not in group['paragraph_ids']:groups.append(group);continue
                ids=group['paragraph_ids'];index=ids.index(pid)
                groups.extend({'paragraph_ids':part,'panel':panel} for part,panel in
                    ((ids[:index],False),([pid],True),(ids[index+1:],False)) if part)
            band['groups']=groups
    assert target_spans(snapshot,frames,decisions,context)==[]
    assert [s['page_number'] for s in direction_target_spans(snapshot,frames,decisions,context)]==[2,3]
    # Even after earlier qualifying pages, malformed later proof is not ignored.
    evidence[KEY]['folios'][-1]['unexpected']=True
    with pytest.raises(ValueError,match='source_folio_proof'):
        direction_target_spans(snapshot,frames,decisions,context)
