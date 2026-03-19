from __future__ import annotations

from io import BytesIO
from pathlib import Path

import legalpdf_translate.gmail_focus_host as host_module


def _to_wsl_repo_path(path: Path) -> str:
    text = str(path.resolve())
    if len(text) >= 3 and text[1:3] == ":\\":
        drive = text[0].lower()
        tail = text[3:].replace("\\", "/")
        return f"/mnt/{drive}/{tail}" if tail else f"/mnt/{drive}"
    return text.replace("\\", "/")


def _ready_auto_launch_target(tmp_path: Path) -> host_module.AutoLaunchTarget:
    return host_module.AutoLaunchTarget(
        ready=True,
        worktree_path=str(tmp_path),
        python_executable=str(tmp_path / ".venv311" / "Scripts" / "python.exe"),
        launcher_script=str(tmp_path / "tooling" / "launch_qt_build.py"),
        reason="launch_target_ready",
    )


def test_launch_repo_worktree_detaches_browser_server(monkeypatch, tmp_path: Path) -> None:
    target = host_module.AutoLaunchTarget(
        ready=True,
        worktree_path=str(tmp_path),
        python_executable=str(tmp_path / ".venv311" / "Scripts" / "python.exe"),
        launcher_script=None,
        reason="launch_target_ready",
        ui_owner="browser_app",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
        launch_args=("-m", "legalpdf_translate.shadow_web.server", "--port", "8877"),
    )
    recorded: dict[str, object] = {}

    def fake_popen(command, **kwargs):
        recorded["command"] = list(command)
        recorded["kwargs"] = dict(kwargs)

        class _Proc:
            pid = 4242

        return _Proc()

    monkeypatch.setattr(host_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(
        host_module.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("subprocess.run should not be used")),
    )

    result = host_module._launch_repo_worktree(target)

    assert result == "launch_started"
    assert recorded["command"] == [
        str(tmp_path / ".venv311" / "Scripts" / "python.exe"),
        "-m",
        "legalpdf_translate.shadow_web.server",
        "--port",
        "8877",
    ]
    assert recorded["kwargs"]["cwd"] == str(tmp_path)
    assert recorded["kwargs"]["stdout"] == host_module.subprocess.DEVNULL
    assert recorded["kwargs"]["stderr"] == host_module.subprocess.DEVNULL
    assert recorded["kwargs"]["stdin"] == host_module.subprocess.DEVNULL


def test_resolve_auto_launch_target_uses_canonical_worktree_python_when_local_worktree_lacks_venv(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "worktree"
    canonical = tmp_path / "canonical"
    (worktree / "tooling").mkdir(parents=True)
    (worktree / "src" / "legalpdf_translate").mkdir(parents=True)
    (worktree / "docs" / "assistant" / "runtime").mkdir(parents=True)
    (canonical / ".venv311" / "Scripts").mkdir(parents=True)
    (worktree / "tooling" / "launch_qt_build.py").write_text("print('ok')\n", encoding="utf-8")
    (worktree / "src" / "legalpdf_translate" / "qt_app.py").write_text("print('qt')\n", encoding="utf-8")
    python_exe = canonical / ".venv311" / "Scripts" / "python.exe"
    python_exe.write_text("", encoding="utf-8")
    (worktree / "docs" / "assistant" / "runtime" / "CANONICAL_BUILD.json").write_text(
        host_module.json.dumps(
            {
                "canonical_worktree_path": _to_wsl_repo_path(canonical),
                "canonical_branch": "main",
                "approved_base_branch": "main",
                "approved_base_head_floor": "abc1234",
                "canonical_head_floor": "abc1234",
                "allow_noncanonical_by_flag": True,
            }
        ),
        encoding="utf-8",
    )

    target = host_module._resolve_auto_launch_target(
        runtime_path=worktree / "dist" / "legalpdf_translate" / "LegalPDFGmailFocusHost.exe"
    )

    assert target.ready is True
    assert target.worktree_path == str(worktree.resolve())
    assert target.python_executable == str(python_exe.resolve())
    assert target.reason == "launch_target_ready"


def test_build_edge_native_host_manifest_uses_stable_origin(tmp_path: Path) -> None:
    payload = host_module.build_edge_native_host_manifest(
        tmp_path / "LegalPDFGmailFocusHost.exe",
        edge_user_data_dir=tmp_path / "missing-edge-profile",
    )

    assert payload["name"] == "com.legalpdf.gmail_focus"
    assert payload["type"] == "stdio"
    assert payload["allowed_origins"] == ["chrome-extension://afckgbhjkmojchdlinolkepffchlgpin/"]
    assert str(payload["path"]).endswith("LegalPDFGmailFocusHost.exe")


def test_discover_edge_unpacked_gmail_extensions_reads_secure_preferences(tmp_path: Path) -> None:
    secure_preferences = tmp_path / "Profile 2" / "Secure Preferences"
    secure_preferences.parent.mkdir(parents=True, exist_ok=True)
    secure_preferences.write_text(
        host_module.json.dumps(
            {
                "extensions": {
                    "settings": {
                        "hgcahodlnieddgimjmallmidgigdfclc": {
                            "location": 4,
                            "path": r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake",
                            "disable_reasons": [4],
                        },
                        "ignorednongmail": {
                            "location": 4,
                            "path": r"C:\Users\FA507\.codex\other_extension\extension",
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    records = host_module.discover_edge_unpacked_gmail_extensions(edge_user_data_dir=tmp_path)

    assert records == (
        host_module.EdgeUnpackedExtensionRecord(
            profile_name="Profile 2",
            extension_id="hgcahodlnieddgimjmallmidgigdfclc",
            path=r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake",
            disable_reasons=(4,),
            enabled=False,
        ),
    )


def test_edge_native_host_allowed_origins_include_discovered_unpacked_ids(tmp_path: Path) -> None:
    secure_preferences = tmp_path / "Profile 2" / "Secure Preferences"
    secure_preferences.parent.mkdir(parents=True, exist_ok=True)
    secure_preferences.write_text(
        host_module.json.dumps(
            {
                "extensions": {
                    "settings": {
                        "hgcahodlnieddgimjmallmidgigdfclc": {
                            "location": 4,
                            "path": r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert host_module.edge_native_host_allowed_origins(edge_user_data_dir=tmp_path) == (
        "chrome-extension://afckgbhjkmojchdlinolkepffchlgpin/",
        "chrome-extension://hgcahodlnieddgimjmallmidgigdfclc/",
    )


def test_build_edge_extension_report_separates_active_and_stale_ids(tmp_path: Path) -> None:
    secure_preferences = tmp_path / "Profile 2" / "Secure Preferences"
    secure_preferences.parent.mkdir(parents=True, exist_ok=True)
    secure_preferences.write_text(
        host_module.json.dumps(
            {
                "extensions": {
                    "settings": {
                        "afckgbhjkmojchdlinolkepffchlgpin": {
                            "location": 4,
                            "path": r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake",
                            "disable_reasons": [],
                        },
                        "hgcahodlnieddgimjmallmidgigdfclc": {
                            "location": 4,
                            "path": r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake",
                            "disable_reasons": [4],
                        },
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    report = host_module.build_edge_extension_report(edge_user_data_dir=tmp_path)

    assert report["active_extension_ids"] == ["afckgbhjkmojchdlinolkepffchlgpin"]
    assert report["stale_extension_ids"] == ["hgcahodlnieddgimjmallmidgigdfclc"]
    assert report["paths"] == [r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake"]


def test_edge_native_host_manifest_path_uses_native_messaging_dir(tmp_path: Path) -> None:
    assert host_module.edge_native_host_manifest_path(tmp_path) == (
        tmp_path / "native_messaging" / "com.legalpdf.gmail_focus.edge.json"
    )


def test_ensure_edge_native_host_registered_writes_manifest_and_registry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(host_module, "_is_windows", lambda: True)
    host_exe = tmp_path / "LegalPDFGmailFocusHost.exe"
    host_exe.write_text("host", encoding="utf-8")
    registry: dict[str, str] = {}

    result = host_module.ensure_edge_native_host_registered(
        base_dir=tmp_path,
        host_executable_path=host_exe,
        read_registry_value=lambda: registry.get("value"),
        write_registry_value=lambda value: registry.__setitem__("value", value),
    )

    manifest_path = tmp_path / "native_messaging" / "com.legalpdf.gmail_focus.edge.json"
    assert result == host_module.NativeHostRegistrationResult(
        ok=True,
        changed=True,
        manifest_path=str(manifest_path.resolve()),
        executable_path=str(host_exe.resolve()),
        reason="registered",
    )
    assert registry["value"] == str(manifest_path.resolve())
    payload = host_module.json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["name"] == "com.legalpdf.gmail_focus"
    assert payload["path"] == str(host_exe.resolve())


def test_ensure_edge_native_host_registered_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(host_module, "_is_windows", lambda: True)
    host_exe = tmp_path / "LegalPDFGmailFocusHost.exe"
    host_exe.write_text("host", encoding="utf-8")
    manifest_path = tmp_path / "native_messaging" / "com.legalpdf.gmail_focus.edge.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        host_module.json.dumps(
            host_module.build_edge_native_host_manifest(host_exe.resolve()),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    result = host_module.ensure_edge_native_host_registered(
        base_dir=tmp_path,
        host_executable_path=host_exe,
        read_registry_value=lambda: str(manifest_path.resolve()),
        write_registry_value=lambda _value: (_ for _ in ()).throw(AssertionError("unexpected registry write")),
    )

    assert result == host_module.NativeHostRegistrationResult(
        ok=True,
        changed=False,
        manifest_path=str(manifest_path.resolve()),
        executable_path=str(host_exe.resolve()),
        reason="already_registered",
    )


def test_native_message_round_trip() -> None:
    payload = {"action": "focus_app", "bridgePort": 9011}
    stream = BytesIO()

    host_module.write_native_message(stream, payload)
    stream.seek(0)

    assert host_module.read_native_message(stream) == payload


def test_prepare_gmail_intake_returns_config_and_focus_diagnostics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: _ready_auto_launch_target(tmp_path),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {
                "ok": bridge_port == 9011 and base_dir == tmp_path,
                "pid": 4321,
                "hwnd": 101,
                "reason": "bridge_owner_ready",
            },
        )(),
    )
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {
                "ok": bridge_port == 9011 and base_dir == tmp_path,
                "focused": False,
                "flashed": True,
                "reason": "foreground_blocked",
            },
        )(),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": True,
        "focused": False,
        "flashed": True,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "qt_app",
        "bridgePort": 9011,
        "bridgeToken": "shared-token",
        "reason": "foreground_blocked",
    }


def test_prepare_gmail_intake_rejects_disabled_bridge(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: _ready_auto_launch_target(tmp_path),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": False,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("focus should not be requested")),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "none",
        "bridgePort": 9011,
        "reason": "bridge_disabled",
    }


def test_prepare_gmail_intake_rejects_blank_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: _ready_auto_launch_target(tmp_path),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "   ",
            "gmail_intake_port": 9011,
        },
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": False,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "none",
        "bridgePort": 9011,
        "reason": "bridge_token_missing",
    }


def test_prepare_gmail_intake_without_focus_uses_runtime_validation_and_hides_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: _ready_auto_launch_target(tmp_path),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {
                "ok": bridge_port == 9011 and base_dir == tmp_path,
                "pid": 4321,
                "hwnd": 101,
                "reason": "bridge_owner_ready",
            },
        )(),
    )
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("focus path should not run")),
    )

    payload = host_module.prepare_gmail_intake(
        base_dir=tmp_path,
        request_focus=False,
        include_token=False,
    )

    assert payload == {
        "ok": True,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "qt_app",
        "bridgePort": 9011,
        "reason": "bridge_owner_ready",
    }


def test_prepare_gmail_intake_returns_runtime_failure_without_token(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: _ready_auto_launch_target(tmp_path),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {
                "ok": False,
                "pid": 4321,
                "hwnd": None,
                "reason": "runtime_metadata_missing",
            },
        )(),
    )
    monkeypatch.setattr(
        host_module,
        "_launch_repo_worktree",
        lambda _target: (_ for _ in ()).throw(AssertionError("launch should not run when request_focus is false")),
    )

    payload = host_module.prepare_gmail_intake(
        base_dir=tmp_path,
        request_focus=False,
        include_token=False,
    )

    assert payload == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "none",
        "bridgePort": 9011,
        "reason": "runtime_metadata_missing",
    }


def test_prepare_gmail_intake_launches_app_when_bridge_missing(monkeypatch, tmp_path: Path) -> None:
    ready_target = _ready_auto_launch_target(tmp_path)
    monkeypatch.setattr(host_module, "_resolve_auto_launch_target", lambda: ready_target)
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )

    validate_calls = {"count": 0}

    def fake_validate_bridge_owner(*, bridge_port, base_dir):
        validate_calls["count"] += 1
        if validate_calls["count"] == 1:
            return type(
                "Result",
                (),
                {"ok": False, "pid": None, "hwnd": None, "reason": "runtime_metadata_missing"},
            )()
        return type(
            "Result",
            (),
            {"ok": True, "pid": 4321, "hwnd": 101, "reason": "bridge_owner_ready"},
        )()

    launch_calls: list[str] = []
    wait_calls: list[int] = []
    monkeypatch.setattr(host_module, "validate_bridge_owner", fake_validate_bridge_owner)
    monkeypatch.setattr(
        host_module,
        "_launch_repo_worktree",
        lambda target: launch_calls.append(str(target.worktree_path)) or "launch_started",
    )
    monkeypatch.setattr(
        host_module,
        "_wait_for_bridge_owner_after_launch",
        lambda *, bridge_port, base_dir: wait_calls.append(bridge_port) or "launch_ready",
    )
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {"ok": True, "focused": True, "flashed": False, "reason": "foreground_set"},
        )(),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": True,
        "focused": True,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": True,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "qt_app",
        "bridgePort": 9011,
        "bridgeToken": "shared-token",
        "reason": "foreground_set",
    }
    assert launch_calls == [str(tmp_path)]
    assert wait_calls == [9011]


def test_prepare_gmail_intake_launches_app_when_runtime_metadata_is_stale(monkeypatch, tmp_path: Path) -> None:
    ready_target = _ready_auto_launch_target(tmp_path)
    monkeypatch.setattr(host_module, "_resolve_auto_launch_target", lambda: ready_target)
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )

    validate_calls = {"count": 0}

    def fake_validate_bridge_owner(*, bridge_port, base_dir):
        validate_calls["count"] += 1
        if validate_calls["count"] == 1:
            return type(
                "Result",
                (),
                {"ok": False, "pid": None, "hwnd": None, "reason": "bridge_owner_stale"},
            )()
        return type(
            "Result",
            (),
            {"ok": True, "pid": 4321, "hwnd": 101, "reason": "bridge_owner_ready"},
        )()

    launch_calls: list[str] = []
    monkeypatch.setattr(host_module, "validate_bridge_owner", fake_validate_bridge_owner)
    monkeypatch.setattr(
        host_module,
        "_launch_repo_worktree",
        lambda target: launch_calls.append(str(target.worktree_path)) or "launch_started",
    )
    monkeypatch.setattr(
        host_module,
        "_wait_for_bridge_owner_after_launch",
        lambda *, bridge_port, base_dir: "launch_ready",
    )
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {"ok": True, "focused": True, "flashed": False, "reason": "foreground_set"},
        )(),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload["ok"] is True
    assert payload["launched"] is True
    assert payload["reason"] == "foreground_set"
    assert launch_calls == [str(tmp_path)]


def test_prepare_gmail_intake_returns_launch_target_missing_when_autostart_is_unavailable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: host_module.AutoLaunchTarget(
            ready=False,
            worktree_path=None,
            python_executable=None,
            launcher_script=None,
            reason="launch_target_missing",
        ),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {"ok": False, "pid": None, "hwnd": None, "reason": "runtime_metadata_missing"},
        )(),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": False,
        "launchTargetReason": "launch_target_missing",
        "ui_owner": "none",
        "bridgePort": 9011,
        "reason": "launch_target_missing",
    }


def test_prepare_gmail_intake_returns_launch_timeout_after_spawn(monkeypatch, tmp_path: Path) -> None:
    ready_target = _ready_auto_launch_target(tmp_path)
    monkeypatch.setattr(host_module, "_resolve_auto_launch_target", lambda: ready_target)
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {"ok": False, "pid": None, "hwnd": None, "reason": "bridge_not_running"},
        )(),
    )
    monkeypatch.setattr(host_module, "_launch_repo_worktree", lambda _target: "launch_started")
    monkeypatch.setattr(
        host_module,
        "_wait_for_bridge_owner_after_launch",
        lambda *, bridge_port, base_dir: "launch_timeout",
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": True,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "none",
        "bridgePort": 9011,
        "reason": "launch_timeout",
    }


def test_prepare_gmail_intake_does_not_launch_when_bridge_port_owner_mismatches(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: _ready_auto_launch_target(tmp_path),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {"ok": False, "pid": 777, "hwnd": None, "reason": "bridge_port_owner_mismatch"},
        )(),
    )
    monkeypatch.setattr(
        host_module,
        "_launch_repo_worktree",
        lambda _target: (_ for _ in ()).throw(AssertionError("launch should not run for owner mismatch")),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "none",
        "bridgePort": 9011,
        "reason": "bridge_port_owner_mismatch",
    }


def test_prepare_gmail_intake_returns_browser_owner_context_without_focus(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "_resolve_auto_launch_target",
        lambda: host_module.AutoLaunchTarget(
            ready=True,
            worktree_path=str(tmp_path),
            python_executable=str(tmp_path / ".venv311" / "Scripts" / "python.exe"),
            launcher_script=None,
            reason="launch_target_ready",
            ui_owner="browser_app",
            browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
            launch_args=("-m", "legalpdf_translate.shadow_web.server", "--port", "8877"),
        ),
    )
    monkeypatch.setattr(
        host_module,
        "load_gui_settings",
        lambda: {
            "gmail_intake_bridge_enabled": True,
            "gmail_intake_bridge_token": "shared-token",
            "gmail_intake_port": 9011,
        },
    )
    monkeypatch.setattr(
        host_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {
                "ok": bridge_port == 9011 and base_dir == tmp_path,
                "pid": 4321,
                "hwnd": None,
                "reason": "bridge_owner_ready",
                "owner_kind": "browser_app",
                "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
                "workspace_id": "gmail-intake",
                "runtime_mode": "live",
            },
        )(),
    )
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("focus should not run for browser owner")),
    )

    payload = host_module.prepare_gmail_intake(base_dir=tmp_path)

    assert payload == {
        "ok": True,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": True,
        "launched": False,
        "autoLaunchReady": True,
        "launchTarget": str(tmp_path),
        "launchTargetReason": "launch_target_ready",
        "ui_owner": "browser_app",
        "browser_url": "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
        "workspace_id": "gmail-intake",
        "runtime_mode": "live",
        "bridgePort": 9011,
        "bridgeToken": "shared-token",
        "reason": "bridge_owner_ready",
    }


def test_handle_native_message_validates_action_and_port() -> None:
    assert host_module.handle_native_message(None) == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "reason": "invalid_payload",
    }
    assert host_module.handle_native_message({"action": "noop"}) == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "reason": "unsupported_action",
    }
    assert host_module.handle_native_message({"action": "focus_app", "bridgePort": "bad"}) == {
        "ok": False,
        "focused": False,
        "flashed": False,
        "reason": "invalid_bridge_port",
    }


def test_handle_native_message_prepare_gmail_intake_honors_flags(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_prepare_gmail_intake(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "focused": False, "flashed": False, "reason": "bridge_owner_ready"}

    monkeypatch.setattr(host_module, "prepare_gmail_intake", fake_prepare_gmail_intake)

    payload = host_module.handle_native_message(
        {
            "action": "prepare_gmail_intake",
            "requestFocus": False,
            "includeToken": False,
        },
        base_dir=tmp_path,
    )

    assert payload == {
        "ok": True,
        "focused": False,
        "flashed": False,
        "reason": "bridge_owner_ready",
    }
    assert captured["base_dir"] == tmp_path
    assert captured["request_focus"] is False
    assert captured["include_token"] is False


def test_handle_native_message_delegates_to_focus_bridge_owner(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        host_module,
        "focus_bridge_owner",
        lambda *, bridge_port, base_dir: type(
            "Result",
            (),
            {
                "ok": bridge_port == 9011 and base_dir == tmp_path,
                "focused": False,
                "flashed": True,
                "reason": "foreground_blocked",
            },
        )(),
    )

    payload = host_module.handle_native_message(
        {"action": "focus_app", "bridgePort": 9011},
        base_dir=tmp_path,
    )

    assert payload == {
        "ok": True,
        "focused": False,
        "flashed": True,
        "reason": "foreground_blocked",
    }
