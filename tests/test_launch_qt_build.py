from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from legalpdf_translate.build_identity import current_branch, current_head_sha


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tooling" / "launch_qt_build.py"


def _init_git_repo(repo: Path, branch: str, *, marker: str = "") -> str:
    (repo / "src" / "legalpdf_translate").mkdir(parents=True)
    (repo / "src" / "legalpdf_translate" / "qt_app.py").write_text(
        f"print('ok{marker}')\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-b", branch], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    return subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def test_launch_qt_build_dry_run_emits_identity_packet(tmp_path: Path) -> None:
    branch = current_branch(REPO_ROOT)
    head_sha = current_head_sha(REPO_ROOT)
    config_path = tmp_path / "CANONICAL_BUILD.json"
    config_path.write_text(
        json.dumps(
            {
                "canonical_worktree_path": str(REPO_ROOT),
                "canonical_branch": branch,
                "approved_base_branch": branch,
                "approved_base_head_floor": head_sha,
                "canonical_head_floor": head_sha,
                "allow_noncanonical_by_flag": True,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["LEGALPDF_CANONICAL_BUILD_CONFIG"] = str(config_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--worktree",
            str(REPO_ROOT),
            "--labels",
            "base,qt",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert Path(payload["worktree_path"]).resolve() == REPO_ROOT.resolve()
    assert payload["entrypoint_module"] == "legalpdf_translate.qt_app"
    assert payload["branch"] == branch
    assert payload["head_sha"] == head_sha
    assert payload["labels"] == ["base", "qt"]
    assert payload["dry_run"] is True
    assert payload["is_canonical"] is True
    assert payload["is_lineage_valid"] is True
    assert payload["approved_base_branch"] == branch
    assert payload["approved_base_head_floor"] == head_sha
    assert "launch_command" in payload
    assert payload["allow_noncanonical"] is False
    assert payload["noncanonical_reasons"] == []


def test_launch_qt_build_rejects_invalid_worktree() -> None:
    missing = REPO_ROOT / "missing_worktree_for_test"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--worktree", str(missing), "--dry-run"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 1
    assert "Invalid worktree path" in proc.stderr


def test_launch_qt_build_rejects_noncanonical_without_override(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    head_sha = _init_git_repo(repo, branch="feature-branch")
    config_path = tmp_path / "CANONICAL_BUILD.json"
    config_path.write_text(
        json.dumps(
            {
                "canonical_worktree_path": str(repo),
                "canonical_branch": "feat/ai-docs-bootstrap",
                "approved_base_branch": "feat/ai-docs-bootstrap",
                "approved_base_head_floor": head_sha,
                "canonical_head_floor": head_sha,
                "allow_noncanonical_by_flag": True,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["LEGALPDF_CANONICAL_BUILD_CONFIG"] = str(config_path)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--worktree", str(repo), "--dry-run"],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 1
    assert "Refusing to launch noncanonical worktree" in proc.stderr
    assert "branch feature-branch does not match canonical branch feat/ai-docs-bootstrap" in proc.stderr


def test_launch_qt_build_allows_noncanonical_with_override(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    head_sha = _init_git_repo(repo, branch="feature-branch")
    config_path = tmp_path / "CANONICAL_BUILD.json"
    config_path.write_text(
        json.dumps(
            {
                "canonical_worktree_path": str(tmp_path / "canonical_repo"),
                "canonical_branch": "feat/ai-docs-bootstrap",
                "approved_base_branch": "feat/ai-docs-bootstrap",
                "approved_base_head_floor": head_sha,
                "canonical_head_floor": head_sha,
                "allow_noncanonical_by_flag": True,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["LEGALPDF_CANONICAL_BUILD_CONFIG"] = str(config_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--worktree",
            str(repo),
            "--labels",
            "gemini,mail",
            "--allow-noncanonical",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["is_canonical"] is False
    assert payload["allow_noncanonical"] is True
    assert payload["labels"] == ["gemini", "mail"]
    assert payload["canonical_branch"] == "feat/ai-docs-bootstrap"
    assert payload["approved_base_branch"] == "feat/ai-docs-bootstrap"
    assert payload["approved_base_head_floor"] == head_sha
    assert payload["is_lineage_valid"] is True
    assert any("does not match canonical branch" in item for item in payload["noncanonical_reasons"])


def test_launch_qt_build_rejects_branch_missing_approved_base_floor_even_with_override(
    tmp_path: Path,
) -> None:
    canonical_repo = tmp_path / "canonical_repo"
    canonical_repo.mkdir()
    floor_sha = _init_git_repo(canonical_repo, branch="feat/ai-docs-bootstrap")

    stale_repo = tmp_path / "stale_repo"
    stale_repo.mkdir()
    _init_git_repo(stale_repo, branch="feature-branch", marker="-stale")

    config_path = tmp_path / "CANONICAL_BUILD.json"
    config_path.write_text(
        json.dumps(
            {
                "canonical_worktree_path": str(canonical_repo),
                "canonical_branch": "feat/ai-docs-bootstrap",
                "approved_base_branch": "feat/ai-docs-bootstrap",
                "approved_base_head_floor": floor_sha,
                "canonical_head_floor": floor_sha,
                "allow_noncanonical_by_flag": True,
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["LEGALPDF_CANONICAL_BUILD_CONFIG"] = str(config_path)
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--worktree",
            str(stale_repo),
            "--allow-noncanonical",
            "--dry-run",
        ],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )
    assert proc.returncode == 1
    assert "does not contain the approved base floor" in proc.stderr
