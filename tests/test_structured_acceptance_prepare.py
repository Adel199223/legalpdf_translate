"""Synthetic request parity, including preferences absent from old test helpers."""
from copy import deepcopy
from dataclasses import replace
import json
import hashlib
from pathlib import Path

import pytest

from legalpdf_translate.acceptance_continuation import AcceptanceContinuationError
from legalpdf_translate.acceptance_budget import stable_acceptance_run_identity
from legalpdf_translate.acceptance_provenance import canonical_run_config, request_fingerprint
from legalpdf_translate.types import ReasoningEffort, EffortPolicy
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_acceptance_campaign_integration import _campaign, _forbid_source_acquisition, _approve
from tests.test_acceptance_budget_adapter import _provenance
from tests.test_structured_acceptance_run import invoke
from tests.test_acceptance_continuation import offline
from tooling.structured_acceptance_prepare import prepare_reviewed_requests, PreparationOnly


LIMITS = {"requested_service_tier": "default", "max_input_tokens": 400000, "max_output_tokens": 24000}


def arguments(tmp_path, monkeypatch, *, pages=2):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=pages, reviewed=True)
    return case, dict(config=case.config, preferences={}, campaign_id="synthetic-campaign",
        case_id="new-current-case", eligible_pages=(1,),
        source_review_json=Path(case.review_entry["path"]).read_text(),
        reviewed_source_evidence=case.reviewed_case.evidence, source_review_guard=lambda: None,
        dispatch_limits=LIMITS, directory=tmp_path / "current-prepare")


@pytest.mark.parametrize("legacy_key", [False, True])
def test_prepared_request_equals_actual_dispatch_with_complete_prompt_preferences(tmp_path, monkeypatch, legacy_key):
    case, args = arguments(tmp_path, monkeypatch)
    def row(source, target, tier=1):
        return dict(source_text=source, preferred_translation=target, tier=tier, source_lang="PT", match_mode="contains")
    project = tmp_path / "project-glossary.json"
    project.write_text(json.dumps({"AR": [row("factos", "وقائع"), row("documento", "project choice")]}), encoding="utf-8")
    context = tmp_path / "context.txt"
    context.write_text("FILE CONTEXT WINS", encoding="utf-8")
    settings = {"glossaries_by_lang" if legacy_key else "personal_glossaries_by_lang": {
        "AR": [row("arguido", "المتهم"), row("documento", "مستند"), row("tribunal", "DISABLED TIER", 2)]},
        "enabled_glossary_tiers_by_target_lang": {"AR": [1]},
        "prompt_addendum_by_lang": {"AR": "  Preserve all legal conditions.  "},
        "perf_timeout_text_seconds": 91, "perf_timeout_image_seconds": 123}
    config = replace(case.config, glossary_file=project, context_file=context, context_text="IGNORED INLINE CONTEXT")
    args.update(config=config, preferences=settings)
    before = deepcopy(settings), canonical_run_config(config)
    prepared = prepare_reviewed_requests(**args)
    assert (settings, canonical_run_config(config)) == before
    assert prepared["sdk_calls_entered"] == 0 and not case.sdk.requests
    assert set(prepared["requests"]) == {1}
    assert not list(args["directory"].rglob("*.json"))
    expected = prepared["requests"][1]["request"]
    prompt = expected["input"][0]["content"][0]["text"]
    for part in ("factos", "وقائع", "arguido", "المتهم", "مستند", "FILE CONTEXT WINS", "Preserve all legal conditions."):
        assert part in prompt
    assert "DISABLED TIER" not in prompt and "IGNORED INLINE CONTEXT" not in prompt
    assert "project choice" not in prompt
    case.config = config
    case.identity = prepared["run_identity"]
    case.hashes = {1: prepared["requests"][1]["request_sha256"]}
    provenance, case.execution = _provenance(case.authority, source=config.pdf_path,
        runtime_config=canonical_run_config(config), preferences=settings)
    manifest_path = Path(provenance["config_manifest"]["path"])
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"].extend([case.review_entry, *case.evidence_entries,
        *[{"path": str(p.resolve()), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in (project, context)]])
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    provenance["config_manifest"]["sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    case.execution["config_manifest_sha256"] = provenance["config_manifest"]["sha256"]
    case.amendment.update(provenance=provenance, execution_identity=case.execution,
        stable_run_identity=stable_acceptance_run_identity(case.identity))
    case.amendment["case"]["case_id"] = args["case_id"]
    case.amendment["dispatch_limits"]["openai:translation"].update(LIMITS, ceiling_usd="1.5")
    case.sdk.max_retries = 0
    result = invoke(case, _approve(case, (1,)), preferences=settings)
    assert result.error == "acceptance_phase_complete", result.error
    assert len(case.sdk.requests) == 1
    sent = {k: v for k, v in case.sdk.requests[0].items() if k != "timeout"}
    assert sent == expected
    assert request_fingerprint(sent) == prepared["requests"][1]["request_sha256"]
    state = json.loads((result.run_dir / "run_state.json").read_bytes())
    assert state["protocol_identity"] == prepared["run_identity"]["protocol_identity"]
    hydrated = TranslationWorkflow(client=object(), gui_settings={})
    hydrated._hydrate_request_settings(config=config, gui_settings=settings)
    assert hydrated._translation_timeout_text_seconds == 91
    assert hydrated._translation_timeout_image_seconds == 123


@pytest.mark.parametrize("change", ["tier", "output", "input", "pages", "evidence", "resume", "workers", "xhigh", "resolved_xhigh"])
def test_preparation_rejects_scope_drift_without_dispatch(tmp_path, monkeypatch, change):
    case, args = arguments(tmp_path, monkeypatch)
    args["dispatch_limits"] = deepcopy(LIMITS)
    if change == "tier": args["dispatch_limits"]["requested_service_tier"] = "auto"
    elif change == "output": args["dispatch_limits"]["max_output_tokens"] = 128000
    elif change == "input": args["dispatch_limits"]["max_input_tokens"] = 1
    elif change == "pages": args["eligible_pages"] = (3,)
    elif change == "evidence": args["reviewed_source_evidence"] = None
    elif change == "resume": args["config"] = replace(case.config, resume=True)
    elif change == "workers": args["config"] = replace(case.config, workers=2)
    elif change == "xhigh": args["config"] = replace(case.config, allow_xhigh_escalation=True)
    else: args["config"] = replace(case.config, effort=ReasoningEffort.XHIGH, effort_policy=EffortPolicy.FIXED_XHIGH)
    with pytest.raises(ValueError):
        prepare_reviewed_requests(**args)
    assert not case.sdk.requests
    assert not list(args["directory"].rglob("*.json"))


def test_preparation_refuses_existing_folder_and_rechecks_source(tmp_path, monkeypatch):
    case, args = arguments(tmp_path, monkeypatch)
    guards = []
    args["source_review_guard"] = lambda: guards.append(True)
    prepare_reviewed_requests(**args)
    assert len(guards) >= 3
    with pytest.raises(FileExistsError):
        prepare_reviewed_requests(**args)
    assert not case.sdk.requests


def test_preparation_transport_and_accountant_cannot_dispatch():
    dry = PreparationOnly(LIMITS)
    for method in (dry.responses.create, dry.begin, dry.finish, dry.verify_dispatch):
        with pytest.raises(AcceptanceContinuationError, match="cannot_dispatch"):
            method()
    limits = dry.request_limits("openai", "translation", "gpt-5.2")
    limits["max_output_tokens"] = 1
    assert dry.request_limits("openai", "translation", "gpt-5.2") == LIMITS


@pytest.mark.parametrize("fail_at", [2, 3])
def test_review_guard_failure_during_preparation_leaves_no_paid_intent(tmp_path, monkeypatch, fail_at):
    case, args = arguments(tmp_path, monkeypatch)
    checks = []
    def guard():
        checks.append(True)
        if len(checks) == fail_at:
            raise AcceptanceContinuationError("fixture_source_changed")
    args["source_review_guard"] = guard
    with pytest.raises(AcceptanceContinuationError):
        prepare_reviewed_requests(**args)
    assert not case.sdk.requests and not list(args["directory"].rglob("*.json"))
