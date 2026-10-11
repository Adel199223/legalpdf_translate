"""Persisted primary assembly recipes remain independent of pricing revisions."""
import pytest
from legalpdf_translate.checkpoint import primary_assembly_recipe
from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy


def test_absent_recipe_preserves_legacy_assembly():
    assert primary_assembly_recipe({"ordinary_auto_layout_policy": frozen_automatic_layout_policy()}) is None


@pytest.mark.parametrize("recipe", [None, {}, {"version": "unknown", "ordinary_auto_layout_policy": "a"*64},
    {"version": "terminal_labeled_folio_v1", "ordinary_auto_layout_policy": "b"*64},
    {"version": "terminal_labeled_folio_v1", "ordinary_auto_layout_policy": 1}])
def test_invalid_or_mismatched_recipe_is_rejected(recipe):
    with pytest.raises(ValueError, match="saved primary assembly recipe"):
        primary_assembly_recipe({"ordinary_auto_layout_policy": frozen_automatic_layout_policy(), "primary_assembly_recipe": recipe})


def test_saved_recipe_is_validated_and_copied():
    policy=frozen_automatic_layout_policy()
    recipe={"version":"terminal_labeled_folio_v1","ordinary_auto_layout_policy":policy}
    result=primary_assembly_recipe({"ordinary_auto_layout_policy":policy,"primary_assembly_recipe":recipe})
    assert result==recipe and result is not recipe

from pathlib import Path
import json
from decimal import Decimal
from datetime import date
from hashlib import sha256
from fastapi.testclient import TestClient
from legalpdf_translate import ordinary_layout_accounting as layout_accounting_module
from legalpdf_translate.accounting_policy import OrdinaryAccountingPolicy
from legalpdf_translate.ordinary_layout_contracts import LayoutSuggestionPolicy
from tests.test_ordinary_auto_layout_recovery import offline, _success_layout_provider
from tests.test_ordinary_auto_layout_workflow import _app, _source, _start, _wait

def test_terminal_folio_recipe_survives_catalog_resume(tmp_path, monkeypatch):
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    output.mkdir()
    _source(source, ("digital",))
    original_catalog = layout_accounting_module.layout_accounting_policy()
    args = original_catalog.accounting_arguments(today=date(2026, 10, 9))
    args["dispatch_limits"]["openai:layout_suggestion:gpt-5.2"]["max_output_tokens"] = 8000
    old_catalog = OrdinaryAccountingPolicy.from_mapping(
        pricing=args["pricing_snapshot"], limits=args["dispatch_limits"])
    old_catalog = OrdinaryAccountingPolicy(old_catalog._pricing_json, old_catalog._limits_json,
        date(2026, 10, 9))
    app, jobs, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        ("English page one alpha 42\nPage 1",), (1,), failed_page=1, failure="incomplete")
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        with monkeypatch.context() as old:
            old.setattr(layout_accounting_module, "layout_accounting_policy", lambda: old_catalog)
            old.setattr(layout_accounting_module, "PAGE_CEILING", Decimal("0.812"))
            old.setattr(layout_accounting_module.OrdinaryLayoutAccounting, "policy",
                lambda self, job: LayoutSuggestionPolicy("gpt-5.2", ".812", ".812",
                    max_output_tokens=8000, timeout_seconds=240.0))
            original_id = _start(client, source, output, "EN", start=1, end=1, image_mode="off")
            failed = _wait(jobs, original_id)
            assert failed["result"]["automatic_layout"]["status"] == "raw_fallback"
            assert layout_requests[0]["max_output_tokens"] == 8000
            checkpoint=json.loads((Path(failed["result"]["run_dir"])/"run_state.json").read_text(encoding="utf-8"))
            assert checkpoint["settings"]["primary_assembly_recipe"]["ordinary_auto_layout_policy"]==checkpoint["settings"]["ordinary_auto_layout_policy"]
            raw_path=Path(failed["result"]["save_seed"]["output_docx"])
            original_raw=raw_path.read_bytes()
            from zipfile import ZipFile
            with ZipFile(raw_path) as package:
                assert not any(b"PAGE" in package.read(name) for name in package.namelist() if name.startswith("word/footer"))

        assert len(translation_sdk.requests) == len(layout_requests) == 1
        manager = app.state.ordinary_layouts.manager_for_context(
            app.state.shadow_context, "shadow", "fictional")
        manager.suggestion_policy = app.state.ordinary_layouts._accounting.policy
        manager.provider_factory = _success_layout_provider(app, layout_requests)
        resumed_id = _start(client, source, output, "EN", start=1, end=1,
            image_mode="off", resume=True)
        resumed = _wait(jobs, resumed_id)
        assert resumed["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert raw_path.read_bytes()==original_raw
        assert len(translation_sdk.requests) == len(layout_requests) == 1
        started = client.post(f"/api/translation/jobs/{resumed_id}/layout/recover" + scope)
        assert started.status_code == 200, started.text
        recovered = _wait(jobs, resumed_id)
        assert recovered["result"]["automatic_layout"]["status"] == "automatic_unreviewed", recovered
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 2
        assert layout_requests[1]["max_output_tokens"] == 32000
        shown = client.get(f"/api/translation/jobs/{resumed_id}" + scope).json()["normalized_payload"]["job"]
        assert shown["layout_costs"]["operations"] == 2
        downloaded = client.get(f"/api/translation/jobs/{resumed_id}/artifact/output_docx" + scope)
        assert downloaded.status_code == 200 and sha256(downloaded.content).hexdigest() == shown["delivery"]["sha256"]

@pytest.mark.parametrize("bad_recipe", [None, {"version":"unknown","ordinary_auto_layout_policy":"a"*64}, {"version":"terminal_labeled_folio_v1","ordinary_auto_layout_policy":"b"*64}, {"version":"terminal_labeled_folio_v1","ordinary_auto_layout_policy":"malformed"}])
def test_invalid_loaded_recipe_refuses_offline_rebuild_before_output_write(tmp_path, bad_recipe):
    from legalpdf_translate.checkpoint import build_run_paths, new_run_state, save_run_state_atomic, load_run_state, PrimaryAssemblyRecipeError
    from legalpdf_translate.types import RunConfig, TargetLang, ReasoningEffort, ImageMode
    from legalpdf_translate.workflow import TranslationWorkflow
    source=tmp_path/"source.pdf"; source.write_bytes(b"fictional")
    config=RunConfig(pdf_path=source,output_dir=tmp_path/"out",target_lang=TargetLang.EN,effort=ReasoningEffort.HIGH,image_mode=ImageMode.OFF)
    paths=build_run_paths(config.output_dir,source,config.target_lang)
    state=new_run_state(config=config,paths=paths,pdf_fingerprint="fictional",context_hash="",total_pages=1,selected_pages=[1],ordinary_auto_layout_policy=frozen_automatic_layout_policy())
    state.settings["primary_assembly_recipe"]=bad_recipe
    if isinstance(bad_recipe, dict) and bad_recipe.get("ordinary_auto_layout_policy")=="malformed":
        state.settings["ordinary_auto_layout_policy"]="malformed"
    save_run_state_atomic(paths.run_state_path,state)
    output=tmp_path/"retained.docx"; output.write_bytes(b"unchanged retained output")
    workflow=object.__new__(TranslationWorkflow)
    workflow._normalize_config=lambda value:value
    workflow._validate_config=lambda value:None
    workflow._rebuild_docx_locked=lambda *args,**kwargs: pytest.fail("invalid recipe reached output assembly")
    with pytest.raises(PrimaryAssemblyRecipeError): load_run_state(paths.run_state_path)
    with pytest.raises(PrimaryAssemblyRecipeError): workflow.rebuild_docx(config)
    assert output.read_bytes()==b"unchanged retained output"
