from __future__ import annotations

from PIL import Image

import legalpdf_translate.metadata_autofill as metadata_autofill
from legalpdf_translate.metadata_autofill import (
    MetadataAutofillConfig,
    MetadataSuggestion,
    OcrMode,
    _metadata_extracted_fields,
    extract_from_photo_ocr_text,
    extract_photo_metadata_from_image,
    extract_interpretation_photo_metadata_from_ocr_text,
)


def test_extract_photo_metadata_from_screenshot_like_ocr_text() -> None:
    ocr_text = """
    Monday, February 2, 2026 • 4:20 PM
    Rua da Liberdade, Beja, Portugal
    69/26.8PBBBJA
    """
    suggestion = extract_from_photo_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )
    assert suggestion.service_city == "Beja"
    assert suggestion.service_date == "2026-02-02"
    assert suggestion.case_number == "69/26.8PBBBJA"


def test_extract_photo_city_prefers_vocab_match() -> None:
    ocr_text = """
    Monday, February 10, 2026 • 11:15 AM
    Meeting notes near Tribunal, Moura district office
    """
    suggestion = extract_from_photo_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Cuba"],
        ai_enabled=False,
    )
    assert suggestion.service_city == "Moura"
    assert suggestion.service_date == "2026-02-10"


def test_extract_interpretation_photo_metadata_defaults_case_fields_from_service_city() -> None:
    ocr_text = """
    Monday, February 2, 2026 • 4:20 PM
    Rua da Liberdade, Beja, Portugal
    69/26.8PBBBJA
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "69/26.8PBBBJA"
    assert suggestion.service_city is None
    assert suggestion.service_date == "2026-02-02"


def test_extract_interpretation_photo_metadata_recovers_distinct_gnr_service_city() -> None:
    ocr_text = """
    Ministério Público de Beja
    Processo n.º 69/26.8PBBBJA
    Para comparência no Posto Territorial da GNR de Moura no dia 02/02/2026 às 16:20
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "69/26.8PBBBJA"
    assert suggestion.service_entity == "GNR"
    assert suggestion.service_city == "Moura"
    assert suggestion.service_date == "2026-02-02"


def test_extract_interpretation_photo_metadata_recovers_servico_de_turno_city() -> None:
    ocr_text = """
    Ministério Público de Beja
    Processo 69/26.8PBBBJA
    Serviço de Turno de Moura
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_city == "Beja"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"


def test_extract_interpretation_photo_metadata_recovers_city_before_service_turn_label() -> None:
    ocr_text = """
    Ministério Público de Beja
    Comarca de Beja - Serviço de Turno
    Moura - Serviço de Turno
    Palácio da Justiça - Rua Exemplo - 7860-204 Moura
    Processo 55/26.8GDODM
    Autuação: 25-04-2026
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"


def test_extract_interpretation_photo_metadata_rejects_subject_title_as_case_city() -> None:
    ocr_text = """
    Assunto de Cidadão Estrangeiro em Situação Processual
    Comarca de Beja - Serviço de Turno
    Moura - Serviço de Turno
    Palácio da Justiça - Rua Exemplo - 7860-204 Moura
    Processo 55/26.8GDODM
    Autuação: 25-04-2026
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_city != "Cidadão Estrangeiro em"
    assert "Cidadão Estrangeiro" not in (suggestion.case_entity or "")
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert {"service_entity", "service_city"}.issubset(_metadata_extracted_fields(suggestion))


def test_extract_interpretation_photo_metadata_rejects_palacio_address_as_case_header() -> None:
    ocr_text = """
    Ministério Público de Palácio da Justiça - Largo Santa Clara - 7860-204 Moura
    Comarca de Beja - Serviço
    Processo 55/26.8GDODM
    Autuação: 25/04/2026
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert "Palácio" not in (suggestion.case_entity or "")
    assert suggestion.case_city != "Palácio da Justiça"
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert suggestion.service_date == "2026-04-25"
    assert {"service_entity", "service_city"}.issubset(_metadata_extracted_fields(suggestion))


def test_extract_interpretation_photo_metadata_leaves_address_only_case_header_blank() -> None:
    ocr_text = """
    Ministério Público de Palácio da Justiça - Largo Santa Clara
    Processo 55/26.8GDODM
    Autuação: 25/04/2026
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity is None
    assert suggestion.case_city is None
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity is None
    assert suggestion.service_city is None


def test_extract_interpretation_photo_metadata_merges_header_crop_over_bad_palacio_full_ocr(
    tmp_path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (1200, 800), color="white").save(image_path)
    responses = [
        metadata_autofill.OcrResult(
            text="""
            Ministério Público de Palácio da Justiça - Largo Santa Clara
            Processo 55/26.8GDODM
            Autuação: 25/04/2026
            """,
            engine="api",
            failed_reason=None,
            chars=110,
        ),
        metadata_autofill.OcrResult(
            text="""
            Comarca de Beja - Serviço
            Palácio da Justiça - Largo Santa Clara - 7860-204 Moura
            """,
            engine="api",
            failed_reason=None,
            chars=90,
        ),
    ]
    calls: list[bytes] = []

    class FakeEngine:
        pass

    def fake_invoke_ocr_image(engine, image_bytes, **kwargs):
        calls.append(image_bytes)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(metadata_autofill, "_build_ocr_engine_from_config", lambda config: FakeEngine())
    monkeypatch.setattr(metadata_autofill, "invoke_ocr_image", fake_invoke_ocr_image)

    suggestion = metadata_autofill.extract_interpretation_photo_metadata_from_image(
        image_path,
        vocab_cities=["Beja", "Moura", "Serpa"],
        config=MetadataAutofillConfig(),
        use_exif_date_as_service_date=False,
    )

    assert len(calls) == 2
    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert suggestion.service_date == "2026-04-25"
    assert suggestion.safe_diagnostics["service_location_recovery_attempted"] is True
    assert suggestion.safe_diagnostics["service_location_recovered"] is True


def test_extract_interpretation_photo_metadata_rejects_placeholder_case_fields() -> None:
    ocr_text = """
    Ministério Público de não especificado
    Cidade: não especificado
    Assunto de Cidadão Estrangeiro em Situação Processual
    Comarca de Beja - Serviço
    Moura - Serviço
    Palácio da Justiça - Largo Santa Clara - 7860 204 Moura
    Processo 55/26.8GDODM
    Autuação: 25-04-2026
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_city != "não especificado"
    assert "não especificado" not in (suggestion.case_entity or "")
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert {"service_entity", "service_city"}.issubset(_metadata_extracted_fields(suggestion))
    assert suggestion.safe_diagnostics == {
        "placeholder_values_rejected": True,
        "placeholder_rejection_reasons": ["metadata_placeholder"],
        "official_case_header_preferred": True,
        "service_location_evidence": "service_header_or_postcode",
        "field_sources": {
            "case_city": "official_header",
            "service_city": "ocr_service_location",
        },
        "ocr_evidence_flags": {
            "has_comarca": True,
            "has_service_word": True,
            "has_postcode": True,
        },
    }


def test_extract_interpretation_photo_metadata_recovers_service_city_when_turno_is_missing() -> None:
    ocr_text = """
    Ministério Público de Beja
    Moura - Serviço
    Palácio da Justiça - Largo Santa Clara - 7860204 Moura
    Processo 55/26.8GDODM
    Autuação: 25-04-2026
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"


def test_extract_interpretation_photo_metadata_ignores_ai_subject_title_case_entity(
    monkeypatch,
) -> None:
    def fake_ai_extract_json(prompt: str, *, config: MetadataAutofillConfig) -> dict[str, str] | None:
        if "legal case metadata" not in prompt:
            return None
        return {
            "case_entity": "Assunto de Cidadão Estrangeiro em Situação Processual",
            "case_city": "Cidadão Estrangeiro em",
            "case_number": "",
        }

    monkeypatch.setattr(metadata_autofill, "_ai_extract_json", fake_ai_extract_json)

    ocr_text = """
    Assunto de Cidadão Estrangeiro em Situação Processual
    Comarca de Beja - Serviço de Turno
    Moura - Serviço de Turno
    Palácio da Justiça - Rua Exemplo - 7860-204 Moura
    Processo 55/26.8GDODM
    Autuação: 25-04-2026
    """
    suggestion = metadata_autofill.extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=True,
        ai_config=MetadataAutofillConfig(metadata_ai_enabled=True),
    )

    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert "Cidadão Estrangeiro" not in (suggestion.case_entity or "")
    assert suggestion.case_city != "Cidadão Estrangeiro em"


def test_extract_interpretation_photo_metadata_skips_case_jurisdiction_service_turn_as_service_city() -> None:
    ocr_text = """
    Ministério Público de Beja
    Comarca de Beja - Serviço de Turno
    Processo 55/26.8GDODM
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_city == "Beja"
    assert suggestion.service_entity is None
    assert suggestion.service_city is None


def test_extract_interpretation_photo_metadata_uses_nearby_postcode_city_when_turno_is_noisy() -> None:
    ocr_text = """
    Ministério Público de Beja
    Comarca de Beja Serviço
    Palácio da Justiça
    Contactos
    Referência interna
    Largo Santa Clara - 7860-204 Moura
    Processo 55/26.8GDODM
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Serpa"],
        ai_enabled=False,
    )

    assert suggestion.case_city == "Beja"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"


def test_extract_interpretation_photo_metadata_rejects_justica_address_as_service_city() -> None:
    ocr_text = """
    Ministério Público de Beja
    Comarca de Beja - Serviço
    Palácio da Justiça - Serviço
    Largo Santa Clara - 7860-204 Moura
    Processo 55/26.8GDODM
    """
    suggestion = extract_interpretation_photo_metadata_from_ocr_text(
        ocr_text,
        vocab_cities=["Beja", "Moura", "Justiça"],
        ai_enabled=False,
    )

    assert suggestion.case_city == "Beja"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert suggestion.service_city != "Justiça"
    assert suggestion.safe_diagnostics["service_location_evidence"] == "service_header_or_postcode"


def test_extract_interpretation_photo_metadata_uses_header_crop_when_full_ocr_misses_service_city(
    tmp_path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (1200, 800), color="white").save(image_path)
    responses = [
        metadata_autofill.OcrResult(
            text="""
            Ministério Público de Beja
            Processo 55/26.8GDODM
            Autuação: 25/04/2026
            """,
            engine="api",
            failed_reason=None,
            chars=80,
        ),
        metadata_autofill.OcrResult(
            text="""
            Comarca de Beja - Serviço
            Palácio da Justiça - Largo Santa Clara - 7860-204 Moura
            """,
            engine="api",
            failed_reason=None,
            chars=90,
        ),
    ]
    calls: list[bytes] = []

    class FakeEngine:
        pass

    def fake_invoke_ocr_image(engine, image_bytes, **kwargs):
        calls.append(image_bytes)
        return responses[min(len(calls) - 1, len(responses) - 1)]

    monkeypatch.setattr(metadata_autofill, "_build_ocr_engine_from_config", lambda config: FakeEngine())
    monkeypatch.setattr(metadata_autofill, "invoke_ocr_image", fake_invoke_ocr_image)

    suggestion = metadata_autofill.extract_interpretation_photo_metadata_from_image(
        image_path,
        vocab_cities=["Beja", "Moura", "Serpa"],
        config=MetadataAutofillConfig(),
        use_exif_date_as_service_date=False,
    )

    assert len(calls) == 2
    assert suggestion.case_entity == "Ministério Público de Beja"
    assert suggestion.case_city == "Beja"
    assert suggestion.case_number == "55/26.8GDODM"
    assert suggestion.service_entity == "Serviço de Turno"
    assert suggestion.service_city == "Moura"
    assert suggestion.service_date == "2026-04-25"
    assert {"service_entity", "service_city"}.issubset(_metadata_extracted_fields(suggestion))
    assert suggestion.safe_diagnostics["ocr_variant_count"] == 2
    assert suggestion.safe_diagnostics["service_location_recovery_attempted"] is True
    assert suggestion.safe_diagnostics["service_location_recovered"] is True


def test_extract_photo_metadata_can_keep_exif_date_as_provenance_only(tmp_path) -> None:
    image_path = tmp_path / "photo.jpg"
    image = Image.new("RGB", (10, 10), color="white")
    exif = Image.Exif()
    exif[36867] = "2026:02:03 12:00:00"
    image.save(image_path, exif=exif)

    suggestion = extract_photo_metadata_from_image(
        image_path,
        vocab_cities=["Beja", "Moura"],
        config=MetadataAutofillConfig(ocr_mode=OcrMode.OFF),
        use_exif_date_as_service_date=False,
    )

    assert suggestion.service_date is None
    assert suggestion.confidence == {"service_city": 0.0, "service_date": 0.0, "case_number": 0.0, "photo_taken_date": 0.99}


def test_interpretation_photo_exif_date_does_not_override_ocr_service_date(tmp_path, monkeypatch) -> None:
    image_path = tmp_path / "photo.jpg"
    image = Image.new("RGB", (10, 10), color="white")
    exif = Image.Exif()
    exif[36867] = "2026:02:03 12:00:00"
    image.save(image_path, exif=exif)

    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill._ocr_photo_text",
        lambda image_path, config: metadata_autofill.OcrResult(text="redacted", engine="fake", failed_reason="", chars=8),
    )
    monkeypatch.setattr(
        "legalpdf_translate.metadata_autofill.extract_interpretation_photo_metadata_from_ocr_text",
        lambda *args, **kwargs: MetadataSuggestion(
            case_city="Beja",
            service_date="2026-04-25",
            confidence={"service_date": 0.9},
        ),
    )

    suggestion = metadata_autofill.extract_interpretation_photo_metadata_from_image(
        image_path,
        vocab_cities=["Beja", "Moura"],
        config=MetadataAutofillConfig(),
        use_exif_date_as_service_date=True,
    )

    assert suggestion.service_date == "2026-04-25"
    assert suggestion.confidence["service_date"] == 0.9
    assert suggestion.confidence["photo_taken_date"] == 0.99
