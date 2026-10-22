"""Ordinary-entry saved policy routing, true loss, and zero-call replay."""
from dataclasses import replace

import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy

from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.ar_literal_fidelity import visible_text
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_ar_prefixed_postal_packaging_v2 import FIRST, POSTAL, SOURCE, token, V1, V2
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_workflow_semantic_review_integration import setup_review

KEY = "primary_literal_packaging_version"


def postal_pdf(config):
    import fitz
    first = "Palácio da Justiça da Aurora - Rua Dr. Flores 18"
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((48, 80), first + "\n" + POSTAL, fontsize=11)
        config.pdf_path.write_bytes(document.tobytes())
    return first


def test_real_ordinary_entry_new_witness_needs_no_retry_and_replays_without_dispatch(tmp_path, monkeypatch):
    config, sdk, flow = setup_review(tmp_path, corrected=False)
    first = postal_pdf(config)
    primary = "العنوان: " + token(first + " " + POSTAL) + "\n" + token("R")
    create = sdk.create
    def response(**request):
        result = create(**request)
        if not request.get("text", {}).get("format"):
            result.output_text = "```\n" + primary + "\n```"
        return result
    monkeypatch.setattr(sdk.responses, "create", response)
    result = flow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 4
    assert flow._last_state.settings["ordinary_semantic_audit_recipe"][KEY] == V2
    selected = (result.run_dir / "pages/page_0001.txt").read_text(encoding="utf-8").strip()
    assert visible_text(selected) == visible_text(primary)
    assert token(first) in selected and token(POSTAL) in selected and token("R") in selected
    protected = {p: p.read_bytes() for name in ("semantic_audit", "semantic_source")
                 for p in (result.run_dir / name).rglob("*") if p.is_file()}
    protected[result.run_dir / "semantic_context.json"] = (result.run_dir / "semantic_context.json").read_bytes()
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(sdk.requests) == 4 and all(p.read_bytes() == b for p, b in protected.items())


@pytest.mark.parametrize("policy", [None, V1, V2])
def test_saved_policy_controls_retry_kwargs_and_exact_prompt_without_upgrading_history(tmp_path, monkeypatch, policy):
    fresh = glue.fresh_recipe
    def select(*args, **kwargs):
        recipe = fresh(*args, **kwargs)
        if policy is None:
            recipe.pop(KEY)
        else:
            recipe[KEY] = policy
        return recipe
    monkeypatch.setattr(glue, "fresh_recipe", select)
    config, sdk, flow = setup_review(tmp_path)
    evaluate = flow._evaluate_output
    seen = []
    def force_retry(raw, lang, **kwargs):
        seen.append(kwargs)
        result = evaluate(raw, lang, **kwargs)
        if len(seen) == 1:
            assert result.ok
            return replace(result, ok=False, validator_failed=True,
                ar_violation_kind="latin_or_digits_outside_wrapped_tokens",
                defect_reason="Fictional forced routing boundary.")
        return result
    monkeypatch.setattr(flow, "_evaluate_output", force_retry)
    result = flow.run(config)
    assert result.success, result.error
    assert seen[0].get("literal_wrapper_policy") == policy
    assert ("literal_wrapper_policy" in seen[0]) is (policy is not None)
    assert ("literal_wrapper_policy" in seen[1]) is (policy == V2)
    if policy == V2:
        assert seen[1]["literal_wrapper_policy"] == V2
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved.get(KEY) == policy and (KEY in saved) is (policy is not None)
    requests = len(sdk.requests)
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(sdk.requests) == requests


@pytest.mark.parametrize("lose", [False, True])
def test_real_entry_retry_exact_line_restoration_passes_but_loss_stops_before_audit(tmp_path, monkeypatch, lose):
    config, sdk, flow = setup_review(tmp_path, corrected=False)
    first = postal_pdf(config)
    primary = "العنوان: " + token(first + " " + POSTAL) + "\n" + token("R")
    corrected = "العنوان: " + token(first) + "\n" + token(POSTAL) + ("" if lose else "\n" + token("R"))
    create = sdk.create
    def response(**request):
        result = create(**request)
        if not request.get("text", {}).get("format"):
            result.output_text = "```\n" + (primary if len(sdk.requests) == 1 else corrected) + "\n```"
        return result
    monkeypatch.setattr(sdk.responses, "create", response)
    evaluate = flow._evaluate_output
    seen = []
    def force_retry(raw, lang, **kwargs):
        result = evaluate(raw, lang, **kwargs)
        seen.append(result)
        if len(seen) == 1:
            # Retain the fused primary as the anti-loss reference to exercise
            # the source-line proof rather than the initial wrapper split.
            prior = evaluate(raw, lang, **{k: v for k, v in kwargs.items() if k != "literal_wrapper_policy"})
            return prior
        return result
    monkeypatch.setattr(flow, "_evaluate_output", force_retry)
    result = flow.run(config)
    assert result.success is (not lose)
    assert len(sdk.requests) == (2 if lose else 5)
    assert seen[1].ok is (not lose)
    if lose:
        assert seen[1].ar_violation_kind == "correction_literal_fidelity_loss" and not sdk.stages()
