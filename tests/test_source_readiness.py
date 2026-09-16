"""Synthetic source and review gates; no OCR, network, Word or user documents."""
from copy import deepcopy
from dataclasses import replace
import json
import time
from types import SimpleNamespace

import pytest

from legalpdf_translate import ocr_engine as ocr
from legalpdf_translate.document_structure import (classify_document_boundaries,
    apply_reviewed_document_boundary, structure_from_tesseract_tsv, rebind_page_structure, text_sha256)
from legalpdf_translate.new_translation_blocks import NewTranslationBlocks
from legalpdf_translate.source_readiness import (source_readiness_diagnostics, source_structure_digest,
    verify_source_review, verify_reviewed_page, _digest)
from legalpdf_translate.structured_artifacts import StructuredArtifactError
from legalpdf_translate.workflow import TranslationWorkflow
from legalpdf_translate.types import PageStatus
from tests.test_acceptance_continuation import offline, policy
from tests.test_new_translation_blocks import configuration, FakeClient
from tests.test_document_structure import _word_tsv
from tests.test_source_layout_eligibility import simple_page
from tests.source_readiness_fixtures import synthetic_review, synthetic_native_review


def test_saturated_legacy_score_is_not_source_fidelity_and_does_not_add_passes(monkeypatch):
    tsv = _word_tsv(*[{"text": "Texto legal com referencia 1234 e notificacao", "line": n,
        "top": 100 + n * 40, "confidence": 45 if n == 7 else 99} for n in range(1, 19)])
    text = "\n".join(["Texto legal com referencia 1234 e notificacao"] * 18)
    calls = []
    monkeypatch.setattr(ocr, "which", lambda _: "synthetic-not-executed")
    def fake_pass(self, **kwargs):
        calls.append(kwargs["pass_spec"])
        return 0, text, "", tsv
    monkeypatch.setattr(ocr.LocalTesseractEngine, "_run_pass", fake_pass)
    result = ocr.LocalTesseractEngine().ocr_image(b"synthetic-image", lang_hint="AR", preserve_structure=True)
    assert result.quality_score == 1.0 and result.selected_pass == "pass_a_document"
    assert len(calls) == 1 and result.text == text and result.structure is not None
    diagnostic = result.structure_metadata["source_readiness"]
    assert diagnostic["status"] == "review_required" and diagnostic["fidelity_status"] == "not_evaluated"
    assert diagnostic["winner_score_is_fidelity"] is False
    assert diagnostic["counts"]["below_60"] > 0
    assert "low_confidence_source_words" in diagnostic["codes"]


def test_mixed_columns_small_critical_fields_and_footer_ink_remain_source_uncertainty():
    tsv = _word_tsv({"text": "Tribunal Judicial", "word_gap": 200, "top": 50},
        {"text": "Referencia 100/26", "top": 400, "line": 2, "height": 12, "confidence": 55},
        {"text": "Email secretaria@example.invalid", "top": 1800, "block": 2, "confidence": 40})
    source = structure_from_tesseract_tsv(tsv)
    before = source.to_dict()
    diagnostic = source_readiness_diagnostics(source)
    assert {"possible_mixed_columns", "small_source_fields_require_review", "uncertain_footer_content",
            "unrecognized_ink_not_evaluated"} <= set(diagnostic["codes"])
    assert diagnostic["counts"]["wide_word_gaps"] == 1
    assert source.to_dict() == before  # No discarded/footer cleanup/reordered winner.


@pytest.mark.parametrize("change", [
    lambda s: s.metadata.pop("ocr_word_evidence"),
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(confidence=float("nan")),
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(text="substituted"),
    lambda s: s.metadata["ocr_word_evidence"]["words"][0].update(block_id="foreign"),
    lambda s: s.metadata["ocr_word_evidence"].update(tsv_sha256="b" * 64),
])
def test_missing_or_invalid_word_evidence_never_looks_like_zero_uncertain_words(change):
    source, _, _ = simple_page()
    change(source)
    diagnostic = source_readiness_diagnostics(source)
    assert "same_pass_word_evidence_invalid_or_missing" in diagnostic["codes"]
    assert diagnostic["counts"]["words"] is None


def missing_title_scan():
    source, _, identity = simple_page()
    source = rebind_page_structure(source, page_number=3)
    return classify_document_boundaries(source), identity


def test_missing_title_recurring_header_requests_review_without_inventing_a_boundary():
    source, _ = missing_title_scan()
    assert not source.document_start and source.metadata["document_boundary_review_required"]
    assert source.metadata["document_boundary_signals"] == ["recurring_header_not_sufficient"]
    assert "document_boundary_unresolved" in source_readiness_diagnostics(source)["codes"]


@pytest.mark.parametrize("decision", ["start", "continuation"])
def test_explicit_hash_bound_boundary_review_preserves_text_boxes_and_uncertainty(decision):
    source, identity = missing_title_scan()
    before = source.to_dict()
    record = {"source_structure_sha256": source_structure_digest(source), "decision": decision,
              "review_kind": "ai_test_review", "review_evidence_sha256": "b" * 64}
    reviewed = apply_reviewed_document_boundary(source, record)
    assert reviewed.document_start is (decision == "start")
    assert reviewed.uncertain and reviewed.text == source.text
    assert [b.bbox for b in reviewed.blocks] == [b.bbox for b in source.blocks]
    assert source.to_dict() == before and not reviewed.metadata["document_boundary_review_required"]
    verify_source_review(synthetic_review([reviewed]), page_identities={3: identity}, source_hash="a" * 64)
    source.blocks[0].text += " changed"
    with pytest.raises(ValueError, match="boundary_review_invalid"):
        apply_reviewed_document_boundary(source, record)


def test_unresolved_boundary_blocks_layout_before_render_or_cache(monkeypatch, tmp_path):
    from legalpdf_translate import layout_integration as layout
    source, _ = missing_title_scan()
    monkeypatch.setattr(layout, "_render_source", lambda *a: pytest.fail("no render"))
    monkeypatch.setattr(layout.LayoutCache, "get", lambda *a: pytest.fail("no cache reuse"))
    result = layout.derive_source_layout(source, tmp_path / "absent.pdf")
    assert result["status"] == "needs_review" and "document_boundary_unresolved" in result["warnings"]


@pytest.mark.parametrize("change", [
    lambda r: r["pages"].clear(),
    lambda r: r["pages"].append(deepcopy(r["pages"][0])),
    lambda r: r["pages"][0].update(source_fidelity="review_required"),
    lambda r: r["pages"][0].update(document_boundary="not_evaluated"),
    lambda r: r["pages"][0].update(unresolved_findings=["small critical field"]),
    lambda r: r["pages"][0].update(readiness_sha256="0" * 64),
    lambda r: r["pages"][0]["source_structure"]["metadata"]["source_page_identity"].update(image_sha256="0" * 64),
    lambda r: r["pages"][0]["source_structure"]["metadata"].update(selected_text_sha256="0" * 64),
    lambda r: r["pages"][0]["source_structure"].update(source_text_sha256="0" * 64),
    lambda r: r["pages"][0]["source_structure"]["blocks"][0].update(text="changed"),
])
def test_review_is_bound_to_complete_source_raster_text_geometry_and_completed_findings(change):
    source, _, identity = simple_page()
    raw = synthetic_review([source])
    verify_source_review(raw, page_identities={1: identity}, source_hash="a" * 64)
    record = json.loads(raw)
    change(record)
    with pytest.raises(StructuredArtifactError):
        verify_source_review(json.dumps(record), page_identities={1: identity}, source_hash="a" * 64)


def test_later_page_unresolved_stops_first_page_before_client_or_ocr(tmp_path):
    config = configuration(tmp_path, pages=2)
    client = FakeClient()
    review = json.loads(synthetic_native_review(config, (1, 2)))
    review["pages"][1]["source_fidelity"] = "review_required"
    continuation = replace(policy(pages=(1, 2), subset=(1,)), source_review_json=json.dumps(review))
    workflow = TranslationWorkflow(client=client, gui_settings={}, environment_loader=lambda: None,
        translation_protocol="legal_blocks_v2", acceptance_continuation=continuation)
    with pytest.raises(StructuredArtifactError, match="source_review_unresolved"):
        NewTranslationBlocks(workflow, config, (1, 2), source_hash=review["source_file_sha256"], context_hash="fixture")
    assert not client.calls


def test_source_change_after_review_cannot_dispatch_or_create_paid_intent(tmp_path):
    config = configuration(tmp_path)
    review = synthetic_native_review(config, (1,))
    source_hash = json.loads(review)["source_file_sha256"]
    client = FakeClient()
    continuation = replace(policy(), source_review_json=review)
    workflow = TranslationWorkflow(client=client, gui_settings={}, environment_loader=lambda: None,
        translation_protocol="legal_blocks_v2", acceptance_continuation=continuation)
    workflow._last_state = SimpleNamespace(pages={})
    adapter = NewTranslationBlocks(workflow, config, (1,), source_hash=source_hash, context_hash="fixture")
    adapter.prepare_native_evidence()
    ordered = adapter.ordered_pages[1]
    source = adapter.make_source(number=1, ordered=ordered, text=ordered.text,
        ocr_result=None, ocr_used=False, merged=False, suspect=False)
    source.blocks[0].bbox = (1, 2, 3, 4)
    result = adapter.translate(client=client, source=source, paths=SimpleNamespace(run_dir=tmp_path),
        page_number=1, total_pages=1, context_text=None, image_data_url=None, image_detail="low", effort="high",
        metadata={"api_calls_count": 0, "transport_retries_count": 0}, started=time.perf_counter())
    assert result.status == PageStatus.FAILED and not client.calls
    assert not (tmp_path / "acceptance_private").exists()


def test_duplicate_json_keys_cannot_hide_unresolved_review():
    source, _, identity = simple_page()
    raw = synthetic_review([source]).replace('"source_fidelity": "accepted"',
        '"source_fidelity":"review_required","source_fidelity":"accepted"')
    with pytest.raises(StructuredArtifactError):
        verify_source_review(raw, page_identities={1: identity}, source_hash="a" * 64)


def test_neighbor_context_uses_the_same_explicit_reviewed_boundaries(monkeypatch):
    from tests.test_new_run_adapter_safety import adapter, source_page
    from legalpdf_translate import new_translation_blocks as module
    run = adapter(monkeypatch, pages=(1, 2, 3))
    monkeypatch.setattr(module, "source_page_identity", lambda *a: {"source_file_sha256": "1" * 64})
    sources = {n: run._bind_source(source_page(n), number=n, text=source_page(n).text) for n in (1, 2, 3)}
    assert run.native_sources == {}
    run.native_sources.update(sources)
    assert run.contexts(sources[2])[1]
    record = {"source_structure_sha256": source_structure_digest(sources[3]), "decision": "start",
              "review_kind": "ai_test_review", "review_evidence_sha256": "b" * 64}
    reviewed = apply_reviewed_document_boundary(sources[3], record)
    run.reviewed_sources[3] = {"source_structure": reviewed.to_dict()}
    run.native_sources[3] = run._bind_source(source_page(3), number=3, text=source_page(3).text)
    assert run.native_sources[3].document_start and run.contexts(sources[2])[1] == ""
