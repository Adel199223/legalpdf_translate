import pytest

from legalpdf_translate.arabic_pre_tokenize import (
    LRI,
    PDI,
    extract_locked_tokens,
    is_portuguese_month_date_token,
    pretokenize_arabic_source,
)


def test_name_value_is_locked_as_single_token() -> None:
    text = "Nome: Adel Belghali"
    tokenized = pretokenize_arabic_source(text)
    assert tokenized == "Nome: [[Adel Belghali]]"
    assert extract_locked_tokens(tokenized) == ["Adel Belghali"]


def test_address_value_is_locked_as_single_token() -> None:
    text = "Morada: Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira"
    tokenized = pretokenize_arabic_source(text)
    assert tokenized == "Morada: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]"
    assert tokenized.count("[[") == 1
    assert extract_locked_tokens(tokenized) == ["Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira"]


def test_iban_value_is_locked() -> None:
    text = "O pagamento deverá ser efetuado para o seguinte IBAN: PT50003506490000832760029"
    tokenized = pretokenize_arabic_source(text)
    assert "IBAN: [[PT50003506490000832760029]]" in tokenized
    assert extract_locked_tokens(tokenized) == ["PT50003506490000832760029"]


def test_non_sensitive_colon_line_is_not_over_tokenized() -> None:
    text = "Observação: este texto é apenas explicativo."
    tokenized = pretokenize_arabic_source(text)
    assert tokenized == text
    assert extract_locked_tokens(tokenized) == []


def test_is_portuguese_month_date_token() -> None:
    assert is_portuguese_month_date_token("10 de fevereiro de 2026") is True
    assert is_portuguese_month_date_token("PT50003506490000832760029") is False


def test_bracket_adjacent_identifier_is_wrapped_without_triple_brackets() -> None:
    text = "21/25.0FBPTM [36231063]"
    tokenized = pretokenize_arabic_source(text)
    assert "[[[" not in tokenized
    assert tokenized == f"[[21/25.0FBPTM]] [{LRI}[[36231063]]{PDI}]"
    assert extract_locked_tokens(tokenized) == ["21/25.0FBPTM", "36231063"]


def test_extract_locked_tokens_ignores_malformed_nested_triple_brackets() -> None:
    assert extract_locked_tokens("[[[36231063]]]") == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Recebe €850,00/mês.", "Recebe €[[850,00]]/mês."),
        ("Paga €275,50.;", "Paga €[[275,50]].;"),
        ("Valor €125.75/dia.", "Valor €[[125.75]]/dia."),
        ("Valor £25.50.", "Valor £[[25.50]]."),
        ("Entre € 200,00 e € 350,00.", "Entre € [[200,00]] e € [[350,00]]."),
        ("Total €1.234,56/mês.", "Total €[[1.234,56]]/mês."),
    ],
)
def test_currency_decimal_remains_one_locked_value_before_units_and_punctuation(text, expected) -> None:
    assert pretokenize_arabic_source(text) == expected
    assert expected.replace("[[", "").replace("]]", "") == text


def test_decimal_currency_does_not_split_existing_identifiers_or_tokens() -> None:
    text = "Ref. 42/24.0TEST data 12.05.2026 CP 1234-567 valor €[[50,00]]/mês."
    assert pretokenize_arabic_source(text) == (
        "Ref. [[42/24.0TEST]] data [[12.05.2026]] CP [[1234-567]] valor €[[50,00]]/mês."
    )


def test_currency_fraction_is_part_of_required_token() -> None:
    from legalpdf_translate.validators import validate_ar

    expected = extract_locked_tokens(pretokenize_arabic_source("€850,00/mês."))
    assert expected == ["850,00"]
    split = f"المبلغ {LRI}[[850]]{PDI}،{LRI}[[00]]{PDI}"
    complete = f"المبلغ {LRI}[[850,00]]{PDI}"
    assert validate_ar(split, expected_tokens=expected).kind == "expected_token_mismatch"
    assert validate_ar(complete, expected_tokens=expected).ok


@pytest.mark.parametrize("label", ["Arguido", "Arguida", "Requerente", "Requerido", "Requerida",
    "Autor", "Autora", "Réu", "Ré", "Testemunha"])
def test_explicit_party_field_protects_exact_latin_person_name(label):
    source = f"{label}: Ana de Sousa-Martins"
    result = pretokenize_arabic_source(source)
    assert result == f"{label}: [[Ana de Sousa-Martins]]"
    assert pretokenize_arabic_source(result) == result


@pytest.mark.parametrize("anchor", ["Exmo. Senhor", "Exma. Senhora", "Exmo(a) Senhor(a)",
    "O Técnico de Justiça", "A Técnica de Justiça", "Juiz", "Juíza"])
def test_standalone_recipient_and_signer_anchor_protects_only_next_name(anchor):
    source = f"{anchor}\nAna de Sousa\nEste texto permanece traduzível."
    assert pretokenize_arabic_source(source) == f"{anchor}\n[[Ana de Sousa]]\nEste texto permanece traduzível."


def test_postal_block_is_anchored_bounded_and_preserves_lines():
    source = "Exmo. Senhor\nAna de Sousa\nRua das Flores 12\n1234-567 Vila Nova\nNotificação para comparecer."
    result = pretokenize_arabic_source(source)
    assert result == "Exmo. Senhor\n[[Ana de Sousa]]\n[[Rua das Flores 12]]\n[[1234-567 Vila Nova]]\nNotificação para comparecer."
    assert result.replace("[[", "").replace("]]", "") == source
    assert pretokenize_arabic_source(result) == result


@pytest.mark.parametrize("source", ["Arguido: Ministério Público", "Requerente: Tribunal Judicial",
    "Autor: Estado Português", "Testemunha: Este texto explica o caso.",
    "Exmo. Senhor\nTribunal Judicial", "Juiz\nFoi proferida decisão.",
    "Ana de Sousa compareceu perante o tribunal."])
def test_institutions_and_unanchored_prose_remain_translatable(source):
    assert pretokenize_arabic_source(source) == source


def test_street_without_nearby_postcode_or_across_body_boundary_is_not_whole_locked():
    for source in ("Rua das Flores\n\n1234-567 Vila Nova",
                   "Rua das Flores\nEste texto explica a decisão.\n1234-567 Vila Nova",
                   "Rua das Flores\nVila Nova\nOutro Lugar\nMais Um Lugar\n1234-567 Vila Nova"):
        assert "[[Rua das Flores]]" not in pretokenize_arabic_source(source)


def test_period_signature_and_single_word_postal_locality_actual_shapes():
    source = "O Técnico de Justiça.\nAna de Sousa\nRua das Flores\nViseu\n1234-567 Viseu"
    assert pretokenize_arabic_source(source) == (
        "O Técnico de Justiça.\n[[Ana de Sousa]]\n[[Rua das Flores]]\n[[Viseu]]\n[[1234-567 Viseu]]")


def test_decomposed_latin_name_preserves_exact_characters():
    source = "Arguida: Ana de Sa\u0301"
    assert pretokenize_arabic_source(source) == "Arguida: [[Ana de Sa\u0301]]"


def test_comma_signature_title_preserves_exact_next_name():
    assert pretokenize_arabic_source("O Técnico de Justiça,\nAna de Sousa") == "O Técnico de Justiça,\n[[Ana de Sousa]]"


@pytest.mark.parametrize("source", ["AB123456789CD", "*AB123456789CD*", "%AB123456789CD%",
    "%*AB123456789CD*", "%*AB123456789CD*%"])
def test_visible_tracking_core_is_one_exact_token_without_scaffold_changes(source):
    result = pretokenize_arabic_source(source)
    assert "[[AB123456789CD]]" in result
    assert extract_locked_tokens(result) == ["AB123456789CD"]
    assert result.replace("[[", "").replace("]]", "") == source
    assert pretokenize_arabic_source(result) == result


def test_tracking_core_rejects_longer_or_lowercase_alphanumeric_values():
    for source in ("ab123456789cd", "XAB123456789CDX"):
        assert "[[AB123456789CD]]" not in pretokenize_arabic_source(source)
