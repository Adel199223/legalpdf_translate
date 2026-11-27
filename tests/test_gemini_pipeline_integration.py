"""Offline integration tests across Gemini 4 Neon stages and OpenAI compatibility."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate import metadata_autofill, ocr_engine, ocr_text_transport
from legalpdf_translate.accounting_policy import (
    gemini_accounting_policy,
    ordinary_accounting_policy,
    with_semantic_review_policy,
)
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.gemini_client import GeminiInteractionsClient
from legalpdf_translate.ordinary_layout_accounting import (
    GEMINI_MODEL,
    GEMINI_PAGE_CEILING,
    MODEL as OPENAI_LAYOUT_MODEL,
    OrdinaryLayoutAccounting,
    PAGE_CEILING as OPENAI_PAGE_CEILING,
    layout_accounting_policy,
    verified_page_ceiling_for_provider,
)
from legalpdf_translate.ordinary_layout_contracts import LayoutSuggestionPolicy
from legalpdf_translate.semantic_review_billing import (
    GEMINI_MODEL as SEMANTIC_GEMINI_MODEL,
    GEMINI_POLICY,
    response_billing_evidence,
    strict_limits,
    usage_evidence,
)
from legalpdf_translate.semantic_review_model_policy import (
    GEMINI_VERSION,
    fresh_semantic_review_model_policy,
    validate_policy,
)
from legalpdf_translate.types import (
    OcrApiProvider,
    OcrEnginePolicy,
    OcrMode,
    RunConfig,
    TargetLang,
)
from legalpdf_translate.usage_accounting import DispatchAccounting, accounting_context
from legalpdf_translate.workflow_semantic_audit import fresh_recipe


def test_historical_openai_accounting_policy_and_layout_ceiling_unchanged() -> None:
    openai_policy = ordinary_accounting_policy()
    args = openai_policy.accounting_arguments(today=date(2026, 10, 15))
    assert args["pricing_snapshot"]["snapshot_id"] == "openai_public_standard_2026_10_15"
    layout_args = layout_accounting_policy().accounting_arguments(today=date(2026, 10, 9))
    assert layout_args["pricing_snapshot"]["snapshot_id"] == "layout_standard_2026_10_09"
    assert verified_page_ceiling_for_provider("gemini") == GEMINI_PAGE_CEILING
    gemini_args = gemini_accounting_policy().accounting_arguments()
    assert gemini_args["pricing_snapshot"]["snapshot_id"] == "gemini_public_standard_2026_11_26"


def test_gemini_semantic_review_policy_and_billing_evidence(tmp_path: Path) -> None:
    sem_policy = fresh_semantic_review_model_policy(primary_model="gemini-4-neon")
    assert sem_policy == {"version": GEMINI_VERSION, "model": SEMANTIC_GEMINI_MODEL}
    assert validate_policy(sem_policy) == sem_policy
    assert strict_limits({"semantic_review_billing_policy": GEMINI_POLICY}) is True

    # OpenAI default preserved when no primary_model supplied
    assert fresh_semantic_review_model_policy() == {
        "version": "dedicated_semantic_review_model_v1",
        "model": "gpt-6-astra",
    }

    extended = with_semantic_review_policy(gemini_accounting_policy(), sem_policy)
    args = extended.accounting_arguments()
    assert "gemini:semantic_audit:gemini-4-neon" in args["dispatch_limits"]

    # Raw usage admission & response evidence check (omitted service_tier defaults to "default")
    journal_dir = tmp_path / "journal"
    (journal_dir / "provider_responses").mkdir(parents=True)
    raw_body = json.dumps(
        {
            "id": "int-raw-1",
            "model": "gemini-4-neon",
            "status": "completed",
            "usage": {
                "total_input_tokens": 2000,
                "total_output_tokens": 300,
                "total_thought_tokens": 100,
                "total_cached_tokens": 0,
                "total_tokens": 2400,
            },
        }
    ).encode("utf-8")
    resp_path = (journal_dir / "provider_responses" / ("a" * 32)).with_suffix(".json")
    resp_path.write_bytes(raw_body)
    ev = {
        "path": f"provider_responses/{'a' * 32}.json",
        "sha256": hashlib.sha256(raw_body).hexdigest(),
        "bytes": len(raw_body),
        "json_status": "available",
    }
    _, billing_res = response_billing_evidence(
        journal_dir,
        ev,
        max_output_tokens=65536,
        response_id="int-raw-1",
        actual_model="gemini-4-neon",
        actual_service_tier="default",
        policy=GEMINI_POLICY,
    )
    assert billing_res["status"] == "available"


def test_fresh_recipe_for_gemini_validates_in_checkpoint() -> None:
    cfg = RunConfig(
        pdf_path=Path("sample.pdf"),
        output_dir=Path("out"),
        target_lang=TargetLang.AR,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
        ocr_api_provider=OcrApiProvider.GEMINI,
    )
    from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy
    from legalpdf_translate.checkpoint import sha256_of_text

    auto_pol = frozen_automatic_layout_policy()
    recipe = fresh_recipe(cfg, "gemini-4-neon", auto_pol, context_text="ctx", context_hash=sha256_of_text("ctx"))
    assert recipe["model"] == "gemini-4-neon"
    assert recipe["semantic_review_model_policy"]["model"] == "gemini-4-neon"
    assert recipe["ocr_text_transport_policy"] == "gemini_ocr_text_envelope_v1"

    validated = ordinary_semantic_audit_recipe(
        {
            "ordinary_semantic_audit_recipe": recipe,
            "ordinary_auto_layout_policy": auto_pol,
            "image_mode": "auto",
            "ocr_engine": "local_then_api",
            "strip_bidi_controls": True,
            "primary_assembly_recipe": {
                "version": "terminal_source_bound_folio_v4",
                "ordinary_auto_layout_policy": auto_pol,
            },
        }
    )
    assert validated is not None
    assert validated["model"] == "gemini-4-neon"


def test_layout_provider_factory_returns_gemini_client_for_gemini_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    client = OrdinaryLayoutAccounting.provider(
        None,
        LayoutSuggestionPolicy(GEMINI_MODEL, str(GEMINI_PAGE_CEILING), str(GEMINI_PAGE_CEILING), effort="xhigh"),
    )
    assert isinstance(client, GeminiInteractionsClient)
    assert client.model == "gemini-4-neon"

    monkeypatch.setenv("OPENAI_API_KEY", "oai-key")
    oai = OrdinaryLayoutAccounting.provider(
        None,
        LayoutSuggestionPolicy(OPENAI_LAYOUT_MODEL, str(OPENAI_PAGE_CEILING), str(OPENAI_PAGE_CEILING)),
    )
    assert oai.model == "gpt-5.2"


def test_gemini_ocr_engine_and_metadata_autofill_use_interactions(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, object]] = []

    class _FakeInteractions:
        def create(self, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(
                id="int-ocr-1",
                model=kwargs["model"],
                status="completed",
                output_text='{"case_city":"Beja","case_number":"12/25.0T9BJA"}',
                usage=SimpleNamespace(
                    total_input_tokens=80,
                    total_output_tokens=20,
                    total_thought_tokens=10,
                    total_cached_tokens=0,
                    total_tokens=110,
                ),
            )

    monkeypatch.setattr(ocr_engine.genai, "Client", lambda **kw: SimpleNamespace(interactions=_FakeInteractions()))
    engine = ocr_engine.GeminiApiOcrEngine(
        api_key="gem-key",
        model=ocr_engine.GEMINI_OCR_DEFAULT_MODEL,
        helper_thinking_level="high",
    )
    ocr_res = engine.ocr_image(b"\x89PNG\r\n\x1a\nfake")
    assert ocr_res.engine == "api"
    assert seen[0]["store"] is False
    assert seen[0]["model"] == "gemini-4-neon"
    assert seen[0]["generation_config"]["thinking_level"] == "high"

    monkeypatch.setattr(metadata_autofill, "resolve_ocr_api_key", lambda cfg: "gem-key")
    monkeypatch.setattr(
        metadata_autofill.GeminiInteractionsClient,
        "create_page_response",
        lambda self, **kw: SimpleNamespace(raw_output='{"case_city": "Moura", "case_number": "99/25.1"}'),
    )
    cfg = metadata_autofill.MetadataAutofillConfig(
        ocr_api_provider=OcrApiProvider.GEMINI,
        ocr_api_model="gemini-4-neon",
        helper_thinking_level="medium",
    )
    extracted = metadata_autofill._ai_extract_json("Extract metadata", config=cfg)
    assert extracted == {"case_city": "Moura", "case_number": "99/25.1"}


def test_legacy_pre_gemini_settings_upgrade_to_gemini_priority_once(tmp_path: Path) -> None:
    from legalpdf_translate.user_settings import load_gui_settings_from_path, load_joblog_settings_from_path

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 9,
                "ocr_api_provider": "openai",
                "ocr_api_provider_default": "openai",
                "ocr_api_key_env_name": "OPENAI_API_KEY",
                "default_effort": "high",
                "default_effort_policy": "adaptive",
                "effort": "high",
                "effort_policy": "adaptive",
            }
        ),
        encoding="utf-8",
    )

    loaded_gui = load_gui_settings_from_path(settings_file)
    assert loaded_gui["translation_provider"] == "gemini"
    assert loaded_gui["translation_model"] == "gemini-4-neon"
    assert loaded_gui["default_effort"] == "xhigh"
    assert loaded_gui["effort"] == "xhigh"
    assert loaded_gui["default_effort_policy"] == "fixed_xhigh"
    assert loaded_gui["effort_policy"] == "fixed_xhigh"
    assert loaded_gui["allow_xhigh_escalation"] is True
    assert loaded_gui["ocr_api_provider"] == "gemini"
    assert loaded_gui["ocr_api_provider_default"] == "gemini"
    assert loaded_gui["ocr_api_key_env_name"] == "GEMINI_API_KEY"

    loaded_joblog = load_joblog_settings_from_path(settings_file)
    assert loaded_joblog["ocr_api_provider"] == "gemini"
    assert loaded_joblog["ocr_api_key_env_name"] == "GEMINI_API_KEY"


def test_explicit_v10_openai_preference_stays_preserved(tmp_path: Path) -> None:
    from legalpdf_translate.user_settings import load_gui_settings_from_path, load_joblog_settings_from_path

    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 10,
                "translation_provider": "openai",
                "translation_model": "gpt-5.2",
                "ocr_api_provider": "openai",
                "ocr_api_provider_default": "openai",
                "ocr_api_key_env_name": "OPENAI_API_KEY",
            }
        ),
        encoding="utf-8",
    )

    loaded_gui = load_gui_settings_from_path(settings_file)
    assert loaded_gui["translation_provider"] == "openai"
    assert loaded_gui["translation_model"] == "gpt-5.2"
    assert loaded_gui["ocr_api_provider"] == "openai"
    assert loaded_gui["ocr_api_key_env_name"] == "OPENAI_API_KEY"

    loaded_joblog = load_joblog_settings_from_path(settings_file)
    assert loaded_joblog["ocr_api_provider"] == "openai"
    assert loaded_joblog["ocr_api_key_env_name"] == "OPENAI_API_KEY"


def test_metadata_autofill_defaults_to_gemini_provider() -> None:
    cfg = metadata_autofill.metadata_config_from_settings({})
    assert cfg.ocr_api_provider == OcrApiProvider.GEMINI
    assert cfg.ocr_api_key_env_name == "GEMINI_API_KEY"


def test_run_glossary_builder_lemma_client_uses_gemini_by_default(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from legalpdf_translate import power_tools_service

    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}", encoding="utf-8")
    outputs_dir = tmp_path / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    fake_pdf = tmp_path / "sample.pdf"
    fake_pdf.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(
        power_tools_service,
        "_builder_pages_from_pdf",
        lambda path: [
            (path.stem, page_idx, "Tribunal Judicial de Beja\nMinistério Público\nDespacho de acusação penal\n")
            for page_idx in range(1, 6)
        ],
    )
    created: list[dict[str, object]] = []
    sentinel_client = object()

    def _fake_create_client(**kwargs):
        created.append(kwargs)
        return sentinel_client

    monkeypatch.setattr(power_tools_service, "create_translation_client", _fake_create_client)
    monkeypatch.setattr(
        power_tools_service,
        "batch_normalize_lemmas",
        lambda terms, *, client, effort, cache: SimpleNamespace(
            mapping={},
            api_calls=0,
            cache_hits=0,
            cache_misses=0,
            failures=0,
            fallback_to_surface=True,
            wall_seconds=0.0,
        ),
    )

    result = power_tools_service.run_glossary_builder(
        settings_path=settings_file,
        outputs_dir=outputs_dir,
        source_mode="pdfs",
        run_dirs=[],
        pdf_paths=[str(fake_pdf)],
        target_lang="EN",
        mode="full_text",
        lemma_enabled=True,
        lemma_effort="high",
    )

    assert result["status"] == "ok"
    assert created == [{"provider": "gemini", "model": "gemini-4-neon"}]
