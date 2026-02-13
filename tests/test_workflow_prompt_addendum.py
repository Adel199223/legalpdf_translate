from __future__ import annotations

from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


def _make_workflow() -> TranslationWorkflow:
    return TranslationWorkflow(client=object())


def test_append_prompt_addendum_applies_only_for_target_language() -> None:
    workflow = _make_workflow()
    workflow._prompt_addendum_by_lang = {"EN": "Prefer legal register.", "FR": "", "AR": ""}  # type: ignore[attr-defined]

    prompt_en = workflow._append_prompt_addendum("BASE", TargetLang.EN)
    prompt_fr = workflow._append_prompt_addendum("BASE", TargetLang.FR)

    assert "<<<BEGIN ADDENDUM>>>" in prompt_en
    assert "Prefer legal register." in prompt_en
    assert "<<<END ADDENDUM>>>" in prompt_en
    assert prompt_fr == "BASE"


def test_append_prompt_addendum_noop_when_value_is_empty_or_whitespace() -> None:
    workflow = _make_workflow()
    workflow._prompt_addendum_by_lang = {"EN": "   ", "FR": "", "AR": ""}  # type: ignore[attr-defined]

    prompt = workflow._append_prompt_addendum("BASE", TargetLang.EN)
    assert prompt == "BASE"
