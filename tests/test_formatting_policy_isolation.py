"""Offline publication guards for the formatting-only integration.

Expected requests/resources were inspected at production base 022b5af. These
small contract snapshots intentionally do not read git, another checkout, real
credentials, or provider services. A future deliberate policy change can update
them explicitly; formatting work must not do so implicitly.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import legalpdf_translate.config as config_module
import legalpdf_translate.ocr_engine as ocr_module
import legalpdf_translate.openai_client as client_module
import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.checkpoint import (
    build_run_paths, ensure_run_dirs, load_run_state, mark_page_done,
    new_run_state, save_run_state_atomic,
)
from legalpdf_translate.pdf_text_order import OrderedPageText
from legalpdf_translate.prompt_builder import build_page_prompt, build_retry_prompt
from legalpdf_translate.resources_loader import load_system_instructions
from legalpdf_translate.types import (
    EffortPolicy, ImageMode, OcrMode, PageStatus, ReasoningEffort, RunConfig, TargetLang,
)


_INSTRUCTION_SHA256 = {
    "EN": "a7df7e97b012e2a235e8edc7374247e05e9ef4006c8a03b0f2c891962d968b9a",
    "FR": "661180b1a3a2e711f50f5f82777c9cc86d1224f5ff65d06fb4cde20d67a7c3c4",
    "AR": "9bbae954d09864fb62f6f0f9c0d02352161eccaa77e8707f64a282f480e2b4a0",
}
_SOURCE = "O arguido deve cumprir as obrigações determinadas pelo tribunal."
_TARGET = {
    TargetLang.EN: "The defendant must comply with the obligations ordered by the court.",
    TargetLang.FR: "Le prévenu doit respecter les obligations imposées par le tribunal.",
    TargetLang.AR: "يجب على المتهم الامتثال للالتزامات التي تقررها المحكمة.",
}


def _forbidden(*args, **kwargs):
    pytest.fail("Formatting isolation attempted a provider, credential, OCR or environment operation.", pytrace=False)


@pytest.fixture
def no_external_work(monkeypatch):
    # Keep fakes local to these tests: no new global/conftest behavior.
    monkeypatch.setattr(client_module, "OpenAI", _forbidden)
    monkeypatch.setattr(client_module, "resolve_openai_key_with_source", _forbidden)
    monkeypatch.setattr(ocr_module, "OpenAI", _forbidden)
    monkeypatch.setattr(ocr_module, "urlopen", _forbidden)
    monkeypatch.setattr(workflow_module, "build_ocr_engine", _forbidden)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test", _forbidden)
    monkeypatch.setattr(workflow_module, "resolve_openai_key_with_source", _forbidden)
    monkeypatch.setattr(workflow_module, "load_environment", _forbidden)


def _config(tmp_path: Path, lang: TargetLang, **changes) -> RunConfig:
    source = tmp_path / "synthetic_source.pdf"
    source.write_bytes(b"%PDF-1.4\n% synthetic fixture; no native renderer required\n")
    outdir = tmp_path / "out"
    outdir.mkdir(exist_ok=True)
    return RunConfig(pdf_path=source, output_dir=outdir, target_lang=lang,
                     image_mode=ImageMode.OFF, ocr_mode=OcrMode.OFF,
                     workers=1, max_pages=1, resume=False, **changes)


def test_formatting_does_not_promote_translation_or_ocr_defaults():
    assert config_module.OPENAI_MODEL == "gpt-5.2"
    assert config_module.OPENAI_STORE is False
    assert config_module.DEFAULT_REASONING_EFFORT == "high"
    assert config_module.RETRY_REASONING_EFFORT == "medium"
    assert config_module.DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS == 480
    assert config_module.DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS == 720
    assert ocr_module.OPENAI_OCR_DEFAULT_MODEL == "gpt-4o-mini"
    assert ocr_module.GEMINI_OCR_DEFAULT_MODEL == "gemini-3.1-flash-lite-preview"
    assert RunConfig.__dataclass_fields__["effort_policy"].default == EffortPolicy.ADAPTIVE
    assert RunConfig.__dataclass_fields__["allow_xhigh_escalation"].default is False
    assert "model_policy" not in inspect.signature(workflow_module.TranslationWorkflow).parameters


@pytest.mark.parametrize("lang", list(TargetLang))
def test_production_instructions_and_page_prompt_remain_plain_text(lang):
    instructions = load_system_instructions(lang)
    assert hashlib.sha256(instructions.encode("utf-8")).hexdigest() == _INSTRUCTION_SHA256[lang.value]
    prefix = "" if lang == TargetLang.AR else lang.value + "\n"
    assert build_page_prompt(lang, 2, 4, _SOURCE, "Earlier source context.") == (
        prefix + "<<<PAGE 2 OF 4>>>\n<<<BEGIN CONTEXT>>>\nEarlier source context.\n"
        "<<<END CONTEXT>>>\n<<<BEGIN SOURCE>>>\n" + _SOURCE + "\n<<<END SOURCE>>>"
    )
    hint = {TargetLang.AR: "", TargetLang.EN: " Keep the output strictly in English.",
            TargetLang.FR: " Keep the output strictly in French."}[lang]
    assert build_retry_prompt(lang, "PRIOR") == (
        "COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, "
        "as ONE plain-text code block and NOTHING ELSE." + hint
        + "\n<<<BEGIN PRIOR OUTPUT>>>\nPRIOR\n<<<END PRIOR OUTPUT>>>"
    )


@pytest.mark.parametrize("lang", list(TargetLang))
def test_actual_page_processing_keeps_one_legacy_request_without_review_or_ocr(
    tmp_path, monkeypatch, no_external_work, lang,
):
    config = _config(tmp_path, lang)
    paths = build_run_paths(config.output_dir, config.pdf_path, lang)
    ensure_run_dirs(paths)
    ordered = OrderedPageText(_SOURCE, False, 0.0, False, 1, 0, 0, 0, 1, False)
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda *a, **k: ordered)
    monkeypatch.setattr(workflow_module, "_assess_extraction_integrity",
                        lambda **kwargs: workflow_module._ExtractionIntegrityAssessment())

    class RecordingClient:
        def __init__(self):
            self.calls = []

        def create_page_response(self, **kwargs):
            self.calls.append(deepcopy(kwargs))
            return client_module.ApiCallResult(
                raw_output="```\n" + _TARGET[lang] + "\n```",
                usage={"input_tokens": 12, "output_tokens": 14}, response_id="synthetic-only",
            )

    client = RecordingClient()
    workflow = workflow_module.TranslationWorkflow(client=client)
    monkeypatch.setattr(workflow, "_remaining_request_budget_seconds", lambda **kwargs: 480.0)
    result = workflow._process_page(
        client=client, config=config, paths=paths, instructions=load_system_instructions(lang),
        context_text="Earlier source context.", page_number=1, total_pages=1,
    )
    assert result.status == PageStatus.DONE
    assert result.page_metadata["api_calls_count"] == 1
    assert result.page_metadata["ocr_used"] is False
    prefix = "" if lang == TargetLang.AR else lang.value + "\n"
    assert client.calls == [{
        "instructions": load_system_instructions(lang),
        "prompt_text": prefix + "<<<PAGE 1 OF 1>>>\n<<<BEGIN CONTEXT>>>\nEarlier source context.\n"
                       "<<<END CONTEXT>>>\n<<<BEGIN SOURCE>>>\n" + _SOURCE + "\n<<<END SOURCE>>>",
        "effort": "high", "image_data_url": None, "image_detail": "low", "timeout_seconds": 480.0,
    }]


@pytest.mark.parametrize("lang", list(TargetLang))
def test_native_request_contract_has_no_new_model_tools_or_output_policy(monkeypatch, no_external_work, lang):
    calls = []

    def create(**kwargs):
        calls.append(deepcopy(kwargs))
        return SimpleNamespace(output_text="synthetic response", usage=None, id="synthetic-only")

    # Bypass the credential-bearing constructor entirely, with an in-memory SDK.
    client = object.__new__(client_module.OpenAIResponsesClient)
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    client._max_transport_retries = 0
    client._pre_call_jitter_seconds = 0
    client._request_timeout_seconds = 480.0
    client._logger = None
    monkeypatch.setattr(client_module.time, "perf_counter", lambda: 100.0)
    prompt = build_page_prompt(lang, 1, 1, _SOURCE)
    client.create_page_response(instructions=load_system_instructions(lang), prompt_text=prompt, effort="high")
    assert calls == [{
        "model": "gpt-5.2", "instructions": load_system_instructions(lang),
        "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
        "reasoning": {"effort": "high"}, "store": False, "timeout": 480.0,
    }]


def test_workflow_keeps_existing_two_page_call_sites_and_no_experimental_policy_imports():
    tree = ast.parse(Path(workflow_module.__file__).read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imports.intersection({"model_policy", "fidelity_review", "benchmark_dispatch", "benchmark_sol",
                                     "benchmark_xhigh", "benchmark_arabic_layout", "arabic_source_spans"})
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute) and node.func.attr == "create_page_response"]
    assert len(calls) == 2
    contracts = [{keyword.arg: ast.unparse(keyword.value) for keyword in node.keywords} for node in calls]
    assert contracts == [
        {"instructions": "instructions", "prompt_text": "prompt_text", "effort": "attempt1_effort.value",
         "image_data_url": "image_data_url", "image_detail": "str(page_metadata['image_detail'] or 'low')",
         "timeout_seconds": "attempt1_timeout"},
        {"instructions": "instructions", "prompt_text": "retry_prompt", "effort": "retry_effort.value",
         "image_data_url": "None", "timeout_seconds": "remaining_retry_budget"},
    ]


@pytest.mark.parametrize("module_name", [
    "document_structure", "document_layout", "document_spacing", "docx_furniture_reflow",
    "section_furniture", "formatting_support", "layout_cache", "layout_integration",
])
def test_passive_formatting_dependencies_do_not_import_provider_or_prompt_policy(module_name):
    source = Path(workflow_module.__file__).parent / (module_name + ".py")
    tree = ast.parse(source.read_text(encoding="utf-8"))
    forbidden_modules = {"openai", "requests", "httpx", "urllib", "subprocess", "secrets_store",
                         "model_policy", "openai_client", "ocr_engine", "fidelity_review",
                         "prompt_builder", "translation_structure", "arabic_source_spans"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden_modules
        elif isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in forbidden_modules for alias in node.names)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"__import__", "eval", "exec", "OpenAI", "OpenAIResponsesClient",
                                         "build_ocr_engine", "run_translation_auth_test"}


@pytest.mark.parametrize("lang", list(TargetLang))
def test_legacy_rebuild_never_creates_clients_or_changes_saved_translation_costs_or_findings(
    tmp_path, monkeypatch, no_external_work, lang,
):
    config = _config(tmp_path, lang, page_breaks=False)
    paths = build_run_paths(config.output_dir, config.pdf_path, lang)
    ensure_run_dirs(paths)
    page_path = paths.pages_dir / "page_0001.txt"
    page_path.write_text(_TARGET[lang], encoding="utf-8")
    state = new_run_state(config=config, paths=paths, pdf_fingerprint="a" * 64, context_hash="NO_CONTEXT",
                          total_pages=1, selected_pages=[1])
    mark_page_done(state, 1, image_used=False, retry_used=False,
                   usage={"input_tokens": 31, "output_tokens": 17})
    state.pages["1"]["existing_review_required"] = True
    state.pages["1"]["estimated_cost"] = 0.001
    save_run_state_atomic(paths.run_state_path, state)
    summary = {"totals": {"known_cost_usd": 0.001, "api_calls_total": 1},
               "model_policy": {"translation": {"model": "historical-model"}},
               "usage_summary": {"historical": True}, "review_queue_count": 1}
    summary_path = paths.run_dir / "run_summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    review_path = paths.run_dir / "review_queue.json"
    review = {"pages": [{"page_number": 1, "reasons": ["preexisting_semantic_finding"]}]}
    review_path.write_text(json.dumps(review), encoding="utf-8")
    original_page_bytes = page_path.read_bytes()
    original_state_page = deepcopy(state.pages["1"])
    monkeypatch.setattr(workflow_module, "OpenAIResponsesClient", _forbidden)
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", _forbidden)
    workflow = workflow_module.TranslationWorkflow()
    output = workflow.rebuild_docx(config)
    assert output.is_file() and output.suffix == ".docx"
    assert page_path.read_bytes() == original_page_bytes
    rebuilt_state = load_run_state(paths.run_state_path)
    assert rebuilt_state is not None
    for field in ("usage", "estimated_cost", "existing_review_required", "status"):
        assert rebuilt_state.pages["1"][field] == original_state_page[field]
    after_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    for field in ("totals", "model_policy", "usage_summary"):
        assert after_summary[field] == summary[field]
    assert json.loads(review_path.read_text(encoding="utf-8")) == review


def test_source_bound_layout_derivation_is_local_and_preserves_all_historical_inputs(tmp_path, monkeypatch, no_external_work):
    import legalpdf_translate.layout_integration as layout_module
    from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
    from legalpdf_translate.formatting_support import save_translated_structure, write_json_atomic

    config = _config(tmp_path, TargetLang.AR, page_breaks=False)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
    ensure_run_dirs(paths)
    source = PageStructure(
        1, text_sha256(_SOURCE), [StructureBlock("p0001_b0001", _SOURCE, bbox=(50, 100, 500, 125))],
        source_file_sha256=hashlib.sha256(config.pdf_path.read_bytes()).hexdigest(),
        source_text_sha256=text_sha256(_SOURCE),
    )
    page_path = paths.pages_dir / "page_0001.txt"
    page_path.write_text(_TARGET[TargetLang.AR], encoding="utf-8")
    source_path = page_path.with_suffix(".source_structure.json")
    target_path = page_path.with_suffix(".structure.json")
    write_json_atomic(source_path, source.to_dict())
    save_translated_structure(
        path=target_path, source_structure=source,
        translated_blocks=[{"id": "p0001_b0001", "text": _TARGET[TargetLang.AR]}],
        translated_text=_TARGET[TargetLang.AR], translation_fingerprint="historical-request-identity",
        review_metadata={"review_required": True, "status": "preexisting_semantic_finding"},
    )
    originals = {path: path.read_bytes() for path in (config.pdf_path, source_path, target_path, page_path)}
    # A missing optional local renderer is a layout review, never permission for
    # API/OCR fallback or reconstruction of source/translation text.
    def unavailable_renderer(*args, **kwargs):
        raise OSError("Synthetic local renderer unavailable")
    monkeypatch.setattr(layout_module, "_render_source", unavailable_renderer)
    result = layout_module.prepare_layout_rebuild(paths.pages_dir, config.pdf_path)
    assert result["prepared_pages"] == [1]
    assert result["review_required_pages"] == [1]
    assert all(path.read_bytes() == original for path, original in originals.items())
    derivative = json.loads(page_path.with_suffix(".layout.json").read_text(encoding="utf-8"))
    assert derivative["translation_sha256"] == text_sha256(_TARGET[TargetLang.AR])
    assert derivative["source_file_sha256"] == source.source_file_sha256
    assert derivative["layout"]["review_required"] is True
