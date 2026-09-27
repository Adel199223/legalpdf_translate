"""Bounded formatting reads retain identity and changing-file rejection."""

import os
from pathlib import Path

import pytest

from legalpdf_translate import run_docx_formatting as module


def observe_read(monkeypatch, path, *, phase=None, mutate=None, short_read=False):
    original_open = Path.open
    sizes = []

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            result = self.stream.__exit__(*args)
            if phase == "after_close":
                mutate(original_open)
            return result

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            sizes.append(size)
            if phase == "before_read":
                mutate(original_open)
            raw = self.stream.read(size)
            if phase == "after_read":
                mutate(original_open)
            return raw[:-1] if short_read else raw

    def open_file(current, mode="r", *args, **kwargs):
        if current != path or mode != "rb":
            return original_open(current, mode, *args, **kwargs)
        if phase == "before_open":
            mutate(original_open)
        return Stream(original_open(current, mode, *args, **kwargs))

    monkeypatch.setattr(Path, "open", open_file)
    return sizes


@pytest.mark.parametrize("raw,maximum", [
    (b"", 64_000_000), (b"x", 64_000_000),
    (bytes(range(256)), 64_000_000), (b"exact-limit", 11),
], ids=["empty", "one-byte", "binary", "exact-limit"])
def test_reads_complete_file_using_observed_size_plus_one(tmp_path, monkeypatch, raw, maximum):
    path = tmp_path / "fictional-evidence.bin"
    path.write_bytes(raw)
    sizes = observe_read(monkeypatch, path)
    assert module._read(path, maximum=maximum, within=tmp_path) == raw
    assert sizes == [len(raw) + 1]


def test_known_oversize_fails_before_open_or_allocation(tmp_path, monkeypatch):
    path = tmp_path / "oversized.bin"
    path.write_bytes(b"12345")

    def forbidden_open(_original):
        pytest.fail("Known oversized evidence must not be opened")

    sizes = observe_read(monkeypatch, path, phase="before_open", mutate=forbidden_open)
    with pytest.raises(module.RunDocxFormattingError, match="^run_formatting_file_too_large$"):
        module._read(path, maximum=4)
    assert sizes == []


@pytest.mark.parametrize("phase", ["before_open", "before_read", "after_read", "after_close"])
@pytest.mark.parametrize("change", ["grow", "truncate"])
def test_size_races_fail_with_mtime_preserved(tmp_path, monkeypatch, phase, change):
    path = tmp_path / "changing.bin"
    original = b"complete fictional evidence"
    path.write_bytes(original)
    stamp = path.stat()

    def mutate(original_open):
        replacement = original + b" appended" if change == "grow" else original[:3]
        with original_open(path, "wb") as stream:
            stream.write(replacement)
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    sizes = observe_read(monkeypatch, path, phase=phase, mutate=mutate)
    with pytest.raises(module.RunDocxFormattingError, match="^run_formatting_file_changed_during_read$"):
        module._read(path, maximum=len(original))
    assert sizes == [len(original) + 1]


@pytest.mark.parametrize("phase", ["before_open", "after_close"])
def test_same_size_replacement_preserves_inode_guard(tmp_path, monkeypatch, phase):
    path, replacement = tmp_path / "evidence.bin", tmp_path / "replacement.bin"
    raw = b"same exact bytes"
    path.write_bytes(raw)
    replacement.write_bytes(raw)
    stamp = path.stat()
    os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert replacement.stat().st_ino != stamp.st_ino
    observe_read(monkeypatch, path, phase=phase, mutate=lambda _original: os.replace(replacement, path))
    with pytest.raises(module.RunDocxFormattingError, match="^run_formatting_file_changed_during_read$"):
        module._read(path)


def test_short_read_is_rejected_even_when_metadata_is_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "short.bin"
    path.write_bytes(b"complete evidence")
    stamp = path.stat()
    observe_read(monkeypatch, path, short_read=True)
    with pytest.raises(module.RunDocxFormattingError, match="^run_formatting_file_changed_during_read$"):
        module._read(path)
    now = path.stat()
    assert (now.st_ino, now.st_size, now.st_mtime_ns, now.st_ctime_ns) == (
        stamp.st_ino, stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns)


def test_next_read_returns_fresh_bytes_without_a_cache(tmp_path):
    path = tmp_path / "fresh.bin"
    path.write_bytes(b"first")
    stamp = path.stat()
    assert module._read(path) == b"first"
    path.write_bytes(b"later")
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert module._read(path) == b"later"


def test_existing_owner_boundary_is_retained(tmp_path):
    owned = tmp_path / "owned"
    owned.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"fictional foreign bytes")
    with pytest.raises(module.RunDocxFormattingError, match="^run_formatting_path_outside_owner$"):
        module._read(outside, within=owned)
