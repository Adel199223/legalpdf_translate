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

    assert runtime == Path(os.path.abspath(str(fallback_python)))


def test_python_runtime_prefers_console_python_with_no_window_flags(tmp_path: Path) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    python = repo_root / ".venv311" / "Scripts" / "python.exe"
    pythonw = repo_root / ".venv311" / "Scripts" / "pythonw.exe"
    pythonw.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    pythonw.write_text("", encoding="utf-8")

    runtime = module._python_runtime(repo_root)

    assert runtime == Path(os.path.abspath(str(python)))


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
    gmail_url = module._browser_url(port=8877, mode="live", workspace="gmail-intake")
    legacy_url = module._browser_url(port=9988, mode="shadow", workspace="workspace-preview", ui="legacy")

    assert qt_url == "http://127.0.0.1:9988/?mode=shadow&workspace=workspace-preview#new-job"
    assert gmail_url == "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake"
    assert legacy_url == "http://127.0.0.1:9988/?mode=shadow&workspace=workspace-preview&ui=legacy#dashboard"


def test_main_reuses_existing_server_and_opens_requested_preview_url(monkeypatch) -> None:
    module = _load_module()
    seen: dict[str, object] = {}

    monkeypatch.setattr(module, "_probe_browser_url", lambda url: True)
    monkeypatch.setattr(module, "_spawn_server", lambda **kwargs: (_ for _ in ()).throw(AssertionError()))
    monkeypatch.setattr(
        module,
        "_open_browser",
        lambda url, **kwargs: seen.setdefault("opened", (url, kwargs)) or True,
    )

    result = module.main(["--mode", "shadow", "--workspace", "workspace-preview", "--port", "8888"])

    assert result == 0
    assert seen["opened"] == (
        "http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job",
        {
            "workspace": "workspace-preview",
            "launch_session_id": "",
        },
    )


def test_main_launches_browser_server_with_no_open_and_src_pythonpath(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    repo_root = tmp_path / "repo"
    python = repo_root / ".venv311" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
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
        str(python),
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


def test_open_browser_uses_server_only_launch_for_gmail_workspace(monkeypatch) -> None:
    module = _load_module()
    launch_updates: list[dict[str, object]] = []
    monkeypatch.setattr(
        module,
        "_update_launch_session",
        lambda launch_session_id, **fields: launch_updates.append(
            {
                "launch_session_id": launch_session_id,
                **fields,
            }
        ) if str(launch_session_id or "").strip() else None,
    )
    monkeypatch.setattr(module.os, "startfile", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic startfile should not run")))
    monkeypatch.setattr(module.webbrowser, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic webbrowser.open should not run")))

    result = module._open_browser(
        "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
        workspace="gmail-intake",
        launch_session_id="launch-123",
    )

    assert result is False
    assert launch_updates == [
        {
            "launch_session_id": "launch-123",
            "browser_launch_status": "server_only",
            "browser_launch_reason": "extension_browser_surface_owner",
            "launched_browser_pid": 0,
            "launched_browser_path": "",
            "launched_browser_user_data_dir": "",
            "launched_browser_profile": "",
            "launched_browser_command": "",
        }
    ]


def test_open_browser_does_not_need_launch_session_id_for_gmail_server_only_mode(
    monkeypatch,
) -> None:
    module = _load_module()
    launch_updates: list[dict[str, object]] = []

    monkeypatch.setattr(
        module,
        "_update_launch_session",
        lambda launch_session_id, **fields: launch_updates.append(
            {
                "launch_session_id": launch_session_id,
                **fields,
            }
        ) if str(launch_session_id or "").strip() else None,
    )
    monkeypatch.setattr(module.os, "startfile", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic startfile should not run")))
    monkeypatch.setattr(module.webbrowser, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic webbrowser.open should not run")))

    result = module._open_browser(
        "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
        workspace="gmail-intake",
        launch_session_id="",
    )

    assert result is False
    assert launch_updates == []


def test_open_browser_uses_generic_launch_for_non_gmail_workspace(monkeypatch) -> None:
    module = _load_module()
    seen: dict[str, object] = {}

    monkeypatch.setattr(module.os, "startfile", lambda url: seen.setdefault("startfile", url))
    monkeypatch.setattr(module.webbrowser, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic webbrowser.open should not run when startfile succeeds")))

    result = module._open_browser(
        "http://127.0.0.1:8877/?mode=live&workspace=workspace-preview#new-job",
        workspace="workspace-preview",
    )

    assert result is True
    assert seen["startfile"] == "http://127.0.0.1:8877/?mode=live&workspace=workspace-preview#new-job"
