from __future__ import annotations

from copy import deepcopy
import json

import pytest

from legalpdf_translate import checkpoint
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.structured_artifacts import StructuredArtifactError, publish_structured_page
from legalpdf_translate.types import RunConfig, TargetLang


IDENTITY = {"protocol": "legal_blocks_v2", "fingerprint": "a" * 64}


def case(tmp_path, identity=IDENTITY):
    config = RunConfig(pdf_path=tmp_path / "source.pdf", output_dir=tmp_path / "out", target_lang=TargetLang.EN)
    paths = checkpoint.build_run_paths(config.output_dir, config.pdf_path, config.target_lang, run_started_at="20260907_180000")
    state = checkpoint.new_run_state(config=config, paths=paths, pdf_fingerprint="b" * 64,
        context_hash="empty", total_pages=1, selected_pages=[1], protocol_identity=identity)
    args = dict(config=config, paths=paths, pdf_fingerprint="b" * 64, context_hash="empty",
        selection_start_page=1, selection_end_page=1, selection_page_count=1, max_pages_effective=1,
        protocol_identity=identity)
    return state, paths, args


def commit_page(paths):
    source = PageStructure(page_number=1, source_sha256=text_sha256("Aviso"), source_text_sha256=text_sha256("Aviso"),
        source_file_sha256="b" * 64, blocks=[StructureBlock("p0001_b0001", "Aviso")])
    target = source.to_dict()
    target["blocks"][0]["text"] = "Notice"
    target["translation_sha256"] = text_sha256("Notice")
    return publish_structured_page(paths.pages_dir, source_structure=source, translated_structure=target,
        translated_text="Notice", protocol_identity=IDENTITY, page_fingerprint="c" * 64)


def test_additive_checkpoint_identity_round_trip_and_old_file_default(tmp_path):
    state, paths, _ = case(tmp_path)
    checkpoint.save_run_state_atomic(paths.run_state_path, state)
    assert checkpoint.load_run_state(paths.run_state_path).protocol_identity == IDENTITY
    legacy = state.to_dict()
    legacy.pop("protocol_identity")
    paths.run_state_path.write_text(json.dumps(legacy), encoding="utf-8")
    assert checkpoint.load_run_state(paths.run_state_path).protocol_identity == {}


@pytest.mark.parametrize("old,new", [({}, IDENTITY), (IDENTITY, {}), (IDENTITY, {**IDENTITY, "fingerprint": "d" * 64})])
def test_protocol_mismatch_is_read_only_even_with_no_directories(tmp_path, old, new):
    state, paths, args = case(tmp_path, old)
    before = deepcopy(state.to_dict())
    args["protocol_identity"] = new
    assert "protocol" in checkpoint.resume_incompatibility_reason(state, **args).lower()
    assert state.to_dict() == before
    assert not paths.run_dir.exists()


def test_structured_done_requires_verified_commit_not_metadata_claim(tmp_path):
    state, paths, _ = case(tmp_path)
    before = deepcopy(state.to_dict())
    with pytest.raises(StructuredArtifactError):
        checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={})
    assert state.to_dict() == before
    record = commit_page(paths)
    (paths.pages_dir / "page_0001.txt").write_text("changed", encoding="utf-8")
    with pytest.raises(StructuredArtifactError):
        checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={}, structured_commit=record)
    assert state.to_dict() == before


def test_completed_structured_page_resumes_only_with_matching_artifacts(tmp_path):
    state, paths, args = case(tmp_path)
    record = commit_page(paths)
    checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={"total_tokens": 2}, structured_commit=record)
    assert state.pages["1"]["structured_commit"] == record
    assert state.pages["1"]["structured_evidence_state"] == "retained"
    assert checkpoint.is_resume_compatible(state, **args)
    before = deepcopy(state.to_dict())
    (paths.pages_dir / "page_0001.structure.json").unlink()
    assert "structured" in checkpoint.resume_incompatibility_reason(state, **args).lower()
    assert state.to_dict() == before


def test_lone_text_or_uncheckpointed_commit_cannot_trigger_paid_resume(tmp_path):
    state, paths, args = case(tmp_path)
    paths.pages_dir.mkdir(parents=True)
    (paths.pages_dir / "page_0001.txt").write_text("unfinished", encoding="utf-8")
    assert "incomplete" in checkpoint.resume_incompatibility_reason(state, **args).lower()


def test_deliberate_purge_is_distinct_without_deleting_evidence_or_usage(tmp_path):
    state, paths, args = case(tmp_path)
    record = commit_page(paths)
    checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={"total_tokens": 2}, structured_commit=record)
    checkpoint.mark_structured_evidence_purged(state, [1])
    assert state.pages["1"]["structured_evidence_state"] == "purged"
    assert state.pages["1"]["status"] == "done"
    assert state.pages["1"]["usage"] == {"total_tokens": 2}
    assert (paths.pages_dir / "page_0001.txt").exists()
    assert "purged" in checkpoint.resume_incompatibility_reason(state, **args).lower()


def test_legacy_done_still_works_without_new_proof(tmp_path):
    state, _, args = case(tmp_path, {})
    checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={})
    assert checkpoint.is_resume_compatible(state, **args)


def test_legacy_cannot_be_marked_done_with_structured_commit(tmp_path):
    state, paths, _ = case(tmp_path, {})
    record = commit_page(paths)
    with pytest.raises(StructuredArtifactError):
        checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={}, structured_commit=record)
    assert state.pages["1"]["status"] == "pending"


def test_commit_without_recoverable_result_requires_explicit_recovery_not_translation(tmp_path):
    state, paths, args = case(tmp_path)
    commit_page(paths)
    before = deepcopy(state.to_dict())
    assert "explicit recovery" in checkpoint.resume_incompatibility_reason(state, **args)
    assert state.to_dict() == before


def test_failed_purge_selection_does_not_partially_change_state(tmp_path):
    state, paths, _ = case(tmp_path)
    record = commit_page(paths)
    checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={}, structured_commit=record)
    before = deepcopy(state.to_dict())
    with pytest.raises(StructuredArtifactError):
        checkpoint.mark_structured_evidence_purged(state, [1, 2])
    assert state.to_dict() == before


def test_formatting_only_change_does_not_modify_protocol_evidence(tmp_path):
    state, paths, _ = case(tmp_path)
    record = commit_page(paths)
    checkpoint.mark_page_done(state, 1, image_used=False, retry_used=False, usage={}, structured_commit=record)
    from legalpdf_translate.docx_writer import assemble_docx
    # Evidence is available through assembly regardless of whether its caller
    # will retain these files afterward. No provider/source extraction is used.
    output = assemble_docx(paths.pages_dir, paths.frozen_outdir / "synthetic.docx", lang=TargetLang.EN, page_breaks=False)
    assert output.is_file()
    assert state.protocol_identity == IDENTITY
    assert state.pages["1"]["structured_commit"] == record
    checkpoint.mark_structured_evidence_purged(state, [1])
    assert output.is_file()
