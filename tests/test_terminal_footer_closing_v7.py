"""Target-footer membership and one certified predecessor field table, no text repair."""
from copy import deepcopy
import pytest
from lxml import etree
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_terminal_closing_group as closing
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate.ordinary_terminal_source_layout import _field_pairs
from legalpdf_translate.saved_docx_layout_writer import _table
from tests.test_ordinary_body_columns_v3 import body_case
from tests.test_terminal_closing_group import fixture as closing_fixture

W=model.W


def footer_case():
    snapshot,view,proposal=body_case()
    ids=c.page_ids(view,1)
    proposal['bands']=[{'kind':'flow','groups':[{'paragraph_ids':ids[:-2],'panel':False}]},
        {'kind':'flow','groups':[{'paragraph_ids':ids[-2:][::-1],'panel':False}]}]
    proposal['paragraphs'][-2].update(role='body',bbox=[.2,.9,.8,.93])
    proposal['paragraphs'][-1].update(role='source_folio',bbox=[.3,.94,.7,.97])
    proposal['source_layout_evidence']=[{'kind':'source_footer','paragraph_ids':ids[-2:][::-1],'bbox':[.1,.88,.9,.99]}]
    return snapshot,view,proposal


def test_v7_derives_only_target_membership_and_preserves_original_hint_and_decisions():
    snapshot,view,proposal=footer_case();before=c.encode([snapshot,view,proposal]);ids=c.page_ids(view,1)
    evidence=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V7)
    assert evidence['layout']==[{**proposal['source_layout_evidence'][0],'paragraph_ids':ids[-2:]}]
    diagnostic=evidence['terminal_footer_membership_normalization']
    assert diagnostic['version']==c.BAND_NORMALIZATION_V7 and diagnostic['review_required'] is True
    row=diagnostic['associations'][0]
    assert row['original_hint']==proposal['source_layout_evidence'][0]
    assert row['original_paragraph_ids']==ids[-2:][::-1] and row['paragraph_ids']==ids[-2:]
    assert row['source_printed_order_verified'] is False
    assert c.source_evidence_review_fields([evidence])['source_layout_review_required'] is True
    assert c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V7)==c.normalize_proposals(snapshot,view,[proposal],band_normalization_version=c.BAND_NORMALIZATION_V6)
    assert c.encode([snapshot,view,proposal])==before


@pytest.mark.parametrize('version',[c.BAND_NORMALIZATION_V2,c.BAND_NORMALIZATION_V3,c.BAND_NORMALIZATION_V4,c.BAND_NORMALIZATION_V5,c.BAND_NORMALIZATION_V6])
def test_old_footer_association_remains_quarantined(version):
    evidence=c.proposal_source_evidence(*footer_case(),band_normalization_version=version)
    assert evidence['layout']==[] and 'terminal_footer_membership_normalization' not in evidence
    assert evidence['normalization']['rejected_hints'][0]['reason']=='reordered_source_footer_hint_kept_in_flow'


@pytest.mark.parametrize('fault',['one_id','three_ids','duplicate','foreign','nonterminal','reference','institution','signature','no_folio',
    'null_box','outside_box','reversed_box','boolean_box','nonbottom','panel','columns','partition','numbering','numPr',
    'field','break','tab','unsafe_control','choices_order','band_duplicate'])
def test_unproven_footer_membership_never_becomes_accepted(fault):
    snapshot,view,proposal=footer_case();ids=c.page_ids(view,1);hint=proposal['source_layout_evidence'][0]
    raw=snapshot['paragraphs'][-2];choice=proposal['paragraphs'][-2]
    if fault=='one_id':hint['paragraph_ids']=ids[-2:-1]
    elif fault=='three_ids':hint['paragraph_ids']=ids[-3:][::-1]
    elif fault=='duplicate':hint['paragraph_ids']=[ids[-1]]*2
    elif fault=='foreign':hint['paragraph_ids'][0]='p999999'
    elif fault=='nonterminal':hint['paragraph_ids']=ids[-3:-1][::-1]
    elif fault in {'reference','institution','signature'}:choice['role']=fault
    elif fault=='no_folio':proposal['paragraphs'][-1]['role']='body'
    elif fault=='null_box':choice['bbox']=None
    elif fault=='outside_box':choice['bbox']=[.01,.1,.99,.99]
    elif fault=='reversed_box':choice['bbox']=[.8,.9,.2,.93]
    elif fault=='boolean_box':choice['bbox'][0]=False
    elif fault=='nonbottom':hint['bbox']=[.1,.7,.9,.8]
    elif fault=='panel':proposal['bands'][-1]['groups'][0]['panel']=True
    elif fault=='columns':proposal['bands'][-1]={'kind':'columns','widths_pct':[50,50],'gutter_pt':10,'cells':[{'groups':[{'paragraph_ids':[i],'panel':False}]}for i in ids[-2:][::-1]]}
    elif fault=='partition':proposal['paragraph_partitions']=[{'paragraph_id':ids[-2],'split_before':['tail']}]
    elif fault=='numbering':raw['has_numbering']=True
    elif fault=='numPr':raw['ppr_xml']='<w:numPr/>'
    elif fault=='field':raw['has_field']=True
    elif fault=='break':raw['has_page_break']=True
    elif fault=='tab':raw['tokens'].append({'kind':'tab','text':'\t'})
    elif fault=='unsafe_control':raw['tokens'][0]['text']+='\u202e'
    elif fault=='choices_order':proposal['paragraphs'][:2]=proposal['paragraphs'][1::-1]
    elif fault=='band_duplicate':proposal['bands'][0]['groups'][0]['paragraph_ids'].append(ids[-1])
    try:evidence=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V7)
    except c.OrdinaryLayoutError:return
    assert 'terminal_footer_membership_normalization' not in evidence
    # A one-ID already ordered hint is a different existing source association.
    if fault!='one_id':assert not evidence['layout']


def table_case():
    args=list(closing_fixture());root,nodes,mapped,rows,choices,owners,plan,members=args
    body=root.find(W+'body');table,cells=_table([4000,4000],gutter_pt=12)
    for i,text,(cell,_) in zip(['label','value'],['Contact:','Fictional detail'],cells):
        p=etree.SubElement(cell,W+'p');etree.SubElement(p,W+'pPr');etree.SubElement(etree.SubElement(p,W+'r'),W+'t').text=text
        nodes[i]=p;mapped[i]={'paragraph_id':i,'part_uri':'word/document.xml'}
        rows[i]={'text':text,'tokens':[{'kind':'t','text':text}],'ppr_xml':'','has_page_break':False,'has_field':False}
        choices[i]={'role':'body'}
    body.insert(1,table)
    owners[1][1:1]=['label','value']
    for i,p in nodes.items():mapped[i]['location']=root.getroottree().getpath(p)
    plan['spacing_field_pairs']=_field_pairs(nodes,choices,rows,owners,mapped)
    return args


def test_closing_v2_recertifies_exact_predecessor_without_changing_table_text_or_styles():
    args=table_case();table=args[0].find(W+'body/'+W+'tbl');before=etree.tostring(table)
    assert closing.derive(*args)==[]
    groups=closing.derive(*args,version=closing.VERSION_V2)
    assert len(groups)==1 and groups[0]['predecessor_boundary']['paragraph_ids']==['label','value']
    baseline={i:deepcopy(p)for i,p in args[1].items()}
    closing.apply(*args,version=closing.VERSION_V2)
    closing.verify(args[0],{'paragraphs':list(args[2].values())},args[3],args[4],args[5],args[6],args[7],baseline)
    assert etree.tostring(table)==before
    assert args[6]['source_closing_group_version']==closing.VERSION_V2


@pytest.mark.parametrize('fault',['missing_pair','forged_pair','wrong_page','source_order','duplicate_owner','partition','wrong_part',
    'unowned_paragraph','extra_cell','extra_row','nested','merged','custom_table','custom_cell','field','numbering',
    'unsafe_control','changed_actual_text','direct_keep_left','direct_keep_right','inherited_keep','default_keep','hidden','outgoing'])
def test_closing_v2_has_no_arbitrary_table_or_incoming_chain_bypass(fault):
    args=table_case();root,nodes,mapped,rows,choices,owners,plan,members=args
    table=root.find(W+'body/'+W+'tbl');label=nodes['label'];value=nodes['value']
    if fault=='missing_pair':plan['spacing_field_pairs']=[]
    elif fault=='forged_pair':plan['spacing_field_pairs'][0]['value_id']='outside'
    elif fault=='wrong_page':plan['spacing_field_pairs'][0]['source_page_number']=2
    elif fault=='source_order':owners[1][1:3]=['value','label']
    elif fault=='duplicate_owner':owners[2]=['label','value']
    elif fault=='partition':mapped['label']['parts']=[{'location':'child'}]
    elif fault=='wrong_part':mapped['label']['part_uri']='word/footer1.xml'
    elif fault=='unowned_paragraph':etree.SubElement(label.getparent(),W+'p')
    elif fault=='extra_cell':etree.SubElement(table.find(W+'tr'),W+'tc')
    elif fault=='extra_row':etree.SubElement(table,W+'tr')
    elif fault=='nested':etree.SubElement(value.getparent(),W+'tbl')
    elif fault=='merged':etree.SubElement(label.getparent().find(W+'tcPr'),W+'gridSpan').set(W+'val','2')
    elif fault=='custom_table':table.set(W+'custom','1')
    elif fault=='custom_cell':label.getparent().set(W+'custom','1')
    elif fault=='field':etree.SubElement(label.find(W+'r'),W+'fldChar')
    elif fault=='numbering':rows['label']['has_numbering']=True
    elif fault=='unsafe_control':rows['label']['text']='Contact:\u202e'
    elif fault=='changed_actual_text':label.find('.//'+W+'t').text='Different: '
    elif fault.startswith('direct_keep'):etree.SubElement((label if fault.endswith('left')else value).find(W+'pPr'),W+'keepNext')
    elif fault=='inherited_keep':
        styles=model._xml(members['word/styles.xml']);style=etree.SubElement(styles,W+'style');style.set(W+'styleId','Incoming');style.set(W+'type','paragraph');etree.SubElement(etree.SubElement(style,W+'pPr'),W+'keepNext');members['word/styles.xml']=etree.tostring(styles)
        etree.SubElement(value.find(W+'pPr'),W+'pStyle').set(W+'val','Incoming')
    elif fault=='default_keep':
        styles=model._xml(members['word/styles.xml']);defaults=styles.find(W+'docDefaults/'+W+'pPrDefault/'+W+'pPr');etree.SubElement(defaults,W+'keepNext');members['word/styles.xml']=etree.tostring(styles)
    elif fault=='hidden':etree.SubElement(etree.SubElement(label.find(W+'r'),W+'rPr'),W+'vanish')
    elif fault=='outgoing':etree.SubElement(nodes['folio'].find(W+'pPr'),W+'keepNext')
    assert closing.derive(*args,version=closing.VERSION_V2)==[]


def test_fresh_v7_keeps_concrete_v6_recipe_and_old_closing_version():
    v6=auto._plain_list_columns_v6_policy()
    assert v6=='source_image_unreviewed_v1:9fd38bcf825d143d0f5109020ad5eacfc42d9d05187dd5ba44ba343152253ecd'
    assert auto._terminal_source_layout_versions(v6.split(':')[1])['source_closing_group_version']==closing.VERSION
    v7=auto._terminal_footer_membership_v7_policy()
    assert v7==auto._terminal_footer_membership_v7_policy() and v7!=v6
    assert auto._band_normalization_version(v7.split(':')[1])==c.BAND_NORMALIZATION_V7
    assert auto._terminal_source_layout_versions(v7.split(':')[1])['source_closing_group_version']==closing.VERSION_V2
    assert v6 in auto._metadata_normalization_policies() and v6 in auto._source_folio_policies()
