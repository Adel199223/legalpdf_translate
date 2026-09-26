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
