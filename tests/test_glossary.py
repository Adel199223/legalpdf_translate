from __future__ import annotations

import json
from pathlib import Path

import pytest

from legalpdf_translate.glossary import (
    cap_entries_for_prompt,
    build_consistency_glossary_markdown,
    coerce_glossary_tier,
    GlossaryEntry,
    apply_glossary,
    builtin_glossary_json,
    detect_source_lang_for_glossary,
    default_ar_entries,
    default_ar_seed_preset_name,
    default_en_entries,
    default_fr_entries,
    default_seed_entries_for_target_lang,
    entries_from_legacy_rules,
    filter_entries_for_prompt,
    filter_entries_for_source_lang,
    format_glossary_for_prompt,
    load_glossary,
    load_glossary_from_text,
    normalize_enabled_tiers_by_target_lang,
    normalize_glossaries,
    seed_missing_entries_for_target_lang,
    seed_missing_ar_entries,
    serialize_glossaries,
    sort_entries_for_prompt,
    supported_target_langs,
    valid_glossary_tiers,
)
from legalpdf_translate.types import TargetLang


def _entry_tuple_set(entries: list[GlossaryEntry]) -> set[tuple[int, str, str, str, str]]:
    return {
        (entry.tier, entry.match_mode, entry.source_lang, entry.source_text, entry.preferred_translation)
        for entry in entries
    }


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
        {
            "AR": [
                {
                    "source_text": "honorários devidos",
                    "preferred_translation": "دفع الأتعاب المستحقة",
                    "match_mode": "contains",
                    "source_lang": "PT",
                    "tier": 1,
                }
            ]
        },
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
    serialized = serialize_glossaries(source)
    restored = normalize_glossaries(serialized, ["EN", "FR", "AR"])
    assert restored == source


def test_default_ar_entries_contains_two_seeded_rows() -> None:
    defaults = default_ar_entries()
    assert default_ar_seed_preset_name() == "PT→AR Court/Judgment (Tiered)"
    assert len(defaults) == 45
    expected_rows = {
        (1, "contains", "PT", "Notificação por carta registada", "تبليغ برسالة مضمونة"),
        (1, "contains", "PT", "com Prova de Receção", "مع إشعار بالاستلام"),
        (1, "exact", "PT", "Assunto: Tradução", "الموضوع: ترجمة"),
        (1, "exact", "PT", "Processo Comum (Tribunal Singular)", "مسطرة عادية (محكمة منفردة)"),
        (1, "exact", "PT", "SENTENÇA.", "حكم"),
        (1, "exact", "PT", "I – RELATÓRIO.", "أولاً – التقرير"),
        (1, "exact", "PT", "II – SANEAMENTO.", "ثانياً – المسائل التمهيدية"),
        (1, "exact", "PT", "III – FUNDAMENTAÇÃO.", "ثالثاً – التعليل"),
        (1, "exact", "PT", "A – DE FACTO.", "أ – من حيث الوقائع"),
        (1, "exact", "PT", "Factos Provados", "الوقائع الثابتة"),
        (1, "exact", "PT", "Factos não Provados", "الوقائع غير الثابتة"),
        (1, "exact", "PT", "B – DE DIREITO.", "ب – من حيث القانون"),
        (1, "exact", "PT", "IV – CUSTAS.", "رابعاً – المصاريف القضائية"),
        (1, "exact", "PT", "V – DISPOSITIVO.", "خامساً – المنطوق"),
        (2, "exact", "PT", "Ministério Público", "النيابة العامة"),
        (2, "contains", "PT", "deduziu acusação", "وجهت الاتهام"),
        (2, "exact", "PT", "acusação", "الاتهام"),
        (2, "exact", "PT", "peça acusatória", "لائحة الاتهام"),
        (2, "exact", "PT", "arguido", "المتهم"),
        (2, "exact", "PT", "arguida", "المتهمة"),
        (2, "exact", "PT", "contestação escrita", "مذكرة دفاع كتابية"),
        (2, "exact", "PT", "audiência de julgamento", "جلسة المحاكمة"),
        (2, "exact", "PT", "autos", "ملف الدعوى"),
        (2, "exact", "PT", "absolvição", "البراءة"),
        (3, "contains", "PT", "Fica V. Exª notificado", "يُخطر سيادتكم"),
        (3, "exact", "PT", "na qualidade de", "بصفتكم"),
        (3, "contains", "PT", "entregar nos autos", "إيداع بملف الدعوى"),
        (3, "exact", "PT", "no prazo de", "في أجل"),
        (3, "exact", "PT", "a tradução da sentença", "ترجمة الحكم"),
        (3, "contains", "PT", "cuja cópia se junta", "المرفقة نسخة منه"),
        (4, "contains", "PT", "p. e p. pelos artigos", "المعاقب عليها بمقتضى المواد"),
        (4, "exact", "PT", "alínea", "الفقرة"),
        (4, "exact", "PT", "n.º", "رقم"),
        (4, "exact", "PT", "doravante", "يشار إليه فيما بعد بـ"),
        (4, "exact", "PT", "in dubio pro reo", "مبدأ الشك يفسر لصالح المتهم"),
        (4, "exact", "PT", "presunção de inocência", "قرينة البراءة"),
        (5, "exact", "PT", "crime de falsificação de documento", "جريمة تزوير مستند"),
        (5, "exact", "PT", "documento falso", "مستند مزور"),
        (5, "exact", "PT", "falsificação material", "تزوير مادي"),
        (5, "exact", "PT", "falsificação intelectual", "تزوير معنوي"),
        (6, "exact", "PT", "Sem custas.", "دون مصاريف قضائية."),
        (6, "exact", "PT", "Notifique.", "يُبلغ."),
        (6, "contains", "PT", "Lida, vai proceder-se, de imediato, ao depósito da sentença", "بعد تلاوته، يتم فوراً إيداع الحكم"),
        (6, "exact", "PT", "Processei e revi", "حررت وراجعت"),
        (6, "exact", "PT", "O Juiz de Direito", "القاضي"),
    }
    actual_rows = {
        (entry.tier, entry.match_mode, entry.source_lang, entry.source_text, entry.preferred_translation)
        for entry in defaults
    }
    assert actual_rows == expected_rows


def test_default_en_entries_contains_expected_seed_rows() -> None:
    defaults = default_en_entries()
    assert len(defaults) == 45
    expected_rows = {
        (1, "contains", "PT", "Notificação por carta registada", "Notification by registered mail"),
        (1, "contains", "PT", "com Prova de Receção", "with acknowledgment of receipt"),
        (1, "exact", "PT", "Assunto: Tradução", "Subject: Translation"),
        (1, "exact", "PT", "Processo Comum (Tribunal Singular)", "Ordinary proceedings (single-judge court)"),
        (1, "exact", "PT", "SENTENÇA.", "JUDGMENT"),
        (1, "exact", "PT", "I – RELATÓRIO.", "I – REPORT"),
        (1, "exact", "PT", "II – SANEAMENTO.", "II – PRELIMINARY MATTERS"),
        (1, "exact", "PT", "III – FUNDAMENTAÇÃO.", "III – REASONS"),
        (1, "exact", "PT", "A – DE FACTO.", "A – FACTS"),
        (1, "exact", "PT", "Factos Provados", "Facts established"),
        (1, "exact", "PT", "Factos não Provados", "Facts not established"),
        (1, "exact", "PT", "B – DE DIREITO.", "B – LAW"),
        (1, "exact", "PT", "IV – CUSTAS.", "IV – COSTS"),
        (1, "exact", "PT", "V – DISPOSITIVO.", "V – OPERATIVE PART"),
        (2, "exact", "PT", "Ministério Público", "Public Prosecutor’s Office"),
        (2, "contains", "PT", "deduziu acusação", "brought charges"),
        (2, "exact", "PT", "acusação", "indictment"),
        (2, "exact", "PT", "peça acusatória", "bill of indictment"),
        (2, "exact", "PT", "arguido", "defendant"),
        (2, "exact", "PT", "arguida", "defendant"),
        (2, "exact", "PT", "contestação escrita", "written defence"),
        (2, "exact", "PT", "audiência de julgamento", "trial hearing"),
        (2, "exact", "PT", "autos", "case file"),
        (2, "exact", "PT", "absolvição", "acquittal"),
        (3, "contains", "PT", "Fica V. Exª notificado", "You are hereby notified"),
        (3, "exact", "PT", "na qualidade de", "in your capacity as"),
        (3, "contains", "PT", "entregar nos autos", "file with the case file"),
        (3, "exact", "PT", "no prazo de", "within"),
        (3, "exact", "PT", "a tradução da sentença", "the translation of the judgment"),
        (3, "contains", "PT", "cuja cópia se junta", "a copy of which is attached"),
        (4, "contains", "PT", "p. e p. pelos artigos", "punishable under Articles"),
        (4, "exact", "PT", "alínea", "subparagraph"),
        (4, "exact", "PT", "n.º", "No."),
        (4, "exact", "PT", "doravante", "hereinafter"),
        (4, "exact", "PT", "in dubio pro reo", "in dubio pro reo"),
        (4, "exact", "PT", "presunção de inocência", "presumption of innocence"),
        (5, "exact", "PT", "crime de falsificação de documento", "offence of document forgery"),
        (5, "exact", "PT", "documento falso", "forged document"),
        (5, "exact", "PT", "falsificação material", "material forgery"),
        (5, "exact", "PT", "falsificação intelectual", "intellectual forgery"),
        (6, "exact", "PT", "Sem custas.", "No costs."),
        (6, "exact", "PT", "Notifique.", "Notify."),
        (
            6,
            "contains",
            "PT",
            "Lida, vai proceder-se, de imediato, ao depósito da sentença",
            "Having been read, the judgment shall immediately be deposited",
        ),
        (6, "exact", "PT", "Processei e revi", "Drafted and reviewed"),
        (6, "exact", "PT", "O Juiz de Direito", "The Judge"),
    }
    assert _entry_tuple_set(defaults) == expected_rows


def test_default_fr_entries_contains_expected_seed_rows() -> None:
    defaults = default_fr_entries()
    assert len(defaults) == 45
    expected_rows = {
        (1, "contains", "PT", "Notificação por carta registada", "Notification par lettre recommandée"),
        (1, "contains", "PT", "com Prova de Receção", "avec accusé de réception"),
        (1, "exact", "PT", "Assunto: Tradução", "Objet : Traduction"),
        (1, "exact", "PT", "Processo Comum (Tribunal Singular)", "Procédure commune (juge unique)"),
        (1, "exact", "PT", "SENTENÇA.", "JUGEMENT"),
        (1, "exact", "PT", "I – RELATÓRIO.", "I – RAPPORT"),
        (1, "exact", "PT", "II – SANEAMENTO.", "II – RÉGULARITÉ DE LA PROCÉDURE"),
        (1, "exact", "PT", "III – FUNDAMENTAÇÃO.", "III – MOTIFS"),
        (1, "exact", "PT", "A – DE FACTO.", "A – EN FAIT"),
        (1, "exact", "PT", "Factos Provados", "Faits établis"),
        (1, "exact", "PT", "Factos não Provados", "Faits non établis"),
        (1, "exact", "PT", "B – DE DIREITO.", "B – EN DROIT"),
        (1, "exact", "PT", "IV – CUSTAS.", "IV – FRAIS"),
        (1, "exact", "PT", "V – DISPOSITIVO.", "V – DISPOSITIF"),
        (2, "exact", "PT", "Ministério Público", "Ministère public"),
        (2, "contains", "PT", "deduziu acusação", "a présenté l’acte d’accusation"),
        (2, "exact", "PT", "acusação", "acte d’accusation"),
        (2, "exact", "PT", "peça acusatória", "acte d’accusation"),
        (2, "exact", "PT", "arguido", "prévenu"),
        (2, "exact", "PT", "arguida", "prévenue"),
        (2, "exact", "PT", "contestação escrita", "mémoire en défense"),
        (2, "exact", "PT", "audiência de julgamento", "audience de jugement"),
        (2, "exact", "PT", "autos", "dossier de la procédure"),
        (2, "exact", "PT", "absolvição", "acquittement"),
        (3, "contains", "PT", "Fica V. Exª notificado", "Vous êtes par la présente notifié(e)"),
        (3, "exact", "PT", "na qualidade de", "en votre qualité de"),
        (3, "contains", "PT", "entregar nos autos", "verser au dossier"),
        (3, "exact", "PT", "no prazo de", "dans le délai de"),
        (3, "exact", "PT", "a tradução da sentença", "la traduction du jugement"),
        (3, "contains", "PT", "cuja cópia se junta", "dont copie est jointe"),
        (4, "contains", "PT", "p. e p. pelos artigos", "prévu et puni par les articles"),
        (4, "exact", "PT", "alínea", "alinéa"),
        (4, "exact", "PT", "n.º", "n°"),
        (4, "exact", "PT", "doravante", "ci-après"),
        (4, "exact", "PT", "in dubio pro reo", "in dubio pro reo"),
        (4, "exact", "PT", "presunção de inocência", "présomption d’innocence"),
        (5, "exact", "PT", "crime de falsificação de documento", "infraction de falsification de document"),
        (5, "exact", "PT", "documento falso", "document falsifié"),
        (5, "exact", "PT", "falsificação material", "falsification matérielle"),
        (5, "exact", "PT", "falsificação intelectual", "falsification intellectuelle"),
        (6, "exact", "PT", "Sem custas.", "Sans dépens."),
        (6, "exact", "PT", "Notifique.", "Notifier."),
        (
            6,
            "contains",
            "PT",
            "Lida, vai proceder-se, de imediato, ao depósito da sentença",
            "Lecture faite, il sera procédé immédiatement au dépôt du jugement",
        ),
        (6, "exact", "PT", "Processei e revi", "Rédigé et relu"),
        (6, "exact", "PT", "O Juiz de Direito", "Le juge"),
    }
    assert _entry_tuple_set(defaults) == expected_rows


def test_format_glossary_for_prompt_is_empty_when_no_rows() -> None:
    assert format_glossary_for_prompt("AR", []) == ""


def test_format_glossary_for_prompt_includes_guardrails() -> None:
    block = format_glossary_for_prompt(
        "AR",
        [
            GlossaryEntry(
                source_text="honorários devidos",
                preferred_translation="دفع الأتعاب المستحقة",
                match_mode="contains",
                source_lang="PT",
                tier=1,
            )
        ],
        detected_source_lang="PT",
    )
    assert "<<<BEGIN GLOSSARY>>>" in block
    assert "Do not rewrite IDs, IBANs, case numbers, addresses, dates, or names." in block
    assert "Detected source language: PT" in block
    assert "[T1][PT][contains] 'honorários devidos' => 'دفع الأتعاب المستحقة'" in block


def test_normalize_glossaries_migrates_legacy_row_shape_to_canonical() -> None:
    normalized = normalize_glossaries(
        {"AR": [{"source": "foo", "target": "bar", "match": "exact"}]},
        ["EN", "FR", "AR"],
    )
    assert normalized["AR"] == [
        GlossaryEntry(
            source_text="foo",
            preferred_translation="bar",
            match_mode="exact",
            source_lang="ANY",
            tier=2,
        )
    ]


def test_filter_entries_for_source_lang_includes_pt_any_auto() -> None:
    entries = [
        GlossaryEntry("pt-only", "x", "exact", "PT", 1),
        GlossaryEntry("any", "x", "exact", "ANY", 2),
        GlossaryEntry("auto", "x", "exact", "AUTO", 3),
        GlossaryEntry("en-only", "x", "exact", "EN", 4),
    ]
    filtered = filter_entries_for_source_lang(entries, "PT")
    assert [entry.source_text for entry in filtered] == ["pt-only", "any", "auto"]


def test_detect_source_lang_for_glossary_pt_sentence() -> None:
    detected = detect_source_lang_for_glossary("O processo não tem retenção de IRS e honorários devidos.")
    assert detected == "PT"


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
    assert migrated["AR"] == [
        GlossaryEntry(
            source_text="foo",
            preferred_translation="bar",
            match_mode="exact",
            source_lang="ANY",
            tier=2,
        )
    ]


def test_seed_missing_ar_entries_adds_all_entries_to_empty_glossary() -> None:
    seeded = seed_missing_ar_entries([])
    defaults = default_ar_entries()
    assert len(seeded) == len(defaults)
    assert seeded == sorted(seeded, key=lambda entry: (entry.tier, entry.source_text.casefold()))
    assert all(entry.source_lang == "PT" for entry in seeded)


def test_seed_missing_entries_for_target_lang_adds_all_entries_to_empty_en_and_fr() -> None:
    for lang, defaults in (("EN", default_en_entries()), ("FR", default_fr_entries())):
        seeded = seed_missing_entries_for_target_lang(lang, [])
        assert len(seeded) == len(defaults)
        assert seeded == sorted(seeded, key=lambda entry: (entry.tier, entry.source_text.casefold()))
        assert all(entry.source_lang == "PT" for entry in seeded)
        assert _entry_tuple_set(seeded) == _entry_tuple_set(defaults)
        assert default_seed_entries_for_target_lang(lang) == defaults


def test_seed_missing_ar_entries_preserves_user_rows_and_avoids_duplicates() -> None:
    user_row = GlossaryEntry(
        source_text="termo personalizado",
        preferred_translation="ترجمة مخصصة",
        match_mode="exact",
        source_lang="PT",
        tier=1,
    )
    seeded_row_equivalent = GlossaryEntry(
        source_text="Assunto: Tradução",
        preferred_translation="الموضوع: ترجمة",
        match_mode="contains",  # different match mode should still dedupe against seed key
        source_lang="PT",
        tier=1,
    )
    merged = seed_missing_ar_entries([user_row, seeded_row_equivalent])

    assert user_row in merged
    matching = [
        entry
        for entry in merged
        if entry.source_text == "Assunto: Tradução"
        and entry.preferred_translation == "الموضوع: ترجمة"
        and entry.source_lang == "PT"
        and entry.tier == 1
    ]
    assert len(matching) == 1


def test_seed_missing_entries_for_target_lang_preserves_user_rows_and_avoids_duplicates_for_en_fr() -> None:
    for lang, seeded_source, seeded_target in (
        ("EN", "Assunto: Tradução", "Subject: Translation"),
        ("FR", "Assunto: Tradução", "Objet : Traduction"),
    ):
        user_row = GlossaryEntry(
            source_text=f"termo personalizado {lang.lower()}",
            preferred_translation=f"custom {lang.lower()}",
            match_mode="exact",
            source_lang="PT",
            tier=1,
        )
        seeded_row_equivalent = GlossaryEntry(
            source_text=seeded_source,
            preferred_translation=seeded_target,
            match_mode="contains",
            source_lang="PT",
            tier=1,
        )
        merged = seed_missing_entries_for_target_lang(lang, [user_row, seeded_row_equivalent])

        assert user_row in merged
        matching = [
            entry
            for entry in merged
            if entry.source_text == seeded_source
            and entry.preferred_translation == seeded_target
            and entry.source_lang == "PT"
            and entry.tier == 1
        ]
        assert len(matching) == 1


def test_coerce_glossary_tier_clamps_invalid_values() -> None:
    assert coerce_glossary_tier("3") == 3
    assert coerce_glossary_tier(0) == 1
    assert coerce_glossary_tier(99) == 6
    assert coerce_glossary_tier("x") == 2


def test_valid_glossary_tiers_returns_one_to_six() -> None:
    assert valid_glossary_tiers() == [1, 2, 3, 4, 5, 6]


def test_normalize_enabled_tiers_defaults_and_future_langs() -> None:
    normalized = normalize_enabled_tiers_by_target_lang({}, ["EN", "FR", "AR", "ES"])
    assert normalized == {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2], "ES": [1, 2]}


def test_normalize_enabled_tiers_filters_invalid_values() -> None:
    normalized = normalize_enabled_tiers_by_target_lang({"AR": ["2", "2", "x", 7, 1]}, ["AR"])
    assert normalized["AR"] == [1, 2]


def test_build_consistency_glossary_markdown_uses_schema_columns_only() -> None:
    markdown = build_consistency_glossary_markdown(
        {
            "AR": [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 1)],
            "EN": [],
            "FR": [],
        },
        enabled_tiers_by_lang={"AR": [1, 3], "EN": [1, 2], "FR": [2]},
        generated_at_iso="2026-02-13T12:00:00",
        title="AI Glossary",
    )

    assert markdown.startswith("# AI Glossary")
    assert "## AR" in markdown
    assert "Enabled tiers: T1, T3" in markdown
    assert "| Source phrase (PDF text) | Preferred translation | Match | Source lang | Tier |" in markdown
    assert "| Notes |" not in markdown
    assert "acusação" in markdown


def test_filter_entries_for_prompt_filters_by_source_lang_and_enabled_tiers() -> None:
    entries = [
        GlossaryEntry("pt-tier1", "a", "exact", "PT", 1),
        GlossaryEntry("pt-tier3", "b", "exact", "PT", 3),
        GlossaryEntry("any-tier2", "c", "exact", "ANY", 2),
        GlossaryEntry("en-tier1", "d", "exact", "EN", 1),
    ]
    filtered = filter_entries_for_prompt(entries, detected_source_lang="PT", enabled_tiers=[1, 2])
    assert [entry.source_text for entry in filtered] == ["pt-tier1", "any-tier2"]


def test_sort_entries_for_prompt_orders_by_tier_then_source_length() -> None:
    entries = [
        GlossaryEntry("xx", "a", "exact", "ANY", 2),
        GlossaryEntry("very long source", "b", "exact", "ANY", 2),
        GlossaryEntry("tier one", "c", "exact", "ANY", 1),
    ]
    sorted_entries = sort_entries_for_prompt(entries)
    assert [entry.source_text for entry in sorted_entries] == ["tier one", "very long source", "xx"]


def test_cap_entries_for_prompt_is_deterministic_and_caps_by_entries() -> None:
    entries = [
        GlossaryEntry(f"src-{i}", f"dst-{i}", "exact", "ANY", 1)
        for i in range(60)
    ]
    capped = cap_entries_for_prompt(
        entries,
        target_lang="AR",
        detected_source_lang="AUTO",
        max_entries=50,
        max_chars=100000,
    )
    assert len(capped) == 50
    assert capped[0].source_text == "src-0"
    assert capped[-1].source_text == "src-49"


def test_cap_entries_for_prompt_caps_by_chars() -> None:
    entries = [
        GlossaryEntry("a" * 500, "b" * 500, "contains", "ANY", 1),
        GlossaryEntry("c" * 500, "d" * 500, "contains", "ANY", 1),
    ]
    capped = cap_entries_for_prompt(
        entries,
        target_lang="AR",
        detected_source_lang="AUTO",
        max_entries=50,
        max_chars=900,
    )
    assert capped == []
