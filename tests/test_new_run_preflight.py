"""Output probes must not mutate a rejected structured run or user sentinels."""

from dataclasses import replace
import json
import tempfile

import fitz
import pytest

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.structured_artifacts import StructuredArtifactError
from legalpdf_translate.types import ImageMode, OcrMode, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


SOURCE = ("O documento apresenta os factos e as circunstancias do processo. "
          "O arguido deve comparecer no tribunal e cumprir todas as obrigacoes indicadas. "
          "As condicoes continuam a aplicar-se durante o periodo determinado na decisao.")
TARGET = ("The document sets out the facts and circumstances of the case. "
          "The defendant must attend court and comply with all stated obligations. "
          "The conditions continue to apply during the period specified in the decision.")


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_page_response(self, **kwargs):
        self.calls.append(kwargs)
        prompt = kwargs["prompt_text"]
        if prompt.startswith("{"):
            payload, _ = json.JSONDecoder().raw_decode(prompt)
            text = json.dumps({"blocks": [{"id": row["id"], "text": TARGET}
                                          for row in payload["blocks"]]})
        else:
            text = f"```text\n{TARGET}\n```"
        return ApiCallResult(raw_output=text, usage={"input_tokens": 12, "output_tokens": 14},
                             response_id="offline-preflight", response_status="completed")


def config_for(tmp_path):
    source = tmp_path / "source.pdf"
    with fitz.open() as document:
        document.new_page().insert_textbox(fitz.Rect(48, 80, 540, 250), SOURCE, fontsize=11)
        document.save(source)
    output = tmp_path / "output"
    output.mkdir()
    return RunConfig(source, output, TargetLang.EN, image_mode=ImageMode.OFF,
                     ocr_mode=OcrMode.OFF, workers=1, resume=False, page_breaks=False)


def snapshot(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test",
                        lambda *a, **k: pytest.fail("Unexpected authentication call"))


def test_normalization_is_read_only_and_preserves_fixed_probe_sentinel(tmp_path, monkeypatch):
    config = config_for(tmp_path)
    sentinel = config.output_dir / ".write_test.tmp"
    sentinel.write_bytes(b"pre-existing user file")
    before = snapshot(config.output_dir)
    monkeypatch.setattr(tempfile, "TemporaryFile", lambda **kwargs: pytest.fail("Normalization wrote"))
    normalized = TranslationWorkflow(client=FakeClient())._normalize_config(config)
    assert normalized.output_dir == config.output_dir.resolve()
    assert snapshot(config.output_dir) == before


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_normalization_rejects_invalid_directory_without_probe(tmp_path, monkeypatch, kind):
    config = config_for(tmp_path)
    target = tmp_path / "invalid-output"
    if kind == "file":
        target.write_bytes(b"not a directory")
    before = snapshot(tmp_path)
    monkeypatch.setattr(tempfile, "TemporaryFile", lambda **kwargs: pytest.fail("Invalid directory wrote"))
    with pytest.raises(ValueError, match="Output folder"):
        TranslationWorkflow(client=FakeClient())._normalize_config(replace(config, output_dir=target))
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("protocol", ["legacy_text_v1", "legal_blocks_v2"])
def test_accepted_new_run_uses_owned_probe_not_fixed_sentinel(tmp_path, monkeypatch, protocol):
    config = config_for(tmp_path)
    sentinel = config.output_dir / ".write_test.tmp"
    sentinel.write_bytes(b"user-owned sentinel")
    real_probe = tempfile.TemporaryFile
    probes = []

    def tracked_probe(**kwargs):
        assert kwargs["dir"] == config.output_dir.resolve()
        assert kwargs["prefix"] == ".legalpdf_write_test_"
        assert sentinel.read_bytes() == b"user-owned sentinel"
        probes.append(kwargs)
        return real_probe(**kwargs)

    monkeypatch.setattr(tempfile, "TemporaryFile", tracked_probe)
    client = FakeClient()
    result = TranslationWorkflow(client=client, translation_protocol=protocol).run(config)
    assert result.success, result.error
    assert len(probes) == len(client.calls) == 1
    assert sentinel.read_bytes() == b"user-owned sentinel"
    assert not list(config.output_dir.glob(".legalpdf_write_test_*"))


@pytest.mark.parametrize("damage", ["context", "source", "checkpoint", "target", "text", "commit", "protocol"])
def test_rejected_structured_resume_is_read_only_even_with_fixed_probe_sentinel(tmp_path, monkeypatch, damage):
    config = config_for(tmp_path)
    client = FakeClient()
    workflow = TranslationWorkflow(client=client, translation_protocol="legal_blocks_v2")
    result = workflow.run(config)
    assert result.success, result.error
    sentinel = config.output_dir / ".write_test.tmp"
    sentinel.write_bytes(b"do not overwrite or delete")
    resume_config = replace(config, resume=True)
    if damage == "context":
        resume_config = replace(resume_config, context_text="Changed translation instructions")
    elif damage == "source":
        config.pdf_path.write_bytes(config.pdf_path.read_bytes() + b"\n")
    elif damage == "checkpoint":
        (result.run_dir / "run_state.json").write_text("{}", encoding="utf-8")
    elif damage == "target":
        (result.run_dir / "pages/page_0001.structure.json").write_text("{}", encoding="utf-8")
    elif damage == "text":
        (result.run_dir / "pages/page_0001.txt").write_text("Intentional manual edit", encoding="utf-8")
    elif damage == "commit":
        (result.run_dir / "pages/page_0001.commit.json").unlink()
    else:
        workflow = TranslationWorkflow(client=client, translation_protocol="legacy_text_v1")
    before = snapshot(config.output_dir)
    monkeypatch.setattr(tempfile, "TemporaryFile", lambda **kwargs: pytest.fail("Rejected resume probed output"))
    with pytest.raises(ValueError):
        workflow.run(resume_config)
    assert snapshot(config.output_dir) == before
    assert len(client.calls) == 1


def test_second_commit_validation_failure_precedes_probe(tmp_path, monkeypatch):
    config = config_for(tmp_path)
    client = FakeClient()
    workflow = TranslationWorkflow(client=client, translation_protocol="legal_blocks_v2")
    result = workflow.run(config)
    assert result.success
    before = snapshot(config.output_dir)

    def fail_recovery(*args, **kwargs):
        raise StructuredArtifactError("synthetic_evidence_changed")

    monkeypatch.setattr(workflow_module, "recover_structured_commits", fail_recovery)
    monkeypatch.setattr(tempfile, "TemporaryFile", lambda **kwargs: pytest.fail("Unvalidated recovery probed"))
    with pytest.raises(StructuredArtifactError, match="synthetic_evidence_changed"):
        workflow.run(replace(config, resume=True))
    assert snapshot(config.output_dir) == before
    assert len(client.calls) == 1


def test_accepted_resume_probes_after_evidence_and_before_checkpoint_write(tmp_path, monkeypatch):
    config = config_for(tmp_path)
    client = FakeClient()
    workflow = TranslationWorkflow(client=client, translation_protocol="legal_blocks_v2")
    assert workflow.run(config).success
    real_recover = workflow_module.recover_structured_commits
    real_probe = tempfile.TemporaryFile
    real_save = workflow_module.save_run_state_atomic
    events = []

    def recover(*args, **kwargs):
        result = real_recover(*args, **kwargs)
        events.append("evidence_validated")
        return result

    def probe(**kwargs):
        assert events == ["evidence_validated"]
        events.append("probe")
        return real_probe(**kwargs)

    def save(*args, **kwargs):
        assert events[:2] == ["evidence_validated", "probe"]
        events.append("checkpoint_write")
        return real_save(*args, **kwargs)

    monkeypatch.setattr(workflow_module, "recover_structured_commits", recover)
    monkeypatch.setattr(tempfile, "TemporaryFile", probe)
    monkeypatch.setattr(workflow_module, "save_run_state_atomic", save)
    result = workflow.run(replace(config, resume=True, page_breaks=True))
    assert result.success, result.error
    assert "checkpoint_write" in events
    assert len(client.calls) == 1


@pytest.mark.parametrize("protocol", ["legacy_text_v1", "legal_blocks_v2"])
def test_probe_failure_precedes_run_artifacts_and_provider_calls(tmp_path, monkeypatch, protocol):
    config = config_for(tmp_path)
    sentinel = config.output_dir / ".write_test.tmp"
    sentinel.write_bytes(b"leave existing user file intact")
    before = snapshot(config.output_dir)

    def denied(**kwargs):
        raise PermissionError("synthetic denied probe")

    monkeypatch.setattr(tempfile, "TemporaryFile", denied)
    client = FakeClient()
    with pytest.raises(ValueError, match="Output folder is not writable"):
        TranslationWorkflow(client=client, translation_protocol=protocol).run(config)
    assert snapshot(config.output_dir) == before
    assert list(config.output_dir.iterdir()) == [sentinel]
    assert client.calls == []
