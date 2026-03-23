from __future__ import annotations

import importlib.util
import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tooling" / "launch_browser_app_live_detached.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("launch_browser_app_live_detached", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_python_runtime_falls_back_to_current_interpreter(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    fallback_python = tmp_path / "python.exe"
    fallback_python.write_text("", encoding="utf-8")

    monkeypatch.setattr(module.sys, "executable", str(fallback_python))

    runtime = module._python_runtime(tmp_path)

    assert runtime == fallback_python.resolve()


def test_launcher_env_prepends_repo_src_to_pythonpath(tmp_path: Path, monkeypatch) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    (repo_root / "src").mkdir(parents=True)
    monkeypatch.setenv("PYTHONPATH", "C:\\existing\\path")

    env = module._launcher_env(repo_root)

    expected_src = str((repo_root / "src").resolve())
    assert env["PYTHONPATH"] == os.pathsep.join([expected_src, "C:\\existing\\path"])


def test_browser_url_uses_mode_workspace_port_and_ui() -> None:
    module = _load_module()

    qt_url = module._browser_url(port=9988, mode="shadow", workspace="workspace-preview")
    legacy_url = module._browser_url(port=9988, mode="shadow", workspace="workspace-preview", ui="legacy")
    gmail_url = module._browser_url(
        port=8877,
        mode="live",
        workspace="gmail-intake",
        view="gmail-intake",
    )

    assert qt_url == "http://127.0.0.1:9988/?mode=shadow&workspace=workspace-preview#new-job"
    assert legacy_url == "http://127.0.0.1:9988/?mode=shadow&workspace=workspace-preview&ui=legacy#dashboard"
    assert gmail_url == "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake"


def test_main_reuses_existing_server_and_opens_requested_preview_url(monkeypatch) -> None:
    module = _load_module()
    seen: dict[str, object] = {}

    monkeypatch.setattr(module, "_probe_browser_url", lambda url: True)
    monkeypatch.setattr(module, "_spawn_server", lambda **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(module, "_open_browser", lambda url: seen.setdefault("opened", url) or True)

    result = module.main(["--mode", "shadow", "--workspace", "workspace-preview", "--port", "8888"])

    assert result == 0
    assert seen["opened"] == "http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job"


def test_main_opens_requested_gmail_intake_view(monkeypatch) -> None:
    module = _load_module()
    seen: dict[str, object] = {}

    monkeypatch.setattr(module, "_probe_browser_url", lambda url: True)
    monkeypatch.setattr(module, "_spawn_server", lambda **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(module, "_open_browser", lambda url: seen.setdefault("opened", url) or True)

    result = module.main(
        ["--mode", "live", "--workspace", "gmail-intake", "--port", "8877", "--view", "gmail-intake"]
    )

    assert result == 0
    assert seen["opened"] == "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake"


def test_main_launches_browser_server_with_no_open_and_src_pythonpath(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    pythonw = repo_root / ".venv311" / "Scripts" / "pythonw.exe"
    pythonw.parent.mkdir(parents=True)
    pythonw.write_text("", encoding="utf-8")
    (repo_root / "src").mkdir(parents=True)
    monkeypatch.setattr(module, "REPO_ROOT", repo_root)
    monkeypatch.delenv("PYTHONPATH", raising=False)

    seen: dict[str, object] = {}

    class _FakeProc:
        pid = 4321

    def _fake_popen(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return _FakeProc()

    monkeypatch.setattr(module.subprocess, "Popen", _fake_popen)
    monkeypatch.setattr(module, "_probe_browser_url", lambda url: False)
    monkeypatch.setattr(module, "_wait_until_ready", lambda url: True)
    monkeypatch.setattr(module, "_open_browser", lambda url: (_ for _ in ()).throw(AssertionError()))

    result = module.main(
        [
            "--mode",
            "shadow",
            "--workspace",
            "workspace-preview",
            "--port",
            "8888",
            "--ui",
            "legacy",
            "--no-open",
        ]
    )

    assert result == 0
    assert seen["args"] == [
        str(pythonw),
        "-m",
        "legalpdf_translate.shadow_web.server",
        "--port",
        "8888",
    ]
    kwargs = seen["kwargs"]
    assert kwargs["cwd"] == str(repo_root)
    assert kwargs["close_fds"] is True
    assert kwargs["creationflags"] == (
        module.DETACHED_PROCESS | module.CREATE_NEW_PROCESS_GROUP | module.CREATE_NO_WINDOW
    )
    expected_src = str((repo_root / "src").resolve())
    assert kwargs["env"]["PYTHONPATH"] == expected_src
    assert (repo_root / "tmp" / "browser_app_8888.spawned.out.log").exists()
    assert (repo_root / "tmp" / "browser_app_8888.spawned.err.log").exists()
