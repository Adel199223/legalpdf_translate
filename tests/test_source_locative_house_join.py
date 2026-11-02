"""Fictional opt-in source locative joins; no retained documents/provider data."""
from dataclasses import asdict, replace
from types import SimpleNamespace
import json

import pytest

from legalpdf_translate import ar_source_fields as fields
from legalpdf_translate import ordinary_semantic_audit as audit
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import workflow_semantic_audit as integration
from legalpdf_translate import ordinary_semantic_literal_authority as authority
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
from legalpdf_translate.output_normalize import LRI, PDI
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from tests.test_workflow_semantic_review_integration import saved_recipe, setup_review

POLICY = "source_locative_house_join_v1"
V2 = "source_locative_house_join_v2"
KEY = "source_inline_address_join_policy"
SOURCE = "Residente na Rua do Cedro, no nº [[27]]."
STREET = "Rua do Cedro"


def token(value):
    return LRI + "[[" + value + "]]" + PDI


def target(gap="، عند رقم ", street=STREET, number="27"):
    return "يقيم في " + token(street) + gap + token(number) + "."


def canonical(text=None, source=SOURCE, required=None, enabled=True):
    options = {KEY: POLICY} if enabled else {}
    return fields.canonicalize_source_address_literals(target() if text is None else text,
        source, ["27"] if required is None else required, **options)


@pytest.mark.parametrize("gap", [" عند رقم ", ", عند رقم ", "، عند رقم ", "\tعند\tرقم\t", "،\tعند رقم "])
def test_new_permission_preserves_every_raw_target_character(gap):
    text = target(gap)
    assert canonical(text) == (text, ["27"], 0, None)
    assert canonical(text, enabled=False)[3] == "source_address_coverage_mismatch"


@pytest.mark.parametrize("marker", ["no nº ", "no n.º ", "no n° ", "no n.o ", "no\tnº\t"])
def test_explicit_source_locative_house_marker_is_required(marker):
    assert canonical(source="Residente na Rua do Cedro, " + marker + "[[27]].")[3] is None


@pytest.mark.parametrize("source", [
    "Residente na Rua do Cedro, nº [[27]].",
    "Residente na Rua do Cedro, no [[27]].",
    "Residente na Rua do Cedro, no nº [[27]], em Vale Claro.",
    "Residente na Rua do Cedro, no n\u2066º [[27]].",
    "Residente na Rua do Ce\u2069dro, no nº [[27]].",
    "Residente na Rua do Cedro, no nº \u2066[[27]]\u2069\u2066.",
])
def test_unwitnessed_changed_town_or_raw_control_source_does_not_gain_proof(source):
    # A control outside the local field has no new proof authority. The last
    # case is deliberately outside the field and remains historical behavior.
    if source.endswith("\u2066."):
        assert canonical(source=source)[3] is None
    else:
        assert canonical(source=source)[3] is not None


@pytest.mark.parametrize("gap", [
    " عند بالرقم ", " في رقم ", " وليس رقم ", " عند رقم -", " عند رقم\n",
    "، عند\rرقم ", "، عند رقم \u2066", "، عند رقم \u2069",
    "، عند\u2066 رقم ", "، عند رقم \u200e", "، عند رقم \u200f", "، عند رقم \u202e",
])
def test_new_raw_interstitial_rejects_other_words_newlines_and_controls(gap):
    assert canonical(target(gap))[3] is not None


@pytest.mark.parametrize("text", [
    target(number="28"), target(street="Rua do Freixo"),
    "يقيم عند رقم " + token("27") + ".",
    "يقيم في " + token(STREET) + ".",
    target() + " " + token("27"), target() + " " + token(STREET),
    "يقيم في " + STREET + "، عند رقم " + token("27"),
    "يقيم في " + token(STREET + "، عند رقم 27"),
    "يقيم في " + token(STREET) + "، عند رقم " + token("27") + ".5",
])
def test_whole_token_ownership_coverage_and_numeric_multiplicity_remain_required(text):
    assert canonical(text)[3] is not None


def test_two_source_fields_must_keep_exact_order_and_association():
    source = SOURCE + "\nResidente na Rua do Freixo, no nº [[38]]."
    second = target(street="Rua do Freixo", number="38")
    assert canonical(target() + "\n" + second, source, ["27", "38"])[3] is None
    assert canonical(second + "\n" + target(), source, ["27", "38"])[3] == "source_address_association_mismatch"
    assert canonical(target(number="38") + "\n" + target(street="Rua do Freixo"), source, ["27", "38"])[3] is not None


@pytest.mark.parametrize("gap", [" رقم ", " بالرقم ", "، رقم "])
def test_existing_join_outcomes_remain_identical(gap):
    assert canonical(target(gap)) == canonical(target(gap), enabled=False)


def test_no_source_and_work_bound_do_not_create_an_inline_witness():
    assert canonical(source=None)[3] is None
    assert canonical(source="x" * 120001)[3] == "source_address_malformed_tokens"


@pytest.mark.parametrize("invalid", ["", "unknown", False, [], {}])
def test_unknown_explicit_capability_fails_closed(invalid):
    with pytest.raises(ValueError, match="inline address join"):
        fields.canonicalize_source_address_literals(target(), SOURCE, ["27"], **{KEY: invalid})


def test_primary_and_identical_correction_pass_only_with_the_saved_permission():
    raw = "```\n" + target() + "\n```"
    old = evaluate_output(raw, TargetLang.AR, expected_ar_tokens=["27"], ar_source_text=SOURCE)
    assert not old.ok and old.ar_token_details["source_address_violation"] == "source_address_coverage_mismatch"
    primary = evaluate_output(raw, TargetLang.AR, expected_ar_tokens=["27"], ar_source_text=SOURCE, **{KEY: POLICY})
    assert primary.ok, primary
    correction = evaluate_output(raw, TargetLang.AR, expected_ar_tokens=["27"], ar_source_text=SOURCE,
        primary_normalized_text=primary.normalized_text, **{KEY: POLICY})
    assert correction.ok and correction.normalized_text == primary.normalized_text
    assert not correction_preserves_additional_literals(target() + " " + token("retain-me"), target(), ["27"], SOURCE, **{KEY: POLICY})


def page():
    return audit.SemanticAuditPage(1, SOURCE, ("27",), None, target(), source_text_kind="pretokenized",
        visual_coverage="text_only_configured_image_off")


def recipe(enabled=True):
    return audit.SemanticAuditRecipe("gpt-5.2", "high", configured_image_mode="off",
        source_field_policy="baseline_label_value_v1", **({KEY: POLICY} if enabled else {}))


def test_semantic_corrected_text_uses_same_permission_and_keeps_old_default():
    raw = audit._json({"version": audit.AUDIT_VERSION, "pages": [{"page_number": 1,
        "status": "corrected", "corrected_text": target(), "reason_codes": ["material_meaning"]}]})
    with pytest.raises(audit.SemanticAuditError, match="correction_literal_or_language_failure"):
        audit.validate_semantic_audit_response(raw, [page()], **audit._validation_options(recipe(False)))
    selected, _ = audit.validate_semantic_audit_response(raw, [page()], **audit._validation_options(recipe()))
    assert selected[1] == target()


def test_provider_request_is_exactly_unchanged_while_local_binding_records_permission():
    old, fresh = recipe(False), recipe()
    before = audit.build_semantic_audit_request([page()], old, "a" * 64)
    after = audit.build_semantic_audit_request([page()], fresh, "a" * 64)
    assert before == after and KEY not in after["prompt_text"]
    historical = asdict(old)
    historical.pop(KEY)
    assert audit._binding([page()], old, "a" * 64, before)["recipe_sha256"] == audit._sha(audit._json(historical))
    assert audit._binding([page()], fresh, "a" * 64, after)["recipe_sha256"] != audit._binding([page()], old, "a" * 64, before)["recipe_sha256"]


def test_fresh_saved_recipe_opt_in_roundtrips_without_rewriting_absence(tmp_path):
    _, saved, settings = saved_recipe(tmp_path)
    settings["ocr_engine"] = "api"
    assert saved[KEY] == "source_locative_house_join_v3" and saved["source_field_policy"] == "baseline_label_value_v1"
    assert saved["primary_literal_packaging_version"] == "lossless_source_components_v3"
    assert ordinary_semantic_audit_recipe(settings) == saved
    saved.pop(KEY)
    assert KEY not in ordinary_semantic_audit_recipe(settings)
    saved[KEY] = "unknown"
    with pytest.raises(SemanticAuditRecipeError, match="inline_address_join_policy"):
        ordinary_semantic_audit_recipe(settings)


def test_workflow_delegate_passes_only_explicit_saved_permission(monkeypatch):
    calls = []
    monkeypatch.setattr(workflow_module, "evaluate_workflow_output", lambda *a, **kw: calls.append(kw))
    workflow = object.__new__(TranslationWorkflow)
    workflow._evaluate_output("raw", TargetLang.AR)
    workflow._evaluate_output("raw", TargetLang.AR, **{KEY: POLICY})
    assert KEY not in calls[0] and calls[1][KEY] == POLICY


def test_literal_authority_wrapper_projection_uses_permission_without_changing_text():
    assert authority._wrapper_equivalent_candidate(target(), page(), recipe()) == target()


def test_unrecognized_source_field_does_not_gain_a_new_permission():
    source = "Residente na Rua do Cedro, em nº [[27]]."
    assert canonical(source=source) == canonical(source=source, enabled=False)
    assert canonical(source=SOURCE.replace("27", "28"), required=["28"])[3] is not None


@pytest.mark.parametrize("invalid", [None, "", "unknown", False, [], {}])
def test_saved_explicit_invalid_join_policy_is_not_historical_absence(tmp_path, invalid):
    _, saved, settings = saved_recipe(tmp_path)
    settings["ocr_engine"] = "api"
    saved[KEY] = invalid
    with pytest.raises(SemanticAuditRecipeError, match="inline_address_join_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("enabled", [False, True])
def test_review_correction_forwards_local_validation_capability(monkeypatch, enabled):
    rows = [{"page_number": 1, "status": "corrected", "corrected_text": target(),
             "reason_codes": ["material_meaning"]}]
    raw = audit._json({"version": review.CORRECTION_VERSION, "pages": rows, "claim_coverage": []})
    calls = []
    def validate(raw, pages, **kwargs):
        calls.append(kwargs)
        return {1: target()}, rows
    monkeypatch.setattr(audit, "validate_semantic_audit_response", validate)
    review.validate_source_correction(raw, [page()], {"claims": []}, recipe(enabled))
    assert calls == [audit._validation_options(recipe(enabled))]
    assert (KEY in calls[0]) is enabled


@pytest.mark.parametrize("enabled", [False, True])
def test_literal_authority_strict_and_replacement_checks_forward_policy(monkeypatch, enabled):
    rows = [{"page_number": 1, "status": "no_change", "corrected_text": "", "reason_codes": []}]
    monkeypatch.setattr(authority, "parse_correction", lambda *a: {"pages": rows})
    calls = []
    def evaluate(raw, lang, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(ok=True, normalized_text=target())
    monkeypatch.setattr(audit, "evaluate_output", evaluate)
    assert authority.classify("raw", [page()], {}, recipe(enabled), {"pages": [{}]}) is None
    authority.check_replacement_eligibility("raw", [page()], {}, recipe(enabled),
        SimpleNamespace(projected_pages=[page()]))
    strict = [kw for kw in calls if "expected_ar_tokens" in kw]
    assert len(strict) == 2
    assert all((kw.get(KEY) == POLICY) is enabled for kw in strict)
    assert all((KEY in kw) is enabled for kw in strict)


@pytest.mark.parametrize("enabled", [False, True])
def test_literal_authority_final_full_candidate_forwards_policy(monkeypatch, enabled):
    rows = [{"page_number": 1, "status": "no_change", "corrected_text": "", "reason_codes": []}]
    monkeypatch.setattr(authority, "parse_correction", lambda *a: {"pages": rows})
    calls = []
    def validate(raw, pages, **kwargs):
        calls.append(kwargs)
        return {1: target()}, rows
    monkeypatch.setattr(audit, "validate_semantic_audit_response", validate)
    selected, _, _ = authority.validate("raw", [page()], {}, recipe(enabled))
    assert selected == {1: target()}
    assert calls == [audit._validation_options(recipe(enabled))]


def test_unknown_semantic_capability_and_direct_evaluator_fail_closed():
    with pytest.raises(audit.SemanticAuditError, match="invalid_recipe"):
        audit.build_semantic_audit_request([page()], replace(recipe(), **{KEY: "unknown"}), "a" * 64)
    with pytest.raises(audit.SemanticAuditError, match="invalid_recipe"):
        audit.validate_semantic_audit_response("{}", [page()], **{KEY: "unknown"})
    with pytest.raises(ValueError, match="inline address join"):
        evaluate_output("```\nنص\n```", TargetLang.AR, **{KEY: "unknown"})


@pytest.mark.parametrize("enabled", [False, True])
def test_primary_and_retry_read_the_explicit_saved_join_capability(tmp_path, monkeypatch, enabled):
    fresh = integration.fresh_recipe
    def three_stage(*args, **kwargs):
        saved = fresh(*args, **kwargs)
        for key in ("semantic_repair_policy", "semantic_literal_authority_policy",
                    "semantic_enclosure_authority_policy", "source_enclosure_identity_policy",
                    "semantic_target_ambiguity_policy", "ocr_text_transport_policy", "primary_literal_markup_policy",
                    "semantic_enclosure_sequence_repair_policy", "primary_page_evidence_policy"):
            saved.pop(key, None)
        assert "semantic_target_ambiguity_policy" not in saved
        if not enabled:
            saved.pop(KEY)
        else:
            saved[KEY] = POLICY  # Retained v1 forwarding stays explicitly v1.
        return saved
    monkeypatch.setattr(integration, "fresh_recipe", three_stage)
    config, sdk, workflow = setup_review(tmp_path)
    evaluate, calls = workflow._evaluate_output, []
    def require_retry(raw, lang, **kwargs):
        calls.append(kwargs)
        result = evaluate(raw, lang, **kwargs)
        if len(calls) == 1:
            assert result.ok
            return replace(result, ok=False, validator_failed=True,
                ar_violation_kind="latin_or_digits_outside_wrapped_tokens",
                defect_reason="Fictional forced retry for saved policy forwarding.")
        return result
    monkeypatch.setattr(workflow, "_evaluate_output", require_retry)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(calls) == 2
    assert all((kw.get(KEY) == POLICY) is enabled for kw in calls)
    assert all((KEY in kw) is enabled for kw in calls)
    # This capability is local validation, never prompt coaching.
    assert all(KEY not in json.dumps(request) for request in sdk.requests)


@pytest.mark.parametrize("enabled", [False, True])
def test_semantic_repair_quality_diagnostic_keeps_join_permission(monkeypatch, enabled):
    rows = [{"page_number": 1, "status": "corrected", "corrected_text": target(),
             "reason_codes": ["material_meaning"]}]
    calls = []
    def reject_quality(*args, **kwargs):
        if kwargs:
            calls.append(kwargs)
        raise audit.SemanticAuditError("new_actionable_quality_failure")
    monkeypatch.setattr(review, "validate_source_correction", reject_quality)
    monkeypatch.setattr(audit, "validate_semantic_audit_response", reject_quality)
    def evaluate(*args, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(ok=True, normalized_text=target())
    monkeypatch.setattr(audit, "evaluate_output", evaluate)
    counter = iter([0, 1])
    def quality(**kwargs):
        count = next(counter)
        return {"numeric_mismatches_count": count, "citation_actionable_missing_count": 0,
                "bidi_actionable_count": 0, "visible_replacement_char_count": 0}
    monkeypatch.setattr(audit, "run_all_quality_checks", quality)
    monkeypatch.setattr(audit, "_quality_anchors", lambda *a: {})
    report = repair.correction_validation_diagnostic(audit._json({"pages": rows}),
        [page()], {"claims": []}, recipe(enabled))
    assert report["correction_validation_diagnostic"]["trigger"] == "new_actionable_quality_failure"
    assert len(calls) == 2
    assert all((kw.get(KEY) == POLICY) is enabled for kw in calls)
    assert all((KEY in kw) is enabled for kw in calls)


# V2 derives one complete target-visible alternative. All earlier tests above
# still exercise the saved v1 capability, including its intentional rejection
# of copied-marker alternatives.
ALT = "Rua do Cedro, nº 27"


def v2_canonical(text, source=SOURCE, required=None):
    return fields.canonicalize_source_address_literals(text, source,
        ["27"] if required is None else required, **{KEY: V2})


def v2_eval(text, source=SOURCE, required=None, primary=None):
    return evaluate_output("```\n" + text + "\n```", TargetLang.AR,
        expected_ar_tokens=["27"] if required is None else required,
        ar_source_text=source, source_field_policy="baseline_label_value_v1",
        literal_wrapper_policy="lossless_source_components_v3",
        primary_normalized_text=primary, **{KEY: V2})


@pytest.mark.parametrize("packing", [
    lambda: token(ALT),
    lambda: token("Rua do Cedro, nº") + " " + token("27"),
    lambda: token("Rua do Cedro") + ", " + token("nº 27"),
    lambda: token("Rua do Cedro") + ", " + token("nº") + " " + token("27"),
    lambda: token("Rua do") + " " + token("Cedro") + ", " + token("nº") + " " + token("27"),
])
def test_v2_complete_source_derived_alternate_coalesces_disjoint_carriers(packing):
    text = "يقيم في " + packing() + "."
    result, expected, count, error = v2_canonical(text)
    assert error is None and expected == [ALT] and count >= 0
    assert result == "يقيم في " + token(ALT) + "."
    assert fields._view(result)[0] == fields._view(text)[0]
    assert fields.canonicalize_source_address_literals(text, SOURCE, ["27"], **{KEY: POLICY})[3] is not None


def test_v2_unwrapped_semantics_do_not_themselves_confer_new_carrier_ownership():
    assert v2_canonical("يقيم في " + ALT + ".")[3] == "source_address_component_carrier_mismatch"
    # Generic numeric wrapping cannot manufacture ownership for unprotected
    # street/ordinal text. The complete-carrier obligation remains unmet.
    assert not v2_eval("يقيم في " + ALT + ".").ok


@pytest.mark.parametrize("value", [
    "Rua do Freixo, nº 27", "Rua do Cedro, nº 28", "Rua do Cedro, nº",
    "Rua do Cedro, n° 27", "Rua do Cedro, n.º 27", "Rua do Cedro; nº 27",
    "Rua do Cedro, nº  27", "Rua do Cedro, nº perto de 27", "Rua do Cedro, nº 270",
    "Rua do Cedro, nº 27.5", "Rua do Cedro, nº 27-A", "Rua do Cedro, Nº 27",
])
def test_v2_preserves_every_other_source_character_and_number_boundary(value):
    assert not v2_eval("يقيم في " + token(value) + ".").ok


@pytest.mark.parametrize("damage", [
    "source_owned_no", "source_owned_street", "source_owned_marker", "source_isolate",
    "target_isolate", "target_lrm", "target_newline", "crossing_wrapper",
    "duplicate_short", "original_and_short", "extra_street", "extra_house", "source_town",
])
def test_v2_rejects_unowned_controls_competing_representations_and_partial_fields(damage):
    source, text, required = SOURCE, "يقيم في " + token(ALT) + ".", ["27"]
    if damage == "source_owned_no":
        source = source.replace("no nº", "[[no]] nº"); required.append("no")
    elif damage == "source_owned_street":
        source = source.replace(STREET, "[[" + STREET + "]]"); required.append(STREET)
    elif damage == "source_owned_marker":
        source = source.replace("nº", "[[nº]]"); required.append("nº")
    elif damage == "source_isolate":
        source = source.replace("no nº", "no\u2066\u2069 nº")
    elif damage in {"target_isolate", "target_lrm", "target_newline"}:
        gap = {"target_isolate": "\u2066\u2069", "target_lrm": "\u200e", "target_newline": "\n"}[damage]
        text = "يقيم في " + token(STREET) + ", " + gap + token("nº") + " " + token("27")
    elif damage == "crossing_wrapper":
        text = token("كلام " + ALT)
    elif damage == "duplicate_short":
        text += " " + token(ALT)
    elif damage == "original_and_short":
        text += " " + token("Rua do Cedro, no nº 27")
    elif damage == "extra_street":
        text += " " + token(STREET)
    elif damage == "extra_house":
        text += " " + token("27")
    elif damage == "source_town":
        source = source.replace("[[27]].", "[[27]], em Vale Claro.")
        text += " " + token("Vale Claro")
    assert not v2_eval(text, source, required).ok


def test_v2_original_plus_alternate_is_an_explicit_joint_association_failure():
    original = token("Rua do Cedro, no nº 27")
    text = "يقيم في " + original + " و " + token(ALT)
    assert v2_canonical(text)[3] == "source_address_association_mismatch"
    # This is a new fail-closed proof boundary, not a silent decline/fallback.
    assert fields.canonicalize_source_address_literals(text, SOURCE, ["27"], **{KEY: POLICY})[3] is None


def test_v2_keeps_exact_source_original_and_older_arabic_join_behavior():
    for text in [token("Rua do Cedro, no nº 27"), target(), target(" رقم ")]:
        assert v2_canonical(text) == canonical(text)


def test_v2_correction_cannot_erase_locative_protected_by_the_primary():
    primary = v2_eval("يقيم في " + token("Rua do Cedro, no nº 27") + ".")
    assert primary.ok
    corrected = v2_eval("يقيم في " + token(ALT) + ".", primary=primary.normalized_text)
    assert not corrected.ok and corrected.ar_violation_kind == "correction_literal_fidelity_loss"


def test_v2_primary_and_split_correction_converge_with_no_visible_changes():
    primary_text = "يقيم في " + token(ALT) + "."
    corrected_text = "يقيم في " + token("Rua do Cedro, nº") + " " + token("27") + "."
    primary = v2_eval(primary_text)
    corrected = v2_eval(corrected_text, primary=primary.normalized_text)
    assert primary.ok and corrected.ok
    assert primary.normalized_text == corrected.normalized_text
    assert fields._view(primary.normalized_text)[0] == fields._view(primary_text)[0]
    assert fields._view(corrected.normalized_text)[0] == fields._view(corrected_text)[0]
    assert not v2_eval(corrected_text + " " + token("unrelated-lost"), primary=primary.normalized_text + " " + token("retain-me")).ok


@pytest.mark.parametrize("case", ["ordered", "reversed", "swapped", "repeated_street"])
def test_v2_joint_source_field_order_and_unique_street_ownership(case):
    street = STREET if case == "repeated_street" else "Rua do Freixo"
    source = SOURCE + "\nResidente na " + street + ", no nº [[38]]."
    first = token(ALT)
    second = token(street + ", nº 38")
    if case == "reversed":
        text = second + " ثم " + first
    elif case == "swapped":
        text = token("Rua do Cedro, nº 38") + " ثم " + token(street + ", nº 27")
    else:
        text = first + " ثم " + second
    assert v2_eval(text, source, ["27", "38"]).ok is (case == "ordered")


def test_v2_complete_alternate_work_and_carrier_bounds_are_fail_closed(monkeypatch):
    text = "يقيم في " + token(ALT)
    monkeypatch.setattr(fields, "_MAX_INLINE_COMPONENT_WORK", 1)
    expensive = fields._source_inline_locative_alternative
    monkeypatch.setattr(fields, "_source_inline_locative_alternative",
        lambda *args: pytest.fail("Source/target occurrence scans ran after work budget exhaustion."))
    assert v2_canonical(text)[3] == "source_address_component_bound"
    monkeypatch.setattr(fields, "_source_inline_locative_alternative", expensive)
    monkeypatch.setattr(fields, "_MAX_INLINE_COMPONENT_WORK", 200000)
    monkeypatch.setattr(fields, "_MAX_INLINE_COMPONENT_CARRIERS", 1)
    assert v2_canonical(token(STREET) + ", " + token("nº") + " " + token("27"))[3] == "source_address_component_carrier_mismatch"


def test_v2_semantic_corrected_candidate_and_local_binding_use_same_policy():
    fresh = replace(recipe(), **{KEY: V2})
    before = "يقيم في " + token(ALT)
    p = replace(page(), primary_text=before)
    raw = audit._json({"version": audit.AUDIT_VERSION, "pages": [{"page_number": 1,
        "status": "corrected", "corrected_text": before, "reason_codes": ["material_meaning"]}]})
    selected, _ = audit.validate_semantic_audit_response(raw, [p], **audit._validation_options(fresh))
    assert selected[1] == before
    assert audit.build_semantic_audit_request([p], fresh, "a" * 64) == audit.build_semantic_audit_request([p], replace(fresh, **{KEY: POLICY}), "a" * 64)


@pytest.mark.parametrize("representation", ["original", "alternate"])
@pytest.mark.parametrize("suffix", [".", ",", ":", "/", "-", "_"])
@pytest.mark.parametrize("source_house", ["27", "27B"])
def test_v2_original_and_alternate_reject_split_compound_number_extensions(representation, suffix, source_house):
    source = SOURCE.replace("27", source_house)
    field = "Rua do Cedro, " + ("no " if representation == "original" else "") + "nº"
    text = "يقيم في " + token(field) + " " + token(source_house) + suffix + token("5")
    result = v2_eval(text, source, [source_house])
    assert not result.ok
    assert result.ar_token_details["source_address_violation"] == "source_address_association_mismatch"


@pytest.mark.parametrize("representation", ["original", "alternate"])
@pytest.mark.parametrize("tail", ["0", "B", "B5"])
def test_v2_cannot_fallback_after_a_word_boundary_filtered_house_extension(representation, tail):
    field = "Rua do Cedro, " + ("no " if representation == "original" else "") + "nº 27"
    changed = token(field + tail)
    # A correct-looking competing original cannot hide a changed alias that
    # the old whole-word occurrence search would otherwise filter out.
    text = "يقيم في " + changed + " و " + token("Rua do Cedro, no nº 27")
    assert v2_canonical(text)[3] == "source_address_association_mismatch"


@pytest.mark.parametrize("representation", ["original", "alternate"])
def test_v2_house_letter_suffix_and_sentence_final_period_remain_valid(representation):
    source = SOURCE.replace("27", "27B")
    field = "Rua do Cedro, " + ("no " if representation == "original" else "") + "nº 27B"
    assert v2_eval("يقيم في " + token(field) + ".", source, ["27B"]).ok


def test_v2_compound_suffix_guard_does_not_rewrite_saved_none_or_v1_behavior():
    text = "يقيم في " + token("Rua do Cedro, no nº") + " " + token("27") + "." + token("5")
    for saved in [None, POLICY]:
        old = fields.canonicalize_source_address_literals(text, SOURCE, ["27"],
            **({KEY: saved} if saved else {}))
        assert old[3] is None
    assert v2_canonical(text)[3] == "source_address_association_mismatch"
