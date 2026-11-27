"""Source-owned Arabic first-use pairs, selected-page scope and historical fallback."""

from copy import deepcopy

import pytest

from legalpdf_translate import ordinary_source_acronyms as ac
from legalpdf_translate import primary_literal_markup as markup
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.pdf_text_order import check_primary_page_evidence_policy
from tests.test_workflow_semantic_audit_integration import offline


def tok(s):
    return "\u2066[[" + s + "]]\u2069"


def test_printed_forms_only_across_selected_pages():
    first = "Emitiu a Ordem de Serviço nº 4/2025. A Polícia Judiciária recebeu o relatório da GNR. Foi entregue à PJ."
    second = "A Polícia Judiciária ouviu o agente."
    last = ("Aplica-se o Código de Processo Penal. Nos termos do CPP. Comunique à PJ. "
            "Circular da PGR. Disposição do CPP. (O.S. 4/2025).")
    pages = [(1, first), (2, second), (3, last)]
    one = ac.page_acronyms(first, pages, 1)
    three = ac.page_acronyms(last, pages, 3)
    assert [(r["spelling"],r["modes"]) for r in one] == [("GNR",["gloss"]),("PJ",["gloss"])]
    assert ac.page_acronyms(second, pages, 2) == ()
    assert [(r["spelling"],r["modes"]) for r in three] == [
        ("CPP",["gloss","bare"]),("PJ",["bare"]),("PGR",["uncertain"]),("O.S.",["gloss"])]
    assert three[-1]["source_meaning"] == "Ordem de Serviço"
    assert ac.page_acronyms(last, [(3,last)], 3)[-1]["modes"] == ["uncertain"]
    foreign = last.replace("O.S. 4/2025","O.S. 7/2025")
    assert ac.page_acronyms(foreign, [(1,first),(3,foreign)], 3)[-1]["modes"] == ["uncertain"]


def test_partial_known_aliases_and_unrelated_capitals_do_not_create_obligations():
    s = ("DESPACHO DE ARQUIVAMENTO\nPOLÍCIA JUDICIÁRIA\nNas ruas de BEJA. "
         "Tel. 27. Conta IBAN e NIF. Dos XYZ/26 e da GNR/X. "
         "A Polícia Judiciária enviou o ofício. Em nome de MARIA. Referência A.PJ.12.")
    assert ac.page_acronyms(s, [(1,s)], 1) == ()


def test_approved_source_term_and_explicit_printed_definition():
    line = "A Agência Nacional Fluvial (ANF) comunicou à ANF. Oficie à XYZ."
    entry = {"source_text":"XYZ", "preferred_translation":"الجهة المعتمدة", "source_lang":"PT", "match_mode":"exact"}
    rows = ac.page_acronyms(line, [(1,line)], 1, [entry])
    assert [(r["spelling"],r["modes"]) for r in rows] == [("ANF",["printed","bare"]),("XYZ",["gloss"])]
    assert ac.acronym_violation(tok("XYZ")+" (الجهة المعتمدة)", rows[1:]) is None
    assert ac.acronym_violation(tok("XYZ")+" (جهة أخرى)", rows[1:]) == "acronym_first_gloss"
    bare = deepcopy(entry)
    bare["preferred_translation"] = "XYZ"
    assert ac.page_acronyms(line, [(1,line)], 1, [bare])[1]["modes"] == ["bare"]
    assert ac.page_acronyms(line, [(1,line)], 1)[0]["spelling"] == "ANF"
    assert len(ac.page_acronyms(line, [(1,line)], 1)) == 1


def test_source_count_gloss_location_and_existing_compliance():
    text = "Oficiou à GNR. Registou 690 ofícios. A Polícia Judiciária prestou apoio. Comunicou à PJ. Registe 840 casos."
    rows = ac.page_acronyms(text, [(1,text)], 1)
    prepared = ac.wrap_acronyms(pretokenize_arabic_source(text), rows)
    required = extract_locked_tokens(prepared)
    assert required == ["GNR","690","PJ","840"]
    recipe = {"source_field_policy":"baseline_label_value_v1",
              "primary_literal_packaging_version":"lossless_source_components_v3"}
    val = tok("GNR")+" (الحرس الوطني الجمهوري). سجل "+tok("690")+". تدخلت الشرطة القضائية. أُبلغت "+tok("PJ")+" (الشرطة القضائية). سجل "+tok("840")+"."
    def raw(s):
        return chr(96)*3+"text\n"+s+"\n"+chr(96)*3
    lost = val.replace(tok("GNR")+" (الحرس الوطني الجمهوري)", "الحرس الوطني الجمهوري")
    initial, ev, groups = markup.evaluate_initial(raw(lost), prepared, required, 1, recipe, acronym_rows=rows)
    assert not ev.ok and ev.ar_violation_kind == "expected_token_mismatch"
    repaired = markup.evaluate_compliance(raw(val), ev, initial, groups, prepared, required, recipe, acronym_rows=rows)
    assert repaired.ok, repaired.defect_reason
    for bad, defect in [
        (val.replace(tok("PJ")+" (الشرطة القضائية)", "الشرطة القضائية")+" "+tok("PJ")+" (الشرطة القضائية)", "acronym_source_clause"),
        (val.replace(tok("GNR"),tok("PJ"),1).replace(tok("PJ")+" (الشرطة القضائية)",tok("GNR")+" (الشرطة القضائية)"), "acronym_source_clause"),
        (val.replace(tok("PJ"),tok("PJ")+" "+tok("PJ")), "acronym_occurrence_count"),
        (val.replace(tok("GNR")+" (الحرس الوطني الجمهوري)", tok("GNR")+" إلى (الحرس الوطني الجمهوري)"), "acronym_first_gloss"),
    ]:
        assert ac.acronym_violation(bad,rows) == defect
    assert ac.wrap_acronyms("[[Morada: GNR]]", rows) == "[[Morada: GNR]]"


def test_repeated_email_owners_do_not_create_unfulfillable_separate_tokens():
    source = "da GNR@example.pt e da GNR@example.pt."
    assert ac.page_acronyms(source, [(1, source)], 1) == ()


def test_source_context_glossary_and_competing_preferences():
    s = "A Polícia Judiciária dirigiu o ofício à PJ. Juntou a nota da PJ (por via postal)."
    term = {"source_text":"Polícia Judiciária", "preferred_translation":"الجهة المختصة",
            "source_lang":"PT", "match_mode":"contains"}
    rows = ac.page_acronyms(s, [(1,s)], 1, [term])
    assert rows[0]["modes"] == ["gloss","bare"] and rows[0]["preferred"] == "الجهة المختصة"
    assert ac.acronym_violation(tok("PJ")+" (الجهة المختصة). توضيح "+tok("PJ")+" (عن طريق البريد).", rows) is None
    other = {**term,"source_text":"PJ","preferred_translation":"PJ – اسم آخر"}
    assert ac.page_acronyms(s, [(1,s)], 1, [other])[0]["modes"] == ["configured","bare"]
    assert ac.page_acronyms(s, [(1,s)], 1, [term,other])[0]["modes"] == ["configured","bare"]


def test_first_gloss_is_distinct_from_a_source_citation_and_accepts_wrapped_continuation():
    source = "Nos termos da lei, oficie-se, com cópia do expediente à GNR (artigo 53.º do Código de Processo Penal)."
    rows = ac.page_acronyms(source, [(1, source)], 1)
    assert rows[0]["modes"] == ["gloss"]
    bare_citation = "يؤمر بإرسال نسخة من الملف إلى\n"+tok("GNR")+" (المادة "+tok("53")+" من قانون الإجراءات الجنائية)."
    assert ac.acronym_violation(bare_citation, rows) == "acronym_first_gloss"
    paired = bare_citation.replace(tok("GNR"), tok("GNR")+" (الحرس الوطني الجمهوري)")
    assert ac.acronym_violation(paired, rows) is None
    entry = {"source_text":"gnr","match_mode":"exact","source_lang":"ANY","preferred_translation":"[[GNR]]"}
    assert ac.page_acronyms(source, [(1,source)], 1, [entry])[0]["modes"] == ["bare"]


def test_prior_protected_field_is_not_first_mention():
    old = "Morada: Rua da GNR, n.º 9, em Beja"
    current = "Recebido da GNR em Beja."
    pages = [(1,old),(2,current)]
    assert not ac.page_acronyms(old,pages,1)
    assert ac.page_acronyms(current,pages,2)[0]["modes"] == ["gloss"]


def test_saved_rows_rederived_and_source_claim_must_own_target_unit():
    from types import SimpleNamespace
    s = "Oficie à GNR. Apure os factos."
    selections = [(1,s)]
    rows = ac.page_acronyms(s,selections,1)
    data = {"page_number":1, "original_source_text":s, "applicable_terminology":[], "source_acronyms":list(rows)}
    direct = {"ocr_used":False,"extraction_integrity_suspect":False}
    assert ac.capture_matches(data,selections,direct)
    for bad in [None,{},[],[{}],[{**rows[0],"modes":["bare"]}]]:
        assert not ac.capture_matches({**data,"source_acronyms":bad},selections,direct)
    assert not ac.capture_matches(data,selections,{**direct,"ocr_used":True})
    loc = rows[0]["locations"][0]
    candidate = tok("GNR")+" (الحرس الوطني الجمهوري)."
    page = SimpleNamespace(source_acronyms=rows,page_number=1)
    units = [{"page":1,"unit_id":"S","start":loc["start"],"end":loc["end"]}]
    target = [{"page":1,"unit_id":"T","start":0,"end":len(candidate)}]
    inventory = {"claims":[{"claim_id":"correct","source_unit_ids":["S"]}]}
    assert ac.verified_owners(page,candidate,units,inventory,target,{"T":{"correct"}})
    assert not ac.verified_owners(page,candidate,units,inventory,target,{"T":{"other"}})


def test_saved_versions_and_primary_source_absence():
    check_primary_page_evidence_policy(None)
    check_primary_page_evidence_policy("source_page_occurrences_v1")
    check_primary_page_evidence_policy(ac.POLICY)
    with pytest.raises(ValueError):
        check_primary_page_evidence_policy("arbitrary")
    assert not ac.read_selection("nonexistent.pdf", [1])
    assert ac.page_acronyms("Oficie à PJ.", [], 1) == ()


@pytest.mark.parametrize("legacy", [False, True])
def test_ordinary_start_compliance_selection_and_saved_resume(tmp_path, monkeypatch, legacy):
    import json
    from dataclasses import replace
    import fitz
    from tests.test_semantic_review_model_integration import setup

    primary_calls = []
    def respond(body, data):
        output = data["output"][0]["content"][0]
        if "text" not in body:
            primary_calls.append(body)
            translated = "أُبلغ الحرس الوطني الجمهوري."
            if not legacy and len(primary_calls) > 1:
                translated = "أُبلغ " + tok("GNR") + " (الحرس الوطني الجمهوري)."
            output["text"] = chr(96)*3 + "text\n" + translated + "\n" + chr(96)*3
        else:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == "correction":
                answer = json.loads(output["text"])
                for row in answer["pages"]:
                    row.update(status="no_change", corrected_text="", reason_codes=[])
                output["text"] = json.dumps(answer, ensure_ascii=False)
        return data

    config, http, flow = setup(tmp_path, mutate=respond)
    with fitz.open(config.pdf_path) as doc:
        doc[0].insert_text((50,240), "O expediente foi comunicado diretamente à GNR para conhecimento.")
        doc.saveIncr()
    if legacy:
        # Represents an already-saved v1 job with this same document.
        monkeypatch.setattr(ac, "read_selection", lambda *args: ())
    result = flow.run(config)
    assert result.success, result.error
    recipe = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert recipe["primary_page_evidence_policy"] == ("source_page_occurrences_v1" if legacy else ac.POLICY)
    source = json.loads((result.run_dir/"semantic_source/page_0001.json").read_bytes())
    assert (source.get("source_acronyms") or []) == ([] if legacy else list(ac.page_acronyms(
        source["original_source_text"], [(1,source["original_source_text"])], 1)))
    assert ("GNR" in source["expected_ar_tokens"]) is not legacy
    assert len(primary_calls) == (1 if legacy else 2)
    if not legacy:
        assert all("Source acronym occurrences" in json.dumps(b, ensure_ascii=False) for b in primary_calls)
    calls = len(http.requests)
    if legacy:
        monkeypatch.setattr(ac, "read_selection", lambda *args: pytest.fail("requalified historical page"))
    assert flow.run(replace(config, resume=True)).success
    assert len(http.requests) == calls
