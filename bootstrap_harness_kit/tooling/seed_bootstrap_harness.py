#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def copy_path(source: Path, destination: Path, overwrite: bool) -> tuple[int, int]:
    copied = 0
    skipped = 0

    if source.is_dir():
        for child in source.rglob("*"):
            if child.is_dir():
                continue
            relative = child.relative_to(source)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and not overwrite:
                skipped += 1
                continue
            shutil.copy2(child, target)
            copied += 1
        return copied, skipped

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not overwrite:
        return 0, 1
    shutil.copy2(source, destination)
    return 1, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed reusable bootstrap harness source into a target repo.")
    parser.add_argument("--repo-root", required=True, help="Path to the target repo root")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing kit-managed source files")
    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    kit_root = script_path.parents[1]
    repo_root = Path(args.repo_root).resolve()

    copy_jobs = [
        (kit_root / "docs/assistant/templates", repo_root / "docs/assistant/templates"),
        (kit_root / "docs/assistant/schemas/HARNESS_PROFILE.schema.json", repo_root / "docs/assistant/schemas/HARNESS_PROFILE.schema.json"),
        (kit_root / "docs/assistant/CODEX_ENVIRONMENT.md", repo_root / "docs/assistant/CODEX_ENVIRONMENT.md"),
        (kit_root / ".vscode/mcp.json.example", repo_root / ".vscode/mcp.json.example"),
        (kit_root / "tooling/bootstrap_profile_wizard.py", repo_root / "tooling/bootstrap_profile_wizard.py"),
        (kit_root / "tooling/check_harness_profile.py", repo_root / "tooling/check_harness_profile.py"),
        (kit_root / "tooling/preview_harness_sync.py", repo_root / "tooling/preview_harness_sync.py"),
        (kit_root / "tooling/harness_profile_lib.py", repo_root / "tooling/harness_profile_lib.py"),
    ]

    missing_sources = [str(source) for source, _ in copy_jobs if not source.exists()]
    if missing_sources:
        print("Cannot seed harness because these kit source files are missing:", file=sys.stderr)
        for source in missing_sources:
            print(f"- {source}", file=sys.stderr)
        return 1

    copied = 0
    skipped = 0
    for source, destination in copy_jobs:
        added, ignored = copy_path(source, destination, args.overwrite)
        copied += added
        skipped += ignored

    print(f"Seeded reusable bootstrap source into {repo_root}")
    print(f"Copied files: {copied}")
    print(f"Skipped existing files: {skipped}")
    if not args.overwrite:
        print("Use --overwrite to refresh existing kit-managed source files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
