"""Actual workflow/checkpoint/client/journal; synthetic SDK and source only."""
from dataclasses import replace
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import fitz
import pytest

from legalpdf_translate import workflow as module
from legalpdf_translate import ordinary_semantic_audit as engine
from legalpdf_translate.checkpoint import (load_run_state, save_run_state_atomic,
    ordinary_semantic_audit_recipe, SemanticAuditRecipeError)
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy
from legalpdf_translate.types import TargetLang, ImageMode
from legalpdf_translate.workflow import TranslationWorkflow
from legalpdf_translate.workflow_semantic_audit import (SemanticIntegrationError, capture_source,
    select_pages, dispatch_rollup)
from tests.test_new_run_preflight import config_for


PRIMARY = "طلب مقدم الطلب جوابا."
CORRECTED = "طلب المدعى عليه جوابا."


class AuditSDK:
    base_url = "https://api.openai.com/v1/"
    def __init__(self, *, failure=None, correction=True):
        self.requests = []
        self.failure = failure
        self.correction = correction
        self.on_audit = None
        self.primary_labels = None
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **request):
        self.requests.append(request)
        audit = "text" in request
        if audit and self.on_audit is not None:
            self.on_audit()
        if audit and self.failure == "transport":
            from legalpdf_translate.openai_client import APIConnectionError
            raise APIConnectionError(request=None)
        if audit and self.failure == "rate_limit":
            class Throttled(Exception): status_code = 429
            raise Throttled("synthetic rate limit")
        if audit:
            source = json.loads(request["input"][0]["content"][0]["text"])
            rows = [{"page_number": p["page_number"],
                     "status": "unresolved" if self.failure == "unresolved" else "corrected" if self.correction else "no_change",
                     "corrected_text": CORRECTED if self.correction else "",
                     "reason_codes": ["actor_recipient"] if self.correction else []} for p in source["pages"]]
            raw = json.dumps({"version": engine.AUDIT_VERSION, "pages": rows})
        else:
            raw = "```text\n" + PRIMARY + "\n```"
            if self.primary_labels is not None:
                from legalpdf_translate.arabic_pre_tokenize import pretokenize_arabic_source
                index = sum("text" not in item for item in self.requests) - 1
                raw = "```text\n" + PRIMARY + "\n" + pretokenize_arabic_source(self.primary_labels[index]) + "\n```"
        return SimpleNamespace(id=f"synthetic-{len(self.requests)}", model="gpt-5.2",
            status="incomplete" if audit and self.failure == "incomplete" else "completed",
            incomplete_details={"reason": "max_output_tokens"} if audit and self.failure == "incomplete" else None,
            service_tier="default", output_text=raw,
            output=[{"type": "refusal", "refusal": "synthetic refusal"}] if audit and self.failure == "refused" else [],
            usage=None if audit and self.failure == "unknown_usage" else {
                "input_tokens": 10 if audit else 100, "output_tokens": 5 if audit else 60,
                "total_tokens": 15 if audit else 160})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import legalpdf_translate.accounting_policy as policies
    class VerifiedDate(date):
        @classmethod
        def today(cls): return cls(2026, 10, 15)
    monkeypatch.setattr(policies, "date", VerifiedDate)
    monkeypatch.setattr(module, "load_environment", lambda: None)
    monkeypatch.setattr(module, "run_translation_auth_test", lambda **_: pytest.fail("auth dispatched"))
    monkeypatch.setattr(module, "resolve_openai_key_with_source", lambda **_: pytest.fail("ambient credentials"))


@pytest.fixture(autouse=True)
def saved_v2_protocol(monkeypatch):
    """These retained lifecycle cases exercise the unchanged one-pass v2 path."""
    from legalpdf_translate import workflow_semantic_audit as integration
    fresh = integration.fresh_recipe
    def v2(*args, **kwargs):
        recipe = fresh(*args, **kwargs)
        recipe["version"] = "ordinary_semantic_audit_v2"
        recipe.pop("review_protocol", None)
        recipe.pop("primary_literal_packaging_version", None)
        recipe.pop("semantic_unit_reference_policy", None)
        recipe.pop("source_question_row_policy", None)
        recipe.pop("source_inventory_max_output_tokens", None)
        recipe.pop("semantic_source_review_policy", None)
        recipe.pop("semantic_page_coverage_policy", None)
        recipe.pop("semantic_review_model_policy", None)
        recipe.pop("semantic_repair_policy", None)
        recipe.pop("semantic_literal_authority_policy", None)
        recipe.pop("semantic_enclosure_authority_policy", None)
        recipe.pop("source_enclosure_identity_policy", None)
        recipe.pop("semantic_target_ambiguity_policy", None)
        recipe.pop("semantic_enclosure_sequence_repair_policy", None)
        recipe.pop("primary_page_evidence_policy", None)
        recipe.pop("primary_literal_markup_policy", None)
        recipe.pop("ocr_text_transport_policy", None)
        # This explicitly pre-v3 recipe cannot own the later local join key.
        recipe.pop("source_inline_address_join_policy", None)
        return recipe
    monkeypatch.setattr(integration, "fresh_recipe", v2)


def setup(tmp_path, *, failure=None, image=True, ordinary=True):
    config = replace(config_for(tmp_path), target_lang=TargetLang.AR,
        image_mode=ImageMode.ALWAYS if image else ImageMode.OFF, diagnostics_admin_mode=True)
    sdk = AuditSDK(failure=failure)
    client = OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0, pre_call_jitter_seconds=0)
    flow = TranslationWorkflow(client=client, gui_settings={},
        ordinary_auto_layout_policy=frozen_automatic_layout_policy() if ordinary else None)
    return config, sdk, flow


def text(path):
    from lxml import etree
    with ZipFile(path) as z:
        return "".join(etree.fromstring(z.read("word/document.xml")).xpath("//*[local-name()='t']/text()"))


def test_fresh_audited_selection_drives_docx_and_source_map_without_changing_primary(tmp_path):
    config, sdk, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 2
    assert CORRECTED in text(result.output_docx) and PRIMARY not in text(result.output_docx)
    primary = result.run_dir / "pages/page_0001.txt"
    assert primary.read_text(encoding="utf-8").strip() == PRIMARY
    source = json.loads((result.run_dir / "semantic_source/page_0001.json").read_text(encoding="utf-8"))
    assert source["source_text_kind"] == "pretokenized"
    assert source["original_source_text"] and source["image_data_url"].startswith("data:image/")
    prompt = json.loads(sdk.requests[1]["input"][0]["content"][0]["text"])
    assert prompt["pages"][0]["source_text"] == source["source_text"]
    assert prompt["pages"][0]["original_source_text"] == source["original_source_text"]
    mapping = json.loads(result.output_docx.with_suffix(".source_map.json").read_text(encoding="utf-8"))
    from legalpdf_translate.ordinary_auto_layout_artifacts import bind_raw_page_map
    bound = bind_raw_page_map(result.output_docx.read_bytes(), mapping,
        source_pdf_sha256=hashlib.sha256(config.pdf_path.read_bytes()).hexdigest(),
        selected_pages=(1,), target_lang="AR")
    assert any(p.text == CORRECTED for p in bound.paragraphs)
    report = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert report["totals"]["total_input_tokens"] == 110
    assert report["totals"]["total_output_tokens"] == 65
    assert report["totals"]["total_tokens"] == 175
    assert report["diagnostics"]["api_calls_total"] == 2
    assert report["dispatch_accounting"]["call_count"] == 2
    assert report["ordinary_semantic_audit"]["human_review_completed"] is False


def test_resume_and_offline_rebuild_reuse_exact_candidate_and_journal_once(tmp_path):
    config, sdk, flow = setup(tmp_path)
    original = flow.run(config)
    assert original.success
    journal = flow._dispatch_accounting.journal_path
    before_journal = journal.read_bytes()
    before_primary = (original.run_dir / "pages/page_0001.txt").read_bytes()
    resumed = flow.run(replace(config, resume=True))
    assert resumed.success and len(sdk.requests) == 2
    rebuilt = TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert CORRECTED in text(rebuilt)
    assert journal.read_bytes() == before_journal
    assert (original.run_dir / "pages/page_0001.txt").read_bytes() == before_primary
    report = json.loads(resumed.run_summary_path.read_text(encoding="utf-8"))
    assert report["totals"]["total_tokens"] == 175
    assert report["ordinary_semantic_audit"]["accounting"]["call_count"] == 1


@pytest.mark.parametrize("failure,code", [
    ("unresolved", "semantic_audit_unresolved"),
    ("transport", "semantic_audit_provider_operation_unsettled"),
    ("unknown_usage", "semantic_audit_usage_unknown_or_unsettled"),
    ("refused", "semantic_audit_provider_refusal"),
    ("incomplete", "semantic_audit_provider_incomplete"),
])
def test_audit_failures_are_precise_and_keep_primary_partial_costs_and_no_repurchase(tmp_path, failure, code):
    config, sdk, flow = setup(tmp_path, failure=failure)
    result = flow.run(config)
    assert not result.success and result.error == code
    assert result.output_docx is None and result.partial_docx and PRIMARY in text(result.partial_docx)
    assert flow._last_state.run_status == "semantic_audit_failed"
    assert flow._last_state.failure_context["scope"] == "semantic_audit"
    assert (result.run_dir / "pages/page_0001.txt").is_file()
    assert len(sdk.requests) == 2
    report = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert report["dispatch_accounting"]["call_count"] == 2
    assert report["ordinary_semantic_audit"]["accounting"]["call_count"] == 1
    again = flow.run(replace(config, resume=True))
    assert not again.success and len(sdk.requests) == 2
    with pytest.raises(SemanticIntegrationError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)


def test_image_off_keeps_both_primary_and_audit_imagery_free_with_explicit_coverage(tmp_path, monkeypatch):
    config, sdk, flow = setup(tmp_path, image=False)
    monkeypatch.setattr(module, "render_page_image_data_url", lambda *a, **k: pytest.fail("Image Off rendered"))
    result = flow.run(config)
    assert result.success and len(sdk.requests) == 2
    assert len(sdk.requests[0]["input"][0]["content"]) == 1
    assert len(sdk.requests[1]["input"][0]["content"]) == 1
    data = json.loads((result.run_dir / "semantic_source/page_0001.json").read_text(encoding="utf-8"))
    assert data["primary_image_data_url"] is None and data["image_data_url"] is None
    assert data["visual_coverage"] == "text_only_configured_image_off"
    assert ordinary_semantic_audit_recipe(flow._last_state.settings)["source_image_policy"] == "configured_image_mode_v1"


def test_unexpected_missing_auto_image_requires_review_without_text_only_downgrade(tmp_path):
    config, sdk, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success
    state = flow._last_state
    p = result.run_dir / "semantic_source/page_0001.json"
    data = json.loads(p.read_text(encoding="utf-8"));data["image_data_url"] = None
    p.write_text(json.dumps(data), encoding="utf-8")
    state.pages["1"]["semantic_source_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(SemanticIntegrationError, match="review_required_source_image"):
        select_pages(state=state, config=config, run_dir=result.run_dir, pages_dir=result.run_dir / "pages")


@pytest.mark.parametrize("change", ["source", "pdf", "primary", "candidate", "extra_candidate", "selection"])
def test_corrupt_or_changed_audit_inputs_never_fall_back_to_primary(tmp_path, change):
    config, sdk, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success
    if change == "source":
        p = result.run_dir / "semantic_source/page_0001.json"
        p.write_bytes(p.read_bytes() + b" ")
    elif change == "pdf":
        config.pdf_path.write_bytes(config.pdf_path.read_bytes() + b"\nmodified source\n")
    elif change == "primary":
        (result.run_dir / "pages/page_0001.txt").write_text(PRIMARY + " زائد", encoding="utf-8")
    elif change == "candidate":
        (result.run_dir / "semantic_audit/page_0001.txt").write_text("بديل", encoding="utf-8")
    elif change == "extra_candidate":
        (result.run_dir / "semantic_audit/page_9999.txt").write_text("بديل", encoding="utf-8")
    else:
        state = load_run_state(flow._last_paths.run_state_path)
        state.selection_page_count = 2
        save_run_state_atomic(flow._last_paths.run_state_path, state)
    with pytest.raises(SemanticIntegrationError):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert len(sdk.requests) == 2


def test_cancellation_after_audit_settlement_retains_raw_and_reuses_without_publishing_until_resume(tmp_path):
    config, sdk, flow = setup(tmp_path)
    sdk.on_audit = flow.cancel
    result = flow.run(config)
    assert not result.success and result.error == "cancelled"
    assert flow._last_state.run_status == "cancelled"
    assert result.output_docx is None and result.partial_docx
    assert not (result.run_dir / "semantic_audit/manifest.json").exists()
    assert (result.run_dir / "semantic_audit/raw_response.json").is_file()
    assert (result.run_dir / "semantic_audit/raw_receipt.json").is_file()
    report = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert report["totals"]["total_tokens"] == 175
    assert report["dispatch_accounting"]["call_count"] == 2
    sdk.on_audit = None
    resumed = flow.run(replace(config, resume=True))
    assert resumed.success and len(sdk.requests) == 2
    assert CORRECTED in text(resumed.output_docx)


def test_cancellation_during_429_prevents_backoff_and_second_audit_dispatch(tmp_path, monkeypatch):
    config, sdk, flow = setup(tmp_path, failure="rate_limit")
    flow._provided_client._max_transport_retries = 3
    sdk.on_audit = flow.cancel
    monkeypatch.setattr(module.time, "sleep", lambda _: pytest.fail("cancelled audit entered backoff"))
    result = flow.run(config)
    assert not result.success and result.error == "cancelled"
    assert len(sdk.requests) == 2 and result.output_docx is None


def test_cancelled_before_audit_sdk_dispatch_resumes_only_with_strict_zero_dispatch_proof(tmp_path, monkeypatch):
    config, sdk, flow = setup(tmp_path)
    flow._provided_client._pre_call_jitter_seconds = .05
    from legalpdf_translate import openai_client as transport
    monkeypatch.setattr(transport.random, "uniform", lambda *_: .01)
    sleeps = []
    def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 2: flow.cancel()
    monkeypatch.setattr(transport.time, "sleep", sleep)
    result = flow.run(config)
    assert not result.success and result.error == "cancelled"
    assert len(sdk.requests) == 1  # Primary only; no audit begin/finish or SDK attempt.
    rollup = dispatch_rollup(state=flow._last_state, run_dir=result.run_dir, accountant=flow._dispatch_accounting)
    assert rollup["call_count"] == 0
    assert (result.run_dir / "semantic_audit/intent.json").is_file()
    assert not (result.run_dir / "semantic_audit/raw_response.json").exists()
    resumed = flow.run(replace(config, resume=True))
    assert resumed.success and len(sdk.requests) == 2
    assert CORRECTED in text(resumed.output_docx)


def test_fresh_and_rebuild_forward_exact_v4_source_folio_proof_to_audit_candidate(tmp_path):
    from tests.test_primary_source_bound_folio import source, has_page
    config, sdk, flow = setup(tmp_path)
    config.pdf_path.write_bytes(source(["Page 1", "Page 1 / 2", "Page 2 / 2"]))
    sdk.correction = False
    sdk.primary_labels = ["الصفحة 1", "ص. 1 / 2", "ص. 2 / 2"]
    result = flow.run(config)
    assert result.success, result.error
    assert flow._last_state.settings["primary_assembly_recipe"]["version"] == "terminal_source_bound_folio_v4"
    assert not has_page(result.output_docx)
    mapping = json.loads(result.output_docx.with_suffix(".source_map.json").read_text(encoding="utf-8"))
    assert [(p["source_folio_proof"]["number"], p["source_folio_proof"]["total"]) for p in mapping["pages"]] == [(1, None), (1, 2), (2, 2)]
    rebuilt = TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert not has_page(rebuilt) and len(sdk.requests) == 4


@pytest.mark.parametrize("provided", [False, True])
def test_reused_workflow_restores_constructor_model_before_a_saved_resume_override(tmp_path, provided):
    config = config_for(tmp_path)
    sdk = AuditSDK()
    client = OpenAIResponsesClient(sdk_client=sdk, model="gpt-5.6-sol", pre_call_jitter_seconds=0) if provided else None
    class StopBeforeAnyWork(Exception): pass
    observed = []
    def stop():
        observed.append(flow._translation_model)
        raise StopBeforeAnyWork
    flow = TranslationWorkflow(client=client, gui_settings={}, environment_loader=stop)
    # Simulate a prior no-client Resume restoring a different saved model.
    flow._translation_model = "gpt-5.6-terra"
    with pytest.raises(StopBeforeAnyWork): flow._run_locked(config)
    assert observed == [client.model if provided else module.OPENAI_MODEL]
    assert not sdk.requests
    if provided: assert client.model == "gpt-5.6-sol"


@pytest.mark.parametrize("corruption", ["fingerprint", "identity", "schema", "events", "usage", "pricing"])
def test_offline_rebuild_validates_retained_journal_integrity_identity_and_events_without_writes(tmp_path, corruption):
    config, sdk, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success
    journal = flow._dispatch_accounting.journal_path
    saved = json.loads(journal.read_text(encoding="utf-8"))
    from legalpdf_translate.usage_accounting import _state_fingerprint, _fingerprint
    if corruption == "fingerprint": saved["fingerprint"] = "0" * 64
    elif corruption == "identity":
        saved["run_identity"]["source_sha256"] = "0" * 64
        saved["run_identity_hash"] = _fingerprint(saved["run_identity"])
    elif corruption == "schema": saved["schema_version"] = 100
    elif corruption == "events": saved["events"].append(saved["events"][0])
    elif corruption == "usage":
        finish = next(e for e in saved["events"] if e["event"] == "finish")
        finish["usage"]["input_tokens"] = -1
    elif corruption == "pricing": saved["pricing_catalog"] = []
    if corruption != "fingerprint": saved["fingerprint"] = _state_fingerprint(saved)
    journal.write_text(json.dumps(saved), encoding="utf-8")
    before = {p: p.read_bytes() for p in result.run_dir.rglob("*") if p.is_file()}
    before_docx = result.output_docx.read_bytes()
    with pytest.raises(SemanticIntegrationError, match="accounting_evidence_invalid"):
        TranslationWorkflow(gui_settings={}).rebuild_docx(config)
    assert before == {p: p.read_bytes() for p in result.run_dir.rglob("*") if p.is_file()}
    assert result.output_docx.read_bytes() == before_docx and len(sdk.requests) == 2


@pytest.mark.parametrize("change", [None, "version", "model", "effort_policy", "extra", "policy", "deleted"])
def test_saved_recipe_absence_or_malformation_cannot_downgrade_audited_run(tmp_path, change):
    config, sdk, flow = setup(tmp_path)
    assert flow.run(config).success
    path = flow._last_paths.run_state_path
    data = json.loads(path.read_text(encoding="utf-8"))
    recipe = data["settings"]["ordinary_semantic_audit_recipe"]
    if change is None: data["settings"]["ordinary_semantic_audit_recipe"] = None
    elif change == "deleted": del data["settings"]["ordinary_semantic_audit_recipe"]
    elif change == "extra": recipe["extra"] = True
    elif change == "policy": recipe["ordinary_auto_layout_policy"] = "unknown"
    else: recipe[change] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SemanticAuditRecipeError): load_run_state(path)
    assert len(sdk.requests) == 2


def test_historical_absent_recipe_stays_legacy_on_resume_and_rebuild(tmp_path):
    config, sdk, flow = setup(tmp_path, ordinary=False)
    original = flow.run(config)
    assert original.success and len(sdk.requests) == 1
    assert ordinary_semantic_audit_recipe(flow._last_state.settings) is None
    assert flow.run(replace(config, resume=True)).success
    assert PRIMARY in text(TranslationWorkflow(gui_settings={}).rebuild_docx(config))
    assert len(sdk.requests) == 1


def test_page_limit_preserves_ordinary_behavior_and_freezes_explicit_not_audited_qualification(tmp_path):
    config, sdk, flow = setup(tmp_path)
    with fitz.open(config.pdf_path) as original:
        with fitz.open() as extended:
            for _ in range(13): extended.insert_pdf(original)
            other = config.pdf_path.with_name("larger.pdf")
            extended.save(other)
    result = flow.run(replace(config, pdf_path=other))
    assert result.success and len(sdk.requests) == 13
    state = flow._last_state
    assert ordinary_semantic_audit_recipe(state.settings) is None
    assert state.settings["ordinary_semantic_audit_qualification"]["audit_not_run"] == "selected_page_limit"
    report = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert report["ordinary_semantic_audit"]["audit_not_run"] == "selected_page_limit"
    assert report["ordinary_semantic_audit"]["human_review_completed"] is False
    assert not (result.run_dir / "semantic_audit").exists()
    assert flow.run(replace(config, pdf_path=other, resume=True)).success
    assert len(sdk.requests) == 13


def test_historical_auto_layout_checkpoint_without_audit_stays_historical(tmp_path):
    config, sdk, flow = setup(tmp_path, ordinary=False)
    assert flow.run(config).success
    state = flow._last_state
    policy = frozen_automatic_layout_policy()
    state.settings["ordinary_auto_layout_policy"] = policy
    state.settings["primary_assembly_recipe"] = {"version": "terminal_labeled_folio_v2", "ordinary_auto_layout_policy": policy}
    save_run_state_atomic(flow._last_paths.run_state_path, state)
    # The existing accountant identity is source/protocol/model-based and remains exact.
    resumed = TranslationWorkflow(client=flow._provided_client, gui_settings={}).run(replace(config, resume=True))
    assert resumed.success and len(sdk.requests) == 1
    final = load_run_state(flow._last_paths.run_state_path)
    assert ordinary_semantic_audit_recipe(final.settings) is None


def test_capture_is_immutable_and_original_glossary_source_is_independently_pinned(tmp_path):
    config, sdk, flow = setup(tmp_path)
    assert flow.run(config).success
    data = json.loads((flow._last_paths.run_dir / "semantic_source/page_0001.json").read_text(encoding="utf-8"))
    arguments = dict(state=flow._last_state, run_dir=flow._last_paths.run_dir, page_number=1,
        source_text=data["source_text"], original_source_text=data["original_source_text"],
        expected_ar_tokens=data["expected_ar_tokens"], image_data_url=data["primary_image_data_url"])
    assert capture_source(**arguments)["semantic_source_sha256"] == flow._last_state.pages["1"]["semantic_source_sha256"]
    with pytest.raises(SemanticIntegrationError, match="source_evidence_changed"):
        capture_source(**{**arguments, "original_source_text": "changed original source"})
