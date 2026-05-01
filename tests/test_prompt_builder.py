from legalpdf_translate.prompt_builder import (
    build_ar_token_retry_prompt,
    build_language_retry_prompt,
    build_page_prompt,
    build_retry_prompt,
)
from legalpdf_translate.types import TargetLang


def test_prompt_builder_en_includes_marker_and_delimiters() -> None:
    prompt = build_page_prompt(
        lang=TargetLang.EN,
        page_number=2,
        total_pages=10,
        source_text="SOURCE",
        context_text=None,
    )
    lines = prompt.split("\n")
    assert lines[0] == "EN"
    assert lines[1] == "<<<PAGE 2 OF 10>>>"
    assert "<<<BEGIN SOURCE>>>" in lines
    assert "<<<END SOURCE>>>" in lines


def test_prompt_builder_ar_has_no_enfr_marker_and_keeps_context() -> None:
    prompt = build_page_prompt(
        lang=TargetLang.AR,
        page_number=1,
        total_pages=4,
        source_text="TEXT",
        context_text="CTX",
    )
    lines = prompt.split("\n")
    assert lines[0] == "<<<PAGE 1 OF 4>>>"
    assert "<<<BEGIN CONTEXT>>>" in lines
    assert "CTX" in lines
    assert "<<<END CONTEXT>>>" in lines


def test_retry_prompt_en_includes_english_language_hint_and_markers() -> None:
    prompt = build_retry_prompt(TargetLang.EN, "PRIOR")
    assert "Keep the output strictly in English." in prompt
    assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
    assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_retry_prompt_fr_includes_french_language_hint_and_markers() -> None:
    prompt = build_retry_prompt(TargetLang.FR, "PRIOR")
    assert "Keep the output strictly in French." in prompt
    assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
    assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_retry_prompt_ar_keeps_shared_header_without_language_hint() -> None:
    prompt = build_retry_prompt(TargetLang.AR, "PRIOR")
    assert "COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only," in prompt
    assert "strictly in English" not in prompt
    assert "strictly in French" not in prompt
    assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
    assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_ar_token_retry_prompt_includes_locked_token_inventory_and_markers() -> None:
    prompt = build_ar_token_retry_prompt("PRIOR", ["Adel Belghali", "PT50003506490000832760029"])
    assert "ARABIC TOKEN CORRECTION ONLY" in prompt
    assert "<<<BEGIN LOCKED TOKENS>>>" in prompt
    assert "1. [[Adel Belghali]]" in prompt
    assert "2. [[PT50003506490000832760029]]" in prompt
    assert "Do not translate, edit, split, remove, reorder, or add token contents." in prompt
    assert "Every listed token must appear only inside [[...]]." in prompt
    assert "No Latin letters or digits may appear outside protected tokens." in prompt
    assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
    assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_ar_token_retry_prompt_highlights_outside_token_violation() -> None:
    prompt = build_ar_token_retry_prompt(
        "PRIOR",
        ["Adel Belghali"],
        violation_kind="latin_or_digits_outside_wrapped_tokens",
    )
    assert "CURRENT DEFECT TO FIX: Latin letters or digits still appear outside [[...]] tokens." in prompt
    assert "Wrap every verbatim identifier span in [[...]]" in prompt


def test_ar_token_retry_prompt_includes_source_and_mismatch_summary_when_available() -> None:
    prompt = build_ar_token_retry_prompt(
        "PRIOR",
        ["342", "Beja"],
        source_text="Fonte original da pagina",
        violation_kind="expected_token_mismatch",
        defect_reason="Expected locked token mismatch.",
        token_details={
            "violation_kind": "expected_token_mismatch",
            "missing_count": 1,
            "altered_count": 1,
            "missing_token_samples": ["342"],
            "unexpected_token_samples": ["Beja"],
        },
    )
    assert "<<<BEGIN TOKEN MISMATCH SUMMARY>>>" in prompt
    assert "Validator reason: Expected locked token mismatch." in prompt
    assert "Violation kind: expected_token_mismatch" in prompt
    assert "Missing token samples:" in prompt
    assert "- [[342]]" in prompt
    assert "Unexpected or altered token samples:" in prompt
    assert "- [[Beja]]" in prompt
    assert "<<<BEGIN SOURCE PAGE>>>" in prompt
    assert "Fonte original da pagina" in prompt
    assert "<<<END SOURCE PAGE>>>" in prompt


def test_language_retry_prompt_fr_has_language_correction_header_and_markers() -> None:
    prompt = build_language_retry_prompt(TargetLang.FR, "PRIOR")
    assert "LANGUAGE CORRECTION ONLY: Re-emit the SAME content, fix language compliance only" in prompt
    assert "Re-emit in legal French only; remove Portuguese residual terms" in prompt
    assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
    assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_language_retry_prompt_en_has_language_correction_header_and_markers() -> None:
    prompt = build_language_retry_prompt(TargetLang.EN, "PRIOR")
    assert "LANGUAGE CORRECTION ONLY: Re-emit the SAME content, fix language compliance only" in prompt
    assert "Re-emit in legal English only; remove Portuguese residual terms" in prompt
    assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
    assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_language_retry_prompt_ar_allows_portuguese_only_inside_protected_tokens() -> None:
    prompt = build_language_retry_prompt(TargetLang.AR, "PRIOR")
    assert "Portuguese is allowed only inside verbatim protected [[...]] tokens." in prompt
    assert "Outside protected tokens, all remaining text must be Arabic." in prompt
