from legalpdf_translate.output_normalize import LRI, PDI, normalize_output_text
from legalpdf_translate.types import TargetLang


def test_normalize_removes_blank_lines_and_normalizes_newlines() -> None:
    text = "line1\r\n\r\nline2   \n   \nline3"
    normalized = normalize_output_text(text, lang=TargetLang.EN)
    assert normalized == "line1\nline2\nline3"


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
