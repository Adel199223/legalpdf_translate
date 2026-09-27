"""Arabic review responses must not run unrelated capability/native probes."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import browser_arabic_review, word_automation
from legalpdf_translate.shadow_web import app as browser


_ROOT = "/api/translation/arabic-review"
_WORKSPACE = "review-test"
_JOB_ID = "fictional-ar-job"


@pytest.fixture
def review_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Only the real review manager and route serialization are under test. The
    # injected bundle isolates credentials, listeners, Gmail and process state.
    clock = [1000.0]
    monkeypatch.setattr(word_automation, "time", SimpleNamespace(time=lambda: clock[0]))
    monkeypatch.setattr(browser_arabic_review, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(word_automation, "_WORD_READINESS_CACHE", {})
    calls: list[str] = []

    def forbidden(*_args, **_kwargs):
        pytest.fail("Arabic review response crossed an unrelated capability or native boundary")

    def provider_state(**_kwargs):
        calls.append("provider_state")
        # A regression into response decoration reaches the actual cache logic:
        # both cold and expired entries would hit the forbidden Word probe.
        word_automation.assess_word_pdf_export_readiness(cache_scope="review-response-test")
        return {}

    monkeypatch.setattr(word_automation, "probe_word_pdf_export_support", forbidden)
    monkeypatch.setattr(word_automation, "run_word_pdf_export_canary", forbidden)
    monkeypatch.setattr(browser_arabic_review, "open_docx_in_word", forbidden)
    monkeypatch.setattr(browser_arabic_review, "align_right_and_save_docx_in_word", forbidden)
    docx_path = tmp_path / "fictional-ar.docx"
    # The manager only fingerprints an existing durable file; no document parser
    # or renderer is involved in this route-boundary fixture.
    docx_path.write_bytes(b"fictional baseline")
    job = {
        "job_id": _JOB_ID,
        "job_kind": "translate",
        "status": "completed",
        "runtime_mode": "shadow",
        "workspace_id": _WORKSPACE,
        "config": {"target_lang": "AR"},
        "result": {"save_seed": {"target_lang": "AR", "output_docx": str(docx_path)}},
    }
    jobs = {_JOB_ID: job}
    manager = browser_arabic_review.ArabicDocxReviewManager()
    services = replace(
        browser.offline_browser_app_services(state_root=tmp_path / "isolated"),
        translation_jobs_factory=lambda: SimpleNamespace(get_job=jobs.get),
        arabic_reviews_factory=lambda: manager,
        browser_provider_state=provider_state,
        browser_capability_snapshot=forbidden,
    )
    app = browser.create_shadow_app(
        repo_root=tmp_path / "empty-repo", port=18877,
        enable_live_gmail_bridge=False, services=services,
    )
    with TestClient(app, headers={
        "X-LegalPDF-Runtime-Mode": "shadow",
        "X-LegalPDF-Workspace-Id": _WORKSPACE,
    }) as client:
        yield SimpleNamespace(client=client, app=app, clock=clock, calls=calls,
                              job=job, docx_path=docx_path, manager=manager)
    assert calls == []


def _review(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["capability_flags"] == {}
    return payload["normalized_payload"]["arabic_review"]


@pytest.mark.parametrize("cache_state", ["cold", "expired"])
def test_idle_unresolved_and_saved_polls_stay_passive_across_cache_expiry(review_client, cache_state):
    env = review_client
    if cache_state == "expired":
        word_automation._WORD_READINESS_CACHE["review-response-test"] = (
            env.clock[0] - 61, {"finalization_ready": True},
        )
    cache_before = dict(word_automation._WORD_READINESS_CACHE)
    idle = _review(env.client.get(f"{_ROOT}/state"))
    assert idle["required"] is False and idle["resolved"] is True
    for advance in (0, 61, 122, 600):
        env.clock[0] += advance
        pending = _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))
        assert pending["required"] is True and pending["resolved"] is False
        assert pending["status"] == "required"
        assert pending["completion_key"] == f"job:{_JOB_ID}:translate"

    env.docx_path.write_bytes(b"fictional saved revision with different length")
    detected = _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))
    assert detected["save_detected"] is True and detected["resolved"] is False
    env.clock[0] += 2
    for _ in range(3):
        resolved = _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))
        assert resolved["resolved"] is True and resolved["resolution"] == "saved"
        env.clock[0] += 61
    assert word_automation._WORD_READINESS_CACHE == cache_before
    assert env.calls == []


@pytest.mark.parametrize("ownership", ["unknown", "other-workspace", "other-mode"])
def test_state_not_found_is_passive(review_client, ownership):
    env = review_client
    job_id = _JOB_ID
    if ownership == "unknown":
        job_id = "missing-job"
    elif ownership == "other-workspace":
        env.job["workspace_id"] = "different-owner"
    else:
        env.job["runtime_mode"] = "live"
    response = env.client.get(f"{_ROOT}/state", params={"job_id": job_id})
    assert response.status_code == 404
    assert response.json()["capability_flags"] == {}
    assert response.json()["diagnostics"]["error"]


@pytest.mark.parametrize("route", ["state", "open", "align-right-save", "continue"])
@pytest.mark.parametrize("invalid", ["unfinished-job", "wrong-language", "missing-file"])
def test_all_review_validation_errors_are_passive(review_client, route, invalid):
    env = review_client
    if invalid == "unfinished-job":
        env.job["status"] = "running"
    elif invalid == "wrong-language":
        env.job["result"]["save_seed"]["target_lang"] = "EN"
    else:
        env.job["result"]["save_seed"]["output_docx"] = str(env.docx_path.with_name("absent.docx"))
    payload = {"job_id": _JOB_ID, "continuation": "continue_now"}
    response = (env.client.get(f"{_ROOT}/{route}", params=payload) if route == "state"
                else env.client.post(f"{_ROOT}/{route}", json=payload))
    assert response.status_code == 422
    assert response.json()["status"] == "failed"
    assert response.json()["capability_flags"] == {}
    assert response.json()["diagnostics"]["error"]


@pytest.mark.parametrize("route", ["open", "align-right-save", "continue"])
def test_action_unknown_job_error_is_passive(review_client, route):
    response = review_client.client.post(f"{_ROOT}/{route}", json={"job_id": "missing-job"})
    assert response.status_code == 422
    assert response.json()["capability_flags"] == {}


def test_explicit_open_and_align_actions_run_only_the_requested_word_action(review_client, monkeypatch):
    env = review_client
    actions = []

    def action_result(action, path):
        actions.append((action, Path(path)))
        return word_automation.WordAutomationResult(ok=True, action=action, message="Fictional action completed.")

    monkeypatch.setattr(browser_arabic_review, "open_docx_in_word",
                        lambda path: action_result("open_docx", path))
    monkeypatch.setattr(browser_arabic_review, "align_right_and_save_docx_in_word",
                        lambda path: action_result("align_right_and_save_docx", path))
    opened = env.client.post(f"{_ROOT}/open", json={"job_id": _JOB_ID})
    assert _review(opened)["resolved"] is False
    assert opened.json()["diagnostics"]["word_action"]["action"] == "open_docx"
    _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))
    aligned = env.client.post(f"{_ROOT}/align-right-save", json={"job_id": _JOB_ID})
    assert _review(aligned)["resolved"] is True
    _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))
    assert actions == [("open_docx", env.docx_path), ("align_right_and_save_docx", env.docx_path)]
    assert env.calls == []


@pytest.mark.parametrize("continuation", ["continue_now", "continue_without_changes"])
def test_explicit_continuation_resolves_without_native_actions(review_client, continuation):
    env = review_client
    response = env.client.post(f"{_ROOT}/continue", json={"job_id": _JOB_ID, "continuation": continuation})
    assert _review(response)["resolved"] is True
    assert _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))["resolved"] is True


def test_invalid_continuation_remains_unresolved_without_probes(review_client):
    env = review_client
    response = env.client.post(f"{_ROOT}/continue", json={"job_id": _JOB_ID, "continuation": "invalid"})
    assert response.status_code == 422
    assert response.json()["capability_flags"] == {}
    assert _review(env.client.get(f"{_ROOT}/state", params={"job_id": _JOB_ID}))["resolved"] is False


def test_validation_helper_preserves_existing_default_capability_behavior(review_client, monkeypatch):
    context = review_client.app.state.shadow_context
    target = browser.ActiveBrowserTarget(
        mode="shadow", workspace_id=_WORKSPACE,
        data_paths=context.services.detect_data_paths(mode="shadow", repo=context.repo_root,
                                                      identity=context.build_identity),
    )
    calls = []

    def capabilities(actual_context, actual_target):
        calls.append((actual_context, actual_target))
        return {"fictional_capability": {"status": "ok"}}

    monkeypatch.setattr(browser, "_browser_capability_flags", capabilities)
    default_response = browser._validation_error_response(context, target, message="Fictional error")
    assert json.loads(default_response.body)["capability_flags"] == {"fictional_capability": {"status": "ok"}}
    explicit_response = browser._validation_error_response(context, target, message="Fictional error", capability_flags={})
    assert json.loads(explicit_response.body)["capability_flags"] == {}
    assert calls == [(context, target)]
