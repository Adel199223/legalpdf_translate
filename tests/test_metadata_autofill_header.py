from __future__ import annotations

from pathlib import Path

from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    choose_court_email_suggestion,
    extract_from_header_text,
    extract_pdf_header_metadata_priority_pages,
    rank_court_email_suggestions,
)


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


def test_extract_header_court_email_prefers_court_nearest_match() -> None:
    header = """
    contacto-geral@example.org
    Tribunal Judicial da Comarca de Beja
    Juízo Local Cível de Beja
    secretaria.beja@tribunais.org.pt
    Processo n.º 140/22.5JAFAR
    """
    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja"],
        ai_enabled=False,
    )
    assert suggestion.court_email == "secretaria.beja@tribunais.org.pt"


def test_extract_header_court_email_falls_back_to_first_email_when_no_court_nearby() -> None:
    header = """
    contacto.geral@example.org
    Processo n.º 140/22.5JAFAR
    Documento processado por terceiros
    """
    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja"],
        ai_enabled=False,
    )
    assert suggestion.court_email == "contacto.geral@example.org"


def test_priority_page_metadata_falls_back_to_second_page_email(monkeypatch) -> None:
    def _fake_header_text(_pdf_path: Path, *, page_number: int, config: MetadataAutofillConfig | None = None) -> str:
        del config
        if page_number == 1:
            return "Processo n.º 140/22.5JAFAR"
        return """
        Tribunal Judicial da Comarca de Beja
        Juízo Local Criminal de Beja
        expediente.beja@tribunais.org.pt
        """

    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_header_text_from_pdf_page_with_ocr_fallback",
        _fake_header_text,
    )

    suggestion = extract_pdf_header_metadata_priority_pages(
        Path("sample.pdf"),
        vocab_cities=["Beja"],
        config=MetadataAutofillConfig(metadata_ai_enabled=False),
    )

    assert suggestion.case_number == "140/22.5JAFAR"
    assert suggestion.case_entity == "Juízo Local Criminal de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.court_email == "expediente.beja@tribunais.org.pt"


def test_rank_court_email_suggestions_prefers_ministerio_publico_curated_match() -> None:
    ranked = rank_court_email_suggestions(
        exact_email=None,
        case_entity="Ministério Público - Família e Menores",
        case_city="Beja",
        vocab_court_emails=[
            "beja.judicial@tribunais.org.pt",
            "beja.ministeriopublico@tribunais.org.pt",
            "beja.familia.ministeriopublico@tribunais.org.pt",
        ],
    )
    assert ranked[0] == "beja.familia.ministeriopublico@tribunais.org.pt"
    assert ranked[1] == "beja.ministeriopublico@tribunais.org.pt"


def test_rank_court_email_suggestions_uses_alias_slug_for_reguengos_de_monsaraz() -> None:
    ranked = rank_court_email_suggestions(
        exact_email=None,
        case_entity="Tribunal Judicial",
        case_city="Reguengos de Monsaraz",
        vocab_court_emails=[
            "beja.judicial@tribunais.org.pt",
            "rmonsaraz.judicial@tribunais.org.pt",
        ],
    )
    assert ranked[0] == "rmonsaraz.judicial@tribunais.org.pt"


def test_choose_court_email_suggestion_prefers_exact_email_when_present() -> None:
    selected = choose_court_email_suggestion(
        exact_email="header.found@example.org",
        case_entity="Tribunal Judicial",
        case_city="Beja",
        vocab_court_emails=["beja.judicial@tribunais.org.pt"],
    )
    assert selected == "header.found@example.org"
