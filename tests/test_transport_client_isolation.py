"""Offline credential/SDK provenance checks for worker creation."""

from types import SimpleNamespace

import legalpdf_translate.openai_client as module
from legalpdf_translate.openai_client import OpenAIResponsesClient


def _forbidden(*args, **kwargs):
    raise AssertionError("ambient credentials or provider construction was accessed")


def test_injected_client_and_worker_clone_never_resolve_ambient_credentials(monkeypatch):
    monkeypatch.setattr(module, "resolve_openai_key_with_source", _forbidden)
    monkeypatch.setattr(module, "OpenAI", _forbidden)
    sdk = SimpleNamespace(responses=SimpleNamespace(create=_forbidden))
    logger = lambda _message: None
    client = OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=2, logger=logger)
    worker = client.clone()

    assert worker is not client
    assert worker._client is sdk
    assert worker._logger is logger
    assert worker._max_transport_retries == 2
    assert worker.local_credential_preflight().ok is True
    assert "not yet tested" in worker.local_credential_preflight().message


def test_injected_sdk_disables_hidden_retries_and_clone_keeps_exact_configuration(monkeypatch):
    monkeypatch.setattr(module, "resolve_openai_key_with_source", _forbidden)
    configured = SimpleNamespace(responses=SimpleNamespace(create=_forbidden))
    options = []
    original = SimpleNamespace(with_options=lambda **kwargs: options.append(kwargs) or configured)
    client = OpenAIResponsesClient(sdk_client=original, base_backoff_seconds=2.5,
                                   backoff_cap_seconds=9, request_timeout_seconds=42)
    worker_logger = lambda _message: None
    worker = client.clone(logger=worker_logger)

    assert options == [{"max_retries": 0}]
    assert worker._client is configured
    assert worker._logger is worker_logger
    assert client._logger is None
    assert worker._base_backoff_seconds == 2.5
    assert worker._backoff_cap_seconds == 9
    assert worker._request_timeout_seconds == 42


def test_inline_client_preflight_and_clone_do_not_reresolve_key(monkeypatch):
    sdk = SimpleNamespace(responses=SimpleNamespace(create=_forbidden))
    monkeypatch.setattr(module, "OpenAI", lambda **kwargs: sdk)
    client = OpenAIResponsesClient(api_key="synthetic-key")
    monkeypatch.setattr(module, "resolve_openai_key_with_source", _forbidden)
    assert client.local_credential_preflight().credential_source.kind == "inline"
    assert client.clone()._client is sdk
