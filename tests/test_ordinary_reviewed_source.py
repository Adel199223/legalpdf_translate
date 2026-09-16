"""Synthetic public context/ordinary workflow coverage; no private authority."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import builtins
import json
import traceback
from types import SimpleNamespace

import pytest

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.browser_pdf_bundle import write_browser_pdf_bundle
from legalpdf_translate.checkpoint import load_run_state, settings_fingerprint
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.ordinary_reviewed_source import OrdinaryReviewedSourceContext, OrdinaryReviewedSourceError
from legalpdf_translate.reviewed_source import ReviewedSourceEvidence, adapt_reviewed_candidate
from legalpdf_translate.source_document import source_page_dimensions, source_page_identity
from legalpdf_translate.source_readiness import source_readiness_diagnostics, source_structure_digest
from legalpdf_translate.types import ImageMode, OcrMode, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_source_review_candidate import fixture, bind_review, build, digest, encode


def case(tmp_path, *, reviewer="operator_review"):
    manifest, review, artifacts = fixture()
    page = manifest["pages"][0]
    old_review = page["review_evidence_sha256"]
    review["review_kind"] = reviewer
    bind_review(manifest, review, artifacts)
    if old_review != page["review_evidence_sha256"]:
        del artifacts[old_review]
    source = tmp_path / "source.pdf"
    source.write_bytes(artifacts[manifest["document_sha256"]])
    write_browser_pdf_bundle(source_path=source, page_count=1, pages=[{
        "page_number": 1, "mime_type": "image/png", "width_px": 200, "height_px": 300,
        "image_bytes": artifacts[page["image_sha256"]]}])
    candidate = build(manifest, artifacts, require_complete=True)
    evidence = ReviewedSourceEvidence(encode(candidate), encode(manifest), tuple(artifacts.items()))
    identities = {1: source_page_identity(source, 1)}
    sizes = {1: source_page_dimensions(source, 1)}
    source_hash = manifest["document_sha256"]
    sources = adapt_reviewed_candidate(evidence, candidate_sha256=digest(evidence.candidate),
        manifest_sha256=digest(evidence.manifest), source_hash=source_hash,
        page_identities=identities, page_sizes=sizes)
    decision = b"Explicit fictional complete operator/source decision."
    def pin(label, raw):
        return {"path": str(tmp_path / label), "sha256": digest(raw)}
    envelope = {"version": "reviewed_source_acceptance_v1", "review_kind": reviewer,
        "review_evidence_sha256": digest(decision), "source_file_sha256": source_hash,
        "candidate_file": pin("candidate.json", evidence.candidate),
        "manifest_file": pin("manifest.json", evidence.manifest),
        "evidence_files": [pin(key + ".bin", raw) for key, raw in evidence.artifacts],
        "pages": [{"page_number": n, "reviewed_source_sha256": source_structure_digest(s),
            "readiness_sha256": digest(encode(source_readiness_diagnostics(s))),
            "source_fidelity": "accepted", "document_boundary": "accepted", "unresolved_findings": []}
            for n, s in sources.items()]}
    guard_state = {"valid": True, "calls": 0}
    def guard():
        guard_state["calls"] += 1
        if not guard_state["valid"]:
            raise ValueError("private details must not escape")
        return False  # A return value is never used as proof or acceptance.
    context = OrdinaryReviewedSourceContext("source-revision-1", reviewer, encode(envelope),
        evidence, decision, guard)
    output = tmp_path / "output"
    output.mkdir()
    config = RunConfig(source, output, TargetLang.EN, workers=1,
        resume=False, image_mode=ImageMode.OFF, ocr_mode=OcrMode.OFF, page_breaks=False)
    return SimpleNamespace(context=context, config=config, identities=identities, sizes=sizes,
        source_hash=source_hash, source=source, sources=sources, envelope=envelope,
        evidence=evidence, guard_state=guard_state)


def verify(c, context=None, **overrides):
    args = {"source_hash": c.source_hash, "page_identities": c.identities, "page_sizes": c.sizes}
    args.update(overrides)
    return (context or c.context).verify(**args)


class Client:
    def __init__(self, after_response=None):
        self.calls = []
        self.after_response = after_response

    def create_page_response(self, **kwargs):
        self.calls.append(kwargs)
        prompt, _ = json.JSONDecoder().raw_decode(kwargs["prompt_text"])
        translated = [{"id": row["id"], "text": ("Case 121/26" if "Processo" in row["text"] else "Article 42")}
                      for row in prompt["blocks"]]
        if self.after_response:
            self.after_response()
        return ApiCallResult(raw_output=json.dumps({"blocks": translated}),
            usage={"input_tokens": 12, "output_tokens": 14, "reasoning_tokens": 4, "total_tokens": 26},
            response_id=f"synthetic-{len(self.calls)}", response_status="completed")


@pytest.fixture(autouse=True)
def no_external_work(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    def forbidden(*_a, **_kw):
        pytest.fail("No authentication, extraction or OCR operation is permitted")
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test", forbidden)
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", forbidden)


def workflow(c, client=None, **options):
    return TranslationWorkflow(client=client or Client(), gui_settings={},
        reviewed_source_context=c.context, **options)


@pytest.mark.parametrize("reviewer", ["operator_review", "ai_test_review"])
def test_context_retains_distinct_genuine_review_kind_and_freezes_containers(tmp_path, reviewer):
    c = case(tmp_path, reviewer=reviewer)
    sources = verify(c)
    assert sources[1]["source_structure"]["metadata"]["reviewed_source"]["review_kind"] == reviewer
    assert c.context.identity["reviewer_kind"] == reviewer
    assert c.context.evidence == c.evidence and c.context.evidence is not c.evidence
    identity = c.context.identity
    identity["revision_id"] = "changed"
    sources[1]["source_structure"]["blocks"][0]["text"] = "changed"
    assert c.context.identity["revision_id"] == "source-revision-1"
    assert verify(c)[1]["source_structure"] == c.sources[1].to_dict()
    with pytest.raises(FrozenInstanceError):
        c.context.revision_id = "changed"
    with pytest.raises(OrdinaryReviewedSourceError, match="invalid_evidence"):
        replace(c.context, evidence=replace(c.evidence, artifacts=list(c.evidence.artifacts)))


@pytest.mark.parametrize("field", ["source_review_json", "decision_evidence", "candidate", "manifest", "artifact"])
def test_changed_bound_bytes_are_rejected(tmp_path, field):
    c = case(tmp_path)
    with pytest.raises(OrdinaryReviewedSourceError):
        if field in {"source_review_json", "decision_evidence"}:
            replace(c.context, **{field: getattr(c.context, field) + b"changed"})
        elif field in {"candidate", "manifest"}:
            replace(c.context, evidence=replace(c.evidence, **{field: getattr(c.evidence, field) + b"changed"}))
        else:
            pairs = list(c.evidence.artifacts)
            pairs[0] = (pairs[0][0], pairs[0][1] + b"changed")
            replace(c.context, evidence=replace(c.evidence, artifacts=tuple(pairs)))


def test_noop_guard_cannot_authorize_wrong_actual_source_or_reviewer(tmp_path):
    c = case(tmp_path)
    wrong = deepcopy(c.identities)
    wrong[1]["image_sha256"] = "0" * 64
    with pytest.raises(OrdinaryReviewedSourceError):
        verify(c, page_identities=wrong)
    with pytest.raises(OrdinaryReviewedSourceError):
        verify(c, page_identities={2: c.identities[1]})
    # Outer labels cannot upgrade the genuinely operator-reviewed inner page.
    envelope = deepcopy(c.envelope)
    envelope["review_kind"] = "ai_test_review"
    relabelled = replace(c.context, reviewer_kind="ai_test_review", source_review_json=encode(envelope))
    with pytest.raises(OrdinaryReviewedSourceError, match="reviewer_changed"):
        verify(c, relabelled)


def test_source_guard_failure_is_content_free(tmp_path):
    c = case(tmp_path)
    c.guard_state["valid"] = False
    with pytest.raises(OrdinaryReviewedSourceError, match="^ordinary_source_review_storage_changed$") as caught:
        verify(c)
    assert "private details must not escape" not in "".join(traceback.format_exception(caught.value))


def test_protocol_is_explicit_per_workflow_and_contexts_cannot_mix(tmp_path, monkeypatch):
    c = case(tmp_path)
    before = settings_fingerprint(c.config)
    monkeypatch.setenv("LEGALPDF_TRANSLATION_PROTOCOL", "legacy_text_v1")
    w = workflow(c)
    assert w._configured_translation_protocol == "legal_blocks_v2"
    assert TranslationWorkflow(gui_settings={})._configured_translation_protocol == "legacy_text_v1"
    assert settings_fingerprint(c.config) == before and c.config.page_breaks is False
    assert "ordinary_source_review" not in before
    with pytest.raises(OrdinaryReviewedSourceError, match="conflicting_context"):
        workflow(c, translation_protocol="legacy_text_v1")
    with pytest.raises(OrdinaryReviewedSourceError, match="conflicting_context"):
        workflow(c, acceptance_continuation=object())


@pytest.mark.parametrize("reviewer", ["operator_review", "ai_test_review"])
def test_ordinary_public_context_produces_real_commits_without_private_authority(tmp_path, monkeypatch, reviewer):
    c = case(tmp_path, reviewer=reviewer)
    original_import = builtins.__import__
    def no_private_authority(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("acceptance_") or name.startswith("legalpdf_translate.acceptance_"):
            pytest.fail("Ordinary reviewed translation must not import private acceptance authority")
        return original_import(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", no_private_authority)
    client = Client()
    w = workflow(c, client)
    result = w.run(c.config)
    assert result.success, result.error
    assert len(client.calls) == 1 and w._acceptance_continuation is None
    assert w._structured_run.acceptance is None
    assert not (result.run_dir / "acceptance_private").exists()
    state = load_run_state(result.run_dir / "run_state.json")
    assert state.settings["ordinary_source_review"] == c.context.identity
    assert state.settings["page_breaks"] is False
    assert state.protocol_identity == w._structured_run.identity
    assert state.pages["1"]["structured_commit"]["page_result"] is not None
    assert state.pages["1"]["source_review_kind"] == reviewer
    source = json.loads((result.run_dir / "pages/page_0001.source_structure.json").read_bytes())
    target = json.loads((result.run_dir / "pages/page_0001.structure.json").read_bytes())
    assert source == c.sources[1].to_dict()
    assert source["metadata"]["reviewed_source"]["review_kind"] == reviewer
    assert target["metadata"]["ordinary_source_review"] == c.context.identity
    assert target["metadata"]["review"]["human_review_required"] is True
    assert state.dispatch_accounting and w._dispatch_accounting.budget_context is None
    assert (result.run_dir / "accounting" / state.dispatch_accounting["id"] / "dispatch_accounting.json").is_file()
    before = len(client.calls)
    resumed = workflow(c, client).run(replace(c.config, resume=True))
    assert resumed.success and len(client.calls) == before


@pytest.mark.parametrize("change", ["missing", "revision", "decision"])
def test_resume_requires_exact_context_before_environment_or_accounting(tmp_path, change):
    c = case(tmp_path)
    first = workflow(c).run(c.config)
    assert first.success
    checkpoint = (first.run_dir / "run_state.json").read_bytes()
    context = c.context
    if change == "missing":
        context = None
    elif change == "revision":
        context = replace(context, revision_id="source-revision-2")
    else:
        decision = b"A different explicit decision record."
        envelope = deepcopy(c.envelope)
        envelope["review_evidence_sha256"] = digest(decision)
        context = replace(context, decision_evidence=decision, source_review_json=encode(envelope))
    def forbidden(*_a, **_kw):
        pytest.fail("Resume mismatch must precede environment/accounting/auth")
    w = TranslationWorkflow(client=Client(), gui_settings={}, reviewed_source_context=context,
        environment_loader=forbidden, accounting_factory=forbidden)
    with pytest.raises(OrdinaryReviewedSourceError, match="resume_context_changed"):
        w.run(replace(c.config, resume=True))
    assert (first.run_dir / "run_state.json").read_bytes() == checkpoint


def test_recheck_blocks_changed_storage_before_auth_and_before_publication(tmp_path):
    c = case(tmp_path)
    c.guard_state["valid"] = False
    def forbidden(*_a, **_kw):
        pytest.fail("Unverified source must precede environment/accounting/auth")
    with pytest.raises(OrdinaryReviewedSourceError, match="storage_changed"):
        workflow(c, environment_loader=forbidden, accounting_factory=forbidden).run(c.config)
    c.guard_state["valid"] = True
    client = Client(after_response=lambda: c.guard_state.update(valid=False))
    result = workflow(c, client).run(c.config)
    assert not result.success and len(client.calls) == 1
    assert not (result.run_dir / "pages/page_0001.commit.json").exists()


def test_changed_in_memory_source_cannot_reach_publication(tmp_path):
    c = case(tmp_path)
    w = workflow(c)
    client = Client(after_response=lambda: w._structured_run.reviewed_sources[1]["source_structure"]["blocks"][0].update(text="changed"))
    w._provided_client = client
    result = w.run(c.config)
    assert not result.success
    assert not (result.run_dir / "pages/page_0001.commit.json").exists()


def test_retention_and_nonbrowser_profiles_decline_without_changing_preferences(tmp_path):
    c = case(tmp_path)
    with pytest.raises(OrdinaryReviewedSourceError, match="retained_evidence"):
        workflow(c).run(replace(c.config, keep_intermediates=False))
    assert c.config.keep_intermediates is True
    image_config = replace(c.config, pdf_path=c.source.with_name("image.png"))
    image_config.pdf_path.write_bytes(dict(c.evidence.artifacts)[c.identities[1]["image_sha256"]])
    with pytest.raises(OrdinaryReviewedSourceError, match="full_browser_source_required"):
        workflow(c).run(image_config)


@pytest.mark.parametrize("mutation", ["jitter", "reservation", "retry_backoff"])
def test_real_transport_rechecks_review_before_each_sdk_send(tmp_path, monkeypatch, mutation):
    from legalpdf_translate import openai_client as transport
    from legalpdf_translate.usage_accounting import DispatchAccounting

    c = case(tmp_path)
    calls, events = [], []
    class Throttled(Exception):
        status_code = 429

    def create(**request):
        calls.append(request)
        assert events[-1][0] == "begin"
        raise Throttled()

    original_begin, original_finish = DispatchAccounting.begin, DispatchAccounting.finish
    def begin(accountant, **kwargs):
        ticket = original_begin(accountant, **kwargs)
        events.append(("begin", ticket.call_id))
        if mutation == "reservation":
            c.guard_state["valid"] = False
        return ticket
    def finish(accountant, ticket, **kwargs):
        result = original_finish(accountant, ticket, **kwargs)
        events.append(("finish", kwargs["outcome"]))
        return result
    monkeypatch.setattr(DispatchAccounting, "begin", begin)
    monkeypatch.setattr(DispatchAccounting, "finish", finish)
    monkeypatch.setattr(transport.random, "uniform", lambda *_: 0.1)
    def sleep(_seconds):
        if mutation == "jitter" or (mutation == "retry_backoff" and calls):
            c.guard_state["valid"] = False
    monkeypatch.setattr(transport.time, "sleep", sleep)
    sdk = SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create))
    client = transport.OpenAIResponsesClient(sdk_client=sdk,
        pre_call_jitter_seconds=0.1 if mutation == "jitter" else 0,
        max_transport_retries=2)
    w = workflow(c, client)
    result = w.run(c.config)
    assert not result.success
    assert len(calls) == (1 if mutation == "retry_backoff" else 0)
    assert not (result.run_dir / "pages/page_0001.commit.json").exists()
    assert isinstance(w._dispatch_accounting, DispatchAccounting)
    assert w._dispatch_accounting.budget_context is None
    if mutation == "jitter":
        assert events == []
    elif mutation == "reservation":
        assert [event[0] for event in events] == ["begin", "finish"]
        assert events[-1] == ("finish", "not_dispatched")
    else:
        assert [event[0] for event in events] == ["begin", "finish"]
        assert events[-1] == ("finish", "failed")
    journal = json.loads(w._dispatch_accounting.journal_path.read_bytes())
    assert len([e for e in journal["events"] if e["event"] == "begin"]) == len(events) // 2
    assert len([e for e in journal["events"] if e["event"] == "finish"]) == len(events) // 2


@pytest.mark.parametrize("mutation", [None, "extra_identity", "different_identity", "extra_settings"])
def test_context_produced_checkpoint_reaches_cli_draft_without_losing_identity(tmp_path, capsys, mutation):
    from legalpdf_translate import formatting_review_cli as cli
    c = case(tmp_path)
    result = workflow(c).run(c.config)
    assert result.success
    checkpoint_path = result.run_dir / "run_state.json"
    payload = json.loads(checkpoint_path.read_bytes())
    if mutation == "extra_identity":
        payload["settings"]["ordinary_source_review"]["unrecognized"] = True
    elif mutation == "different_identity":
        payload["settings"]["ordinary_source_review"]["revision_id"] = "different"
    elif mutation == "extra_settings":
        payload["settings"]["unrecognized"] = True
    if mutation:
        checkpoint_path.write_bytes(encode(payload))
    before = checkpoint_path.read_bytes()
    packet = tmp_path / "cli-packet"
    code = cli.main(["draft", "--run", str(result.run_dir), "--profile", "ordinary_operator_browser_v1",
        "--reviewer-kind", "operator_review", "--output", str(packet)])
    output = capsys.readouterr()
    response = json.loads(output.out or output.err)
    if mutation:
        assert code == 1 and response["status"] == "error" and not packet.exists()
    else:
        assert code == 0 and response["status"] == "draft"
        assert "reviewed_profile_requires_page_breaks" in response["notice_codes"]
        assert json.loads(checkpoint_path.read_bytes())["settings"]["ordinary_source_review"] == c.context.identity
    assert checkpoint_path.read_bytes() == before
