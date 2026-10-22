"""Ordinary workflow, actual SDK/native journal, fictional HTTP and source only."""
from dataclasses import replace, asdict
from decimal import Decimal
import json
from pathlib import Path

import fitz
import pytest

from legalpdf_translate import semantic_review_model_policy as policy
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.checkpoint import save_run_state_atomic
from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy
from legalpdf_translate.types import TargetLang, ImageMode, BudgetExceedPolicy
from legalpdf_translate.workflow import TranslationWorkflow
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.usage_accounting import _state_fingerprint
from tests.test_new_run_preflight import config_for
from tests.test_workflow_semantic_audit_integration import offline
from tests.semantic_model_fakes import ModelHTTP


def setup(tmp_path, *, mutate=None, primary_retry=False):
    config = replace(config_for(tmp_path), target_lang=TargetLang.AR, image_mode=ImageMode.OFF,
        context_text="Fictional bounded terminology preference.")
    http = ModelHTTP(mutate, primary_retry)
    flow = TranslationWorkflow(client=http.client, gui_settings={}, ordinary_auto_layout_policy=frozen_automatic_layout_policy())
    return config, http, flow


def immutable(run_dir):
    return {p: p.read_bytes() for folder in ("semantic_source", "semantic_audit", "accounting")
            for p in (run_dir / folder).rglob("*") if p.is_file() and p.suffix != ".lock"}


def test_fresh_three_page_real_workflow_roles_source_v5_native_usage_and_offline_replay(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_semantic_review as engine
    from legalpdf_translate import ordinary_semantic_repair as repair
    captured = []
    original = repair.run_semantic_repair
    def observe(**kwargs):
        captured.append(kwargs["recipe"])
        return original(**kwargs)
    monkeypatch.setattr(repair, "run_semantic_repair", observe)
    config, http, flow = setup(tmp_path)
    with fitz.open(config.pdf_path) as doc:
        for _ in range(2): doc.new_page().insert_text((50, 80), "Fictional page source.")
        doc.saveIncr()
    result = flow.run(config)
    assert result.success, result.error
    assert [r["model"] for r in http.requests] == ["gpt-5.2"] * 3 + ["gpt-6-astra"] * 3
    assert [r["max_output_tokens"] for r in http.requests[-3:]] == [64000, 32000, 32000]
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved["model"] == "gpt-5.2" and saved[policy.KEY]["model"] == "gpt-6-astra"
    assert saved["semantic_source_review_policy"] == "source_commitment_visual_v5"
    manifest = json.loads((result.run_dir / "semantic_audit/manifest.json").read_bytes())
    assert captured[0].model == "gpt-6-astra"
    assert manifest["binding"]["recipe_sha256"] == engine.audit._sha(engine.audit._json(asdict(captured[0])))
    assert manifest["binding"]["semantic_source_review_policy"]["policy"] == "source_commitment_visual_v5"
    for request in http.requests[-3:]:
        payload = json.loads(request["input"][0]["content"][0]["text"])
        assert payload["semantic_source_review_policy"]["policy"] == "source_commitment_visual_v5"
        assert request["reasoning"]["effort"] == saved["reasoning_effort"]
        assert payload.get("context_text") is not None if payload["stage"] == "correction" else "context_text" not in payload
    correction = http.requests[-2]["text"]["format"]["schema"]["properties"]["pages"]
    assert correction["minItems"] == correction["maxItems"] == 3
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    assert journal["run_identity"][policy.KEY] == saved[policy.KEY]
    roles = {(e["purpose"], e["requested_model"]) for e in journal["events"] if e["event"] == "begin"}
    assert roles == {("translation", "gpt-5.2"), ("semantic_audit", "gpt-6-astra")}
    assert len(list((flow._dispatch_accounting.run_dir / "provider_responses").glob("*.json"))) == 3
    assert flow._budget_pre_run_packet["estimated_cost_usd"] is None
    before = immutable(result.run_dir)
    monkeypatch.setattr(policy, "fresh_semantic_review_model_policy", lambda: pytest.fail("Saved replay consulted fresh model policy"))
    assert flow.run(replace(config, resume=True)).success
    monkeypatch.setattr(OpenAIResponsesClient, "for_semantic_review", lambda *a, **k: pytest.fail("Offline rebuild constructed a client"))
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == 6 and immutable(result.run_dir) == before


def test_primary_correction_stays_primary_model(tmp_path):
    config, http, flow = setup(tmp_path, primary_retry=True)
    result = flow.run(config)
    assert result.success, result.error
    assert [r["model"] for r in http.requests] == ["gpt-5.2", "gpt-5.2"] + ["gpt-6-astra"] * 3
    events = json.loads(flow._dispatch_accounting.journal_path.read_bytes())["events"]
    assert any(e["event"] == "begin" and e["purpose"] == "correction" and e["requested_model"] == "gpt-5.2" for e in events)


def test_unknown_first_semantic_usage_retains_raw_stops_no_next_stage_or_resume_purchase(tmp_path):
    def mutate(body, data):
        if body["model"] == "gpt-6-astra": data["usage"]["input_tokens_details"].pop("cache_write_tokens")
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    result = flow.run(config)
    assert not result.success and len(http.requests) == 2
    folder = result.run_dir / "semantic_audit/attempt_00/source_inventory"
    assert json.loads((folder / "raw_response.json").read_bytes())["raw_output"]
    assert (folder / "raw_receipt.json").is_file()
    assert not (result.run_dir / "semantic_audit/attempt_00/correction").exists()
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
    before = immutable(result.run_dir)
    assert not flow.run(replace(config, resume=True)).success
    assert len(http.requests) == 2 and immutable(result.run_dir) == before


def test_strict_block_fails_before_any_primary_or_semantic_send(tmp_path):
    config, http, flow = setup(tmp_path)
    with pytest.raises(ValueError, match="BLOCK"):
        flow.run(replace(config, budget_cap_usd=10, budget_on_exceed=BudgetExceedPolicy.BLOCK))
    assert http.requests == []


@pytest.mark.parametrize("damage", ["policy_removed", "purpose_model", "raw_body"])
def test_saved_role_or_native_body_tamper_stops_without_sdk_calls(tmp_path, damage):
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    if damage == "policy_removed":
        flow._last_state.settings["ordinary_semantic_audit_recipe"].pop(policy.KEY)
        save_run_state_atomic(flow._last_paths.run_state_path, flow._last_state)
    elif damage == "purpose_model":
        path = flow._dispatch_accounting.journal_path
        journal = json.loads(path.read_bytes())
        next(e for e in journal["events"] if e["event"] == "begin" and e["purpose"] == "semantic_audit")["requested_model"] = "gpt-5.2"
        journal["fingerprint"] = _state_fingerprint(journal)
        path.write_bytes(json.dumps(journal).encode())
    else:
        path = next((flow._dispatch_accounting.run_dir / "provider_responses").glob("*.json"))
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises((ValueError, RuntimeError)):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(http.requests) == 4


def test_historical_absence_retains_primary_review_model_and_saved_replay(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "fresh_semantic_review_model_policy", lambda: None)
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert all(r["model"] == "gpt-5.2" for r in http.requests)
    assert policy.KEY not in flow._last_state.settings["ordinary_semantic_audit_recipe"]
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    assert policy.KEY not in journal["run_identity"]
    assert "openai:semantic_audit:gpt-6-astra" not in journal["dispatch_limits"]
    before = immutable(result.run_dir)
    monkeypatch.setattr(policy, "fresh_semantic_review_model_policy", lambda: {"version": policy.VERSION, "model": "gpt-6-astra"})
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == 4 and immutable(result.run_dir) == before


@pytest.mark.parametrize("stage,failure,expected_calls", [("source_inventory", "refusal", 2),
    ("correction", "incomplete", 3), ("source_inventory", "cancel", 2)])
def test_fresh_native_refusal_incomplete_cancel_retains_settled_raw_without_followup(tmp_path, stage, failure, expected_calls):
    holder = {}
    def mutate(body, data):
        if body["model"] == "gpt-6-astra":
            payload = json.loads(body["input"][0]["content"][0]["text"])
            if payload["stage"] == stage:
                if failure == "refusal": data["output"] = [{"type": "refusal", "refusal": "Fictional refusal"}]
                elif failure == "incomplete":
                    data["status"] = "incomplete"
                    data["incomplete_details"] = {"reason": "max_output_tokens"}
                else: holder["flow"]._cancel_event.set()
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    holder["flow"] = flow
    result = flow.run(config)
    assert not result.success and len(http.requests) == expected_calls
    assert (result.run_dir / "semantic_audit/attempt_00" / stage / "raw_response.json").is_file()
    assert (result.run_dir / "semantic_audit/attempt_00" / stage / "raw_receipt.json").is_file()
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
    before = immutable(result.run_dir)
    resumed = flow.run(replace(config, resume=True))
    if failure == "cancel":
        # Explicit Resume may continue later stages from the settled raw response;
        # it must not repurchase the cancelled-but-completed source inventory.
        assert resumed.success and len(http.requests) == expected_calls + 2
        assert sum(json.loads(r["input"][0]["content"][0]["text"]).get("stage") == "source_inventory"
                   for r in http.requests if r["model"] == "gpt-6-astra") == 1
        assert all(p.read_bytes() == raw for p, raw in before.items() if stage in p.parts)
    else:
        assert not resumed.success and len(http.requests) == expected_calls
        assert immutable(result.run_dir) == before
