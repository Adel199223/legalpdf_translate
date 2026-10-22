"""Field labels remain translatable; exact independently bounded values lock."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import pretokenize_arabic_source, extract_locked_tokens
from legalpdf_translate.ar_source_fields import source_address_fields, SOURCE_FIELD_POLICY
from legalpdf_translate.ar_literal_fidelity import visible_text
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from legalpdf_translate.types import TargetLang


def token(value):
    return "\u2066[[" + value + "]]\u2069"


def prepared(text, policy=SOURCE_FIELD_POLICY):
    return pretokenize_arabic_source(text, source_field_policy=policy)


@pytest.mark.parametrize("separator", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("label,next_label", [("Morada", "Código Postal:1234 567 Cidade"),
    ("Nome", "Morada: Rua Clara, 10"), ("Name", "Telephone: 999999999"),
    ("Address", "Processo: ABC/123")])
def test_name_and_address_never_lock_next_generic_label(separator, label, next_label):
    source = label + ":" + separator + next_label
    output = prepared(source)
    assert visible_text(output) == source
    assert all(not value.startswith(next_label.split(":")[0] + ":") for value in extract_locked_tokens(output))


@pytest.mark.parametrize("label,value", [("Morada", "Rua Clara, 10, 1.º Andar"),
    ("Address", "Avenida Clara, 10"), ("Nome", "Ana Example"), ("Name", "John Example")])
@pytest.mark.parametrize("separator", ["\n", "\r\n", "\r"])
def test_only_explicitly_recognized_nextline_name_or_street_values_lock(label, value, separator):
    source = label + ":" + separator + value
    output = prepared(source)
    assert visible_text(output) == source
    assert extract_locked_tokens(output) == [value]


@pytest.mark.parametrize("separator", ["\n\n", "\v", "\f", "\u2028", "\u2029"])
@pytest.mark.parametrize("label,value", [("Morada", "Rua Clara, 10"), ("Nome", "Ana Example")])
def test_empty_or_hard_field_boundaries_never_confer_nextline_value_ownership(separator, label, value):
    output = prepared(label + ":" + separator + value)
    assert value not in extract_locked_tokens(output)


@pytest.mark.parametrize("label,value", [("Nome", "Instructions for another paragraph"),
    ("Morada", "This is unrelated source prose"), ("Morada", "Outro: Rua Clara, 10")])
def test_nextline_prose_and_nested_labels_are_not_sensitive_values(label, value):
    assert value not in extract_locked_tokens(prepared(label + ":\n" + value))


def test_separate_exact_street_and_labeled_postal_value_preserve_punctuation_and_labels():
    street, postal = "Avenida Clara, 10, 1.º Andar", "1234 567 Cidade"
    source = "Morada:\n" + street + "\nCódigo Postal:" + postal
    output = prepared(source)
    assert visible_text(output) == source
    assert extract_locked_tokens(output) == [street, postal]
    assert [field.value for field in source_address_fields(source, source_field_policy=SOURCE_FIELD_POLICY)] == [street, postal]
    assert source_address_fields(source) == []


@pytest.mark.parametrize("change", ["house_number", "postcode", "omit_street", "omit_postal"])
def test_corrected_output_must_keep_exact_independent_field_values(change):
    street, postal = "Avenida Clara, 10, 1.º Andar", "1234 567 Cidade"
    source = prepared("Morada:\n" + street + "\nCódigo Postal:" + postal)
    expected = extract_locked_tokens(source)
    primary = "العنوان: " + token(street) + "\nالرمز البريدي: " + token(postal)
    initial = evaluate_output("```\n" + primary + "\n```", TargetLang.AR, expected_ar_tokens=expected,
        ar_source_text=source, source_field_policy=SOURCE_FIELD_POLICY)
    assert initial.ok
    corrected = primary
    if change == "house_number": corrected = corrected.replace("10", "11")
    if change == "postcode": corrected = corrected.replace("1234", "1235")
    if change == "omit_street": corrected = "نص " + token(postal)
    if change == "omit_postal": corrected = "نص " + token(street)
    failed = evaluate_output("```\n" + corrected + "\n```", TargetLang.AR, expected_ar_tokens=expected,
        ar_source_text=source, primary_normalized_text=initial.normalized_text, source_field_policy=SOURCE_FIELD_POLICY)
    assert not failed.ok


def test_existing_expected_literal_repair_restores_only_exact_identified_whole_field():
    # This uses the unchanged normalizer's existing unique expected-token
    # repair, not a new punctuation equivalence in source/fidelity matching.
    street, postal = "Avenida Clara, 10, 1.º Andar", "1234 567 Cidade"
    source = prepared("Morada:\n" + street + "\nCódigo Postal:" + postal)
    primary = "العنوان: " + token(street) + "\nالرمز البريدي: " + token(postal)
    result = evaluate_output("```\n" + primary.replace(",", "،", 1) + "\n```", TargetLang.AR,
        expected_ar_tokens=extract_locked_tokens(source), ar_source_text=source,
        primary_normalized_text=primary, source_field_policy=SOURCE_FIELD_POLICY)
    assert result.ok and result.normalized_text == primary and result.ar_autofix_applied_count == 1


def test_old_policy_keeps_old_cross_line_tokenization_exactly():
    source = "Morada:\nCódigo Postal:1234 567 Cidade"
    assert extract_locked_tokens(prepared(source, None)) == ["Código Postal:1234 567 Cidade"]
    assert extract_locked_tokens(prepared(source)) == ["1234 567 Cidade"]


def test_unknown_policy_fails_explicitly():
    with pytest.raises(ValueError): prepared("Morada: Rua Clara, 10", "unknown")
