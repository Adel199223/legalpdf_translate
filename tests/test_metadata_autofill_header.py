from __future__ import annotations

from legalpdf_translate.metadata_autofill import extract_from_header_text


def test_extract_header_metadata_with_court_pattern_and_case_number() -> None:
    header = """
    Tribunal Judicial da Comarca de Beja
    Juízo Local Criminal de Beja
    Processo n.º 140/22.5JAFAR
    """
    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja", "Moura"],
        ai_enabled=False,
    )
    assert suggestion.case_entity is not None
    assert "Juízo Local Criminal de Beja" in suggestion.case_entity
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "140/22.5JAFAR"


def test_extract_header_city_from_comarca_heuristic() -> None:
    header = """
    Tribunal Judicial da Comarca de Serpa
    Ministério Público
    Processo 69/26.8PBBBJA
    """
    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja", "Moura"],
        ai_enabled=False,
    )
    assert suggestion.case_entity is not None
    assert "Ministério Público" in suggestion.case_entity
    assert suggestion.case_city == "Serpa"
    assert suggestion.case_number == "69/26.8PBBBJA"
