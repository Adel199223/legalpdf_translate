"""Registered postal source ownership, exact primary derivation and old-policy behavior."""
from hashlib import sha256
from types import SimpleNamespace

import fitz
import pytest

from legalpdf_translate import ordinary_source_postal_band as band
from legalpdf_translate import primary_literal_markup as markup
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source


CORE = "RR014691300PT"
LABEL = "73-24681357"
ROWS = [{"core": CORE, "mark": "R", "label": LABEL}]


def token(text):
    return "\u2066[[" + text + "]]\u2069"


def response(core, *, mark="R", separator="\n", label=LABEL):
    return separator.join(("```", "إخطار", token(label), token(mark), token(core), "انتهى", "```"))


@pytest.mark.parametrize("ending", ["\n", "\r\n"])
def test_one_printed_core_is_compacted_with_every_other_character_preserved(ending):
    raw = response(" ".join(CORE), separator=ending)
    derived = band.derive(raw, ROWS)
    assert derived == response(CORE, separator=ending)
    assert len(raw) - len(derived) == 12
    assert band.violation(derived, ROWS) is None
    assert band.derive(derived, ROWS) == derived
    assert band.derive(raw, ()) == raw


@pytest.mark.parametrize("value", [
    CORE.lower(), " ".join(CORE.lower()), " ".join(CORE[:-1]+"R"), "  ".join(CORE),
    "\t".join(CORE), "\u00a0".join(CORE), "\u2009".join(CORE), "\ufeff".join(CORE),
    " \n".join(CORE), "("+" ".join(CORE)+")", "%*"+" ".join(CORE)+"*",
])
def test_foreign_or_nonuniform_tracking_is_never_derived(value):
    raw = response(value)
    assert band.derive(raw, ROWS) == raw
    assert band.violation(raw, ROWS)


@pytest.mark.parametrize("extra", [CORE, " ".join(CORE), "\u00a0".join(CORE), "\u2009".join(CORE),
                                   "\ufeff".join(CORE), "\u2066".join(CORE)])
def test_duplicate_is_refused_even_when_spelled_with_other_spacing_or_controls(extra):
    raw = response(" ".join(CORE)) + "\n" + token(extra)
    assert band.derive(raw, ROWS) == raw
    assert band.violation(raw, ROWS)


@pytest.mark.parametrize("edit", [
    lambda v:v.replace(token("R")+"\n", ""),
    lambda v:v.replace(token("R"), token("R")+"\n"+token("R")),
    lambda v:v.replace(token("R"), token("R")+"\nملاحظة"),
    lambda v:v.replace(token(LABEL), token(LABEL)+"9"),
    lambda v:v.replace(token(LABEL), "داخل "+token(LABEL)+" نص"),
    lambda v:v.replace(token(CORE), "%*"+token(CORE)+"*"),
    lambda v:v.replace(token(CORE), token(CORE)+"\n\n%*"),
    lambda v:v.replace(token("R"), "*\n\n"+token("R")),
])
def test_extra_glyphs_and_displaced_mark_or_label_block_integrity(edit):
    wrong = edit(response(CORE))
    assert band.violation(wrong, ROWS)
    spaced = wrong.replace(token(CORE), token(" ".join(CORE)))
    assert band.derive(spaced, ROWS) == spaced


def test_producer_selection_runs_original_and_normalized_checks():
    raw = response(" ".join(CORE)); source = pretokenize_arabic_source(LABEL+"\n%*"+CORE+"*")
    required = extract_locked_tokens(source)
    settings = {"source_field_policy":"baseline_label_value_v1", "primary_literal_packaging_version":"lossless_source_components_v3", band.KEY:band.POLICY}
    initial, result, _ = markup.evaluate_initial(raw, source, required, 1, settings, postal_rows=ROWS)
    assert initial.raw == raw and initial.transformed == response(CORE) and result.ok
    dropped = response(CORE).replace(token("R")+"\n", "")
    assert not markup.evaluate_compliance(dropped, result, initial, [], source, required, settings, postal_rows=ROWS).ok
    assert not markup.evaluate_initial(response(CORE[:-1]+"7"), source, required, 1, settings, postal_rows=ROWS)[1].ok
    old = dict(settings);del old[band.KEY]
    old_initial, _, _ = markup.evaluate_initial(raw, source, required, 1, old)
    assert old_initial.transformed == raw
    with pytest.raises(markup.PrimaryMarkupError, match="postal_source_binding"):
        markup.evaluate_initial(raw, source, required, 1, old, postal_rows=ROWS)


def test_plain_font_same_encoded_text_has_no_authority(tmp_path):
    path=tmp_path/'input.pdf'
    with fitz.open() as doc:
        page=doc.new_page();page.insert_text((60,100), "%*"+CORE+"*",fontname='helv')
        page.insert_text((60,150), "R "+CORE,fontname='cour');doc.save(path)
    digest=sha256(path.read_bytes()).hexdigest()
    assert band.read_selection(path,[1],digest)=={}
    assert band.read_selection(path,[1],"0"*64)=={}
    assert band.read_selection(path,[1,1],digest)=={}


@pytest.mark.parametrize("mode,expected", [("visible",True),("covered",False),("invisible",False)])
def test_separate_mailing_label_requires_its_own_visible_print(mode,expected):
    with fitz.open() as doc:
        page=doc.new_page()
        page.insert_text((80,90), LABEL,fontname="helv",fontsize=10,render_mode=3 if mode=="invisible" else 0)
        trace=page.get_texttrace()[0]
        if mode=="covered":
            page.draw_rect(fitz.Rect(trace['bbox']),color=None,fill=(1,1,1))
        assert band._visible_label(page,trace) is expected


def test_generic_near_match_cannot_license_a_changed_postal_character():
    source = pretokenize_arabic_source(LABEL + "\n%*" + CORE + "*")
    required = extract_locked_tokens(source)
    old = {"source_field_policy":"baseline_label_value_v1", "primary_literal_packaging_version":"lossless_source_components_v3"}
    wrong = response(CORE.replace("0", "O", 1))
    assert markup.evaluate_initial(wrong,source,required,1,old)[1].ok
    saved = {**old,band.KEY:band.POLICY}
    initial, result, groups = markup.evaluate_initial(response(CORE),source,required,1,saved,postal_rows=ROWS)
    candidate = markup.evaluate_initial(wrong,source,required,1,saved,postal_rows=ROWS)[1]
    assert not candidate.ok and "postal_band_tracking" in candidate.defect_reason
    retry = markup.evaluate_compliance(wrong,result,initial,groups,source,required,saved,postal_rows=ROWS)
    assert not retry.ok


def test_capture_cannot_borrow_or_drop_a_physical_source_record(monkeypatch):
    state=SimpleNamespace(pdf_path='input.pdf',pdf_fingerprint='a'*64,pages={'1':{"source_route":"direct_text","ocr_used":False,"semantic_source_sha256":"bound"}})
    monkeypatch.setattr(band,'read_selection',lambda *_: {'1':ROWS})
    source=pretokenize_arabic_source(LABEL+"\n%*"+CORE+"*");expected=extract_locked_tokens(source)
    data={'source_text':source,'original_source_text':LABEL+"\n%*"+CORE+"*",'image_data_url':'original','expected_ar_tokens':expected,band.FIELD:ROWS,band.ROUTE:'direct_text'}
    recipe={band.KEY:band.POLICY};band.validate_capture(state,recipe,1,data)
    for fields in [{band.FIELD:[]},{band.ROUTE:'unqualified'},{'expected_ar_tokens':[CORE]}, {'image_data_url':None}, {'original_source_text':CORE}]:
        with pytest.raises(ValueError):band.validate_capture(state,recipe,1,{**data,**fields})
    with pytest.raises(ValueError):band.validate_capture(state,{},1,data)
    band.validate_capture(state,{},1,{})
