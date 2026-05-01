# ExecPlan: Commit, Publish, and Batched March 12 Docs Sync

## Goal and non-goals
- Goal: run one batched Assistant Docs Sync for the accepted March 12 governance, honorários, and desktop-stability changes, then validate, package, publish, merge, and clean up the branch.
- Goal: keep the publish packaging as two commits in one PR.
- Non-goal: make further product behavior changes beyond docs-sync truth repair discovered during the audit.
- Non-goal: widen docs sync into unrelated historical cleanup outside the touched March 12 scope unless a real continuity blocker is discovered during publish.

## Scope (in/out)
- In scope:
  - touch-scope assistant docs sync for March 12 accepted changes
  - one consolidated issue-memory/workflow update only if the desktop-stability lesson is not already covered
  - validation, two commits, push, PR, merge, and post-merge cleanup
- Out of scope:
  - new feature work
  - unrelated dormant active ExecPlans from earlier dates
  - template/bootstrap rewrites beyond the already touched deferred-docs-sync policy surfaces

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/honorarios-pdf-stage1`
- Base branch: `main`
- Base SHA at start: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`

## Planned packaging
1. Commit 1:
   - `docs(governance): defer immediate assistant docs sync by default`
2. Commit 2:
   - `feat(honorarios): finish pdf workflow and desktop stability pass`

## Validation plan
- `.\.venv311\Scripts\python.exe -m pytest -q`
- `.\.venv311\Scripts\python.exe -m compileall src tests tooling`
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

## Publish/closeout plan
- Push `codex/honorarios-pdf-stage1` to `origin`
- Create or update one PR against `main`
- Merge with a merge commit after checks pass
- Delete the source branch, prune refs, fast-forward local `main`, and confirm a clean tree

## Execution evidence before publish
- Ran `git fetch --prune origin` and confirmed `origin/main...HEAD` was `0 0` before staging.
- Audited the March 12 docs surfaces and widened the batched docs sync only where real drift remained:
  - fixed stale interpretation footer-date wording
  - synced the transport-sentence toggle and calmer PDF-failure recovery flow into current-truth and user docs
  - added one consolidated issue-memory entry plus harness workflow guidance for the desktop Qt/export reliability lesson
- Validation completed on the full pending tree:
  - `.\.venv311\Scripts\python.exe -m pytest -q` -> `925 passed`
  - `.\.venv311\Scripts\python.exe -m compileall src tests tooling` -> PASS
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS (`67 cases`)
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
- Created commit 1:
  - `docs(governance): defer immediate assistant docs sync by default`
