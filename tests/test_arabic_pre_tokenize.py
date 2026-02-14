from legalpdf_translate.arabic_pre_tokenize import (
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
