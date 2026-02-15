"""Prompt structure regression tests.

Verifies section ordering, required markers, glossary block conditional
inclusion, and addendum block format.
"""
from __future__ import annotations

from legalpdf_translate.glossary import GlossaryEntry, format_glossary_for_prompt
from legalpdf_translate.prompt_builder import (
    build_language_retry_prompt,
    build_page_prompt,
    build_retry_prompt,
)
from legalpdf_translate.types import TargetLang


# ---------------------------------------------------------------------------
# Section ordering
# ---------------------------------------------------------------------------


def test_en_prompt_section_order() -> None:
    """EN prompt has: language marker, page marker, source block — in order."""
    prompt = build_page_prompt(
        lang=TargetLang.EN, page_number=3, total_pages=20,
        source_text="Legal text here.", context_text=None,
    )
    lines = prompt.splitlines()
    lang_idx = lines.index("EN")
    page_idx = next(i for i, l in enumerate(lines) if l.startswith("<<<PAGE"))
    src_begin = next(i for i, l in enumerate(lines) if l == "<<<BEGIN SOURCE>>>")
    src_end = next(i for i, l in enumerate(lines) if l == "<<<END SOURCE>>>")
    assert lang_idx < page_idx < src_begin < src_end


def test_fr_prompt_section_order() -> None:
    """FR prompt has: language marker, page marker, source block — in order."""
    prompt = build_page_prompt(
        lang=TargetLang.FR, page_number=1, total_pages=5,
        source_text="Texte.", context_text=None,
    )
    lines = prompt.splitlines()
    assert lines[0] == "FR"
    assert lines[1].startswith("<<<PAGE")


def test_ar_prompt_has_no_language_marker() -> None:
    """AR prompt starts directly with page marker, no EN/FR line."""
    prompt = build_page_prompt(
        lang=TargetLang.AR, page_number=1, total_pages=1,
        source_text="نص", context_text=None,
    )
    lines = prompt.splitlines()
    assert lines[0].startswith("<<<PAGE")
    assert "EN" not in lines
    assert "FR" not in lines


def test_context_block_precedes_source_block() -> None:
    """When context is provided, it appears between page marker and source."""
    prompt = build_page_prompt(
        lang=TargetLang.EN, page_number=1, total_pages=1,
        source_text="SOURCE", context_text="CONTEXT",
    )
    lines = prompt.splitlines()
    ctx_begin = lines.index("<<<BEGIN CONTEXT>>>")
    ctx_end = lines.index("<<<END CONTEXT>>>")
    src_begin = lines.index("<<<BEGIN SOURCE>>>")
    assert ctx_begin < ctx_end < src_begin


def test_no_context_block_when_none() -> None:
    """When context is None, no context markers appear."""
    prompt = build_page_prompt(
        lang=TargetLang.EN, page_number=1, total_pages=1,
        source_text="SOURCE", context_text=None,
    )
    assert "<<<BEGIN CONTEXT>>>" not in prompt
    assert "<<<END CONTEXT>>>" not in prompt


# ---------------------------------------------------------------------------
# Source text preserved verbatim
# ---------------------------------------------------------------------------


def test_source_text_preserved_verbatim() -> None:
    """Source text appears exactly between markers, not modified."""
    source = "Artigo 1.º\nO arguido é notificado."
    prompt = build_page_prompt(
        lang=TargetLang.EN, page_number=1, total_pages=1,
        source_text=source, context_text=None,
    )
    lines = prompt.splitlines()
    src_begin = lines.index("<<<BEGIN SOURCE>>>")
    src_end = lines.index("<<<END SOURCE>>>")
    inner = "\n".join(lines[src_begin + 1 : src_end])
    assert inner == source


# ---------------------------------------------------------------------------
# Glossary block
# ---------------------------------------------------------------------------


def test_glossary_block_format_with_entries() -> None:
    """format_glossary_for_prompt produces correct delimiters and entry format."""
    entries = [
        GlossaryEntry(
            source_text="arguido",
            preferred_translation="defendant",
            match_mode="exact",
            source_lang="PT",
            tier=2,
        ),
        GlossaryEntry(
            source_text="tribunal",
            preferred_translation="court",
            match_mode="contains",
            source_lang="ANY",
            tier=1,
        ),
    ]
    block = format_glossary_for_prompt("EN", entries, detected_source_lang="PT")
    lines = block.splitlines()
    assert lines[0] == "<<<BEGIN GLOSSARY>>>"
    assert lines[-1] == "<<<END GLOSSARY>>>"
    assert "Target language: EN" in block
    assert "Detected source language: PT" in block
    # Entry format
    assert "1. [T2][PT][exact] 'arguido' => 'defendant'" in block
    assert "2. [T1][ANY][contains] 'tribunal' => 'court'" in block


def test_glossary_block_empty_when_no_entries() -> None:
    """format_glossary_for_prompt returns empty string when no entries."""
    block = format_glossary_for_prompt("EN", [], detected_source_lang="PT")
    assert block == ""


def test_glossary_block_not_in_prompt_by_default() -> None:
    """build_page_prompt does not include glossary markers (appended later)."""
    prompt = build_page_prompt(
        lang=TargetLang.EN, page_number=1, total_pages=1,
        source_text="text", context_text=None,
    )
    assert "<<<BEGIN GLOSSARY>>>" not in prompt
    assert "<<<END GLOSSARY>>>" not in prompt


# ---------------------------------------------------------------------------
# Retry prompts
# ---------------------------------------------------------------------------


def test_retry_prompt_contains_compliance_header() -> None:
    """Compliance retry contains the exact header phrase."""
    for lang in (TargetLang.EN, TargetLang.FR, TargetLang.AR):
        prompt = build_retry_prompt(lang, "output")
        assert "COMPLIANCE FIX ONLY" in prompt
        assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt
        assert "output" in prompt
        assert "<<<END PRIOR OUTPUT>>>" in prompt


def test_language_retry_prompt_contains_correction_header() -> None:
    """Language correction retry contains the exact header phrase."""
    for lang in (TargetLang.EN, TargetLang.FR, TargetLang.AR):
        prompt = build_language_retry_prompt(lang, "output")
        assert "LANGUAGE CORRECTION ONLY" in prompt
        assert "<<<BEGIN PRIOR OUTPUT>>>" in prompt


def test_retry_prompts_preserve_prior_output_verbatim() -> None:
    """Prior output appears verbatim between markers in both retry types."""
    prior = "Line 1\nLine 2\nSpecial chars: <<>>"
    for builder in (build_retry_prompt, build_language_retry_prompt):
        prompt = builder(TargetLang.EN, prior)
        lines = prompt.splitlines()
        begin = lines.index("<<<BEGIN PRIOR OUTPUT>>>")
        end = lines.index("<<<END PRIOR OUTPUT>>>")
        inner = "\n".join(lines[begin + 1 : end])
        assert inner == prior


# ---------------------------------------------------------------------------
# Page marker format
# ---------------------------------------------------------------------------


def test_page_marker_format() -> None:
    """Page marker uses exact format <<<PAGE n OF total>>>."""
    prompt = build_page_prompt(
        lang=TargetLang.EN, page_number=7, total_pages=42,
        source_text="x", context_text=None,
    )
    assert "<<<PAGE 7 OF 42>>>" in prompt
