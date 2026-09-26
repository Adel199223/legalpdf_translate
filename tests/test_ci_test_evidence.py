"""Fictional artifact fixtures exercise retry selection and the actual verifier."""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from tooling import ci_test_evidence as evidence
from tooling import test_shards


def artifact(root, index, attempt=1, *, state="passed", count=4, nodes=None):
    nodes = nodes or [f"tests/test_file_{number}.py::test_case" for number in range(count)]
    plan = test_shards.make_plan(nodes, count)
    folder = root / f"pytest-shard-{index}-attempt-{attempt}"
    worker = folder / f"worker-{index}"
    worker.mkdir(parents=True)
    assigned = plan["shards"][index]["node_ids"]
    test_shards.write_json(folder / "plan.json", plan)
    test_shards.write_json(worker / "execution.json", {
        "exit_code": 0 if state == "passed" else 1, "collection_sha256": plan["collection_sha256"],
        "executed_node_ids": assigned})
    (worker / "junit.xml").write_text("<testsuites><testsuite>" + "".join(
        f'<testcase classname="fictional" name="case-{i}"/>' for i, _ in enumerate(assigned)
    ) + "</testsuite></testsuites>", encoding="utf-8")
    test_shards.write_json(folder / "result.json", {
        "status": state, "exit_code": 0 if state == "passed" else 1,
        "collection_sha256": plan["collection_sha256"], "plan_sha256": test_shards.digest(plan),
        "workers": [{"index": index, "directory": worker.name, "exit_code": 0 if state == "passed" else 1,
                     "junit": test_shards.junit_summary(worker / "junit.xml")}]})
    return folder


def complete_run(root):
    return [artifact(root, index) for index in range(4)]


def hashes(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def test_mixed_attempts_reconcile_a_failed_jobs_only_rerun_and_preserve_history(tmp_path):
    root = tmp_path / "artifacts"
    for index in range(4):
        artifact(root, index, state="failed" if index == 1 else "passed")
    artifact(root, 1, 2)
    artifact(root, 3, 10)
    before = hashes(root)
    result = evidence.verify_artifacts(root, tmp_path / "verified")
    assert result["status"] == "passed" and result["tests"] == 4
    assert [item["attempt"] for item in result["selected_artifacts"]] == [1, 2, 1, 10]
    assert hashes(root) == before


@pytest.mark.parametrize("state", ["failed", "cancelled", "skipped"])
def test_latest_unsuccessful_attempt_never_falls_back_to_an_older_pass(tmp_path, state):
    root = tmp_path / "artifacts"
    complete_run(root)
    artifact(root, 2, 2, state=state)
    with pytest.raises(ValueError, match="did not pass"):
        evidence.verify_artifacts(root, tmp_path / "verified")
    result = test_shards.read_json(tmp_path / "verified" / "verification.json")
    assert result["status"] == "failed"
    assert test_shards.read_json(tmp_path / "verified" / "selection.json")["shards"][2]["attempt"] == 2


@pytest.mark.parametrize("missing", ["shard", "receipt", "latest_receipt"])
def test_missing_shard_or_selected_receipt_refuses_verification(tmp_path, missing):
    root = tmp_path / "artifacts"
    for index in range(3 if missing == "shard" else 4):
        artifact(root, index)
    if missing == "receipt":
        (root / "pytest-shard-3-attempt-1" / "result.json").unlink()
    elif missing == "latest_receipt":
        (root / "pytest-shard-3-attempt-2").mkdir()
    with pytest.raises(ValueError, match="missing"):
        evidence.verify_artifacts(root, tmp_path / "verified")


@pytest.mark.parametrize("name", ["pytest-shard-4-attempt-1", "pytest-shard-0-attempt-0",
                                  "pytest-shard-0-attempt--1", "pytest-shard-0-attempt-x",
                                  "pytest-shard-0-attempt-1-extra", "pytest-shard-0"])
def test_malformed_matching_artifacts_fail_closed(tmp_path, name):
    complete_run(tmp_path)
    (tmp_path / name).mkdir()
    with pytest.raises(ValueError, match="Malformed"):
        evidence.select_artifacts(tmp_path)


def test_duplicate_integer_attempt_is_not_silently_selected(tmp_path):
    complete_run(tmp_path)
    artifact(tmp_path, 0, "01")
    with pytest.raises(ValueError, match="Duplicate"):
        evidence.select_artifacts(tmp_path)


def test_unrelated_artifacts_are_ignored_and_matching_files_are_rejected(tmp_path):
    complete_run(tmp_path)
    (tmp_path / "validator-report").mkdir()
    assert len(evidence.select_artifacts(tmp_path)) == 4
    (tmp_path / "pytest-shard-0-attempt-2").write_text("not a directory", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed"):
        evidence.select_artifacts(tmp_path)


def test_two_shard_plan_cannot_masquerade_as_four_artifacts(tmp_path):
    root = tmp_path / "artifacts"
    complete_run(root)
    target = root / "pytest-shard-0-attempt-1" / "plan.json"
    test_shards.write_json(target, test_shards.make_plan(["tests/a.py::test_a", "tests/b.py::test_b"], 2))
    with pytest.raises(ValueError, match="four-shard"):
        evidence.verify_artifacts(root, tmp_path / "verified")


def test_artifact_shard_name_must_match_its_only_worker(tmp_path):
    root = tmp_path / "artifacts"
    complete_run(root)
    target = root / "pytest-shard-0-attempt-1" / "result.json"
    result = test_shards.read_json(target)
    result["workers"][0]["index"] = 1
    test_shards.write_json(target, result)
    with pytest.raises(ValueError, match="sole worker"):
        evidence.verify_artifacts(root, tmp_path / "verified")


def test_differing_latest_collection_cannot_merge_with_previous_shards(tmp_path):
    root = tmp_path / "artifacts"
    complete_run(root)
    artifact(root, 2, 2, nodes=[f"tests/test_new_{number}.py::test_case" for number in range(4)])
    with pytest.raises(ValueError, match="same tests"):
        evidence.verify_artifacts(root, tmp_path / "verified")


def test_existing_verification_is_never_overwritten(tmp_path):
    output = tmp_path / "verified"
    output.mkdir()
    receipt = output / "verification.json"
    receipt.write_text("previous", encoding="utf-8")
    with pytest.raises(FileExistsError):
        evidence.verify_artifacts(tmp_path, output)
    assert receipt.read_text() == "previous"


def test_cli_verifies_with_standard_library_only(tmp_path):
    root = tmp_path / "artifacts"
    complete_run(root)
    result = subprocess.run([sys.executable, "-S", "-B", str(Path(evidence.__file__).resolve()),
                             "--artifacts", str(root), "--output", str(tmp_path / "verified")],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "Verified 4 tests across four shards" in result.stdout
