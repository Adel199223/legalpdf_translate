"""Coverage, failure and isolation contracts for the offline pytest runner."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tooling import test_shards as shards


def nodes_for(*names):
    return [f"tests/{name}.py::test_{case}" for name in names for case in ("a", "b")]


@pytest.mark.parametrize("count", [1, 2, 4])
def test_partition_covers_every_collected_case_once_and_preserves_file_order(count):
    nodes = nodes_for("test_b", "test_a", "test_c", "test_new")
    plan = shards.make_plan(nodes, count, {"tests/test_b.py": 20, "tests/test_a.py": 3})
    assigned = [node for shard in plan["shards"] for node in shard["node_ids"]]
    assert sorted(assigned) == sorted(nodes) and len(assigned) == len(set(assigned))
    for name in {shards.test_file(node) for node in nodes}:
        owners = [part for part in plan["shards"] if name in part["files"]]
        assert len(owners) == 1
        assert [node for node in owners[0]["node_ids"] if shards.test_file(node) == name] == [
            node for node in nodes if shards.test_file(node) == name]
    assert shards.make_plan(nodes, count, {"tests/test_a.py": 3, "tests/test_b.py": 20}) == plan


def test_new_files_are_automatically_assigned_with_a_positive_estimated_weight():
    nodes = nodes_for("test_old", "test_added")
    plan = shards.make_plan(nodes, 2, {"tests/test_old.py": 12, "tests/test_removed.py": 70})
    assert plan["file_weights"]["tests/test_added.py"] == 12
    assert "tests/test_removed.py" not in plan["file_weights"]
    assert all(part["node_ids"] for part in plan["shards"])


def test_qt_family_and_honorarios_remain_on_one_worker_including_new_qt_files():
    nodes = nodes_for("test_qt_app_state", "test_qt_new_window", "test_honorarios_docx",
                      "test_plain_a", "test_plain_b", "test_plain_c")
    plan = shards.make_plan(nodes, 4)
    owners = {part["index"] for part in plan["shards"] for name in part["files"]
              if "test_qt_" in name or "honorarios" in name}
    assert len(owners) == 1
    assert all(part["node_ids"] for part in plan["shards"])


@pytest.mark.parametrize("weight", [0, -1, float("inf"), float("nan"), True, "2"])
def test_invalid_timing_weights_fail_closed(weight):
    with pytest.raises(ValueError, match="finite positive"):
        shards.make_plan(nodes_for("test_a"), timings={"tests/test_a.py": weight})


@pytest.mark.parametrize("nodes", [[], ["tests/test_a.py::test_a"] * 2,
                                    ["../outside.py::test_a"], ["C:/outside.py::test_a"]])
def test_invalid_collections_cannot_form_a_plan(nodes):
    with pytest.raises(ValueError):
        shards.make_plan(nodes)


def fictional_repo(path):
    path.mkdir()
    (path / "tests").mkdir()
    (path / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    return path


def run_cli(repo, output, *options, pytest_args=()):
    result = subprocess.run([sys.executable, "-B", str(shards.SCRIPT), "run", "--repo", str(repo),
                             "--output", str(output), *options, "--", *(pytest_args or ["tests"])],
                            cwd=repo, capture_output=True, text=True, timeout=60)
    return result, shards.read_json(output / "result.json")


@pytest.fixture(scope="module")
def successful_run(tmp_path_factory):
    base = tmp_path_factory.mktemp("test-shard-contract")
    repo = fictional_repo(base / "repo")
    for name in ("a", "b"):
        (repo / "tests" / f"test_{name}.py").write_text(
            "import os\nfrom pathlib import Path\nimport pytest\n"
            "def test_environment():\n"
            "    assert os.environ['TEMP'] == os.environ['TMP']\n"
            "    assert os.environ['APPDATA'] != os.environ['LOCALAPPDATA']\n"
            "    assert Path(os.environ['APPDATA']).is_dir()\n"
            "    Path(os.environ['TEMP'], 'owned.txt').write_text(str(os.getpid()))\n"
            "def test_pass():\n    assert 2 + 2 == 4\n"
            "def test_skip():\n    pytest.skip('fictional optional platform')\n", encoding="utf-8")
    result, receipt = run_cli(repo, base / "run", "--workers", "2")
    assert result.returncode == 0, result.stderr
    assert receipt["status"] == "passed"
    return base / "run"


def test_real_workers_execute_exhaustive_scope_with_isolated_roots_and_junit(successful_run):
    receipt = shards.verify_results([successful_run / "result.json"])
    assert receipt["tests"] == 6 and receipt["shards"] == 2
    pids = []
    for index in (0, 1):
        folder = successful_run / f"worker-{index}"
        execution_root = Path(shards.read_json(folder / "request.json")["execution_root"])
        pids.append((execution_root / "temp" / "owned.txt").read_text())
        assert successful_run not in execution_root.parents
        assert shards.junit_summary(folder / "junit.xml")["skipped"] == 1
        execution = shards.read_json(folder / "execution.json")
        assert len(execution["executed_node_ids"]) == 3
        assert all(phase["seconds"] >= 0 for phase in execution["phases"])
    assert pids[0] != pids[1]


@pytest.mark.parametrize("mutation", ["missing_worker", "duplicate_worker", "missing_execution",
                                       "wrong_collection", "junit_changed", "skipped", "cancelled", "failed"])
def test_gate_rejects_missing_duplicate_or_changed_execution_evidence(successful_run, tmp_path, mutation):
    root = tmp_path / "downloaded"
    root.mkdir()
    # Deliberately copy only the public artifact allowlist, not original paths,
    # request files, temporary app data or fixture outputs.
    for name in ("plan.json", "result.json"):
        shutil.copy2(successful_run / name, root / name)
    for index in (0, 1):
        target = root / f"worker-{index}"
        target.mkdir()
        for name in ("execution.json", "junit.xml"):
            shutil.copy2(successful_run / f"worker-{index}" / name, target / name)
    result = shards.read_json(root / "result.json")
    assert shards.verify_results([root / "result.json"])["tests"] == 6
    if mutation == "missing_worker":
        result["workers"].pop()
    elif mutation == "duplicate_worker":
        result["workers"].append(result["workers"][0])
    elif mutation in ("skipped", "cancelled", "failed"):
        result["status"] = mutation
    else:
        path = root / "worker-0" / "execution.json"
        execution = shards.read_json(path)
        if mutation == "missing_execution":
            execution["executed_node_ids"].pop()
        elif mutation == "wrong_collection":
            execution["collection_sha256"] = "wrong"
        else:
            (root / "worker-0" / "junit.xml").write_text("<testsuites/>", encoding="utf-8")
        shards.write_json(path, execution)
    shards.write_json(root / "result.json", result)
    with pytest.raises(ValueError):
        shards.verify_results([root / "result.json"])


@pytest.mark.parametrize("body, expected", [("def test_bad():\n    assert False\n", 1), ("", 5)])
def test_pytest_failure_and_no_tests_exit_codes_are_not_hidden(tmp_path, body, expected):
    repo = fictional_repo(tmp_path / "repo")
    (repo / "tests" / "test_case.py").write_text(body, encoding="utf-8")
    result, receipt = run_cli(repo, tmp_path / "run")
    assert result.returncode == expected
    assert receipt["exit_code"] == expected
    assert receipt["status"] != "passed"


def test_selection_filter_and_order_survive_collection_and_execution(tmp_path):
    repo = fictional_repo(tmp_path / "repo")
    (repo / "tests" / "test_case.py").write_text(
        "def test_keep_second():\n    pass\ndef test_omit():\n    assert False\n"
        "def test_keep_first():\n    pass\n", encoding="utf-8")
    result, _ = run_cli(repo, tmp_path / "run", pytest_args=["tests/test_case.py", "-k", "keep"])
    assert result.returncode == 0, result.stderr
    plan = shards.read_json(tmp_path / "run" / "plan.json")
    assert plan["node_ids"] == ["tests/test_case.py::test_keep_second", "tests/test_case.py::test_keep_first"]
    assert shards.verify_results([tmp_path / "run" / "result.json"])["tests"] == 2


@pytest.mark.parametrize("platform", [None, "offscreen", "minimal"])
def test_real_child_preserves_callers_qt_platform(tmp_path, monkeypatch, platform):
    repo = fictional_repo(tmp_path / "repo")
    monkeypatch.delenv("QT_QPA_FONTDIR", raising=False)
    if platform is None:
        monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    else:
        monkeypatch.setenv("QT_QPA_PLATFORM", platform)
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    expected_fonts = str(fonts) if os.name == "nt" and platform == "offscreen" and fonts.is_dir() else None
    (repo / "tests" / "test_environment.py").write_text(
        "import os\n"
        "def test_environment():\n"
        f"    assert os.environ.get('QT_QPA_PLATFORM') == {platform!r}\n"
        f"    assert os.environ.get('QT_QPA_FONTDIR') == {expected_fonts!r}\n", encoding="utf-8")
    result, receipt = run_cli(repo, tmp_path / "run")
    assert result.returncode == 0, result.stderr
    assert receipt["status"] == "passed"


def test_worker_exit_five_is_propagated_after_successful_collection(tmp_path):
    repo = fictional_repo(tmp_path / "repo")
    (repo / "conftest.py").write_text(
        "import pytest\n"
        "def pytest_runtestloop(session):\n"
        "    if not session.config.option.collectonly:\n"
        "        pytest.exit('fictional runner stops', returncode=5)\n", encoding="utf-8")
    (repo / "tests" / "test_case.py").write_text("def test_case():\n    pass\n", encoding="utf-8")
    result, receipt = run_cli(repo, tmp_path / "run")
    assert result.returncode == 5
    assert receipt["workers"][0]["exit_code"] == 5


def test_planning_error_retains_terminal_infrastructure_receipt(tmp_path):
    repo = fictional_repo(tmp_path / "repo")
    (repo / "tests" / "test_case.py").write_text("def test_case():\n    pass\n", encoding="utf-8")
    result, receipt = run_cli(repo, tmp_path / "run", "--workers", "4")
    assert result.returncode == 1
    assert receipt["status"] == "infrastructure_failed" and receipt["error_class"] == "ValueError"


def test_collection_drift_fails_before_test_body(tmp_path):
    repo = fictional_repo(tmp_path / "repo")
    (repo / "conftest.py").write_text(
        "from pathlib import Path\n"
        "def pytest_collection_modifyitems(items):\n"
        "    marker = Path(__file__).parent / 'collected'\n"
        "    if marker.exists():\n        items[0]._nodeid += '-changed'\n"
        "    marker.write_text('yes')\n", encoding="utf-8")
    (repo / "tests" / "test_case.py").write_text(
        "def test_never_runs():\n    raise AssertionError('body must not execute')\n", encoding="utf-8")
    result, receipt = run_cli(repo, tmp_path / "run")
    assert result.returncode != 0 and receipt["status"] == "failed"
    execution = shards.read_json(tmp_path / "run" / "worker-0" / "execution.json")
    assert execution["executed_node_ids"] == []


def test_existing_output_is_never_overwritten(tmp_path):
    output = tmp_path / "retained"
    output.mkdir()
    (output / "result.json").write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        shards.run_suite(tmp_path, output, [])
    assert (output / "result.json").read_text() == "original"


def test_independent_ci_shards_reconcile_using_only_relative_artifact_paths(tmp_path):
    repo = fictional_repo(tmp_path / "repo")
    for index in range(4):
        (repo / "tests" / f"test_file_{index}.py").write_text("def test_case():\n    pass\n", encoding="utf-8")
    paths = []
    for index in range(4):
        root = tmp_path / f"shard-{index}"
        result, _ = run_cli(repo, root, "--shard-count", "4", "--shard-index", str(index))
        assert result.returncode == 0, result.stderr
        paths.append(root / "result.json")
    result = shards.verify_results(paths)
    assert result["tests"] == 4 and result["shards"] == 4
    with pytest.raises(ValueError, match="exhaustive"):
        shards.verify_results(paths[:3])


def test_windows_cleanup_targets_only_still_running_owned_pids_and_reaps_all(monkeypatch):
    killed, waited = [], []

    class Child:
        def __init__(self, pid, code):
            self.pid, self.code = pid, code
        def poll(self):
            return self.code
        def wait(self, timeout):
            waited.append(self.pid)
            return 0

    monkeypatch.setattr(shards, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(shards.subprocess, "run", lambda command, **kwargs: killed.append(command))
    shards.stop_owned([Child(123, None), Child(456, 0)])
    assert killed == [["taskkill", "/PID", "123", "/T", "/F"]]
    assert waited == [123, 456]


def test_interrupt_cleans_only_processes_owned_by_the_current_launch(tmp_path, monkeypatch):
    made, stopped = [], []

    class Child:
        def __init__(self, *args, **kwargs):
            self.returncode = None
            made.append(self)
        def poll(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(shards.subprocess, "Popen", Child)
    monkeypatch.setattr(shards, "stop_owned", lambda children: stopped.extend(children))
    with pytest.raises(KeyboardInterrupt):
        shards.launch_requests([({"execution_root": str(tmp_path / "run-one")}, tmp_path / "one"),
                                ({"execution_root": str(tmp_path / "run-two")}, tmp_path / "two")], tmp_path)
    assert len(made) == 2 and stopped == made
