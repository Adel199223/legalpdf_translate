from copy import deepcopy
from io import BytesIO
import pytest
from docx import Document
from legalpdf_translate.saved_docx_layout import inspect_docx, default_decisions, validate_decisions, SavedDocxLayoutError
from legalpdf_translate.ordinary_layout_contracts import normalize_proposals, proposal_source_evidence, source_evidence_review_fields, OrdinaryLayoutError, PROPOSAL_VERSION_V3

def fixture():
    d=Document()
    for text in ["Office", "Reference", "Recipient"]: d.add_paragraph(text)
    b=BytesIO();d.save(b);s=inspect_docx(b.getvalue(),"EN")
    pages=[{"page_number":1,"width_px":1000,"height_px":1400,"image_sha256":"a"*64}]
    choices=default_decisions(s,pages)
    for row in choices["paragraphs"]:row["regions"]=[{"page_number":1,"bbox_px":[10,10,100,100]}]
    v={"decisions":choices,"pages":pages,"paragraphs":s["paragraphs"]}
    rows=[]
    for row in choices["paragraphs"]:
        r=deepcopy(row);r.pop("regions");r.pop("unmapped_reason");r.update(bbox=[.1,.1,.5,.2],role="reference");rows.append(r)
    p={"version":PROPOSAL_VERSION_V3,"page_number":1,"paragraphs":rows,"bands":[{"kind":"columns","widths_pct":[60,40],"gutter_pt":18,"cells":[{"groups":[{"paragraph_ids":["p000001","p000003"],"panel":False}]},{"groups":[{"paragraph_ids":["p000002"],"panel":False}]}]}],"paragraph_partitions":[],"source_layout_evidence":[],"source_coverage_findings":[]}
    return s,v,p

def test_generated_metadata_downgrade_preserves_choices_and_manual_guard():
    s,v,p=fixture();original=deepcopy(p);result=normalize_proposals(s,v,[p]);assert p==original
    assert result["bands"]==[{"kind":"flow","groups":[{"paragraph_ids":["p000001","p000002","p000003"],"panel":False}]}]
    assert [x["paragraph_id"] for x in result["paragraphs"]]==[x["id"] for x in s["paragraphs"]]
    record=proposal_source_evidence(s,v,p);assert source_evidence_review_fields([record])["source_layout_review_required"]
    authored=deepcopy(result);authored["bands"]=p["bands"]
    with pytest.raises(SavedDocxLayoutError):validate_decisions(s,v["pages"],authored)
    with pytest.raises(OrdinaryLayoutError):normalize_proposals(s,v,[p],band_normalization_version=None)

@pytest.mark.parametrize("mutation",["duplicate","missing","body","list","panel","partition","field","numbering","control"])
def test_unsafe_or_incomplete_band_is_not_rescued(mutation):
    s,v,p=fixture()
    if mutation=="duplicate":p["bands"][0]["cells"][0]["groups"][0]["paragraph_ids"]=["p000001","p000002"]
    elif mutation=="missing":p["bands"][0]["cells"][0]["groups"][0]["paragraph_ids"]=["p000001"]
    elif mutation in {"body","list"}:p["paragraphs"][0]["role"]=mutation
    elif mutation=="panel":p["bands"][0]["cells"][0]["groups"][0]["panel"]=True
    elif mutation=="partition":p["paragraph_partitions"]=[{"paragraph_id":"p000001","anchors":["Office"]}]
    elif mutation=="field":s["paragraphs"][0]["tokens"].append({"kind":"tab","text":"\t"})
    elif mutation=="numbering":s["paragraphs"][0]["ppr_xml"]="<w:numPr/>"
    else:s["paragraphs"][0]["tokens"][0]["text"]="Office\u202e"
    with pytest.raises((OrdinaryLayoutError,SavedDocxLayoutError)):normalize_proposals(s,v,[p])

@pytest.mark.parametrize("mutation",["width","sum","emptycell","emptygroup"])
def test_invalid_container_schema_cannot_be_erased(mutation):
    s,v,p=fixture();b=p["bands"][0]
    if mutation=="width":b["widths_pct"]=[99,1]
    elif mutation=="sum":b["widths_pct"]=[60,40.005]
    elif mutation=="emptycell":b["cells"].append({"groups":[]});b["widths_pct"]=[40,30,30]
    else:b["cells"][0]["groups"].append({"paragraph_ids":[],"panel":False})
    with pytest.raises((OrdinaryLayoutError,SavedDocxLayoutError)):normalize_proposals(s,v,[p])
