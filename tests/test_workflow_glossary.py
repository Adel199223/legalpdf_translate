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


def test_append_glossary_prompt_ignores_study_glossary_data() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [],
        "FR": [],
        "AR": [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 1)],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}
    workflow._study_glossary_entries = [  # type: ignore[attr-defined]
        {"term_pt": "acusação", "translations_by_lang": {"AR": "نص دراسة"}}
    ]

    prompt = workflow._append_glossary_prompt("BASE", TargetLang.AR, source_text="acusação")

    assert "<<<BEGIN GLOSSARY>>>" in prompt
    assert "الاتهام" in prompt
    assert "نص دراسة" not in prompt


def test_append_glossary_prompt_prepends_header_priority_matches_before_generic_rows() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [
            GlossaryEntry("Ministério Público", "Public Prosecutor's Office", "exact", "PT", 2),
            GlossaryEntry("arguido", "defendant", "exact", "PT", 2),
        ],
        "FR": [],
        "AR": [],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}

    prompt = workflow._append_glossary_prompt(
        "BASE",
        TargetLang.EN,
        source_text="Ministério Público - Procuradoria da República da Comarca de Beja",
    )

    assert "Public Prosecutor's Office - Republic Prosecutor's Office of the District of Beja" in prompt
    header_idx = prompt.index("Ministério Público - Procuradoria da República da Comarca de Beja")
    generic_idx = prompt.index("'Ministério Público' => 'Public Prosecutor's Office'")
    assert header_idx < generic_idx


def test_append_glossary_prompt_keeps_header_matches_when_generic_rows_hit_prompt_cap() -> None:
    workflow = TranslationWorkflow(client=object())
    workflow._prompt_glossaries_by_lang = {
        "EN": [GlossaryEntry(f"src-{i}", f"dst-{i}", "exact", "PT", 1) for i in range(120)],
        "FR": [],
        "AR": [],
    }
    workflow._enabled_glossary_tiers_by_lang = {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}

    prompt = workflow._append_glossary_prompt(
        "BASE",
        TargetLang.EN,
        source_text="Juízo Local Criminal de Beja\n" + "\n".join(f"src-{i}" for i in range(120)),
    )

    assert "'Juízo Local Criminal de Beja' => 'Local Criminal Division of Beja'" in prompt
