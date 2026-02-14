from legalpdf_translate.output_normalize import LRI, PDI, normalize_output_text
from legalpdf_translate.types import TargetLang


def test_normalize_removes_blank_lines_and_normalizes_newlines() -> None:
    text = "line1\r\n\r\nline2   \n   \nline3"
    normalized = normalize_output_text(text, lang=TargetLang.EN)
    assert normalized == "line1\nline2\nline3"


def test_en_portuguese_month_date_is_normalized_to_english_month() -> None:
    text = "Beja, 10 de fevereiro de 2026"
    normalized = normalize_output_text(text, lang=TargetLang.EN)
    assert normalized == "Beja, 10 February 2026"


def test_fr_portuguese_month_date_is_normalized_to_french_month() -> None:
    text = "Beja, 10 de fevereiro de 2026"
    normalized = normalize_output_text(text, lang=TargetLang.FR)
    assert normalized == "Beja, 10 février 2026"


def test_en_portuguese_month_date_without_year_is_normalized_to_english_month() -> None:
    text = "Beja, 20 de Março às 11:30"
    normalized = normalize_output_text(text, lang=TargetLang.EN)
    assert normalized == "Beja, 20 March às 11:30"


def test_fr_portuguese_month_date_without_year_is_normalized_to_french_month() -> None:
    text = "Beja, 27 de Março à 09:00"
    normalized = normalize_output_text(text, lang=TargetLang.FR)
    assert normalized == "Beja, 27 mars à 09:00"


def test_enfr_slash_date_remains_unchanged() -> None:
    text = "Date: 09/02/2026"
    normalized_en = normalize_output_text(text, lang=TargetLang.EN)
    normalized_fr = normalize_output_text(text, lang=TargetLang.FR)
    assert normalized_en == text
    assert normalized_fr == text


def test_enfr_unknown_month_date_remains_unchanged() -> None:
    text = "Beja, 10 de fevereirx de 2026"
    normalized_en = normalize_output_text(text, lang=TargetLang.EN)
    normalized_fr = normalize_output_text(text, lang=TargetLang.FR)
    assert normalized_en == text
    assert normalized_fr == text


def test_enfr_address_line_with_month_word_is_not_rewritten() -> None:
    text = "Rua 1.º de Dezembro, 2.º 7800-190 Beja"
    normalized_en = normalize_output_text(text, lang=TargetLang.EN)
    normalized_fr = normalize_output_text(text, lang=TargetLang.FR)
    assert normalized_en == text
    assert normalized_fr == text


def test_arabic_isolate_autofix_wraps_existing_tokens_only() -> None:
    text = "نص [[ABC-123]] آخر"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == f"نص {LRI}[[ABC-123]]{PDI} آخر"


def test_arabic_isolate_autofix_does_not_double_wrap() -> None:
    text = f"نص {LRI}[[ABC-123]]{PDI} آخر"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == text


def test_arabic_isolate_autofix_repairs_partial_wrapping() -> None:
    text = f"نص {LRI}[[ABC-123]] آخر"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == f"نص {LRI}[[ABC-123]]{PDI} آخر"


def test_arabic_isolate_autofix_preserves_token_content() -> None:
    text = "x [[A/B.C-01]] y"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert "[[A/B.C-01]]" in normalized
    assert "[[[A/B.C-01]]]" not in normalized


def test_arabic_isolate_autofix_does_not_create_new_tokens() -> None:
    text = "لا توجد رموز هنا"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == text


def test_arabic_expected_token_literal_is_wrapped_deterministically() -> None:
    text = "الاسم: Adel Belghali"
    normalized = normalize_output_text(
        text,
        lang=TargetLang.AR,
        expected_ar_tokens=["Adel Belghali"],
    )
    assert normalized == f"الاسم: {LRI}[[Adel Belghali]]{PDI}"


def test_arabic_expected_token_partial_wrapper_is_repaired() -> None:
    text = f"الاسم: {LRI}[[Adel Belghali]]"
    normalized = normalize_output_text(
        text,
        lang=TargetLang.AR,
        expected_ar_tokens=["Adel Belghali"],
    )
    assert normalized == f"الاسم: {LRI}[[Adel Belghali]]{PDI}"


def test_arabic_portuguese_month_date_token_is_normalized_to_arabic_month() -> None:
    text = "بتاريخ [[10 de fevereiro de 2026]]"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == f"بتاريخ {LRI}[[10]]{PDI} فبراير {LRI}[[2026]]{PDI}"


def test_arabic_plain_portuguese_month_date_is_normalized_to_arabic_month() -> None:
    text = "بتاريخ 10 de fevereiro de 2026"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == f"بتاريخ {LRI}[[10]]{PDI} فبراير {LRI}[[2026]]{PDI}"


def test_arabic_unknown_month_date_falls_back_to_single_protected_token() -> None:
    text = "بتاريخ 10 de fevereirx de 2026"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == f"بتاريخ {LRI}[[10 de fevereirx de 2026]]{PDI}"


def test_arabic_slash_date_remains_single_protected_token() -> None:
    text = "بتاريخ [[09/02/2026]]"
    normalized = normalize_output_text(text, lang=TargetLang.AR)
    assert normalized == f"بتاريخ {LRI}[[09/02/2026]]{PDI}"
