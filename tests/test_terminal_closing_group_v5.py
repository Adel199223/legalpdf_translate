"""Accepted local footer association is distinct from bounded group eligibility."""
from copy import deepcopy
import hashlib
import pytest
from lxml import etree
from legalpdf_translate import ordinary_terminal_closing_group as closing
from legalpdf_translate import ordinary_terminal_closing_v4 as v4
from legalpdf_translate import ordinary_terminal_closing_v5 as v5
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
W=model.W


def fixture(signatures=2):
    from tests.test_terminal_closing_group import fixture as old
    args=old(signatures=signatures)
    root,nodes,mapped,rows,choices,owners,plan,members=args
    plan['source_footers']=[]
    choices['footer']['role']='source_folio'
    for i,n in nodes.items():rows[i]['paragraph_sha256']=model._sha(model._c14n(n).encode())
    associations=[{'source_page_number':1,'accepted_footer':{'kind':'source_footer','paragraph_ids':['footer','folio'],'bbox':[.1,.9,.9,.99]},'canonical_proposal_sha256':'a'*64,'response_sha256':'b'*64}]
    return args,associations


def before_context(args):
    root,nodes,mapped,*_=args
    old=deepcopy(root)
    return {'root':old,'nodes':{i:old.xpath(root.getroottree().getpath(n),namespaces=v5.NS)[0] for i,n in nodes.items()},'mapped':deepcopy(mapped),'members':args[-1]}


def test_local_source_folio_group_without_promotion_and_exact_false_property_inverse():
    args,associations=fixture()
    etree.SubElement(args[1]['sign0'].find(W+'pPr'),W+'keepNext').set(W+'val','false')
    before=before_context(args)
    assert closing.derive(*args,version=closing.VERSION_V4,base_context={})==[]
    closing.apply(*args,version=v5.VERSION,base_context={},local_footer_context=associations)
    assert args[6][v5.LEDGER]==associations
    assert args[6]['source_closing_groups'][0]['kind']==v5.KIND
    closing.verify(args[0],{'paragraphs':list(args[2].values())},args[3],args[4],args[5],args[6],args[7],base_context={},pre_closing_context=before,local_footer_context=associations)


def writer_case():
    from tests.test_saved_docx_layout import document_bytes,reviewed,PAGES
    from legalpdf_translate import ordinary_layout_contracts as contracts
    from legalpdf_translate.docx_writer import _configure_styles,_add_page_number_footer
    raw=document_bytes(['Earlier first source page.','Earlier second source page.','Complete closing context one.','Complete closing context two.','Witness: ____________________','Interpreter: ____________________','Prepared automatically.','1 / 1'],lambda d:(_configure_styles(d,'EN'),_add_page_number_footer(d,'EN')))
    frames=deepcopy(PAGES)+[{**deepcopy(PAGES[0]),'page_number':2,'image_sha256':'2'*64}]
    snapshot,pages,decisions=reviewed(raw,'EN',frames)
    ids=[r['id'] for r in snapshot['paragraphs']]
    decisions['review'].update(document_reviewed=False,pages_reviewed=[],reviewer='',note='')
    decisions['bands']=[{'kind':'flow','groups':[{'paragraph_ids':[i],'panel':False}]} for i in ids]
    for index,row in enumerate(decisions['paragraphs']):
        page=1 if index==0 else 2
        row.update(role='signature' if index in (4,5) else 'source_folio' if index>=6 else 'body',regions=[{'page_number':page,'bbox_px':[200,1290,800,1350] if index>=6 else [100,100,800,200]}])
    records=[]
    for page,owned in [(1,ids[:1]),(2,ids[1:])]:
        proposal={'version':contracts.PROPOSAL_VERSION_V3,'page_number':page,'paragraphs':[],'bands':[b for b in decisions['bands'] if b['groups'][0]['paragraph_ids'][0] in owned],'paragraph_partitions':[],'source_coverage_findings':[],'source_layout_evidence':[{'kind':'source_footer','paragraph_ids':ids[-2:],'bbox':[.1,.9,.9,.99]}] if page==2 else []}
        for row in decisions['paragraphs']:
            if row['paragraph_id'] not in owned:continue
            choice=deepcopy(row);region=choice.pop('regions')[0];choice.pop('unmapped_reason',None)
            choice['bbox']=[v/(1000 if j%2==0 else 1400) for j,v in enumerate(region['bbox_px'])]
            proposal['paragraphs'].append(choice)
        record=contracts.proposal_source_evidence(snapshot,{'paragraphs':snapshot['paragraphs'],'pages':pages,'decisions':decisions},proposal,band_normalization_version=contracts.BAND_NORMALIZATION_V8)
        record['response_sha256']=contracts.digest(contracts.encode(proposal))
        records.append(record)
    context={'selected_pages':[1,2],'page_groups':[[1,ids[:1]],[2,ids[1:]]],'source_evidence':{'version':'ordinary_source_evidence_v1','pages':records},'source_footer_placement_version':'terminal_body_flow_v1','source_spacing_version':'baseline_metadata_heading_spacing_v1','source_closing_group_version':v5.VERSION}
    return raw,snapshot,pages,decisions,context


def test_public_strict_writer_requalifies_local_footer_with_global_holdback():
    args=writer_case()
    artifact=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    writer.validate_built_docx(artifact.docx_bytes,artifact.source_map,original_docx=args[0],snapshot=args[1],pages=args[2],decisions=args[3],require_review=False,ordinary_context=args[4])
    plan=artifact.source_map['source_layout_plan']
    assert plan['source_footers']==[] and len(plan[v5.LEDGER])==1
    assert len(plan['source_closing_groups'])==1
    old_context={**args[4],'source_closing_group_version':v4.VERSION}
    old=writer.build_unreviewed_docx(*args[:4],ordinary_context=old_context)
    assert old.source_map['source_layout_plan']['source_closing_groups']==[]
@pytest.mark.parametrize('fault',['wrong_footer_role','seventh_signature','single_signature','parts','field','numbering','unsafe_control','interposed','incoming','outgoing','duplicate_owner','wrong_page','unlabelled','whole_page'])
def test_new_local_class_refuses_ambiguous_or_unsafe_owners(fault):
    args,associations=fixture(signatures=7 if fault=='seventh_signature' else 1 if fault=='single_signature' else 2)
    root,nodes,mapped,rows,choices,owners,plan,members=args
    if fault=='wrong_footer_role':choices['footer']['role']='body'
    elif fault=='parts':mapped['sign0']['parts']=[{'location':'unowned'}]
    elif fault=='field':rows['sign0']['has_field']=True
    elif fault=='numbering':rows['sign0']['has_numbering']=True
    elif fault=='unsafe_control':rows['sign0']['text']='Name: ______\u202e'
    elif fault=='interposed':root.find(W+'body').insert(2,etree.Element(W+'p'))
    elif fault=='incoming':etree.SubElement(nodes['outside'].find(W+'pPr'),W+'keepNext')
    elif fault=='outgoing':etree.SubElement(nodes['folio'].find(W+'pPr'),W+'keepNext')
    elif fault=='duplicate_owner':owners[2]=['sign0']
    elif fault=='wrong_page':associations[0]['source_page_number']=2
    elif fault=='unlabelled':
        for i in ['sign0','sign1']:
            rows[i]['text']='______';nodes[i].find(W+'r/'+W+'t').text='______'
    elif fault=='whole_page':
        owners[1].remove('outside');nodes['outside'].getparent().remove(nodes['outside'])
    assert v5.derive(*args,associations)==[]


@pytest.mark.parametrize('fault',['seven','raw_signature','raw_footer'])
def test_new_work_bounds_precede_signature_regex_and_xml_inventory(monkeypatch,fault):
    args,associations=fixture(signatures=7 if fault=='seven' else 2)
    if fault=='raw_signature':args[3]['sign0']['text']='Name: '+'_'*1600
    if fault=='raw_footer':args[3]['footer']['text']='x'*1601
    monkeypatch.setattr(closing,'_signature',lambda *_:pytest.fail('Regex ran before bounded refusal'))
    monkeypatch.setattr(v4,'_owned',lambda *_a,**_k:pytest.fail('Inventory ran before bounded refusal'))
    assert v5.derive(*args,associations)==[]


@pytest.mark.parametrize('fault',['false_empty','subset','extra','page_float','role_bool','wrong_identity','property_removed','unrelated_property'])
def test_independent_rederivation_rejects_ledger_group_and_xml_forgery(fault):
    args,associations=fixture();before=before_context(args)
    closing.apply(*args,version=v5.VERSION,base_context={},local_footer_context=associations)
    if fault in {'false_empty','subset'}:args[6][v5.LEDGER]=[]
    elif fault=='extra':args[6][v5.LEDGER].append(deepcopy(associations[0]))
    elif fault=='page_float':args[6][v5.LEDGER][0]['source_page_number']=1.0
    elif fault=='wrong_identity':args[6][v5.LEDGER][0]['canonical_proposal_sha256']='c'*64
    elif fault=='role_bool':args[6]['source_closing_groups'][0]['paragraph_proofs'][0]['role']=True
    elif fault=='property_removed':args[1]['sign0'].find(W+'pPr').remove(args[1]['sign0'].find(W+'pPr/'+W+'keepLines'))
    else:etree.SubElement(args[1]['outside'].find(W+'pPr'),W+'keepLines')
    with pytest.raises(ValueError):
        closing.verify(args[0],{'paragraphs':list(args[2].values())},args[3],args[4],args[5],args[6],args[7],base_context={},pre_closing_context=before,local_footer_context=associations)


def test_complete_accepted_ledger_does_not_filter_a_non_group_footer():
    args=list(writer_case())
    args[3]['paragraphs'][-2]['role']='body'
    result=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    plan=result.source_map['source_layout_plan']
    assert len(plan[v5.LEDGER])==1 and plan['source_closing_groups']==[]
    assert plan[v5.LEDGER][0]['accepted_footer']['paragraph_ids']==args[4]['page_groups'][-1][1][-2:]


@pytest.mark.parametrize('fault',['null_identity','missing_response','wrong_page','rejected_only'])
def test_local_association_requalification_never_uses_claimed_direction_or_rejection(fault):
    args=list(writer_case());evidence=args[4]['source_evidence']
    if fault=='null_identity':evidence['pages'][1]['retained_terminal_associations']['canonical_proposal_sha256']=None
    elif fault=='missing_response':evidence['pages'][1].pop('response_sha256')
    elif fault=='wrong_page':evidence['pages'][1]['page_number']=2.0
    else:evidence['pages'][1]['layout']=[]
    if fault=='rejected_only':
        result=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
        assert result.source_map['source_layout_plan'][v5.LEDGER]==[]
        assert result.source_map['source_layout_plan']['source_closing_groups']==[]
    else:
        with pytest.raises(ValueError):writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])


def test_V5_delegates_complete_promoted_V4_and_preserves_concrete_V16_pair(monkeypatch):
    from tests.test_terminal_closing_group_v4 import writer_case as oldcase
    from legalpdf_translate import ordinary_auto_layout as auto,ordinary_layout_reproposal as attempts
    args=oldcase();old=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    args[4]['source_closing_group_version']=v5.VERSION
    new=writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])
    assert new.docx_bytes==old.docx_bytes and new.source_map['source_layout_plan'][v5.LEDGER]==[]
    assert new.source_map['source_layout_plan']['source_closing_groups']==old.source_map['source_layout_plan']['source_closing_groups']
    old_policy,new_policy=auto._bounded_signature_label_v16_policy(),auto._local_footer_closing_v17_policy()
    monkeypatch.setattr(auto, 'frozen_automatic_layout_policy', auto._local_footer_closing_v17_policy)
    assert auto.frozen_automatic_layout_policy()==new_policy and new_policy!=old_policy
    assert auto._terminal_source_layout_versions(old_policy.split(':')[1])['source_closing_group_version']==v4.VERSION
    assert auto._terminal_source_layout_versions(new_policy.split(':')[1])['source_closing_group_version']==v5.VERSION
    assert old_policy in auto._source_folio_policies() and old_policy in auto._metadata_normalization_policies()
    assert attempts.automatic_policy(attempts.POLICY_V2,new_policy.split(':')[1])==new_policy
    with pytest.raises(ValueError):attempts.automatic_policy(attempts.POLICY,new_policy.split(':')[1])


def test_historical_V17_Start_has_mandatory_empty_ledger_and_saved_zero_call_reuse(tmp_path,monkeypatch):
    import json,os
    from pathlib import Path
    from legalpdf_translate import ordinary_auto_layout as auto,ordinary_layout_reproposal as attempts
    from legalpdf_translate.ordinary_layout_contracts import decode
    from tests import test_ordinary_layout_reproposal as lifecycle
    lifecycle.isolate_provider(monkeypatch)
    with monkeypatch.context() as historical:
        historical.setattr(auto, 'frozen_automatic_layout_policy', auto._local_footer_closing_v17_policy)
        assert auto.frozen_automatic_layout_policy()==auto._local_footer_closing_v17_policy()
        case=lifecycle.normal_start(tmp_path,monkeypatch)
    result=case.job['result']['automatic_layout']
    assert result['status']=='automatic_unreviewed',result
    witness,context=lifecycle.witness_context(case)
    assert len(attempts.verify_witness(witness,**context)[0])==3
    mapping=decode((Path(result['output_path']).parent/'source_map.json').read_bytes())
    plan=mapping['source_layout_plan']
    assert plan['source_closing_group_version']==v5.VERSION and plan[v5.LEDGER]==[]
    assert plan['source_closing_groups']==[]  # Generic retained actual25 separately covers the nonempty new class.
    before={p:p.read_bytes() for p in case.operation.rglob('*') if p.is_file() and p.suffix!='.lock'}
    reused=auto.run_completed_unreviewed_rebuild(case.manager,case.app.state.ordinary_layouts._accounting,case.job['job_id'])
    assert reused['reused_durable_candidate'] and reused['sha256']==result['sha256'] and len(case.calls)==3
    assert all(p.read_bytes()==raw for p,raw in before.items())
    index=os.environ.get('CLOSING_V17_SPECIMEN_INDEX')
    if index:Path(index).write_text(json.dumps({'job':case.job,'operation':str(case.operation),'pointer':case.pointer,'baseline':case.baseline,'layout_requests':case.calls,'new_group_count':0,'qualification':'genuine TestClient current Start identity/public/reuse; retained actual25 strict writer owns nonempty group proof'},ensure_ascii=False,indent=2,default=str),encoding='utf8')
