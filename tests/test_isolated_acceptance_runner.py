"""Pure decisions only; never install an audit hook into the test host."""
import os
from pathlib import Path

import pytest

from tooling.run_isolated_acceptance_tests import (
    OfflineBoundary, OfflineBoundaryDenied, isolated_import_paths,
)


@pytest.fixture
def boundary(tmp_path):
    root = tmp_path / "fixture"
    root.mkdir()
    return OfflineBoundary(read_roots=(tmp_path / "readable",), write_root=root)


@pytest.mark.parametrize("event,args", [
    ("socket.connect", (None, ("example.invalid", 443))),
    ("socket.getaddrinfo", ("example.invalid", 443)),
    ("socket.bind", (None, ("127.0.0.1", 0))),
    ("socket.sendto", (None, ("example.invalid", 443))),
    ("subprocess.Popen", ("not-executed",)),
    ("os.system", ("not-executed",)),
    ("os.startfile", ("not-opened.docx",)),
    ("winreg.OpenKey", (None, "not-opened")),
    ("import", ("pythoncom",)),
    ("import", ("win32com.client",)),
])
def test_prohibited_events_are_rejected_without_performing_them(boundary, event, args):
    with pytest.raises(OfflineBoundaryDenied):
        boundary.check(event, args)
    assert sum(boundary.denials.values()) == 1


def test_read_roots_do_not_become_write_roots(boundary, tmp_path):
    readable = str(tmp_path / "readable" / "code.py")
    boundary.check("open", (readable, "r", os.O_RDONLY))
    with pytest.raises(OfflineBoundaryDenied, match="write_outside_fixture"):
        boundary.check("open", (readable, "w", os.O_CREAT | os.O_WRONLY))


@pytest.mark.parametrize("mode,flags", [("w", 0), ("a", 0), ("r+", 0), (None, os.O_RDWR)])
def test_all_write_modes_are_bounded(boundary, tmp_path, mode, flags):
    with pytest.raises(OfflineBoundaryDenied, match="write_outside_fixture"):
        boundary.check("open", (str(tmp_path / "outside"), mode, flags))


def test_fixture_reads_writes_and_owned_numeric_capture_are_allowed(boundary):
    path = str(boundary.write_root / "new.json")
    boundary.check("open", (path, "w", os.O_CREAT | os.O_WRONLY))
    boundary.check("open", (path, "r", os.O_RDONLY))
    boundary.check("open", (7, "r", os.O_RDONLY))
    assert not boundary.denials


def test_paths_cannot_escape_by_parent_or_sibling_prefix(boundary, tmp_path):
    for path in (boundary.write_root / ".." / "outside",
                 Path(str(boundary.write_root) + "_sibling") / "new"):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("open", (str(path), "w", os.O_CREAT))
    with pytest.raises(OfflineBoundaryDenied, match="read_outside_scope"):
        boundary.check("open", (str(tmp_path / "private"), "r", 0))


def test_move_checks_both_endpoints(boundary, tmp_path):
    owned = str(boundary.write_root / "a")
    outside = str(tmp_path / "outside")
    for pair in ((owned, outside), (outside, owned)):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("os.rename", pair)
    boundary.check("os.rename", (owned, str(boundary.write_root / "b")))


def test_directory_mutation_and_enumeration_stay_scoped(boundary, tmp_path):
    with pytest.raises(OfflineBoundaryDenied):
        boundary.check("os.remove", (str(tmp_path / "private"),))
    with pytest.raises(OfflineBoundaryDenied):
        boundary.check("os.scandir", (str(tmp_path / "private"),))
    boundary.check("os.mkdir", (str(boundary.write_root / "nested"),))


@pytest.mark.parametrize("event,args", [
    ("os.remove", ("a", 5)),
    ("os.mkdir", ("a", 0o700, 5)),
    ("os.rename", ("a", "b", -1, 5)),
    ("os.symlink", ("a", "b", 5)),
])
def test_descriptor_relative_mutations_are_not_resolved_against_cwd(boundary, event, args):
    with pytest.raises(OfflineBoundaryDenied, match="descriptor_relative_mutation"):
        boundary.check(event, args)


def test_ambient_env_files_are_not_read_even_under_a_read_root(boundary, tmp_path):
    with pytest.raises(OfflineBoundaryDenied, match="ambient_env_file"):
        boundary.check("open", (str(tmp_path / "readable" / ".env.local"), "r", 0))


def test_only_exact_null_device_opens_are_allowed_for_capture(boundary):
    boundary.check("open", (os.devnull, "r+", os.O_RDWR))
    with pytest.raises(OfflineBoundaryDenied):
        boundary.check("os.remove", (os.devnull,))


def test_shared_venv_does_not_import_another_editable_checkout(tmp_path):
    canonical = tmp_path / "canonical"
    venv = canonical / ".venv311"
    interpreter = tmp_path / "python"
    feature = tmp_path / "feature"
    selected = isolated_import_paths(
        ["", str(canonical / "src"), str(venv / "Lib"), str(interpreter / "Lib")],
        repository=feature, runtime_roots=(venv, interpreter),
    )
    assert selected == [str(feature / "src"), str(feature),
                        str(venv / "Lib"), str(interpreter / "Lib")]
