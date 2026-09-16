"""Explicit synthetic review authorities. Never an actual-document reviewer."""
import hashlib
import json

from legalpdf_translate.source_readiness import (SOURCE_READINESS_VERSION,
    source_readiness_diagnostics, source_structure_digest, _digest)


def synthetic_review(sources):
    return json.dumps({"version": SOURCE_READINESS_VERSION, "review_kind": "ai_test_review",
        "review_evidence_sha256": hashlib.sha256(b"SYNTHETIC UNIT TEST REVIEW ONLY").hexdigest(),
        "source_file_sha256": sources[0].source_file_sha256,
        "pages": [{"source_structure": source.to_dict(),
            "reviewed_source_sha256": source_structure_digest(source),
            "readiness_sha256": _digest(source_readiness_diagnostics(source)),
            "source_fidelity": "accepted", "document_boundary": "accepted", "unresolved_findings": []}
            for source in sources]}, ensure_ascii=False, sort_keys=True)


def synthetic_native_review(config, pages):
    from legalpdf_translate.new_translation_blocks import NewTranslationBlocks
    from legalpdf_translate.workflow import TranslationWorkflow
    workflow = TranslationWorkflow(gui_settings={}, environment_loader=lambda: None,
                                   translation_protocol="legal_blocks_v2")
    source_hash = hashlib.sha256(config.pdf_path.read_bytes()).hexdigest()
    adapter = NewTranslationBlocks(workflow, config, pages, source_hash=source_hash, context_hash="fixture-only")
    adapter.prepare_native_evidence()
    sources = []
    for number in pages:
        ordered = adapter.ordered_pages[number]
        sources.append(adapter.make_source(number=number, ordered=ordered, text=ordered.text,
            ocr_result=None, ocr_used=False, merged=False, suspect=False))
    return synthetic_review(sources)
