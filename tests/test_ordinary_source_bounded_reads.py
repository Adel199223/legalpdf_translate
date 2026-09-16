"""Exact source reads without allocating the maximum permitted file size.

The races are deterministic file operations at real reader boundaries. No
timing sleeps, persistent cache, providers or native extraction are involved.
"""
import hashlib
import os
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_source_review_service as module
from tests.test_ordinary_source_review_service import (
    RAW_TXT, config_case, local_only, local_pass,
)


def observe_read(monkeypatch, path, *, before_open=None, before_read=None,
                 after_read=None, short_read=False):
    original_open = Path.open
    sizes = []

    class Stream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, size):
            sizes.append(size)
            if before_read:
                before_read(original_open)
            raw = self.stream.read(size)
            if after_read:
                after_read(original_open)
            return raw[:-1] if short_read else raw

    def open_file(current, mode="r", *args, **kwargs):
        if current != path or mode != "rb":
            return original_open(current, mode, *args, **kwargs)
        if before_open:
            before_open(original_open)
        return Stream(original_open(current, mode, *args, **kwargs))

    monkeypatch.setattr(Path, "open", open_file)
    return sizes


@pytest.mark.parametrize("raw,maximum", [
    (b"", 8_000_000), (b"x", 64_000_000),
    (bytes(range(256)), 64_000_000), (b"exact-limit", 11),
])
def test_read_allocates_only_file_size_plus_sentinel_and_returns_all_bytes(tmp_path, monkeypatch, raw, maximum):
    path = tmp_path / "evidence.bin"
    path.write_bytes(raw)
    sizes = observe_read(monkeypatch, path)
    assert module._read(path, maximum=maximum) == raw
    assert sizes == [len(raw) + 1]


def test_known_oversize_is_rejected_before_opening_or_allocating(tmp_path, monkeypatch):
    path = tmp_path / "oversize.bin"
    path.write_bytes(b"12345")

    def forbidden_open(_original):
        pytest.fail("An already oversized source must not be opened for a large read")

    sizes = observe_read(monkeypatch, path, before_open=forbidden_open)
    with pytest.raises(module.SourceReviewServiceError, match="^source_review_file_changed_or_too_large$"):
        module._read(path, maximum=4)
    assert sizes == []


@pytest.mark.parametrize("phase", ["before_open", "before_read", "after_read"])
@pytest.mark.parametrize("change", ["grow", "truncate"])
def test_size_changes_across_read_boundaries_fail_closed(tmp_path, monkeypatch, phase, change):
    path = tmp_path / "changing.bin"
    original = b"original bytes"
    path.write_bytes(original)
    stamp = path.stat()

    def mutate(original_open):
        replacement = original + b"extra bytes" if change == "grow" else original[:3]
        with original_open(path, "wb") as stream:
            stream.write(replacement)
        # Even preserving mtime cannot conceal the changed size or short read.
        os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))

    sizes = observe_read(monkeypatch, path, **{phase: mutate})
    with pytest.raises(module.SourceReviewServiceError, match="^source_review_file_changed_or_too_large$"):
        module._read(path, maximum=len(original))
    assert sizes == [len(original) + 1]


@pytest.mark.parametrize("phase", ["before_open", "after_close"])
def test_same_size_and_mtime_replacement_keeps_inode_checks(tmp_path, monkeypatch, phase):
    path = tmp_path / "replaced.bin"
    replacement = tmp_path / "replacement.bin"
    raw = b"same exact bytes"
    path.write_bytes(raw)
    replacement.write_bytes(raw)
    stamp = path.stat()
    os.utime(replacement, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert replacement.stat().st_ino != stamp.st_ino

    def replace_file(_original=None):
        os.replace(replacement, path)

    if phase == "before_open":
        observe_read(monkeypatch, path, before_open=replace_file)
    else:
        original_direct = module._direct
        calls = []

        def direct(current, **kwargs):
            if Path(current) == path:
                calls.append(current)
                if len(calls) == 2:
                    replace_file()
            return original_direct(current, **kwargs)

        monkeypatch.setattr(module, "_direct", direct)
    with pytest.raises(module.SourceReviewServiceError, match="^source_review_file_changed_or_too_large$"):
        module._read(path)


def test_short_read_fails_even_when_file_identity_is_unchanged(tmp_path, monkeypatch):
    path = tmp_path / "short.bin"
    path.write_bytes(b"complete evidence")
    before = path.stat()
    sizes = observe_read(monkeypatch, path, short_read=True)
    with pytest.raises(module.SourceReviewServiceError, match="^source_review_file_changed_or_too_large$"):
        module._read(path)
    after = path.stat()
    assert (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) == (
        after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
    assert sizes == [before.st_size + 1]


def test_source_review_rehashes_fresh_same_size_objects_without_a_cache(tmp_path, monkeypatch):
    local_pass(monkeypatch)
    service = module.OrdinarySourceReviewService(config_case(tmp_path))
    draft = service.prepare()
    assert draft["status"] == "draft"
    key = hashlib.sha256(RAW_TXT).hexdigest()
    path = service.run_dir / "source_reviews" / "objects" / key
    stamp = path.stat()
    changed = RAW_TXT.replace(b"42", b"43")
    assert changed != RAW_TXT and len(changed) == len(RAW_TXT)
    path.write_bytes(changed)
    os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    assert module._read(path) == changed
    with pytest.raises(module.SourceReviewServiceError, match="^source_review_object_changed_or_too_large$"):
        service.read(draft["draft_id"])
