# Staged Publish, Docs Sync, and Repo Hygiene

## Goal and non-goals
- Goal: publish the accepted March 28-30 browser/Gmail stabilization wave from `feat/browser-gmail-autostart-repair` using two intentional commits, then merge and return the authoritative worktree to a clean `main`.
- Goal: repair the assistant docs sync/validation path before the docs commit so documentation closeout is trustworthy.
- Goal: limit cleanup to the current authoritative worktree/branch and remote refs, leaving unrelated dirty side worktrees untouched.
- Non-goal: triage or clean the extra dirty side worktrees during this pass.
- Non-goal: rewrite history or force-push any branch.

## Scope (in/out)
- In scope:
  - publish-tree inventory and staging split
  - implementation validation and implementation commit
  - assistant docs sync for touched browser/Gmail/runtime/finalization scope
  - docs validator/workflow repair
  - ExecPlan lifecycle cleanup for the March 28-30 wave
  - push, PR, merge, local-main sync, and current-branch cleanup
- Out of scope:
  - any edits to the other dirty worktrees
  - unrelated product work beyond what is already pending on this branch
  - follow-up pruning of ambiguous unpublished local branches

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch that still contains the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Git/publish contract:
  - two preserved commits on `main`
  - no squash merge
- Assistant docs contract:
  - `SESSION_RESUME.md` must point to the stable browser-first daily path after merge
  - relevant March 28-30 ExecPlans must no longer remain in `active/`
- Tooling contract:
  - docs validation path referenced by workflows/docs/tests must be coherent again before docs sync completes

## File-by-file implementation steps
1. Inventory the branch diff and classify paths into implementation/test vs docs/governance vs obsolete blockers.
2. Repair docs validation coherence by restoring or replacing `tooling/validate_agent_docs.dart` and updating any affected references.
3. Move March 28-30 completed ExecPlans from `docs/assistant/exec_plans/active/` to `completed/`, keeping only genuinely active plans in `active/`.
4. Stage and validate only the implementation/runtime/test wave, then create Commit 1.
5. Perform scoped assistant docs sync across the touched browser/Gmail/runtime/finalization documents, run docs/workspace validation, then create Commit 2.
6. Push the feature branch, open/update the PR to `main`, merge while preserving the two commits, then sync local `main`.
7. Delete the merged source branch locally/remotely, prune refs, and verify the authoritative worktree is clean without touching side worktrees.

## Tests and acceptance criteria
- Implementation gate before Commit 1:
  - targeted `.venv311` pytest suites for browser/Gmail/runtime/finalization/reporting pass
- Docs gate before Commit 2:
  - docs validator path is functional
  - docs validation and workspace hygiene pass
  - `active/` vs `completed/` ExecPlan placement matches reality
- Publish gate before merge:
  - PR preserves the intended two-commit structure
  - merge target is `main`
- Final acceptance:
  - `origin/main` contains the merged stabilization wave
  - local `main` matches `origin/main`
  - `git status` is clean in `C:\Users\FA507\.codex\legalpdf_translate`
  - extra side worktrees remain untouched

## Rollout and fallback
- If the docs validator cannot be repaired cleanly, stop before the docs commit and fix that tooling path first.
- If targeted validation fails, stop before the corresponding commit and fix the failure inside the same scope.
- If PR merge cannot preserve the two commits, stop and choose a merge mode that does.

## Risks and mitigations
- Risk: docs sync could bless stale or incomplete lifecycle state.
  - Mitigation: repair validator coherence and ExecPlan placement before running docs validation.
- Risk: implementation and docs scopes could bleed into each other.
  - Mitigation: stage from an explicit manifest and commit in two passes.
- Risk: cleanup could accidentally destroy unrelated work in side worktrees.
  - Mitigation: limit cleanup to the current authoritative worktree/branch and remote refs only.

## Assumptions/defaults
- The current branch is the only publish target for this pass.
- The March 28-30 active ExecPlans represent completed work and should be archived unless inspection proves otherwise.
- The user-approved publish flow includes push, PR, merge, and current-branch cleanup.

## Completion notes
- PR #34 merged to `main` on 2026-03-30 with preserved non-squash commit history.
- The branch-local CI regressions discovered during publish were fixed before merge, and the local Windows full pytest suite passed (`1112 passed`).
- Assistant docs sync and docs-tooling validation were repaired and completed as part of the published wave.
- Cleanup remained scoped to the authoritative worktree plus branch/ref hygiene; unrelated dirty side worktrees were intentionally left untouched.
