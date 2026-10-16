"""All-settled institutional-footer recovery never repurchases saved pages."""
from decimal import Decimal
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_auto_layout as automatic
from legalpdf_translate import ordinary_layout_manager as manager_module
from legalpdf_translate.ordinary_layout_contracts import (
    PROPOSAL_VERSION_V3, OPTIONAL_HINT_NORMALIZATION_V2, OPTIONAL_HINT_NORMALIZATION_V3, OrdinaryLayoutError)
from legalpdf_translate.ordinary_layout_service import _read
from tests.test_ordinary_auto_layout_recovery import offline
from tests import test_ordinary_auto_layout_workflow as flow


@pytest.mark.parametrize("restart", [False, True], ids=["same_process", "capsule_restart_intent_only"])
def test_real_recover_route_revalidates_all_three_paid_responses_without_dispatch(tmp_path, monkeypatch, restart):
    source, output = tmp_path / "fictional.pdf", tmp_path / "outputs"
    output.mkdir()
    flow._source(source, ("digital",) * 3)
    original_proposal = flow._proposal
    def proposal(view, page, columns=0):
        result = original_proposal(view, page, columns)
        for row in result["paragraphs"]:
            row.update(role="body", heading_level=0, heading_size_pt=None, bold=False)
        ids = [row["paragraph_id"] for row in result["paragraphs"]]
        result.update(version=PROPOSAL_VERSION_V3, paragraph_partitions=[],
            source_coverage_findings=[], source_layout_evidence=[{
                "kind": "source_footer", "paragraph_ids": ids[-3:], "bbox": [.06, .952, .94, .998]}])
        result["bands"] = [{"kind": "flow", "groups": [{"paragraph_ids": ids, "panel": False}]}]
        for row, role in zip(result["paragraphs"][-3:],
                ["institution", "source_folio", "institution"] if page == 3 else ["body", "source_folio", "body"]):
            row["role"] = role
        return result
    monkeypatch.setattr(flow, "_proposal", proposal)
    outputs = tuple(f"Fictional body {page}.\nFictional address.\nPage {page} of 3\nFictional contact." for page in (1, 2, 3))
    app, jobs, translation_sdk, layout_requests = flow._app(tmp_path, monkeypatch, outputs, (1, 2, 3))
    from tests.test_terminal_accounting_restore import gmail_fixture, restart_into_app
    loaded, session, gmail_context = gmail_fixture(source, output)
    scope = "?mode=shadow&workspace=fictional"
    normalize = manager_module.normalize_proposals
    old_policy = automatic._optional_hint_policy(OPTIONAL_HINT_NORMALIZATION_V2,
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_labeled_folio_v2")
    with TestClient(app) as client:
        with monkeypatch.context() as historical:
            historical.setattr(automatic, "frozen_automatic_layout_policy", lambda: old_policy)
            historical.setattr(manager_module, "normalize_proposals", lambda *a, **kw:
                normalize(*a, **{**kw, "normalization_version": OPTIONAL_HINT_NORMALIZATION_V2}))
            response = client.post("/api/translation/jobs/translate", json={"mode": "shadow",
                "workspace_id": "fictional", "form_values": {"source_path": str(source),
                "output_dir": str(output), "target_lang": "EN", "start_page": 1, "end_page": 3,
                "image_mode": "off", "ocr_mode": "off", "workers": 1,
                "gmail_batch_context": gmail_context}})
            assert response.status_code == 200, response.text
            job_id = response.json()["normalized_payload"]["job"]["job_id"]
            first = flow._wait(jobs, job_id)
        assert first["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(layout_requests) == len(translation_sdk.requests) == 3
        manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, "shadow", "fictional")
        run = Path(first["result"]["run_dir"])
        root = run / "ordinary_auto_layout"
        pointer = json.loads((root / "operation.json").read_bytes())
        operation = manager.service.root / job_id / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
        failed = _read(operation / "result.json")
        assert failed["error_code"] == "ordinary_layout_invalid_source_footer_evidence"
        assert failed["completed_pages"] == [1, 2]
        cost = Decimal(str(_read(operation / "accounting_summary.json")["cost_usd"]))
        protected = {p: p.read_bytes() for p in operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
        protected.update({p: p.read_bytes() for p in (root / "intent.json", root / "operation.json")})
        journal = jobs._jobs[job_id]._completed_accountant.journal_path
        protected[journal] = journal.read_bytes()
        original_summary = jobs._jobs[job_id]._completed_accountant.summary()
        if restart:
            # Reproduce the already-written direct intent from the failed
            # post-restart Recover, with no operation or new authorization.
            jobs._jobs[job_id]._completed_accountant = None
            assert client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope).status_code == 200
            held = flow._wait(jobs, job_id)
            assert held["result"]["automatic_layout"]["reason"] == "ordinary_layout_accounting_unavailable"
            direct = root / "recoveries" / "layout_direct_revalidation_v1"
            interrupted_intent = (direct / "intent.json").read_bytes()
            assert not (direct / "operation.json").exists()
            app, jobs = restart_into_app(tmp_path, app, jobs, job_id, loaded, session)
            assert jobs._jobs[job_id]._completed_accountant.summary() == original_summary
            client = TestClient(app)
            manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, "shadow", "fictional")
            protected[direct / "intent.json"] = interrupted_intent
        # A retained response or unsettled accounting cannot authorize assembly,
        # budget mutation or even a single extra provider dispatch.
        for path in (operation / "page-0003.response.json", operation / "accounting_summary.json"):
            original = path.read_bytes()
            path.write_bytes(b"{}")
            assert client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope).status_code == 200
            held = flow._wait(jobs, job_id)
            assert held["result"]["automatic_layout"]["status"] == "raw_fallback"
            assert len(layout_requests) == len(translation_sdk.requests) == 3
            path.write_bytes(original)
        provider = manager.provider_factory
        def no_dispatch(*args):
            client = provider(*args)
            client._client.responses.create = lambda **kwargs: pytest.fail("All retained pages must use zero provider calls")
            return client
        manager.provider_factory = no_dispatch
        assert client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope).status_code == 200
        final = flow._wait(jobs, job_id)
        result = final["result"]["automatic_layout"]
        assert result["status"] == "automatic_unreviewed", result
        assert result["source_layout_review_required"] is True
        assert result["source_layout_rejected_hints"][0]["reason"] == "source_footer_institution_kept_in_flow"
        assert len(layout_requests) == len(translation_sdk.requests) == 3
        direct = root / "recoveries" / "layout_direct_revalidation_v1"
        identity = json.loads((direct / "intent.json").read_bytes())
        assert set(identity["retained_pages"]) == {"1", "2", "3"}
        new_pointer = json.loads((direct / "operation.json").read_bytes())
        current = manager.service.root / job_id / "baselines" / new_pointer["baseline_id"] / "suggestions" / new_pointer["operation_nonce"]
        summary = _read(current / "accounting_summary.json")
        assert summary["provider_dispatch_count"] == summary["attempt_count"] == 0
        assert summary["unknown_cost_count"] == summary["in_flight_count"] == 0
        assert Decimal(str(summary["cost_usd"])) == 0
        assert Decimal(result["layout_costs"]["known_cost_usd"]) == cost
        assert result["layout_costs"]["operations"] == 2
        evidence = _read(current / "source_evidence.json")
        assert evidence["pages"][-1]["normalization"]["version"] == OPTIONAL_HINT_NORMALIZATION_V3
        # A V3 sidecar must never be relabeled as historical V2 behavior.
        with pytest.raises(OrdinaryLayoutError, match="source_evidence_response_changed"):
            automatic._proposal_evidence(manager, job_id, new_pointer["baseline_id"],
                new_pointer["review_id"], new_pointer["operation_nonce"], (1, 2, 3), old_policy,
                retained_pages=new_pointer["retained_pages"])
        for page in (1, 2, 3):
            assert (current / f"page-{page:04d}.response.json").read_bytes() == protected[operation / f"page-{page:04d}.response.json"]
        downloaded = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
        assert downloaded.status_code == 200
        text = flow._docx_text(downloaded.content)
        assert text.count("Fictional address.") == text.count("Fictional contact.") == 3
        # The existing all-page footer proof keeps every footer in body flow.
        from io import BytesIO
        from zipfile import ZipFile
        with ZipFile(BytesIO(downloaded.content)) as package:
            for name in package.namelist():
                if name.startswith("word/footer") and name.endswith(".xml"):
                    assert b"Fictional address." not in package.read(name)
                    assert b"Fictional contact." not in package.read(name)
        assert all(path.read_bytes() == value for path, value in protected.items())
        before = downloaded.content
        assert client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope).status_code == 200
        repeated = flow._wait(jobs, job_id)
        assert repeated["result"]["automatic_layout"]["sha256"] == result["sha256"]
        assert client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope).content == before
        assert len(layout_requests) == len(translation_sdk.requests) == 3
