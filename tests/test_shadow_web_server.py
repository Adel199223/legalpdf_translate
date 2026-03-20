from __future__ import annotations

import asyncio
from contextlib import nullcontext

from legalpdf_translate.shadow_web import server


class _FakePolicy(asyncio.DefaultEventLoopPolicy):
    pass


class _FakeSelectorPolicy(asyncio.DefaultEventLoopPolicy):
    pass


def test_configure_windows_asyncio_policy_sets_selector_policy(monkeypatch) -> None:
    seen: list[asyncio.AbstractEventLoopPolicy] = []
    current_policy = _FakePolicy()

    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(server.asyncio, "WindowsSelectorEventLoopPolicy", _FakeSelectorPolicy, raising=False)
    monkeypatch.setattr(server.asyncio, "get_event_loop_policy", lambda: current_policy)
    monkeypatch.setattr(server.asyncio, "set_event_loop_policy", lambda policy: seen.append(policy))

    server._configure_windows_asyncio_policy()

    assert len(seen) == 1
    assert isinstance(seen[0], _FakeSelectorPolicy)


def test_configure_windows_asyncio_policy_noops_when_selector_already_active(monkeypatch) -> None:
    current_policy = _FakeSelectorPolicy()
    seen: list[asyncio.AbstractEventLoopPolicy] = []

    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(server.asyncio, "WindowsSelectorEventLoopPolicy", _FakeSelectorPolicy, raising=False)
    monkeypatch.setattr(server.asyncio, "get_event_loop_policy", lambda: current_policy)
    monkeypatch.setattr(server.asyncio, "set_event_loop_policy", lambda policy: seen.append(policy))

    server._configure_windows_asyncio_policy()

    assert seen == []


def test_run_browser_server_disables_uvicorn_signal_handlers_on_windows(monkeypatch) -> None:
    seen: dict[str, object] = {}

    class FakeConfig:
        def __init__(self, app, **kwargs):
            seen["config_app"] = app
            seen["config_kwargs"] = kwargs

    class FakeServer:
        def __init__(self, config):
            seen["server_config"] = config
            self.install_signal_handlers = object()
            self.capture_signals = object()

        def run(self) -> None:
            seen["install_signal_handlers"] = self.install_signal_handlers
            seen["capture_signals"] = self.capture_signals
            seen["ran"] = True

    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(server.uvicorn, "Config", FakeConfig)
    monkeypatch.setattr(server.uvicorn, "Server", FakeServer)

    app = object()
    server._run_browser_server(app, port=8877)

    assert seen["config_app"] is app
    assert seen["config_kwargs"] == {
        "host": server.SHADOW_HOST,
        "port": 8877,
        "log_level": "info",
        "loop": "asyncio",
        "http": "h11",
    }
    assert seen["install_signal_handlers"]() is None
    assert seen["capture_signals"] is nullcontext
    assert seen["ran"] is True


def test_default_browser_url_targets_new_job() -> None:
    assert server._default_browser_url(8877) == "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job"
