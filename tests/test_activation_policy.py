"""Unmasked fresh-run policy and read-only queue rollout gates."""
import json

import pytest

from legalpdf_translate import config as defaults
from legalpdf_translate.translation_policy import (
    DEFAULT_TRANSLATION_PROTOCOL,
    require_inactive_queues,
    resolve_translation_protocol,
)
from legalpdf_translate.workflow import TranslationWorkflow


def test_current_default_and_model_remain_unchanged(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    assert DEFAULT_TRANSLATION_PROTOCOL == "legacy_text_v1"
    assert TranslationWorkflow(gui_settings={})._translation_protocol == "legacy_text_v1"
    assert defaults.OPENAI_MODEL == "gpt-5.2"
    assert defaults.DEFAULT_REASONING_EFFORT == "high"


def test_explicit_selection_environment_rollback_and_invalid_values(monkeypatch):
    monkeypatch.setenv("LEGALPDF_TRANSLATION_PROTOCOL", "legacy_text_v1")
    assert resolve_translation_protocol("legal_blocks_v2") == "legal_blocks_v2"
    assert resolve_translation_protocol() == "legacy_text_v1"
    monkeypatch.setenv("LEGALPDF_TRANSLATION_PROTOCOL", "legal_blocks_v2")
    assert resolve_translation_protocol() == "legal_blocks_v2"
    for invalid in ("", "garbage", "LEGAL_BLOCKS_V2"):
        with pytest.raises(ValueError, match="Unsupported"):
            resolve_translation_protocol(invalid)
        with pytest.raises(ValueError, match="Unsupported"):
            resolve_translation_protocol(environment={"LEGALPDF_TRANSLATION_PROTOCOL": invalid})


@pytest.mark.parametrize("status", ["pending", "running", "cancel_requested", "unknown", None])
def test_queue_rollout_refuses_unfinished_or_unknown_evidence(tmp_path, status):
    checkpoint = tmp_path / "queue.json"
    checkpoint.write_text(json.dumps({"jobs": [{"status": status}]}), encoding="utf-8")
    before = checkpoint.read_bytes()
    with pytest.raises(ValueError, match="inactive queues"):
        require_inactive_queues([checkpoint])
    assert checkpoint.read_bytes() == before


def test_queue_rollout_reads_terminal_checkpoints_without_mutation(tmp_path):
    checkpoint = tmp_path / "queue.json"
    checkpoint.write_text(json.dumps({"jobs": [{"status": s} for s in ("done", "failed", "skipped")]}), encoding="utf-8")
    before = checkpoint.read_bytes()
    require_inactive_queues([checkpoint])
    assert checkpoint.read_bytes() == before
    require_inactive_queues([])
    with pytest.raises(ValueError, match="inactive queues"):
        require_inactive_queues([tmp_path / "missing.json"])
