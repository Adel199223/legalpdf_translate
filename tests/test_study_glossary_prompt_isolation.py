from __future__ import annotations

from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


def test_study_glossary_entries_are_not_used_for_prompt_injection() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {"EN": [], "FR": [], "AR": []}
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}
    # Simulate study-only data living on the workflow instance; prompt path must ignore it.
    workflow._study_glossary_entries = [  # type: ignore[attr-defined]
        {"term_pt": "acusação", "translations_by_lang": {"AR": "الاتهام"}}
    ]

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.AR, source_text="acusação")

    assert prompt == "BASE"
    assert "study_glossary_entries" not in prompt


def test_ai_glossary_prompt_injection_still_works_with_study_data_present() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [],
        "FR": [],
        "AR": [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 1)],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}
    workflow._study_glossary_entries = [  # type: ignore[attr-defined]
        {"term_pt": "acusação", "translations_by_lang": {"AR": "نص تعلمي"}}
    ]

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.AR, source_text="acusação")

    assert "<<<BEGIN GLOSSARY>>>" in prompt
    assert "study_glossary_entries" not in prompt
    assert "term_pt" not in prompt
    assert "نص تعلمي" not in prompt
    assert "الاتهام" in prompt
