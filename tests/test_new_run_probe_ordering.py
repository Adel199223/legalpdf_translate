"""New-run probes precede permanent artifacts without bypassing run ownership."""
from concurrent.futures import ThreadPoolExecutor
import hashlib

import pytest

from legalpdf_translate.checkpoint import build_run_paths, new_run_state, save_run_state_atomic
from legalpdf_translate.run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_new_run_preflight import FakeClient, config_for, offline, snapshot


@pytest.mark.parametrize("protocol", ["legacy_text_v1", "legal_blocks_v2"])
@pytest.mark.parametrize("rival", ["checkpoint", "malformed_checkpoint", "source_review"])
def test_rival_evidence_created_during_fresh_probe_is_preserved(tmp_path, monkeypatch, protocol, rival):
    config = config_for(tmp_path)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
    assert not paths.run_dir.exists()
    client = FakeClient()
    workflow = TranslationWorkflow(client=client, translation_protocol=protocol)
    original_probe = TranslationWorkflow._require_writable_run_output_dir
    observations = []

    def probe(output_dir):
        assert output_dir == config.output_dir.resolve()
        assert not paths.run_dir.exists()
        original_probe(output_dir)
        # A competing owner completes publication while the fresh-run caller is
        # between its successful probe and acquiring the permanent run lock.
        with run_workspace_slot(paths.run_dir, create=True):
            if rival == "checkpoint":
                state = new_run_state(config=config, paths=paths,
                    pdf_fingerprint=hashlib.sha256(config.pdf_path.read_bytes()).hexdigest(),
                    context_hash="NO_CONTEXT", total_pages=1, selected_pages=[1])
                save_run_state_atomic(paths.run_state_path, state)
            elif rival == "malformed_checkpoint":
                paths.run_state_path.write_bytes(b"incomplete rival checkpoint")
            else:
                review_root = paths.run_dir / "source_reviews"
                review_root.mkdir()
                (review_root / "retained_evidence.json").write_bytes(b'{"rival_source_review":true}')
            lock = (paths.run_dir / ".run_workspace.lock").stat()
        observations.append((snapshot(paths.run_dir), (lock.st_dev, lock.st_ino)))

    def forbidden_body(*_args, **_kwargs):
        pytest.fail("A raced fresh run must stop before loading or overwriting rival evidence")

    monkeypatch.setattr(workflow, "_require_writable_run_output_dir", probe)
    monkeypatch.setattr(workflow, "_run_locked", forbidden_body)
    with pytest.raises(ValueError, match="^New run folder was populated during output preflight;"):
        workflow.run(config)
    assert len(observations) == 1 and client.calls == []
    expected, lock_identity = observations[0]
    assert snapshot(paths.run_dir) == expected
    lock = (paths.run_dir / ".run_workspace.lock").stat()
    assert (lock.st_dev, lock.st_ino) == lock_identity


@pytest.mark.parametrize("protocol", ["legacy_text_v1", "legal_blocks_v2"])
def test_precreated_pristine_run_probes_once_under_the_existing_lock(tmp_path, monkeypatch, protocol):
    config = config_for(tmp_path)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
    with run_workspace_slot(paths.run_dir, create=True):
        pass
    lock = (paths.run_dir / ".run_workspace.lock").stat()
    identity = (lock.st_dev, lock.st_ino)
    original_probe = TranslationWorkflow._require_writable_run_output_dir
    calls = []

    def probe(output_dir):
        calls.append(output_dir)
        with ThreadPoolExecutor(max_workers=1) as pool:
            def contend():
                with run_workspace_slot(paths.run_dir):
                    pytest.fail("Existing run must remain locked before probing")
            with pytest.raises(RunWorkspaceBusy):
                pool.submit(contend).result(timeout=5)
        original_probe(output_dir)

    client = FakeClient()
    workflow = TranslationWorkflow(client=client, translation_protocol=protocol)
    monkeypatch.setattr(workflow, "_require_writable_run_output_dir", probe)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(calls) == len(client.calls) == 1
    after = (paths.run_dir / ".run_workspace.lock").stat()
    assert (after.st_dev, after.st_ino) == identity
