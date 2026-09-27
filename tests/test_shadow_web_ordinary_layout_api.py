import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from legalpdf_translate.shadow_web.ordinary_layout_routes import OrdinaryLayoutRoutes
from tests.test_ordinary_layout_service import make_case, nonce


def client_for(case):
    app = FastAPI()
    OrdinaryLayoutRoutes(app, manager_for=lambda request, mode, workspace: case.manager)
    return TestClient(app)


def url(case, suffix="/layout"):
    return f"/api/translation/jobs/{case.job.job_id}{suffix}?mode=shadow&workspace_id=fixture"


def test_state_and_explicit_original_selection_route(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    with client_for(case) as client:
        result = client.get(url(case))
        assert result.status_code == 200
        assert result.json()["capability_flags"] == {}
        assert result.headers["cache-control"] == "no-store"
        result = client.post(url(case, "/delivery"), json={"baseline_id": case.view["baseline_id"],
            "expected_delivery_generation": 0, "selection_nonce": nonce(), "kind": "original", "review_id": None,
            "artifact_id": None, "expected_review_generation": None, "keep_ordinary_confirmed": True})
        assert result.status_code == 200, result.text
        assert result.json()["normalized_payload"]["ordinary_layout"]["delivery"]["kind"] == "original"


@pytest.mark.parametrize("body", [b'{"prepare_nonce":"a","prepare_nonce":"b"}', b'{"prepare_nonce":NaN}',
    b'{"prepare_nonce":"a","path":"C:/private"}', b'{}'])
def test_duplicate_nonfinite_and_extra_fields_are_rejected(tmp_path, monkeypatch, body):
    case = make_case(tmp_path, monkeypatch)
    with client_for(case) as client:
        result = client.post(url(case, "/layout/prepare"), content=body, headers={"Content-Type": "application/json"})
        assert result.status_code == 422
        assert "C:/private" not in result.text and result.json()["capability_flags"] == {}


def test_actual_stream_limit_and_wrong_owner(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    with client_for(case) as client:
        result = client.post(url(case, "/layout/prepare"), content=b" " * (65536 + 1), headers={"Content-Type": "application/json"})
        assert result.status_code == 413
        result = client.get(url(case).replace("workspace_id=fixture", "workspace_id=other"))
        assert result.status_code == 409


def test_cancel_endpoint_is_owned_idempotent_and_never_dispatches(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); operation = nonce()
    case.manager.service.begin_suggestion(case.job.job_id, case.view["generation"], operation, [1], {},
        expected_baseline_id=case.view["baseline_id"])
    body = {"baseline_id": case.view["baseline_id"], "expected_generation": case.view["generation"]}
    with client_for(case) as client:
        first = client.post(url(case, f"/layout/suggestions/{operation}/cancel"), json=body)
        assert first.status_code == 200
        result = first.json()["normalized_payload"]["ordinary_layout"]
        assert result["status"] == "cancel_requested" and result["operation_nonce"] == operation
        assert client.post(url(case, f"/layout/suggestions/{operation}/cancel"), json=body).json() == first.json()
        assert client.post(url(case, f"/layout/suggestions/{operation}/cancel"),
            json={**body, "baseline_id": nonce()}).status_code == 409
