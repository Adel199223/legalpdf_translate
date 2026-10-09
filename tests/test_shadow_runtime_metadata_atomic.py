from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Barrier, Lock

import pytest

import legalpdf_translate.shadow_runtime as runtime


def test_concurrent_metadata_writers_use_distinct_closed_temporary_files(tmp_path, monkeypatch):
    destination = tmp_path / "shadow_runtime.json"
    unrelated = tmp_path / "shadow_runtime.tmp"
    unrelated.write_bytes(b"unrelated")
    barrier = Barrier(2)
    original = Path.replace
    temporary_paths = []
    first_attempts = set()
    coordination_lock = Lock()

    def coordinated(source, target):
        temporary_paths.append(source)
        # Reopening for exclusive replacement is exercised by the real Windows operation.
        assert json.loads(source.read_text()) in ({"writer": 1}, {"writer": 2})
        with coordination_lock:
            first = source not in first_attempts
            first_attempts.add(source)
        if first:
            barrier.wait(timeout=5)
        return original(source, target)

    monkeypatch.setattr(Path, "replace", coordinated)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(runtime.write_shadow_runtime_metadata, destination, {"writer": i}) for i in (1, 2)]
        assert all(f.result(timeout=10) == destination for f in futures)
    assert len(set(temporary_paths)) == 2
    assert json.loads(destination.read_text()) in ({"writer": 1}, {"writer": 2})
    assert unrelated.read_bytes() == b"unrelated"
    assert list(tmp_path.glob("*.tmp")) == [unrelated]


def test_metadata_replace_retries_only_transient_permission_denial(tmp_path, monkeypatch):
    destination = tmp_path / "shadow_runtime.json"
    original = Path.replace
    attempts = []
    sleeps = []

    def replace(source, target):
        attempts.append(source)
        if len(attempts) == 1:
            raise PermissionError("reader briefly holds destination")
        return original(source, target)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.setattr(runtime.time, "sleep", sleeps.append)
    runtime.write_shadow_runtime_metadata(destination, {"value": "complete"})
    assert len(attempts) == 2 and attempts[0] == attempts[1]
    assert sleeps == [0.05]
    assert json.loads(destination.read_text()) == {"value": "complete"}
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("error", [PermissionError("persistent denial"), OSError("other failure")])
def test_metadata_failure_preserves_exception_destination_and_unrelated_file(tmp_path, monkeypatch, error):
    destination = tmp_path / "shadow_runtime.json"
    destination.write_bytes(b'{"old":true}')
    unrelated = tmp_path / "unrelated.tmp"
    unrelated.write_bytes(b"keep")
    attempts = []
    sleeps = []

    def deny(source, target):
        attempts.append(source)
        raise error

    monkeypatch.setattr(Path, "replace", deny)
    monkeypatch.setattr(runtime.time, "sleep", sleeps.append)
    with pytest.raises(type(error)) as captured:
        runtime.write_shadow_runtime_metadata(destination, {"new": True})
    assert captured.value is error
    assert len(attempts) == (5 if isinstance(error, PermissionError) else 1)
    assert sleeps == ([0.05] * 4 if isinstance(error, PermissionError) else [])
    assert destination.read_bytes() == b'{"old":true}'
    assert unrelated.read_bytes() == b"keep"
    assert list(tmp_path.glob("*.tmp")) == [unrelated]
