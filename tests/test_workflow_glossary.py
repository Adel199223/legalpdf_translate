from __future__ import annotations

from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


def test_evaluate_output_no_longer_applies_glossary_replacement_for_ar() -> None:
    workflow = TranslationWorkflow(client=object())
    raw_output = "```\nتم صرف الأتعاب، ويؤكد النص أنه لا يخضع لأي حجز.\n```"

    result = workflow._evaluate_output(raw_output, TargetLang.AR)

    assert result.ok is True
    assert result.normalized_text is not None
    assert "صرف الأتعاب" in result.normalized_text
    assert "لا يخضع لأي حجز" in result.normalized_text


def test_evaluate_output_does_not_apply_glossary_for_non_ar() -> None:
    workflow = TranslationWorkflow(client=object())
    raw_output = "```\nThe fee payment wording should remain untouched.\n```"

    result = workflow._evaluate_output(raw_output, TargetLang.EN)

    assert result.ok is True
    assert result.normalized_text == "The fee payment wording should remain untouched."


def test_append_glossary_prompt_adds_block_for_target_language() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [],
        "FR": [],
        "AR": [
            GlossaryEntry(
                source_text="honorários devidos",
                preferred_translation="دفع الأتعاب المستحقة",
                match_mode="contains",
                source_lang="PT",
                tier=1,
            )
        ],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}

    prompt = workflow._append_glossary_prompt(
        "BASE",
        TargetLang.AR,
        source_text="O processo menciona honorários devidos.",
    )

    assert prompt.startswith("BASE\n")
    assert "<<<BEGIN GLOSSARY>>>" in prompt
    assert "Detected source language: PT" in prompt
    assert "[T1][PT][contains] 'honorários devidos' => 'دفع الأتعاب المستحقة'" in prompt


def test_append_glossary_prompt_noop_when_language_has_no_entries() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {"EN": [], "FR": [], "AR": []}
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.FR, source_text="Source")

    assert prompt == "BASE"


def test_append_glossary_prompt_filters_rows_by_detected_source_lang() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [],
        "FR": [],
        "AR": [
            GlossaryEntry("pt-only", "x", "exact", "PT", 1),
            GlossaryEntry("any", "x", "exact", "ANY", 1),
            GlossaryEntry("en-only", "x", "exact", "EN", 1),
        ],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}

    prompt = workflow._append_glossary_prompt(
        "BASE",
        TargetLang.AR,
        source_text="O texto base inclui honorários e retenção.",
    )

    assert "pt-only" in prompt
    assert "any" in prompt
    assert "en-only" not in prompt


def test_append_glossary_prompt_excludes_disabled_tiers() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [],
        "FR": [],
        "AR": [
            GlossaryEntry("tier1", "a", "exact", "ANY", 1),
            GlossaryEntry("tier3", "b", "exact", "ANY", 3),
        ],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.AR, source_text="Source")

    assert "tier1" in prompt
    assert "tier3" not in prompt


def test_append_glossary_prompt_caps_entries_deterministically() -> None:
    workflow = TranslationWorkflow(client=object())
    many_entries = [GlossaryEntry(f"src-{i}", f"dst-{i}", "exact", "ANY", 1) for i in range(80)]
    workflow._prompt_glossaries_by_lang = {"EN": [], "FR": [], "AR": many_entries}
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1]}

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.AR, source_text="Source")

    assert "src-10" in prompt
    assert "src-59" in prompt
    assert "src-60" not in prompt
