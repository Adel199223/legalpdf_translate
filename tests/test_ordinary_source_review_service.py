"""Public actions -> retained local evidence -> context -> real ordinary commits.

The local recognizer and SDK are synthetic boundaries; no fixture injects a
candidate, acceptance envelope, structured commit, provider or native process.
"""
from copy import deepcopy
from dataclasses import replace
import builtins
import json
from types import SimpleNamespace
from pathlib import Path
import threading

import pytest

from legalpdf_translate import ocr_engine as ocr, workflow as workflow_module
from legalpdf_translate.browser_pdf_bundle import write_browser_pdf_bundle
from legalpdf_translate.checkpoint import load_run_state, settings_fingerprint
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.ordinary_source_review_service import (
    OrdinarySourceReviewService, SourcePageDecision, SourceReviewAction, SourceReviewFinding,
    SourceReviewServiceError,
)
from legalpdf_translate.types import ImageMode, OcrMode, OcrEnginePolicy, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_source_review_candidate import png


RAW_TXT = b"Processo 121/26\r\nArtigo 42\r\n"
RAW_TSV = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "1\t1\t0\t0\t0\t0\t0\t0\t200\t300\t-1\t\n"
    "5\t1\t1\t1\t1\t1\t10\t10\t40\t20\t95\tProcesso\n"
    "5\t1\t1\t1\t1\t2\t60\t10\t40\t20\t95\t121/26\n"
    "5\t1\t2\t1\t1\t1\t10\t40\t40\t20\t95\tArtigo\n"
    "5\t1\t2\t1\t1\t2\t60\t40\t40\t20\t95\t42\n").encode()


@pytest.fixture(autouse=True)
def local_only(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    def forbidden(*_a, **_kw):
        pytest.fail("Synthetic source review must not invoke providers, credentials or native extraction")
    for name in ("run_translation_auth_test", "extract_ordered_page_text", "resolve_openai_key_with_source"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    monkeypatch.setattr(ocr, "build_ocr_engine", forbidden)
    monkeypatch.setattr(ocr.subprocess, "run", forbidden)
    monkeypatch.setattr(ocr, "resolve_ocr_api_key", forbidden)
    monkeypatch.setattr(ocr, "which", lambda _: "synthetic-tesseract")
    monkeypatch.setattr(ocr, "_text_quality_score", lambda _: 0.99)


def local_pass(monkeypatch, *, retain=True):
    calls = []
    def run_pass(self, *, input_path, pass_spec, preserve_structure=False):
        assert preserve_structure
        calls.append(input_path)
        assert input_path.read_bytes() == png()
        if retain:
            base = input_path.parent / pass_spec.name
            base.with_suffix(".txt").write_bytes(RAW_TXT)
            base.with_suffix(".tsv").write_bytes(RAW_TSV)
        return 0, RAW_TXT.decode(), "", RAW_TSV.decode()
    monkeypatch.setattr(ocr.LocalTesseractEngine, "_run_pass", run_pass)
    return calls


def config_case(tmp_path, *, count=1):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"Fictional source acquisition document")
    write_browser_pdf_bundle(source_path=source, page_count=count,
        pages=[{"page_number": n, "mime_type": "image/png", "width_px": 200,
                "height_px": 300, "image_bytes": png()} for n in range(1, count + 1)])
    output = tmp_path / "output"
    output.mkdir()
    return RunConfig(source, output, TargetLang.EN, ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.LOCAL_THEN_API, workers=1, resume=False,
        image_mode=ImageMode.OFF, page_breaks=False)


def explicit_decision(page, *, complete=True):
    actions = []
    for index, block in enumerate(page["baseline_blocks"], 1):
        boxes = [w["bbox_px"] for w in page["word_evidence"]["words"] if w["block_id"] == block["id"]]
        region = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        actions.append(SourceReviewAction(f"a{index}", "retain", (block["id"],), block["text"],
            region, "Explicit fictional operator comparison with the displayed image."))
    return SourcePageDecision(tuple(actions), tuple(a.id for a in actions), complete, complete,
        "start", "Explicit fictional document boundary check.", (), "Fictional operator")


def accepted(service):
    view = service.prepare()
    assert view["status"] == "draft"
    draft_id = view["draft_id"]
    for page in view["pages"]:
        view = service.save_page(draft_id, expected_generation=view["generation"],
            page_number=page["page_number"], decision=explicit_decision(page))
    return service.submit(draft_id, expected_generation=view["generation"],
        reviewer="Fictional final operator", accept_source=True)


def sdk_client(calls):
    def create(**request):
        calls.append(request)
        prompt, _ = json.JSONDecoder().raw_decode(request["input"][0]["content"][0]["text"])
        blocks = [{"id": row["id"], "text": "Case 121/26" if "Processo" in row["text"] else "Article 42"}
                  for row in prompt["blocks"]]
        return SimpleNamespace(id=f"synthetic-{len(calls)}", status="completed", model=request["model"],
            output_text=json.dumps({"blocks": blocks}), output=[],
            usage={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20})
    sdk = SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create))
    return OpenAIResponsesClient(sdk_client=sdk, pre_call_jitter_seconds=0)


def test_raw_local_bytes_survive_cleanup_only_when_explicitly_requested(monkeypatch):
    calls = local_pass(monkeypatch)
    engine = ocr.LocalTesseractEngine()
    normal = engine.ocr_image(png(), preserve_structure=True)
    retained = engine.ocr_image(png(), retain_local_evidence=True)
    assert normal.text == retained.text and normal.selected_pass == retained.selected_pass
    assert normal.local_evidence is None
    assert retained.local_evidence.text_bytes == RAW_TXT
    assert retained.local_evidence.tsv_bytes == RAW_TSV
    assert json.loads(retained.local_evidence.structure_bytes) == retained.structure
    assert all(not path.exists() for path in calls)
    assert normal.structure_metadata == retained.structure_metadata
    assert "Processo" not in repr(retained.local_evidence)
    json.dumps(retained.structure_metadata)


def test_public_operator_actions_reach_real_workflow_commits_and_resume(tmp_path, monkeypatch, capsys):
    local_calls = local_pass(monkeypatch)
    config = config_case(tmp_path, count=2)
    before = deepcopy(settings_fingerprint(config))
    service = OrdinarySourceReviewService(config)
    original_import = builtins.__import__
    def public_only(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith(("tooling", "acceptance_", "legalpdf_translate.acceptance_")):
            pytest.fail("Public source operation cannot import private authority/tooling")
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", public_only)
    submitted = accepted(service)
    context = service.load_context(submitted["revision_id"])
    assert context.reviewer_kind == "operator_review"
    assert RAW_TXT in dict(context.evidence.artifacts).values()
    assert RAW_TSV in dict(context.evidence.artifacts).values()
    assert len(local_calls) == 2 and all(not p.exists() for p in local_calls)
    calls = []
    workflow = TranslationWorkflow(client=sdk_client(calls), gui_settings={}, reviewed_source_context=context)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(calls) == 2 and len(local_calls) == 2
    state = load_run_state(result.run_dir / "run_state.json")
    assert state.settings["ordinary_source_review"] == context.identity
    assert state.settings["page_breaks"] is False
    for n in (1, 2):
        assert state.pages[str(n)]["structured_commit"]
        source = json.loads((result.run_dir / f"pages/page_{n:04d}.source_structure.json").read_bytes())
        target = json.loads((result.run_dir / f"pages/page_{n:04d}.structure.json").read_bytes())
        assert source["metadata"]["reviewed_source"]["review_kind"] == "operator_review"
        assert target["metadata"]["ordinary_source_review"] == context.identity
    accounting = json.loads(workflow._dispatch_accounting.journal_path.read_bytes())
    assert len([e for e in accounting["events"] if e["event"] == "begin"]) == 2
    assert len([e for e in accounting["events"] if e["event"] == "finish"]) == 2
    assert not (result.run_dir / "acceptance_private").exists()
    abandoned = json.loads((result.run_dir / "run_state.json").read_bytes())
    abandoned["run_status"] = "running"
    abandoned["finished_at"] = ""
    (result.run_dir / "run_state.json").write_text(json.dumps(abandoned), encoding="utf-8")
    restored = OrdinarySourceReviewService(replace(config, resume=True)).load_context(submitted["revision_id"])
    resumed = TranslationWorkflow(client=sdk_client(calls), gui_settings={}, reviewed_source_context=restored).run(replace(config, resume=True))
    assert resumed.success and len(calls) == 2 and len(local_calls) == 2
    assert settings_fingerprint(config) == before and config.page_breaks is False
    from legalpdf_translate import formatting_review_cli as cli
    checkpoint_before = (result.run_dir / "run_state.json").read_bytes()
    code = cli.main(["draft", "--run", str(result.run_dir), "--profile", "ordinary_operator_browser_v1",
        "--reviewer-kind", "operator_review", "--output", str(tmp_path / "formatting-packet")])
    output = capsys.readouterr()
    response = json.loads(output.out or output.err)
    assert code == 0 and response["status"] == "draft"
    assert "reviewed_profile_requires_page_breaks" in response["notice_codes"]
    assert (result.run_dir / "run_state.json").read_bytes() == checkpoint_before


@pytest.mark.parametrize("change,code", [
    ({"ocr_mode": OcrMode.OFF}, "ocr_disabled"),
    ({"ocr_engine": OcrEnginePolicy.API}, "local_baseline_unavailable"),
    ({"keep_intermediates": False}, "retained_evidence_required"),
    ({"start_page": 2}, "full_selection_required"),
])
def test_saved_policy_declines_without_ocr_fallback_or_preference_changes(tmp_path, monkeypatch, change, code):
    calls = local_pass(monkeypatch)
    config = replace(config_case(tmp_path, count=2), **change)
    before = settings_fingerprint(config)
    service = OrdinarySourceReviewService(config)
    result = service.prepare()
    assert result == {"status": "declined", "notice_codes": ["source_review_" + code]}
    assert calls == [] and settings_fingerprint(config) == before
    assert not (service.run_dir / "source_reviews").exists()


def test_missing_real_renderer_files_declines_instead_of_reconstructing_tsv(tmp_path, monkeypatch):
    calls = local_pass(monkeypatch, retain=False)
    service = OrdinarySourceReviewService(config_case(tmp_path))
    result = service.prepare()
    assert result["status"] == "declined" and calls
    assert result["notice_codes"] == ["source_review_local_evidence_unavailable"]
    assert not (service.run_dir / "source_reviews").exists()


def test_no_preselected_approval_and_stale_or_submitted_generation_is_immutable(tmp_path, monkeypatch):
    local_pass(monkeypatch)
    service = OrdinarySourceReviewService(config_case(tmp_path))
    first = service.prepare()
    assert all(page["decision"] is None for page in first["pages"])
    with pytest.raises(SourceReviewServiceError, match="review_incomplete"):
        service.submit(first["draft_id"], expected_generation=1, reviewer="operator", accept_source=True)
    decision = explicit_decision(first["pages"][0], complete=False)
    second = service.save_page(first["draft_id"], expected_generation=1, page_number=1, decision=decision)
    with pytest.raises(SourceReviewServiceError):
        service.submit(first["draft_id"], expected_generation=2, reviewer="operator", accept_source=True)
    with pytest.raises(SourceReviewServiceError, match="stale_generation"):
        service.save_page(first["draft_id"], expected_generation=1, page_number=1, decision=decision)
    third = service.save_page(first["draft_id"], expected_generation=2, page_number=1,
        decision=replace(decision, full_page_review_completed=True, reading_order_reviewed=True))
    with pytest.raises(SourceReviewServiceError, match="explicit_acceptance_required"):
        service.submit(first["draft_id"], expected_generation=3, reviewer="operator", accept_source=False)
    revision = service.submit(first["draft_id"], expected_generation=3, reviewer="operator", accept_source=True)
    with pytest.raises(SourceReviewServiceError, match="draft_submitted"):
        service.save_page(first["draft_id"], expected_generation=3, page_number=1, decision=decision)
    assert service.read(first["draft_id"])["submitted"] is True
    assert service.load_context(revision["revision_id"])


@pytest.mark.parametrize("mutation", ["object", "source", "generation", "settings"])
def test_submit_and_load_recheck_owned_physical_evidence(tmp_path, monkeypatch, mutation):
    local_pass(monkeypatch)
    config = config_case(tmp_path)
    service = OrdinarySourceReviewService(config)
    revision = accepted(service)
    context = service.load_context(revision["revision_id"])
    if mutation == "object":
        key = next(key for key, raw in context.evidence.artifacts if raw == RAW_TXT)
        (service.run_dir / "source_reviews/objects" / key).write_bytes(b"changed")
    elif mutation == "source":
        config.pdf_path.write_bytes(b"changed")
    elif mutation == "generation":
        path = service.run_dir / "source_reviews/drafts" / revision["draft_id"] / "000002.json"
        value = json.loads(path.read_bytes())
        value["generation"] = 3
        (path.parent / "000003.json").write_text(json.dumps(value), encoding="utf-8")
    else:
        service = OrdinarySourceReviewService(replace(config, page_breaks=True))
    with pytest.raises(SourceReviewServiceError):
        service.load_context(revision["revision_id"])


def test_partial_decisions_do_not_publish_and_path_ids_cannot_escape(tmp_path, monkeypatch):
    local_pass(monkeypatch)
    service = OrdinarySourceReviewService(config_case(tmp_path, count=2))
    view = service.prepare()
    view = service.save_page(view["draft_id"], expected_generation=1, page_number=1,
        decision=explicit_decision(view["pages"][0]))
    with pytest.raises(SourceReviewServiceError, match="review_incomplete"):
        service.submit(view["draft_id"], expected_generation=2, reviewer="operator", accept_source=True)
    assert not list((service.run_dir / "source_reviews/revisions").iterdir())
    with pytest.raises(SourceReviewServiceError, match="invalid_id"):
        service.load_context("../../outside")


def test_production_candidate_builder_preserves_existing_tooling_contract():
    from legalpdf_translate.source_review_candidate import build_candidate as production
    from tooling.source_review_candidate import build_candidate as prior
    from tests.test_source_review_candidate import fixture, encode, digest
    manifest, _, artifacts = fixture()
    raw = encode(manifest)
    kwargs = dict(expected_manifest_sha256=digest(raw), document_sha256=manifest["document_sha256"],
        page_numbers=(1,), artifacts=artifacts, require_complete=True)
    assert production(raw, **kwargs) == prior(raw, **kwargs)


def test_real_workflow_guard_allows_coherent_atomic_progress_replacement(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_source_review_service as module
    local_pass(monkeypatch)
    config = config_case(tmp_path, count=2)
    service = OrdinarySourceReviewService(config)
    revision = accepted(service)
    context = service.load_context(revision["revision_id"])
    local = threading.local()
    original_check = service._check_checkpoint
    original_open = Path.open
    replaced = []
    checkpoint = service.run_dir / "run_state.json"
    def check(**kwargs):
        local.checking = True
        try:
            return original_check(**kwargs)
        finally:
            local.checking = False
    class ProgressRead:
        def __init__(self, stream):
            self.stream = stream
        def __enter__(self):
            return self.stream
        def __exit__(self, *args):
            self.stream.close()
            if not replaced:
                # Deterministically interleave legitimate atomic progress after
                # the coherent read closes, as another completion thread can.
                with original_open(checkpoint, "rb") as stream:
                    payload = json.load(stream)
                payload["updated_at"] = "2026-09-16T00:00:00+00:00"
                temp = checkpoint.with_suffix(".progress-test")
                with original_open(temp, "wb") as stream:
                    stream.write(json.dumps(payload).encode())
                temp.replace(checkpoint)
                replaced.append(True)
    def open_path(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        if path == checkpoint and args == ("rb",) and getattr(local, "checking", False):
            return ProgressRead(stream)
        return stream
    monkeypatch.setattr(service, "_check_checkpoint", check)
    monkeypatch.setattr(Path, "open", open_path)
    calls = []
    result = TranslationWorkflow(client=sdk_client(calls), gui_settings={}, reviewed_source_context=context).run(config)
    assert result.success and len(calls) == 2 and replaced == [True]


def test_repeated_images_count_toward_incremental_acquisition_limit(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_source_review_service as module
    local_calls = local_pass(monkeypatch)
    service = OrdinarySourceReviewService(config_case(tmp_path, count=3))
    # All page rasters are byte-identical. A deduplicated final sum must not
    # authorize unbounded per-page reads/allocations before the final check.
    from legalpdf_translate.browser_pdf_bundle import browser_pdf_bundle_manifest_path
    fixed = len(service._config.pdf_path.read_bytes()) + len(browser_pdf_bundle_manifest_path(service._config.pdf_path).read_bytes())
    monkeypatch.setattr(module, "_MAX_TOTAL", fixed + 2 * len(png()))
    with pytest.raises(SourceReviewServiceError, match="evidence_too_large"):
        service.prepare()
    assert local_calls == [] and not (service.run_dir / "source_reviews").exists()


@pytest.mark.parametrize("lang,expected_passes", [(TargetLang.EN, 2), (TargetLang.FR, 2), (TargetLang.AR, 3)])
def test_acquisition_preserves_existing_target_derived_local_pass_profile(tmp_path, monkeypatch, lang, expected_passes):
    local_pass(monkeypatch)
    run = ocr.LocalTesseractEngine._run_pass
    passes = []
    def pass_with_profile(self, **kwargs):
        passes.append(kwargs["pass_spec"])
        return run(self, **kwargs)
    monkeypatch.setattr(ocr.LocalTesseractEngine, "_run_pass", pass_with_profile)
    monkeypatch.setattr(ocr, "_text_quality_score", lambda _: 0.9 if len(passes) == 3 else 0.6)
    config = replace(config_case(tmp_path), target_lang=lang)
    view = OrdinarySourceReviewService(config).prepare()
    assert view["status"] == "draft" and len(passes) == expected_passes
    assert [p.lang for p in passes[:2]] == ["por+eng+fra", "por+eng+fra"]
    if lang == TargetLang.AR:
        assert passes[-1].lang == "ara+eng" and view["pages"][0]["selected_pass"] == passes[-1].name


def test_context_loading_cannot_enter_an_actively_owned_run(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from legalpdf_translate.run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
    local_pass(monkeypatch)
    service = OrdinarySourceReviewService(config_case(tmp_path))
    revision = accepted(service)
    with run_workspace_slot(service.run_dir), ThreadPoolExecutor(max_workers=1) as pool:
        operation = pool.submit(service.load_context, revision["revision_id"])
        with pytest.raises(RunWorkspaceBusy):
            operation.result()


def submission_case(tmp_path, monkeypatch):
    """Actual acquisition and explicit actions, with no injected accepted proof."""
    local_pass(monkeypatch)
    config = config_case(tmp_path)
    service = OrdinarySourceReviewService(config)
    draft = service.prepare()
    draft = service.save_page(draft["draft_id"], expected_generation=draft["generation"], page_number=1,
        decision=explicit_decision(draft["pages"][0]))
    arguments = {"expected_generation": draft["generation"], "reviewer": "Fictional final operator",
                 "accept_source": True}
    return config, service, draft, arguments


def publication_files(service):
    root = service.run_dir / "source_reviews"
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("failure", ["intent", "receipt", "revision", "response"])
def test_exact_submission_recovers_each_publication_boundary_after_restart(tmp_path, monkeypatch, failure):
    from legalpdf_translate import ordinary_source_review_service as module
    config, service, draft, arguments = submission_case(tmp_path, monkeypatch)
    original_publish, original_finish = module._publish, service._finish_submission
    fired = []
    def publish(path, raw):
        original_publish(path, raw)
        selected = ((failure == "intent" and path.name == "submit_intent.json")
                    or (failure == "receipt" and path.name == "submitted.json")
                    or (failure == "revision" and path.parent.name == "revisions"))
        if selected and not fired:
            fired.append(path)
            raise OSError("Fictional private publication interruption")
    def finish(*args):
        result = original_finish(*args)
        fired.append("response")
        raise OSError("Fictional response lost after completed publication")
    monkeypatch.setattr(module, "_publish", publish)
    if failure == "response":
        monkeypatch.setattr(service, "_finish_submission", finish)
    with pytest.raises(SourceReviewServiceError, match="operation_failed"):
        service.submit(draft["draft_id"], **arguments)
    assert len(fired) == 1
    directory = service.run_dir / "source_reviews/drafts" / draft["draft_id"]
    intent_raw = (directory / "submit_intent.json").read_bytes()
    intent = json.loads(intent_raw)
    selected_id = intent["revision_id"]
    assert intent["generation"] == draft["generation"]
    with pytest.raises(SourceReviewServiceError, match="draft_submission_pending|draft_submitted"):
        service.save_page(draft["draft_id"], expected_generation=draft["generation"], page_number=1,
            decision=explicit_decision(draft["pages"][0]))
    monkeypatch.setattr(module, "_publish", original_publish)
    restarted = OrdinarySourceReviewService(config)
    before_read = publication_files(restarted)
    recovered_view = restarted.read(draft["draft_id"])
    assert publication_files(restarted) == before_read  # Read never completes a pending acceptance.
    assert recovered_view["submission"] == {"status": "completed" if failure in {"revision", "response"} else "pending",
        "revision_id": selected_id, "generation": draft["generation"], "reviewer": arguments["reviewer"]}
    assert recovered_view["submitted"] is (failure in {"revision", "response"})
    result = restarted.submit(draft["draft_id"], **arguments)
    assert result["revision_id"] == selected_id
    assert (directory / "submit_intent.json").read_bytes() == intent_raw
    completed_files = publication_files(restarted)
    assert len(list((service.run_dir / "source_reviews/revisions").glob("*.json"))) == 1
    assert restarted.submit(draft["draft_id"], **arguments) == result
    assert publication_files(restarted) == completed_files
    context = restarted.load_context(selected_id)
    assert context.identity == intent["revision"]["context_identity"]
    assert json.loads(context.decision_evidence)["recorded_at"] == json.loads(
        (service.run_dir / "source_reviews/objects" / intent["revision"]["decision"]).read_bytes())["recorded_at"]
    if failure == "receipt":
        calls = []
        workflow = TranslationWorkflow(client=sdk_client(calls), gui_settings={}, reviewed_source_context=context)
        summary = workflow.run(config)
        assert summary.success and len(calls) == 1
        state = load_run_state(summary.run_dir / "run_state.json")
        assert state.settings["ordinary_source_review"] == context.identity
        assert state.pages["1"]["structured_commit"]
        accounting = json.loads(workflow._dispatch_accounting.journal_path.read_bytes())
        assert len([row for row in accounting["events"] if row["event"] == "begin"]) == 1
        assert len([row for row in accounting["events"] if row["event"] == "finish"]) == 1


@pytest.mark.parametrize("changed", ["reviewer", "generation", "bool_generation", "acceptance"])
def test_submission_retry_requires_same_explicit_acceptance(tmp_path, monkeypatch, changed):
    from legalpdf_translate import ordinary_source_review_service as module
    _, service, draft, arguments = submission_case(tmp_path, monkeypatch)
    original = module._publish
    def fail_after_intent(path, raw):
        original(path, raw)
        if path.name == "submit_intent.json":
            raise OSError("Fictional interruption")
    monkeypatch.setattr(module, "_publish", fail_after_intent)
    with pytest.raises(SourceReviewServiceError):
        service.submit(draft["draft_id"], **arguments)
    monkeypatch.setattr(module, "_publish", original)
    retry = dict(arguments)
    if changed == "reviewer":
        retry["reviewer"] = "A different fictional reviewer"
    elif changed == "generation":
        retry["expected_generation"] += 1
    elif changed == "bool_generation":
        retry["expected_generation"] = True
    else:
        retry["accept_source"] = False
    before = publication_files(service)
    with pytest.raises(SourceReviewServiceError):
        service.submit(draft["draft_id"], **retry)
    assert publication_files(service) == before
    assert not list((service.run_dir / "source_reviews/revisions").iterdir())


@pytest.mark.parametrize("changed", ["reviewer", "generation_bool", "revision_generation_bool", "owner", "revision_hash", "missing_intent"])
def test_completed_intent_tamper_blocks_read_resubmit_and_context(tmp_path, monkeypatch, changed):
    from legalpdf_translate.source_review_candidate import canonical_json
    import hashlib
    _, service, draft, arguments = submission_case(tmp_path, monkeypatch)
    result = service.submit(draft["draft_id"], **arguments)
    path = service.run_dir / "source_reviews/drafts" / draft["draft_id"] / "submit_intent.json"
    intent = json.loads(path.read_bytes())
    if changed == "reviewer":
        intent["reviewer"] = "Different reviewer"
    elif changed == "generation_bool":
        intent["generation"] = True
    elif changed == "revision_generation_bool":
        intent["revision"]["generation"] = True
        intent["revision_sha256"] = hashlib.sha256(canonical_json(intent["revision"])).hexdigest()
    elif changed == "owner":
        intent["owner"]["target_lang"] = "FR"
    elif changed == "revision_hash":
        intent["revision_sha256"] = "0" * 64
    if changed == "missing_intent":
        path.unlink()  # Only this test-owned temporary record is removed.
    else:
        path.write_bytes(canonical_json(intent))
    before = publication_files(service)
    for action in (lambda: service.read(draft["draft_id"]),
                   lambda: service.submit(draft["draft_id"], **arguments),
                   lambda: service.load_context(result["revision_id"])):
        with pytest.raises(SourceReviewServiceError):
            action()
    assert publication_files(service) == before


@pytest.mark.parametrize("changed", ["source", "object", "receipt", "revision"])
def test_pending_submission_never_overwrites_changed_evidence_or_publications(tmp_path, monkeypatch, changed):
    from legalpdf_translate import ordinary_source_review_service as module
    config, service, draft, arguments = submission_case(tmp_path, monkeypatch)
    original = module._publish
    def interrupt(path, raw):
        original(path, raw)
        if path.name == "submit_intent.json":
            raise OSError("Fictional interruption")
    monkeypatch.setattr(module, "_publish", interrupt)
    with pytest.raises(SourceReviewServiceError):
        service.submit(draft["draft_id"], **arguments)
    monkeypatch.setattr(module, "_publish", original)
    directory = service.run_dir / "source_reviews/drafts" / draft["draft_id"]
    intent = json.loads((directory / "submit_intent.json").read_bytes())
    if changed == "source":
        config.pdf_path.write_bytes(b"Fictional source mutation")
    elif changed == "object":
        key = intent["revision"]["decision"]
        (service.run_dir / "source_reviews/objects" / key).write_bytes(b"Fictional evidence mutation")
    elif changed == "receipt":
        (directory / "submitted.json").write_bytes(b"Existing conflicting record")
    else:
        (service.run_dir / "source_reviews/revisions" / (intent["revision_id"] + ".json")).write_bytes(b"Existing conflicting record")
    before = publication_files(service)
    with pytest.raises(SourceReviewServiceError):
        service.read(draft["draft_id"])
    with pytest.raises(SourceReviewServiceError):
        service.submit(draft["draft_id"], **arguments)
    assert publication_files(service) == before


def test_atomic_submission_publication_never_replaces_a_racing_target(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_source_review_service as module
    from legalpdf_translate.run_workspace_lock import run_workspace_slot
    # Exercise the actual trusted helper; insert a target after the wrapper's
    # initial check. The platform's exclusive final operation must preserve it.
    run = tmp_path / "run"
    run.mkdir()
    target = run / "intent.json"
    actual = module._publish_file_exclusive
    def race(path, raw):
        path.write_bytes(b"Existing user evidence")
        actual(path, raw)
    monkeypatch.setattr(module, "_publish_file_exclusive", race)
    with run_workspace_slot(run):
        with pytest.raises(FileExistsError):
            module._publish(target, b"Replacement is prohibited")
    assert target.read_bytes() == b"Existing user evidence"
    assert not list(run.glob(".structured-*"))


def test_legacy_completed_storage_remains_readable_but_orphan_is_not_reconstructed(tmp_path, monkeypatch):
    from legalpdf_translate.source_review_candidate import canonical_json
    import hashlib
    _, service, draft, arguments = submission_case(tmp_path, monkeypatch)
    result = service.submit(draft["draft_id"], **arguments)
    directory = service.run_dir / "source_reviews/drafts" / draft["draft_id"]
    revision = service.run_dir / "source_reviews/revisions" / (result["revision_id"] + ".json")
    marker = json.loads(revision.read_bytes())
    # Reproduce only the older storage shape from this genuinely acquired and
    # explicitly reviewed submission; no accepted source/commit is fabricated.
    marker.pop("submission_version")
    raw = canonical_json(marker)
    revision.write_bytes(raw)
    (directory / "submit_intent.json").unlink()
    (directory / "submitted.json").write_bytes(canonical_json({"revision_id": result["revision_id"],
        "generation": draft["generation"], "revision_sha256": hashlib.sha256(raw).hexdigest()}))
    before = publication_files(service)
    assert service.read(draft["draft_id"])["submission"]["status"] == "completed"
    assert service.submit(draft["draft_id"], **arguments) == result
    assert service.load_context(result["revision_id"])
    assert publication_files(service) == before
    revision.unlink()
    before = publication_files(service)
    for action in (lambda: service.read(draft["draft_id"]), lambda: service.submit(draft["draft_id"], **arguments)):
        with pytest.raises(SourceReviewServiceError, match="legacy_submission_incomplete"):
            action()
    assert publication_files(service) == before


@pytest.mark.parametrize("boundary", ["before_intent", "after_intent", "between_records", "after_records"])
@pytest.mark.parametrize("mutation", ["selected_file", "newer_generation"])
def test_publication_rereads_exact_selected_draft_at_every_boundary(tmp_path, monkeypatch, boundary, mutation):
    from legalpdf_translate import ordinary_source_review_service as module
    from legalpdf_translate.source_review_candidate import canonical_json
    _, service, draft, arguments = submission_case(tmp_path, monkeypatch)
    directory = service.run_dir / "source_reviews/drafts" / draft["draft_id"]
    selected = directory / f"{draft['generation']:06d}.json"
    original_publish, original_validate = module._publish, service._validate_submission
    changed, accepted_publications = [], []
    def mutate():
        if changed:
            return
        value = json.loads(selected.read_bytes())
        if mutation == "selected_file":
            value["fictional_interleaved_change"] = True
            selected.write_bytes(canonical_json(value))
        else:
            value["generation"] += 1
            (directory / f"{value['generation']:06d}.json").write_bytes(canonical_json(value))
        changed.append(mutation)
    def validate(*args, **kwargs):
        result = original_validate(*args, **kwargs)
        if boundary == "before_intent":
            mutate()
        return result
    def publish(path, raw):
        original_publish(path, raw)
        if path.name == "submitted.json" or path.parent.name == "revisions":
            accepted_publications.append(path)
        if ((boundary == "after_intent" and path.name == "submit_intent.json")
                or (boundary == "between_records" and path.name == "submitted.json")
                or (boundary == "after_records" and path.parent.name == "revisions")):
            mutate()
    monkeypatch.setattr(service, "_validate_submission", validate)
    monkeypatch.setattr(module, "_publish", publish)
    with pytest.raises(SourceReviewServiceError, match="submission_draft_changed"):
        service.submit(draft["draft_id"], **arguments)
    assert changed == [mutation]
    expected_count = {"before_intent": 0, "after_intent": 0, "between_records": 1, "after_records": 2}[boundary]
    assert len(accepted_publications) == expected_count
    assert (directory / "submit_intent.json").exists() is (boundary != "before_intent")
    # A mutation after the last write is reported as failure, never as a
    # successful acceptance. Every earlier boundary blocks remaining writes.
    if boundary == "after_records":
        revision_id = json.loads((directory / "submit_intent.json").read_bytes())["revision_id"]
        with pytest.raises(SourceReviewServiceError):
            service.load_context(revision_id)
