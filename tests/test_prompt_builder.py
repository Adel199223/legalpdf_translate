from legalpdf_translate.prompt_builder import (
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
