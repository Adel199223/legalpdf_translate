"""V2 whitespace projection owns source fields, never arbitrary raw prose."""
from copy import deepcopy
import re

import fitz
import pytest

from legalpdf_translate import ordinary_ocr_source_spans as spans
from legalpdf_translate import ordinary_ocr_visual_source as source

CASE, BAD, REF = "307/25.3ABCDE", "307/25.3ACDE", "918663"
MAIL, BADMAIL = "porto.juizo@tribunal.org.pt", "porto.juizo@tribunal.gov.pt"
ADDRESS, POSTCODE = "Palácio da Justiça - Rua do Pinhal", "4150-307 Porto"
DATE, MAILREF, TRACK = "Data de envio: 12-11-2025", "83-20088221", "RR 818384848 PT"
FOLLOW = "Exmo Senhor"


def data():
    groups = [("mailing", [DATE, MAILREF, TRACK]), ("mailing_follow", [FOLLOW]),
              ("head", [f"{CASE} [{REF}]"]), ("address", [ADDRESS, POSTCODE]),
              ("email", [MAIL]), ("case", [f"Processo nº {CASE}"]),
              ("reference", [f"Referência deste documento: {REF}"])]
    rows = ["Tribunal do exemplo", ADDRESS.replace("da", "de", 1), POSTCODE, BADMAIL,
            f"Processo nº {BAD}", f"Referência deste documento: {REF}", DATE, MAILREF,
            " ".join(TRACK.replace(" ", "")), FOLLOW, "Observação 654/22.7XYZ com 83 dias."]
    return rows, groups


@pytest.mark.parametrize("separator", ["\n", "  ", " ", "\r\n", "\t"])
def test_virtual_rows_keep_all_words_and_original_order(separator):
    rows, groups = data()
    raw = separator.join(rows)
    virtual, proof = spans.project(raw, groups)
    assert re.sub(r"\s+", "", virtual) == re.sub(r"\s+", "", raw)
    assert "654/22.7XYZ" in virtual and "83 dias." in virtual
    assert proof["raw_sha256"] == source._sha(raw)
    assert len(proof["owners"]) == 8
    assert all(raw[o["start"]:o["end"]].strip() and source._sha(raw[o["start"]:o["end"]]) == o["raw_sha256"]
               for o in proof["owners"])
    effective, obligations = source._derive(virtual, groups)
    assert effective.startswith(f"{CASE} [{REF}]\n") and effective.count(CASE) == 2
    assert MAIL in effective and BADMAIL not in effective and ADDRESS in effective
    assert effective.count(MAILREF) == effective.count(TRACK.replace(" ", "")) == 1
    assert obligations["headers"] == [[CASE, REF]]


def test_wrapped_words_and_spaced_email_still_have_one_complete_owner():
    rows, groups = data()
    raw = " ".join(rows).replace("porto.juizo", "porto. juizo")
    raw = "\n".join(raw.split())
    virtual, _ = spans.project(raw, groups)
    effective, _ = source._derive(virtual, groups)
    assert MAIL in effective and ADDRESS in effective
    assert re.sub(r"\s+", "", virtual) == re.sub(r"\s+", "", raw)


def test_source_bound_following_row_owns_alternate_raw_block_order():
    rows, groups = data()
    raw = " ".join(rows[:4]+[MAILREF,FOLLOW]+rows[4:7]+rows[-1:])
    virtual, proof = spans.project(raw, groups)
    assert virtual.index(MAILREF) < virtual.index(DATE)
    assert "mailing_follow" in [o["role"] for o in proof["owners"]]
    effective, _ = source._derive(virtual, groups)
    assert TRACK.replace(" ", "") in effective
    with pytest.raises(ValueError, match="requires_review"):
        spans.project(raw, [g for g in groups if g[0] != "mailing_follow"])


@pytest.mark.parametrize("damage", [
    "duplicate_email", "near_duplicate_email", "duplicate_case", "duplicate_reference", "lost_reference",
    "crossing_claims", "repeated_source_mail", "larger_identifier", "unrelated_case_reference_gap",
    "postal_after_track", "postal_before_ref", "spaced_wrong_track", "reversed_tracking",
    "foreign_reference", "foreign_postcode", "wrong_follow", "stray_follow_gap",
])
def test_ambiguous_or_foreign_raw_owners_never_become_virtual_authority(damage):
    rows, groups = data();raw = " ".join(rows)
    if damage == "duplicate_email": raw += " " + BADMAIL
    elif damage == "near_duplicate_email": raw += " porto.juizo2@tribunal.gov.pt"
    elif damage == "duplicate_case": raw += f" Processo nº {BAD}"
    elif damage == "duplicate_reference": raw += f" Referência deste documento: {REF}"
    elif damage == "lost_reference": raw = raw.replace(f"Referência deste documento: {REF}", "Outra matéria")
    elif damage == "crossing_claims": groups.append(("address", [ADDRESS, POSTCODE]))
    elif damage == "repeated_source_mail": groups.append(("email", [MAIL]))
    elif damage == "larger_identifier": raw = raw.replace(MAILREF, "0" + MAILREF)
    elif damage == "unrelated_case_reference_gap": raw = raw.replace(f"Referência deste documento: {REF}", f"Outro pedido Referência deste documento: {REF}")
    elif damage == "postal_after_track": raw = raw.replace(FOLLOW, "83-20088222 " + FOLLOW)
    elif damage == "postal_before_ref": raw = raw.replace(MAILREF, "83-20088222 " + MAILREF)
    elif damage == "spaced_wrong_track": raw = raw.replace(" ".join(TRACK.replace(" ", "")), "R R 8 1 8 3 8 4 8 4 O P T")
    elif damage == "reversed_tracking": raw = raw.replace(MAILREF + " " + " ".join(TRACK.replace(" ", "")), " ".join(TRACK.replace(" ", "")) + " " + MAILREF)
    elif damage == "foreign_reference": groups[-1] = ("reference", ["Referência deste documento: 918664"])
    elif damage == "foreign_postcode": groups[3] = ("address", [ADDRESS, "4150-308 Porto"])
    else:
        raw = " ".join(rows[:4]+[MAILREF,FOLLOW]+rows[4:7]+rows[-1:])
        raw = raw.replace(FOLLOW, "Exmo Advogado" if damage == "wrong_follow" else "Outro pedido " + FOLLOW)
    with pytest.raises(ValueError, match="requires_review"):
        spans.project(raw, groups)


def test_missing_tracking_is_not_recovered_over_conflicting_inline_postal_token():
    rows, groups = data()
    raw = " ".join(rows).replace(" ".join(TRACK.replace(" ", "")), "RR81838484OPT")
    with pytest.raises(ValueError, match="requires_review"):
        spans.project(raw, groups)


@pytest.mark.parametrize("prefix", ["porto informa", "porto. titular", "porto porto"])
def test_email_prefix_in_unrelated_prose_is_never_part_of_email_owner(prefix):
    raw = prefix + " " + BADMAIL
    groups = [("email", [MAIL])]
    virtual, proof = spans.project(raw, groups)
    effective, _ = source._derive(virtual, groups)
    assert effective == prefix + "\n" + MAIL
    assert raw[proof["owners"][0]["start"]:proof["owners"][0]["end"]] == BADMAIL


@pytest.mark.parametrize("code", ["rr818384848pt", "rr81838484opt", "rr818384849pt"])
def test_lowercase_postal_value_cannot_hide_beside_recovered_value(code):
    rows, groups = data()
    raw = " ".join(rows).replace(" ".join(TRACK.replace(" ", "")), code)
    with pytest.raises(ValueError, match="requires_review"):
        spans.project(raw, groups)


def test_metadata_gap_is_bounded_and_requires_the_next_aligned_typed_row(monkeypatch):
    def row(text, y, x=300):
        return {"text":text,"words":[{"text":text,"box":[x,y,180,12]}]}
    monkeypatch.setattr(source,"_plans",lambda *a:[("case",[0])])
    cases = [(80,300,True),(97,300,False),(80,370,False)]
    for y,x,allowed in cases:
        rows = [row(f"Processo nº {CASE}",0),row(f"Referência: {REF}",y,x)]
        assert (len(spans.plans(rows,"",800,None))==2) is allowed
    rows = [row(f"Processo nº {CASE}",0),row("Observação intercalar",30),row(f"Referência: {REF}",60)]
    assert len(spans.plans(rows,"",800,None))==1


def test_no_positive_native_observations_preserves_raw_bytes():
    raw = "\nOriginal  \n\nprosa e 123/45.6XYZ.\r\n"
    virtual, proof = spans.project(raw, [])
    assert virtual == raw and not proof["owners"]


@pytest.mark.parametrize("separator", [" ", "\n", "\t"])
def test_existing_closed_condition_edits_work_across_whitespace_only(separator):
    before="Poderá ocorrer o arquivamento do"
    printed="inquérito se durante a investigação não for"
    after="possível reunir prova bastante dos factos."
    raw="OUTRA MATÉRIA "+separator.join((before+" inquérito ou durante a investigação após "+after).split())+" FIM"
    groups=[("flow_condition",[before,printed,after])]
    virtual, proof=spans.project(raw,groups)
    effective,_=source._derive(virtual,groups)
    assert "".join(virtual.split())=="".join(raw.split())
    assert printed in effective and "OUTRA MATÉRIA" in effective and "FIM" in effective
    for token in ("101/26.5XYZ", "participante", "77777"):
        bad=raw.replace("investigação", "investigação "+token)
        with pytest.raises(ValueError,match="requires_review"):
            spans.project(bad,groups)


def test_existing_standalone_condition_line_keeps_its_own_span(monkeypatch):
    printed="inquérito se durante a investigação não for"
    prior="inquérito ou durante a investigação não foi"
    raw="Outro assunto\r\n  "+prior+"  \r\nOutro fim"
    row={"text":printed,"words":[{"text":printed,"box":[10,20,300,12]}]}
    monkeypatch.setattr(source,"_plans",lambda *a:[])
    assert spans.plans([row],raw,800,None)==[("condition",[0])]
    virtual, proof=spans.project(raw,[("condition",[printed])])
    effective,_=source._derive(virtual,[("condition",[printed])])
    assert effective=="Outro assunto\n"+printed+"\nOutro fim"
    owner=proof["owners"][0]
    assert raw[owner["start"]:owner["end"]]==prior


def test_explicit_v1_saved_derivation_never_uses_v2_and_cross_policy_is_rejected(monkeypatch):
    def no_projection(*args, **kwargs):
        pytest.fail("V1 entered V2 projection")
    monkeypatch.setattr(spans, "plans", no_projection)
    monkeypatch.setattr(spans, "project", no_projection)
    scan = {"dpi":144,"bounds":[0,0,100,100],"png_sha256":"a"*64,"lines":[]}
    monkeypatch.setattr(source, "_scan", lambda *a, **kw:deepcopy(scan))
    raw = "\nOriginal  \n\nprosa e 123/45.6XYZ.\r\n"
    with fitz.open() as doc:
        page = doc.new_page()
        effective, saved = source._build(page, raw, 1, "b"*64, None)
        assert saved["policy"] == source.POLICY and "raw_span_projection" not in saved
        assert source._build(page,raw,1,"b"*64,None,saved,policy=source.POLICY) == (effective,saved)
        with pytest.raises(ValueError, match="evidence_changed"):
            source._build(page,raw,1,"b"*64,None,saved,policy=source.POLICY_V2)


def test_policy_scope_retains_explicit_saved_choice(tmp_path):
    from legalpdf_translate import ocr_text_transport as transport
    for policy in source.SUPPORTED_POLICIES:
        with transport.scope(tmp_path,1,"c"*64,visual_source_policy=policy,pdf_path=tmp_path/'source.pdf'):
            assert transport._SCOPE.get().visual_source_policy == policy
    with pytest.raises(ValueError):
        with transport.scope(tmp_path,1,"c"*64,visual_source_policy="unknown",pdf_path=tmp_path/'source.pdf'):
            pass
