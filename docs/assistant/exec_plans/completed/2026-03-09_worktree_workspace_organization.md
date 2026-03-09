# Worktree Workspace Organization

## Goal and non-goals
- Goal:
  - Organize the existing sibling worktrees into one saved VS Code workspace.
  - Remove stale folder clutter from the daily workspace view by archiving the broken `legalpdf_translate_optmax` folder and temporary Gmail-intake backup files.
  - Add a short user-facing guide in the main repo explaining how this worktree layout should be used.
- Non-goals:
  - No renaming or relocation of the active Git worktrees.
  - No branch merges, rebases, or Git history changes.

## Scope (in/out)
- In:
  - create `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`
  - add one short workspace/worktree guide in the main repo
  - archive stale `legalpdf_translate_optmax`
  - archive `*.codex_backup_*` files from `legalpdf_translate_gmail_intake/extensions/gmail_intake/`
- Out:
  - editing code inside the sibling worktrees
  - changing branch topology or creating/removing active worktrees

## Worktree provenance
- Main repo/worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Active worktrees discovered:
  - `/mnt/c/Users/FA507/.codex/legalpdf_translate` -> `feat/ai-docs-bootstrap`
  - `/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail` -> `feat/gmail-honorarios-draft`
  - `/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail_intake` -> `feat/gmail-intake-batch-reply`
  - `/mnt/c/Users/FA507/.codex/legalpdf_translate_integration` -> `feat/ocr-runtime-gemini-integration`
- Stale folder discovered:
  - `/mnt/c/Users/FA507/.codex/legalpdf_translate_optmax`
  - points at missing worktree metadata and is not listed by `git worktree list`

## Interfaces/types/contracts affected
- Local machine workspace contract:
  - saved multi-root workspace file at `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`
  - folder order and display names are fixed for repeatable opening
- User-facing guide:
  - documents which folder is the default main repo, how to open the workspace, and not to move active worktrees manually

## File-by-file implementation steps
- `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`
  - add the four active worktrees with friendly names and workspace-level search/watcher exclusions
- `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`
  - add a short guide for the multi-worktree setup
- archive area under `/mnt/c/Users/FA507/.codex/_archive/`
  - store the stale `legalpdf_translate_optmax` folder under a dated archive name with a note
  - store the Gmail-intake `*.codex_backup_*` files under a dated archive folder with a note

## Tests and acceptance criteria
- Validate the workspace JSON parses cleanly.
- Confirm the workspace file references exactly the four active worktrees and excludes noise paths.
- Confirm `legalpdf_translate_optmax` has moved under `_archive` and no longer sits beside the active worktrees.
- Confirm the six Gmail-intake `*.codex_backup_*` files moved out of the live extension directory.
- Confirm `git worktree list --porcelain` still reports the same four active worktrees after the move.

## Risks and mitigations
- Risk: archiving a stale folder that still matters.
  - Mitigation: archive, do not delete; add a note explaining why it was moved.
- Risk: confusing the main repo with sibling worktrees.
  - Mitigation: label the workspace folders explicitly and document the main default path in the guide.

## Assumptions/defaults
- The saved workspace is local-machine tooling and does not need to be the repo’s primary shared entry point.
- The active four worktrees should remain visible in the saved workspace.
- The stale `optmax` folder is safe to archive because its Git worktree metadata is already broken.

## Validation log
- Created `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace` with the four active worktrees in the required order and verified the JSON parses cleanly.
- `git worktree list --porcelain` still reports the same four active worktrees after the archive move.
- Moved the stale `/mnt/c/Users/FA507/.codex/legalpdf_translate_optmax` folder to `/mnt/c/Users/FA507/.codex/_archive/legalpdf_translate_optmax_stale_2026-03-09` and added `ARCHIVE_NOTE.txt`.
- Moved the Gmail-intake `*.codex_backup_*` files into `/mnt/c/Users/FA507/.codex/_archive/gmail_intake_backup_clutter_2026-03-09` and confirmed none remain in the live extension folder.
- Added `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md` and indexed it in `docs/assistant/INDEX.md` and `docs/assistant/manifest.json`.
- `dart run tooling/validate_agent_docs.dart` -> PASS.
