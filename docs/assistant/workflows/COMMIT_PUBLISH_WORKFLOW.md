# COMMIT_PUBLISH_WORKFLOW

## What This Workflow Is For
Safe, deterministic commit/push/publish flow with triage and validation gates.

## Expected Outputs
- Cleanly scoped commit(s).
- Correct branch push.
- No blind staging/publishing.

## When To Use
- User asks to commit, push, publish, or prepare PR/merge flow.

## What Not To Do
- Don't use this workflow when implementation/design work is still in progress.
- Instead use the relevant implementation workflow first.

## Primary Files
- `.github/workflows/python-package.yml`
- `docs/assistant/workflows/CI_REPO_WORKFLOW.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`

## Minimal Commands
PowerShell:
```powershell
git fetch --prune origin
git status --short --branch
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
```
POSIX:
```bash
git fetch --prune origin
git status --short --branch
git diff --name-only
git diff --cached --name-only
git ls-files --others --exclude-standard
```

## Targeted Tests
- `python -m pytest -q <targeted paths>`
- `dart run tooling/validate_agent_docs.dart` (when docs changed)
- `dart run tooling/validate_workspace_hygiene.dart` (when perf/workspace docs changed)

## Failure Modes and Fallback Steps
- Wrong branch for major work: create/switch to `feat/<scope-name>`.
- Wrong worktree base for the current branch: stop before commit/push, compare against the latest approved baseline SHA, and transplant/rebase first.
- Unintended staged files: `git restore --staged <path>` and restage explicitly.
- Push safety risk: never force-push `main`; use PR flow.

## Handoff Checklist
1. Branch safety gate (before staging):
   - for parallel threads, use `git worktree` isolation first
   - if change is major and branch is `main`, create/switch to `feat/<scope-name>`
   - keep `main` as stable integration branch
   - lock the latest approved baseline branch and SHA before parallel work starts
   - verify the current branch still contains that approved baseline before push/PR
   - if newer approved work is missing from the current branch, stop and fix branch lineage first
2. Fetch/prune and inspect state.
3. Triage:
   - what to stage
   - what to ignore
   - what to split into separate commits
4. Validate:
   - targeted tests for touched area
   - docs validator when docs changed
5. Commit:
   - scoped staging (`git add <path>`)
   - remove accidental staged files (`git restore --staged <path>`)
   - meaningful commit message
6. Push:
   - push correct branch only
   - never force-push `main`
   - when the task involves a GUI build, identify the build under test in the handoff:
     - repo/worktree path
     - branch
     - HEAD commit
     - distinguishing feature set
7. Repo cleanup:
   - ff-only merge to `main`
   - delete stale branches with explicit keep-list
   - prune refs and verify final clean state
