"""Offline ordinary-run acquisition/rebuild; synthetic evidence only."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from legalpdf_translate import run_docx_formatting as adapter
from legalpdf_translate.browser_pdf_bundle import write_browser_pdf_bundle, browser_pdf_bundle_dir
from legalpdf_translate.document_structure import (PageStructure, classify_document_boundaries,
    structure_from_ordered, structure_from_tesseract_tsv)
from legalpdf_translate.formatting_support import fingerprint
from legalpdf_translate.reviewed_source import adapt_reviewed_candidate
from legalpdf_translate.source_document import source_page_identity
from legalpdf_translate.source_readiness import source_readiness_diagnostics
from legalpdf_translate.structured_artifacts import publish_structured_page
from legalpdf_translate.types import RunConfig, TargetLang
from tests.test_reviewed_source import reviewed_fixture, decision_envelope
from tests.source_readiness_fixtures import synthetic_review


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def extracted_source(source_path, *, number, provenance, native_pdf):
    """Production constructors and identity binder shape; no native extraction."""
    size = (500.0, 700.0) if native_pdf else (595.276, 841.89)
    source_hash = sha(source_path.read_bytes())
    if provenance == "digital_pdf":
        text = "Conteúdo integral fictício."
        ordered = SimpleNamespace(text=text, page_width=size[0], page_height=size[1], fragmented=False,
            tables=(), extraction_metadata={}, all_blocks=(SimpleNamespace(text=text, group="body",
                x0=20, y0=60, x1=350, y1=95, bold=False, italic=False, alignment=None),))
        source = structure_from_ordered(ordered, page_number=number, source_file_sha256=source_hash)
    else:
        tsv = "\n".join((
            "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
            "1\t1\t0\t0\t0\t0\t0\t0\t200\t300\t-1\t",
            "5\t1\t1\t1\t1\t1\t10\t60\t55\t15\t95\tConteúdo",
            "5\t1\t1\t1\t1\t2\t70\t60\t45\t15\t95\tintegral",
            "5\t1\t1\t1\t1\t3\t120\t60\t60\t15\t95\tfictício.",
        ))
        source = structure_from_tesseract_tsv(tsv, page_number=number,
            page_size=size, source_file_sha256=source_hash)
    # NewTranslationBlocks._bind_source uses these public identity/diagnostic
    # contracts for both native digital and native/browser OCR sources.
    source.metadata.update(selected_text_sha256=sha(source.text.encode()),
        source_page_identity=source_page_identity(source_path, number),
        source_coverage_status="recognized_words_only")
    source = classify_document_boundaries(source)
    source.metadata["source_readiness"] = source_readiness_diagnostics(source)
    return source


def setup(tmp_path, *, reviewer="ai_test_review", provenance="reviewed_image_source_v1",
          lang=TargetLang.FR, pages=1, selected=None, page_breaks=True, strip=True, native_pdf=False):
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"FICTIONAL PDF")
    output = tmp_path / "output"
    output.mkdir()
    run_dir = output / "source_run"
    saved = run_dir / "pages"
    saved.mkdir(parents=True)
    config = RunConfig(source_path, output, lang, page_breaks=page_breaks, strip_bidi_controls=strip)
    reviewed = reviewed_fixture(pages=pages)
    identities = deepcopy(reviewed.bindings["page_identities"])
    for identity in identities.values():
        identity["paper_size_basis"] = "a4_assumed"
    reviewed.bindings["page_identities"] = identities
    reviewed.sources = adapt_reviewed_candidate(reviewed.evidence, **reviewed.bindings)
    blobs = dict(reviewed.evidence.artifacts)
    native_pdf = native_pdf or provenance == "digital_pdf"
    if not native_pdf:
        write_browser_pdf_bundle(source_path=source_path, page_count=pages, pages=[
            {"page_number": number, "image_bytes": blobs[identities[number]["image_sha256"]],
             "mime_type": "image/png", "width_px": 200, "height_px": 300}
            for number in range(1, pages + 1)])
    identity = {"protocol": "legal_blocks_v2", "fingerprint": "b" * 64}
    selected = list(range(1, pages + 1)) if selected is None else selected
    state = SimpleNamespace(pages={}, total_pages=pages, selection_start_page=selected[0],
        selection_end_page=selected[-1], selection_page_count=len(selected), lang=lang.value,
        run_dir_abs=str(run_dir), pdf_path=str(source_path), pdf_fingerprint=sha(source_path.read_bytes()),
        protocol_identity=identity, dispatch_accounting={"retained_cost": "0.0123"},
        settings={"model": "historical-model", "page_breaks": page_breaks}, run_status="completed")
    sources = []
    for number in range(1, pages + 1):
        source = reviewed.sources[number].to_dict()
        if provenance != "reviewed_image_source_v1":
            source = extracted_source(source_path, number=number, provenance=provenance,
                                      native_pdf=native_pdf).to_dict()
        sources.append(PageStructure.from_dict(source))
        if number not in selected:
            continue
        target = deepcopy(source)
        target["blocks"][0]["text"] = {TargetLang.FR: "Contenu juridique fictif complet.",
            TargetLang.EN: "Complete fictional legal content.", TargetLang.AR: "محتوى قانوني افتراضي كامل."}[lang]
        target["translation_sha256"] = sha(target["blocks"][0]["text"].encode())
        commit = publish_structured_page(saved, source_structure=source, translated_structure=target,
            translated_text=target["blocks"][0]["text"], protocol_identity=identity,
            page_fingerprint=fingerprint(["synthetic-original-paid-page", number]))
        state.pages[str(number)] = {"status": "done", "structured_commit": commit, "original_usage": 17}
    if provenance == "reviewed_image_source_v1":
        source_review = encode(decision_envelope(reviewed))
        source_evidence = reviewed.evidence
        source_decision_evidence = b"SEPARATE FICTIONAL SOURCE DECISION"
    else:
        source_review = synthetic_review(sources).encode()
        source_evidence = None
        source_decision_evidence = b"SYNTHETIC UNIT TEST REVIEW ONLY"
    draft = adapter.begin_run_formatting_review(run_dir, config, state, reviewer_kind=reviewer)
    manifest = draft["formatting_manifest"]
    manifest["document_groups"] = [{"start_page": 1, "end_page": len(selected)}]
    for row, inputs in zip(manifest["pages"], draft["review_inputs"]):
        source, target = inputs["source_structure"], inputs["target_structure"]
        number = row["page_number"]
        raw_source, raw_target = source["blocks"][0]["text"], target["blocks"][0]["text"]
        row.update(image_size_px=[200, 300], frame={"origin": "top_left", "units": "pixel",
            "page_size_pt": [595.276, 841.89], "paper_size_basis": "a4_assumed"},
            fragments=[{"rendering_id": f"p{number:04d}_f0001", "parent_block_id": source["blocks"][0]["id"],
                "source_range": [0, len(raw_source)], "target_range": [0, len(raw_target)],
                "source_text_sha256": sha(raw_source.encode()), "target_text_sha256": sha(raw_target.encode()),
                "role": "body", "alignment": "right" if lang == TargetLang.AR else "left",
                "bold": False, "italic": False, "bbox_px": [10, 20, 180, 200],
                "review_note": "Explicit fictional source-region and independent target-range review."}],
            region_layout={"version": "reviewed_region_layout_v1", "header": [],
                "body": [{"kind": "paragraph", "fragment_id": f"p{number:04d}_f0001"}], "footer": []})
    return SimpleNamespace(run_dir=run_dir, pages_dir=saved, config=config, state=state,
        reviewer=reviewer, source_review=source_review, source_evidence=source_evidence,
        source_decision_evidence=source_decision_evidence, manifest=manifest)


def submit(case):
    return adapter.submit_run_formatting_review(case.run_dir, case.config, case.state,
        reviewer_kind=case.reviewer, source_review=case.source_review, source_evidence=case.source_evidence,
        source_review_evidence=case.source_decision_evidence,
        formatting_manifest=encode(case.manifest), review_evidence=b"Separate fictional formatting review.")


def prepare(case, revision):
    return adapter.prepare_run_docx_formatting(case.run_dir, case.config, case.state, revision_id=revision)


def originals(case):
    return {path.name: path.read_bytes() for path in case.pages_dir.iterdir()}


@pytest.mark.parametrize("lang", [TargetLang.AR, TargetLang.EN, TargetLang.FR])
def test_ordinary_rebuild_uses_run_owned_revision_and_keeps_original_evidence(tmp_path, lang):
    case = setup(tmp_path, lang=lang)
    # Unlike the private exact-bundle caller, ordinary runs legitimately carry
    # unrelated local format derivatives. They are not translation authority.
    (case.pages_dir / "page_0001.layout.json").write_text('{"ordinary":true}')
    (case.pages_dir / "page_0001.layout_eligibility.json").write_text('{"ordinary":true}')
    before, state_before = originals(case), deepcopy(vars(case.state))
    revision = submit(case)
    prepared = prepare(case, revision)
    assert prepared.status == "ready" and not prepared.notice_codes
    output = adapter.build_run_reviewed_docx(prepared, config=case.config, state=case.state,
                                             output_path=case.config.output_dir / "result.docx")
    assert output.is_file() and output.with_suffix(".source_map.json").is_file()
    receipt = json.loads(output.with_suffix(".formatting_assembly.json").read_text())
    assert receipt["provider_dispatch_count"] == 0 and receipt["layout_review_required"]
    assert originals(case) == before and vars(case.state) == state_before
    assert case.config.page_breaks and case.config.strip_bidi_controls


def test_draft_requires_explicit_source_review_regions_and_independent_target_mapping(tmp_path):
    case = setup(tmp_path)
    before = originals(case)
    draft = adapter.begin_run_formatting_review(case.run_dir, case.config, case.state, reviewer_kind="operator_review")
    assert draft["status"] == "draft" and draft["formatting_manifest"]["reviewer_kind"] == "operator_review"
    assert draft["formatting_manifest"]["document_groups"] == []
    assert draft["formatting_manifest"]["pages"][0]["fragments"] == []
    assert draft["formatting_manifest"]["pages"][0]["region_layout"] is None
    assert originals(case) == before and not (case.run_dir / "formatting_reviews").exists()


@pytest.mark.parametrize("reviewer", ["ai_test_review", "operator_review"])
def test_exclusive_review_revisions_are_owned_by_run_and_keep_reviewer_kind(tmp_path, reviewer):
    case = setup(tmp_path, reviewer=reviewer)
    first = submit(case)
    path = case.run_dir / "formatting_reviews" / first
    before = {file.relative_to(path): file.read_bytes() for file in path.rglob("*") if file.is_file()}
    second = submit(case)
    assert second != first
    assert {file.relative_to(path): file.read_bytes() for file in path.rglob("*") if file.is_file()} == before
    record = json.loads((path / "revision.json").read_text())
    assert record["region_review_kind"] == reviewer and record["status"] == "submitted"
    assert record["layout_acceptance"] == "not_evaluated"
    outcome = prepare(case, first)
    assert outcome.status == ("ready" if reviewer == "ai_test_review" else "declined")
    if reviewer == "operator_review":
        assert "reviewed_profile_unsupported_reviewer" in outcome.notice_codes


@pytest.mark.parametrize("provenance,native_pdf", [("local_ocr_tsv", False),
                                                  ("local_ocr_tsv", True), ("digital_pdf", True)])
def test_digital_and_ocr_review_submissions_preserve_real_provenance_and_decline(tmp_path, provenance, native_pdf):
    case = setup(tmp_path, provenance=provenance, reviewer="operator_review", native_pdf=native_pdf)
    revision = submit(case)
    result = prepare(case, revision)
    assert result.status == "declined"
    assert "reviewed_profile_unsupported_source_provenance" in result.notice_codes
    record = json.loads((case.run_dir / "formatting_reviews" / revision / "revision.json").read_text())
    page = record["binding"]["pages"][0]
    assert page["source_provenance"] == provenance
    assert page["source_identity"] == source_page_identity(case.config.pdf_path, 1)
    assert page["source_identity"]["source_type"] == ("pdf" if native_pdf else "browser_pdf_image")
    assert page["source_identity"]["paper_size_basis"] == ("source_pdf" if native_pdf else "a4_assumed")
    original = json.loads((case.pages_dir / "page_0001.source_structure.json").read_bytes())
    assert "reviewed_source" not in original["metadata"]
    assert original["metadata"]["source_coverage_status"] == "recognized_words_only"
    if provenance == "local_ocr_tsv":
        assert original["metadata"]["ocr_word_evidence"]["words"]
    assert record["region_review_kind"] == "operator_review"


@pytest.mark.parametrize("option,code", [("page_breaks", "reviewed_profile_requires_page_breaks"),
    ("strip_bidi_controls", "reviewed_profile_requires_bidi_stripping")])
def test_unsupported_saved_preferences_are_declined_without_silent_changes(tmp_path, option, code):
    case = setup(tmp_path, page_breaks=option != "page_breaks", strip=option != "strip_bidi_controls")
    revision = submit(case)
    result = prepare(case, revision)
    assert result.status == "declined" and code in result.notice_codes
    assert getattr(case.config, option) is False


@pytest.mark.parametrize("selected", [[1], [2]])
def test_partial_and_non_one_based_selection_are_not_relabelled_full_case(tmp_path, selected):
    case = setup(tmp_path, pages=2, selected=selected)
    revision = submit(case)
    result = prepare(case, revision)
    assert result.status == "declined" and "reviewed_profile_unsupported_selection" in result.notice_codes
    assert result.selected_pages == tuple(selected)


def test_missing_review_declines_without_writes(tmp_path):
    case = setup(tmp_path)
    before = originals(case)
    result = prepare(case, None)
    assert result.status == "declined" and result.notice_codes == ("reviewed_profile_review_missing",)
    assert not (case.run_dir / "formatting_reviews").exists() and originals(case) == before


def test_partial_output_is_explicitly_declined_even_when_all_pages_are_done(tmp_path):
    case = setup(tmp_path)
    revision = submit(case)
    result = adapter.prepare_run_docx_formatting(case.run_dir, case.config, case.state,
        revision_id=revision, partial_output=True)
    assert result.status == "declined" and "reviewed_profile_unsupported_selection" in result.notice_codes


def test_source_operator_decision_is_preserved_separately_and_declines_strict_ai_profile(tmp_path):
    case = setup(tmp_path)
    review = json.loads(case.source_review)
    review["review_kind"] = "operator_review"
    case.source_review = encode(review)
    revision = submit(case)
    result = prepare(case, revision)
    assert result.status == "declined" and "reviewed_profile_unsupported_source_reviewer" in result.notice_codes
    record = json.loads((case.run_dir / "formatting_reviews" / revision / "revision.json").read_text())
    assert record["source_review_kind"] == "operator_review" and record["region_review_kind"] == "ai_test_review"


def test_source_decision_digest_requires_retained_exact_evidence(tmp_path):
    case = setup(tmp_path)
    case.source_decision_evidence = b"Changed independently authored source decision."
    with pytest.raises(adapter.RunDocxFormattingError, match="source_decision_evidence_changed"):
        submit(case)
    assert not (case.run_dir / "formatting_reviews").exists()


def test_edited_txt_invalidates_mapping_without_rewriting_paid_structures_or_state(tmp_path):
    case = setup(tmp_path)
    revision = submit(case)
    before, state_before = originals(case), deepcopy(vars(case.state))
    text = case.pages_dir / "page_0001.txt"
    text.write_text("User edited complete text.", encoding="utf-8")
    result = prepare(case, revision)
    assert result.status == "declined"
    assert {"reviewed_profile_stale_edited_target", "reviewed_profile_stale_review"} <= set(result.notice_codes)
    assert vars(case.state) == state_before
    assert all(path.read_bytes() == before[path.name] for path in case.pages_dir.iterdir() if path != text)
    with pytest.raises(adapter.RunDocxFormattingError, match="edited_target_requires_new_mapping"):
        submit(case)


@pytest.mark.parametrize("option", ["page_breaks", "strip_bidi_controls"])
def test_changed_preferences_never_reuse_old_review(tmp_path, option):
    case = setup(tmp_path)
    revision = submit(case)
    setattr(case.config, option, False)
    result = prepare(case, revision)
    assert result.status == "declined" and "reviewed_profile_stale_review" in result.notice_codes


@pytest.mark.parametrize("kind", ["source_file", "source_raster", "source_structure", "target_structure", "commit"])
def test_changed_physical_or_committed_evidence_is_an_integrity_failure(tmp_path, kind):
    case = setup(tmp_path)
    revision = submit(case)
    path = {"source_file": case.config.pdf_path,
        "source_raster": browser_pdf_bundle_dir(case.config.pdf_path) / "pages" / "page_0001.png",
        "source_structure": case.pages_dir / "page_0001.source_structure.json",
        "target_structure": case.pages_dir / "page_0001.structure.json",
        "commit": case.pages_dir / "page_0001.commit.json"}[kind]
    path.write_bytes(path.read_bytes() + b" changed")
    with pytest.raises(ValueError):
        prepare(case, revision)


@pytest.mark.parametrize("name", ["source_review.json", "formatting.json", "candidate.json",
                                 "review_evidence.bin", "source_decision_evidence.bin"])
def test_revision_bytes_are_verified_before_rebuild(tmp_path, name):
    case = setup(tmp_path)
    revision = submit(case)
    path = case.run_dir / "formatting_reviews" / revision / name
    path.write_bytes(path.read_bytes() + b" changed")
    with pytest.raises(adapter.RunDocxFormattingError, match="revision_file_changed"):
        prepare(case, revision)


@pytest.mark.parametrize("field", ["source_file_sha256", "preferences_sha256", "target_lang", "reviewer_kind"])
def test_review_submission_requires_exact_current_manifest_identity(tmp_path, field):
    case = setup(tmp_path)
    case.manifest[field] = "changed"
    with pytest.raises(adapter.RunDocxFormattingError, match="manifest_binding_changed"):
        submit(case)
    assert not (case.run_dir / "formatting_reviews").exists()


def test_supported_review_rejects_incomplete_target_partition_before_publication(tmp_path):
    case = setup(tmp_path)
    case.manifest["pages"][0]["fragments"][0]["target_range"][1] -= 1
    with pytest.raises(ValueError):
        submit(case)
    assert not (case.run_dir / "formatting_reviews").exists()


def test_source_review_envelope_is_revalidated_not_trusted_as_a_flag(tmp_path):
    case = setup(tmp_path)
    review = json.loads(case.source_review)
    review["pages"][0]["source_fidelity"] = "not_evaluated"
    case.source_review = encode(review)
    with pytest.raises(ValueError):
        submit(case)
    assert not (case.run_dir / "formatting_reviews").exists()


@pytest.mark.parametrize("action", ["add", "edit", "remove"])
def test_ignored_ordinary_layout_sidecars_are_bound_without_becoming_translation_authority(tmp_path, action):
    case = setup(tmp_path)
    sidecar = case.pages_dir / "page_0001.layout.json"
    if action != "add":
        sidecar.write_bytes(b'{"ordinary":"original"}')
    revision = submit(case)
    if action == "remove":
        sidecar.unlink()
    else:
        sidecar.write_bytes(b'{"ordinary":"changed"}')
    result = prepare(case, revision)
    assert result.status == "declined" and "reviewed_profile_stale_review" in result.notice_codes


def test_changed_completed_page_selection_does_not_reuse_old_mapping(tmp_path):
    case = setup(tmp_path, pages=2)
    revision = submit(case)
    case.state.pages["2"]["status"] = "failed"
    result = prepare(case, revision)
    assert result.status == "declined"
    assert {"reviewed_profile_stale_review", "reviewed_profile_unsupported_selection"} <= set(result.notice_codes)


def test_rebuilt_output_cannot_be_published_over_committed_page_namespace(tmp_path):
    case = setup(tmp_path)
    preparation = prepare(case, submit(case))
    before = originals(case)
    with pytest.raises(adapter.RunDocxFormattingError, match="invalid_output_path"):
        adapter.build_run_reviewed_docx(preparation, config=case.config, state=case.state,
                                        output_path=case.pages_dir / "result.docx")
    assert originals(case) == before


def test_prepared_rebuild_is_invalidated_before_writer_if_text_changes(tmp_path, monkeypatch):
    case = setup(tmp_path)
    preparation = prepare(case, submit(case))
    (case.pages_dir / "page_0001.txt").write_text("User edit.")
    import legalpdf_translate.reviewed_formatting_writer as writer
    monkeypatch.setattr(writer, "build_reviewed_docx", lambda _: pytest.fail("Stale mapping cannot reach writer"))
    with pytest.raises(adapter.RunDocxFormattingError, match="preparation_changed"):
        adapter.build_run_reviewed_docx(preparation, config=case.config, state=case.state,
                                        output_path=case.config.output_dir / "result.docx")
    assert not (case.config.output_dir / "result.docx").exists()


def test_actual_writer_output_is_independently_checked_and_changed_source_prevents_publish(tmp_path, monkeypatch):
    case = setup(tmp_path)
    preparation = prepare(case, submit(case))
    import legalpdf_translate.reviewed_formatting_writer as writer
    original = writer.build_reviewed_docx
    def mutate(projection):
        artifact = original(projection)
        (case.pages_dir / "page_0001.txt").write_text("Concurrent user edit.")
        return artifact
    monkeypatch.setattr(writer, "build_reviewed_docx", mutate)
    with pytest.raises(adapter.RunDocxFormattingError, match="inputs_changed_during_assembly"):
        adapter.build_run_reviewed_docx(preparation, config=case.config, state=case.state,
                                        output_path=case.config.output_dir / "result.docx")
    assert not (case.config.output_dir / "result.docx").exists()


def test_writer_output_cannot_bypass_independent_docx_and_source_map_validation(tmp_path, monkeypatch):
    case = setup(tmp_path)
    preparation = prepare(case, submit(case))
    import legalpdf_translate.reviewed_formatting_writer as writer
    original = writer.build_reviewed_docx
    def corrupt(projection):
        artifact = original(projection)
        return SimpleNamespace(docx_bytes=artifact.docx_bytes + b"changed",
                               source_map_bytes=artifact.source_map_bytes)
    monkeypatch.setattr(writer, "build_reviewed_docx", corrupt)
    with pytest.raises(ValueError):
        adapter.build_run_reviewed_docx(preparation, config=case.config, state=case.state,
                                        output_path=case.config.output_dir / "result.docx")
    assert not (case.config.output_dir / "result.docx").exists()


def test_existing_docx_is_not_overwritten(tmp_path):
    case = setup(tmp_path)
    preparation = prepare(case, submit(case))
    requested = case.config.output_dir / "result.docx"
    requested.write_bytes(b"Prior user-owned DOCX sentinel")
    result = adapter.build_run_reviewed_docx(preparation, config=case.config, state=case.state, output_path=requested)
    assert result != requested and requested.read_bytes() == b"Prior user-owned DOCX sentinel"


@pytest.mark.parametrize("revision", ["../outside", "", "A" * 32, [], None])
def test_malformed_revision_id_cannot_read_arbitrary_paths(tmp_path, revision):
    case = setup(tmp_path)
    if revision is None:
        assert prepare(case, revision).status == "declined"
    else:
        with pytest.raises(adapter.RunDocxFormattingError, match="invalid_revision_id"):
            prepare(case, revision)
