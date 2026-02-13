from __future__ import annotations

from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.types import TargetLang
from legalpdf_translate.validators import validate_ar
from legalpdf_translate.workflow import TranslationWorkflow


def test_evaluate_output_applies_glossary_for_ar_after_validation() -> None:
    workflow = TranslationWorkflow(client=object())
    raw_output = "```\nتم صرف الأتعاب، ويؤكد النص أنه لا يخضع لأي حجز.\n```"

    result = workflow._evaluate_output(raw_output, TargetLang.AR)

    assert result.ok is True
    assert result.normalized_text is not None
    assert "دفع الأتعاب المستحقة" in result.normalized_text
    assert "لا يخضع لأي استقطاع (IRS)" in result.normalized_text
    # Confirms glossary runs after AR validator, since canonical text includes IRS.
    assert validate_ar(result.normalized_text).ok is False


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
        "AR": [GlossaryEntry(source="صرف الأتعاب", target="دفع الأتعاب المستحقة", match="contains")],
    }

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.AR)

    assert prompt.startswith("BASE\n")
    assert "<<<BEGIN GLOSSARY>>>" in prompt
    assert "صرف الأتعاب => دفع الأتعاب المستحقة" in prompt


def test_append_glossary_prompt_noop_when_language_has_no_entries() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {"EN": [], "FR": [], "AR": []}

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.FR)

    assert prompt == "BASE"
