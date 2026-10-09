from copy import deepcopy
from io import BytesIO

import pytest
from docx import Document
from legalpdf_translate.ordinary_layout_contracts import _generated_emphasis, OrdinaryLayoutError
from legalpdf_translate.saved_docx_layout import inspect_docx, _emphasis, SavedDocxLayoutError

def row(text="Alpha beta gamma."):
    document=Document();document.add_paragraph(text);stream=BytesIO();document.save(stream)
    return inspect_docx(stream.getvalue(),"EN")["paragraphs"][0]

def span(start,end,**changes):
    return {"start":start,"end":end,"bold":True,"italic":False,"underline":False}|changes

def test_drops_only_word_interior_span_and_preserves_valid_styles():
    original=[span(1,5),span(6,10,italic=True)]
    before=deepcopy(original)
    assert _generated_emphasis(row(),original)==[original[1]]
    assert original==before
    with pytest.raises(SavedDocxLayoutError,match="unsafe_emphasis_boundary"):_emphasis(row(),original)

@pytest.mark.parametrize("invalid",[
    span(1,3,unknown=True),span(True,3),span(1,3,bold=1),span(1,3,bold=False),
    span(-1,3),span(1,999),span(3,3),span(5,3),
])
def test_entire_original_shape_is_rejected_before_filtering(invalid):
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(row(),[invalid])

@pytest.mark.parametrize("spans",[[span(6,8),span(1,3)],[span(1,8),span(6,10)]])
def test_bad_order_or_overlap_is_never_hidden_by_dropping(spans):
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(row(),spans)

@pytest.mark.parametrize("text,start,end",[("A/B value",1,3),("A\u200dB value",1,3),("A\u2066B value",1,3),("A—B value",1,3)])
def test_nonlexical_or_control_edges_remain_rejected(text,start,end):
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(row(text),[span(start,end)])

def test_protected_identifier_interior_remains_rejected():
    # Existing literal-token protection remains strict even for lexical endpoints.
    document=Document();p=document.add_paragraph("نص ");run=p.add_run("[[AB123456789CD]]")
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    rtl=OxmlElement("w:rtl");rtl.set(qn("w:val"),"0");run._r.get_or_add_rPr().append(rtl)
    stream=BytesIO();document.save(stream);snapshot=inspect_docx(stream.getvalue(),"AR")
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(snapshot["paragraphs"][0],[span(4,8)])

def test_nontext_token_overlap_remains_rejected():
    value=row();value["tokens"].append({"kind":"tab","start":2,"end":3})
    with pytest.raises(OrdinaryLayoutError):_generated_emphasis(value,[span(1,5)])

@pytest.mark.parametrize("text",["Alpha beta gamma.","École café fin.","نص عربي طويل"])
def test_optional_interior_drop_never_expands_or_rewrites_text(text):
    value=row(text);before=deepcopy(value)
    assert _generated_emphasis(value,[span(1,len(text))])==[]
    assert value==before
