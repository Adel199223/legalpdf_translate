"""Structural closing-block authority, pagination deltas and historical isolation."""
from copy import deepcopy
import pytest
from lxml import etree
from legalpdf_translate import ordinary_terminal_closing_group as closing
from legalpdf_translate import saved_docx_layout as model
from tests.test_saved_docx_layout import document_bytes

W=model.W


def fixture(context=('Closing context one.','Closing context two.'),signatures=2):
    members,_=model._package(document_bytes(['Fictional seed']))
    root=etree.Element(W+'document',nsmap={'w':W[1:-1]});body=etree.SubElement(root,W+'body')
    data=[('outside','heading','Substantive earlier source content.')]
    data.extend((f'context{x}','body',t) for x,t in enumerate(context))
    data.extend((f'sign{x}','signature',f'Signer {x}: ____________________') for x in range(signatures))
    data.extend([('footer','body','Prepared automatically.'),('folio','source_folio','1 / 1')])
    nodes={};mapped={};rows={};choices={}
    for i,role,text in data:
        p=etree.SubElement(body,W+'p');etree.SubElement(p,W+'pPr');etree.SubElement(etree.SubElement(p,W+'r'),W+'t').text=text
        nodes[i]=p;mapped[i]={'paragraph_id':i,'part_uri':'word/document.xml','location':root.getroottree().getpath(p)}
        rows[i]={'text':text,'tokens':[{'kind':'t','text':text}],'ppr_xml':'','has_page_break':False,'has_field':False}
        choices[i]={'role':role}
    for i,node in nodes.items():mapped[i]['location']=root.getroottree().getpath(node)
    owners={1:list(nodes)};plan={'source_footers':[{'source_page_number':1,'paragraph_ids':['footer','folio']}]}
    return root,nodes,mapped,rows,choices,owners,plan,dict(members)


def derive(args):return closing.derive(*args)


@pytest.mark.parametrize('count',[0,1,2])
def test_complete_plain_context_counts_and_exact_pagination_only_delta(count):
    args=fixture(tuple('A complete multiline-capable context '+str(x) for x in range(count)))
    before=etree.tostring(args[0]);groups=derive(args)
    assert len(groups)==1 and len(groups[0]['context_ids'])==count
    closing.apply(*args)
    mapping={'paragraphs':list(args[2].values())};closing.verify(args[0],mapping,args[3],args[4],args[5],args[6],args[7])
    group=groups[0]['paragraph_ids']
    assert args[6]['source_closing_pagination_additions']=={'keepNext':group[:-1],'keepLines':group}
    for name,ids in args[6]['source_closing_pagination_additions'].items():
        for i in ids:
            p=args[1][i];p.find(W+'pPr').remove(p.find(W+'pPr/'+W+name))
    assert etree.tostring(args[0])==before


@pytest.mark.parametrize('case',['table','partition','field_flag','field_xml','tab','break','section',
                               'numbering','drawing','unsafe_bidi','unbalanced_isolate','short_line',
                               'no_line','too_many_signatures','one_signature','interposed_blank',
                               'wrong_part','duplicate_node','reversed','missing_footer','whole_section',
                               'incoming_keep','incoming_inherited_keep','outgoing_keep','nested_paragraph',
                               'text_separator','footer_partition','oversized_group','three_footers'])
def test_ambiguous_or_unbounded_signing_blocks_decline(case):
    a=fixture();root,nodes,mapped,rows,choices,owners,plan,members=a;p=nodes['sign0'];props=p.find(W+'pPr')
    if case=='table':
        body=p.getparent();body.remove(p);cell=etree.SubElement(etree.SubElement(etree.SubElement(body,W+'tbl'),W+'tr'),W+'tc');cell.append(p)
    elif case=='partition':mapped['sign0']['parts']=[{'location':'child'}]
    elif case=='field_flag':rows['sign0']['has_field']=True
    elif case=='field_xml':etree.SubElement(p.find(W+'r'),W+'fldChar')
    elif case=='tab':etree.SubElement(p.find(W+'r'),W+'tab')
    elif case=='break':etree.SubElement(p.find(W+'r'),W+'br')
    elif case=='section':etree.SubElement(props,W+'sectPr')
    elif case=='numbering':etree.SubElement(props,W+'numPr')
    elif case=='drawing':etree.SubElement(p.find(W+'r'),W+'drawing')
    elif case=='unsafe_bidi':rows['sign0']['text']='\u202eName: ______'
    elif case=='unbalanced_isolate':rows['sign0']['text']='Name: ______\u2066'
    elif case=='short_line':rows['sign0']['text']='Name: __'
    elif case=='no_line':rows['sign0']['text']='Name: A Person'
    elif case=='too_many_signatures':a=fixture(signatures=7)
    elif case=='one_signature':a=fixture(signatures=1)
    elif case=='interposed_blank':p.getparent().insert(p.getparent().index(p)+1,etree.Element(W+'p'))
    elif case=='wrong_part':mapped['sign0']['part_uri']='word/footer1.xml'
    elif case=='duplicate_node':nodes['sign1']=p
    elif case=='reversed':owners[1][3:5]=list(reversed(owners[1][3:5]))
    elif case=='missing_footer':plan['source_footers']=[]
    elif case=='whole_section':
        owners[1].remove('outside');nodes['outside'].getparent().remove(nodes['outside']);del nodes['outside']
    elif case=='incoming_keep':etree.SubElement(nodes['outside'].find(W+'pPr'),W+'keepNext')
    elif case=='incoming_inherited_keep':
        styles=model._xml(members['word/styles.xml']);style=etree.SubElement(styles,W+'style');style.set(W+'styleId','Incoming');style.set(W+'type','paragraph');etree.SubElement(etree.SubElement(style,W+'pPr'),W+'keepNext');members['word/styles.xml']=etree.tostring(styles)
        etree.SubElement(nodes['outside'].find(W+'pPr'),W+'pStyle').set(W+'val','Incoming')
    elif case=='outgoing_keep':etree.SubElement(nodes['folio'].find(W+'pPr'),W+'keepNext')
    elif case=='nested_paragraph':etree.SubElement(p.find(W+'r'),W+'p')
    elif case=='text_separator':rows['sign0']['text']='Name:\u2028________________'
    elif case=='footer_partition':mapped['footer']['parts']=[{'location':'child'}]
    elif case=='oversized_group':
        rows['sign0']['text']='Name: '+'_'*800;rows['sign1']['text']='Name: '+'_'*800
    elif case=='three_footers':plan['source_footers'][0]['paragraph_ids']=['sign1','footer','folio']
    assert derive(a)==[]


@pytest.mark.parametrize('context,expected',[
    (('x'*160,'y'*320),2),(('x'*161,'y'*320),1),(('short','y'*321),0),
    (('a '*20,'b '*60),2),(('a '*21,'b '*60),1),(('short','b '*61),0)])
def test_context_bounds_are_whole_and_never_skip_over_immediate_excess(context,expected):
    a=fixture(context);assert len(derive(a)[0]['context_ids'])==expected


def test_safe_directional_literal_runs_are_preserved_without_rewriting():
    a=fixture(('Text \u200eREF42\u200e remains complete.','Text \u2066REF99\u2069 remains complete.'))
    before=[etree.tostring(n.find(W+'r')) for n in a[1].values()]
    closing.apply(*a)
    assert [etree.tostring(n.find(W+'r')) for n in a[1].values()]==before
    assert len(a[6]['source_closing_groups'][0]['context_ids'])==2


def test_maximum_six_signature_rows_with_two_contexts_and_two_footers_remains_bounded():
    a=fixture(signatures=6);groups=derive(a)
    assert len(groups)==1 and len(groups[0]['paragraph_ids'])==10


@pytest.mark.parametrize('mutation',['disabled_link','disabled_lines','extra_end_link','wrong_ids','mapping',
                                   'unrelated_delta','unknown_property','duplicate_delta','missing_delta'])
def test_independent_actual_xml_and_plan_verifier_rejects_pagination_tamper(mutation):
    a=fixture();baseline={i:deepcopy(n) for i,n in a[1].items()};closing.apply(*a);nodes=a[1];plan=a[6];mapping={'paragraphs':list(a[2].values())}
    if mutation=='disabled_link':nodes['sign0'].find(W+'pPr/'+W+'keepNext').set(W+'val','0')
    elif mutation=='disabled_lines':nodes['sign0'].find(W+'pPr/'+W+'keepLines').set(W+'val','0')
    elif mutation=='extra_end_link':etree.SubElement(nodes['folio'].find(W+'pPr'),W+'keepNext')
    elif mutation=='wrong_ids':plan['source_closing_groups'][0]['paragraph_ids'].pop(0)
    elif mutation=='mapping':mapping['paragraphs'][1]['location']='/w:document/w:missing'
    elif mutation=='unrelated_delta':plan['source_closing_pagination_additions']['keepLines'].append('outside')
    elif mutation=='unknown_property':plan['source_closing_pagination_additions']['pageBreakBefore']=[]
    elif mutation=='duplicate_delta':plan['source_closing_pagination_additions']['keepLines'].append('sign0')
    elif mutation=='missing_delta':plan['source_closing_pagination_additions']['keepLines'].remove('sign0')
    with pytest.raises(ValueError):closing.verify(a[0],mapping,a[3],a[4],a[5],plan,a[7],baseline)


def writer_fixture():
    from tests.test_saved_docx_layout import reviewed
    from legalpdf_translate.docx_writer import _configure_styles,_add_page_number_footer
    raw=document_bytes(['Earlier source heading',
        'This complete fictional closing context preserves each condition and source identity. '*2,'Complete second closing context.',
        'Party: ____________________','Interpreter: ____________________','Prepared automatically.','1 / 1'],
        lambda doc:(_configure_styles(doc,'EN'),_add_page_number_footer(doc,'EN')))
    snapshot,pages,decisions=reviewed(raw,'EN');ids=[p['id'] for p in snapshot['paragraphs']]
    decisions['review'].update(document_reviewed=False,pages_reviewed=[],reviewer='',note='')
    decisions['bands']=[{'kind':'flow','groups':[{'paragraph_ids':[i],'panel':False}]} for i in ids]
    for index,row in enumerate(decisions['paragraphs']):
        row.update(role='institution' if index==0 else 'signature' if index in (3,4) else 'source_folio' if index==6 else 'body',
                   regions=[{'page_number':1,'bbox_px':[100,100,800,200]}])
    evidence={'version':'ordinary_source_evidence_v1','pages':[{'page_number':1,'findings':[],
        'layout':[{'kind':'source_footer','paragraph_ids':ids[-2:],'bbox':[.1,.9,.9,.98]}],'source_coverage_verified':False}]}
    context={'selected_pages':[1],'page_groups':[[1,ids]],'source_evidence':evidence,
        'source_footer_placement_version':'terminal_body_flow_v1','source_spacing_version':'baseline_metadata_heading_spacing_v1'}
    return raw,snapshot,pages,decisions,context


def test_closed_writer_multiline_context_preserves_old_recipe_and_records_whole_paragraph_flags():
    from legalpdf_translate import saved_docx_layout_writer as writer
    args=writer_fixture();before=deepcopy(args)
    old=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    args[4]['source_closing_group_version']=closing.VERSION
    new=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    writer.validate_built_docx(new.docx_bytes,new.source_map,original_docx=args[0],snapshot=args[1],pages=args[2],decisions=args[3],require_review=False,ordinary_context=args[4])
    group=new.source_map['source_layout_plan']['source_closing_groups'][0]
    assert group['context_ids']==[p['id'] for p in args[1]['paragraphs'][1:3]]
    assert new==writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    del args[4]['source_closing_group_version']
    assert args==before
    assert old==writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])


def test_new_policy_retains_exact_terminal_v1_capabilities_and_rejects_capability_forgery():
    from legalpdf_translate import ordinary_auto_layout as auto
    from legalpdf_translate.ordinary_auto_layout_artifacts import _terminal_source_layout_context
    old=auto._terminal_source_layout_policy();new=auto.frozen_automatic_layout_policy()
    assert old=='source_image_unreviewed_v1:98a25bdde6fa1f5b950c3b073653a5fc634fdf6248f4015fa9d13ddfae039099'
    assert new==auto._terminal_closing_group_policy() and new!=old
    assert old in auto._source_folio_policies() and old in auto._metadata_normalization_policies()
    assert auto._terminal_source_layout_versions(old.split(':')[1])=={'source_footer_placement_version':'terminal_body_flow_v1','source_spacing_version':'baseline_metadata_heading_spacing_v1'}
    evidence={'source_evidence':{},'policy_fingerprint':new.split(':')[1],**auto._terminal_source_layout_versions(new.split(':')[1])}
    assert _terminal_source_layout_context(evidence)['source_closing_group_version']==closing.VERSION
    evidence['policy_fingerprint']=old.split(':')[1]
    with pytest.raises(ValueError):_terminal_source_layout_context(evidence)
