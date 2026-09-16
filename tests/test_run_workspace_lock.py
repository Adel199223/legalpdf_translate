"""Synthetic OS exclusion tests; no translation or native application calls."""
from concurrent.futures import ThreadPoolExecutor

import pytest

from legalpdf_translate.run_workspace_lock import RunWorkspaceBusy, run_workspace_slot


def test_same_thread_nesting_retains_lock_until_outer_exit(tmp_path):
    root = tmp_path / "run"
    with run_workspace_slot(root, create=True):
        with run_workspace_slot(root):
            pass
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(RunWorkspaceBusy):
                pool.submit(lambda: enter_once(root)).result(timeout=5)
    assert enter_once(root) == root
    assert (root / ".run_workspace.lock").is_file()


def enter_once(root):
    with run_workspace_slot(root) as resolved:
        return resolved


def test_unrelated_run_directories_are_not_globally_serialized(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    second.mkdir()
    with run_workspace_slot(first, create=True):
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(enter_once, second).result(timeout=5) == second


def test_exception_releases_the_os_lock_and_reentrant_owner(tmp_path):
    with pytest.raises(RuntimeError, match="synthetic"):
        with run_workspace_slot(tmp_path):
            with run_workspace_slot(tmp_path):
                raise RuntimeError("synthetic failure")
    with ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(enter_once, tmp_path).result(timeout=5) == tmp_path


def test_lock_file_is_not_a_deletable_stale_activity_flag(tmp_path):
    path = tmp_path / ".run_workspace.lock"
    path.write_bytes(b"0")
    before = path.stat().st_ino
    assert enter_once(tmp_path) == tmp_path
    assert path.read_bytes() == b"0" and path.stat().st_ino == before


def test_directory_cannot_stand_in_for_lock_file(tmp_path):
    (tmp_path / ".run_workspace.lock").mkdir()
    with pytest.raises(ValueError, match="regular file"):
        enter_once(tmp_path)


def test_lock_path_cannot_redirect_to_another_file(tmp_path):
    target = tmp_path / "retained.txt"
    target.write_bytes(b"retained")
    link = tmp_path / ".run_workspace.lock"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Host does not permit synthetic symbolic links.")
    with pytest.raises(ValueError, match="regular file"):
        enter_once(tmp_path)
    assert target.read_bytes() == b"retained"
