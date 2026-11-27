"""Fictional pagination-only source associations and exact writer carriers."""
from copy import deepcopy
from functools import lru_cache
import pytest
from lxml import etree
from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import ordinary_terminal_closing_group as closing
from legalpdf_translate import ordinary_terminal_closing_v3 as v3
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests.test_saved_docx_layout import document_bytes, reviewed

W=model.W


def fixture():
    raw=document_bytes(['Earlier substantive content.', 'Contact\uff1a', 'Fictional contact value',
        'Complete first closing context.', 'Complete second context.',
        'Party: ____________________', 'Interpreter: ____________________',
        'Prepared automatically.', '1 / 1'])
    snapshot,pages,decisions=reviewed(raw,'AR')
    ids=[p['id'] for p in snapshot['paragraphs']]
    decisions['review'].update(document_reviewed=False,pages_reviewed=[],reviewer='',note='')
    for index,row in enumerate(decisions['paragraphs']):
        row.update(role='reference' if index==7 else 'source_folio' if index==8 else 'signature' if index in (5,6) else 'body',
            regions=[{'page_number':1,'bbox_px':[100,100+index*40,900,130+index*40]}])
    decisions['paragraphs'][7]['regions'][0]['bbox_px']=[300,1300,700,1320]
    decisions['paragraphs'][8]['regions'][0]['bbox_px']=[400,1340,600,1360]
    flow=lambda values:{'kind':'flow','groups':[{'paragraph_ids':values,'panel':False}]}
    decisions['bands']=[flow(ids[:1]),{'kind':'columns','widths_pct':[50,50],'gutter_pt':12,
        'cells':[{'groups':[{'paragraph_ids':[i],'panel':False}]} for i in ids[1:3]]},flow(ids[3:])]
    proposal={'version':c.PROPOSAL_VERSION_V3,'page_number':1,'paragraphs':[],
        'bands':deepcopy(decisions['bands']),'paragraph_partitions':[],
        'source_coverage_findings':[],'source_layout_evidence':[{'kind':'source_footer','paragraph_ids':ids[-2:],
        'bbox':[.2,.9,.8,.99]}]}
    for row in decisions['paragraphs']:
        choice=deepcopy(row);region=choice.pop('regions')[0];choice.pop('unmapped_reason')
        choice['bbox']=[v/(1000 if i%2==0 else 1400) for i,v in enumerate(region['bbox_px'])]
        proposal['paragraphs'].append(choice)
    view={'pages':pages,'decisions':decisions,'paragraphs':snapshot['paragraphs']}
    evidence=c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V8)
    context={'selected_pages':[1],'page_groups':[[1,ids]],
        'source_evidence':{'version':'ordinary_source_evidence_v1','pages':[evidence]},
        'source_footer_placement_version':'terminal_body_flow_v1',
        'source_spacing_version':'baseline_metadata_heading_spacing_v1',
        'source_closing_group_version':closing.VERSION_V3}
    return raw,snapshot,pages,decisions,context,proposal,view


@lru_cache(maxsize=1)
def _built():
    args=fixture(); artifact=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    base_context=deepcopy(args[4]);base_context.pop('source_evidence');base_context.pop('source_closing_group_version')
    base_context.pop('source_footer_placement_version');base_context.pop('source_spacing_version')
    baseline=writer.build_unreviewed_docx(*args[:4],ordinary_context=base_context)
    return args,artifact,baseline


def built():
    return deepcopy(_built())


def proof_args():
    args,artifact,baseline=built();snapshot,pages,decisions,context=args[1:5]
    trusted=v3.baseline_context(baseline,snapshot,pages,decisions,context)
    root=deepcopy(trusted['root']);nodes={i:root.xpath(r['location'],namespaces=v3.NS)[0] for i,r in trusted['mapped'].items()}
    plan=deepcopy(artifact.source_map['source_layout_plan'])
    for key in ['source_closing_groups','source_closing_pagination_additions','source_closing_structural_additions']:
        plan.pop(key,None)
    return [root,nodes,deepcopy(trusted['mapped']),{r['id']:r for r in snapshot['paragraphs']},
        {r['paragraph_id']:r for r in decisions['paragraphs']},{1:[r['id'] for r in snapshot['paragraphs']]},plan,dict(trusted['members'])],trusted


def test_full_writer_proof_preserves_reference_role_and_exact_nonflag_xml():
    args,artifact,baseline=built()
    writer.validate_built_docx(artifact.docx_bytes,artifact.source_map,original_docx=args[0],snapshot=args[1],
        pages=args[2],decisions=args[3],require_review=False,ordinary_context=args[4])
    plan=artifact.source_map['source_layout_plan'];ids=[r['id'] for r in args[1]['paragraphs']]
    assert plan['source_footers']==[] and len(plan['source_closing_groups'])==1
    group=plan['source_closing_groups'][0]
    assert group['paragraph_ids']==ids[3:] and group['context_ids']==ids[3:5]
    assert group['predecessor_boundary']['kind']=='exact_writer_two_cell_stop_sentinel'
    assert group['reference_carrier']['paragraph_id']==ids[-2]
    assert plan['spacing_field_pairs']==[]  # Fullwidth source colon is untouched.
    assert len(plan['source_closing_structural_additions']['paragraphs'])==3
    actual,_=model._package(artifact.docx_bytes);before,_=model._package(baseline.docx_bytes)
    root=model._xml(actual['word/document.xml']);old=model._xml(before['word/document.xml'])
    for node in list(root.iter(W+'keepNext'))+list(root.iter(W+'keepLines')):node.getparent().remove(node)
    assert model._c14n(root)==model._c14n(old)
    assert {k:v for k,v in actual.items() if k!='word/document.xml'}=={k:v for k,v in before.items() if k!='word/document.xml'}
    assert artifact==writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])


@pytest.mark.parametrize('fault',['role','duplicate','foreign','reordered','nonterminal','nonbottom','nan','outside',
    'panel','columns','partition','field','numbering','break','control','extra_key','overlap','no_reference'])
def test_positive_association_requires_complete_original_hint_and_safe_source(fault):
    args=fixture();snapshot,proposal,view=args[1],args[5],args[6];ids=[r['id'] for r in snapshot['paragraphs']]
    hint=proposal['source_layout_evidence'][0];row=proposal['paragraphs'][-2];raw=snapshot['paragraphs'][-2]
    if fault=='role':row['role']='institution'
    elif fault=='duplicate':hint['paragraph_ids']=[ids[-1]]*2
    elif fault=='foreign':hint['paragraph_ids'][0]='foreign'
    elif fault=='reordered':hint['paragraph_ids'].reverse()
    elif fault=='nonterminal':hint['paragraph_ids']=ids[-3:-1]
    elif fault=='nonbottom':hint['bbox']=[.2,.1,.8,.8]
    elif fault=='nan':hint['bbox'][0]=float('nan')
    elif fault=='outside':row['bbox']=[.01,.91,.99,.92]
    elif fault=='panel':proposal['bands'][-1]['groups'][0]['panel']=True
    elif fault=='columns':proposal['bands'][-1]={'kind':'columns','cells':[{'groups':[{'paragraph_ids':ids[3:],'panel':False}]}]}
    elif fault=='partition':proposal['paragraph_partitions']=[{'paragraph_id':ids[-2]}]
    elif fault in {'field','numbering','break'}:raw['has_'+{'field':'field','numbering':'numbering','break':'page_break'}[fault]]=True
    elif fault=='control':raw['tokens'][0]['text']+='\u202e'
    elif fault=='extra_key':hint['authority']='accepted'
    elif fault=='overlap':proposal['source_layout_evidence'].append(deepcopy(hint))
    elif fault=='no_reference':row['role']='body'
    assert c.retained_terminal_association(snapshot,proposal,ids,hint) is None


@pytest.mark.parametrize('fault',['missing','sha','purpose','hint','bbox','role','target_box','duplicate'])
def test_transform_independently_requalifies_positive_record(fault):
    args=fixture();page=args[4]['source_evidence']['pages'][0];container=page['retained_terminal_associations']
    record=container['associations'][0]
    if fault=='missing':page.pop('retained_terminal_associations')
    elif fault=='sha':container['canonical_proposal_sha256']='0'*64
    elif fault=='purpose':record['nonrelocatable']=False
    elif fault=='hint':record['original_hint']['paragraph_ids'].reverse()
    elif fault=='bbox':record['original_hint']['bbox']=[.2,.2,.8,.8]
    elif fault=='role':args[3]['paragraphs'][-2]['role']='body'
    elif fault=='target_box':args[3]['paragraphs'][-2]['regions'][0]['bbox_px']=[0,0,1000,1400]
    elif fault=='duplicate':container['associations'].append(deepcopy(record))
    with pytest.raises(ValueError):writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])


@pytest.mark.parametrize('fault',['frame_attr','frame_row','frame_cell','frame_merge','frame_nested','frame_extra_p',
    'spacer_text','spacer_flag','spacer_unowned','anchor_missing','anchor_text','anchor_flag',
    'incoming_attr','incoming_nested','incoming_merge','incoming_unowned','incoming_keep','incoming_break',
    'incoming_default_keep','incoming_inherited_break','incoming_numbering','incoming_hidden',
    'signature_one','signature_seven','signature_bad','no_signature','outgoing',
    'folio_frame','duplicate_owner','partition','field','control'])
def test_exact_carrier_sentinel_and_existing_whole_group_bounds(fault):
    a,baseline=proof_args();root,nodes,mapped,rows,choices,owners,plan,members=a
    ids=owners[1];body=root.find(W+'body');frame=nodes[ids[-2]].getparent().getparent().getparent()
    incoming=nodes[ids[1]].getparent().getparent().getparent();side=frame.find(W+'tr/'+W+'tc/'+W+'p');anchor=body[body.index(frame)+1]
    if fault=='frame_attr':frame.set(W+'custom','1')
    elif fault=='frame_row':etree.SubElement(frame,W+'tr')
    elif fault=='frame_cell':etree.SubElement(frame.find(W+'tr'),W+'tc')
    elif fault=='frame_merge':etree.SubElement(frame.find(W+'tr/'+W+'tc/'+W+'tcPr'),W+'gridSpan')
    elif fault=='frame_nested':etree.SubElement(side.getparent(),W+'tbl')
    elif fault=='frame_extra_p':etree.SubElement(side.getparent(),W+'p')
    elif fault=='spacer_text':etree.SubElement(etree.SubElement(side,W+'r'),W+'t').text='unowned'
    elif fault=='spacer_flag':etree.SubElement(side.find(W+'pPr'),W+'keepNext')
    elif fault=='spacer_unowned':baseline['structural'].remove(root.getroottree().getpath(side))
    elif fault=='anchor_missing':body.remove(anchor)
    elif fault=='anchor_text':etree.SubElement(etree.SubElement(anchor,W+'r'),W+'t').text='unowned'
    elif fault=='anchor_flag':etree.SubElement(anchor.find(W+'pPr'),W+'pageBreakBefore')
    elif fault=='incoming_attr':incoming.set(W+'custom','1')
    elif fault=='incoming_nested':etree.SubElement(nodes[ids[1]].getparent(),W+'tbl')
    elif fault=='incoming_merge':etree.SubElement(nodes[ids[1]].getparent().find(W+'tcPr'),W+'gridSpan')
    elif fault=='incoming_unowned':del nodes[ids[1]]
    elif fault=='incoming_keep':etree.SubElement(nodes[ids[2]].find(W+'pPr'),W+'keepNext')
    elif fault=='incoming_break':etree.SubElement(nodes[ids[2]].find(W+'pPr'),W+'pageBreakBefore')
    elif fault in {'incoming_default_keep','incoming_inherited_break'}:
        styles=model._xml(members['word/styles.xml'])
        if fault=='incoming_default_keep':props=styles.find(W+'docDefaults/'+W+'pPrDefault/'+W+'pPr');name='keepNext'
        else:
            style=etree.SubElement(styles,W+'style');style.set(W+'styleId','Boundary');style.set(W+'type','paragraph')
            props=etree.SubElement(style,W+'pPr');name='pageBreakBefore';etree.SubElement(nodes[ids[2]].find(W+'pPr'),W+'pStyle').set(W+'val','Boundary')
        etree.SubElement(props,W+name);members['word/styles.xml']=etree.tostring(styles)
    elif fault=='incoming_numbering':rows[ids[2]]['has_numbering']=True
    elif fault=='incoming_hidden':etree.SubElement(etree.SubElement(nodes[ids[2]].find(W+'r'),W+'rPr'),W+'vanish')
    elif fault in {'signature_one','no_signature'}:
        choices[ids[5]]['role']='body'
        if fault=='no_signature':choices[ids[6]]['role']='body'
    elif fault=='signature_seven':
        # An extra claimed signature cannot replace arbitrary earlier content.
        for i in ids[:-2]:choices[i]['role']='signature'
    elif fault=='signature_bad':rows[ids[5]]['text']='Not a signing line'
    elif fault=='context_excess':rows[ids[4]]['text']='x'*321;nodes[ids[4]].find(W+'r/'+W+'t').text=rows[ids[4]]['text']
    elif fault=='outgoing':etree.SubElement(nodes[ids[-1]].find(W+'pPr'),W+'keepNext')
    elif fault=='folio_frame':body.remove(nodes[ids[-1]]);frame.find(W+'tr/'+W+'tc').append(nodes[ids[-1]])
    elif fault=='duplicate_owner':owners[2]=[ids[-2]]
    elif fault=='partition':mapped[ids[-2]]['parts']=[{}]
    elif fault=='field':etree.SubElement(nodes[ids[-2]].find(W+'r'),W+'fldChar')
    elif fault=='control':rows[ids[-2]]['text']+='\u202e'
    assert closing.derive(*a,version=closing.VERSION_V3,base_context=baseline)==[]


@pytest.mark.parametrize('fault',['ledger_sha','ledger_path','ledger_extra','ledger_missing','group_carrier','extra_flag','missing_flag'])
def test_structural_ledger_is_exact_baseline_bound_not_permission_to_strip(fault):
    a,baseline=proof_args();old_nodes={i:deepcopy(n) for i,n in a[1].items()}
    closing.apply(*a,version=closing.VERSION_V3,base_context=baseline)
    plan=a[6];ledger=plan['source_closing_structural_additions']['paragraphs'];path=ledger[0]['baseline_location']
    if fault=='ledger_sha':ledger[0]['baseline_sha256']='0'*64
    elif fault=='ledger_path':ledger[0]['baseline_location']=a[2][next(iter(a[2]))]['location']
    elif fault=='ledger_extra':ledger.append(deepcopy(ledger[0]))
    elif fault=='ledger_missing':ledger.pop()
    elif fault=='group_carrier':plan['source_closing_groups'][0]['reference_carrier']['structural_locations'].pop()
    elif fault=='extra_flag':etree.SubElement(a[0].xpath(path,namespaces=v3.NS)[0].find(W+'pPr'),W+'pageBreakBefore')
    elif fault=='missing_flag':node=a[0].xpath(path,namespaces=v3.NS)[0].find(W+'pPr');node.remove(node.find(W+'keepNext'))
    with pytest.raises(ValueError):closing.verify(a[0],{'paragraphs':list(a[2].values())},*a[3:],old_nodes,base_context=baseline)


def test_new_fresh_identity_keeps_v7_named_hash_and_capabilities():
    old=auto._terminal_footer_membership_v7_policy();new=auto._in_body_terminal_closing_v8_policy()
    assert new==auto._in_body_terminal_closing_v8_policy() and new!=old
    assert auto._band_normalization_version(old.split(':')[1])==c.BAND_NORMALIZATION_V7
    assert auto._terminal_source_layout_versions(old.split(':')[1])['source_closing_group_version']==closing.VERSION_V2
    assert auto._band_normalization_version(new.split(':')[1])==c.BAND_NORMALIZATION_V8
    assert auto._terminal_source_layout_versions(new.split(':')[1])['source_closing_group_version']==closing.VERSION_V3
    assert old in auto._metadata_normalization_policies() and old in auto._source_folio_policies()


@pytest.mark.parametrize('count',[1,2])
def test_plain_retained_terminal_association_needs_no_reference_frame(count):
    args=fixture();snapshot,pages,decisions,context,proposal,view=args[1:]
    ids=[p['id'] for p in snapshot['paragraphs']]
    if count==1:
        # The final reference itself is the complete retained footer suffix.
        decisions['paragraphs'][-2]['role']='signature'
        text='Witness: ____________________'
        # Rebuild source evidence from a wholly fictional source instead of editing snapshot hashes.
        raw=document_bytes([p['text'] if p['id']!=ids[-2] else text for p in snapshot['paragraphs']])
        snapshot,pages,new=reviewed(raw,'AR');new.update(decisions)
        decisions=new;args=args[:1]+(snapshot,pages,decisions,context,proposal,view)
        decisions['paragraphs'][-1]['role']='reference'
        proposal['paragraphs'][-2]['role']='signature';proposal['paragraphs'][-1]['role']='reference'
        proposal['source_layout_evidence'][0]['paragraph_ids']=ids[-1:]
    target=decisions['paragraphs'][-count]
    target['regions'][0]['bbox_px']=[100,1300,900,1320]
    proposal['paragraphs'][-count]['bbox']=[.1,1300/1400,.9,1320/1400]
    proposal['source_layout_evidence'][0]['bbox']=[.05,.9,.95,.99]
    # The optional association still preserves reference roles and body placement.
    view={'pages':pages,'decisions':decisions,'paragraphs':snapshot['paragraphs']}
    context['source_evidence']['pages']=[c.proposal_source_evidence(snapshot,view,proposal,band_normalization_version=c.BAND_NORMALIZATION_V8)]
    artifact=writer.build_unreviewed_docx(args[0] if count==2 else raw,snapshot,pages,decisions,ordinary_context=context)
    group=artifact.source_map['source_layout_plan']['source_closing_groups'][0]
    assert len(group['footer_ids'])==count and 'reference_carrier' not in group
    assert artifact.source_map['source_layout_plan']['source_closing_structural_additions']['paragraphs']==[]


def test_v3_inherits_existing_promoted_footer_group_without_new_table_permission():
    from tests.test_terminal_closing_group import writer_fixture
    args=list(writer_fixture());args[4]['source_closing_group_version']=closing.VERSION_V2
    old=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    args[4]['source_closing_group_version']=closing.VERSION_V3
    args[4]['source_evidence']['pages'][0]['retained_terminal_associations']={
        'version':c.RETAINED_TERMINAL_ASSOCIATIONS_V1,'canonical_proposal_sha256':'a'*64,
        'associations':[],'review_required':True}
    new=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    assert new.source_map['source_layout_plan']['source_closing_groups']==old.source_map['source_layout_plan']['source_closing_groups']
    assert new.docx_bytes==old.docx_bytes
    assert new.source_map['source_layout_plan']['source_closing_structural_additions']['paragraphs']==[]


@pytest.mark.parametrize('lang,fault',[('EN','absent'),('EN','null'),('EN','empty'),('EN','object'),
    ('AR','absent'),('AR','null'),('AR','object')])
def test_writer_plan_absence_is_language_specific_not_null_or_forgery(lang,fault):
    raw=document_bytes(['Fictional ordinary paragraph.'])
    snapshot,pages,decisions=reviewed(raw,lang)
    decisions['review'].update(document_reviewed=False,pages_reviewed=[],reviewer='',note='')
    context={'selected_pages':[1],'page_groups':[[1,[p['id'] for p in snapshot['paragraphs']]]]}
    artifact=writer.build_unreviewed_docx(raw,snapshot,pages,decisions,ordinary_context=context)
    mapping=deepcopy(artifact.source_map)
    if fault=='absent':mapping.pop('derived_horizontal_plan',None)
    else:mapping['derived_horizontal_plan']={'null':None,'empty':[],'object':{}}[fault]
    forged=writer.SavedDocxLayoutArtifact(artifact.docx_bytes,mapping)
    if lang=='EN' and fault=='absent':v3.baseline_context(forged,snapshot,pages,decisions,context)
    else:
        with pytest.raises(ValueError):v3.baseline_context(forged,snapshot,pages,decisions,context)
