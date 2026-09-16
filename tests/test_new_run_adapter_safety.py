"""Synthetic adapter regressions: correction, authoritative context and identity."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from legalpdf_translate import new_translation_blocks as module
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.document_structure import structure_from_text
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.types import OcrMode, PageStatus, TargetLang


SOURCE = "o arguido deve pagar 25 EUR e cumprir todas as obrigacoes indicadas no prazo determinado"
TRANSLATED = "The defendant must pay 25 EUR and comply with all the stated obligations within the specified deadline."


def adapter(monkeypatch, *, mode=OcrMode.OFF, pages=(1,)):
    monkeypatch.setattr(module, "source_page_identity", lambda _path, _number: {"source_file_sha256": "1" * 64})
    config = SimpleNamespace(pdf_path=Path("synthetic.pdf"), target_lang=TargetLang.EN,
        ocr_mode=mode, effort="high", effort_policy="fixed", page_breaks=False)
    def accumulate(metadata, usage):
        for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
            metadata[key] = metadata.get(key, 0) + usage.get(key, 0)
    workflow = SimpleNamespace(_prompt_glossaries_by_lang={}, _enabled_glossary_tiers_by_lang={},
        _dispatch_accounting=None,
        _prompt_addendum_by_lang={}, _last_state=SimpleNamespace(pages={}), _cancel_event=threading.Event(),
        _translation_request_timeout_seconds=lambda **_kw: 30, _utc_now=lambda: "synthetic-time",
        _accumulate_usage_totals=accumulate, _is_usable_source_text=lambda text: bool(text.strip()))
    return module.NewTranslationBlocks(workflow, config, pages, source_hash="1" * 64, context_hash="context")


def source_page(number, *, uncertain=False):
    source = structure_from_text(SOURCE, page_number=number, source_file_sha256="1" * 64)
    source.provenance, source.uncertain = "digital_pdf", uncertain
    source.blocks[0].uncertain = uncertain
    # Middle page spans both zones, permitting a proven continuation on either side.
    source.blocks[0].bbox = (48, 60 if number > 1 else 680, 530, 760)
    return source


@pytest.mark.parametrize("final_correct", [True, False])
def test_block_numeric_defect_gets_exactly_one_source_grounded_correction(tmp_path, monkeypatch, final_correct):
    run = adapter(monkeypatch)
    source = structure_from_text(SOURCE, page_number=1, source_file_sha256="1" * 64)
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        text = TRANSLATED if len(calls) == 2 and final_correct else TRANSLATED.replace("25", "26")
        return ApiCallResult(raw_output=json.dumps({"blocks": [{"id": "p0001_b0001", "text": text}]}),
            usage={"input_tokens": 8, "output_tokens": 12, "total_tokens": 20}, response_id="synthetic",
            response_status="completed", model=module.OPENAI_MODEL, effort="high")
    metadata = {"api_calls_count": 0, "transport_retries_count": 0}
    result = run.translate(client=SimpleNamespace(create_page_response=create), source=source,
        paths=SimpleNamespace(pages_dir=tmp_path / "pages"), page_number=1, total_pages=1,
        context_text=None, image_data_url=None, image_detail="low", effort="high",
        metadata=metadata, started=time.perf_counter())
    assert len(calls) == 2 and result.retry_used
    assert calls[1]["prompt_text"].startswith(calls[0]["prompt_text"])
    diagnostic_text = calls[1]["prompt_text"].split("Validated block diagnostics: ", 1)[1]
    diagnostics, _ = json.JSONDecoder().raw_decode(diagnostic_text)
    assert diagnostics == [{"block_id": "p0001_b0001", "code": "block_numeric_association_defect"}]
    assert result.page_metadata["total_tokens"] == 40
    assert result.page_metadata["fidelity_review_status"] == "not_evaluated"
    assert result.status == (PageStatus.DONE if final_correct else PageStatus.FAILED)
    assert (tmp_path / "pages" / "page_0001.commit.json").exists() is final_correct


@pytest.mark.parametrize("mode,required,helpful,suspect,eligible", [
    (OcrMode.OFF, False, False, False, True),
    (OcrMode.OFF, False, True, False, True),
    (OcrMode.AUTO, False, False, False, True),
    (OcrMode.ALWAYS, False, False, False, False),
    (OcrMode.AUTO, False, True, False, False),
    (OcrMode.AUTO, True, False, False, False),
    (OcrMode.OFF, True, False, False, False),
    (OcrMode.OFF, False, False, True, False),
    (OcrMode.AUTO, False, False, True, False),
])
def test_neighbor_context_requires_proven_direct_source_winner(monkeypatch, mode, required, helpful, suspect, eligible):
    run = adapter(monkeypatch, mode=mode, pages=(1, 2, 3))
    extracted = []
    def extract(_path, index, **kwargs):
        assert kwargs == {"preserve_structure": True}
        extracted.append(index)
        return SimpleNamespace(text=SOURCE, extraction_failed=False)
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", extract)
    monkeypatch.setattr(workflow_module, "classify_extracted_text_quality",
        lambda _text: {"ocr_required": required, "ocr_helpful": helpful})
    monkeypatch.setattr(workflow_module, "_assess_extraction_integrity",
        lambda **_kw: SimpleNamespace(suspect=suspect))
    monkeypatch.setattr(module, "structure_from_ordered", lambda _ordered, **kw: source_page(kw["page_number"]))
    # Only local extraction/routing evidence may run; no OCR is acquired for a neighbor.
    monkeypatch.setattr(workflow_module, "ocr_pdf_page_text", lambda *a, **kw: pytest.fail("No neighbor OCR"))
    monkeypatch.setattr(workflow_module, "ocr_pdf_page_crop_text", lambda *a, **kw: pytest.fail("No neighbor OCR"))
    run.prepare_native_evidence()
    assert extracted == [0, 1, 2]
    assert sorted(run.ordered_pages) == [1, 2, 3]
    assert sorted(run.native_sources) == ([1, 2, 3] if eligible else [])
    assert run.contexts(source_page(2)) == ((SOURCE[-600:], SOURCE[:600]) if eligible else ("", ""))


@pytest.mark.parametrize("failure", ["failed", "uncertain", "integrity_unavailable"])
def test_missing_or_uncertain_evidence_does_not_certify_neighbors(monkeypatch, failure):
    run = adapter(monkeypatch, pages=(1, 2))
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda *a, **kw:
        SimpleNamespace(text=SOURCE, extraction_failed=failure == "failed"))
    monkeypatch.setattr(workflow_module, "classify_extracted_text_quality", lambda _text: {})
    def assess(**_kw):
        if failure == "integrity_unavailable":
            raise OSError("synthetic unavailable evidence")
        return SimpleNamespace(suspect=False)
    monkeypatch.setattr(workflow_module, "_assess_extraction_integrity", assess)
    monkeypatch.setattr(module, "structure_from_ordered", lambda _ordered, **kw:
        source_page(kw["page_number"], uncertain=failure == "uncertain"))
    run.prepare_native_evidence()
    assert run.native_sources == {}
    assert run.contexts(source_page(2)) == ("", "")


@pytest.mark.parametrize("version", ["STRUCTURE_VERSION", "SOURCE_STRUCTURE_VERSION", "NATIVE_EXTRACTION_VERSION", "CONTEXT_POLICY_VERSION"])
def test_extraction_and_context_versions_invalidate_translation_identity(monkeypatch, version):
    first = adapter(monkeypatch).identity
    original = getattr(module, version)
    monkeypatch.setattr(module, version, original + 1 if isinstance(original, int) else original + "_changed")
    assert adapter(monkeypatch).identity != first


def test_formatting_only_change_does_not_invalidate_adapter_identity(monkeypatch):
    first = adapter(monkeypatch)
    original = deepcopy(first.identity)
    first.config.page_breaks = True
    second = module.NewTranslationBlocks(first.workflow, first.config, (1,), source_hash="1" * 64, context_hash="context")
    assert second.identity == original


@pytest.mark.parametrize("label", ["nome", "Nome", "NOME", "Testemunha", "SIGNATÁRIO", "Name"])
def test_name_label_case_is_flexible_but_name_spelling_is_not(label):
    source = {"id": "p0001_b0001", "text": f"{label}: João Guerreiro"}
    assert module._NAME.findall(source["text"]) == ["João Guerreiro"]
    assert module._NAME.findall(f"{label}: joão guerreiro") == []
    with pytest.raises(module.BlockCoverageError, match="block_name_defect"):
        module.validate_block(source, "Name: Joao Guerreiro", TargetLang.EN, None, set())
