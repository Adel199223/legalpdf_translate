"""Runtime build identity and canonical-build policy helpers."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any


@dataclass(frozen=True, slots=True)
class CanonicalBuildConfig:
    canonical_worktree_path: str
    canonical_branch: str
    approved_base_branch: str
    approved_base_head_floor: str
    canonical_head_floor: str
    allow_noncanonical_by_flag: bool = True


@dataclass(frozen=True, slots=True)
class RuntimeBuildIdentity:
    worktree_path: str
    branch: str
    head_sha: str
    labels: tuple[str, ...]
    is_canonical: bool
    is_lineage_valid: bool
    canonical_worktree_path: str
    canonical_branch: str
    approved_base_branch: str
    approved_base_head_floor: str
    canonical_head_floor: str
    reasons: tuple[str, ...] = ()

    def window_title(self, base_title: str) -> str:
        if self.is_canonical:
            return base_title
        return f"{base_title} [{self.branch}@{self.head_sha}]"

    def summary_text(self) -> str:
        status = "canonical" if self.is_canonical else "noncanonical"
        labels_text = ", ".join(self.labels) if self.labels else "(none)"
        reason_text = "\n".join(f"- {item}" for item in self.reasons) if self.reasons else "- none"
        return (
            f"Status: {status}\n"
            f"Worktree: {self.worktree_path}\n"
            f"Branch: {self.branch}\n"
            f"HEAD SHA: {self.head_sha}\n"
            f"Approved base branch: {self.approved_base_branch}\n"
            f"Approved base head floor: {self.approved_base_head_floor}\n"
            f"Lineage valid: {'yes' if self.is_lineage_valid else 'no'}\n"
            f"Canonical worktree: {self.canonical_worktree_path}\n"
            f"Canonical branch: {self.canonical_branch}\n"
            f"Canonical head floor: {self.canonical_head_floor}\n"
            f"Labels: {labels_text}\n"
            f"Noncanonical reasons:\n{reason_text}"
        )


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def canonical_build_config_path(repo: Path | None = None) -> Path:
    override = os.getenv("LEGALPDF_CANONICAL_BUILD_CONFIG", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    root = repo if repo is not None else repo_root()
    return root / "docs" / "assistant" / "runtime" / "CANONICAL_BUILD.json"


def load_canonical_build_config(repo: Path | None = None) -> CanonicalBuildConfig:
    path = canonical_build_config_path(repo)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return CanonicalBuildConfig(
        canonical_worktree_path=str(payload["canonical_worktree_path"]),
        canonical_branch=str(payload["canonical_branch"]),
        approved_base_branch=str(payload.get("approved_base_branch", payload["canonical_branch"])),
        approved_base_head_floor=str(payload.get("approved_base_head_floor", payload["canonical_head_floor"])),
        canonical_head_floor=str(payload["canonical_head_floor"]),
        allow_noncanonical_by_flag=bool(payload.get("allow_noncanonical_by_flag", True)),
    )


def try_load_canonical_build_config(repo: Path | None = None) -> CanonicalBuildConfig | None:
    path = canonical_build_config_path(repo)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None
    except json.JSONDecodeError:
        return None
    try:
        return CanonicalBuildConfig(
            canonical_worktree_path=str(payload["canonical_worktree_path"]),
            canonical_branch=str(payload["canonical_branch"]),
            approved_base_branch=str(payload.get("approved_base_branch", payload["canonical_branch"])),
            approved_base_head_floor=str(payload.get("approved_base_head_floor", payload["canonical_head_floor"])),
            canonical_head_floor=str(payload["canonical_head_floor"]),
            allow_noncanonical_by_flag=bool(payload.get("allow_noncanonical_by_flag", True)),
        )
    except KeyError:
        return None


def _to_wsl_path(path_like: str | Path) -> str | None:
    text = str(path_like).strip()
    match = _WSL_MNT_RE.match(text)
    if match:
        drive = match.group(1).lower()
        tail = match.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{tail}" if tail else f"/mnt/{drive}"
    if _DRIVE_RE.match(text):
        win = PureWindowsPath(text)
        drive = str(win.drive).rstrip(":").lower()
        tail = "/".join(part for part in win.parts[1:])
        return f"/mnt/{drive}/{tail}" if tail else f"/mnt/{drive}"
    return None


def _should_try_wsl_git(stderr_text: str, repo: Path) -> bool:
    stderr_lower = stderr_text.lower()
    if "not a git repository" in stderr_lower:
        return True
    git_file = repo / ".git"
    if git_file.is_file():
        try:
            return "/mnt/" in git_file.read_text(encoding="utf-8")
        except OSError:
            return False
    return False


def _resolve_wsl_executable() -> str | None:
    found = shutil.which("wsl.exe")
    if found:
        return found
    system_root = str(os.environ.get("SystemRoot", r"C:\Windows") or r"C:\Windows").strip() or r"C:\Windows"
    fallback = Path(system_root) / "System32" / "wsl.exe"
    if fallback.exists():
        return str(fallback)
    return None


def _run_git_proc(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    native = subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if native.returncode == 0:
        return native
    if not _should_try_wsl_git(native.stderr or native.stdout, repo):
        return native
    wsl_repo = _to_wsl_path(repo)
    wsl_exe = _resolve_wsl_executable()
    if not wsl_repo or not wsl_exe:
        return native
    return subprocess.run(
        [wsl_exe, "--exec", "git", "-C", wsl_repo, *args],
        text=True,
        capture_output=True,
        check=False,
    )


def _run_git(repo: Path, *args: str) -> str:
    proc = _run_git_proc(repo, *args)
    if proc.returncode != 0:
        message = proc.stderr.strip() or proc.stdout.strip() or "git command failed"
        raise RuntimeError(message)
    return proc.stdout.strip()


def current_branch(repo: Path | None = None) -> str:
    root = repo if repo is not None else repo_root()
    proc = _run_git_proc(root, "symbolic-ref", "--short", "-q", "HEAD")
    if proc.returncode == 0:
        branch = proc.stdout.strip()
        if branch:
            return branch
    for env_name in (
        "LEGALPDF_BUILD_BRANCH",
        "GITHUB_HEAD_REF",
        "GITHUB_REF_NAME",
        "BUILD_SOURCEBRANCHNAME",
        "CI_COMMIT_REF_NAME",
        "BRANCH_NAME",
    ):
        value = str(os.getenv(env_name, "") or "").strip()
        if value:
            return value
    branch = _run_git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        return branch
    return "HEAD"


def current_head_sha(repo: Path | None = None) -> str:
    root = repo if repo is not None else repo_root()
    return _run_git(root, "rev-parse", "--short", "HEAD")


def head_contains_floor(repo: Path, floor_sha: str) -> bool:
    proc = _run_git_proc(repo, "merge-base", "--is-ancestor", floor_sha, "HEAD")
    return proc.returncode == 0


_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_WSL_MNT_RE = re.compile(r"^/mnt/([A-Za-z])/(.*)$")


def normalize_path_identity(path_like: str | Path) -> str:
    text = str(path_like).strip()
    match = _WSL_MNT_RE.match(text)
    if match:
        drive = match.group(1).lower()
        tail = match.group(2).replace("\\", "/")
        return f"{drive}:/{tail}".lower().rstrip("/")
    if _DRIVE_RE.match(text):
        win = PureWindowsPath(text)
        drive = str(win.drive).rstrip(":").lower()
        tail = "/".join(part for part in win.parts[1:])
        return f"{drive}:/{tail}".lower().rstrip("/")
    return str(Path(text).expanduser().resolve()).replace("\\", "/").rstrip("/").lower()


def parse_build_labels(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(item.strip() for item in str(raw).split(",") if item.strip())


def detect_runtime_build_identity(*, repo: Path | None = None, labels: tuple[str, ...] | None = None) -> RuntimeBuildIdentity:
    root = repo if repo is not None else repo_root()
    branch = current_branch(root)
    head_sha = current_head_sha(root)
    worktree = str(root.resolve())
    reasons: list[str] = []
    config = try_load_canonical_build_config(root)
    if config is None:
        reasons.append(
            f"canonical build config missing or invalid at {canonical_build_config_path(root)}"
        )
        resolved_labels = labels if labels is not None else parse_build_labels(os.getenv("LEGALPDF_BUILD_LABELS"))
        return RuntimeBuildIdentity(
            worktree_path=worktree,
            branch=branch,
            head_sha=head_sha,
            labels=resolved_labels,
            is_canonical=False,
            is_lineage_valid=False,
            canonical_worktree_path="(missing)",
            canonical_branch="(missing)",
            approved_base_branch="(missing)",
            approved_base_head_floor="(missing)",
            canonical_head_floor="(missing)",
            reasons=tuple(reasons),
        )
    worktree_norm = normalize_path_identity(worktree)
    canonical_norm = normalize_path_identity(config.canonical_worktree_path)
    if worktree_norm != canonical_norm:
        reasons.append(
            f"worktree {worktree_norm} does not match canonical worktree {canonical_norm}"
        )
    if branch != config.canonical_branch:
        reasons.append(
            f"branch {branch} does not match canonical branch {config.canonical_branch}"
        )
    lineage_valid = head_contains_floor(root, config.approved_base_head_floor)
    if not lineage_valid:
        reasons.append(
            f"HEAD does not contain approved base floor {config.approved_base_head_floor}"
        )
    if not head_contains_floor(root, config.canonical_head_floor):
        reasons.append(
            f"HEAD does not contain canonical floor {config.canonical_head_floor}"
        )
    resolved_labels = labels if labels is not None else parse_build_labels(os.getenv("LEGALPDF_BUILD_LABELS"))
    return RuntimeBuildIdentity(
        worktree_path=worktree,
        branch=branch,
        head_sha=head_sha,
        labels=resolved_labels,
        is_canonical=not reasons,
        is_lineage_valid=lineage_valid,
        canonical_worktree_path=config.canonical_worktree_path,
        canonical_branch=config.canonical_branch,
        approved_base_branch=config.approved_base_branch,
        approved_base_head_floor=config.approved_base_head_floor,
        canonical_head_floor=config.canonical_head_floor,
        reasons=tuple(reasons),
    )
