"""Caller-owned settings remain independent of ambient live preferences."""
from copy import deepcopy

import pytest

from legalpdf_translate import workflow as module
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_new_run_preflight import FakeClient, config_for


@pytest.mark.parametrize("protocol", ["legacy_text_v1", "legal_blocks_v2"])
def test_explicit_settings_snapshot_never_loads_live_settings(tmp_path, monkeypatch, protocol):
    settings = {"prompt_addendum_by_lang": {"EN": "Preserve the supplied legal wording."},
                "perf_timeout_text_seconds": 321, "perf_timeout_image_seconds": 654,
                "personal_glossaries_by_lang": {"EN": []}}
    expected = deepcopy(settings)
    monkeypatch.setattr(module, "load_environment", lambda: pytest.fail("Ambient .env discovery"))
    monkeypatch.setattr(module, "load_gui_settings", lambda: pytest.fail("Live settings read"))
    monkeypatch.setattr(module, "resolve_openai_key_with_source", lambda: pytest.fail("Report resolved live key"))
    client = FakeClient()
    workflow = TranslationWorkflow(client=client, gui_settings=settings, translation_protocol=protocol,
        environment_loader=lambda: None)
    settings["prompt_addendum_by_lang"]["EN"] = "Caller mutation after construction"
    summary = workflow.run(config_for(tmp_path))
    assert summary.success, summary.error
    assert workflow._gui_settings == expected
    assert workflow._translation_timeout_text_seconds == 321
    assert workflow._translation_timeout_image_seconds == 654
    assert "Preserve the supplied legal wording." in client.calls[0]["prompt_text"]
    assert "Caller mutation" not in client.calls[0]["prompt_text"]


def test_explicit_empty_settings_and_legacy_omission_are_distinct(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "load_environment", lambda: None)
    calls = []
    monkeypatch.setattr(module, "load_gui_settings", lambda: calls.append(True) or {})
    config = config_for(tmp_path)
    assert TranslationWorkflow(client=FakeClient(), gui_settings={}).run(config).success
    assert not calls
    assert TranslationWorkflow(client=FakeClient()).run(config).success
    assert calls == [True]


def test_auto_auth_never_uses_a_billable_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "load_environment", lambda: None)
    class Client(FakeClient):
        def run_translation_auth_test(self):
            pytest.fail("Automatic billable auth probe")
    assert TranslationWorkflow(client=Client(), gui_settings={}).run(config_for(tmp_path)).success


def test_injected_ocr_engine_does_not_discover_ambient_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "build_ocr_engine", lambda *_: pytest.fail("Ambient OCR provider construction"))
    sentinel = object()
    received = []
    workflow = TranslationWorkflow(client=FakeClient(), gui_settings={}, environment_loader=lambda: None,
        ocr_engine_factory=lambda config: received.append(config) or sentinel)
    engine, configured = workflow._resolve_ocr_engine_for_reason(
        config=config_for(tmp_path), request_reason="required", page_number=1)
    assert engine is sentinel and configured
    assert len(received) == 1
