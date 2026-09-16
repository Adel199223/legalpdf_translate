"""Synthetic continuation only: no provider, credential, OCR or native operations."""
from dataclasses import replace
import json
import socket

import pytest

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate import acceptance_continuation as module
from legalpdf_translate.acceptance_continuation import AcceptanceContinuation
from legalpdf_translate.checkpoint import load_run_state
from legalpdf_translate.workflow import TranslationWorkflow
from legalpdf_translate.types import TargetLang
from tests.test_new_translation_blocks import FakeClient, configuration
from tests.source_readiness_fixtures import synthetic_native_review


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("External or ambient operation forbidden in continuation tests")
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    for name in ("load_gui_settings", "load_environment", "run_translation_auth_test",
                 "resolve_openai_key_with_source"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def policy(*, pages=(1,), subset=None, correction=None):
    # These are explicit synthetic test authorities, never generated approvals.
    return AcceptanceContinuation("a" * 64, pages, subset or pages,
        lambda request: "b" * 64 if request["purpose"] == "translation" else correction)


def run(config, client, continuation):
    # Fixture authority is explicit and source-bound, not a production bypass.
    continuation = replace(continuation, source_review_json=synthetic_native_review(config, continuation.full_case_pages))
    def forbidden(*args, **kwargs):
        pytest.fail("OCR/credential discovery forbidden")
    class ContinuationUnitWorkflow(TranslationWorkflow):
        # Persistence-unit boundary only. FakeClient never reaches transport
        # accounting; real amendment binding is independently integration-tested.
        # Do not mistake this substitution for an executable acceptance runner.
        def _initialize_dispatch_accounting(self, **kwargs):
            selected = self._acceptance_continuation
            self._acceptance_continuation = None
            try:
                super()._initialize_dispatch_accounting(**kwargs)
            finally:
                self._acceptance_continuation = selected
    return ContinuationUnitWorkflow(client=client, gui_settings={}, environment_loader=lambda: None,
        ocr_engine_factory=forbidden, translation_protocol="legal_blocks_v2",
        acceptance_continuation=continuation).run(config)


def defect_primary(response, payload):
    if response.response_id == "synthetic-1":
        response.raw_output = '{"blocks":[]}'
    return response


def test_primary_pauses_then_separately_approved_correction_reuses_paid_response(tmp_path):
    config, client = configuration(tmp_path), FakeClient(transform=defect_primary)
    first = run(config, client, policy())
    assert not first.success and len(client.calls) == 1
    folder = first.run_dir / "acceptance_private"
    pending = folder / "page_0001.correction.pending.json"
    assert pending.exists()
    assert not (folder / "page_0001.correction.intent.json").exists()
    retained = {path.name: path.read_bytes() for path in folder.iterdir()}
    paused = run(replace(config, resume=True), client, policy())
    assert not paused.success and len(client.calls) == 1
    assert retained == {path.name: path.read_bytes() for path in folder.iterdir()}
    same_approval = run(replace(config, resume=True), client, policy(correction="b" * 64))
    assert not same_approval.success and len(client.calls) == 1
    final = run(replace(config, resume=True), client, policy(correction="c" * 64))
    assert final.success and len(client.calls) == 2
    assert "The prior response failed validation" in client.calls[1]["prompt_text"]
    assert pending.read_bytes() == retained[pending.name]
    state = load_run_state(final.run_dir / "run_state.json")
    assert state.pages["1"]["api_calls_count"] == 2
    assert state.pages["1"]["input_tokens"] == 24
    assert state.pages["1"]["output_tokens"] == 28
    assert (final.run_dir / "pages" / "page_0001.commit.json").exists()
    assert run(replace(config, resume=True), client, policy(correction="c" * 64)).success
    assert len(client.calls) == 2


@pytest.mark.parametrize("boundary", ["primary.intent", "primary.response", "correction.pending", "correction.intent", "correction.response"])
def test_crash_after_each_durable_boundary_never_rebuys_completed_or_uncertain_attempt(tmp_path, monkeypatch, boundary):
    config, client = configuration(tmp_path), FakeClient(transform=defect_primary)
    real_write = module.AcceptancePageJournal._write
    crashed = []
    class SyntheticCrash(BaseException):
        pass
    def crash(self, name, payload):
        record = real_write(self, name, payload)
        if name == boundary and not crashed:
            crashed.append(name)
            raise SyntheticCrash("synthetic crash after durable boundary")
        return record
    monkeypatch.setattr(module.AcceptancePageJournal, "_write", crash)
    with pytest.raises(SyntheticCrash, match="synthetic crash"):
        run(config, client, policy(correction="c" * 64))
    calls = len(client.calls)
    monkeypatch.setattr(module.AcceptancePageJournal, "_write", real_write)
    resumed = run(replace(config, resume=True), client, policy(correction="c" * 64))
    if boundary.endswith("intent"):
        assert not resumed.success and len(client.calls) == calls
    else:
        assert resumed.success and len(client.calls) == 2


def test_paid_response_persistence_failure_leaves_intent_and_stops_future_purchase(tmp_path, monkeypatch):
    config, client = configuration(tmp_path), FakeClient()
    real_write = module.AcceptancePageJournal._write
    def fail(self, name, payload):
        if name == "primary.response":
            raise OSError("synthetic disk failure")
        return real_write(self, name, payload)
    monkeypatch.setattr(module.AcceptancePageJournal, "_write", fail)
    first = run(config, client, policy())
    assert not first.success and len(client.calls) == 1
    monkeypatch.setattr(module.AcceptancePageJournal, "_write", real_write)
    resumed = run(replace(config, resume=True), client, policy())
    assert not resumed.success and len(client.calls) == 1


@pytest.mark.parametrize("artifact", ["primary.intent", "primary.response", "correction.pending"])
@pytest.mark.parametrize("change", ["missing", "tampered"])
def test_missing_or_tampered_retained_primary_or_pending_request_fails_closed(tmp_path, artifact, change):
    config, client = configuration(tmp_path), FakeClient(transform=defect_primary)
    first = run(config, client, policy())
    path = first.run_dir / "acceptance_private" / f"page_0001.{artifact}.json"
    if change == "missing":
        path.unlink()  # Deliberate isolated corruption, never production cleanup.
    else:
        record = json.loads(path.read_text("utf-8"))
        record["identity"]["page_number"] = 2
        path.write_text(json.dumps(record), encoding="utf-8")
    resumed = run(replace(config, resume=True), client, policy(correction="c" * 64))
    assert not resumed.success and len(client.calls) == 1


def test_one_failed_correction_is_terminal_and_not_repeated(tmp_path):
    def fail(response, payload):
        response.raw_output = '{"blocks":[]}'
        return response
    config, client = configuration(tmp_path), FakeClient(transform=fail)
    first = run(config, client, policy(correction="c" * 64))
    assert not first.success and len(client.calls) == 2
    assert not run(replace(config, resume=True), client, policy(correction="c" * 64)).success
    assert len(client.calls) == 2


def test_acceptance_selection_is_fixed_and_retention_required(tmp_path):
    config, client = configuration(tmp_path, pages=2), FakeClient()
    with pytest.raises(ValueError, match="full_case_selection"):
        run(replace(config, end_page=1), client, policy(pages=(1, 2), subset=(1,)))
    with pytest.raises(ValueError, match="evidence_retention"):
        run(replace(config, keep_intermediates=False), client, policy(pages=(1, 2)))
    with pytest.raises(ValueError, match="serial_dispatch"):
        run(replace(config, workers=2), client, policy(pages=(1, 2)))
    assert not client.calls


def test_full_case_ar_pilots_then_only_remaining_pages_preserve_identity_and_commits(tmp_path):
    config = configuration(tmp_path, pages=9, lang=TargetLang.AR)
    client = FakeClient(TargetLang.AR)
    full, pilot, remaining = tuple(range(1, 10)), (1, 5, 6, 9), (2, 3, 4, 7, 8)
    first = run(config, client, policy(pages=full, subset=pilot))
    assert not first.success and first.error == "acceptance_phase_complete"
    assert first.completed_pages == 4 and first.partial_docx is not None
    state = load_run_state(first.run_dir / "run_state.json")
    identity = state.protocol_identity
    commits = {path.name: path.read_bytes() for path in (first.run_dir / "pages").glob("*.commit.json")}
    assert len(commits) == 4
    repeated_pilot = run(replace(config, resume=True), client, policy(pages=full, subset=pilot))
    assert not repeated_pilot.success and len(client.calls) == 4
    final = run(replace(config, resume=True), client, policy(pages=full, subset=remaining))
    assert final.success and final.completed_pages == 9 and len(client.calls) == 9
    final_state = load_run_state(final.run_dir / "run_state.json")
    assert final_state.protocol_identity == identity
    assert final_state.selection_page_count == 9
    assert all((final.run_dir / "pages" / name).read_bytes() == data for name, data in commits.items())
    translated_pages = [json.JSONDecoder().raw_decode(request["prompt_text"])[0]["page"]
                        for request in client.calls]
    assert sorted(translated_pages) == list(full) and len(set(translated_pages)) == 9
    source_ids, target_ids = [], []
    for number in full:
        folder = final.run_dir / "pages"
        source = json.loads((folder / f"page_{number:04d}.source_structure.json").read_text("utf-8"))
        target = json.loads((folder / f"page_{number:04d}.structure.json").read_text("utf-8"))
        source_ids.extend(row["id"] for row in source["blocks"])
        target_ids.extend(row["id"] for row in target["blocks"])
    assert source_ids == target_ids and len(set(target_ids)) == len(target_ids)
