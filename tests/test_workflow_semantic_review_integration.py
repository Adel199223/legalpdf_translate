"""Fictional v3 workflow boundaries and exact retained audit compatibility."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from legalpdf_translate import ordinary_semantic_audit as historical
from legalpdf_translate import workflow_semantic_audit as integration
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.checkpoint import (SemanticAuditRecipeError, new_run_state,
    build_run_paths, ordinary_semantic_audit_recipe, sha256_of_file, sha256_of_text)
from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.types import ImageMode, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_new_run_preflight import config_for
from tests.test_workflow_semantic_audit_integration import offline
from tests.test_workflow_semantic_audit_integration import PRIMARY, CORRECTED, text
from tests.semantic_review_fakes import VERSIONS, UNIT_REF_VERSIONS, ALL_FORMAT_NAMES, review_response


STAGES = tuple(VERSIONS)
STAGE_USAGE = {"source_inventory": (11, 7), "correction": (13, 9), "verification": (17, 10)}


@pytest.fixture(autouse=True)
def without_repair_policy(monkeypatch):
    """Keep this retained three-stage contract explicit as fresh policy evolves."""
    fresh = integration.fresh_recipe
    def historical(*args, **kwargs):
        saved = fresh(*args, **kwargs)
        saved.pop("semantic_repair_policy", None)
        saved.pop("semantic_literal_authority_policy", None)
        saved.pop("semantic_enclosure_authority_policy", None)
        saved.pop("ocr_text_transport_policy", None)
        return saved
    monkeypatch.setattr(integration, "fresh_recipe", historical)


class ReviewSDK:
    base_url = "https://api.openai.com/v1/"

    def __init__(self, *, failure_stage=None, failure=None, corrected=True):
        self.requests = []
        self.failure_stage, self.failure = failure_stage, failure
        self.corrected = corrected
        self.on_stage = None
        self.responses = SimpleNamespace(create=self.create,
            with_raw_response=SimpleNamespace(create=self.raw_create))

    def raw_create(self, **request):
        response = self.create(**request)
        return SimpleNamespace(content=json.dumps(vars(response), ensure_ascii=False).encode())

    def create(self, **request):
        self.requests.append(request)
        name = request.get("text", {}).get("format", {}).get("name")
        stage = None
        if name in ALL_FORMAT_NAMES:
            payload = json.loads(request["input"][0]["content"][0]["text"])
            stage = payload["stage"]
            if self.on_stage is not None:
                self.on_stage(stage)
            if stage == self.failure_stage and self.failure == "transport":
                from legalpdf_translate.openai_client import APIConnectionError
                raise APIConnectionError(request=None)
            corrections = {p["page"]: CORRECTED for p in payload.get("primary_pages", [])} if self.corrected else None
            response = review_response(payload, corrected_by_page=corrections,
                unit_references=name in UNIT_REF_VERSIONS.values())
            if stage == self.failure_stage and self.failure == "unresolved":
                if stage == "source_inventory":
                    response["claims"][0]["unresolved"] = True
                elif stage == "correction":
                    response["claim_coverage"][0]["status"] = "unresolved"
                else:
                    response["claim_results"][0]["status"] = "unresolved"
            raw = json.dumps(response, ensure_ascii=False)
            input_tokens, output_tokens = STAGE_USAGE[stage]
        else:
            assert name is None, "Unexpected fictional provider schema"
            raw = "```text\n" + PRIMARY + "\n```"
            input_tokens, output_tokens = 100, 60
        failed = stage == self.failure_stage
        return SimpleNamespace(id=f"v3-fictional-{len(self.requests)}", model=request["model"],
            status="incomplete" if failed and self.failure == "incomplete" else "completed",
            incomplete_details={"reason": "max_output_tokens"} if failed and self.failure == "incomplete" else None,
            service_tier="default", output_text=raw,
            output=[{"type": "refusal", "refusal": "fictional refusal"}] if failed and self.failure == "refused" else [],
            usage=None if failed and self.failure == "unknown_usage" else {
                "input_tokens": input_tokens, "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                **({"input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0}}
                   if request["model"] == "gpt-6-astra" else {})})

    def stages(self):
        return [json.loads(r["input"][0]["content"][0]["text"])["stage"]
                for r in self.requests if r.get("text", {}).get("format", {}).get("name") in ALL_FORMAT_NAMES]


def setup_review(tmp_path, *, mode=ImageMode.OFF, **sdk_options):
    config = replace(config_for(tmp_path), target_lang=TargetLang.AR, image_mode=mode,
        context_text="Fictional user preference unique to correction.", diagnostics_admin_mode=True)
    sdk = ReviewSDK(**sdk_options)
    client = OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0, pre_call_jitter_seconds=0)
    flow = TranslationWorkflow(client=client, gui_settings={}, ordinary_auto_layout_policy=frozen_automatic_layout_policy())
    return config, sdk, flow


def private_files(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def saved_recipe(tmp_path):
    config = replace(config_for(tmp_path), target_lang=TargetLang.AR, image_mode=ImageMode.OFF)
    policy = frozen_automatic_layout_policy()
    recipe = integration.fresh_recipe(config, "gpt-5.2", policy,
        context_text="Fictional context.", context_hash=sha256_of_text("Fictional context."))
    settings = {"ordinary_semantic_audit_recipe": recipe,
        "ordinary_auto_layout_policy": policy, "image_mode": "off"}
    return config, recipe, settings


def test_fresh_recipe_explicitly_selects_source_inventory_correct_verify(tmp_path):
    _, recipe, settings = saved_recipe(tmp_path)
    assert recipe["version"] == "ordinary_semantic_audit_v3"
    assert recipe["review_protocol"] == "source_inventory_correct_verify_v1"
    assert recipe["source_field_policy"] == "baseline_label_value_v1"
    assert ordinary_semantic_audit_recipe(settings) == recipe
    assert "Fictional context." not in json.dumps(settings)


@pytest.mark.parametrize("value", [None, "unknown", "source_claims_correct_verify_v1", [], {}])
def test_invalid_v3_review_protocol_never_downgrades_to_historical(tmp_path, value):
    _, _, settings = saved_recipe(tmp_path)
    settings["ordinary_semantic_audit_recipe"]["review_protocol"] = value
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)


def test_missing_v3_review_protocol_never_downgrades_to_historical(tmp_path):
    _, _, settings = saved_recipe(tmp_path)
    settings["ordinary_semantic_audit_recipe"].pop("review_protocol")
    with pytest.raises(SemanticAuditRecipeError):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("version", ["ordinary_semantic_audit_v1", "ordinary_semantic_audit_v2"])
def test_historical_recipe_validation_keeps_exact_keys_and_never_adds_protocol(tmp_path, version):
    _, recipe, settings = saved_recipe(tmp_path)
    recipe["version"] = version
    recipe.pop("review_protocol")
    recipe.pop("primary_literal_packaging_version")
    recipe.pop("semantic_unit_reference_policy")
    recipe.pop("source_question_row_policy")
    recipe.pop("source_inventory_max_output_tokens")
    recipe.pop("semantic_source_review_policy")
    recipe.pop("semantic_page_coverage_policy")
    recipe.pop("semantic_review_model_policy")
    if version == "ordinary_semantic_audit_v1":
        for key in ("context_sha256", "context_binding_version", "terminology_policy", "source_field_policy"):
            recipe.pop(key)
    before = json.dumps(settings, sort_keys=True)
    assert ordinary_semantic_audit_recipe(settings) == recipe
    assert json.dumps(settings, sort_keys=True) == before
    assert "review_protocol" not in recipe


@pytest.mark.parametrize("version", ["terminal_source_bound_folio_v3", "terminal_source_bound_folio_v4"])
def test_v3_v4_primary_folio_options_forward_exact_original_bytes_and_hash(tmp_path, version):
    config = replace(config_for(tmp_path), target_lang=TargetLang.AR)
    policy = frozen_automatic_layout_policy()
    state = new_run_state(config=config,
        paths=build_run_paths(config.output_dir, config.pdf_path, config.target_lang),
        pdf_fingerprint=sha256_of_file(config.pdf_path), context_hash=sha256_of_text(None),
        total_pages=1, selected_pages=[1], ordinary_auto_layout_policy=policy,
        primary_recipe={"version": version, "ordinary_auto_layout_policy": policy})
    options = TranslationWorkflow._primary_folio_options(state, config)
    assert options == {"terminal_folio_policy": version,
        "terminal_folio_source_pdf": config.pdf_path.read_bytes(),
        "terminal_folio_source_sha256": state.pdf_fingerprint}
    with pytest.raises(ValueError, match="source is unavailable"):
        TranslationWorkflow._primary_folio_options(state, None)
    config.pdf_path.write_bytes(config.pdf_path.read_bytes() + b"\nchanged source\n")
    with pytest.raises(ValueError, match="source changed"):
        TranslationWorkflow._primary_folio_options(state, config)


def test_genuine_pre_review_v2_engine_request_and_all_evidence_replay_unchanged(tmp_path):
    fixture = Path(__file__).parent / "fixtures/semantic_audit_pre_review_v2"
    inputs = json.loads((fixture / "inputs.json").read_bytes())
    receipt = json.loads((fixture / "generation_receipt.json").read_bytes())
    assert receipt["generator_engine_sha256"] == "38a614689e30d0f23016b0b4c55011c6cb8f6bed43555c7dcbaeac6489b952de"
    for name, digest in receipt["fixture_files"].items():
        assert hashlib.sha256((fixture / name).read_bytes()).hexdigest() == digest
    pages = [historical.SemanticAuditPage(**page) for page in inputs["pages"]]
    recipe = historical.SemanticAuditRecipe(**inputs["recipe"])
    request = historical.build_semantic_audit_request(pages, recipe, inputs["pdf_sha256"])
    assert json.loads(json.dumps(request)) == inputs["request"]
    evidence = tmp_path / "v2_saved_evidence"
    shutil.copytree(fixture / "evidence", evidence)
    before = {p.name: p.read_bytes() for p in evidence.iterdir()}
    result = historical.load_semantic_audit(pages=pages, recipe=recipe,
        pdf_sha256=inputs["pdf_sha256"], evidence_dir=evidence)
    assert result.reused and result.binding_sha256 == receipt["binding_sha256"]
    assert before == {p.name: p.read_bytes() for p in evidence.iterdir()}


def test_fresh_three_stage_candidate_drives_docx_and_counts_all_usage_once(tmp_path):
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert sdk.stages() == list(STAGES)
    assert len(sdk.requests) == 4
    assert CORRECTED in text(result.output_docx) and PRIMARY not in text(result.output_docx)
    assert (result.run_dir / "pages/page_0001.txt").read_text(encoding="utf-8").strip() == PRIMARY
    manifest = json.loads((result.run_dir / "semantic_audit/manifest.json").read_bytes())
    assert manifest["version"] == "source_inventory_correct_verify_unit_refs_v1"
    assert manifest["automated_semantic_verified"] is True and manifest["human_review_complete"] is False
    assert [row["stage"] for row in manifest["stages"]] == list(STAGES)
    for stage in STAGES:
        assert (result.run_dir / "semantic_audit" / stage / "raw_receipt.json").is_file()
    report = json.loads(result.run_summary_path.read_bytes())
    assert report["totals"]["total_input_tokens"] == 141
    assert report["totals"]["total_output_tokens"] == 86
    assert report["totals"]["total_tokens"] == 227
    assert report["diagnostics"]["api_calls_total"] == 4
    assert report["ordinary_semantic_audit"]["accounting"]["call_count"] == 3
    assert report["ordinary_semantic_audit"]["human_review_completed"] is False
    assert flow._last_state.settings["primary_assembly_recipe"]["version"] == "terminal_source_bound_folio_v4"


def test_three_pass_request_boundaries_freeze_context_only_for_correction(tmp_path, monkeypatch):
    # This regression pins the historical primary-model review path.
    from legalpdf_translate.semantic_review_model_policy import __name__ as model_policy_module
    monkeypatch.setattr(model_policy_module + ".fresh_semantic_review_model_policy", lambda: None)
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    inventory, correction, verification = [json.loads(r["input"][0]["content"][0]["text"])
        for r in sdk.requests[1:]]
    assert "primary_pages" not in inventory and "context_text" not in inventory and "literal_protocol" not in inventory
    assert PRIMARY not in json.dumps(inventory, ensure_ascii=False)
    assert config.context_text not in json.dumps(inventory, ensure_ascii=False)
    assert json.loads(correction["context_text"])["resolved_user_context"] == config.context_text
    assert correction["primary_pages"][0]["text"].strip() == PRIMARY
    assert verification["candidate_pages"][0]["text"].strip() == CORRECTED
    assert all(key not in verification for key in ("primary_pages", "context_text", "claim_coverage", "reason_codes"))
    assert "reason_codes" not in json.dumps(verification, ensure_ascii=False)
    assert all(r["model"] == flow._provided_client.model and r["reasoning"]["effort"] == config.effort.value
               for r in sdk.requests[1:])


@pytest.mark.parametrize("mode", [ImageMode.OFF, ImageMode.AUTO, ImageMode.ALWAYS])
def test_v3_configured_image_control_applies_to_all_three_subpasses(tmp_path, monkeypatch, mode):
    config, sdk, flow = setup_review(tmp_path, mode=mode, corrected=False)
    if mode == ImageMode.OFF:
        monkeypatch.setattr(workflow_module, "render_page_image_data_url",
            lambda *a, **k: pytest.fail("Image Off unexpectedly rendered"))
    result = flow.run(config)
    assert result.success, result.error
    for request in sdk.requests[1:]:
        content = request["input"][0]["content"]
        assert len(content) == (1 if mode == ImageMode.OFF else 2)
        payload = json.loads(content[0]["text"])
        assert payload["source_pages"][0]["image_position"] == (None if mode == ImageMode.OFF else 1)


def test_v3_resume_and_offline_rebuild_revalidate_frozen_three_stage_evidence_without_calls(tmp_path):
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success
    stages = result.run_dir / "semantic_audit"
    before = private_files(stages)
    journal = flow._dispatch_accounting.journal_path
    before_journal = journal.read_bytes()
    assert flow.run(replace(config, resume=True)).success
    rebuilt = TranslationWorkflow(gui_settings={}).rebuild_docx(replace(config,
        context_text="A changed current preference must not replace frozen context.",
        context_file=tmp_path / "missing_current_context.txt", glossary_file=tmp_path / "missing_current_glossary.json"))
    assert CORRECTED in text(rebuilt) and len(sdk.requests) == 4
    assert stages.is_dir() and private_files(stages) == before
    assert journal.read_bytes() == before_journal


@pytest.mark.parametrize("stage,code", [("source_inventory", "review_source_unresolved"),
    ("correction", "review_correction_unresolved"), ("verification", "review_independent_verification_failed")])
def test_unresolved_subpass_fails_unapproved_and_never_rebuys_the_same_stage(tmp_path, stage, code):
    config, sdk, flow = setup_review(tmp_path, failure_stage=stage, failure="unresolved")
    result = flow.run(config)
    assert not result.success and result.error == "semantic_audit_" + code
    assert result.output_docx is None and result.partial_docx and PRIMARY in text(result.partial_docx)
    assert flow._last_state.run_status == "semantic_audit_failed"
    assert sdk.stages() == list(STAGES[:STAGES.index(stage) + 1])
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
    assert not list((result.run_dir / "semantic_audit").glob("page_*.txt"))
    before = len(sdk.requests)
    assert not flow.run(replace(config, resume=True)).success
    with pytest.raises(integration.SemanticIntegrationError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == before


@pytest.mark.parametrize("stage,failure,code", [("source_inventory", "refused", "provider_refusal"),
    ("correction", "incomplete", "provider_incomplete"),
    ("source_inventory", "transport", "provider_operation_unsettled"),
    ("verification", "unknown_usage", "usage_unknown_or_unsettled")])
def test_failed_or_unknown_stage_retains_charges_and_stops_before_later_dispatch(tmp_path, stage, failure, code, monkeypatch):
    # This regression pins the historical primary-model review path.
    from legalpdf_translate.semantic_review_model_policy import __name__ as model_policy_module
    monkeypatch.setattr(model_policy_module + ".fresh_semantic_review_model_policy", lambda: None)
    config, sdk, flow = setup_review(tmp_path, failure_stage=stage, failure=failure)
    result = flow.run(config)
    assert not result.success and result.error == "semantic_audit_" + code
    assert result.output_docx is None and result.partial_docx
    count = 1 + STAGES.index(stage) + 1
    assert len(sdk.requests) == count
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
    if failure != "transport":
        assert (result.run_dir / "semantic_audit" / stage / "raw_receipt.json").is_file()
    report = json.loads(result.run_summary_path.read_bytes())
    assert report["dispatch_accounting"]["call_count"] == count
    assert report["ordinary_semantic_audit"]["accounting"]["call_count"] == count - 1
    assert not flow.run(replace(config, resume=True)).success
    assert len(sdk.requests) == count


@pytest.mark.parametrize("stage", STAGES)
def test_cancelled_settled_subpass_publishes_no_final_until_resume_and_never_repeats_charge(tmp_path, stage):
    config, sdk, flow = setup_review(tmp_path)
    sdk.on_stage = lambda current: flow.cancel() if current == stage else None
    result = flow.run(config)
    assert not result.success and result.error == "cancelled"
    assert result.output_docx is None and result.partial_docx
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
    assert (result.run_dir / "semantic_audit" / stage / "raw_receipt.json").is_file()
    sdk.on_stage = None
    resumed = flow.run(replace(config, resume=True))
    assert resumed.success, resumed.error
    assert sdk.stages() == list(STAGES) and len(sdk.requests) == 4
    assert CORRECTED in text(resumed.output_docx)
    report = json.loads(resumed.run_summary_path.read_bytes())
    assert report["totals"]["total_tokens"] == 227


def test_predispatch_cancel_conservatively_blocks_unsettled_substage_without_global_zero_proof(tmp_path, monkeypatch):
    config, sdk, flow = setup_review(tmp_path)
    from legalpdf_translate import openai_client as transport
    flow._provided_client._pre_call_jitter_seconds = .05
    monkeypatch.setattr(transport.random, "uniform", lambda *_: .01)
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2:
            flow.cancel()
    monkeypatch.setattr(transport.time, "sleep", sleep)
    result = flow.run(config)
    assert not result.success and result.error == "cancelled" and len(sdk.requests) == 1
    stage = result.run_dir / "semantic_audit/source_inventory"
    assert (stage / "intent.json").is_file() and not (stage / "raw_response.json").exists()
    flow._provided_client._pre_call_jitter_seconds = 0
    resumed = flow.run(replace(config, resume=True))
    assert not resumed.success and resumed.error == "semantic_audit_review_unsettled_stage"
    assert len(sdk.requests) == 1


@pytest.mark.parametrize("damage", ["source_raw", "correction_receipt", "verification_receipt", "candidate", "context"])
def test_v3_corrupt_or_missing_bound_evidence_refuses_rebuild_without_new_calls(tmp_path, damage):
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success
    paths = {"source_raw": "semantic_audit/source_inventory/raw_response.json",
        "correction_receipt": "semantic_audit/correction/raw_receipt.json",
        "verification_receipt": "semantic_audit/verification/raw_receipt.json",
        "candidate": "semantic_audit/page_0001.txt", "context": "semantic_context.json"}
    path = result.run_dir / paths[damage]
    if damage.endswith("receipt"):
        path.unlink()
    else:
        path.write_bytes(path.read_bytes() + b" modified")
    before_output = result.output_docx.read_bytes()
    with pytest.raises(integration.SemanticIntegrationError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == 4 and result.output_docx.read_bytes() == before_output


def test_v3_journal_corruption_blocks_local_publication_before_loading_settled_stages(tmp_path):
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success
    root = result.run_dir / "semantic_audit"
    (root / "manifest.json").unlink()
    (root / "page_0001.txt").unlink()
    journal = flow._dispatch_accounting.journal_path
    data = json.loads(journal.read_bytes())
    data["fingerprint"] = "0" * 64
    journal.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(integration.SemanticIntegrationError, match="accounting_evidence_invalid"):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert not (root / "manifest.json").exists() and not (root / "page_0001.txt").exists()
    assert len(sdk.requests) == 4


@pytest.mark.parametrize("damage", ["supplied_context", "missing_context_pack"])
def test_v3_context_identity_failure_blocks_resume_before_any_additional_send(tmp_path, damage):
    config, sdk, flow = setup_review(tmp_path)
    result = flow.run(config)
    assert result.success
    before = private_files(result.run_dir / "semantic_audit")
    if damage == "supplied_context":
        config = replace(config, context_text="A changed fictional preference.")
        expected_error, expected_message = ValueError, "context mismatch"
    else:
        (result.run_dir / "semantic_context.json").unlink()
        expected_error = integration.SemanticIntegrationError
        expected_message = "^semantic_audit_context_evidence_missing_or_changed$"
    with pytest.raises(expected_error, match=expected_message):
        flow.run(replace(config, resume=True))
    assert len(sdk.requests) == 4
    assert private_files(result.run_dir / "semantic_audit") == before


def test_current_fresh_page_limit_keeps_explicit_unaudited_qualification_on_resume(tmp_path):
    import fitz
    config, sdk, flow = setup_review(tmp_path)
    with fitz.open(config.pdf_path) as original, fitz.open() as extended:
        for _ in range(13):
            extended.insert_pdf(original)
        source = config.pdf_path.with_name("thirteen_pages.pdf")
        extended.save(source)
    config = replace(config, pdf_path=source)
    result = flow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 13 and not sdk.stages()
    assert ordinary_semantic_audit_recipe(flow._last_state.settings) is None
    assert flow._last_state.settings["ordinary_semantic_audit_qualification"]["audit_not_run"] == "selected_page_limit"
    assert not (result.run_dir / "semantic_audit").exists()
    report = json.loads(result.run_summary_path.read_bytes())
    assert report["ordinary_semantic_audit"]["human_review_completed"] is False
    assert flow.run(replace(config, resume=True)).success
    assert len(sdk.requests) == 13
