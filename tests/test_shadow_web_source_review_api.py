"""Owned public routes -> explicit operator actions -> real ordinary commits.

Only OCR renderer/SDK, queued-thread scheduling, upload page-count probing and
post-run metadata enrichment are synthetic boundaries. No review, candidate,
acceptance envelope or structured commit is injected into the positive flow.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import translation_service as jobs_module
from legalpdf_translate.browser_source_review import BrowserSourceReviewError, BrowserSourceReviewManager
from legalpdf_translate.browser_pdf_bundle import browser_pdf_bundle_manifest_path
from legalpdf_translate.checkpoint import build_run_paths
from legalpdf_translate.run_workspace_lock import run_workspace_slot
from legalpdf_translate.shadow_web import app as browser
from legalpdf_translate.shadow_web import source_review_api as review_api
from legalpdf_translate.translation_service import TranslationJobManager, build_translation_config
from tests.test_browser_source_review import capture_jobs, capture_lazy_client
from tests.test_ordinary_source_review_service import local_only, local_pass, explicit_decision
from tests.test_source_review_candidate import png


PREFIX = "/api/translation/source-reviews"
HEADERS = {"X-LegalPDF-Runtime-Mode": "shadow", "X-LegalPDF-Workspace-Id": "workspace-1"}


def api_case(tmp_path, monkeypatch, *, saved=None):
    local_calls = local_pass(monkeypatch)
    queued = capture_jobs(monkeypatch)
    clients, sdk_calls = capture_lazy_client(monkeypatch)
    jobs = TranslationJobManager()
    services = replace(browser.offline_browser_app_services(state_root=tmp_path / "state"),
        translation_jobs_factory=lambda: jobs, source_reviews_factory=BrowserSourceReviewManager)
    app = browser.create_shadow_app(repo_root=tmp_path / "empty-repo", port=18877,
                                   enable_live_gmail_bridge=False, services=services)
    context = app.state.shadow_context
    settings = services.detect_data_paths(mode="shadow").settings_path
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"page_breaks": False, "ocr_mode": "auto", "ocr_engine": "local_then_api",
        "keep_intermediates": True, "perf_max_transport_retries": 2, "perf_backoff_cap_seconds": 3.5,
        **(saved or {})}), encoding="utf-8")
    # The original upload route still saves the real bytes under the owned root.
    # Avoid its unrelated native PDF page-count and capability probes.
    monkeypatch.setattr(jobs_module, "get_source_page_count", lambda _: 1)
    monkeypatch.setattr(jobs_module, "build_translation_capability_flags", lambda **_: {})
    monkeypatch.setattr(browser, "build_translation_capability_flags", lambda **_: {})
    output = tmp_path / "output"
    output.mkdir()
    return SimpleNamespace(app=app, context=context, jobs=jobs, settings=settings, output=output,
        queued=queued, clients=clients, sdk_calls=sdk_calls, local_calls=local_calls)


def bundle(client, source, *, headers=HEADERS, attachment_id=""):
    manifest = {"source_path": str(source), "page_count": 1, "attachment_id": attachment_id,
        "pages": [{"page_number": 1, "mime_type": "image/png", "width_px": 200,
                   "height_px": 300, "file_name": "page.png"}]}
    return client.post("/api/browser-pdf/bundle", headers=headers,
        data={"manifest": json.dumps(manifest)}, files={"page_images": ("page.png", png(), "image/png")})


def upload(client, *, headers=HEADERS):
    response = client.post("/api/translation/upload-source", headers=headers,
        files={"file": ("fictional-source.pdf", b"Fictional browser-rendered document", "application/pdf")})
    assert response.status_code == 200, response.text
    source = Path(response.json()["normalized_payload"]["source_path"])
    response = bundle(client, source, headers=headers)
    assert response.status_code == 200, response.text
    return source


def form(c, source, **extra):
    return {"source_path": str(source), "output_dir": str(c.output), "target_lang": "EN",
        "workers": 1, "resume": False, "image_mode": "off", **extra}


def view(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"status", "normalized_payload", "diagnostics", "capability_flags"}
    assert payload["diagnostics"] == {}
    assert response.headers["cache-control"] == "no-store"
    return payload["normalized_payload"]["source_review"]


def prepare(client, c, source):
    return view(client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": form(c, source)}))


def save_and_submit(client, draft):
    review_id = draft["review_id"]
    # Dataclass conversion is only the explicit fictional operator's form action;
    # IDs/text/word boxes were obtained from the actual public acquisition view.
    decision = asdict(explicit_decision(draft["pages"][0]))
    current = view(client.post(f"{PREFIX}/{review_id}/pages/1", headers=HEADERS,
        json={"expected_generation": draft["generation"], "decision": decision}))
    return view(client.post(f"{PREFIX}/{review_id}/submit", headers=HEADERS,
        json={"expected_generation": current["generation"], "reviewer": "Fictional operator",
              "accept_source": True}))


def test_public_routes_create_genuine_reviewed_commits_and_recover_exact_operation(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    before = c.settings.read_bytes()
    assert c.context.source_reviews._jobs is c.jobs
    with TestClient(c.app) as client:
        source = upload(client)
        draft = prepare(client, c, source)
        assert draft["pages"][0]["decision"] is None and draft["status"] == "draft"
        assert not c.clients and not c.sdk_calls
        image = client.get(f"{PREFIX}/{draft['review_id']}/pages/1/image", headers=HEADERS)
        assert image.status_code == 200 and image.content == png()
        assert image.headers["cache-control"] == "no-store"
        assert str(tmp_path) not in json.dumps(draft) and "image_bytes" not in json.dumps(draft)
        revision = save_and_submit(client, draft)
        assert revision["reviewer_kind"] == "operator_review"
        assert not c.clients and not c.sdk_calls  # Acquisition never authenticates or translates.
        recovered = view(client.get(f"{PREFIX}/{draft['review_id']}", headers=HEADERS))
        assert recovered["revision_ids"] == [revision["revision_id"]]
        request = {"revision_id": revision["revision_id"], "operation_nonce": "a" * 32}
        response = client.post(f"{PREFIX}/{draft['review_id']}/translate", headers=HEADERS, json=request)
        assert response.status_code == 200, response.text
        job = response.json()["normalized_payload"]["job"]
        assert job["status"] == "queued" and len(c.queued) == 1
        repeated = client.post(f"{PREFIX}/{draft['review_id']}/translate", headers=HEADERS, json=request)
        assert repeated.json()["normalized_payload"]["job"]["job_id"] == job["job_id"]
        assert len(c.queued) == 1 and not c.sdk_calls
        recovered = view(client.get(f"{PREFIX}/{draft['review_id']}", headers=HEADERS))
        assert recovered["translation_jobs"] == [{"job_id": job["job_id"], "revision_id": revision["revision_id"]}]
        c.queued.pop(0)()  # Real Workflow, real OpenAIResponsesClient, synthetic SDK only.
        completed = client.get(f"/api/translation/jobs/{job['job_id']}", headers=HEADERS)
        assert completed.status_code == 200, completed.text
        completed = completed.json()["normalized_payload"]["job"]
        assert completed["status"] == "completed", completed["diagnostics"]
    assert len(c.clients) == len(c.sdk_calls) == len(c.local_calls) == 1
    assert c.clients[0]._max_transport_retries == 2 and c.clients[0]._backoff_cap_seconds == 3.5
    assert c.settings.read_bytes() == before
    run = Path(completed["artifacts"]["run_dir"])
    state = json.loads((run / "run_state.json").read_bytes())
    assert state["settings"]["page_breaks"] is False
    assert state["settings"]["ordinary_source_review"]["revision_id"] == revision["revision_id"]
    assert state["pages"]["1"]["structured_commit"]
    assert (run / "pages/page_0001.commit.json").is_file()
    structure = json.loads((run / "pages/page_0001.source_structure.json").read_bytes())
    assert structure["metadata"]["reviewed_source"]["review_kind"] == "operator_review"


@pytest.mark.parametrize("headers,query,extra,code", [
    ({}, "", {}, "explicit_scope_required"),
    ({"X-LegalPDF-Runtime-Mode": "shadow"}, "", {}, "explicit_scope_required"),
    ({**HEADERS, "X-LegalPDF-Workspace-Id": "bad workspace"}, "", {}, "explicit_scope_required"),
    (HEADERS, "?mode=live", {}, "scope_conflict"),
    (HEADERS, "?workspace=another", {}, "scope_conflict"),
    (HEADERS, "", {"mode": "live"}, "scope_conflict"),
    (HEADERS, "?mode=shadow&mode=live", {}, "scope_conflict"),
    (HEADERS, "", {"workspace_id": "another"}, "scope_conflict"),
])
def test_new_routes_require_explicit_conflict_free_scope_before_service(tmp_path, monkeypatch, headers, query, extra, code):
    c = api_case(tmp_path, monkeypatch)
    monkeypatch.setattr(c.context.source_reviews, "prepare", lambda **_: pytest.fail("No acquisition"))
    with TestClient(c.app) as client:
        response = client.post(PREFIX + "/prepare" + query, headers=headers,
                               json={"form_values": {}, **extra})
    assert response.status_code == 422
    assert response.json()["diagnostics"] == {"error": "source_review_" + code}
    assert not c.local_calls and not c.clients


@pytest.mark.parametrize("body,code,status", [
    ('{"form_values":{},"form_values":{}}', "invalid_json", 422),
    ('{"form_values":{},"evidence_path":"fictional-private"}', "invalid_request", 422),
    ('{"form_values":{"x":NaN}}', "invalid_json", 422),
    ('{"form_values":{"x":"' + 'x' * (2 * 1024 * 1024) + '"}}', "request_too_large", 413),
], ids=["duplicate-key", "unexpected-field", "nonfinite-value", "oversized-body"])
def test_bounded_json_and_fixed_diagnostics(tmp_path, monkeypatch, body, code, status):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        response = client.post(PREFIX + "/prepare", headers={**HEADERS, "Content-Type": "application/json"}, content=body)
    assert response.status_code == status
    assert response.json()["diagnostics"] == {"error": "source_review_" + code}
    assert response.json()["normalized_payload"] == {}
    assert not c.local_calls and not c.clients


def test_foreign_and_arbitrary_sources_fail_before_bundle_write_or_review(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    arbitrary = tmp_path / "not-uploaded.pdf"
    arbitrary.write_bytes(b"Fictional foreign file")
    with TestClient(c.app) as client:
        owned = upload(client)
        monkeypatch.setattr(browser, "write_browser_pdf_bundle", lambda **_: pytest.fail("No foreign bundle write"))
        for source, headers in ((arbitrary, HEADERS), (owned, {**HEADERS, "X-LegalPDF-Workspace-Id": "another"}),
                                (owned, {**HEADERS, "X-LegalPDF-Runtime-Mode": "live"})):
            response = bundle(client, source, headers=headers)
            assert response.status_code == 422
            response = client.post(PREFIX + "/prepare", headers=headers, json={"form_values": form(c, source)})
            assert response.status_code == 422
            assert response.json()["diagnostics"] == {"error": "source_review_source_unavailable"}
    assert not browser_pdf_bundle_manifest_path(arbitrary).exists()
    assert not c.local_calls and not c.clients


def test_gmail_bundle_requires_exact_backend_attachment_before_write(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    attachment = tmp_path / "backend-attachment.pdf"
    attachment.write_bytes(b"Fictional backend-owned attachment")
    recorded = []
    monkeypatch.setattr(c.context.gmail_sessions, "current_attachment_file", lambda **kw:
        attachment if kw == {"runtime_mode": "shadow", "workspace_id": "workspace-1", "attachment_id": "att-exact"} else None,
        raising=False)
    monkeypatch.setattr(c.context.gmail_sessions, "record_browser_pdf_bundle", lambda **kw: recorded.append(kw), raising=False)
    with TestClient(c.app) as client:
        response = bundle(client, attachment, attachment_id="att-exact")
        assert response.status_code == 200, response.text
        assert len(recorded) == 1 and recorded[0]["source_path"] == attachment.resolve()
        monkeypatch.setattr(browser, "write_browser_pdf_bundle", lambda **_: pytest.fail("Resolver precedes write"))
        assert bundle(client, attachment, attachment_id="att-wrong").status_code == 422
        assert bundle(client, attachment, attachment_id="att-exact",
                      headers={**HEADERS, "X-LegalPDF-Workspace-Id": "another"}).status_code == 422
        # This release exposes source review only for the owned manual-upload flow.
        response = client.post(PREFIX + "/prepare", headers=HEADERS,
            json={"form_values": form(c, attachment, gmail_batch_context={"attachment_id": "att-exact"})})
        assert response.json()["diagnostics"] == {"error": "source_review_manual_upload_required"}


@pytest.mark.parametrize("kind", ["hardlink", "symlink"])
def test_owned_source_redirections_are_rejected_before_parser_or_bundle_write(tmp_path, monkeypatch, kind):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        source = upload(client)
        redirected = source.with_name("redirected.pdf")
        try:
            if kind == "hardlink":
                os.link(source, redirected)
            else:
                redirected.symlink_to(source)
        except OSError:
            pytest.skip("This test account cannot create the requested temporary link")
        monkeypatch.setattr(review_api, "build_translation_config", lambda **_: pytest.fail("No parser before direct source"))
        monkeypatch.setattr(browser, "write_browser_pdf_bundle", lambda **_: pytest.fail("No bundle write through link"))
        response = client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": form(c, redirected)})
        assert response.json()["diagnostics"] == {"error": "source_review_source_unavailable"}
        assert bundle(client, redirected).status_code == 422
    assert not c.local_calls and not c.clients


def test_raw_output_reparse_ancestor_fails_before_parser_probe_or_acquisition(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        source = upload(client)
        original_lstat = Path.lstat
        def reparse(path, *args, **kwargs):
            info = original_lstat(path, *args, **kwargs)
            if path == c.output:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
            return info
        # Deterministic Windows reparse evidence does not require administrator
        # privilege to create a junction on the validation machine.
        monkeypatch.setattr(Path, "lstat", reparse)
        monkeypatch.setattr(review_api, "build_translation_config", lambda **_: pytest.fail("No parser/probe through output reparse"))
        response = client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": form(c, source)})
        assert response.json()["diagnostics"] == {"error": "source_review_output_unavailable"}
    assert not (c.output / ".write_test.tmp").exists() and not c.local_calls and not c.clients


def test_existing_output_probe_object_is_preserved_before_normal_parser(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    existing = c.output / ".write_test.tmp"
    existing.write_bytes(b"Fictional existing user object")
    with TestClient(c.app) as client:
        source = upload(client)
        monkeypatch.setattr(review_api, "build_translation_config", lambda **_: pytest.fail("No parser overwrite"))
        response = client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": form(c, source)})
        assert response.json()["diagnostics"] == {"error": "source_review_output_probe_conflict"}
    assert existing.read_bytes() == b"Fictional existing user object" and not c.local_calls


def test_review_actions_are_typed_explicit_owned_and_generation_checked(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        draft = prepare(client, c, upload(client))
        route = f"{PREFIX}/{draft['review_id']}"
        foreign = {**HEADERS, "X-LegalPDF-Workspace-Id": "another"}
        for url in (route, route + "/pages/1/image"):
            denied = client.get(url, headers=foreign)
            assert denied.status_code == 422 and denied.json()["normalized_payload"] == {}
        decision = json.loads(json.dumps(asdict(explicit_decision(draft["pages"][0]))))
        bad_decisions = []
        for change in ({"full_page_review_completed": 1}, {"reviewer_kind": "ai_test_review"},
                       {"boundary_decision": "guessed"}):
            bad_decisions.append({**decision, **change})
        invalid_box = deepcopy(decision)
        invalid_box["actions"][0]["region_px"] = [0, 0, 201, 300]
        bad_decisions.append(invalid_box)
        for value in bad_decisions:
            response = client.post(route + "/pages/1", headers=HEADERS,
                json={"expected_generation": draft["generation"], "decision": value})
            assert response.status_code == 422 and response.json()["normalized_payload"] == {}
        response = client.post(route + "/pages/1", headers=HEADERS,
            json={"expected_generation": True, "decision": decision})
        assert response.json()["diagnostics"] == {"error": "source_review_invalid_integer"}
        for accepted in (False, 1, "true"):
            response = client.post(route + "/submit", headers=HEADERS,
                json={"expected_generation": draft["generation"], "reviewer": "Operator", "accept_source": accepted})
            assert response.json()["diagnostics"] == {"error": "source_review_explicit_acceptance_required"}
        # Explicit acceptance still cannot skip page review.
        response = client.post(route + "/submit", headers=HEADERS,
            json={"expected_generation": draft["generation"], "reviewer": "Operator", "accept_source": True})
        assert response.status_code == 422
        current = view(client.post(route + "/pages/1", headers=HEADERS,
            json={"expected_generation": draft["generation"], "decision": decision}))
        assert current["generation"] > draft["generation"]
        stale = client.post(route + "/pages/1", headers=HEADERS,
            json={"expected_generation": draft["generation"], "decision": decision})
        assert stale.status_code == 422
        foreign_save = client.post(route + "/pages/1", headers=foreign,
            json={"expected_generation": current["generation"], "decision": decision})
        assert foreign_save.status_code == 422
    assert not c.clients and not c.sdk_calls and not c.queued


def test_tamper_after_queue_fails_before_lazy_client_and_preserves_error_privacy(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        source = upload(client)
        draft = prepare(client, c, source)
        revision = save_and_submit(client, draft)
        response = client.post(f"{PREFIX}/{draft['review_id']}/translate", headers=HEADERS,
            json={"revision_id": revision["revision_id"], "operation_nonce": "a" * 32})
        job_id = response.json()["normalized_payload"]["job"]["job_id"]
        source.write_bytes(b"Fictional private source changed")
        c.queued.pop(0)()
        failed = c.jobs.get_job(job_id)
        assert failed["status"] == "failed"
        assert failed["diagnostics"]["error"] == "ordinary_source_review_job_failed"
        assert "Fictional" not in json.dumps(failed["diagnostics"]) and str(tmp_path) not in json.dumps(failed["diagnostics"])
    assert not c.clients and not c.sdk_calls


@pytest.mark.parametrize("saved,notice", [
    ({"ocr_mode": "off"}, "source_review_ocr_disabled"),
    ({"ocr_engine": "api"}, "source_review_local_baseline_unavailable"),
    ({"keep_intermediates": False}, "source_review_retained_evidence_required"),
])
def test_saved_policies_decline_without_overrides_or_paid_fallback(tmp_path, monkeypatch, saved, notice):
    c = api_case(tmp_path, monkeypatch, saved=saved)
    before = c.settings.read_bytes()
    with TestClient(c.app) as client:
        result = prepare(client, c, upload(client))
    assert result == {"status": "declined", "notice_codes": [notice]}
    assert not c.local_calls and not c.clients and not c.sdk_calls and c.settings.read_bytes() == before


@pytest.mark.parametrize("saved,corrected,notice", [
    ({"ocr_mode": "off"}, {"ocr_mode": "auto"}, "source_review_ocr_disabled"),
    ({"ocr_engine": "api"}, {"ocr_engine": "local_then_api"}, "source_review_local_baseline_unavailable"),
    ({"keep_intermediates": False}, {"keep_intermediates": True}, "source_review_retained_evidence_required"),
])
def test_pristine_policy_decline_allows_explicit_saved_correction_for_same_upload(
        tmp_path, monkeypatch, saved, corrected, notice):
    c = api_case(tmp_path, monkeypatch, saved=saved)
    routes = c.app.state.source_review_routes
    original = c.settings.read_bytes()
    with TestClient(c.app) as client:
        source = upload(client)
        result = prepare(client, c, source)
        assert result == {"status": "declined", "notice_codes": [notice]}
        assert not routes._run_owners and c.settings.read_bytes() == original
        assert not c.local_calls and not c.clients and not c.sdk_calls
        config = build_translation_config(form_values=form(c, source), settings_path=c.settings)
        run = build_run_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir
        assert [p.name for p in run.iterdir()] == [".run_workspace.lock"]

        # The operator explicitly changes the saved policy. Preparing again is
        # a separate request; the decline performs no retry or setting write.
        settings = json.loads(original)
        settings.update(corrected)
        c.settings.write_text(json.dumps(settings), encoding="utf-8")
        changed = c.settings.read_bytes()
        draft = prepare(client, c, source)
        assert draft["status"] == "draft" and draft["pages"][0]["decision"] is None
        assert len(routes._run_owners) == 1 and c.settings.read_bytes() == changed
    assert len(c.local_calls) == 1 and not c.clients and not c.sdk_calls and not c.queued


@pytest.mark.parametrize("outcome", [
    "artifact_file", "artifact_directory", "generic_exception", "bridge_exception",
    "empty_notices", "extra_handle", "invalid_notice", "replaced_claim",
])
def test_uncertain_or_acquired_decline_keeps_claim_and_blocks_changed_config(tmp_path, monkeypatch, outcome):
    c = api_case(tmp_path, monkeypatch)
    routes = c.app.state.source_review_routes
    calls = []
    marker = None

    def prepare_boundary(**kwargs):
        nonlocal marker
        calls.append(kwargs)
        config = kwargs["config"]
        run = build_run_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir
        key = os.path.normcase(str(run.resolve()))
        if outcome == "artifact_file":
            marker = run / "acquired-evidence.txt"
            marker.write_bytes(b"Fictional retained acquisition evidence")
        elif outcome == "artifact_directory":
            marker = run / "acquired-evidence"
            marker.mkdir()
        elif outcome == "generic_exception":
            raise RuntimeError("Fictional private acquisition outcome")
        elif outcome == "bridge_exception":
            raise BrowserSourceReviewError("browser_source_review_prepare_failed")
        elif outcome == "empty_notices":
            return {"status": "declined", "notice_codes": []}
        elif outcome == "extra_handle":
            return {"status": "declined", "notice_codes": ["source_review_ocr_disabled"], "review_id": "a" * 32}
        elif outcome == "invalid_notice":
            return {"status": "declined", "notice_codes": ["not a source review notice"]}
        elif outcome == "replaced_claim":
            with routes._guard:
                retained = routes._run_owners[key]
                replacement = tuple(list(retained))
                assert replacement == retained and replacement is not retained
                routes._run_owners[key] = replacement
        return {"status": "declined", "notice_codes": ["source_review_ocr_disabled"]}

    # Only this uncertainty/ownership test substitutes the acquisition boundary;
    # no accepted source, review decision or completed job is fabricated.
    monkeypatch.setattr(c.context.source_reviews, "prepare", prepare_boundary)
    with TestClient(c.app) as client:
        source = upload(client)
        first = client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": form(c, source)})
        assert first.status_code == (422 if "exception" in outcome else 200)
        assert len(routes._run_owners) == len(calls) == 1
        retained = next(iter(routes._run_owners.values()))
        response = client.post(PREFIX + "/prepare", headers=HEADERS,
                               json={"form_values": form(c, source, workers=2)})
        assert response.status_code == 422
        assert response.json()["diagnostics"] == {"error": "source_review_run_owner_conflict"}
        assert len(calls) == 1 and next(iter(routes._run_owners.values())) is retained
        if "exception" in outcome:
            assert "Fictional" not in first.text and first.json()["normalized_payload"] == {}
        if marker is not None:
            assert marker.exists()
            if marker.is_file():
                assert marker.read_bytes() == b"Fictional retained acquisition evidence"
    assert not c.local_calls and not c.clients and not c.sdk_calls and not c.queued


def test_later_explicit_decline_cannot_release_an_existing_pristine_claim(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    routes = c.app.state.source_review_routes
    responses = iter(({"status": "declined", "notice_codes": []},
        {"status": "declined", "notice_codes": ["source_review_ocr_disabled"]}))
    monkeypatch.setattr(c.context.source_reviews, "prepare", lambda **_: next(responses))
    with TestClient(c.app) as client:
        source = upload(client)
        prepare(client, c, source)
        retained = next(iter(routes._run_owners.values()))
        assert prepare(client, c, source)["notice_codes"] == ["source_review_ocr_disabled"]
        assert next(iter(routes._run_owners.values())) is retained
        response = client.post(PREFIX + "/prepare", headers=HEADERS,
                               json={"form_values": form(c, source, workers=2)})
        assert response.json()["diagnostics"] == {"error": "source_review_run_owner_conflict"}
    assert not c.local_calls and not c.clients and not c.sdk_calls


def test_pristine_release_requires_available_actual_run_lock(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    routes = c.app.state.source_review_routes
    run = c.output / "owned-run"
    key = os.path.normcase(str(run.resolve()))
    claim = object()  # Isolated registry identity; not a source or acceptance fixture.
    routes._run_owners[key] = claim
    with run_workspace_slot(run, create=True):
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(routes._release_pristine_claim, run, key, claim).result(timeout=5) is False
        assert routes._run_owners[key] is claim
        assert [p.name for p in run.iterdir()] == [".run_workspace.lock"]
    assert routes._run_owners[key] is claim
    assert not c.local_calls and not c.clients and not c.sdk_calls


def test_unclaimed_saved_run_has_no_browser_restore_path(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        source = upload(client)
        config = build_translation_config(form_values=form(c, source), settings_path=c.settings)
        run = build_run_paths(config.output_dir, config.pdf_path, config.target_lang).run_dir
        run.mkdir(parents=True)
        marker = run / "existing-owner-evidence.txt"
        marker.write_bytes(b"Fictional existing run; browser owner not retained")
        response = client.post(PREFIX + "/prepare", headers=HEADERS, json={"form_values": form(c, source)})
        assert response.json()["diagnostics"] == {"error": "source_review_saved_run_owner_unavailable"}
        assert marker.read_bytes() == b"Fictional existing run; browser owner not retained"
        assert client.post(PREFIX + "/restore", headers=HEADERS, json={}).status_code in {404, 405}
    assert not c.local_calls and not c.clients


def test_prepare_claim_cannot_change_config_or_disclose_private_service_failure(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        source = upload(client)
        draft = prepare(client, c, source)
        response = client.post(PREFIX + "/prepare", headers=HEADERS,
            json={"form_values": form(c, source, workers=2)})
        assert response.json()["diagnostics"] == {"error": "source_review_run_owner_conflict"}
        def private_failure(**_kwargs):
            raise RuntimeError("Fictional private source / local evidence path")
        monkeypatch.setattr(c.context.source_reviews, "read", private_failure)
        response = client.get(f"{PREFIX}/{draft['review_id']}", headers=HEADERS)
        assert response.json()["diagnostics"] == {"error": "source_review_operation_failed"}
        assert response.json()["normalized_payload"] == {}
    assert len(c.local_calls) == 1 and not c.clients


def test_translate_requires_exact_owned_revision_and_operation_nonce(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        draft = prepare(client, c, upload(client))
        revision = save_and_submit(client, draft)
        route = f"{PREFIX}/{draft['review_id']}/translate"
        for payload in ({"revision_id": revision["revision_id"]},
                        {"revision_id": revision["revision_id"], "operation_nonce": "not-an-operation-id"},
                        {"revision_id": "0" * 32, "operation_nonce": "a" * 32}):
            assert client.post(route, headers=HEADERS, json=payload).status_code == 422
        response = client.post(route, headers={**HEADERS, "X-LegalPDF-Workspace-Id": "another"},
            json={"revision_id": revision["revision_id"], "operation_nonce": "a" * 32})
        assert response.status_code == 422 and response.json()["normalized_payload"] == {}
    assert not c.queued and not c.clients and not c.sdk_calls


@pytest.mark.parametrize("owner", [{"runtime_mode": "shadow", "workspace_id": "another"},
                                  {"runtime_mode": "live", "workspace_id": "workspace-1"}, {}])
def test_existing_job_actions_deny_foreign_or_missing_owner_before_side_effects(tmp_path, monkeypatch, owner):
    c = api_case(tmp_path, monkeypatch)
    monkeypatch.setattr(c.jobs, "get_job", lambda _: {"job_id": "tx-foreign", **owner})
    def forbidden(*_args, **_kwargs):
        pytest.fail("Foreign job must fail before action, artifact, save-row or Gmail call")
    for name in ("cancel_job", "resume_job", "rebuild_job", "generate_run_report", "job_artifact_path"):
        monkeypatch.setattr(c.jobs, name, forbidden)
    monkeypatch.setattr(browser, "export_translation_review_queue_for_job", forbidden)
    monkeypatch.setattr(browser, "save_translation_row", forbidden)
    with TestClient(c.app) as client:
        assert client.get("/api/translation/jobs/tx-foreign", headers=HEADERS).status_code == 404
        for action in ("cancel", "resume", "rebuild", "review-export", "run-report"):
            assert client.post(f"/api/translation/jobs/tx-foreign/{action}", headers=HEADERS, json={}).status_code == 404
        assert client.get("/api/translation/jobs/tx-foreign/artifact/output_docx", headers=HEADERS).status_code == 404
        for row_id in (None, 7):
            assert client.post("/api/translation/save-row", headers=HEADERS,
                json={"job_id": "tx-foreign", "row_id": row_id, "form_values": {}}).status_code == 404
        assert client.post("/api/gmail/batch/confirm-current", headers=HEADERS,
                           json={"job_id": "tx-foreign"}).status_code == 404
        assert client.get("/api/translation/arabic-review/state?job_id=tx-foreign", headers=HEADERS).status_code == 404


def test_job_workspace_filter_is_applied_before_limit_and_all_lists_pass_scope(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    # This isolated list test supplies only immutable owner/order records. It does
    # not represent a translated job, accepted source or structured commit.
    c.jobs._jobs = {str(n): SimpleNamespace(runtime_mode="shadow", workspace_id="another", updated_at=str(n + 10))
                    for n in range(20)}
    owned = SimpleNamespace(runtime_mode="shadow", workspace_id="workspace-1", updated_at="00")
    c.jobs._jobs["owned"] = owned
    monkeypatch.setattr(c.jobs, "_snapshot", lambda job: {"workspace_id": job.workspace_id})
    assert c.jobs.list_jobs(runtime_mode="shadow", workspace_id="workspace-1", limit=1) == [{"workspace_id": "workspace-1"}]
    assert c.jobs.list_jobs(runtime_mode="shadow", limit=1) == [{"workspace_id": "another"}]
    seen = []
    monkeypatch.setattr(c.jobs, "list_jobs", lambda **kw: seen.append(kw) or [])
    monkeypatch.setattr(browser, "list_translation_history", lambda **_: [])
    with TestClient(c.app) as client:
        for route in ("/api/bootstrap", "/api/translation/bootstrap", "/api/translation/history"):
            assert client.get(route, headers=HEADERS).status_code == 200
    assert len(seen) == 3
    assert all(item["runtime_mode"] == "shadow" and item["workspace_id"] == "workspace-1" for item in seen)
