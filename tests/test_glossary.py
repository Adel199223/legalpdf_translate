from __future__ import annotations

import json
from pathlib import Path

import pytest

from legalpdf_translate.glossary import (
    GlossaryEntry,
    apply_glossary,
    builtin_glossary_json,
    default_ar_entries,
    entries_from_legacy_rules,
    format_glossary_for_prompt,
    load_glossary,
    load_glossary_from_text,
    normalize_glossaries,
    serialize_glossaries,
    supported_target_langs,
)
from legalpdf_translate.types import TargetLang


def test_builtin_glossary_applies_preferred_ar_phrases() -> None:
    rules = load_glossary(None)
    text = "تم صرف الأتعاب وهو نص قانوني لا يخضع لأي حجز (IRS)."

    output = apply_glossary(text, TargetLang.AR, rules)

    assert "دفع الأتعاب المستحقة" in output
    assert "لا يخضع لأي استقطاع (IRS)" in output


def test_glossary_does_not_change_en_or_fr() -> None:
    rules = load_glossary(None)
    text = "This sentence should stay unchanged."

    assert apply_glossary(text, TargetLang.EN, rules) == text
    assert apply_glossary(text, TargetLang.FR, rules) == text


def test_glossary_respects_protected_tokens() -> None:
    rules = load_glossary(None)
    text = "\u2066[[صرف الأتعاب]]\u2069 وصرف الأتعاب"

    output = apply_glossary(text, TargetLang.AR, rules)

    assert "\u2066[[صرف الأتعاب]]\u2069" in output
    assert output.endswith("ودفع الأتعاب المستحقة")


def test_load_glossary_rejects_malformed_json(tmp_path: Path) -> None:
    glossary_path = tmp_path / "bad_glossary.json"
    glossary_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid glossary JSON"):
        load_glossary(glossary_path)


def test_load_glossary_rejects_invalid_rules(tmp_path: Path) -> None:
    glossary_path = tmp_path / "bad_rules.json"
    payload = {
        "version": 1,
        "rules": [
            {
                "target_lang": "AR",
                "match_type": "literal",
                "match": "صرف الأتعاب",
                "replace": "دفع الأتعاب المستحقة\u2066",
            }
        ],
    }
    glossary_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="isolate controls"):
        load_glossary(glossary_path)


def test_glossary_output_does_not_introduce_isolates() -> None:
    rules = load_glossary(None)
    text = "صرف الأتعاب ولا يخضع لأي حجز (IRS)"

    output = apply_glossary(text, TargetLang.AR, rules)

    for marker in ("\u2066", "\u2067", "\u2068", "\u2069"):
        assert marker not in output


def test_load_glossary_from_text_accepts_builtin_payload() -> None:
    rules = load_glossary_from_text(builtin_glossary_json(), source="builtin-json")
    assert rules


def test_normalize_glossaries_adds_missing_supported_lang_keys() -> None:
    normalized = normalize_glossaries(
        {"AR": [{"source": "صرف الأتعاب", "target": "دفع الأتعاب المستحقة", "match": "contains"}]},
        supported_target_langs(),
    )
    assert set(normalized.keys()) == {"EN", "FR", "AR"}
    assert normalized["EN"] == []
    assert normalized["FR"] == []
    assert normalized["AR"]


def test_normalize_glossaries_supports_future_lang_addition() -> None:
    normalized = normalize_glossaries({}, ["EN", "FR", "AR", "ES"])
    assert set(normalized.keys()) == {"EN", "FR", "AR", "ES"}
    assert normalized["ES"] == []


def test_serialize_glossaries_round_trip() -> None:
    source = {
        "EN": [],
        "FR": [],
        "AR": [GlossaryEntry(source="صرف الأتعاب", target="دفع الأتعاب المستحقة", match="contains")],
    }
    serialized = serialize_glossaries(source)
    restored = normalize_glossaries(serialized, ["EN", "FR", "AR"])
    assert restored == source


def test_default_ar_entries_contains_two_seeded_rows() -> None:
    defaults = default_ar_entries()
    assert len(defaults) == 2
    assert any(entry.target == "دفع الأتعاب المستحقة" for entry in defaults)
    assert any(entry.target == "لا يخضع لأي استقطاع (IRS)" for entry in defaults)


def test_format_glossary_for_prompt_is_empty_when_no_rows() -> None:
    assert format_glossary_for_prompt("AR", []) == ""


def test_format_glossary_for_prompt_includes_guardrails() -> None:
    block = format_glossary_for_prompt(
        "AR",
        [GlossaryEntry(source="صرف الأتعاب", target="دفع الأتعاب المستحقة", match="contains")],
    )
    assert "<<<BEGIN GLOSSARY>>>" in block
    assert "Do not rewrite IDs, IBANs, case numbers, addresses, dates, or names." in block
    assert "[contains] صرف الأتعاب => دفع الأتعاب المستحقة" in block


def test_entries_from_legacy_rules_maps_literal_rules_only(tmp_path: Path) -> None:
    glossary_path = tmp_path / "legacy_glossary.json"
    glossary_path.write_text(
        json.dumps(
            {
                "version": 1,
                "rules": [
                    {"target_lang": "AR", "match_type": "literal", "match": "foo", "replace": "bar"},
                    {"target_lang": "AR", "match_type": "regex", "match": "x+", "replace": "y"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    migrated = entries_from_legacy_rules(glossary_path)
    assert migrated["AR"] == [GlossaryEntry(source="foo", target="bar", match="exact")]
