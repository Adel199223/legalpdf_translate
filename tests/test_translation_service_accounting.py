"""Real browser jobs and workflow accounting with only a synthetic SDK."""
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import socket
import time

import pytest

from legalpdf_translate import accounting_policy as policy_module
from legalpdf_translate import translation_service as service
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.accounting_policy import OrdinaryAccountingPolicy
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.usage_accounting import DispatchAccounting
from tests.test_new_run_preflight import config_for
from tests.test_workflow_dispatch_accounting import FakeSDK


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Manager accounting test attempted ambient credentials or network")

    class ReferenceDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 10)

    monkeypatch.setattr(policy_module, "date", ReferenceDate)
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "load_gui_settings", forbidden)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test", forbidden)
    monkeypatch.setattr(workflow_module, "resolve_openai_key_with_source", forbidden)
    monkeypatch.setattr(service, "resolve_openai_key_with_source", forbidden)


def synthetic_policy():
    return OrdinaryAccountingPolicy.from_mapping(pricing={
        "snapshot_id": "manager-offline-fixture", "verified_at": "2026-09-10",
        "source": "Synthetic test rates, not production pricing",
        "models": {"openai:gpt-5.2|default|fixture|USD": {
            "input_per_1m": 2, "cached_input_per_1m": 1, "output_per_1m": 8,
            "service_tier": "default", "billing_scope": "fixture", "currency": "USD",
        }},
    }, limits={"openai:*:gpt-5.2": {
        "requested_model": "gpt-5.2", "requested_service_tier": "default",
        "max_input_tokens": 50000, "max_output_tokens": 256,
        "billing_scope": "fixture", "currency": "USD",
        "allowed_base_urls": ["https://api.openai.com/v1"],
    }})


def install_sdk(monkeypatch, *, missing_usage=False):
    sdk = FakeSDK(missing_usage=missing_usage)
    monkeypatch.setattr(service, "OpenAIResponsesClient", lambda **kwargs:
        OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0, pre_call_jitter_seconds=0))
    return sdk


def start_and_wait(manager, directory):
    directory.mkdir()
    config = config_for(directory)
    settings = directory / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    job = manager.start_translate(runtime_mode="shadow", workspace_id=directory.name,
        settings_path=settings, form_values={
            "source_path": str(config.pdf_path), "output_dir": str(config.output_dir),
            "target_lang": "EN", "image_mode": "off", "ocr_mode": "off",
            "workers": 1, "resume": False, "page_breaks": False,
        })
    deadline = time.monotonic() + 20
    while job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.01)
        job = manager.get_job(job["job_id"])
    assert job["status"] in {"completed", "failed"}, job
    assert settings.read_text(encoding="utf-8") == "{}"
    return job


def accounting_summary(job):
    summary = Path(job["artifacts"]["run_summary_path"])
    return json.loads(summary.read_text(encoding="utf-8"))["dispatch_accounting"]


@pytest.mark.parametrize("missing_usage", [False, True])
def test_real_manager_jobs_share_cap_and_preserve_unknown_hold(tmp_path, monkeypatch, missing_usage):
    sdk = install_sdk(monkeypatch, missing_usage=missing_usage)
    # One .102048 ceiling fits; after the first .00066 charge a second does not.
    budget = ReservationBudget(tmp_path / "shared.json", cap_usd="0.1025",
        identity={"campaign": "synthetic-manager-test"})
    policy = synthetic_policy()
    factory_arguments = []

    def factory(**arguments):
        factory_arguments.append(arguments)
        return DispatchAccounting(**arguments, budget_context=budget, **policy.accounting_arguments())

    manager = service.TranslationJobManager(accounting_factory=factory, accounting_policy=policy)
    first = start_and_wait(manager, tmp_path / "first")
    assert first["status"] == "completed", first
    assert len(sdk.requests) == 1
    before = budget.path.read_bytes()
    second = start_and_wait(manager, tmp_path / "second")
    assert second["status"] == "failed", second
    assert len(sdk.requests) == 1  # Rejected before SDK dispatch, including retries.
    assert budget.path.read_bytes() == before
    assert len(factory_arguments) == 2
    assert factory_arguments[0]["run_dir"] != factory_arguments[1]["run_dir"]
    assert all(not args["historical_incomplete"] for args in factory_arguments)
    assert all((args["run_dir"] / "dispatch_accounting.json").is_file() for args in factory_arguments)
    status = budget.status()
    assert status["attempts"] == 1
    assert status["blocked"] is missing_usage
    assert Decimal(status["held_usd"]) == (Decimal("0.102048") if missing_usage else Decimal(0))
    assert Decimal(status["known_spend_usd"]) == (Decimal(0) if missing_usage else Decimal("0.00066"))
    assert accounting_summary(first)["cost_usd"] == (None if missing_usage else pytest.approx(.00066))


def test_manager_forwards_explicit_policy_to_real_workflow(tmp_path, monkeypatch):
    sdk = install_sdk(monkeypatch)
    manager = service.TranslationJobManager(accounting_policy=synthetic_policy())
    job = start_and_wait(manager, tmp_path / "policy")
    assert job["status"] == "completed", job
    assert len(sdk.requests) == 1
    assert sdk.requests[0]["service_tier"] == "default"
    assert sdk.requests[0]["max_output_tokens"] == 256
    assert accounting_summary(job)["cost_usd"] == pytest.approx(.00066)


def test_default_manager_keeps_ordinary_request_and_accounting_defaults(tmp_path, monkeypatch):
    sdk = install_sdk(monkeypatch)
    manager = service.TranslationJobManager()
    job = start_and_wait(manager, tmp_path / "ordinary")
    assert job["status"] == "completed", job
    assert len(sdk.requests) == 1
    assert "service_tier" not in sdk.requests[0]
    assert "max_output_tokens" not in sdk.requests[0]
    assert accounting_summary(job)["cost_usd"] == pytest.approx(.0009835)
    assert not list(Path(job["artifacts"]["run_dir"]).glob("accounting/*/budget.json"))
