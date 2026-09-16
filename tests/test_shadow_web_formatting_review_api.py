"""Standard synthetic ASGI tests for the job-owned formatting API.

TestClient's own Windows socketpair is not an isolated-runner network exemption.
The positive flow uses actual source routes, queued Workflow and typed formatting
decisions. No committed page or acceptance evidence is injected.
"""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import translation_service as jobs_module
from legalpdf_translate.browser_formatting_review import BrowserFormattingReviewManager
from legalpdf_translate.shadow_web import formatting_review_api as api
from tests.test_shadow_web_source_review_api import (
    api_case, upload, prepare as source_prepare, save_and_submit, PREFIX as SOURCE_PREFIX, HEADERS,
)
from tests.test_browser_formatting_review import layout_decision, document_decision
from tests.test_ordinary_source_review_service import local_only


def formatting_api_case(tmp_path, monkeypatch):
    """Inject only the new browser service into the existing owned source fixture."""
    c = api_case(tmp_path, monkeypatch)
    manager = BrowserFormattingReviewManager(c.jobs)
    c.context = replace(c.context, formatting_reviews=manager,
        services=replace(c.context.services, formatting_reviews_factory=BrowserFormattingReviewManager))
    c.app.state.shadow_context = c.context
    monkeypatch.setattr(jobs_module, "_translation_result_payload", lambda **kw: {"artifacts": {
        "run_dir": str(kw["summary"].run_dir), "output_docx": str(kw["summary"].output_docx)}})
    return c


def completed_reviewed_job(client, c):
    source = upload(client)
    draft = source_prepare(client, c, source)
    accepted = save_and_submit(client, draft)
    response = client.post(f"{SOURCE_PREFIX}/{draft['review_id']}/translate", headers=HEADERS,
        json={"revision_id": accepted["revision_id"], "operation_nonce": "a" * 32})
    assert response.status_code == 200, response.text
    job = response.json()["normalized_payload"]["job"]
    c.queued.pop(0)()
    response = client.get(f"/api/translation/jobs/{job['job_id']}", headers=HEADERS)
    assert response.status_code == 200, response.text
    job = response.json()["normalized_payload"]["job"]
    assert job["status"] == "completed", job["diagnostics"]
    c.job = job
    c.run_dir = Path(job["artifacts"]["run_dir"])
    return job


def prefix(job):
    return f"/api/translation/jobs/{job['job_id']}/formatting-reviews"


def view(response):
    assert response.status_code == 200, response.text
    payload = response.json()
    assert set(payload) == {"status", "normalized_payload", "diagnostics", "capability_flags"}
    assert payload["diagnostics"] == {} and response.headers["cache-control"] == "no-store"
    return payload["normalized_payload"]["formatting_review"]


def complete_formatting(client, c, job, *, table=False, gap=None):
    base = prefix(job)
    draft = view(client.post(base + "/prepare", headers=HEADERS, json={"page_matched_derivative": True}))
    for page in draft["pages"]:
        draft = view(client.post(base + f"/{draft['review_id']}/pages/{page['page_number']}", headers=HEADERS,
            json={"expected_generation": draft["generation"], "decision": asdict(layout_decision(page, table=table, gap=gap))}))
    draft = view(client.post(base + f"/{draft['review_id']}/document", headers=HEADERS,
        json={"expected_generation": draft["generation"], "decision": asdict(document_decision(len(draft["pages"])))}))
    return view(client.post(base + f"/{draft['review_id']}/submit", headers=HEADERS,
        json={"expected_generation": draft["generation"], "reviewer": "Fictional final operator", "accept_formatting": True}))


def test_public_job_route_build_download_and_exact_nonce_recovery(tmp_path, monkeypatch):
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        job = completed_reviewed_job(client, c)
        before = {p: p.read_bytes() for p in c.run_dir.rglob("*") if p.is_file()}
        before[c.settings] = c.settings.read_bytes()
        original = Path(job["artifacts"]["output_docx"]); before[original] = original.read_bytes()
        base = prefix(job)
        declined = view(client.post(base + "/prepare", headers=HEADERS, json={"page_matched_derivative": False}))
        assert declined["status"] == "declined" and declined["page_matched_derivative"] is False
        accepted = complete_formatting(client, c, job, table=True, gap=(12,))
        rid, revision = accepted["review_id"], accepted["revision_id"]
        current = view(client.get(base + f"/{rid}", headers=HEADERS))
        assert current["offset_unit"] == "unicode_codepoint" and current["revision_id"] == revision
        assert current["pages"][0]["image_available"] is True
        assert current["page_matched_derivative"] is True
        assert current["formatting_derivative"]["original_page_breaks"] is False
        assert str(tmp_path) not in json.dumps(current) and "draft_id" not in current
        image = client.get(base + f"/{rid}/pages/1/image", headers=HEADERS)
        assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
        assert image.headers["x-content-type-options"] == "nosniff"
        inspected = view(client.get(base + f"/{rid}/revisions/{revision}", headers=HEADERS))
        assert inspected["status"] == "ready" and inspected["rendered_layout_acceptance"] == "not_evaluated"
        body = {"revision_id": revision, "operation_nonce": "b" * 32}
        built = view(client.post(base + f"/{rid}/rebuild", headers=HEADERS, json=body))
        replay = view(client.post(base + f"/{rid}/rebuild", headers=HEADERS, json=body))
        assert built == replay and built["status"] == "built"
        artifact = built["artifacts"][0]
        assert built["rebuild_operations"][0]["artifact_id"] == artifact["artifact_id"]
        for kind in artifact["kinds"]:
            response = client.get(base + f"/{rid}/artifacts/{artifact['artifact_id']}/{kind}", headers=HEADERS)
            assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
            assert response.headers["content-disposition"].startswith("attachment;")
            if kind == "source_map":
                assert response.json()["pages"][0]["tables"][0]["column_gaps_px"] == [12]
            if kind == "output_docx": assert response.content.startswith(b"PK")
        final_job = client.get(f"/api/translation/jobs/{job['job_id']}", headers=HEADERS).json()["normalized_payload"]["job"]
        assert final_job["artifacts"]["output_docx"] == str(original)
        assert final_job["artifacts"]["reviewed_formatting"] == [artifact]
        assert {p: p.read_bytes() for p in before} == before
    assert len(c.clients) == len(c.sdk_calls) == 1


@pytest.mark.parametrize("scope", ["missing", "conflicting", "other_workspace", "other_mode", "other_job"])
def test_routes_require_exact_job_and_explicit_scope(tmp_path, monkeypatch, scope):
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        job = completed_reviewed_job(client, c)
        headers, base, payload = dict(HEADERS), prefix(job), {"page_matched_derivative": True}
        if scope == "missing": headers = {}
        if scope == "conflicting": payload["workspace_id"] = "workspace-2"
        if scope == "other_workspace": headers["X-LegalPDF-Workspace-Id"] = "workspace-2"
        if scope == "other_mode": headers["X-LegalPDF-Runtime-Mode"] = "live"
        if scope == "other_job": base = base.replace(job["job_id"], "tx-" + "0" * 12)
        response = client.post(base + "/prepare", headers=headers, json=payload)
        assert response.status_code == 422 and response.json()["normalized_payload"] == {}
        assert str(tmp_path) not in response.text
        assert not (c.run_dir / "browser_formatting_reviews").exists()


@pytest.mark.parametrize("payload", [{"page_matched_derivative": 1}, {"page_matched_derivative": "true"},
    {"page_matched_derivative": True, "output_path": "private-value"}, {"config": {}}, {}],
    ids=["integer", "string", "path", "config", "missing"])
def test_prepare_cannot_accept_paths_config_or_inferred_boolean(tmp_path, monkeypatch, payload):
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        job = completed_reviewed_job(client, c)
        response = client.post(prefix(job) + "/prepare", headers=HEADERS, json=payload)
        assert response.status_code == 422 and "private-value" not in response.text
        assert not (c.run_dir / "browser_formatting_reviews").exists()


@pytest.mark.parametrize("mutation", ["target_edit", "float_offset", "bool_generation", "oversized_box", "unsupported_gap", "null_gap"])
def test_decisions_reject_unknown_text_edits_and_invalid_geometry(tmp_path, monkeypatch, mutation):
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        job = completed_reviewed_job(client, c); base = prefix(job)
        draft = view(client.post(base + "/prepare", headers=HEADERS, json={"page_matched_derivative": True}))
        decision = json.loads(json.dumps(asdict(layout_decision(draft["pages"][0], table=True, gap=(12,)))))
        payload = {"expected_generation": draft["generation"], "decision": decision}
        if mutation == "target_edit": decision["fragments"][0]["target_text"] = "private-invention"
        if mutation == "float_offset": decision["fragments"][0]["target_range"][0] = 0.0
        if mutation == "bool_generation": payload["expected_generation"] = True
        if mutation == "oversized_box": decision["fragments"][0]["bbox_px"][2] = 201
        if mutation == "unsupported_gap": decision["body"][0]["column_gaps_px"] = [21]
        if mutation == "null_gap": decision["body"][0]["column_gaps_px"] = None
        response = client.post(base + f"/{draft['review_id']}/pages/1", headers=HEADERS, json=payload)
        assert response.status_code == 422 and "private-invention" not in response.text
        unchanged = view(client.get(base + f"/{draft['review_id']}", headers=HEADERS))
        assert unchanged["generation"] == draft["generation"] and unchanged["pages"][0]["decision"] is None


@pytest.mark.parametrize("raw", ['{"page_matched_derivative":true,"page_matched_derivative":false}',
    '{"page_matched_derivative":NaN}', "x" * (2 * 1024 * 1024 + 1)], ids=["duplicate", "nonfinite", "oversized"])
def test_bounded_json_parser_before_any_owned_write(tmp_path, monkeypatch, raw):
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        response = client.post("/api/translation/jobs/tx-000000000000/formatting-reviews/prepare",
            headers=HEADERS, content=raw)
        assert response.status_code == (413 if len(raw) > 2 * 1024 * 1024 else 422)
        assert str(tmp_path) not in response.text


def test_download_owner_and_allowlisted_kind_do_not_disclose_paths(tmp_path, monkeypatch):
    c = formatting_api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        job = completed_reviewed_job(client, c); accepted = complete_formatting(client, c, job)
        base = prefix(job) + f"/{accepted['review_id']}"
        built = view(client.post(base + "/rebuild", headers=HEADERS,
            json={"revision_id": accepted["revision_id"], "operation_nonce": "b" * 32}))
        artifact = built["artifact"]["artifact_id"]
        for headers, kind in (({**HEADERS, "X-LegalPDF-Workspace-Id": "workspace-2"}, "output_docx"),
                              (HEADERS, "run_state"), (HEADERS, "output_path")):
            response = client.get(base + f"/artifacts/{artifact}/{kind}", headers=headers)
            assert response.status_code == 422 and str(tmp_path) not in response.text


def test_default_offline_bundle_leaves_formatting_disabled(tmp_path, monkeypatch):
    c = api_case(tmp_path, monkeypatch)
    with TestClient(c.app) as client:
        response = client.post("/api/translation/jobs/tx-000000000000/formatting-reviews/prepare",
            headers=HEADERS, json={"page_matched_derivative": True})
        assert response.status_code == 409
        assert response.json()["diagnostics"] == {"error": "formatting_review_disabled"}
    assert not c.clients and not c.sdk_calls


@pytest.mark.parametrize("field", ["all_pages_reviewed", "allow_pipe_cell_boundaries", "preserve_source_gaps"])
def test_document_flags_require_actual_booleans(field):
    decision = json.loads(json.dumps(asdict(document_decision())))
    decision[field] = int(decision[field])
    with pytest.raises(api.FormattingReviewAPIError, match="invalid_decision"):
        api.formatting_document_decision(decision)
