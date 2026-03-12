from __future__ import annotations

from pathlib import Path

import legalpdf_translate.metadata_autofill as metadata_autofill
from legalpdf_translate.court_email import resolve_court_email_selection
from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    choose_court_email_suggestion,
    extract_from_header_text,
    extract_interpretation_notification_metadata_from_pdf,
    extract_interpretation_notification_metadata_from_text,
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


def test_rank_court_email_suggestions_prefers_canonical_org_domain_for_same_local_conflicts() -> None:
    ranked = rank_court_email_suggestions(
        exact_email=None,
        case_entity="Ministério Público",
        case_city="Beja",
        vocab_court_emails=[
            "beja.ministeriopublico@tribunais.gov.pt",
            "beja.ministeriopublico@tribunais.org.pt",
        ],
    )

    assert ranked[0] == "beja.ministeriopublico@tribunais.org.pt"
    assert ranked[1] == "beja.ministeriopublico@tribunais.gov.pt"


def test_resolve_court_email_selection_flags_same_local_domain_conflicts_as_ambiguous() -> None:
    resolution = resolve_court_email_selection(
        document_email=None,
        document_source=None,
        case_entity="Ministério Público",
        case_city="Beja",
        vocab_court_emails=[
            "beja.ministeriopublico@tribunais.gov.pt",
            "beja.ministeriopublico@tribunais.org.pt",
        ],
    )

    assert resolution.selected_email == "beja.ministeriopublico@tribunais.org.pt"
    assert resolution.ambiguous is True
    assert resolution.requires_manual_confirmation is True


def test_resolve_api_client_uses_bounded_retry_and_timeout(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(
            self,
            *,
            api_key: str,
            base_url: str | None = None,
            max_retries: int = 99,
            timeout: float | None = None,
        ) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["max_retries"] = max_retries
            captured["timeout"] = timeout

    monkeypatch.setattr(metadata_autofill, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(metadata_autofill, "get_ocr_key", lambda: "stored-key")

    client = metadata_autofill._resolve_api_client(
        MetadataAutofillConfig(
            metadata_ai_enabled=True,
            ocr_api_base_url="https://example.invalid/v1",
            metadata_ai_timeout_seconds=120.0,
        )
    )

    assert client is not None
    assert captured == {
        "api_key": "stored-key",
        "base_url": "https://example.invalid/v1",
        "max_retries": 0,
        "timeout": 120.0,
    }


def test_extract_interpretation_notification_metadata_prefers_hearing_date_over_issue_date() -> None:
    notification_text = """
    Tribunal Judicial da Comarca de Évora
    Juízo de Competência Genérica de Montemor-o-Novo - Juiz 1
    Processo: 182/25.9GCMMN
    montnovo.judicial@tribunais.org.pt
    Certificação Citius
    06-06-2025

    Fica notificado para comparecer neste Tribunal, no dia 12-06-2025, às 16:00 horas,
    a fim de prestar serviço de interpretação.
    """

    suggestion = extract_interpretation_notification_metadata_from_text(
        notification_text,
        vocab_cities=["Évora", "Montemor-o-Novo", "Beja"],
        ai_enabled=False,
    )

    assert suggestion.case_number == "182/25.9GCMMN"
    assert suggestion.case_entity is not None
    assert "Montemor-o-Novo" in suggestion.case_entity
    assert suggestion.case_city == "Montemor-o-Novo"
    assert suggestion.court_email == "montnovo.judicial@tribunais.org.pt"
    assert suggestion.service_date == "2025-06-12"
    assert suggestion.service_entity is None
    assert suggestion.service_city is None


def test_extract_interpretation_notification_metadata_detects_explicit_gnr_service_location() -> None:
    notification_text = """
    Ministério Público de Beja
    Processo n.º 000055/25.5GAFAL
    beja.ministeriopublico@tribunais.org.pt

    Deve comparecer no dia 09-04-2025, na GNR de Vidigueira,
    para diligência processual.
    """

    suggestion = extract_interpretation_notification_metadata_from_text(
        notification_text,
        vocab_cities=["Beja", "Vidigueira", "Cuba"],
        ai_enabled=False,
    )

    assert suggestion.case_number == "000055/25.5GAFAL"
    assert suggestion.service_date == "2025-04-09"
    assert suggestion.service_entity == "GNR"
    assert suggestion.service_city == "Vidigueira"


def test_extract_interpretation_notification_metadata_from_pdf_uses_priority_pages(monkeypatch) -> None:
    class _FakeOrderedText:
        def __init__(self, text: str) -> None:
            self.text = text

    monkeypatch.setattr("legalpdf_translate.metadata_autofill.get_page_count", lambda _pdf_path: 2)
    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_ordered_page_text",
        lambda _pdf_path, page_index: (
            _FakeOrderedText("Processo n.º 140/22.5JAFAR\nCertificação Citius\n06-06-2025")
            if page_index == 0
            else _FakeOrderedText(
                """
                Juízo Local Criminal de Beja
                beja.judicial@tribunais.org.pt
                Comparecer no dia 12-06-2025, às 10:00 horas, na PSP de Beja.
                """
            )
        ),
    )

    suggestion = extract_interpretation_notification_metadata_from_pdf(
        Path("sample.pdf"),
        vocab_cities=["Beja", "Moura"],
        config=MetadataAutofillConfig(metadata_ai_enabled=False),
    )

    assert suggestion.case_number == "140/22.5JAFAR"
    assert suggestion.case_entity == "Juízo Local Criminal de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.court_email == "beja.judicial@tribunais.org.pt"
    assert suggestion.service_date == "2025-06-12"
    assert suggestion.service_entity == "PSP"
    assert suggestion.service_city == "Beja"


def test_priority_page_metadata_uses_full_text_fallback_when_header_has_no_email(monkeypatch) -> None:
    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_header_text_from_pdf_page_with_ocr_fallback",
        lambda _pdf_path, *, page_number, config=None: (
            "Tribunal Judicial da Comarca de Beja\nJuízo Local Criminal de Beja\nProcesso n.º 140/22.5JAFAR"
            if page_number == 1
            else ""
        ),
    )
    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_full_text_from_pdf_page_with_ocr_fallback",
        lambda _pdf_path, *, page_number, config=None: (
            "Para mais informações contacte beja.ministeriopublico@tribunais.org.pt" if page_number == 1 else ""
        ),
    )

    suggestion = extract_pdf_header_metadata_priority_pages(
        Path("sample.pdf"),
        vocab_cities=["Beja"],
        config=MetadataAutofillConfig(metadata_ai_enabled=False),
    )

    assert suggestion.case_number == "140/22.5JAFAR"
    assert suggestion.case_city == "Beja"
    assert suggestion.court_email == "beja.ministeriopublico@tribunais.org.pt"
    assert suggestion.court_email_source == "document_first_email"
