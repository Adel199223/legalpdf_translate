"""Fictional opt-in packaging boundaries; no retained document/provider data."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate import workflow_semantic_audit as integration
from legalpdf_translate.checkpoint import (ordinary_semantic_audit_recipe, SemanticAuditRecipeError,
    save_run_state_atomic)
from legalpdf_translate.prompt_builder import build_ar_token_retry_prompt, build_page_prompt
from legalpdf_translate.types import TargetLang, ImageMode, OcrEnginePolicy, OcrApiProvider
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_workflow_semantic_review_integration import saved_recipe, setup_review
from tests.test_workflow_semantic_audit_integration import offline


POLICY = "lossless_source_components_v3"
KEY = "primary_literal_packaging_version"
GOLDEN = Path(__file__).parent / "fixtures/primary_literal_packaging_legacy_prompt.json"


def test_schema_fresh_v3_saves_optional_primary_packaging_policy(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    assert recipe[KEY] == POLICY
    assert ordinary_semantic_audit_recipe(settings) == recipe


def test_schema_historical_v3_absence_remains_absent_and_disabled(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe.pop(KEY)
    before = json.dumps(settings, sort_keys=True)
    assert ordinary_semantic_audit_recipe(settings) == recipe
    assert KEY not in recipe and json.dumps(settings, sort_keys=True) == before


def test_schema_genuine_pre_change_v3_recipe_context_and_source_pack_bytes_match_exactly(tmp_path):
    fixture = GOLDEN.parent / "primary_literal_packaging_prechange_v3"
    receipt = json.loads((fixture / "generation_receipt.json").read_bytes())
    assert receipt["generator_glue_sha256"] == "87f900b60c152333ac62ad50e4dc151c0e13cc5b2ba7de7addb20aa696476a67"
    for name, digest in receipt["fixture_files"].items():
        assert hashlib.sha256((fixture / name).read_bytes()).hexdigest() == digest
    inputs = json.loads((fixture / "inputs.json").read_bytes())
    settings = inputs["settings"]
    recipe = settings["ordinary_semantic_audit_recipe"]
    config = SimpleNamespace(strip_bidi_controls=True, effort=SimpleNamespace(value=recipe["reasoning_effort"]),
        ocr_engine=OcrEnginePolicy.LOCAL, ocr_api_provider=OcrApiProvider.OPENAI,
        effort_policy=SimpleNamespace(value=recipe["effort_policy"]), target_lang=TargetLang.AR, image_mode=ImageMode.OFF)
    current = integration.fresh_recipe(config, recipe["model"], settings["ordinary_auto_layout_policy"],
        context_text=inputs["context_text"], context_hash=inputs["context_hash"])
    current.pop(KEY)
    current.pop("semantic_unit_reference_policy")
    current.pop("source_question_row_policy")
    current.pop("source_inventory_max_output_tokens")
    current.pop("semantic_source_review_policy")
    current.pop("semantic_page_coverage_policy")
    current.pop("semantic_review_model_policy")
    assert current == ordinary_semantic_audit_recipe(settings) == recipe
    state = SimpleNamespace(settings=settings, context_hash=inputs["context_hash"],
        pdf_fingerprint=inputs["pdf_sha256"], pages={"1": {}})
    integration.capture_context(state=state, run_dir=tmp_path,
        context_text=inputs["context_text"], context_hash=inputs["context_hash"])
    integration.capture_source(state=state, run_dir=tmp_path, **inputs["source_args"])
    assert (tmp_path / "semantic_context.json").read_bytes() == (fixture / "semantic_context.json").read_bytes()
    assert (tmp_path / "semantic_source/page_0001.json").read_bytes() == (fixture / "source_page_0001.json").read_bytes()


@pytest.mark.parametrize("value", [None, "", "unknown", "lossless_source_components_v4", False, [], {}])
def test_schema_explicit_invalid_primary_packaging_policy_is_not_absence(tmp_path, value):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe[KEY] = value
    with pytest.raises(SemanticAuditRecipeError, match="primary_literal_packaging"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("version", ["ordinary_semantic_audit_v1", "ordinary_semantic_audit_v2"])
def test_schema_v1_v2_cannot_accept_new_optional_v3_capability(tmp_path, version):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe["version"] = version
    recipe.pop("review_protocol")
    recipe.pop("semantic_unit_reference_policy")
    recipe.pop("source_question_row_policy")
    recipe.pop("source_inventory_max_output_tokens")
    recipe.pop("semantic_source_review_policy")
    recipe.pop("semantic_page_coverage_policy")
    recipe.pop("semantic_review_model_policy")
    if version.endswith("v1"):
        for name in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(name)
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)


def test_prompt_default_and_explicit_none_match_genuine_pre_change_golden():
    fixture = json.loads(GOLDEN.read_bytes())
    assert build_ar_token_retry_prompt(**fixture["retry_inputs"]) == fixture["retry_output"]
    assert build_ar_token_retry_prompt(**fixture["retry_inputs"], literal_wrapper_policy=None) == fixture["retry_output"]
    assert build_page_prompt(TargetLang.AR, **fixture["page_inputs"]) == fixture["page_output"]


def test_prompt_opt_in_allows_only_lossless_source_proven_components_and_keeps_inputs_exact():
    fixture = json.loads(GOLDEN.read_bytes())
    prompt = build_ar_token_retry_prompt(**fixture["retry_inputs"], literal_wrapper_policy=POLICY)
    assert "source-proven postal or address blocks" in prompt
    assert "character-for-character" in prompt and "every separator, street prefix and residual character" in prompt
    assert "Do not duplicate the original fused token" in prompt
    assert "Do not split or regroup names, addresses or other literal spans." not in prompt
    for marker in ("<<<BEGIN LOCKED TOKENS>>>", "<<<BEGIN TOKEN MISMATCH SUMMARY>>>",
                   "<<<BEGIN SOURCE PAGE>>>", "<<<BEGIN PRIOR OUTPUT>>>"):
        assert prompt[prompt.index(marker):] == fixture["retry_output"][fixture["retry_output"].index(marker):]


@pytest.mark.parametrize("policy", ["unknown", "", False, [], {}])
def test_prompt_unknown_policy_fails_closed(policy):
    with pytest.raises(ValueError, match="Unsupported primary literal wrapper policy"):
        build_ar_token_retry_prompt("fictional prior", [], literal_wrapper_policy=policy)


def test_workflow_evaluator_omits_disabled_optional_keyword_from_legacy_delegate(monkeypatch):
    calls = []
    def evaluate(*args, **kwargs):
        calls.append(kwargs)
        return object()
    monkeypatch.setattr(workflow_module, "evaluate_workflow_output", evaluate)
    workflow = object.__new__(TranslationWorkflow)
    workflow._evaluate_output("fictional", TargetLang.AR)
    workflow._evaluate_output("fictional", TargetLang.AR, literal_wrapper_policy=POLICY)
    assert "literal_wrapper_policy" not in calls[0]
    assert calls[1]["literal_wrapper_policy"] == POLICY


@pytest.mark.parametrize("enabled", [False, True])
def test_primary_initial_only_policy_and_conditional_retry_prompt_routing(tmp_path, monkeypatch, enabled):
    if not enabled:
        fresh = integration.fresh_recipe
        def historical(*args, **kwargs):
            recipe = fresh(*args, **kwargs)
            recipe.pop(KEY)
            return recipe
        monkeypatch.setattr(integration, "fresh_recipe", historical)
    config, sdk, workflow = setup_review(tmp_path)
    evaluate = workflow._evaluate_output
    calls = []
    def require_retry(raw, lang, **kwargs):
        calls.append(kwargs)
        result = evaluate(raw, lang, **kwargs)
        if len(calls) == 1:
            assert result.ok
            return replace(result, ok=False, validator_failed=True,
                ar_violation_kind="latin_or_digits_outside_wrapped_tokens",
                defect_reason="Fictional fixture forces the token-retry routing boundary.")
        return result
    monkeypatch.setattr(workflow, "_evaluate_output", require_retry)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(calls) == 2 and len(sdk.requests) == 5
    assert calls[0].get("literal_wrapper_policy") == (POLICY if enabled else None)
    assert ("literal_wrapper_policy" in calls[0]) is enabled
    assert (calls[1].get("literal_wrapper_policy") == POLICY) is enabled
    assert ("literal_wrapper_policy" in calls[1]) is enabled
    retry_prompt = sdk.requests[1]["input"][0]["content"][0]["text"]
    assert ("source-proven postal or address blocks" in retry_prompt) is enabled
    assert (KEY in workflow._last_state.settings["ordinary_semantic_audit_recipe"]) is enabled


def test_historical_v3_absence_keeps_initial_request_exact_and_completed_resume_unmodified(tmp_path, monkeypatch):
    requests, evaluator_kwargs = [], []
    for enabled in (True, False):
        directory = tmp_path / ("enabled" if enabled else "historical")
        directory.mkdir()
        with monkeypatch.context() as scoped:
            if not enabled:
                fresh = integration.fresh_recipe
                def historical(*args, **kwargs):
                    recipe = fresh(*args, **kwargs)
                    recipe.pop(KEY)
                    return recipe
                scoped.setattr(integration, "fresh_recipe", historical)
            config, sdk, workflow = setup_review(directory)
            evaluate = workflow._evaluate_output
            def observe(raw, lang, **kwargs):
                evaluator_kwargs.append(kwargs)
                return evaluate(raw, lang, **kwargs)
            scoped.setattr(workflow, "_evaluate_output", observe)
            result = workflow.run(config)
            assert result.success, result.error
            requests.append(sdk.requests[0])
        protected = {path: path.read_bytes() for name in ("semantic_audit", "semantic_source")
            for path in (result.run_dir / name).rglob("*") if path.is_file()}
        protected[result.run_dir / "semantic_context.json"] = (result.run_dir / "semantic_context.json").read_bytes()
        assert workflow.run(replace(config, resume=True)).success
        assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
        assert len(sdk.requests) == 4 and all(path.read_bytes() == raw for path, raw in protected.items())
        assert (KEY in workflow._last_state.settings["ordinary_semantic_audit_recipe"]) is enabled
    for key in ("model", "instructions", "input", "reasoning"):
        assert requests[0][key] == requests[1][key]
    assert evaluator_kwargs[0]["literal_wrapper_policy"] == POLICY
    assert "literal_wrapper_policy" not in evaluator_kwargs[1]


@pytest.mark.parametrize("mutation", ["remove", "unknown"])
def test_completed_policy_change_fails_context_binding_before_any_new_send(tmp_path, mutation):
    config, sdk, workflow = setup_review(tmp_path)
    result = workflow.run(config)
    assert result.success
    recipe = workflow._last_state.settings["ordinary_semantic_audit_recipe"]
    if mutation == "remove":
        recipe.pop(KEY)
        expected_error, message = integration.SemanticIntegrationError, "^semantic_audit_context_evidence_changed$"
    else:
        recipe[KEY] = "unknown"
        expected_error, message = SemanticAuditRecipeError, "^semantic_audit_invalid_primary_literal_packaging$"
    save_run_state_atomic(workflow._last_paths.run_state_path, workflow._last_state)
    with pytest.raises(expected_error, match=message):
        workflow.run(replace(config, resume=True))
    assert len(sdk.requests) == 4


def fictional_address_source(config):
    import fitz
    from tests.test_ar_lossless_source_components import SOURCE
    from legalpdf_translate.ar_literal_fidelity import visible_text
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((48, 80), visible_text(SOURCE), fontsize=11)
        config.pdf_path.write_bytes(document.tobytes())


def test_source_proven_fused_primary_accepts_without_retry_and_preserves_every_visible_character(tmp_path, monkeypatch):
    from tests.test_ar_lossless_source_components import PRIMARY, token
    from legalpdf_translate.ar_literal_fidelity import visible_text
    config, sdk, workflow = setup_review(tmp_path, corrected=False)
    fictional_address_source(config)
    create = sdk.create
    def response(**request):
        result = create(**request)
        if not request.get("text", {}).get("format"):
            result.output_text = "```\n" + PRIMARY + "\n```"
        return result
    monkeypatch.setattr(sdk.responses, "create", response)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 4 and sdk.stages() == ["source_inventory", "correction", "verification"]
    primary = (result.run_dir / "pages/page_0001.txt").read_text(encoding="utf-8").strip()
    assert visible_text(primary) == visible_text(PRIMARY)
    assert token("8") in primary and token("4321") in primary and token("R") in primary


def test_retry_still_rejects_real_visible_residual_loss_after_lossless_initial_packaging(tmp_path, monkeypatch):
    from tests.test_ar_lossless_source_components import PRIMARY, token
    config, sdk, workflow = setup_review(tmp_path, corrected=False)
    fictional_address_source(config)
    evaluations, selected = [], []
    evaluate = workflow._evaluate_output
    def force_other_compliance_retry(raw, lang, **kwargs):
        result = evaluate(raw, lang, **kwargs)
        evaluations.append((kwargs, result))
        if len(evaluations) == 1:
            assert result.ok and token("R") in result.normalized_text
            selected.append(result.normalized_text)
            return replace(result, ok=False, validator_failed=True,
                ar_violation_kind="latin_or_digits_outside_wrapped_tokens",
                defect_reason="Fictional fixture forces a separate compliance retry.")
        return result
    monkeypatch.setattr(workflow, "_evaluate_output", force_other_compliance_retry)
    create = sdk.create
    def response(**request):
        result = create(**request)
        assert not request.get("text", {}).get("format"), "Failed primary must not dispatch a semantic subpass"
        body = PRIMARY if len(sdk.requests) == 1 else selected[0].replace(token("R"), "")
        result.output_text = "```\n" + body + "\n```"
        return result
    monkeypatch.setattr(sdk.responses, "create", response)
    result = workflow.run(config)
    assert not result.success and len(sdk.requests) == 2 and not sdk.stages()
    assert evaluations[0][0]["literal_wrapper_policy"] == POLICY
    assert evaluations[1][0]["literal_wrapper_policy"] == POLICY
    assert evaluations[1][1].ar_violation_kind == "correction_literal_fidelity_loss"
