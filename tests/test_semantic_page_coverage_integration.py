"""Fresh-only selected-page recipe and actual workflow replay boundaries."""
from dataclasses import replace
import json

import fitz
import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy

from legalpdf_translate import ordinary_semantic_review as engine
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError, save_run_state_atomic
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_workflow_semantic_review_integration import saved_recipe, setup_review

KEY, POLICY = "semantic_page_coverage_policy", "complete_selected_pages_v1"


def test_fresh_v3_selects_policy_and_saved_absence_stays_absent(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    assert recipe[KEY] == POLICY and ordinary_semantic_audit_recipe(settings) == recipe
    recipe.pop(KEY)
    before = json.dumps(settings, sort_keys=True)
    assert KEY not in ordinary_semantic_audit_recipe(settings)
    assert json.dumps(settings, sort_keys=True) == before


@pytest.mark.parametrize("value", [None, "", "unknown", True, False, 0, [], {}])
def test_invalid_saved_policy_cannot_become_historical_absence(tmp_path, value):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe[KEY] = value
    with pytest.raises(SemanticAuditRecipeError, match="semantic_page_coverage_policy"):
        ordinary_semantic_audit_recipe(settings)


def test_saved_dependency_required(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    for key in ("semantic_unit_reference_policy", "semantic_source_review_policy", "source_inventory_max_output_tokens"):
        recipe.pop(key)
    with pytest.raises(SemanticAuditRecipeError, match="semantic_page_coverage_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("version", ["ordinary_semantic_audit_v1", "ordinary_semantic_audit_v2"])
def test_new_policy_rejected_by_old_exact_recipe_versions(tmp_path, version):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe["version"] = version
    for key in ("review_protocol", "primary_literal_packaging_version", "source_question_row_policy",
                "source_inventory_max_output_tokens", "semantic_source_review_policy", "semantic_unit_reference_policy"):
        recipe.pop(key)
    if version.endswith("v1"):
        for key in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(key)
    with pytest.raises(SemanticAuditRecipeError): ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("enabled", [False, True])
def test_ordinary_three_page_run_saved_resume_and_offline_rebuild_only_use_saved_policy(tmp_path, monkeypatch, enabled):
    fresh = glue.fresh_recipe
    if not enabled:
        def historical(*args, **kwargs):
            value = fresh(*args, **kwargs)
            value.pop(KEY)
            return value
        monkeypatch.setattr(glue, "fresh_recipe", historical)
    calls = []
    run, load = engine.run_semantic_review, engine.load_semantic_review
    def observe_run(**kwargs): calls.append(kwargs); return run(**kwargs)
    def observe_load(**kwargs): calls.append(kwargs); return load(**kwargs)
    monkeypatch.setattr(engine, "run_semantic_review", observe_run)
    monkeypatch.setattr(engine, "load_semantic_review", observe_load)
    config, sdk, flow = setup_review(tmp_path)
    with fitz.open(config.pdf_path) as doc:
        for _ in range(2): doc.new_page().insert_text((50, 80), "A fictional source page.")
        doc.saveIncr()
    result = flow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 6
    correction = sdk.requests[-2]
    assert json.loads(correction["input"][0]["content"][0]["text"])["stage"] == "correction"
    schema = correction["text"]["format"]["schema"]["properties"]["pages"]
    assert ("minItems" in schema) is enabled
    if enabled:
        assert schema["minItems"] == schema["maxItems"] == 3
        assert schema["items"]["properties"]["page_number"]["enum"] == [1, 2, 3]
    before = {p: p.read_bytes() for name in ("semantic_source", "semantic_audit")
              for p in (result.run_dir / name).rglob("*") if p.is_file()}
    monkeypatch.setattr(glue, "fresh_recipe", lambda *a, **k: pytest.fail("Resume/rebuild recalculated fresh policy"))
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(sdk.requests) == 6 and all(p.read_bytes() == data for p, data in before.items())
    assert all((KEY in kwargs) is enabled for kwargs in calls)


def test_policy_does_not_change_initial_primary_body_or_model(tmp_path, monkeypatch):
    fresh = glue.fresh_recipe
    requests = []
    for enabled in (False, True):
        folder = tmp_path / str(enabled); folder.mkdir()
        with monkeypatch.context() as scoped:
            if not enabled:
                def historical(*a, **k):
                    value = fresh(*a, **k); value.pop(KEY); return value
                scoped.setattr(glue, "fresh_recipe", historical)
            config, sdk, flow = setup_review(folder)
            assert flow.run(config).success
            requests.append(sdk.requests[0])
            assert sdk.requests[0]["model"] == "gpt-5.2"
            assert all(r["model"] == "gpt-6-astra" for r in sdk.requests[1:])
    assert {k:v for k,v in requests[0].items() if k != "timeout"} == {k:v for k,v in requests[1].items() if k != "timeout"}


def test_saved_policy_removal_cannot_reinterpret_completed_evidence(tmp_path):
    config, sdk, flow = setup_review(tmp_path)
    assert flow.run(config).success
    flow._last_state.settings["ordinary_semantic_audit_recipe"].pop(KEY)
    save_run_state_atomic(flow._last_paths.run_state_path, flow._last_state)
    with pytest.raises(glue.SemanticIntegrationError, match="context_evidence_changed"):
        flow.run(replace(config, resume=True))
    assert len(sdk.requests) == 4
