"""Closed clock recognition and independent, colon-only OOXML delta proof."""
from copy import deepcopy
from hashlib import sha256
import re

from lxml import etree
import pytest

from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import saved_docx_layout as model

W = model.W


def paragraph(text='موعد 09:30h.', *, colon_rtl='1'):
    node = etree.Element(W+'p', nsmap={'w':W[1:-1]})
    etree.SubElement(etree.SubElement(node,W+'pPr'),W+'bidi').set(W+'val','1')
    # Deliberately isolate every colon; digits and h already have explicit LTR.
    for part in re.split('(:)',text):
        if not part: continue
        run=etree.SubElement(node,W+'r');props=etree.SubElement(run,W+'rPr')
        etree.SubElement(props,W+'rFonts').set(W+'ascii','Arial')
        etree.SubElement(props,W+'rtl').set(W+'val',colon_rtl if part == ':' else '0')
        etree.SubElement(run,W+'t').text=part
    row={'id':'p000001','text':text,'tokens':[{'kind':'t','text':text}],
         'has_field':False,'has_numbering':False,'has_page_break':False,'ppr_xml':''}
    return node,row


def apply(node,row,*,owners=None,selected=(1,),lang='AR',excluded=None,mapped=None):
    plan={'decorative_rules':[]}
    source._apply_clock_direction({'p000001':node},mapped or {'p000001':{}},
        {'p000001':row},owners if owners is not None else {1:['p000001']},
        {'paragraph_partitions':excluded or []},plan,lang,list(selected))
    return plan


@pytest.mark.parametrize('text', ['00:00h','23:59h','00:00:00h','23:59:59h',
    'موعد 09:30h.', '(09:30h). Next sentence', '09:30h), ', '09:30h, next item',
    '09:30h؛ ', '«09:30h»', '\u200e09\u200e:\u200e30h\u200e',
    '\u200e09\u200e:\u200e30\u200e:\u200e59h\u200e',
    'تاريخ \u200e12/05/2028\u200e ثم 09:30h.', '09:30h\u2003'])
def test_closed_grammar_positive(text):
    node,row=paragraph(text);before=deepcopy(node);plan=apply(node,row)
    assert len(plan['clock_ltr_spans']) == 1
    span=plan['clock_ltr_spans'][0]
    assert span['clock_text_sha256']==sha256(text[span['start']:span['end']].encode()).hexdigest()
    restored=source._verified_clock_copy(node,before,row,[span])
    assert model._c14n(restored)==model._c14n(before)
    assert ''.join(node.itertext())==''.join(before.itertext())


@pytest.mark.parametrize('text', ['24:00h','12:60h','12:00:60h','9:30h','009:30h','09:3h',
    '09:300h','09:30H','09:30','09:30ha','09:30h5','09:30h_','name09:30h','09:30h.example',
    '09:30h.5','09:30h,name','09:30h.,name','09:30h)name','09:30h.\u0301',
    '09:30h/foo','09:30h:10','https://09:30h','/09:30h',':09:30h','.09:30h',
    '_09:30h','\u030109:30h','09: 30h','09 :30h','09:30 h','09:30:5h',
    '09:30:50:20h','٠٩:٣٠h','０９:３０h','09：30h','0\u200e9:30h','09:3\u200e0h',
    '09:30\u200eh','\u200e\u200e09:30h','09:30h\u200e\u200e','\u202e09:30h',
    '09:30h\t','09:30h\n','09:30h\u200f'])
def test_ineligible_grammar_is_unchanged(text):
    node,row=paragraph(text);before=model._c14n(node)
    assert apply(node,row)['clock_ltr_spans']==[]
    assert model._c14n(node)==before


@pytest.mark.parametrize('fault',['field','numbering','numPr','pagebreak','tab','linebreak','mismatch',
    'hyperlink','bookmark','revision','wrapper','run_break','no_bidi','bidi_false','duplicate_bidi',
    'colon_shared','colon_no_rtl','colon_duplicate_rtl','colon_other_rtl','colon_extra_attribute',
    'colon_child','digit_rtl','digit_no_rtl','duplicate_rPr','paragraph_section','control_elsewhere'])
def test_hidden_or_ambiguous_structure_declines_without_change(fault):
    node,row=paragraph();props=node.find(W+'pPr');runs=node.findall(W+'r');colon=runs[1]
    rtl=colon.find(W+'rPr/'+W+'rtl')
    if fault=='field': row['has_field']=True
    elif fault=='numbering': row['has_numbering']=True
    elif fault=='numPr': etree.SubElement(props,W+'numPr')
    elif fault=='pagebreak': row['has_page_break']=True
    elif fault in {'tab','linebreak'}: row['tokens'].append({'kind':fault,'text':''})
    elif fault=='mismatch': row['tokens'][0]['text']+='extra'
    elif fault in {'hyperlink','bookmark','revision','wrapper'}:
        etree.SubElement(node,W+{'bookmark':'bookmarkStart','revision':'ins','wrapper':'dir'}.get(fault,fault))
    elif fault=='run_break': etree.SubElement(runs[0],W+'br')
    elif fault=='no_bidi': props.remove(props.find(W+'bidi'))
    elif fault=='bidi_false': props.find(W+'bidi').set(W+'val','0')
    elif fault=='duplicate_bidi': etree.SubElement(props,W+'bidi').set(W+'val','1')
    elif fault=='colon_shared': colon.find(W+'t').text=': ';row['tokens'][0]['text']=row['text']='موعد 09: 30h.'
    elif fault=='colon_no_rtl': rtl.getparent().remove(rtl)
    elif fault=='colon_duplicate_rtl': rtl.getparent().append(deepcopy(rtl))
    elif fault=='colon_other_rtl': rtl.set(W+'val','true')
    elif fault=='colon_extra_attribute': rtl.set(W+'other','1')
    elif fault=='colon_child': etree.SubElement(rtl,W+'b')
    elif fault=='digit_rtl': runs[0].find(W+'rPr/'+W+'rtl').set(W+'val','1')
    elif fault=='digit_no_rtl': runs[0].find(W+'rPr').remove(runs[0].find(W+'rPr/'+W+'rtl'))
    elif fault=='duplicate_rPr': colon.insert(0,deepcopy(colon.find(W+'rPr')))
    elif fault=='paragraph_section': etree.SubElement(props,W+'sectPr')
    elif fault=='control_elsewhere':
        runs[0].find(W+'t').text='\u2066'+runs[0].find(W+'t').text
        row['tokens'][0]['text']=row['text']='\u2066'+row['text']
    before=model._c14n(node)
    assert apply(node,row)['clock_ltr_spans']==[]
    assert model._c14n(node)==before


@pytest.mark.parametrize('kwargs',[{'lang':'EN'},{'lang':'FR'},{'owners':{1:[]}},
    {'owners':{1:['p000001'],2:['p000001']}},{'owners':{2:['p000001']}},
    {'excluded':[{'paragraph_id':'p000001'}]}, {'mapped':{'p000001':{'parts':[{}]}}},
    {'mapped':{'p000001':{'part_uri':'word/footer2.xml'}}}])
def test_only_unique_selected_whole_body_owner_is_eligible(kwargs):
    node,row=paragraph();before=model._c14n(node)
    assert apply(node,row,**kwargs)['clock_ltr_spans']==[]
    assert model._c14n(node)==before


def test_already_ltr_colon_is_noop_and_multiple_clocks_are_ordered():
    node,row=paragraph(colon_rtl='0');before=model._c14n(node)
    assert apply(node,row)['clock_ltr_spans']==[] and model._c14n(node)==before
    node,row=paragraph('موعد 09:30h ثم 10:45:59h.');before=deepcopy(node);plan=apply(node,row)
    assert len(plan['clock_ltr_spans'])==2
    assert [len(span['colon_runs']) for span in plan['clock_ltr_spans']]==[1,2]
    assert plan['clock_ltr_spans'][0]['end'] < plan['clock_ltr_spans'][1]['start']
    assert model._c14n(source._verified_clock_copy(node,before,row,plan['clock_ltr_spans']))==model._c14n(before)


@pytest.mark.parametrize('fault',['hash','start','end','run','offset','before','after','bool','extra_key',
    'missing_colon','duplicate_colon','duplicate_span','text','mark','font','digit_rtl','arabic_rtl',
    'pPr','run_order','colon_unchanged'])
def test_independent_delta_proof_rejects_forged_permissions_and_other_xml_changes(fault):
    node,row=paragraph('موعد 09:30:59h.');baseline=deepcopy(node)
    spans=apply(node,row)['clock_ltr_spans'];span=spans[0];change=span['colon_runs'][0]
    if fault=='hash': span['clock_text_sha256']='0'*64
    elif fault=='start': span['start']+=1
    elif fault=='end': span['end']-=1
    elif fault=='run': change['run_index']=0
    elif fault=='offset': change['character_offset']+=1
    elif fault=='before': change['before_rtl']=0
    elif fault=='after': change['after_rtl']=1
    elif fault=='bool': change['before_rtl']=True
    elif fault=='extra_key': change['permission']=True
    elif fault=='missing_colon': span['colon_runs'].pop()
    elif fault=='duplicate_colon': span['colon_runs'].append(deepcopy(change))
    elif fault=='duplicate_span': spans.append(deepcopy(span))
    elif fault in {'text','mark'}: node.find(W+'r/'+W+'t').text += 'x' if fault=='text' else '\u200e'
    elif fault=='font': node.find(W+'r/'+W+'rPr/'+W+'rFonts').set(W+'ascii','Other')
    elif fault in {'digit_rtl','arabic_rtl'}: node.find(W+'r/'+W+'rPr/'+W+'rtl').set(W+'val','1')
    elif fault=='pPr': etree.SubElement(node.find(W+'pPr'),W+'jc').set(W+'val','left')
    elif fault=='run_order': node.append(node.findall(W+'r')[0])
    elif fault=='colon_unchanged': node.findall(W+'r')[1].find(W+'rPr/'+W+'rtl').set(W+'val','1')
    with pytest.raises(ValueError,match='source_clock_direction_delta'):
        source._verified_clock_copy(node,baseline,row,spans)


@pytest.mark.parametrize('fault',['page','unselected','unknown_id','row_key','bool','reorder','duplicate','version','missing_version'])
def test_plan_schema_ownership_and_order_are_closed(fault):
    node,row=paragraph('09:30h ثم 10:45h');plan=apply(node,row)
    if fault=='page': plan['clock_ltr_spans'][0]['source_page_number']=2
    elif fault=='unselected':
        with pytest.raises(ValueError): source._checked_clock_plan(plan,source.CLOCK_DIRECTION_V1,{'p000001':row},{1:['p000001']},[])
        return
    elif fault=='unknown_id': plan['clock_ltr_spans'][0]['paragraph_id']='p999999'
    elif fault=='row_key': plan['clock_ltr_spans'][0]['permission']=True
    elif fault=='bool': plan['clock_ltr_spans'][0]['start']=True
    elif fault=='reorder': plan['clock_ltr_spans'].reverse()
    elif fault=='duplicate': plan['clock_ltr_spans'].append(deepcopy(plan['clock_ltr_spans'][0]))
    elif fault=='version': plan['clock_direction_version']='invented'
    elif fault=='missing_version': del plan['clock_direction_version']
    with pytest.raises(ValueError): source._checked_clock_plan(plan,source.CLOCK_DIRECTION_V1,{'p000001':row},{1:['p000001']},[1])


def test_historical_context_cannot_authorize_any_new_clock_field():
    for plan in [{'clock_direction_version':source.CLOCK_DIRECTION_V1},{'clock_ltr_spans':[]}]:
        with pytest.raises(ValueError,match='source_clock_direction_version'):
            source._checked_clock_plan(plan,None,{}, {}, [])
