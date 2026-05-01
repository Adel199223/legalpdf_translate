from __future__ import annotations

from legalpdf_translate.legal_header_glossary import (
    extract_best_case_entity_match,
    match_legal_header_phrases,
    normalize_legal_header_text,
)


def test_normalize_legal_header_text_collapses_common_ocr_and_spacing_variants() -> None:
    assert normalize_legal_header_text("Via correio electrónico") == normalize_legal_header_text(
        "Via correio eletrónico"
    )
    assert normalize_legal_header_text("Notificação por carta registada (c / PR)") == normalize_legal_header_text(
        "Notificação por carta registada (c/PR)"
    )
    assert normalize_legal_header_text("Procuradoria do Juízo Local Criminal - 1re Sec") == normalize_legal_header_text(
        "Procuradoria do Juízo Local Criminal - 1ª Sec"
    )


def test_match_legal_header_phrases_maps_registered_notification_variant_across_languages() -> None:
    source = "Notificação por carta registada com Prova de Receção"
    en = match_legal_header_phrases(source, "EN")
    fr = match_legal_header_phrases(source, "FR")
    ar = match_legal_header_phrases(source, "AR")

    assert en[0].source_text == source
    assert en[0].preferred_translation == "Notification by registered mail (with acknowledgment of receipt)"
    assert fr[0].preferred_translation == "Notification par lettre recommandée (avec accusé de réception)"
    assert ar[0].preferred_translation == "تبليغ برسالة مضمونة (مع إشعار بالاستلام)"


def test_match_legal_header_phrases_extracts_template_family_with_city_and_judge() -> None:
    source = "Juízo Central Cível e Criminal de Beja - Juiz 2"
    matches = match_legal_header_phrases(source, "EN")

    assert matches[0].source_text == source
    assert matches[0].preferred_translation == "Central Civil and Criminal Division of Beja - Judge 2"
    assert matches[0].case_city == "Beja"


def test_match_legal_header_phrases_extracts_panel_phrase_without_case_number_noise() -> None:
    source = "Processo Comum (Tribunal Coletivo) 39/22.5GACUB"
    matches = match_legal_header_phrases(source, "FR")

    assert matches[0].source_text == "Processo Comum (Tribunal Coletivo)"
    assert matches[0].preferred_translation == "Procédure commune (formation collégiale)"


def test_match_legal_header_phrases_maps_juiz_de_direito_variant_to_canonical_source_text() -> None:
    matches = match_legal_header_phrases("Juiz de Direito", "AR")

    assert matches[0].source_text == "O Juiz de Direito"
    assert matches[0].preferred_translation == "القاضي"


def test_extract_best_case_entity_match_prefers_specific_prosecution_unit_over_generic_header() -> None:
    header = """
    Ministério Público - Procuradoria da República da Comarca de Beja
    Procuradoria do Juízo Local Criminal - 1ª Sec
    Inquéritos de Beja
    """

    match = extract_best_case_entity_match(header)

    assert match is not None
    assert match.source_text == "Procuradoria do Juízo Local Criminal - 1ª Sec"


def test_extract_best_case_entity_match_supports_general_jurisdiction_unit() -> None:
    header = "Tribunal Judicial da Comarca de Beja\nJuízo de Competência Genérica de Ferreira do Alentejo"

    match = extract_best_case_entity_match(header)

    assert match is not None
    assert match.source_text == "Juízo de Competência Genérica de Ferreira do Alentejo"
    assert match.case_city == "Ferreira do Alentejo"
