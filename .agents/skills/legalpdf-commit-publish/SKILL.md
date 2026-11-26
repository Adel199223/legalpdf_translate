---
name: legalpdf-commit-publish
description: >-
  Execute LegalPDF Translate git triage, worktree/baseline checks, commit/push
  shorthand workflows, and post-merge cleanup. Use when the user asks to commit,
  push, open a PR, check worktree lineage, or finalize a release branch.
---

# LegalPDF Commit, Worktree & Publish Workflow

Defer to `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`, `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md`, `docs/assistant/runtime/CANONICAL_BUILD.json`, `docs/assistant/exec_plans/PLANS.md`, and `docs/assistant/HANDOFF.md`.

## Mandatory Gates

- **Never commit, push, merge, or force-push without explicit user authorization.**
- Preserve preexisting protected dirty files noted in `docs/assistant/HANDOFF.md` (`docs/assistant/CACHE_COMPATIBILITY_ASSESSMENT.md`, `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`, `.codex-remote-attachments/`) unless the user explicitly targets them.
- Major work belongs on `feat/<scope-name>` in an isolated `git worktree`; never switch branches in canonical `main` (`C:/Users/FA507/.codex/legalpdf_translate`) while its live server (`8877`/`8765`) is running.

## Baseline & Tree Inspection

```powershell
git fetch --prune origin
git status --short --branch
git rev-parse --short HEAD
git merge-base --is-ancestor 4e9d20e HEAD
git worktree list
```
Verify the current branch contains `approved_base_head_floor` declared in `docs/assistant/runtime/CANONICAL_BUILD.json` before staging or pushing.

## Shorthand Semantics

Unless the user explicitly narrows scope (e.g., `commit only ...` or `push branch only`):
- **`commit`**: Inspect the full pending Source Control tree, triage modified/staged/untracked/scratch files, split into logical grouped commits (do not mix product code, docs, governance, and tests unless inseparable), run targeted + docs/hygiene validation, commit with scoped `git add`, and immediately suggest `push`.
- **`push`**: Push the feature branch -> create or update PR -> confirm latest SHA -> wait for required CI (`test (3.11)`) -> complete branch-scoped closeout (move completed ExecPlans to `docs/assistant/exec_plans/completed/`, update `docs/assistant/SESSION_RESUME.md`, remove scratch outputs) -> merge when green and clean -> delete merged branch, prune refs, remove harvested side worktrees, restore canonical `main` launcher/native-host routing, and verify final clean repo state.

## Handoff Verification

Include repo/worktree path, branch, `HEAD` SHA, canonical vs noncanonical status, distinguishing feature set (plus `tooling/launch_qt_build.py` packet for multi-worktree Qt handoffs), and final `git status --short --branch`.
