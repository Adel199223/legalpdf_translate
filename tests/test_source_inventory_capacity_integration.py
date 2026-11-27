"""Saved inventory-only capacity and genuine pre-budget compact replay."""
from dataclasses import asdict, fields, replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
from tests.test_workflow_semantic_review_integration import without_repair_policy

from legalpdf_translate import ordinary_semantic_review as engine
from legalpdf_translate import workflow_semantic_audit as glue
from legalpdf_translate.checkpoint import (SemanticAuditRecipeError,
    ordinary_semantic_audit_recipe, save_run_state_atomic)
from legalpdf_translate.ordinary_semantic_audit import SemanticAuditError, SemanticAuditRecipe
from legalpdf_translate.types import ImageMode, TargetLang, OcrEnginePolicy, OcrApiProvider
from legalpdf_translate.usage_accounting import _ceiling_for
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_ordinary_semantic_unit_refs import Client
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_workflow_semantic_review_integration import saved_recipe, setup_review


KEY = "source_inventory_max_output_tokens"
POLICY = "caller_unit_refs_v1"
FIXTURE = Path(__file__).parent / "fixtures/source_inventory_capacity_prechange_v3"


def test_fresh_v3_saves_inventory_only_budget_without_changing_shared_recipe(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    assert recipe[KEY] == 64000 and recipe["semantic_unit_reference_policy"] == POLICY
    assert recipe["max_output_tokens"] == 32000 and recipe["timeout_seconds"] == 480
    assert ordinary_semantic_audit_recipe(settings) == recipe


@pytest.mark.parametrize("value", [None, False, True, "64000", 64000.0, 32000, 63999, 128000, [], {}])
def test_invalid_explicit_inventory_budget_is_not_historical_absence(tmp_path, value):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe[KEY] = value
    with pytest.raises(SemanticAuditRecipeError, match=KEY):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("policy", [None, "absent", "unknown"])
def test_inventory_budget_requires_selected_compact_protocol(tmp_path, policy):
    _, recipe, settings = saved_recipe(tmp_path)
    if policy == "absent":
        recipe.pop("semantic_unit_reference_policy")
    else:
        recipe["semantic_unit_reference_policy"] = policy
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("version", ["ordinary_semantic_audit_v1", "ordinary_semantic_audit_v2"])
def test_legacy_key_sets_reject_inventory_budget_even_with_valid_value(tmp_path, version):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe["version"] = version
    for key in ("review_protocol", "primary_literal_packaging_version",
                "semantic_unit_reference_policy", "source_question_row_policy"):
        recipe.pop(key)
    if version.endswith("v1"):
        for key in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(key)
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)


def test_old_v3_absence_stays_absent_without_inserting_a_default(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe.pop(KEY)
    before = json.dumps(settings, sort_keys=True)
    assert ordinary_semantic_audit_recipe(settings) == recipe
    assert KEY not in recipe and json.dumps(settings, sort_keys=True) == before


@pytest.mark.parametrize("enabled", [False, True])
def test_saved_budget_routes_run_load_actual_accounting_and_zero_call_replay(tmp_path, monkeypatch, enabled):
    if not enabled:
        fresh = glue.fresh_recipe
        def historical(*args, **kwargs):
            recipe = fresh(*args, **kwargs)
            recipe.pop(KEY)
            return recipe
        monkeypatch.setattr(glue, "fresh_recipe", historical)
    config, sdk, flow = setup_review(tmp_path)
    observed = []
    run, load = engine.run_semantic_review, engine.load_semantic_review
    def observe_run(**kwargs):
        observed.append(("run", kwargs))
        return run(**kwargs)
    def observe_load(**kwargs):
        observed.append(("load", kwargs))
        return load(**kwargs)
    monkeypatch.setattr(engine, "run_semantic_review", observe_run)
    monkeypatch.setattr(engine, "load_semantic_review", observe_load)
    result = flow.run(config)
    assert result.success, result.error
    caps = [request["max_output_tokens"] for request in sdk.requests[1:]]
    assert caps == [64000 if enabled else 32000, 32000, 32000]
    assert all(request["reasoning"]["effort"] == "high" for request in sdk.requests[1:])
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert (KEY in saved) is enabled and saved["max_output_tokens"] == 32000
    journal_path = flow._dispatch_accounting.journal_path
    journal = json.loads(journal_path.read_bytes())
    begins = [event for event in journal["events"]
              if event["event"] == "begin" and event["purpose"] == "semantic_audit"]
    assert [event["bounds"]["max_output_tokens"] for event in begins] == caps
    snapshot = flow._dispatch_accounting.pricing_snapshot
    for event in begins:
        expected = _ceiling_for(pricing_snapshot=snapshot, provider=event["provider"],
            model=event["requested_model"], bounds=event["bounds"], hard=False)
        # This workflow fixture has no verified conservative input bound.
        # Keep its soft-accounting null ceiling; the engine's separate real
        # transport/reservation fixture supplies verified bounds and checks holds.
        assert (Decimal(event["ceiling_usd"]) if event["ceiling_usd"] is not None else None) == expected
    if enabled and begins[0]["ceiling_usd"] is not None:
        smaller = dict(begins[0]["bounds"], max_output_tokens=32000)
        old_ceiling = _ceiling_for(pricing_snapshot=snapshot, provider=begins[0]["provider"],
            model=begins[0]["requested_model"], bounds=smaller, hard=False)
        assert Decimal(begins[0]["ceiling_usd"]) > old_ceiling
    protected = {p: p.read_bytes() for name in ("semantic_audit", "semantic_source")
                 for p in (result.run_dir / name).rglob("*") if p.is_file()}
    protected[result.run_dir / "semantic_context.json"] = (result.run_dir / "semantic_context.json").read_bytes()
    protected[journal_path] = journal_path.read_bytes()
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(sdk.requests) == 4 and all(p.read_bytes() == raw for p, raw in protected.items())
    assert any(kind == "load" for kind, _ in observed)
    assert all((KEY in kwargs) is enabled for _, kwargs in observed)
    assert all(kwargs.get(KEY, 64000) == 64000 for _, kwargs in observed)
    report = json.loads(result.run_summary_path.read_bytes())
    assert report["totals"]["total_tokens"] == 227
    assert report["ordinary_semantic_audit"]["accounting"]["call_count"] == 3


@pytest.mark.parametrize("mutation", ["remove", "invalid"])
def test_changed_saved_budget_fails_before_resume_or_rebuild_can_send(tmp_path, mutation):
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    protected = {p: p.read_bytes() for name in ("semantic_audit", "semantic_source")
                 for p in (result.run_dir / name).rglob("*") if p.is_file()}
    recipe = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    if mutation == "remove":
        recipe.pop(KEY)
    else:
        recipe[KEY] = 32000
    save_run_state_atomic(flow._last_paths.run_state_path, flow._last_state)
    with pytest.raises(ValueError):
        flow.run(replace(config, resume=True))
    with pytest.raises(ValueError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == 4 and all(p.read_bytes() == raw for p, raw in protected.items())


@pytest.mark.parametrize("enabled", [False, True])
def test_incomplete_inventory_retains_raw_and_never_rebuys_or_advances(tmp_path, monkeypatch, enabled):
    if not enabled:
        fresh = glue.fresh_recipe
        def historical(*args, **kwargs):
            recipe = fresh(*args, **kwargs)
            recipe.pop(KEY)
            return recipe
        monkeypatch.setattr(glue, "fresh_recipe", historical)
    config, sdk, flow = setup_review(tmp_path, failure_stage="source_inventory", failure="incomplete")
    result = flow.run(config)
    assert not result.success and result.error == "semantic_audit_provider_incomplete"
    assert sdk.requests[-1]["max_output_tokens"] == (64000 if enabled else 32000)
    evidence = result.run_dir / "semantic_audit"
    before = {p: p.read_bytes() for p in evidence.rglob("*") if p.is_file()}
    assert (evidence / "source_inventory/raw_receipt.json").is_file()
    assert not (evidence / "correction").exists() and not (evidence / "manifest.json").exists()
    assert not flow.run(replace(config, resume=True)).success
    with pytest.raises(glue.SemanticIntegrationError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == 2 and all(p.read_bytes() == raw for p, raw in before.items())


def test_genuine_prebudget_compact_recipe_requests_raw_context_and_binding_replay_exactly(tmp_path):
    inputs = json.loads((FIXTURE / "inputs.json").read_bytes())
    receipt = json.loads((FIXTURE / "generation_receipt.json").read_bytes())
    assert receipt["generator_engine_sha256"] == "b4b13398b5bd5660ba3c327aec65c29a49537c0882566bf0d6365ff328a57efe"
    for name, digest in receipt["fixture_files"].items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest
    run_dir = tmp_path / "saved"
    shutil.copytree(FIXTURE / "run", run_dir)
    source = tmp_path / "source_stub.txt"
    source.write_bytes((FIXTURE / "source_stub.txt").read_bytes())
    settings = inputs["settings"]
    saved = ordinary_semantic_audit_recipe(settings)
    assert KEY not in saved and saved["semantic_unit_reference_policy"] == POLICY
    config = SimpleNamespace(pdf_path=source, target_lang=TargetLang.AR, image_mode=ImageMode.OFF, strip_bidi_controls=True,
        ocr_engine=OcrEnginePolicy.LOCAL, ocr_api_provider=OcrApiProvider.OPENAI,
        effort=SimpleNamespace(value=saved["reasoning_effort"]), effort_policy=SimpleNamespace(value=saved["effort_policy"]))
    fresh = glue.fresh_recipe(config, saved["model"], settings["ordinary_auto_layout_policy"],
        context_text=inputs["context_text"], context_hash=inputs["context_hash"])
    fresh.pop(KEY)
    fresh.pop("semantic_source_review_policy")
    fresh.pop("semantic_page_coverage_policy")
    fresh.pop("semantic_review_model_policy")
    assert fresh["primary_literal_packaging_version"] == "lossless_source_components_v3"
    assert saved["primary_literal_packaging_version"] == "lossless_source_components_v1"
    # Compare the historical policy projection; the saved fixture is never upgraded.
    fresh["primary_literal_packaging_version"] = saved["primary_literal_packaging_version"]
    assert fresh == saved
    state = SimpleNamespace(settings=settings, context_hash=inputs["context_hash"], pdf_fingerprint=inputs["pdf_sha256"],
        pages={"1": inputs["page_record"]}, selection_page_count=1, selection_start_page=1, selection_end_page=1)
    before = {p: p.read_bytes() for p in run_dir.rglob("*") if p.is_file()}
    glue.capture_context(state=state, run_dir=run_dir, context_text=inputs["context_text"], context_hash=inputs["context_hash"])
    glue.capture_source(state=state, run_dir=run_dir, **inputs["source_args"])
    pages, _, context = glue._pages(state=state, config=config, run_dir=run_dir, pages_dir=run_dir / "pages")
    page_descriptors = json.loads(json.dumps([asdict(page) for page in pages]))
    for descriptor in page_descriptors:
        assert descriptor.pop("source_acronyms") == []
    assert page_descriptors == inputs["engine_pages"]
    recipe = SemanticAuditRecipe(**{f.name: saved[f.name] for f in fields(SemanticAuditRecipe) if f.name in saved}, context_text=context)
    historical_descriptor = asdict(recipe)
    assert "source_inline_address_join_policy" not in saved
    assert historical_descriptor.pop("source_inline_address_join_policy") is None
    assert historical_descriptor == inputs["engine_recipe"]
    kwargs = dict(pages=pages, recipe=recipe, pdf_sha256=inputs["pdf_sha256"], semantic_unit_reference_policy=POLICY)
    loaded = engine.load_semantic_review(**kwargs, evidence_dir=run_dir / "semantic_audit")
    assert loaded.reused and loaded.binding_sha256 == receipt["binding_sha256"]
    assert all(p.read_bytes() == raw for p, raw in before.items())
    client = Client()
    client.model = saved["model"]
    result = engine.run_semantic_review(**kwargs, evidence_dir=tmp_path / "fresh", client=client)
    assert result.binding_sha256 == receipt["binding_sha256"]
    assert json.loads(json.dumps(client.requests)) == inputs["requests"]
    assert all(request["max_output_tokens"] == 32000 for request in client.requests)
    assert engine.semantic_review_source_fingerprint(**{k: v for k, v in kwargs.items() if k != "evidence_dir"}) != engine.semantic_review_source_fingerprint(**kwargs, source_inventory_max_output_tokens=64000)
    with pytest.raises(SemanticAuditError):
        engine.run_semantic_review(**kwargs, evidence_dir=run_dir / "semantic_audit", client=client, source_inventory_max_output_tokens=64000)
    assert len(client.requests) == 3 and all(p.read_bytes() == raw for p, raw in before.items())
