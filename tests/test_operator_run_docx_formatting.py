"""Explicit ordinary operator profile; entirely fictional bound review evidence."""
from copy import deepcopy
from dataclasses import replace
import io
import json
import zipfile

import pytest

from legalpdf_translate import run_docx_formatting as adapter
from legalpdf_translate import reviewed_formatting as formatting
from legalpdf_translate import reviewed_formatting_writer as writer
from legalpdf_translate import reviewed_region_writer as regions
from legalpdf_translate.checkpoint import build_run_paths, load_run_state, new_run_state, save_run_state_atomic
from legalpdf_translate.layout_integration import collect_docx_layout_review
from legalpdf_translate.reviewed_source import ReviewedSourceEvidence, adapt_reviewed_candidate
from legalpdf_translate.types import TargetLang
from tests import test_run_docx_formatting as ordinary
from tests.test_acceptance_formatting import case as acceptance_case
from tests.test_source_review_candidate import bind_review, build


PROFILE = adapter.OPERATOR_REVIEW_PROFILE
encode, sha = ordinary.encode, ordinary.sha


def operator_case(tmp_path, monkeypatch, **options):
    """Bind operator source decisions before creating any committed run pages."""
    original_fixture, original_envelope = ordinary.reviewed_fixture, ordinary.decision_envelope

    def source_fixture(*args, **kwargs):
        case = original_fixture(*args, **kwargs)
        manifest, artifacts = deepcopy(case.manifest), dict(case.evidence.artifacts)
        for index, page in enumerate(manifest["pages"]):
            old_hash = page["review_evidence_sha256"]
            review = json.loads(artifacts[old_hash])
            review.update(review_kind="operator_review", reviewer="Fictional operator")
            bind_review(manifest, review, artifacts, index)
            del artifacts[old_hash]
        candidate = build(manifest, artifacts, require_complete=True)
        evidence = ReviewedSourceEvidence(encode(candidate), encode(manifest), tuple(artifacts.items()))
        case.bindings.update(candidate_sha256=sha(evidence.candidate), manifest_sha256=sha(evidence.manifest))
        case.evidence, case.manifest, case.candidate, case.artifacts = evidence, manifest, candidate, artifacts
        case.sources = adapt_reviewed_candidate(evidence, **case.bindings)
        return case

    def envelope(case):
        result = original_envelope(case)
        result["review_kind"] = "operator_review"
        return result

    with monkeypatch.context() as scope:
        scope.setattr(ordinary, "reviewed_fixture", source_fixture)
        scope.setattr(ordinary, "decision_envelope", envelope)
        return ordinary.setup(tmp_path, reviewer="operator_review", **options)


def submit(case, *, profile=PROFILE, partial=False):
    return adapter.submit_run_formatting_review(case.run_dir, case.config, case.state,
        reviewer_kind=case.reviewer, review_profile=profile, source_review=case.source_review,
        source_evidence=case.source_evidence, source_review_evidence=case.source_decision_evidence,
        formatting_manifest=encode(case.manifest), review_evidence=b"Fictional operator formatting decision.",
        partial_output=partial)


def prepare(case, revision, *, profile=PROFILE, partial=False):
    return adapter.prepare_run_docx_formatting(case.run_dir, case.config, case.state,
        revision_id=revision, review_profile=profile, partial_output=partial)


def revision_record(case, revision):
    return json.loads((case.run_dir / "formatting_reviews" / revision / "revision.json").read_bytes())


def use_v1_manifest(case):
    case.manifest.update(version=formatting.VERSION, policy=formatting.POLICY)
    del case.manifest["document_groups"], case.manifest["folio_policy"]
    for page in case.manifest["pages"]:
        del page["region_layout"], page["folio_fragment_id"]


@pytest.mark.parametrize("lang", [TargetLang.AR, TargetLang.EN, TargetLang.FR])
@pytest.mark.parametrize("version", [1, 2])
def test_explicit_operator_round_trip_retains_all_evidence_and_provenance(tmp_path, monkeypatch, lang, version):
    case = operator_case(tmp_path, monkeypatch, lang=lang, pages=2)
    if version == 1:
        use_v1_manifest(case)
    before, state_before = ordinary.originals(case), deepcopy(vars(case.state))
    draft = adapter.begin_run_formatting_review(case.run_dir, case.config, case.state,
        reviewer_kind="operator_review", review_profile=PROFILE)
    assert draft["version"] == "run_formatting_review_draft_v2" and draft["review_profile"] == PROFILE
    assert not draft["notice_codes"] and not (case.run_dir / "formatting_reviews").exists()
    revision = submit(case)
    record = revision_record(case, revision)
    assert record["version"] == adapter.OPERATOR_REVIEW_VERSION and record["review_profile"] == PROFILE
    assert record["region_review_kind"] == record["source_review_kind"] == "operator_review"
    prepared = prepare(case, revision)
    assert prepared.status == "ready" and prepared.expected_reviewer_kind == "operator_review"
    assert prepared.projection.reviewer_kind == "operator_review"
    for page in prepared.projection.pages:
        source = json.loads(page.source_structure_json)
        assert source["metadata"]["reviewed_source"]["review_kind"] == "operator_review"
    output = adapter.build_run_reviewed_docx(prepared, config=case.config, state=case.state,
                                            output_path=case.config.output_dir / "operator.docx")
    mapping = json.loads(output.with_suffix(".source_map.json").read_bytes())
    assert mapping["reviewer_kind"] == "operator_review"
    assert mapping["source_geometry_status"] == "not_verified"
    assert mapping["rendered_layout_acceptance"] == "not_evaluated" and mapping["layout_review_required"]
    writer.validate_reviewed_docx(output.read_bytes(), output.with_suffix(".source_map.json").read_bytes(),
        projection=prepared.projection, expected_reviewer_kind="operator_review")
    receipt = json.loads(output.with_suffix(".formatting_assembly.json").read_bytes())
    assert receipt["review_profile"] == PROFILE and receipt["provider_dispatch_count"] == 0
    assert receipt["source_review_kind"] == receipt["region_review_kind"] == "operator_review"
    folder = case.run_dir / "formatting_reviews" / revision
    assert (folder / "source_review.json").read_bytes() == case.source_review
    assert (folder / "source_decision_evidence.bin").read_bytes() == case.source_decision_evidence
    assert (folder / "formatting.json").read_bytes() == encode(case.manifest)
    assert ordinary.originals(case) == before and vars(case.state) == state_before
    assert case.config.page_breaks and case.config.strip_bidi_controls


def test_operator_revision_requires_explicit_profile_on_every_prepare(tmp_path, monkeypatch):
    case = operator_case(tmp_path, monkeypatch)
    revision = submit(case)
    default = adapter.prepare_run_docx_formatting(case.run_dir, case.config, case.state, revision_id=revision)
    assert default.status == "declined"
    assert "reviewed_profile_review_profile_mismatch" in default.notice_codes
    assert prepare(case, revision).status == "ready"
    legacy_revision = ordinary.submit(case)
    record = revision_record(case, legacy_revision)
    assert record["version"] == adapter.REVIEW_VERSION and "review_profile" not in record
    assert ordinary.prepare(case, legacy_revision).status == "declined"
    assert "reviewed_profile_review_profile_mismatch" in prepare(case, legacy_revision).notice_codes


def test_strict_default_keeps_existing_revision_and_map_shapes(tmp_path):
    case = ordinary.setup(tmp_path)
    revision = ordinary.submit(case)
    record = revision_record(case, revision)
    assert record["version"] == "run_formatting_review_v1" and "review_profile" not in record
    prepared = ordinary.prepare(case, revision)
    assert prepared.status == "ready" and prepared.review_profile == adapter.STRICT_REVIEW_PROFILE
    artifact = writer.build_reviewed_docx(prepared.projection)
    mapping = json.loads(artifact.source_map_bytes)
    explicit = json.loads(writer.build_reviewed_docx(prepared.projection,
        expected_reviewer_kind="ai_test_review").source_map_bytes)
    assert "reviewer_kind" not in mapping
    # ZIP timestamps may differ; reviewer selection changes no map semantics.
    del mapping["docx_sha256"], explicit["docx_sha256"]
    assert mapping == explicit


@pytest.mark.parametrize("invalid", [None, True, [], "operator", "ordinary_operator_browser_v2"])
def test_profile_context_rejects_unknown_or_nonstring_values(tmp_path, monkeypatch, invalid):
    case = operator_case(tmp_path, monkeypatch)
    with pytest.raises(adapter.RunDocxFormattingError, match="invalid_review_profile"):
        adapter.begin_run_formatting_review(case.run_dir, case.config, case.state,
            reviewer_kind="operator_review", review_profile=invalid)
    assert not (case.run_dir / "formatting_reviews").exists()


@pytest.mark.parametrize("wrong", ["source_envelope", "source_candidate", "region_manifest"])
def test_operator_profile_requires_both_genuine_operator_reviews(tmp_path, monkeypatch, wrong):
    case = (ordinary.setup(tmp_path, reviewer="operator_review") if wrong == "source_candidate"
            else operator_case(tmp_path, monkeypatch))
    if wrong in {"source_envelope", "source_candidate"}:
        envelope = json.loads(case.source_review)
        envelope["review_kind"] = "ai_test_review" if wrong == "source_envelope" else "operator_review"
        case.source_review = encode(envelope)
    else:
        case.reviewer = case.manifest["reviewer_kind"] = "ai_test_review"
    revision = submit(case)
    result = prepare(case, revision)
    assert result.status == "declined"
    expected = "reviewed_profile_unsupported_reviewer" if wrong == "region_manifest" else "reviewed_profile_unsupported_source_reviewer"
    assert expected in result.notice_codes


@pytest.mark.parametrize("options,partial,notice", [
    ({"page_breaks": False}, False, "reviewed_profile_requires_page_breaks"),
    ({"strip": False}, False, "reviewed_profile_requires_bidi_stripping"),
    ({"pages": 2, "selected": [2]}, True, "reviewed_profile_unsupported_selection"),
    ({"provenance": "digital_pdf"}, False, "reviewed_profile_unsupported_source_provenance"),
    ({"provenance": "local_ocr_tsv", "native_pdf": False}, False, "reviewed_profile_unsupported_source_provenance"),
    ({"provenance": "local_ocr_tsv", "native_pdf": True}, False, "reviewed_profile_unsupported_source_provenance"),
])
def test_operator_opt_in_does_not_broaden_other_profile_constraints(tmp_path, monkeypatch, options, partial, notice):
    case = operator_case(tmp_path, monkeypatch, **options)
    revision = submit(case, partial=partial)
    result = prepare(case, revision, partial=partial)
    assert result.status == "declined" and notice in result.notice_codes
    assert case.config.page_breaks == options.get("page_breaks", True)
    assert case.config.strip_bidi_controls == options.get("strip", True)


@pytest.mark.parametrize("version", [1, 2])
def test_shared_validator_and_writer_defaults_stay_strict_and_map_cannot_authorize_operator(tmp_path, monkeypatch, version):
    case = operator_case(tmp_path, monkeypatch)
    if version == 1:
        use_v1_manifest(case)
    prepared = prepare(case, submit(case))
    image = dict(case.source_evidence.artifacts)[case.manifest["pages"][0]["source_image_sha256"]]
    page = prepared.projection.pages[0]
    options = dict(expected_manifest_sha256=sha(encode(case.manifest)),
        pages=[formatting.FormattingPageInput(json.loads(page.source_structure_json),
            json.loads(page.target_structure_json), page.commit_file_sha256, page.bundle_sha256, image)],
        source_file_sha256=prepared.projection.source_file_sha256, target_lang=case.config.target_lang.value,
        preferences_sha256=prepared.projection.preferences_sha256)
    with pytest.raises(formatting.ReviewedFormattingError):
        formatting.validate_reviewed_formatting(encode(case.manifest), **options)
    assert formatting.validate_reviewed_formatting(encode(case.manifest), **options,
        expected_reviewer_kind="operator_review") == prepared.projection
    with pytest.raises(writer.ReviewedFormattingWriterError):
        writer.build_reviewed_docx(prepared.projection)
    artifact = writer.build_reviewed_docx(prepared.projection, expected_reviewer_kind="operator_review")
    with pytest.raises(writer.ReviewedFormattingWriterError):
        writer.validate_reviewed_docx(artifact.docx_bytes, artifact.source_map_bytes, projection=prepared.projection)
    mapping = json.loads(artifact.source_map_bytes)
    mapping["reviewer_kind"] = "ai_test_review"
    with pytest.raises(writer.ReviewedFormattingWriterError):
        writer.validate_reviewed_docx(artifact.docx_bytes, encode(mapping), projection=prepared.projection,
                                     expected_reviewer_kind="operator_review")
    with pytest.raises(writer.ReviewedFormattingWriterError):
        writer.validate_reviewed_docx(artifact.docx_bytes, artifact.source_map_bytes,
                                     projection=replace(prepared.projection, reviewer_kind="ai_test_review"))
    if version == 2:
        with pytest.raises(writer.ReviewedFormattingWriterError):
            regions.build_region_docx(prepared.projection)
        with pytest.raises(writer.ReviewedFormattingWriterError):
            regions.validate_region_docx(artifact.docx_bytes, artifact.source_map_bytes, projection=prepared.projection)


def test_private_acceptance_wrapper_still_rejects_operator_manifest(acceptance_case):
    from legalpdf_translate import acceptance_formatting as acceptance
    options = deepcopy(acceptance_case)
    manifest = json.loads(options["formatting_manifest"])
    manifest["reviewer_kind"] = "operator_review"
    options["formatting_manifest"] = encode(manifest)
    options["expected_manifest_sha256"] = sha(options["formatting_manifest"])
    binding = acceptance.partition_assembly_binding(page_bundles=options["page_bundles"],
        full_case_pages=options["full_case_pages"], source_file_sha256=options["source_file_sha256"],
        lang=options["lang"], preferences_sha256=options["preferences_sha256"],
        formatting_manifest_sha256=options["expected_manifest_sha256"])
    options["evidence_guard"] = lambda: deepcopy(binding)
    before = {path: path.read_bytes() for ref in options["page_bundles"] for path in ref.pages_dir.iterdir()}
    with pytest.raises(ValueError):
        acceptance.assemble_reviewed_partition_case(**options)
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert not list(options["output_dir"].glob("*.docx"))


@pytest.mark.parametrize("name", ["source_review.json", "source_decision_evidence.bin", "formatting.json", "review_evidence.bin"])
def test_operator_saved_evidence_corruption_is_integrity_failure(tmp_path, monkeypatch, name):
    case = operator_case(tmp_path, monkeypatch)
    revision = submit(case)
    path = case.run_dir / "formatting_reviews" / revision / name
    path.write_bytes(path.read_bytes() + b" changed")
    with pytest.raises(adapter.RunDocxFormattingError, match="revision_file_changed"):
        prepare(case, revision)
    assert not list(case.config.output_dir.glob("*.docx"))


def test_operator_revision_version_and_profile_are_closed_bindings(tmp_path, monkeypatch):
    case = operator_case(tmp_path, monkeypatch)
    revision = submit(case)
    path = case.run_dir / "formatting_reviews" / revision / "revision.json"
    record = revision_record(case, revision)
    for change in ({"review_profile": adapter.STRICT_REVIEW_PROFILE}, {"version": adapter.REVIEW_VERSION}):
        path.write_bytes(encode({**record, **change}))
        with pytest.raises(adapter.RunDocxFormattingError, match="invalid_revision"):
            prepare(case, revision)


def test_operator_package_checker_keeps_exact_text_validation_even_with_forged_hash(tmp_path, monkeypatch):
    case = operator_case(tmp_path, monkeypatch)
    prepared = prepare(case, submit(case))
    artifact = writer.build_reviewed_docx(prepared.projection, expected_reviewer_kind="operator_review")
    changed = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(artifact.docx_bytes)) as source, zipfile.ZipFile(changed, "w") as target:
        for info in source.infolist():
            raw = source.read(info.filename)
            if info.filename == "word/document.xml":
                raw = raw.replace(b"Contenu", b"Altered", 1)
            target.writestr(info, raw)
    mapping = json.loads(artifact.source_map_bytes)
    mapping["docx_sha256"] = sha(changed.getvalue())
    with pytest.raises(writer.ReviewedFormattingWriterError):
        writer.validate_reviewed_docx(changed.getvalue(), encode(mapping), projection=prepared.projection,
                                     expected_reviewer_kind="operator_review")


def test_collector_requires_caller_operator_context_and_binds_current_txt(tmp_path, monkeypatch):
    case = operator_case(tmp_path, monkeypatch)
    prepared = prepare(case, submit(case))
    output = adapter.build_run_reviewed_docx(prepared, config=case.config, state=case.state,
                                            output_path=case.config.output_dir / "operator.docx")
    options = dict(page_numbers=[1], reviewed_projection=prepared.projection)
    strict = collect_docx_layout_review(output, case.pages_dir, {}, **options)
    assert "layout_mapping_unavailable" in strict[1]
    assert collect_docx_layout_review(output, case.pages_dir, {}, **options,
        expected_reviewer_kind="operator_review") == {1: ["layout_review_required"]}
    (case.pages_dir / "page_0001.txt").write_bytes(b"Edited fictional text.")
    assert "layout_mapping_unavailable" in collect_docx_layout_review(output, case.pages_dir, {},
        **options, expected_reviewer_kind="operator_review")[1]
    assert "reviewed_profile_stale_edited_target" in prepare(case, prepared.revision_id).notice_codes


def test_workflow_explicit_operator_acquisition_and_rebuild_keep_accounting(tmp_path, monkeypatch):
    from legalpdf_translate import workflow as workflow_module
    from tests.test_reviewed_rebuild_workflow import forbidden
    case = operator_case(tmp_path, monkeypatch)
    paths = build_run_paths(case.config.output_dir, case.config.pdf_path, case.config.target_lang)
    case.run_dir.rename(paths.run_dir)
    case.run_dir, case.pages_dir = paths.run_dir, paths.pages_dir
    state = new_run_state(config=case.config, paths=paths, pdf_fingerprint=case.state.pdf_fingerprint,
                         context_hash="NO_CONTEXT", total_pages=1, selected_pages=[1])
    state.pages, state.protocol_identity = deepcopy(case.state.pages), deepcopy(case.state.protocol_identity)
    state.dispatch_accounting = {"retained": {"cost": "0.0123", "calls": 1}}
    state.run_status, state.finished_at = "completed", "2026-09-15T00:00:00+00:00"
    state.done_count, state.pending_count, state.last_completed_page = 1, 0, 1
    save_run_state_atomic(paths.run_state_path, state)
    workflow = workflow_module.TranslationWorkflow(gui_settings={})
    for name in ("OpenAIResponsesClient", "extract_ordered_page_text", "build_ocr_engine",
                 "run_translation_auth_test", "resolve_openai_key_with_source", "load_environment", "assemble_docx"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    monkeypatch.setattr(workflow, "_prepare_docx_layout", forbidden)
    draft = workflow.begin_docx_formatting_review(case.config, reviewer_kind="operator_review", review_profile=PROFILE)
    assert draft["review_profile"] == PROFILE
    revision = workflow.submit_docx_formatting_review(case.config, reviewer_kind="operator_review",
        review_profile=PROFILE, source_review=case.source_review, source_evidence=case.source_evidence,
        source_review_evidence=case.source_decision_evidence, formatting_manifest=encode(case.manifest),
        review_evidence=b"Fictional operator formatting decision.")
    before = ordinary.originals(case)
    output = workflow.rebuild_docx(case.config, formatting_revision_id=revision, formatting_review_profile=PROFILE)
    assert json.loads(output.with_suffix(".source_map.json").read_bytes())["reviewer_kind"] == "operator_review"
    restored = load_run_state(paths.run_state_path)
    assert restored.dispatch_accounting == state.dispatch_accounting and restored.settings == state.settings
    assert restored.protocol_identity == state.protocol_identity
    assert restored.pages["1"]["structured_commit"] == state.pages["1"]["structured_commit"]
    assert restored.pages["1"]["layout_review_reasons"] == ["layout_review_required"]
    assert ordinary.originals(case) == before
    with pytest.raises(ValueError, match="explicit formatting revision"):
        workflow.rebuild_docx(case.config, formatting_review_profile=PROFILE)
