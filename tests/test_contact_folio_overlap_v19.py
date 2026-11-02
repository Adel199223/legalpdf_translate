"""Complete source-owned contact/standalone folio coverage for the V19 renderer."""
from copy import deepcopy
from hashlib import sha256

import fitz
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_reproposal as reproposal
from legalpdf_translate import ordinary_source_folio_proof as proof
from legalpdf_translate import ordinary_source_layout as layout
from tests.test_source_folio_span_proof import fixture

MAIL = "helpdesk@example.pt"


def original(*, damage=None):
    with fitz.open() as doc:
        for n in range(1,4):
            page=doc.new_page(width=1000,height=1400)
            page.insert_text((50,120),"Legal body text goes here.")
            page.insert_text((700,1320),f"{n} / 3",fontsize=10,
                             render_mode=3 if n==1 and damage=="peer_hidden" else 0)
            if n==1 and damage=="peer_overpaint":
                page.draw_rect(fitz.Rect(697,1305,735,1324),color=None,fill=(1,1,1))
            if n==1 and damage=="peer_ambiguous_email":
                page.insert_text((150,1320),"first@example.pt",fontsize=9)
                page.insert_text((345,1320),"second@example.pt",fontsize=9)
            if n==2:
                page.insert_text((320,1320),MAIL,fontsize=10,render_mode=3 if damage=="hidden" else 0,
                                 color=(1,1,1) if damage=="white" else (0,0,0))
                if damage=="duplicate":
                    page.insert_text((200,350),MAIL,fontsize=10)
                if damage=="split_duplicate":
                    page.insert_text((200,350),"helpdesk@",fontsize=10)
                    offset=fitz.get_text_length("helpdesk@",fontsize=10)
                    page.insert_text((200+offset,350),"example.pt",fontsize=10,fontname="Times-Bold")
                if damage=="extra":
                    page.insert_text((485,1320),"another@example.pt",fontsize=10)
                if damage=="overpaint":
                    page.draw_rect(fitz.Rect(315,1302,430,1323),color=None,fill=(1,1,1))
                if damage=="clip":
                    stream=page.get_contents()[-1]
                    data=doc.xref_stream(stream)
                    doc.update_stream(stream,b"q 0 0 345 1400 re W n\n"+data+b"\nQ")
        return doc.tobytes()


def matrix(tmp_path, damage=None):
    pdf=original(damage=damage)
    raw,snap,frames,decisions,evidence,_,_=fixture(tmp_path,labels=(
        "1 / 3",f"البريد: \u2066[[{MAIL} 2]]\u2069 / \u2066[[3]]\u2069","3 / 3"),source=pdf)
    context={"selected_pages":[1,2,3],"page_groups":snap.page_groups,proof.KEY:evidence[proof.KEY],
             proof.CONTACT_KEY:proof.native_contact_scope(pdf,evidence[proof.KEY])}
    choice=next(row for row in decisions["paragraphs"] if row["role"]=="source_folio"
                and row["regions"][0]["page_number"]==2)
    f=evidence[proof.KEY]["folios"][1]["fraction"]["bbox"]
    cy=(f[1]+f[3])/2
    choice["regions"][0]["bbox_px"]=[100,(cy+f[3])*700,900,1360]
    group={"kind":"source_footer","paragraph_ids":[choice["paragraph_id"]],"bbox":[.1,.90,.95,.99]}
    assoc=[{"source_page_number":2,"accepted_footer":group,
            "canonical_proposal_sha256":"a"*64,"response_sha256":"b"*64}]
    return raw,snap.saved_snapshot,frames,decisions,context,choice,assoc


def new_spans(values):
    _,snap,frames,decisions,context,_,assoc=values
    return proof.contact_overlap_spans(snap,frames,decisions,context,assoc)


def coverage(values,spans):
    _,snap,frames,decisions,context,_,_=values
    return proof.complete_mixed_coverage(snap,frames,decisions,context,spans)


def test_positive_source_overlap_and_complete_different_page_carriers(tmp_path):
    values=matrix(tmp_path);_,snap,frames,decisions,context,choice,_=values
    assert context[proof.CONTACT_KEY]["contacts"]["2"]["email_sha256"]==sha256(MAIL.encode()).hexdigest()
    old=proof.direction_target_spans(snap,frames,decisions,context)
    assert 2 not in [s["page_number"] for s in old]
    spans=new_spans(values)
    assert len(spans)==1 and spans[0]["paragraph_id"]==choice["paragraph_id"]
    assert [r["kind"] for r in coverage(values,spans)]==["standalone","contact","standalone"]
    assert spans[0]["response_sha256"]=="b"*64


@pytest.mark.parametrize("damage",["overpaint","hidden","white","clip","duplicate","split_duplicate","extra"])
def test_extracted_contact_must_match_visible_printed_ink_and_be_unique(tmp_path,damage):
    values=matrix(tmp_path,damage)
    assert "2" not in values[4][proof.CONTACT_KEY]["contacts"]
    assert not new_spans(values) and not coverage(values,[])


@pytest.mark.parametrize("damage",["wrong_email","other_email","url","date_or_id","group_x","group_y","touch_x",
    "touch_y","disjoint_x","disjoint_y","wrong_page","missing_member","duplicate_footer","cut","body"])
def test_geometry_and_exact_terminal_match_are_all_required(tmp_path,damage):
    values=matrix(tmp_path);_,snap,frames,decisions,context,choice,associations=values
    ident=choice["paragraph_id"];row=next(r for r in snap["paragraphs"] if r["id"]==ident)
    group=associations[0]["accepted_footer"]
    source=context[proof.KEY]["folios"][1]["fraction"]["bbox"]
    bounds=choice["regions"][0]["bbox_px"]
    if damage=="wrong_email":row["text"]=row["text"].replace(MAIL,"else@example.pt")
    elif damage=="other_email":row["text"]="twice@example.net "+row["text"]
    elif damage=="url":row["text"]=row["text"].replace(MAIL,"https://test/?q="+MAIL)
    elif damage=="date_or_id":row["text"]=row["text"].replace(MAIL,"2026/11/03")
    elif damage=="group_x":group["bbox"][2]=source[0]
    elif damage=="group_y":group["bbox"][3]=source[1]
    elif damage=="touch_x":bounds[2]=source[0]*frames[1]["width_px"]
    elif damage=="touch_y":bounds[1]=source[3]*frames[1]["height_px"]
    elif damage=="disjoint_x":bounds[2]=source[0]*frames[1]["width_px"]-2
    elif damage=="disjoint_y":bounds[1]=source[3]*frames[1]["height_px"]+2
    elif damage=="wrong_page":associations[0]["source_page_number"]=1
    elif damage=="missing_member":group["paragraph_ids"]=["a_different_paragraph"]
    elif damage=="duplicate_footer":associations.append(deepcopy(associations[0]))
    elif damage=="cut":decisions["paragraph_partitions"]=[{"paragraph_id":ident}]
    else:choice["role"]="body"
    if damage in ("wrong_page","missing_member"):
        with pytest.raises(ValueError,match="source_folio_proof_changed"):
            new_spans(values)
    else:
        assert not new_spans(values)


@pytest.mark.parametrize("damage",["wrong_fraction","missing_peer","duplicate","foreign_source","custom_field",
                                   "missing_region","leading_zero","arabic_leading_zero","nonfolio_role"])
def test_incomplete_or_ambiguous_standalone_peer_cannot_remove_generated_page(tmp_path,damage):
    values=matrix(tmp_path);_,snap,_,decisions,context,_,_=values
    spans=new_spans(values);assert len(spans)==1
    peer=next(r for r in decisions["paragraphs"] if r["role"]=="source_folio" and r["regions"][0]["page_number"]==3)
    row=next(r for r in snap["paragraphs"] if r["id"]==peer["paragraph_id"])
    if damage=="wrong_fraction":row["text"]="3 / 4"
    elif damage=="missing_peer":row["text"]=" "
    elif damage=="duplicate":
        other=next(r for r in snap["paragraphs"] if r["id"] in dict(context["page_groups"])[3] and r["id"]!=row["id"])
        other["text"]="3 / 3"
    elif damage=="foreign_source":context[proof.KEY]["folios"][2]["fraction"]=None
    elif damage=="custom_field":row["has_field"]=True
    elif damage=="missing_region":peer["regions"]=[]
    elif damage=="leading_zero":row["text"]="03 / 3"
    elif damage=="arabic_leading_zero":row["text"]="٠٣ / ٣"
    else:peer["role"]="body"
    assert not coverage(values,spans)


def test_actual_v19_inherits_same_proposal_wire_and_v18_stays_resolvable(tmp_path,monkeypatch):
    from pathlib import Path
    from legalpdf_translate.ordinary_layout_contracts import decode,encode
    from tests import test_ordinary_layout_reproposal as lifecycle
    lifecycle.isolate_provider(monkeypatch)
    case=lifecycle.normal_start(tmp_path,monkeypatch)
    result=case.job["result"]["automatic_layout"]
    assert result["status"]=="automatic_unreviewed",result
    witness,context=lifecycle.witness_context(case)
    assert len(reproposal.verify_witness(witness,**context)[0])==3
    plan=decode((Path(result["output_path"]).parent/"source_map.json").read_bytes())["source_layout_plan"]
    assert plan["inline_folio_direction_version"]==layout.INLINE_FOLIO_DIRECTION_V3
    assert plan[layout.MIXED_COVERAGE]==[]
    old=auto._contact_folio_v18_policy().split(":")[1]
    assert auto._source_folio_inline_direction_version(old)==layout.INLINE_FOLIO_DIRECTION_V2
    v18=reproposal.expected_policy(3,reproposal.POLICY_V2,old)
    m=witness["manifest"]
    for n in (1,2,3):
        assert encode(reproposal.page_request(m["initial_view"],n,m["policy"]))==encode(
            reproposal.page_request(m["initial_view"],n,v18))


def test_previously_supported_horizontal_email_member_in_a_mixed_document(tmp_path):
    values=matrix(tmp_path)
    context,choice=values[4],values[5]
    native=context[proof.CONTACT_KEY]["contacts"]["2"];mail=native["email_bbox"]
    f=context[proof.KEY]["folios"][1]["fraction"]["bbox"];cy=(f[1]+f[3])/2
    member=[mail[0]*1000,(cy-.006)*1400,mail[2]*1000,(cy+.006)*1400]
    choice["regions"][0]["bbox_px"]=member
    mixed=new_spans(values)
    assert len(mixed)==1 and mixed[0]["member_basis"]=="same_row_email_overlap"
    assert len(coverage(values,mixed))==3
    member[2]=mail[0]*1000
    assert not new_spans(values)


def test_expensive_ink_comparisons_follow_whole_page_ambiguity_check(monkeypatch):
    with fitz.open(stream=original(),filetype="pdf") as doc:
        for i in range(32):
            doc[1].insert_text((10,40+i*20),MAIL,fontsize=8)
            doc[1].insert_text((500,40+i*20),"2 / 3",fontsize=8)
        pdf=doc.tobytes()
    frames=[{"page_number":i,"width_px":1000,"height_px":1400,"image_sha256":str(i)*64} for i in (1,2,3)]
    calls=[]
    original_ink=proof._native_ink
    def counted(page,trace,box):
        calls.append(page.number)
        return original_ink(page,trace,box)
    monkeypatch.setattr(proof,"_native_ink",counted)
    witness=proof.derive_proof(pdf,frames,[1,2,3],sha256(pdf).hexdigest())
    assert not proof.native_contacts(pdf,witness) and calls==[]
    pdf=original();witness=proof.derive_proof(pdf,frames,[1,2,3],sha256(pdf).hexdigest())
    assert list(proof.native_contacts(pdf,witness))==["2"] and calls==[1,1]


def test_custom_footer_field_remains_unchanged_even_with_all_selected_pages(tmp_path):
    from types import SimpleNamespace
    raw,snap,_,_,_,_,_=matrix(tmp_path)
    members,_=layout.model._package(raw)
    base=SimpleNamespace(docx_bytes=raw)
    plan={"source_footers":[]}
    out=layout._suppress_mixed_footer(members,base,snap,[{"kind":"contact"}],plan)
    assert plan["suppressed_generated_footer_parts"]==["word/footer1.xml"] and out["word/footer1.xml"]!=members["word/footer1.xml"]
    custom=dict(members);custom["word/footer1.xml"]=custom["word/footer1.xml"].replace(b" PAGE ",b" NUMPAGES ")
    plan={"source_footers":[]}
    assert layout._suppress_mixed_footer(custom,base,snap,[{"kind":"contact"}],plan)==custom
    assert "suppressed_generated_footer_parts" not in plan
    extra={**members,"word/footer2.xml":custom["word/footer1.xml"]}
    assert layout._suppress_mixed_footer(extra,base,snap,[{"kind":"contact"}],plan)==extra


def test_corrupt_inherited_font_cannot_abort_an_ordinary_job(monkeypatch):
    import zlib
    from legalpdf_translate import ordinary_source_postal_band as postal
    with fitz.open() as doc:
        page=doc.new_page()
        class Page:
            rect=page.rect
            cropbox_position=page.cropbox_position
            rotation=0
            parent=doc
            def get_fonts(self):
                return [(page.xref,"ttf","Type0","DamagedFont","F1","Identity-H")]
        def corrupt(*_):
            raise zlib.error("bad compressed font")
        monkeypatch.setattr(postal,"_font_program",corrupt)
        trace={"type":0,"opacity":1,"dir":(1.,0.),"color":(0.,),"size":12,"chars":[],"font":"DamagedFont"}
        assert not proof._native_ink(Page(),trace,fitz.Rect(10,10,35,25))

@pytest.mark.parametrize("version,visual", [(layout.INLINE_FOLIO_DIRECTION_V3,None),
                                          (layout.INLINE_FOLIO_DIRECTION_V3,[]),
                                          (layout.INLINE_FOLIO_DIRECTION_V2,{}),(None,{})])
def test_saved_renderer_mode_and_native_source_authority_must_agree(version,visual):
    from legalpdf_translate import saved_docx_layout_writer as writer
    ctx={proof.KEY:{}, "source_evidence":{}}
    if version is not None:
        ctx["source_folio_inline_direction_version"]=version
    if visual is not None:
        ctx[proof.CONTACT_KEY]=visual
    with pytest.raises(layout.model.SavedDocxLayoutError,match="source_inline_folio_direction_version"):
        writer._source_inline_folio_mode(ctx)

@pytest.mark.parametrize("damage",["peer_hidden","peer_overpaint","peer_ambiguous_email",None])
def test_visible_standalone_peer_needs_no_email_but_must_actually_print(tmp_path,damage):
    values=matrix(tmp_path,damage)
    scope=values[4][proof.CONTACT_KEY]
    assert set(scope["contacts"])=={"2"}
    assert len(new_spans(values))==1
    if damage in {"peer_hidden","peer_overpaint"}:
        assert "1" not in scope["visible_folios"] and coverage(values,new_spans(values))==[]
    else:
        assert set(scope["visible_folios"])=={"1","2","3"} and len(coverage(values,new_spans(values)))==3


@pytest.mark.parametrize("change",["page","document","fraction","bbox","missing"])
def test_borrowed_visible_peer_cannot_complete_source_coverage(tmp_path,change):
    values=matrix(tmp_path);scope=values[4][proof.CONTACT_KEY]["visible_folios"]
    if change=="missing":
        del scope["1"]
    else:
        field={"page":"source_page","document":"source_pdf_sha256","fraction":"source_line_sha256","bbox":"fraction_bbox"}[change]
        scope["1"][field]={"page":2,"document":"a"*64,"fraction":"0"*64,"bbox":[0,0,1,1]}[change]
    assert len(new_spans(values))==1 and not coverage(values,new_spans(values))
