from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate.glossary import GlossaryEntry, load_project_glossaries, merge_glossary_scopes


def test_merge_glossary_scopes_prefers_personal_on_conflict() -> None:
    project = {
        "AR": [GlossaryEntry("acusação", "اتهام قديم", "exact", "PT", 2)],
        "EN": [],
        "FR": [],
    }
    personal = {
        "AR": [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 2)],
        "EN": [GlossaryEntry("acusação", "indictment", "exact", "PT", 2)],
        "FR": [],
    }

    merged = merge_glossary_scopes(project, personal, supported_langs=["EN", "FR", "AR"])

    assert merged["AR"] == [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 2)]
    assert merged["EN"] == [GlossaryEntry("acusação", "indictment", "exact", "PT", 2)]
    assert merged["FR"] == []


def test_merge_glossary_scopes_expands_future_languages() -> None:
    merged = merge_glossary_scopes(
        {"AR": [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 2)]},
        {"EN": [GlossaryEntry("acusação", "indictment", "exact", "PT", 2)]},
        supported_langs=["EN", "FR", "AR", "ES"],
    )

    assert set(merged.keys()) == {"EN", "FR", "AR", "ES"}
    assert merged["ES"] == []


def test_load_project_glossaries_supports_table_format(tmp_path: Path) -> None:
    path = tmp_path / "project_glossary.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "format": "table_glossaries",
                "glossaries_by_lang": {
                    "AR": [
                        {
                            "source_text": "acusação",
                            "preferred_translation": "الاتهام",
                            "match_mode": "exact",
                            "source_lang": "PT",
                            "tier": 2,
                        }
                    ],
                    "EN": [],
                    "FR": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    loaded = load_project_glossaries(path)

    assert loaded["AR"] == [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 2)]
