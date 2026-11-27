"""Fictional raw PDF rows; source characters and historical order stay exact."""
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from legalpdf_translate.pdf_text_order import (build_text_blocks_from_page_dict,
    extract_ordered_page_text, SOURCE_FIELD_POLICY, SOURCE_QUESTION_ROW_POLICY)
from tests.test_source_field_row_order import line, source, fixture as colon_fixture


def fixture():
    return source([line("Pretende prosseguir?", 60, 110.045, 120, 180),
        line("Não", 284.811, 110, 120, 20),
        line("Deseja apresentar queixa?", 60, 135.045, 145, 220),
        line("Sim", 296.374, 135, 145, 20)])


def text(data, policy=SOURCE_QUESTION_ROW_POLICY, field=SOURCE_FIELD_POLICY):
    return build_text_blocks_from_page_dict(data, source_field_policy=field,
        source_question_row_policy=policy)[0].text


def test_exact_two_boolean_pairs_swap_only_existing_lines_without_mutation():
    data=fixture(); before=deepcopy(data)
    legacy=text(data,None); selected=text(data)
    assert legacy.splitlines()==["Não","Pretende prosseguir?","Sim","Deseja apresentar queixa?"]
    assert selected.splitlines()==["Pretende prosseguir?","Não","Deseja apresentar queixa?","Sim"]
    assert Counter(legacy.splitlines())==Counter(selected.splitlines())
    assert data==before
    assert text(data,None)==legacy


def test_absent_question_policy_and_explicit_colon_v1_remain_exact():
    data=fixture()
    assert text(data,None)==text(data,None,None)
    colons=colon_fixture()
    assert text(colons)==text(colons,None)
    assert text(colons,field=None)==text(colons,None,field=None)


@pytest.mark.parametrize("answer",["Sim","SIM","sIm","Não","NÃO","Na\u0303o"," Não "])
def test_portuguese_boolean_recognition_never_rewrites_original_answer(answer):
    data=fixture(); data['blocks'][0]['lines'][1]['spans'][0]['text']=answer
    assert text(data).splitlines()[:2]==["Pretende prosseguir?",answer]


@pytest.mark.parametrize("answer",["Nao","Yes","No","Não.","Sim não","Não quero","1","0","S","N","Verdadeiro",""])
def test_unrecognized_or_expanded_answers_do_not_enable_repair(answer):
    data=fixture(); data['blocks'][0]['lines']=data['blocks'][0]['lines'][:2]
    data['blocks'][0]['lines'][1]['spans'][0]['text']=answer
    assert text(data)==text(data,None)


@pytest.mark.parametrize("label",["A"*80+"?"," ".join(["palavra"]*13)+"?","1 Pergunta?",
    "Pergunta:","Pergunta: outra?","Pergunta, outra?","Pergunta\t?","Pergunta\n?","Pergunta？"])
def test_bounded_question_predicate_abstains_on_unrecognized_labels(label):
    data=fixture(); data['blocks'][0]['lines']=data['blocks'][0]['lines'][:2]
    data['blocks'][0]['lines'][0]['spans'][0]['text']=label
    assert text(data)==text(data,None)


def test_eighty_character_and_twelve_word_bounds_are_inclusive():
    for label in ("A"*79+"?"," ".join(["A"]*12)+"?"):
        data=fixture();data['blocks'][0]['lines']=data['blocks'][0]['lines'][:2]
        data['blocks'][0]['lines'][0]['spans'][0]['text']=label
        assert text(data).splitlines()==[label,"Não"]


@pytest.mark.parametrize("mutation",["different_baseline","top_difference","overlap","too_close","far_column",
    "third_cell","third_unknown_baseline","rotated","missing_origin","multi_span_baseline","nan_origin",
    "nonadjacent_raw","vertical_overlap","negative_width","nan_bbox","zero_width","nan_width","tab","hard_separator"])
def test_all_existing_geometry_guards_and_ambiguity_abstain(mutation):
    data=fixture();rows=data['blocks'][0]['lines'];del rows[2:]
    if mutation=='different_baseline':rows[1]['spans'][0]['origin'][1]+=.2
    if mutation=='top_difference':rows[1]['bbox'][1]-=1
    if mutation=='overlap':rows[1]['bbox'][0]=200
    if mutation=='too_close':rows[1]['bbox'][0]=241
    if mutation=='far_column':rows[1]['bbox']=[400,110,420,122]
    if mutation in {'third_cell','third_unknown_baseline'}:
        rows.append(line('Other cell',400,110,120,50))
        if mutation=='third_unknown_baseline':rows[-1]['spans'][0].pop('origin')
    if mutation=='rotated':rows[1]['dir']=(0.,1.)
    if mutation=='missing_origin':rows[1]['spans'][0].pop('origin')
    if mutation=='multi_span_baseline':rows[1]['spans'].append({'text':' ','origin':[300,121]});rows[1]['spans'][0]['origin'][1]=121
    if mutation=='nan_origin':rows[1]['spans'][0]['origin'][1]=float('nan')
    if mutation=='nonadjacent_raw':rows.insert(1,line('Independent row',60,160,170,100))
    if mutation=='vertical_overlap':rows[1]['bbox'][3]=110.2
    if mutation=='negative_width':rows[0]['bbox'][2]=50
    if mutation=='nan_bbox':rows[1]['bbox'][2]=float('nan')
    if mutation=='zero_width':data['width']=0
    if mutation=='nan_width':data['width']=float('nan')
    if mutation=='tab':rows[1]['spans'][0]['text']='Não\t'
    if mutation=='hard_separator':rows[1]['spans'][0]['text']='Não\u2028'
    assert text(data)==text(data,None)


def test_never_claims_pairs_across_pdf_blocks_or_nonadjacent_geometric_rows():
    data=fixture();rows=data['blocks'][0]['lines']
    data['blocks']=[{'type':0,'bbox':row['bbox'],'lines':[row]} for row in rows]
    assert [b.text for b in build_text_blocks_from_page_dict(data,source_question_row_policy=SOURCE_QUESTION_ROW_POLICY)]==[
        b.text for b in build_text_blocks_from_page_dict(data)]


@pytest.mark.parametrize("value",["unknown","",False,[],{}])
def test_unknown_policy_rejected_before_native_read(value,tmp_path):
    with pytest.raises(ValueError,match='source question row policy'):
        build_text_blocks_from_page_dict(fixture(),source_question_row_policy=value)
    with pytest.raises(ValueError,match='source question row policy'):
        extract_ordered_page_text(tmp_path/'missing.pdf',0,source_question_row_policy=value)


def test_source_wrapper_omits_absent_keyword_and_forwards_only_explicit_policy(tmp_path,monkeypatch):
    from legalpdf_translate import source_document,pdf_text_order
    path=tmp_path/'fictional.pdf';path.write_bytes(b'%PDF-fictional')
    calls=[]
    monkeypatch.setattr(pdf_text_order,'extract_ordered_page_text',lambda *a,**kw:calls.append(kw) or 'fake')
    source_document.extract_ordered_source_text(path,0)
    source_document.extract_ordered_source_text(path,0,source_field_policy=SOURCE_FIELD_POLICY)
    source_document.extract_ordered_source_text(path,0,source_question_row_policy=SOURCE_QUESTION_ROW_POLICY)
    assert calls==[{}, {'source_field_policy':SOURCE_FIELD_POLICY},{'source_question_row_policy':SOURCE_QUESTION_ROW_POLICY}]
