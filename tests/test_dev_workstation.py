from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows workstation checker")
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_dev_workstation.ps1"


@pytest.fixture(scope="session")
def fake_version_executable(tmp_path_factory):
    """A native fake SDK executable, compiled only into the pytest-owned temp tree."""
    target = tmp_path_factory.mktemp("native version probe") / "fake.exe"
    source = '''using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
public class FakeVersionProbe {
    static string Quote(string value) { return "\\\"" + value.Replace("\\\"", "\\\\\\\"") + "\\\""; }
    public static int Main(string[] args) {
        string tool = Path.GetFileNameWithoutExtension(Assembly.GetExecutingAssembly().Location);
        ProcessStartInfo start = new ProcessStartInfo();
        start.FileName = Environment.GetEnvironmentVariable("WORKSTATION_TEST_PYTHON");
        start.Arguments = Quote(Environment.GetEnvironmentVariable("WORKSTATION_TEST_DRIVER")) + " " + Quote(tool);
        foreach (string arg in args) { start.Arguments += " " + Quote(arg); }
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.RedirectStandardOutput = true;
        start.RedirectStandardError = true;
        using (Process child = Process.Start(start)) {
            Console.Write(child.StandardOutput.ReadToEnd());
            Console.Error.Write(child.StandardError.ReadToEnd());
            child.WaitForExit();
            return child.ExitCode;
        }
    }
}
'''
    power_shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    quoted_target = "'" + str(target).replace("'", "''") + "'"
    command = "Add-Type -TypeDefinition @'\n" + source + "'@ -OutputAssembly " + quoted_target + " -OutputType ConsoleApplication"
    result = subprocess.run(
        [str(power_shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        text=True, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0 and target.is_file(), result.stdout + result.stderr
    return target


@pytest.fixture
def workstation_sandbox(tmp_path: Path, fake_version_executable: Path):
    """Only synthetic tools are discoverable by the child PowerShell process."""
    repo = tmp_path / "checkout with spaces"
    for relative in (
        "scripts/check_dev_workstation.ps1",
        "config/dev-workstation.json",
        "config/dev-workstation.winget",
        ".python-version",
        ".node-version",
        ".dart-version",
        "pyproject.toml",
        "uv.lock",
    ):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    tools = tmp_path / "fake tools"
    tools.mkdir()
    state = tmp_path / "state.json"
    log = tmp_path / "calls.jsonl"
    fake = tools / "fake_tool.py"
    fake.write_text(
        '''import json, os, pathlib, sys
state = json.loads(pathlib.Path(os.environ["WORKSTATION_TEST_STATE"]).read_text())
tool, *args = sys.argv[1:]
with open(state["log"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps({"tool": tool, "args": args}) + "\\n")
output = state["discovered_python"] if tool == "uv" and args[:2] == ["python", "find"] else state["outputs"][tool]
sys.stdout.write(output + "\\n")
sys.exit(state.get("failures", {}).get(tool, 0))
''',
        encoding="utf-8",
    )
    outputs = {
        "python": "Python 3.11.9",
        "uv": "uv 0.12.20",
        "node": "v24.14.0",
        "dart": 'Dart SDK version: 3.11.0 (stable) on "windows_x64"',
        "dart-wrapper": 'Dart SDK version: 3.11.0 (stable) on "windows_x64"',
        "direct-dart": 'Dart SDK version: 3.11.0 (stable) on "windows_x64"',
        "git": "git version 2.54.0.windows.1",
        "gh": "gh version 2.91.0 (2026-09-01)",
        "rg": "ripgrep 15.1.0",
        "pwsh": "PowerShell 7.6.1",
        "winget": "v1.29.380",
    }
    for tool in outputs:
        dispatch_name = "dart-wrapper" if tool == "dart" else tool
        (tools / f"{tool}.cmd").write_text(
            f'@echo off\n"{sys.executable}" "{fake}" {dispatch_name} %*\nexit /b %errorlevel%\n',
            encoding="utf-8",
        )
    direct_sdk = tools / "direct SDK"
    direct_sdk.mkdir()
    shutil.copyfile(fake_version_executable, direct_sdk / "dart.exe")
    shutil.copyfile(fake_version_executable, direct_sdk / "direct-dart.exe")
    power_shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    assert power_shell.is_file()
    existing_environment = repo / ".venv311"
    existing_environment.mkdir()
    (existing_environment / "pyvenv.cfg").write_text("protected existing environment\n", encoding="utf-8")
    (existing_environment / "keep.txt").write_text("must remain unchanged\n", encoding="utf-8")

    def run(
        *arguments: str,
        version_outputs: dict[str, str] | None = None,
        failures: dict[str, int] | None = None,
        missing: tuple[str, ...] = (),
        explicit_python: bool = True,
        explicit_dart: bool = True,
        discovered_python: str | None = None,
    ):
        state.write_text(
            json.dumps({
                "log": str(log), "outputs": outputs | (version_outputs or {}), "failures": failures or {},
                "discovered_python": discovered_python or str(tools / "python.cmd"),
            }),
            encoding="utf-8",
        )
        if log.exists():
            log.unlink()
        for tool in missing:
            (tools / f"{tool}.cmd").unlink()
            if tool == "dart":
                (direct_sdk / "dart.exe").unlink()
        env = os.environ.copy()
        # Real installed commands cannot mask a missing fake command or run accidentally.
        env["PATH"] = str(tools)
        env["WORKSTATION_TEST_STATE"] = str(state)
        env["WORKSTATION_TEST_PYTHON"] = sys.executable
        env["WORKSTATION_TEST_DRIVER"] = str(fake)
        baseline = {str(path.relative_to(repo)): path.read_bytes() for path in repo.rglob("*") if path.is_file()}
        args = [str(power_shell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(repo / "scripts" / SCRIPT.name)]
        if explicit_python:
            args.extend(("-PythonExecutable", str(tools / "python.cmd")))
        if explicit_dart and "-DartExecutable" not in arguments:
            args.extend(("-DartExecutable", str(direct_sdk / "dart.exe")))
        args.extend(arguments)
        result = subprocess.run(
            args,
            cwd=tmp_path,
            env=env,
            text=True,
            capture_output=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        assert baseline == {str(path.relative_to(repo)): path.read_bytes() for path in repo.rglob("*") if path.is_file()}
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        for call in calls:
            assert (
                call["args"] == ["--version"]
                or call["tool"] == "pwsh" and call["args"] == ["-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"]
                or call["tool"] == "uv" and call["args"] == ["python", "find", "3.11.9", "--no-project", "--no-python-downloads"]
            ), f"Checker attempted a non-read-only tool operation: {call}"
        return result, calls

    return repo, tools, run


def _report(result: subprocess.CompletedProcess[str]) -> dict:
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"Expected only JSON on stdout; got {result.stdout!r}\n{result.stderr}")
    assert isinstance(report, dict)
    return report


def _check(report: dict, name: str) -> dict:
    matching = [check for check in report["checks"] if check["name"] == name]
    assert len(matching) == 1
    return matching[0]


def test_configuration_only_needs_no_installed_tools_and_leaves_checkout_unchanged(workstation_sandbox):
    _, _, run = workstation_sandbox
    result, calls = run(
        "-ConfigurationOnly", "-AsJson",
        missing=("python", "uv", "node", "dart", "git", "gh", "rg", "pwsh", "winget"),
        explicit_python=False,
        explicit_dart=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = _report(result)
    assert report["status"] == "pass"
    assert report["mode"] == "configuration-only"
    assert _check(report, "configuration")["status"] == "pass"
    assert calls == []


@pytest.mark.parametrize(
    ("pin_file", "wrong_version"),
    [(".python-version", "3.12.10"), (".node-version", "25.0.0"), (".dart-version", "3.12.0")],
)
def test_configuration_pin_drift_is_rejected_before_any_tool_probe(workstation_sandbox, pin_file, wrong_version):
    repo, _, run = workstation_sandbox
    (repo / pin_file).write_text(wrong_version + "\n", encoding="utf-8")
    result, calls = run("-ConfigurationOnly", "-AsJson")
    assert result.returncode != 0
    report = _report(result)
    assert report["status"] == "fail"
    assert _check(report, "configuration")["status"] == "fail"
    assert calls == []


def test_invalid_workstation_manifest_is_rejected_before_any_tool_probe(workstation_sandbox):
    repo, _, run = workstation_sandbox
    (repo / "config/dev-workstation.json").write_text("{ invalid JSON", encoding="utf-8")
    result, calls = run("-ConfigurationOnly", "-AsJson")
    assert result.returncode != 0
    _report(result)
    assert calls == []


def test_default_finds_exact_python_without_downloads_or_environment_changes(workstation_sandbox):
    _, tools, run = workstation_sandbox
    result, calls = run("-AsJson", explicit_python=False)
    assert result.returncode == 0, result.stdout + result.stderr
    report = _report(result)
    assert report["status"] == "pass"
    assert report["mode"] == "read-only-readiness"
    assert all(check["status"] == "pass" for check in report["checks"])
    assert calls[:3] == [
        {"tool": "uv", "args": ["--version"]},
        {"tool": "uv", "args": ["python", "find", "3.11.9", "--no-project", "--no-python-downloads"]},
        {"tool": "python", "args": ["--version"]},
    ]
    assert (tools / "python.cmd").is_file()


def test_explicit_existing_python_skips_uv_python_discovery(workstation_sandbox):
    _, _, run = workstation_sandbox
    result, calls = run("-AsJson")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _check(_report(result), "python")["actual"] == "3.11.9"
    assert [call["args"] for call in calls if call["tool"] == "uv"] == [["--version"]]


@pytest.mark.parametrize(
    ("tool", "wrong_output"),
    [
        ("python", "Python 3.14.4"),
        ("uv", "uv 0.13.0"),
        ("node", "v25.0.0"),
        ("dart", 'Dart SDK version: 3.12.0 (stable) on "windows_x64"'),
        ("git", "git version 2.55.0.windows.1"),
    ],
)
def test_required_version_drift_fails_without_repair(workstation_sandbox, tool, wrong_output):
    _, _, run = workstation_sandbox
    result, calls = run("-AsJson", version_outputs={tool: wrong_output})
    assert result.returncode != 0
    report = _report(result)
    check = _check(report, tool)
    assert report["status"] == "fail"
    assert check["required"] is True and check["status"] == "fail"
    assert "no changes" in check["message"].lower()
    assert all(call["args"] == ["--version"] or call["tool"] == "pwsh" for call in calls)


@pytest.mark.parametrize(
    ("tool", "prerelease_output", "complete_version", "required"),
    [
        ("python", "Python 3.11.9rc1", "3.11.9rc1", True),
        ("uv", "uv 0.12.20-rc.1 (fictional build)", "0.12.20-rc.1", True),
        ("git", "git version 2.54.0.windows.1-rc.1", "2.54.0.windows.1-rc.1", True),
        ("node", "v24.14.0-rc.1", "24.14.0-rc.1", True),
        ("dart", 'Dart SDK version: 3.11.0-2.0.dev (dev) on "windows_x64"', "3.11.0-2.0.dev", True),
        ("gh", "gh version 2.91.0-rc.1 (2026-09-01)", "2.91.0-rc.1", False),
        ("rg", "ripgrep 15.1.0-pre", "15.1.0-pre", False),
        ("pwsh", "7.6.1-preview.1", "7.6.1-preview.1", False),
        ("winget", "v1.29.380-preview.1", "1.29.380-preview.1", False),
    ],
)
def test_prerelease_version_token_cannot_pass_as_a_pinned_stable_version(
    workstation_sandbox, tool, prerelease_output, complete_version, required,
):
    _, _, run = workstation_sandbox
    result, _ = run("-AsJson", version_outputs={tool: prerelease_output})
    assert result.returncode == (1 if required else 0), result.stdout + result.stderr
    report = _report(result)
    check = _check(report, tool)
    assert check["actual"] == complete_version
    assert check["status"] == ("fail" if required else "advisory")
    assert report["status"] == ("fail" if required else "pass")


@pytest.mark.parametrize("tool", ["uv", "git", "node", "dart"])
def test_missing_required_command_cannot_be_masked_by_host_tools(workstation_sandbox, tool):
    _, _, run = workstation_sandbox
    result, calls = run("-AsJson", missing=(tool,))
    assert result.returncode != 0
    check = _check(_report(result), tool)
    assert check["required"] is True and check["status"] == "fail"
    assert check["actual"] == "missing"
    assert not any(call["tool"] == tool for call in calls)


def test_missing_discovered_python_does_not_use_global_python(workstation_sandbox):
    repo, _, run = workstation_sandbox
    result, calls = run("-AsJson", explicit_python=False, discovered_python=str(repo / "absent python.exe"))
    assert result.returncode != 0
    assert _check(_report(result), "python")["actual"] == "missing"
    assert not any(call["tool"] == "python" for call in calls)


@pytest.mark.parametrize("tool", ["python", "uv", "node", "dart"])
def test_native_failure_is_not_accepted_even_with_matching_version_output(workstation_sandbox, tool):
    _, _, run = workstation_sandbox
    result, _ = run("-AsJson", failures={tool: 35})
    assert result.returncode != 0
    check = _check(_report(result), tool)
    assert check["status"] == "fail" and check["actual"] == "unverified"


def test_optional_missing_or_different_tools_are_advisory(workstation_sandbox):
    _, _, run = workstation_sandbox
    result, calls = run("-AsJson", missing=("gh", "rg"), version_outputs={"pwsh": "PowerShell 7.6.5", "winget": "v1.5.0"})
    assert result.returncode == 0, result.stdout + result.stderr
    report = _report(result)
    assert report["status"] == "pass"
    for name in ("gh", "rg", "pwsh", "winget"):
        check = _check(report, name)
        assert check["required"] is False and check["status"] == "advisory"
    assert not any(call["tool"] in ("gh", "rg") for call in calls)


def test_explicit_dart_sdk_bypasses_broken_path_launcher(workstation_sandbox):
    _, tools, run = workstation_sandbox
    result, calls = run("-AsJson", "-DartExecutable", str(tools / "direct SDK/direct-dart.exe"), failures={"dart-wrapper": 255})
    assert result.returncode == 0, result.stdout + result.stderr
    assert _check(_report(result), "dart")["actual"] == "3.11.0"
    assert not any(call["tool"] == "dart-wrapper" for call in calls)
    assert all(call["args"] == ["--version"] for call in calls if call["tool"] == "direct-dart")


def test_automatic_dart_discovery_never_runs_a_launcher_that_could_update_an_sdk(workstation_sandbox):
    _, _, run = workstation_sandbox
    result, calls = run("-AsJson", explicit_dart=False)
    assert result.returncode != 0
    assert _check(_report(result), "dart")["status"] == "fail"
    assert not any(call["tool"] == "dart-wrapper" for call in calls)


def test_explicit_dart_batch_launcher_is_not_run(workstation_sandbox):
    _, tools, run = workstation_sandbox
    result, calls = run("-AsJson", "-DartExecutable", str(tools / "dart.cmd"))
    assert result.returncode != 0
    assert _check(_report(result), "dart")["status"] == "fail"
    assert not any(call["tool"] == "dart-wrapper" for call in calls)


@pytest.mark.parametrize("placement", ["dart.exe", "cache/dart-sdk/bin/dart.exe"])
def test_default_dart_batch_launcher_uses_existing_direct_sdk_only(workstation_sandbox, placement):
    _, tools, run = workstation_sandbox
    direct_sdk = tools / placement
    direct_sdk.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(tools / "direct SDK/dart.exe", direct_sdk)
    result, calls = run("-AsJson", explicit_dart=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert _check(_report(result), "dart")["actual"] == "3.11.0"
    assert any(call["tool"] == "dart" for call in calls)
    assert not any(call["tool"] == "dart-wrapper" for call in calls)


@pytest.mark.parametrize("mutation", ["latest", "version", "module", "unsupported-setting", "string-latest", "string-prerelease", "package-identity"])
def test_winget_configuration_cannot_drift_to_upgrades_or_unsupported_settings(workstation_sandbox, mutation):
    repo, _, run = workstation_sandbox
    path = repo / "config/dev-workstation.winget"
    configuration = json.loads(path.read_text(encoding="utf-8"))
    resource = configuration["properties"]["resources"][0]
    if mutation == "latest":
        resource["settings"]["UseLatest"] = True
    elif mutation == "version":
        resource["settings"]["Version"] = "2.55.0"
    elif mutation == "module":
        resource["directives"]["version"] = "9.0.0"
    elif mutation == "string-latest":
        resource["settings"]["UseLatest"] = "false"
    elif mutation == "string-prerelease":
        resource["directives"]["allowPrerelease"] = "false"
    elif mutation == "package-identity":
        # Updating both files together must not authorize a different machine tool.
        resource["settings"]["Id"] = "Unapproved.Package"
        baseline_path = repo / "config/dev-workstation.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline["packages"][0]["id"] = "Unapproved.Package"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    else:
        resource["settings"]["Scope"] = "user"
    path.write_text(json.dumps(configuration), encoding="utf-8")
    result, calls = run("-AsJson")
    assert result.returncode != 0
    assert _check(_report(result), "configuration")["status"] == "fail"
    assert calls == []


def test_changed_uv_pin_requires_an_explicit_upgrade_review(workstation_sandbox):
    repo, _, run = workstation_sandbox
    path = repo / "pyproject.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('required-version = "==0.12.20"', 'required-version = "==0.13.0"'), encoding="utf-8")
    result, calls = run("-ConfigurationOnly", "-AsJson")
    assert result.returncode != 0
    assert _check(_report(result), "configuration")["status"] == "fail"
    assert calls == []
