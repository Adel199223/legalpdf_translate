"""Actual workflow, transport accounting and original-ledger adapter; fake SDK only."""
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time

import pytest

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.acceptance_budget import LegacyAcceptanceBudget, stable_acceptance_run_identity
from legalpdf_translate.acceptance_continuation import AcceptanceContinuation
from legalpdf_translate.acceptance_execution import build_acceptance_continuation
from legalpdf_translate.acceptance_provenance import canonical_run_config, request_fingerprint
from legalpdf_translate.budget_reservations import BudgetError, fingerprint
from legalpdf_translate.checkpoint import load_run_state
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.new_translation_blocks import NewTranslationBlocks
from legalpdf_translate.usage_accounting import DispatchAccounting, accounting_context
from legalpdf_translate.workflow import TranslationWorkflow
from legalpdf_translate.types import TargetLang
from tests.test_acceptance_budget_adapter import _write_fixture, _provenance
from tests.test_acceptance_provenance import _save
from tests.test_acceptance_continuation import offline
from tests.test_new_translation_blocks import configuration, TARGETS
from tests.test_workflow_dispatch_accounting import FakeSDK, client_for
from tooling.structured_acceptance_preflight import build_acceptance_accounting
from tests.source_readiness_fixtures import synthetic_native_review


class CampaignSDK(FakeSDK):
    def create(self, **request):
        result = super().create(**request)
        payload = json.loads(result.output_text)
        for row in payload["blocks"]:
            row["text"] = TARGETS[getattr(self, "target_lang", TargetLang.AR)]
        result.output_text = json.dumps(payload, ensure_ascii=False)
        return result


def _prepare_case(config, campaign_identity, client, limits, directory, *, review_json=None, reviewed_evidence=None):
    """Real source winner/prompt construction stops at the authorizer, before intent.

    No workflow/accounting guards are overridden. This direct local preparation
    has no dispatch authority and its client is never called.
    """
    captured = {}
    pages = tuple(range(1, limits["case_pages"] + 1))
    def capture(descriptor):
        captured[descriptor["page_number"]] = descriptor["request"]
        return None
    policy = AcceptanceContinuation(campaign_identity, pages, pages, capture,
        review_json if review_json is not None else synthetic_native_review(config, pages),
        reviewed_evidence, (lambda: None) if reviewed_evidence is not None else None)
    workflow = TranslationWorkflow(client=client, gui_settings={}, environment_loader=lambda: None,
        translation_protocol="legal_blocks_v2", acceptance_continuation=policy)
    workflow._last_state = SimpleNamespace(pages={})
    context, context_hash = workflow._resolve_context(config)
    source_hash = hashlib.sha256(config.pdf_path.read_bytes()).hexdigest()
    structured = NewTranslationBlocks(workflow, config, pages, source_hash=source_hash, context_hash=context_hash)
    workflow._structured_run = structured
    structured.prepare_native_evidence()
    directory.mkdir()
    paths = SimpleNamespace(run_dir=directory, pages_dir=directory / "pages")
    for number in pages:
        if reviewed_evidence is not None:
            result = workflow._process_page(client=client, config=config, paths=paths,
                instructions=structured.instructions, context_text=context,
                page_number=number, total_pages=len(pages))
            assert result.error == "acceptance_approval_required"
            continue
        ordered = structured.ordered_pages[number]
        source = structured.make_source(number=number, ordered=ordered, text=ordered.text,
            ocr_result=None, ocr_used=False, merged=False, suspect=False)
        result = structured.translate(client=client, source=source, paths=paths, page_number=number,
            total_pages=len(pages), context_text=context, image_data_url=None, image_detail="low", effort="high",
            metadata={"api_calls_count": 0, "transport_retries_count": 0}, started=time.perf_counter())
        assert result.error == "acceptance_approval_required"
    identity = {"accounting_id": "preparation-only", "run_started_at": "not-dispatched",
        "source_sha256": source_hash, "context_hash": context_hash, "language": config.target_lang.value,
        "model": "gpt-5.2", "protocol": "legal_blocks_v2", "protocol_identity": structured.identity,
        "selection": [1, len(pages)]}
    return captured, identity


def _campaign(tmp_path, *, pages=9, defect=False, reviewed=False, lang=TargetLang.AR):
    config = configuration(tmp_path, pages=pages, lang=lang)
    if reviewed:
        from legalpdf_translate.types import OcrMode, ImageMode
        config = replace(config, ocr_mode=OcrMode.ALWAYS, image_mode=ImageMode.ALWAYS)
    config = TranslationWorkflow(gui_settings={}, environment_loader=lambda: None)._normalize_config(config)
    authority = tmp_path / "synthetic-authority"
    authority.mkdir()
    fixture = _write_fixture(authority)
    ledger, original_path, _, _, _, old_prices, historical = fixture
    amendment = json.loads(original_path.read_bytes())
    provenance, execution = _provenance(authority, source=config.pdf_path,
        runtime_config=canonical_run_config(config), preferences={})
    review_path = authority / "synthetic-source-review.json"
    reviewed_case, extra_entries = None, []
    if reviewed:
        from tests.test_reviewed_source import reviewed_fixture, decision_envelope, digest
        from legalpdf_translate.source_document import source_page_identity, source_page_dimensions
        reviewed_case = reviewed_fixture(pages, document_bytes=config.pdf_path.read_bytes(),
            page_identities={n: source_page_identity(config.pdf_path, n) for n in range(1, pages + 1)},
            page_sizes={n: source_page_dimensions(config.pdf_path, n) for n in range(1, pages + 1)})
        raw_files = [("candidate", reviewed_case.evidence.candidate), ("manifest", reviewed_case.evidence.manifest)]
        raw_files += list(reviewed_case.evidence.artifacts)
        paths = {}
        for label, raw in raw_files:
            artifact_path = authority / (label + ".bin")
            artifact_path.write_bytes(raw)
            paths[digest(raw)] = str(artifact_path.resolve())
            extra_entries.append({"path": str(artifact_path.resolve()), "sha256": digest(raw)})
        review_json = json.dumps(decision_envelope(reviewed_case, paths=paths))
    else:
        review_json = synthetic_native_review(config, tuple(range(1, pages + 1)))
    review_path.write_text(review_json, encoding="utf-8")
    review_entry = {"path": str(review_path.resolve()), "sha256": hashlib.sha256(review_path.read_bytes()).hexdigest()}
    config_manifest_path = authority / "config-manifest.json"
    config_manifest = json.loads(config_manifest_path.read_bytes())
    config_manifest["files"].append(review_entry)
    config_manifest["files"].extend(extra_entries)
    config_manifest_path.write_text(json.dumps(config_manifest), encoding="utf-8")
    provenance["config_manifest"]["sha256"] = hashlib.sha256(config_manifest_path.read_bytes()).hexdigest()
    execution["config_manifest_sha256"] = provenance["config_manifest"]["sha256"]
    prices = PricingSnapshot(snapshot_id="campaign-integration", verified_at="2026-09-10", source="synthetic rates",
        models={"openai:gpt-5.2|default|fixture-standard|USD":
            replace(next(iter(old_prices.models.values())), pricing_model="gpt-5.2", pricing_version="campaign-integration")})
    amendment.update(campaign_id="synthetic-campaign", campaign_cap_usd="2", pricing_snapshot=prices.metadata(),
        provenance=provenance, execution_identity=execution,
        case={"case_id": "synthetic-ar-full", "max_calls": pages + 1, "ceiling_usd": "2"})
    campaign_identity = fingerprint({"campaign_id": amendment["campaign_id"], "case_id": amendment["case"]["case_id"],
        "source_sha256": provenance["source"]["sha256"], "full_case_pages": list(range(1, pages + 1))})
    sdk = CampaignSDK(correction=defect)
    sdk.target_lang = lang
    client = client_for(sdk)
    requests, identity = _prepare_case(config, campaign_identity, client, {"case_pages": pages}, tmp_path / "prepare-only",
        review_json=review_json, reviewed_evidence=reviewed_case.evidence if reviewed_case else None)
    assert not sdk.requests
    amendment["stable_run_identity"] = stable_acceptance_run_identity(identity)
    limit = amendment["dispatch_limits"]["openai:translation"]
    limit.update(requested_model="gpt-5.2", max_input_tokens=50000, max_output_tokens=256,
        ceiling_usd="0.2", allowed_pages=list(range(1, pages + 1)), max_calls=pages)
    prepare_accountant = DispatchAccounting(tmp_path / "prepare-accounting", run_identity={"synthetic": True},
        dispatch_limits={"openai:translation": limit, "openai:correction": limit})
    hashes = {}
    for number, request in requests.items():
        with accounting_context(prepare_accountant, purpose="translation", page_number=number):
            hashes[number] = request_fingerprint(client.prepare_page_request(**request))
    return SimpleNamespace(config=config, sdk=sdk, client=client, ledger=ledger, amendment=amendment,
        prices=prices, historical=historical, execution=execution, identity=identity,
        requests=requests, hashes=hashes, prepare_accountant=prepare_accountant, authority=authority,
        review_entry=review_entry, reviewed_case=reviewed_case, evidence_entries=extra_entries)


def _approve(case, pages, *, purpose="translation", pending=None):
    amendment = deepcopy(case.amendment)
    state = json.loads(case.ledger.read_bytes())
    campaign = state.get("acceptance_campaigns", {}).get(amendment["campaign_id"])
    amendment["prior_amendments"] = campaign["amendments"] if campaign else []
    amendment["prior_reservations_fingerprint"] = fingerprint({key: row for key, row in state["reservations"].items()
        if row.get("execution", {}).get("campaign_id") == amendment["campaign_id"]})
    limit = deepcopy(amendment["dispatch_limits"]["openai:translation"])
    hashes = case.hashes
    if pending is not None:
        record = json.loads(pending.read_bytes())
        with accounting_context(case.prepare_accountant, purpose="correction", page_number=pages[0]):
            exact = case.client.prepare_page_request(**record["payload"]["request"])
        hashes = {pages[0]: request_fingerprint(exact)}
        limit["pending_correction_files"] = {record["sha256"]: {"path": str(pending.resolve()),
            "sha256": hashlib.sha256(pending.read_bytes()).hexdigest()}}
    limit.update(allowed_pages=list(pages), max_calls=len(pages),
        allowed_request_hashes=[hashes[number] for number in pages],
        approved_calls=[{"page_number": number, "attempt": 1, "request_hash": hashes[number],
            **({"pending_correction_sha256": record["sha256"]} if pending is not None else {})} for number in pages])
    amendment["dispatch_limits"] = {f"openai:{purpose}": limit}
    path = case.authority / f"phase-{len(amendment['prior_amendments'])}-{purpose}.json"
    assert not path.exists()
    digest = _save(path, amendment)
    return path, digest


def _run(case, approval, *, resume=False):
    path, digest = approval
    budget = LegacyAcceptanceBudget(case.ledger, amendment_path=path, expected_amendment_sha256=digest,
        run_identity=case.identity, execution_identity=case.execution, pricing_snapshot=case.prices)
    holder = {}
    continuation = build_acceptance_continuation(budget=budget, client=case.client,
        accountant_supplier=lambda: holder["accountant"], source_review_file=case.review_entry)
    def factory(**arguments):
        result = build_acceptance_accounting(**arguments, ledger_path=case.ledger,
            amendment_path=path, expected_amendment_sha256=digest,
            execution_identity=case.execution, pricing_snapshot=case.prices)
        holder["accountant"] = result
        return result
    def forbidden(*args, **kwargs):
        pytest.fail("OCR/ambient provider operation forbidden")
    workflow = TranslationWorkflow(client=case.client, gui_settings={}, environment_loader=lambda: None,
        ocr_engine_factory=forbidden, translation_protocol="legal_blocks_v2",
        accounting_factory=factory, acceptance_continuation=continuation)
    return workflow.run(replace(case.config, resume=resume))


def test_actual_v2_ar_pilot_expansion_reuses_full_case_commits_and_original_ledger(tmp_path):
    case = _campaign(tmp_path)
    pilot = _approve(case, (1, 5, 6, 9))
    first = _run(case, pilot)
    assert not first.success and first.error == "acceptance_phase_complete"
    assert first.completed_pages == 4 and len(case.sdk.requests) == 4
    identity = load_run_state(first.run_dir / "run_state.json").protocol_identity
    prior_commits = {path.name: path.read_bytes() for path in (first.run_dir / "pages").glob("*.commit.json")}
    ledger_before = case.ledger.read_bytes()
    assert not _run(case, pilot, resume=True).success
    assert len(case.sdk.requests) == 4 and case.ledger.read_bytes() == ledger_before
    expansion = _approve(case, (2, 3, 4, 7, 8))
    final = _run(case, expansion, resume=True)
    assert final.success and final.completed_pages == 9 and len(case.sdk.requests) == 9
    state = load_run_state(final.run_dir / "run_state.json")
    assert state.protocol_identity == identity
    assert all((final.run_dir / "pages" / name).read_bytes() == data for name, data in prior_commits.items())
    ledger = json.loads(case.ledger.read_bytes())
    assert ledger["reservations"]["historical-1"] == case.historical["historical-1"]
    assert len(ledger["reservations"]) == 10
    new_rows = [row for row in ledger["reservations"].values() if "execution" in row]
    assert sorted(row["execution"]["page_number"] for row in new_rows) == list(range(1, 10))
    assert {row["execution"]["authorization_sha256"] for row in new_rows} == {pilot[1], expansion[1]}
    assert sum(Decimal(row["actual_usd"]) for row in new_rows) == Decimal("0.00594")
    before = case.ledger.read_bytes()
    assert _run(case, expansion, resume=True).success
    assert len(case.sdk.requests) == 9 and case.ledger.read_bytes() == before


def test_actual_v2_separate_correction_amendment_uses_retained_primary_and_exact_pending(tmp_path):
    case = _campaign(tmp_path, pages=1, defect=True)
    primary = _approve(case, (1,))
    first = _run(case, primary)
    assert not first.success and len(case.sdk.requests) == 1
    pending = first.run_dir / "acceptance_private" / "page_0001.correction.pending.json"
    assert pending.exists()
    before = case.ledger.read_bytes()
    assert not _run(case, primary, resume=True).success
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == before
    correction = _approve(case, (1,), purpose="correction", pending=pending)
    final = _run(case, correction, resume=True)
    assert final.success and len(case.sdk.requests) == 2
    state = load_run_state(final.run_dir / "run_state.json")
    assert state.pages["1"]["input_tokens"] == 200 and state.pages["1"]["output_tokens"] == 120
    ledger = json.loads(case.ledger.read_bytes())
    new_rows = [row for row in ledger["reservations"].values() if "execution" in row]
    assert sorted(row["execution"]["purpose"] for row in new_rows) == ["correction", "translation"]
    assert len(new_rows) == 2 and all(row["status"] == "finalized" for row in new_rows)
    before = case.ledger.read_bytes()
    assert _run(case, correction, resume=True).success
    assert len(case.sdk.requests) == 2 and case.ledger.read_bytes() == before


def test_real_authorizer_rejects_unapproved_endpoint_before_intent_or_reservation(tmp_path):
    case = _campaign(tmp_path, pages=1)
    primary = _approve(case, (1,))
    before = case.ledger.read_bytes()
    case.sdk.base_url = "https://not-approved.invalid/v1/"
    result = _run(case, primary)
    assert not result.success and not case.sdk.requests
    assert not list((result.run_dir / "acceptance_private").glob("*.intent.json"))
    assert case.ledger.read_bytes() == before


def test_real_correction_pending_byte_drift_blocks_before_any_repeat(tmp_path):
    case = _campaign(tmp_path, pages=1, defect=True)
    first = _run(case, _approve(case, (1,)))
    pending = first.run_dir / "acceptance_private" / "page_0001.correction.pending.json"
    correction = _approve(case, (1,), purpose="correction", pending=pending)
    before = case.ledger.read_bytes()
    pending.write_bytes(pending.read_bytes() + b"\n")  # Isolated deliberate evidence corruption.
    with pytest.raises(BudgetError, match="pending correction"):
        _run(case, correction, resume=True)
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == before


@pytest.mark.parametrize("failure", ["missing", "unapproved_file", "byte_drift", "unresolved_later_page"])
def test_real_acceptance_builder_requires_complete_approved_source_review_before_spending(tmp_path, failure):
    case = _campaign(tmp_path, pages=2)
    if failure == "unresolved_later_page":
        # Explicitly approved synthetic bad review: schema checks, not just its
        # outer hash, must reject page 2 before the page-1 pilot can spend.
        path = Path(case.review_entry["path"])
        review = json.loads(path.read_bytes())
        review["pages"][1]["unresolved_findings"] = ["critical_source_field"]
        path.write_text(json.dumps(review), encoding="utf-8")
        case.review_entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest_path = case.authority / "config-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"][-1] = case.review_entry
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        case.amendment["provenance"]["config_manifest"]["sha256"] = digest
        case.execution["config_manifest_sha256"] = digest
    approval = _approve(case, (1,))
    before = case.ledger.read_bytes()
    if failure == "missing":
        case.review_entry = None
    elif failure == "unapproved_file":
        original = Path(case.review_entry["path"])
        copy = case.authority / "unapproved-review.json"
        copy.write_bytes(original.read_bytes())
        case.review_entry = {**case.review_entry, "path": str(copy.resolve())}
    elif failure == "byte_drift":
        path = Path(case.review_entry["path"])
        path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises((BudgetError, ValueError)):
        _run(case, approval)
    assert not case.sdk.requests and case.ledger.read_bytes() == before
    assert not list(case.config.output_dir.rglob("*.intent.json"))


def test_review_bytes_rechecked_between_initial_builder_and_authorization(tmp_path):
    case = _campaign(tmp_path, pages=1)
    path, digest = _approve(case, (1,))
    budget = LegacyAcceptanceBudget(case.ledger, amendment_path=path, expected_amendment_sha256=digest,
        run_identity=case.identity, execution_identity=case.execution, pricing_snapshot=case.prices)
    continuation = build_acceptance_continuation(budget=budget, client=case.client,
        accountant_supplier=lambda: SimpleNamespace(budget_context=budget), source_review_file=case.review_entry)
    before = case.ledger.read_bytes()
    review_path = Path(case.review_entry["path"])
    review_path.write_bytes(review_path.read_bytes() + b"\n")
    with pytest.raises(BudgetError, match="bytes changed"):
        continuation.authorize({"page_number": 1, "purpose": "translation", "attempt": 1,
                                "request": case.requests[1]})
    assert not case.sdk.requests and case.ledger.read_bytes() == before


def _forbid_source_acquisition(monkeypatch):
    import socket
    import subprocess
    from legalpdf_translate import layout_integration, ocr_helpers
    from legalpdf_translate import word_automation
    def forbidden(*args, **kwargs):
        pytest.fail("No extraction, OCR, render, subprocess or external network in reviewed-source lane")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", forbidden)
    monkeypatch.setattr(workflow_module, "_assess_extraction_integrity", forbidden)
    monkeypatch.setattr(TranslationWorkflow, "_resolve_ocr_engine_for_reason", forbidden)
    monkeypatch.setattr(layout_integration, "_render_source", forbidden)
    monkeypatch.setattr(ocr_helpers, "render_image_png", forbidden)
    monkeypatch.setattr(word_automation, "export_docx_to_pdf_in_word", forbidden)
    monkeypatch.setattr(word_automation, "probe_word_pdf_export_support", forbidden)
    monkeypatch.setattr(word_automation, "run_word_pdf_export_canary", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


@pytest.mark.parametrize("pages,lang", [(9, TargetLang.AR), (2, TargetLang.FR), (2, TargetLang.EN)])
def test_reviewed_actual_workflow_skips_raw_sources_and_preserves_full_case_evidence(tmp_path, monkeypatch, pages, lang):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=pages, reviewed=True, lang=lang)
    assert not case.sdk.requests
    approval = _approve(case, tuple(range(1, pages + 1)))
    result = _run(case, approval)
    assert result.success, result.error
    assert len(case.sdk.requests) == pages
    state = load_run_state(result.run_dir / "run_state.json")
    for n in range(1, pages + 1):
        source = json.loads((result.run_dir / "pages" / f"page_{n:04d}.source_structure.json").read_bytes())
        expected = case.reviewed_case.sources[n]
        assert source == expected.to_dict()
        assert source["uncertain"] and source["blocks"][0]["bbox"] is None
        prompt = case.requests[n]["prompt_text"]
        payload, _ = json.JSONDecoder().raw_decode(prompt)
        assert payload["blocks"][0]["text"] == expected.text
        assert "context_only_not_to_translate" not in payload
        assert source["blocks"][0]["id"] == payload["blocks"][0]["id"]
        row = state.pages[str(n)]
        assert row["source_route"] == "reviewed_image_transcription"
        assert row["source_coverage_status"] == "reviewed_image_transcription"
        assert row["layout_review_required"] is True
        assert row["source_review_status"] == "explicit_review_accepted"
        assert row["fidelity_review_status"] == "not_evaluated"
        assert row["ocr_attempts_count"] == 0 and row["ocr_requested"] is False
    from docx import Document
    paragraphs = "\n".join(p.text for p in Document(result.output_docx).paragraphs)
    assert TARGETS[lang] in paragraphs
    assert "p0001_b100000001" not in paragraphs
    before = case.ledger.read_bytes()
    replay = _run(case, approval, resume=True)
    assert replay.success and len(case.sdk.requests) == pages
    assert case.ledger.read_bytes() == before


@pytest.mark.parametrize("failure", ["missing", "unapproved", "changed_candidate", "changed_raw", "unaccepted"])
def test_reviewed_builder_rejects_before_first_fake_dispatch(tmp_path, monkeypatch, failure):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=2, reviewed=True)
    if failure == "unapproved":
        manifest_path = case.authority / "config-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        manifest["files"].remove(case.evidence_entries[0])
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        case.amendment["provenance"]["config_manifest"]["sha256"] = digest
        case.execution["config_manifest_sha256"] = digest
    if failure == "unaccepted":
        review_path = Path(case.review_entry["path"])
        review = json.loads(review_path.read_bytes())
        review["pages"][1]["source_fidelity"] = "not_evaluated"
        review_path.write_text(json.dumps(review), encoding="utf-8")
        case.review_entry["sha256"] = hashlib.sha256(review_path.read_bytes()).hexdigest()
        manifest_path = case.authority / "config-manifest.json"
        manifest = json.loads(manifest_path.read_bytes())
        for index, entry in enumerate(manifest["files"]):
            if entry["path"] == case.review_entry["path"]:
                manifest["files"][index] = case.review_entry
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        case.amendment["provenance"]["config_manifest"]["sha256"] = digest
        case.execution["config_manifest_sha256"] = digest
    approval = _approve(case, (1,))
    if failure == "missing":
        Path(case.evidence_entries[0]["path"]).unlink()  # Fictional fixture only.
    if failure in {"changed_candidate", "changed_raw"}:
        entry = case.evidence_entries[0 if failure == "changed_candidate" else -1]
        artifact = Path(entry["path"])
        artifact.write_bytes(artifact.read_bytes() + b"changed")
    before = case.ledger.read_bytes()
    with pytest.raises(ValueError):
        _run(case, approval)
    assert not case.sdk.requests and case.ledger.read_bytes() == before


def test_reviewed_evidence_rechecked_after_builder_before_raw_or_paid_work(tmp_path, monkeypatch):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=2, reviewed=True)
    approval = _approve(case, (1,))
    original = build_acceptance_continuation
    def builder(**kwargs):
        continuation = original(**kwargs)
        path = Path(case.evidence_entries[0]["path"])
        path.write_bytes(path.read_bytes() + b"changed after approval load")
        return continuation
    monkeypatch.setattr(__import__(__name__, fromlist=["unused"]), "build_acceptance_continuation", builder)
    before = case.ledger.read_bytes()
    with pytest.raises(ValueError):
        _run(case, approval)
    assert not case.sdk.requests and case.ledger.read_bytes() == before


def test_reviewed_separate_correction_reuses_saved_primary(tmp_path, monkeypatch):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=2, reviewed=True, defect=True)
    primary = _approve(case, (1,))
    first = _run(case, primary)
    assert not first.success and len(case.sdk.requests) == 1
    pending = first.run_dir / "acceptance_private" / "page_0001.correction.pending.json"
    assert pending.exists()
    before = case.ledger.read_bytes()
    assert not _run(case, primary, resume=True).success
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == before
    correction = _approve(case, (1,), purpose="correction", pending=pending)
    resumed = _run(case, correction, resume=True)
    assert resumed.completed_pages == 1 and len(case.sdk.requests) == 2


def test_reviewed_changed_input_after_response_preserves_paid_evidence_without_commit(tmp_path, monkeypatch):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=2, reviewed=True)
    approval = _approve(case, (1,))
    original = case.sdk.responses.create
    def response_then_drift(**request):
        response = original(**request)
        artifact = Path(case.evidence_entries[-1]["path"])
        artifact.write_bytes(artifact.read_bytes() + b"changed before commit")
        return response
    case.sdk.responses.create = response_then_drift
    result = _run(case, approval)
    assert not result.success and len(case.sdk.requests) == 1
    assert not (result.run_dir / "pages" / "page_0001.commit.json").exists()
    assert (result.run_dir / "acceptance_private" / "page_0001.primary.response.json").exists()
    before = case.ledger.read_bytes()
    with pytest.raises(ValueError):
        _run(case, approval, resume=True)
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == before


def test_reviewed_missing_guard_and_unapproved_request_never_dispatch(tmp_path, monkeypatch):
    from legalpdf_translate.acceptance_continuation import AcceptanceContinuationError
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=2, reviewed=True)
    with pytest.raises(AcceptanceContinuationError, match="recheck_required"):
        AcceptanceContinuation("a" * 64, (1, 2), (1,), lambda _: "b" * 64,
            Path(case.review_entry["path"]).read_text("utf-8"), case.reviewed_case.evidence)
    approval = _approve(case, (1,))
    case.sdk.base_url = "https://unapproved.invalid/v1/"
    before = case.ledger.read_bytes()
    result = _run(case, approval)
    assert not result.success and not case.sdk.requests
    assert not list((result.run_dir / "acceptance_private").glob("*.intent.json"))
    assert case.ledger.read_bytes() == before


def test_reviewed_identity_changes_and_legacy_resume_is_not_reinterpreted(tmp_path, monkeypatch):
    case = _campaign(tmp_path, pages=2)
    original = _run(case, _approve(case, (1,)))
    assert original.completed_pages == 1
    _forbid_source_acquisition(monkeypatch)
    from tests.test_reviewed_source import reviewed_fixture, decision_envelope
    from legalpdf_translate.source_document import source_page_identity, source_page_dimensions
    fixture = reviewed_fixture(2, document_bytes=case.config.pdf_path.read_bytes(),
        page_identities={n: source_page_identity(case.config.pdf_path, n) for n in (1, 2)},
        page_sizes={n: source_page_dimensions(case.config.pdf_path, n) for n in (1, 2)})
    review = json.dumps(decision_envelope(fixture))
    continuation = AcceptanceContinuation("a" * 64, (1, 2), (2,), lambda _: pytest.fail("No dispatch"),
                                         review, fixture.evidence, lambda: None)
    workflow = TranslationWorkflow(client=case.client, gui_settings={}, environment_loader=lambda: None,
        translation_protocol="legal_blocks_v2", acceptance_continuation=continuation)
    before = case.ledger.read_bytes()
    with pytest.raises(ValueError, match="incompatible"):
        workflow.run(replace(case.config, resume=True))
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == before
