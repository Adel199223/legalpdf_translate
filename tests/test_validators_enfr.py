from legalpdf_translate.validators import validate_enfr
from legalpdf_translate.types import TargetLang


def test_validate_enfr_accepts_non_empty_output() -> None:
    result = validate_enfr("Line one\nLine two")
    assert result.ok is True


def test_validate_enfr_rejects_empty_output() -> None:
    result = validate_enfr("   ")
    assert result.ok is False


def test_validate_enfr_rejects_blank_line() -> None:
    result = validate_enfr("Line one\n\nLine two")
    assert result.ok is False


def test_validate_enfr_rejects_portuguese_month_date_leak_when_lang_specified() -> None:
    result = validate_enfr("Beja, 1.º de Março de 2026", lang=TargetLang.FR)
    assert result.ok is False
    assert result.reason == "Portuguese month-name date leaked after normalization."
    assert result.details == {
        "pt_month_leak_count": 1,
        "pt_legal_leak_count": 0,
        "pt_institution_leak_count": 0,
        "exempted_address_hits": 0,
    }


def test_validate_enfr_allows_address_month_word_context() -> None:
    result = validate_enfr("Rua 1.º de Dezembro, 2.º 7800-190 Beja", lang=TargetLang.FR)
    assert result.ok is True


def test_validate_enfr_rejects_portuguese_institution_leak_in_french() -> None:
    result = validate_enfr(
        "Ministère public - Procuradoria da República da Comarca de Beja",
        lang=TargetLang.FR,
    )
    assert result.ok is False
    assert result.reason == "Portuguese legal/institution terms leaked after normalization."
    assert result.details == {
        "pt_month_leak_count": 0,
        "pt_legal_leak_count": 0,
        "pt_institution_leak_count": 2,
        "exempted_address_hits": 0,
    }


def test_validate_enfr_rejects_portuguese_institution_leak_in_english() -> None:
    result = validate_enfr(
        "Public Prosecutor - Procuradoria da República da Comarca de Beja",
        lang=TargetLang.EN,
    )
    assert result.ok is False
    assert result.reason == "Portuguese legal/institution terms leaked after normalization."


def test_validate_enfr_rejects_portuguese_legal_abbreviation_leak() -> None:
    result = validate_enfr("See art. 117, n.º 2 do C. P. Penal.", lang=TargetLang.FR)
    assert result.ok is False
    assert result.reason == "Portuguese legal/institution terms leaked after normalization."
    assert result.details == {
        "pt_month_leak_count": 0,
        "pt_legal_leak_count": 1,
        "pt_institution_leak_count": 0,
        "exempted_address_hits": 0,
    }


def test_validate_enfr_rejects_mixed_portuguese_preposition_in_french_sentence() -> None:
    result = validate_enfr(
        "Le prévenu résidant na Rua 1.º de Dezembro, 2.º 7800-190 Beja",
        lang=TargetLang.FR,
    )
    assert result.ok is False
    assert result.reason == "Portuguese legal/institution terms leaked after normalization."
    assert result.details == {
        "pt_month_leak_count": 0,
        "pt_legal_leak_count": 1,
        "pt_institution_leak_count": 0,
        "exempted_address_hits": 1,
    }


def test_validate_enfr_allows_fully_translated_institution_lines() -> None:
    fr_result = validate_enfr(
        "Parquet près le tribunal de la circonscription de Beja",
        lang=TargetLang.FR,
    )
    en_result = validate_enfr(
        "Public Prosecution Office of the District of Beja",
        lang=TargetLang.EN,
    )
    assert fr_result.ok is True
    assert en_result.ok is True


def test_validate_enfr_without_lang_keeps_legacy_behavior() -> None:
    result = validate_enfr("Beja, 1.º de Março de 2026")
    assert result.ok is True
