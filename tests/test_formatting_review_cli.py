"""Public CLI tests with fictional local evidence and no executable subprocesses."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json

import pytest

from legalpdf_translate import formatting_review_cli as cli
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.checkpoint import build_run_paths, load_run_state, new_run_state, save_run_state_atomic
from legalpdf_translate.run_docx_formatting import OPERATOR_REVIEW_PROFILE, STRICT_REVIEW_PROFILE
from legalpdf_translate.run_workspace_lock import run_workspace_slot
from tests import test_run_docx_formatting as ordinary
from tests.test_operator_run_docx_formatting import operator_case

encode = ordinary.encode


def forbidden(*args, **kwargs):
    pytest.fail("Formatting review CLI cannot invoke provider/auth/OCR/native/ambient preferences")


@pytest.fixture(autouse=True)
def no_provider_or_native(monkeypatch):
    class ForbiddenClient:
        def __init__(self, *args, **kwargs):
            forbidden()
    # Keep a type: TranslationWorkflow checks isinstance even when no client is supplied.
    monkeypatch.setattr(workflow_module, "OpenAIResponsesClient", ForbiddenClient)
    for name in ("extract_ordered_page_text", "build_ocr_engine", "run_translation_auth_test",
                 "resolve_openai_key_with_source", "load_environment", "load_gui_settings"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    import legalpdf_translate.layout_integration as layout
    monkeypatch.setattr(layout, "_render_source", forbidden)


def saved_case(tmp_path, monkeypatch, *, operator=True, **options):
    case = operator_case(tmp_path, monkeypatch, **options) if operator else ordinary.setup(tmp_path, **options)
    paths = build_run_paths(case.config.output_dir, case.config.pdf_path, case.config.target_lang)
    case.run_dir.rename(paths.run_dir)
    case.run_dir, case.pages_dir, case.paths = paths.run_dir, paths.pages_dir, paths
    old = case.state
    selected = sorted(int(key) for key in old.pages)
    state = new_run_state(config=case.config, paths=paths, pdf_fingerprint=old.pdf_fingerprint,
        context_hash="NO_CONTEXT", total_pages=old.total_pages, selected_pages=selected,
        protocol_identity=old.protocol_identity)
    state.pages = deepcopy(old.pages)
    state.done_count, state.failed_count, state.pending_count = len(selected), 0, 0
    state.run_status, state.finished_at = "completed", "2026-09-15T00:00:00+00:00"
    state.dispatch_accounting = {"original_paid_total": "0.0123", "calls": 1}
    save_run_state_atomic(paths.run_state_path, state)
    case.state = state
    case.profile = OPERATOR_REVIEW_PROFILE if operator else STRICT_REVIEW_PROFILE
    case.packet = tmp_path / "formatting_packet"
    evidence = tmp_path / "explicit_source_evidence"
    evidence.mkdir()
    envelope = json.loads(case.source_review)
    if case.source_evidence is not None:
        files = [("candidate.json", case.source_evidence.candidate, envelope["candidate_file"]),
                 ("manifest.json", case.source_evidence.manifest, envelope["manifest_file"])]
        blobs = dict(case.source_evidence.artifacts)
        files.extend((f"{row['sha256']}.bin", blobs[row["sha256"]], row) for row in envelope["evidence_files"])
        for name, raw, descriptor in files:
            (evidence / name).write_bytes(raw)
            descriptor["path"] = name
    case.envelope_path = tmp_path / "source_decision.json"
    case.envelope_path.write_bytes(encode(envelope))
    case.source_decision_path = tmp_path / "source_decision.bin"
    case.source_decision_path.write_bytes(case.source_decision_evidence)
    case.formatting_decision_path = tmp_path / "formatting_decision.bin"
    case.formatting_decision_path.write_bytes(b"Fictional explicit formatting decision.")
    case.evidence_root = evidence
    return case


def command(case, action, *extra):
    return [action, "--run", str(case.run_dir), "--profile", case.profile, *extra]


def draft_args(case):
    return command(case, "draft", "--reviewer-kind", case.reviewer, "--output", str(case.packet))


def submit_args(case):
    args = command(case, "submit", "--reviewer-kind", case.reviewer, "--packet", str(case.packet),
        "--manifest", str(case.packet / "formatting.json"), "--source-review", str(case.envelope_path),
        "--source-decision-evidence", str(case.source_decision_path),
        "--formatting-evidence", str(case.formatting_decision_path))
    if case.source_evidence is not None:
        args += ["--source-evidence-root", str(case.evidence_root)]
    return args


def invoke(capsys, args):
    code = cli.main(args)
    output = capsys.readouterr()
    assert not (output.out and output.err)
    return code, json.loads(output.out or output.err)


def reviewed_packet(case, capsys):
    code, result = invoke(capsys, draft_args(case))
    assert code == 0 and result["status"] == "draft"
    (case.packet / "formatting.json").write_bytes(encode(case.manifest))


@pytest.mark.parametrize("operator", [True, False])
def test_public_cli_draft_submit_inspect_rebuild_preserves_paid_evidence(tmp_path, monkeypatch, capsys, operator):
    case = saved_case(tmp_path, monkeypatch, operator=operator)
    original_files, original_checkpoint = ordinary.originals(case), case.paths.run_state_path.read_bytes()
    code, draft = invoke(capsys, draft_args(case))
    assert code == 0 and draft["status"] == "draft" and not draft["notice_codes"]
    assert case.paths.run_state_path.read_bytes() == original_checkpoint
    assert not (case.run_dir / "formatting_reviews").exists()
    assert (case.run_dir / ".run_workspace.lock").is_file()
    inputs = json.loads((case.packet / "review_inputs.json").read_bytes())
    template = json.loads((case.packet / "formatting.json").read_bytes())
    assert inputs["review_inputs"][0]["source_structure"]["blocks"][0]["text"]
    assert inputs["source_images"][0]["sha256"] == inputs["binding"]["pages"][0]["source_identity"]["image_sha256"]
    assert template["document_groups"] == []
    assert template["pages"][0]["fragments"] == [] and template["pages"][0]["frame"] is None
    assert template["pages"][0]["region_layout"] is None
    (case.packet / "formatting.json").write_bytes(encode(case.manifest))
    code, submitted = invoke(capsys, submit_args(case))
    assert code == 0 and submitted["status"] == "submitted" and submitted["assembly_status"] == "ready"
    revision = submitted["revision_id"]
    code, inspected = invoke(capsys, command(case, "inspect", "--revision", revision))
    assert code == 0 and inspected["status"] == "ready"
    assert case.paths.run_state_path.read_bytes() == original_checkpoint
    code, rebuilt = invoke(capsys, command(case, "rebuild", "--revision", revision))
    assert code == 0 and rebuilt["status"] == "rebuilt" and rebuilt["provider_dispatch_count"] == 0
    restored = load_run_state(case.paths.run_state_path)
    assert restored.dispatch_accounting == case.state.dispatch_accounting
    assert restored.settings == case.state.settings and restored.protocol_identity == case.state.protocol_identity
    assert restored.pages["1"]["structured_commit"] == case.state.pages["1"]["structured_commit"]
    assert ordinary.originals(case) == original_files
    assert inspected["rendered_layout_acceptance"] == rebuilt["rendered_layout_acceptance"] == "not_evaluated"


@pytest.mark.parametrize("options,notice", [
    ({"page_breaks": False}, "reviewed_profile_requires_page_breaks"),
    ({"strip": False}, "reviewed_profile_requires_bidi_stripping"),
    ({"pages": 2, "selected": [2]}, "reviewed_profile_unsupported_selection"),
    ({"provenance": "digital_pdf"}, "reviewed_profile_unsupported_source_provenance"),
    ({"provenance": "local_ocr_tsv", "native_pdf": True}, "reviewed_profile_unsupported_source_provenance"),
])
def test_unsupported_saved_profiles_are_explicit_declines_without_rebuild(tmp_path, monkeypatch, capsys, options, notice):
    case = saved_case(tmp_path, monkeypatch, **options)
    before = case.paths.run_state_path.read_bytes()
    reviewed_packet(case, capsys)
    code, submitted = invoke(capsys, submit_args(case))
    assert code == 3 and submitted["assembly_status"] == "declined" and notice in submitted["notice_codes"]
    monkeypatch.setattr(workflow_module.TranslationWorkflow, "rebuild_docx", forbidden)
    code, result = invoke(capsys, command(case, "rebuild", "--revision", submitted["revision_id"]))
    assert code == 3 and result["status"] == "declined" and notice in result["notice_codes"]
    assert case.paths.run_state_path.read_bytes() == before
    assert not list(case.config.output_dir.glob("*.docx"))


@pytest.mark.parametrize("key,value", [("page_breaks", None), ("strip_bidi_controls", "true"), ("workers", 7)])
def test_saved_preferences_are_required_and_never_fabricated(tmp_path, monkeypatch, capsys, key, value):
    case = saved_case(tmp_path, monkeypatch)
    payload = json.loads(case.paths.run_state_path.read_bytes())
    if value is None:
        del payload["settings"][key]
    else:
        payload["settings"][key] = value
    case.paths.run_state_path.write_bytes(encode(payload))
    before = case.paths.run_state_path.read_bytes()
    code, result = invoke(capsys, draft_args(case))
    assert code == 1 and result["status"] == "error"
    assert not case.packet.exists() and case.paths.run_state_path.read_bytes() == before


@pytest.mark.parametrize("kind", ["packet", "checkpoint", "text"])
def test_submission_requires_current_immutable_acquisition_inputs(tmp_path, monkeypatch, capsys, kind):
    case = saved_case(tmp_path, monkeypatch)
    reviewed_packet(case, capsys)
    if kind == "packet":
        path = case.packet / "review_inputs.json"
        path.write_bytes(path.read_bytes() + b" ")
    elif kind == "checkpoint":
        state = load_run_state(case.paths.run_state_path)
        state.settings["page_breaks"] = False
        save_run_state_atomic(case.paths.run_state_path, state)
    else:
        (case.pages_dir / "page_0001.txt").write_bytes(b"Edited saved target.")
    code, result = invoke(capsys, submit_args(case))
    assert code == 1 and result["status"] == "error"
    assert not (case.run_dir / "formatting_reviews").exists()


@pytest.mark.parametrize("kind", ["traversal", "outside_absolute", "wrong_hash", "duplicate_path", "missing_root"])
def test_source_evidence_is_explicit_confined_and_hash_bound(tmp_path, monkeypatch, capsys, kind):
    case = saved_case(tmp_path, monkeypatch)
    reviewed_packet(case, capsys)
    envelope = json.loads(case.envelope_path.read_bytes())
    if kind == "traversal":
        envelope["candidate_file"]["path"] = "../private-secret-marker.bin"
    elif kind == "outside_absolute":
        outside = tmp_path / "private-secret-marker.bin"
        outside.write_bytes(case.source_evidence.candidate)
        envelope["candidate_file"]["path"] = str(outside)
    elif kind == "wrong_hash":
        (case.evidence_root / "candidate.json").write_bytes(b"private-secret-marker")
    elif kind == "duplicate_path":
        envelope["manifest_file"]["path"] = envelope["candidate_file"]["path"]
    case.envelope_path.write_bytes(encode(envelope))
    args = submit_args(case)
    if kind == "missing_root":
        args = args[:-2]
    code, result = invoke(capsys, args)
    assert code == 1 and "private-secret-marker" not in json.dumps(result)
    assert not (case.run_dir / "formatting_reviews").exists()


def test_evidence_file_bound_prevents_oversized_read(tmp_path):
    path = tmp_path / "bytes.bin"
    path.write_bytes(b"12345")
    with pytest.raises(cli.FormattingReviewCLIError, match="local_file_too_large"):
        cli._read(path, maximum=4)


def test_no_automatic_revision_or_profile_selection(tmp_path, monkeypatch, capsys):
    case = saved_case(tmp_path, monkeypatch)
    reviewed_packet(case, capsys)
    _, submitted = invoke(capsys, submit_args(case))
    code, result = invoke(capsys, command(case, "rebuild"))
    assert code == 2 and result["code"] == "invalid_arguments"
    args = command(case, "inspect", "--revision", submitted["revision_id"])
    args[args.index(case.profile)] = STRICT_REVIEW_PROFILE
    code, result = invoke(capsys, args)
    assert code == 3 and "reviewed_profile_review_profile_mismatch" in result["notice_codes"]
    assert not list(case.config.output_dir.glob("*.docx"))


def test_lock_contention_and_running_checkpoint_fail_without_packet(tmp_path, monkeypatch, capsys):
    case = saved_case(tmp_path, monkeypatch)
    with run_workspace_slot(case.run_dir):
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(cli.main, draft_args(case)).result(timeout=5) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.err)["code"] == "run_busy" and not case.packet.exists()
    case.state.run_status = "running"
    save_run_state_atomic(case.paths.run_state_path, case.state)
    code, result = invoke(capsys, draft_args(case))
    assert code == 1 and result["code"] == "run_marked_running" and not case.packet.exists()


def test_packet_is_exclusive_and_errors_do_not_echo_private_arguments(tmp_path, monkeypatch, capsys):
    case = saved_case(tmp_path, monkeypatch)
    reviewed_packet(case, capsys)
    before = {path.name: path.read_bytes() for path in case.packet.iterdir()}
    code, result = invoke(capsys, draft_args(case))
    assert code == 1 and result["code"] == "formatting_review_failed"
    assert {path.name: path.read_bytes() for path in case.packet.iterdir()} == before
    code, result = invoke(capsys, ["inspect", "--run", "private-secret-marker", "--profile", "unknown-private-value"])
    assert code == 2 and result == {"status": "error", "code": "invalid_arguments"}


def test_ambiguous_saved_run_location_is_not_redirected_or_guessed(tmp_path, monkeypatch, capsys):
    case = saved_case(tmp_path, monkeypatch)
    renamed = case.run_dir.parent / "unknown_gmail_or_redirect_scope"
    case.run_dir.rename(renamed)
    checkpoint = renamed / "run_state.json"
    payload = json.loads(checkpoint.read_bytes())
    payload["run_dir_abs"] = str(renamed)
    checkpoint.write_bytes(encode(payload))
    case.run_dir = renamed
    code, result = invoke(capsys, draft_args(case))
    assert code == 1 and result["code"] == "unsupported_run_location"
    assert not case.packet.exists()
