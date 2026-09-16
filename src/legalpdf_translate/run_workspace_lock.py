"""Nonblocking, run-owned exclusion for translation and offline formatting.

The lock is an OS-held byte/file lock, not a stale PID or checkpoint flag.
Same-thread nesting allows partial export during a running workflow. Separate
threads/processes fail promptly, while unrelated run folders remain independent.
The stable lock file is retained and never deleted or interpreted as activity.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import threading


class RunWorkspaceBusy(ValueError):
    """Another operation currently owns this run directory."""


_REGISTRY_GUARD = threading.Lock()
_OWNERS: dict[str, tuple[int, int, object]] = {}
_LOCK_NAME = ".run_workspace.lock"


def _after_fork():
    # A fork inherits Python bookkeeping and descriptors, but must contend as a
    # new process. Closing its inherited references leaves the parent's lock.
    global _REGISTRY_GUARD
    for _, _, stream in _OWNERS.values():
        stream.close()
    _OWNERS.clear()
    _REGISTRY_GUARD = threading.Lock()


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork)


def _directory(path, *, create):
    path = Path(path).expanduser().absolute()
    if ".." in path.parts:
        raise ValueError("Run workspace path must be normalized.")
    if create:
        # Output parent is already validated by the caller; do not create it.
        path.mkdir(exist_ok=True)
    for item in (path, *path.parents):
        info = item.lstat()
        if (not stat.S_ISDIR(info.st_mode) or item.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise ValueError("Run workspace must use direct directories.")
    return path.resolve(strict=True)


def _identity(info):
    return info.st_dev, info.st_ino


def _check_file(path, stream):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
            or getattr(info, "st_file_attributes", 0) & 0x400
            or getattr(info, "st_nlink", 1) != 1
            or _identity(info) != _identity(os.fstat(stream.fileno()))):
        raise ValueError("Run workspace lock identity changed.")


def _os_lock(stream, *, release=False):
    stream.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK if release else msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN if release else fcntl.LOCK_EX | fcntl.LOCK_NB)


@contextmanager
def run_workspace_slot(run_dir: Path, *, create=False):
    root = _directory(run_dir, create=create)
    key = os.path.normcase(str(root))
    owner = threading.get_ident()
    path = root / _LOCK_NAME
    with _REGISTRY_GUARD:
        existing = _OWNERS.get(key)
        if existing is not None:
            if existing[0] != owner:
                raise RunWorkspaceBusy("Another operation is already using this run folder.")
            _check_file(path, existing[2])
            _OWNERS[key] = (owner, existing[1] + 1, existing[2])
        else:
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if (not stat.S_ISREG(info.st_mode) or path.is_symlink()
                        or getattr(info, "st_file_attributes", 0) & 0x400):
                    raise ValueError("Run workspace lock must be a direct regular file.")
            descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
                                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
            stream = os.fdopen(descriptor, "r+b", buffering=0)
            try:
                _check_file(path, stream)
                if os.fstat(stream.fileno()).st_size == 0:
                    stream.write(b"0")
                try:
                    _os_lock(stream)
                except OSError as exc:
                    raise RunWorkspaceBusy("Another operation is already using this run folder.") from exc
                _check_file(path, stream)
            except BaseException:
                stream.close()
                raise
            _OWNERS[key] = (owner, 1, stream)
    try:
        yield root
        _check_file(path, _OWNERS[key][2])
    finally:
        with _REGISTRY_GUARD:
            current = _OWNERS[key]
            if current[1] > 1:
                _OWNERS[key] = (owner, current[1] - 1, current[2])
            else:
                try:
                    _os_lock(current[2], release=True)
                finally:
                    current[2].close()
                    del _OWNERS[key]
