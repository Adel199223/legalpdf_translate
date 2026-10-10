from legalpdf_translate.translation_diagnostics import run_all_quality_checks, visible_text_projection

def checks(source, output, lang="AR"):
    return run_all_quality_checks(source_text=source, output_text=output, target_lang=lang)

def test_protocol_heavy_visible_citation_and_bidi_are_not_actionable():
    source="Artigo 277 (1)"
    output="المادة \u2066[[277]]\u2069 (\u2066[[1]]\u2069)" + "\u200e"*30
    r=checks(source,output)
    assert r["citation_actionable_missing_count"]==0
    assert r["parenthesis_delta_abs"]==0
    assert r["bidi_actionable_count"]==0
    assert r["bidi_warnings_count"]==0
    assert r["raw_bidi_control_count"]>20
    assert r["raw_citation_mismatches_count"]>0

def test_natural_brackets_are_not_protocol():
    assert visible_text_projection("natural [[277]]", "AR")==("natural [[277]]",0)
    assert visible_text_projection("\u2066[[277]]\u2069", "EN")[1]==0

def test_malformed_protocol_retains_unbalanced_evidence():
    r=checks("277", "\u2066[[277]]")
    assert r["output_protocol_literal_count"]==0
    assert r["bidi_actionable_count"]>=1
    assert r["bidi_warnings_count"]==1

def test_unsafe_override_inside_protected_literal_survives_projection():
    r=checks("277", "\u2066[[27\u202e7]]\u2069")
    assert r["unsafe_bidi_control_count"]==1
    assert r["bidi_warnings_count"]==1

def test_actual_citation_number_loss_and_replacement_remain_actionable():
    r=checks("Article 277", "المادة 278 \ufffd")
    assert r["citation_actionable_missing_count"]==2
    assert r["numeric_mismatches_count"]==2
    assert r["visible_replacement_char_count"]==1
    assert r["bidi_warnings_count"]==1

def test_translated_citation_labels_preserve_anchor():
    for output in ["Article 277", "article 277", "المادة 277", "الفصل 277"]:
        assert checks("artigo 277",output)["citation_actionable_missing_count"]==0

def test_nested_protocol_is_not_decoded():
    value="\u2066[[one [[two]]]]\u2069"
    assert visible_text_projection(value,"AR")== (value,0)


def test_real_missing_list_marker_is_actionable():
    r=checks("1. First\n2. Second", "1. أول\nثاني")
    assert r["list_marker_missing_count"]==1
    assert r["citation_actionable_missing_count"]==1

def test_balanced_isolates_with_malformed_protocol_are_actionable():
    r=checks("one", "\u2066[[one]\u2069")
    assert r["protocol_anomaly_count"]==1
    assert r["bidi_actionable_count"]>=1


def test_quality_risk_uses_visible_actionable_counts_not_protocol_noise():
    from legalpdf_translate.workflow_components.quality_risk import build_quality_risk_summary
    r=checks("Artigo 277", "المادة \u2066[[277]]\u2069"+"\u200e"*30)
    r.update(status="done")
    result=build_quality_risk_summary([(1,r)], target_lang="AR")
    reasons=result["review_queue"][0]["reasons"] if result["review_queue"] else []
    assert "citation_structure_drift" not in reasons
    assert "bidi_warning" not in reasons
    bad=checks("Article 277", "المادة 278")
    bad.update(status="done")
    assert "citation_structure_drift" in build_quality_risk_summary([(1,bad)], target_lang="AR")["review_queue"][0]["reasons"]


def test_nonprotocol_balanced_isolates_remain_actionable():
    assert checks("ABC", "\u2066ABC\u2069")["bidi_actionable_count"]==2

def test_generic_address_number_is_not_legal_citation():
    assert checks("Rua X, n.º 14", "Rua X, 14")["citation_actionable_missing_count"]==0

def test_article_paragraph_exchange_and_extra_article_are_detected():
    assert checks("Article 277; paragraph 2", "المادة 2؛ الفقرة 277")["citation_actionable_missing_count"]==2
    assert checks("Article 277; Reference 278", "المادة 277؛ المادة 278")["citation_actionable_missing_count"]==1

def test_unmatched_visible_brackets_are_actionable_balanced_changes_advisory():
    assert checks("(note)", "(x")["visible_bracket_anomaly_count"]==1
    assert checks("(note)", "[x]")["visible_bracket_anomaly_count"]==0


def test_unchanged_legal_list_and_subparagraph_are_not_translation_defects():
    for value in ["1) First\n2) Second", "Article 277, subparagraph a).", "source (unfinished"]:
        r=checks(value,value)
        assert r["citation_actionable_missing_count"]==0
        assert r["actionable_bracket_drift_count"]==0

def test_new_misnested_output_remains_actionable():
    assert checks("(x)","([x)]")["actionable_bracket_drift_count"]>0


def test_legal_enumerators_are_script_neutral_and_inline_differences_relative():
    assert checks("a) First", "أ) أول")["actionable_bracket_drift_count"]==0
    assert checks("subparagraph a).", "point a).", "FR")["actionable_bracket_drift_count"]==0
