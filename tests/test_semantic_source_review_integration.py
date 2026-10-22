"""Saved fresh-only policy, unchanged primary bodies, and ordinary replay."""
from dataclasses import replace
import json

import pytest

from legalpdf_translate import ordinary_semantic_review as engine
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError, save_run_state_atomic
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_workflow_semantic_review_integration import saved_recipe, setup_review, without_repair_policy

KEY, POLICY = "semantic_source_review_policy", "source_commitment_visual_v5"


def test_fresh_saved_v3_policy_and_historical_absence_do_not_mutate_settings(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    assert recipe[KEY] == POLICY and ordinary_semantic_audit_recipe(settings) == recipe
    recipe.pop(KEY)
    before = json.dumps(settings, sort_keys=True)
    assert KEY not in ordinary_semantic_audit_recipe(settings)
    assert json.dumps(settings, sort_keys=True) == before


@pytest.mark.parametrize("value", [None, "unknown", "", True, False, [], {}])
def test_saved_explicit_invalid_policy_is_not_historical_absence(tmp_path, value):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe[KEY] = value
    with pytest.raises(SemanticAuditRecipeError, match="semantic_source_review_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("version", ["ordinary_semantic_audit_v1", "ordinary_semantic_audit_v2"])
def test_policy_cannot_enter_historical_v1_v2(tmp_path, version):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe["version"] = version
    for name in ("review_protocol", "primary_literal_packaging_version", "source_question_row_policy",
                 "source_inventory_max_output_tokens", "semantic_unit_reference_policy"):
        recipe.pop(name)
    if version.endswith("v1"):
        for name in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(name)
    with pytest.raises(SemanticAuditRecipeError): ordinary_semantic_audit_recipe(settings)


def test_policy_requires_saved_caller_unit_dependency(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe.pop("semantic_unit_reference_policy")
    with pytest.raises(SemanticAuditRecipeError, match="semantic_source_review_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("enabled", [False, True])
def test_optional_saved_policy_routes_run_resume_and_local_rebuild_only_when_present(tmp_path, monkeypatch, enabled):
    fresh = glue.fresh_recipe
    if not enabled:
        def historical(*args, **kwargs):
            recipe = fresh(*args, **kwargs)
            recipe.pop(KEY)
            return recipe
        monkeypatch.setattr(glue, "fresh_recipe", historical)
    calls = []
    run, load = engine.run_semantic_review, engine.load_semantic_review
    def observe_run(**kwargs): calls.append(kwargs); return run(**kwargs)
    def observe_load(**kwargs): calls.append(kwargs); return load(**kwargs)
    monkeypatch.setattr(engine, "run_semantic_review", observe_run)
    monkeypatch.setattr(engine, "load_semantic_review", observe_load)
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 4
    assert [r["max_output_tokens"] for r in sdk.requests[1:]] == [64000, 32000, 32000]
    before = {p: p.read_bytes() for name in ("semantic_source", "semantic_audit")
              for p in (result.run_dir / name).rglob("*") if p.is_file()}
    before[result.run_dir / "semantic_context.json"] = (result.run_dir / "semantic_context.json").read_bytes()
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(sdk.requests) == 4 and all(p.read_bytes() == raw for p, raw in before.items())
    assert all((KEY in kwargs) is enabled for kwargs in calls)
    assert all(kwargs.get(KEY, POLICY) == POLICY for kwargs in calls)
    assert (KEY in flow._last_state.settings["ordinary_semantic_audit_recipe"]) is enabled


def test_optional_review_policy_does_not_change_primary_request_or_model(tmp_path, monkeypatch):
    requests = []
    fresh = glue.fresh_recipe
    for enabled in (False, True):
        folder = tmp_path / str(enabled)
        folder.mkdir()
        with monkeypatch.context() as scoped:
            if not enabled:
                def historical(*args, **kwargs):
                    value = fresh(*args, **kwargs)
                    value.pop(KEY)
                    return value
                scoped.setattr(glue, "fresh_recipe", historical)
            config, sdk, flow = setup_review(folder)
            assert flow.run(config).success
            requests.append(sdk.requests[0])
            assert sdk.requests[0]["model"] == "gpt-5.2"
            assert all(request["model"] == "gpt-6-astra" for request in sdk.requests[1:])
    # SDK timeout is a remaining deadline, not part of the provider body.
    assert {k: v for k, v in requests[0].items() if k != "timeout"} == {k: v for k, v in requests[1].items() if k != "timeout"}


def test_saved_policy_removal_cannot_reinterpret_complete_evidence(tmp_path):
    config, sdk, flow = setup_review(tmp_path)
    assert flow.run(config).success
    flow._last_state.settings["ordinary_semantic_audit_recipe"].pop(KEY)
    save_run_state_atomic(flow._last_paths.run_state_path, flow._last_state)
    with pytest.raises(glue.SemanticIntegrationError, match="context_evidence_changed"):
        flow.run(replace(config, resume=True))
    assert len(sdk.requests) == 4
