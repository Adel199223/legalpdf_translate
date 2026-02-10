from legalpdf_translate.prompt_builder import build_page_prompt
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
