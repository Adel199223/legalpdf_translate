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
    assert r["citation_actionable_missing_count"]==1
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
    assert r["bidi_actionable_count"]==1


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
