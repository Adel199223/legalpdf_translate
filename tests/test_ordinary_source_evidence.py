from copy import deepcopy
import pytest
from legalpdf_translate.ordinary_layout_contracts import (PROPOSAL_VERSION_V2, PROPOSAL_VERSION_V3, proposal_schema, proposal_source_evidence, OrdinaryLayoutError)

def fixture():
    snapshot={"paragraphs":[{"id":"p000001","tokens":[{"kind":"t","text":"AB123"}]}]}
    view={"paragraphs":[{"id":"p000001","text":"AB123"}],"decisions":{"paragraphs":[{"paragraph_id":"p000001","regions":[{"page_number":1,"bbox_px":[1,1,20,20]}]}]}}
    proposal={"version":PROPOSAL_VERSION_V3,"page_number":1,"paragraphs":[{"paragraph_id":"p000001","role":"body"}],"bands":[{"kind":"flow","groups":[{"paragraph_ids":["p000001"],"panel":False}]}],"paragraph_partitions":[],"source_layout_evidence":[],"source_coverage_findings":[]}
    return snapshot,view,proposal

def finding():
    return {"kind":"missing_readable_literal","literal":"A","source_bbox":[.1,.1,.2,.2],"insertion_context":{"paragraph_id":"p000001","position":"before"}}

def test_occurrence_proposals_not_deduplicated_by_identifier_substring():
    s,v,p=fixture();p["source_coverage_findings"]=[finding(),finding()]
    result=proposal_source_evidence(s,v,p)
    assert len(result["findings"])==2
    assert result["findings"][0]["finding_id"]!=result["findings"][1]["finding_id"]
    assert result["source_coverage_verified"] is False
    assert result["findings"][0]["review_status"]=="unresolved"

@pytest.mark.parametrize("mutation",["control","blank","unknown","reverse","boolean","nan"])
def test_invalid_finding_refuses(mutation):
    s,v,p=fixture();f=finding();p["source_coverage_findings"]=[f]
    if mutation=="control":f["literal"]="A\u202e"
    elif mutation=="blank":f["literal"]=" "
    elif mutation=="unknown":f["insertion_context"]["paragraph_id"]="p000002"
    elif mutation=="reverse":f["source_bbox"]=[.2,.1,.1,.2]
    elif mutation=="boolean":f["source_bbox"][0]=True
    else:f["source_bbox"][0]=float("nan")
    with pytest.raises(OrdinaryLayoutError):proposal_source_evidence(s,v,p)

def test_v2_schema_remains_available_and_empty_v3_never_certifies():
    old=proposal_schema(1,["p000001"],version=PROPOSAL_VERSION_V2)
    assert "source_coverage_findings" not in old["schema"]["properties"]
    assert proposal_schema(1,["p000001"])["schema"]["properties"]["version"]["enum"]==[PROPOSAL_VERSION_V3]
    assert proposal_source_evidence(*fixture())["source_coverage_verified"] is False


def test_decorative_rule_requires_whole_plain_source_rule():
    s,v,p=fixture();s['paragraphs'][0]['tokens']=[{'kind':'t','text':'____'}]
    p['source_layout_evidence']=[{'kind':'decorative_rule','paragraph_ids':['p000001'],'bbox':[.1,.4,.9,.41]}]
    assert proposal_source_evidence(s,v,p)['layout']==p['source_layout_evidence']
    for mutation in ['mixed','signature','height','panel','numbering','control']:
        ss,vv,pp=deepcopy((s,v,p))
        if mutation=='mixed':ss['paragraphs'][0]['tokens'][0]['text']='name ____'
        elif mutation=='signature':pp['paragraphs'][0]['role']='signature'
        elif mutation=='height':pp['source_layout_evidence'][0]['bbox'][3]=.5
        elif mutation=='panel':pp['bands'][0]['groups'][0]['panel']=True
        elif mutation=='numbering':ss['paragraphs'][0]['ppr_xml']='<w:numPr/>'
        else:ss['paragraphs'][0]['tokens'].append({'kind':'tab','text':'\t'})
        with pytest.raises(OrdinaryLayoutError):proposal_source_evidence(ss,vv,pp)


def test_footer_requires_terminal_bottom_plain_ownership():
    s,v,p=fixture();p['source_layout_evidence']=[{'kind':'source_footer','paragraph_ids':['p000001'],'bbox':[.1,.9,.9,.98]}]
    s['paragraphs'][0]['tokens'].append({'kind':'page_break','text':''})
    assert proposal_source_evidence(s,v,p)['layout']==p['source_layout_evidence']
    for mutation in ['midpage','role','interiorbreak','partition','malformedgroup']:
        ss,vv,pp=deepcopy((s,v,p))
        if mutation=='midpage':pp['source_layout_evidence'][0]['bbox'][1]=.5
        elif mutation=='role':pp['paragraphs'][0]['role']='signature'
        elif mutation=='interiorbreak':ss['paragraphs'][0]['tokens'].reverse()
        elif mutation=='partition':pp['paragraph_partitions']=[{'paragraph_id':'p000001','split_before':['x']}]
        else:pp['bands'][0]['groups'][0]['paragraph_ids']=[[]]
        with pytest.raises(OrdinaryLayoutError):proposal_source_evidence(ss,vv,pp)


def test_historical_evidence_is_absent_without_relabeling():
    s,v,p=fixture();p['version']=PROPOSAL_VERSION_V2
    p.pop('source_layout_evidence');p.pop('source_coverage_findings')
    assert proposal_source_evidence(s,v,p)=={'version':'ordinary_source_evidence_v1','findings':[],'layout':[]}


def test_candidate_binds_source_finding_sidecar_and_detects_tampering(tmp_path):
    from dataclasses import replace
    import json
    from runpy import run_path
    _candidate_fixture=run_path(str(__import__("pathlib").Path(__file__).with_name("test_ordinary_auto_layout_artifacts.py")))["_candidate_fixture"]
    from legalpdf_translate.ordinary_auto_layout_artifacts import build_unreviewed_candidate,verify_unreviewed_candidate,OrdinaryAutoArtifactError
    raw,snapshot,frames,decisions,evidence,_=_candidate_fixture(tmp_path)
    evidence['source_evidence']={'version':'ordinary_source_evidence_v1','pages':[{'page_number':2,'findings':[finding()],'layout':[],'source_coverage_verified':False}]}
    artifact=build_unreviewed_candidate(raw,snapshot,frames,decisions,proposal_evidence=evidence)
    assert artifact.source_map['source_evidence']==evidence['source_evidence']
    changed=deepcopy(artifact.source_map);changed['source_evidence']['pages'][0]['findings'][0]['literal']='B'
    encoded=json.dumps(changed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    import hashlib
    tampered=replace(artifact,source_map_bytes=encoded,source_map_sha256=hashlib.sha256(encoded).hexdigest())
    with pytest.raises((OrdinaryAutoArtifactError,ValueError)):verify_unreviewed_candidate(raw,snapshot,frames,decisions,tampered,proposal_evidence=evidence)
