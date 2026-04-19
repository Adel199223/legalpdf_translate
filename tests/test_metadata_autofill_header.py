from __future__ import annotations

from pathlib import Path

import legalpdf_translate.metadata_autofill as metadata_autofill
from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    choose_court_email_suggestion,
    extract_from_header_text,
    extract_interpretation_notification_metadata_from_pdf,
    extract_interpretation_notification_metadata_from_pdf_with_diagnostics,
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
    monkeypatch.setattr(metadata_autofill, "resolve_ocr_api_key", lambda _config: "stored-key")

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


def test_extract_interpretation_notification_metadata_with_diagnostics_attempts_ocr_when_mode_is_off(monkeypatch) -> None:
    class _FakeOrderedText:
        def __init__(self, text: str) -> None:
            self.text = text

    monkeypatch.setattr("legalpdf_translate.metadata_autofill.get_page_count", lambda _pdf_path: 1)
    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_ordered_page_text",
        lambda _pdf_path, _page_index: _FakeOrderedText(""),
    )
    monkeypatch.setattr("legalpdf_translate.metadata_autofill.local_ocr_available", lambda: False)
    monkeypatch.setattr("legalpdf_translate.metadata_autofill.resolve_ocr_api_key", lambda _config: None)
    monkeypatch.setattr("legalpdf_translate.metadata_autofill._build_ocr_engine_from_config", lambda _config: object())
    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.ocr_pdf_page_text",
        lambda **_kwargs: metadata_autofill.OcrResult(
            text="",
            engine="local",
            failed_reason="Local OCR unavailable: 'tesseract' executable was not found in PATH.",
            chars=0,
        ),
    )

    result = extract_interpretation_notification_metadata_from_pdf_with_diagnostics(
        Path("sample.pdf"),
        vocab_cities=["Beja"],
        config=MetadataAutofillConfig(metadata_ai_enabled=False, ocr_mode=metadata_autofill.OcrMode.OFF),
    )

    assert result.suggestion.case_number is None
    assert result.diagnostics.ocr_attempted is True
    assert result.diagnostics.ocr_attempted_pages == (1,)
    assert result.diagnostics.local_ocr_available is False
    assert result.diagnostics.api_ocr_configured is False
    assert result.diagnostics.effective_ocr_mode == "auto"
    assert "tesseract" in result.diagnostics.ocr_failure_reason


def test_extract_header_metadata_prefers_local_criminal_prosecution_section_over_generic_public_prosecution_header() -> None:
    header = """
    Ministério Público - Procuradoria da República da Comarca de Beja
    Procuradoria do Juízo Local Criminal - 1ª Sec
    Inquéritos de Beja
    Processo n.º 6/26.0PFBJA
    """

    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja", "Cuba"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Procuradoria do Juízo Local Criminal - 1ª Sec"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "6/26.0PFBJA"


def test_extract_header_metadata_supports_general_jurisdiction_unit_from_screenshot_family() -> None:
    header = """
    Tribunal Judicial da Comarca de Beja
    Juízo de Competência Genérica de Ferreira do Alentejo
    Processo n.º 19/25.9FBPTM
    """

    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja", "Ferreira do Alentejo", "Cuba"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Juízo de Competência Genérica de Ferreira do Alentejo"
    assert suggestion.case_city == "Ferreira do Alentejo"
    assert suggestion.case_number == "19/25.9FBPTM"


def test_extract_header_metadata_prefers_wrapped_general_jurisdiction_city_over_generic_public_prosecution() -> None:
    header = """
    48/26.5GACUB [36393578]
    Ministério Público - Procuradoria da
    República da Comarca de Beja
    Procuradoria do Juízo de Competência
    Genérica de Cuba - Sec Inquéritos

    Largo Cristóvão Colon
    7940-171 Cuba
    Mail: cuba.ministeriopublico@tribunais.org.pt
    """

    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja", "Cuba", "Ferreira do Alentejo"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Juízo de Competência Genérica de Cuba"
    assert suggestion.case_city == "Cuba"
    assert suggestion.service_city == "Cuba"
    assert suggestion.court_email == "cuba.ministeriopublico@tribunais.org.pt"


def test_priority_page_metadata_prefers_specific_local_unit_over_earlier_generic_comarca_email(monkeypatch) -> None:
    def _fake_header_text(_pdf_path: Path, *, page_number: int, config: MetadataAutofillConfig | None = None) -> str:
        del config
        if page_number == 1:
            return """
            Ministério Público - Procuradoria da República da Comarca de Beja
            Mail: cuba.ministeriopublico@tribunais.org.pt
            Processo n.º 48/26.5GACUB
            """
        return """
        Procuradoria do Juízo de Competência Genérica de Cuba - Sec Inquéritos
        48/26.5GACUB
        """

    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_header_text_from_pdf_page_with_ocr_fallback",
        _fake_header_text,
    )

    suggestion = extract_pdf_header_metadata_priority_pages(
        Path("sample.pdf"),
        vocab_cities=["Beja", "Cuba"],
        config=MetadataAutofillConfig(metadata_ai_enabled=False),
    )

    assert suggestion.case_entity == "Juízo de Competência Genérica de Cuba"
    assert suggestion.case_city == "Cuba"
    assert suggestion.service_city == "Cuba"
    assert suggestion.case_number == "48/26.5GACUB"
    assert suggestion.court_email == "cuba.ministeriopublico@tribunais.org.pt"


def test_extract_header_metadata_supports_central_civil_criminal_unit_from_screenshot_family() -> None:
    header = """
    Tribunal Judicial da Comarca de Beja
    Juízo Central Cível e Criminal de Beja - Juiz 2
    Processo n.º 39/22.5GACUB
    """

    suggestion = extract_from_header_text(
        header,
        vocab_cities=["Beja", "Cuba"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Juízo Central Cível e Criminal de Beja - Juiz 2"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "39/22.5GACUB"
