# COMMIT_PUBLISH_WORKFLOW

## What This Workflow Is For
Safe, deterministic commit/push/publish flow with triage and validation gates.

## Expected Outputs
- Cleanly scoped commit(s).
- Correct branch push and PR state.
- Clean repo and branch state after merge when the user asked to push without narrowing scope.
- No blind staging/publishing.

## When To Use
- User asks to commit, push, publish, or prepare PR/merge flow.

## What Not To Do
- Don't use this workflow when implementation/design work is still in progress.
- Instead use the relevant implementation workflow first.

## Primary Files
- `.github/workflows/python-package.yml`
- `docs/assistant/runtime/CANONICAL_BUILD.json`
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
- Current branch does not contain the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`: stop before commit/push and fix branch lineage first.
- User-accepted functionality exists only on a side branch: stop publish flow, promote that branch into the approved base immediately, then continue.
- Unintended staged files: `git restore --staged <path>` and restage explicitly.
- Push safety risk: never force-push `main`; use PR flow.
- User said `push`, but checks are red, merge is blocked, or cleanup is unsafe: report the exact blocker and stop at the highest clean point instead of silently stopping after the raw branch push.
- Branch-scoped closeout is missing before merge:
  - update completed ExecPlans, roadmap artifacts, and `docs/assistant/SESSION_RESUME.md` on the feature branch before merge
  - remove known scratch outputs such as Qt render-review directories before calling the branch clean
- Something was missed after merge:
  - do not repair it by default through a direct push to `main`
  - open a follow-up branch/PR unless the user explicitly asks for a direct post-merge repair

## Handoff Checklist
1. Branch safety gate (before staging):
   - for parallel threads, use `git worktree` isolation first
   - if change is major and branch is `main`, create/switch to `feat/<scope-name>`
   - keep `main` as stable integration branch
   - lock the latest approved baseline branch and SHA before parallel work starts
   - verify the current branch still contains that approved baseline before push/PR
   - verify the current branch contains the approved-base floor recorded in `docs/assistant/runtime/CANONICAL_BUILD.json`
   - verify the current branch still matches or intentionally overrides the canonical build declared in `docs/assistant/runtime/CANONICAL_BUILD.json`
   - if newer approved work is missing from the current branch, stop and fix branch lineage first
2. Default shorthand semantics:
   - bare `commit` means full pending-tree triage, logical grouped commits, validation, then immediate push suggestion
   - bare `push` means Push+PR+Merge+Cleanup by default
   - if the user narrows scope explicitly, follow the narrower instruction instead
3. Fetch/prune and inspect the full pending tree:
   - modified tracked files
   - staged files
   - untracked files
   - temporary artifacts
4. Triage:
   - what to stage
   - what to ignore
   - what to remove from repo state
   - what to split into separate logical commits
   - do not mix unrelated scopes such as product code, docs, tooling/governance, and tests unless the change is inseparable
5. Validate:
   - targeted tests for touched area
   - docs validator when docs changed
6. Commit:
   - scoped staging (`git add <path>`)
   - remove accidental staged files (`git restore --staged <path>`)
   - meaningful commit message
   - after commit, recommend push immediately unless the user explicitly limited the task to commit only
7. Push default (`push` with no narrower wording):
   - push the correct branch
   - create or update the PR
   - verify the latest SHA is the one under review
   - wait for required checks or CI
   - before merge, make branch-scoped closeout decision-complete:
     - close or archive completed ExecPlans
     - close or archive completed roadmap artifacts
     - update `docs/assistant/SESSION_RESUME.md`
     - remove known scratch outputs
   - merge when:
     - checks are green
     - the PR base is correct
     - branch lineage is clean
     - no unresolved review blockers remain
   - when the task involves a GUI build and more than one worktree/build can exist, use `tooling/launch_qt_build.py` for the handoff
   - identify the build under test in the handoff:
     - repo/worktree path
     - branch
     - HEAD SHA
     - canonical vs noncanonical status
     - distinguishing feature set
   - if the branch has already been user-accepted, merge it into the approved base before starting the next unrelated feature branch
8. Cleanup after merge:
   - delete the source branch when it is no longer needed
   - prune refs
   - remove stale local branch state when safe
   - remove known scratch outputs if they still exist locally
   - verify final clean repo state
