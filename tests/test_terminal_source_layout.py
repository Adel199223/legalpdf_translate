"""Narrow field-row authority; narrative table cells are not metadata evidence."""
from copy import deepcopy
from lxml import etree
import pytest
from legalpdf_translate.ordinary_terminal_source_layout import _field_pairs
from legalpdf_translate import saved_docx_layout as model


def field_fixture():
    root=etree.Element(model.W+'document');body=etree.SubElement(root,model.W+'body')
    table=etree.SubElement(body,model.W+'tbl');tr=etree.SubElement(table,model.W+'tr')
    nodes={};choices={};rows={};mapped={}
    for i,text in enumerate(('Reference:', 'REF-42 / 2026'),1):
        identifier=f'p{i:06d}';p=etree.SubElement(etree.SubElement(tr,model.W+'tc'),model.W+'p')
        etree.SubElement(etree.SubElement(p,model.W+'r'),model.W+'t').text=text
        nodes[identifier]=p;choices[identifier]={'role':'body'}
        rows[identifier]={'text':text,'tokens':[{'kind':'t','text':text}], 'ppr_xml':'','has_page_break':False,'has_field':False}
        mapped[identifier]={}
    return nodes,choices,rows,{2:list(nodes)},mapped


def test_source_adjacent_plain_label_value_row_qualifies_without_rewriting_text():
    args=field_fixture();before=deepcopy(args[2]);result=_field_pairs(*args)
    assert result==[{'label_id':'p000001','value_id':'p000002','source_page_number':2,'basis':'canonical_two_cell_label_value_row'}]
    assert args[2]==before


@pytest.mark.parametrize('case',['narrative','sentence_value','nonadjacent','reversed','cross_source',
                               'multiple_paragraphs','partition','control','multiple_labels','long_value'])
def test_ambiguous_or_narrative_table_rows_never_gain_field_authority(case):
    nodes,choices,rows,owners,mapped=field_fixture()
    if case=='narrative':rows['p000001']['text']='The claimant requested review'
    elif case=='sentence_value':rows['p000002']['text']='The claimant must file within five days.'
    elif case=='nonadjacent':owners[2]=['p000001','p000999','p000002']
    elif case=='reversed':owners[2]=['p000002','p000001']
    elif case=='cross_source':owners={2:['p000001'],3:['p000002']}
    elif case=='multiple_paragraphs':etree.SubElement(nodes['p000002'].getparent(),model.W+'p')
    elif case=='partition':mapped['p000002']['parts']=[{'part_id':'child'}]
    elif case=='control':rows['p000002']['tokens'].append({'kind':'br','text':'\n'})
    elif case=='multiple_labels':rows['p000002']['text']='Another label:'
    elif case=='long_value':rows['p000002']['text']='value '*30
    assert _field_pairs(nodes,choices,rows,owners,mapped)==[]


@pytest.mark.parametrize('question,answer',[
    ('Interpreter requested?', 'Yes'),('Avocat demandé ?', 'Non'),
    ('هل طُلب مترجم؟','لا'),('هل طُلب مترجم؟','نعم - الاسم: شخص افتراضي'),
    ('Interpreter requested?', 'Yes - Name: Fictional Person')])
def test_closed_boolean_field_rows_qualify(question,answer):
    args=field_fixture();args[2]['p000001']['text']=question;args[2]['p000002']['text']=answer
    assert _field_pairs(*args)[0]['basis']=='canonical_two_cell_boolean_row'


@pytest.mark.parametrize('question,answer',[
    ('What happened?', 'The witness gave evidence.'),
    ('Was the application approved?', 'Pending'),
    ('Was it approved? Or refused?', 'No'),
    ('The witness spoke. Was it approved?', 'No'),
    ('"Did you see it?"', 'Yes'),
    ('Was it approved?', 'Yes. It was approved.'),
    ('Was it approved?', 'No - Explanation: It was refused.'),
    ('Interpreter requested?', 'Yes Name: Fictional Person'),
    ('Interpreter requested?', 'Yes - Name: Fictional: Person'),
    ('Interpreter requested?', 'Yes - Name: Person. Then more prose'),
    ('No','Was it approved?')])
def test_dialogue_and_freeform_answers_never_gain_boolean_field_authority(question,answer):
    args=field_fixture();args[2]['p000001']['text']=question;args[2]['p000002']['text']=answer
    assert _field_pairs(*args)==[]


def test_later_partition_child_after_footer_fails_independent_terminal_inventory():
    from legalpdf_translate.ordinary_terminal_source_layout import verify_terminal_order
    root=etree.Element(model.W+'document',nsmap={'w':model.W[1:-1]});body=etree.SubElement(root,model.W+'body')
    children=[etree.SubElement(body,model.W+'p') for _ in range(3)];etree.SubElement(body,model.W+'sectPr')
    path=root.getroottree().getpath
    rows=[{'paragraph_id':'body','part_uri':'word/document.xml','location':path(children[0]),
           'parts':[{'location':path(children[0])},{'location':path(children[2])}]},
          {'paragraph_id':'folio','part_uri':'word/document.xml','location':path(children[1])}]
    plan={'source_footers':[{'source_page_number':1,'paragraph_ids':['folio']}]}
    with pytest.raises(ValueError,match='source_terminal_footer_order'):
        verify_terminal_order(root,{'paragraphs':rows},{1:['body','folio']},plan)
