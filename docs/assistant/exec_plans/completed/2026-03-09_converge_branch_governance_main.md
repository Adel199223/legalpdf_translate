# Converge Branch Governance Back to `main`

## Goal and non-goals
- Goal:
  - restore `main` as the approved integration base
  - converge the full accepted `feat/ai-docs-bootstrap` stack into `main` through a standard merge flow
  - retarget live governance/docs contracts to `main`
  - retire `feat/ai-docs-bootstrap` only after post-merge verification
- Non-goals:
  - do not publish or merge the two preserved local WIP branches
  - do not rewrite historical docs records that accurately describe prior branch state
  - do not change unrelated Dependabot PRs

## Scope (in/out)
- In:
  - Stage 1 convergence worktree creation and full-stack merge commit
  - Stage 2 governance/docs retargeting for live contracts and current workspace guidance
  - Stage 3 PR, merge to `main`, post-merge validation, and source-branch retirement
- Out:
  - reconciliation of the local-only WIP branches into GitHub
  - unrelated workflow or product feature work
  - cleanup of historical completed ExecPlans beyond preserving them as history

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_main_converge`
- Branch name: `chore/converge-main-approved-base`
- Base branch: `main`
- Base SHA: `25fd8e99bc9abf6d2a8463e9a1bf2e9f5f9dc0a4`
- Target integration branch: `main`
- Canonical build status: noncanonical convergence worktree created intentionally to restore `main` as the approved base

## Interfaces/types/contracts affected
- Git/GitHub branch governance contract:
  - `main` becomes the approved base and canonical branch again
  - `feat/ai-docs-bootstrap` becomes a temporary freeze branch pending retirement
- Docs/runtime contracts:
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
  - worktree-baseline workflow docs
  - current workspace/user guidance for the saved VS Code workspace file

## File-by-file implementation steps
- `docs/assistant/exec_plans/active/2026-03-09_converge_branch_governance_main.md`
  - record staged execution, validations, decision locks, and follow-up boundaries
- Stage 1 branch/worktree operations
  - create `chore/converge-main-approved-base` from `origin/main`
  - merge `origin/feat/ai-docs-bootstrap` with a normal merge commit and no cherry-picks
- Stage 2 governance/docs files
  - retarget live contracts to `main`
  - update current workspace/user guide surfaces to reflect the current local worktree layout
  - append convergence notes without rewriting historical records
- Stage 3 publish/cleanup operations
  - push convergence branch, open PR to `main`, wait for green CI, merge with a merge commit
  - fast-forward local `main`, validate from `main`, then delete `feat/ai-docs-bootstrap` locally/remotely

## Tests and acceptance criteria
- Stage 1:
  - convergence worktree exists on `chore/converge-main-approved-base`
  - branch contains a merge commit from `origin/main` and `origin/feat/ai-docs-bootstrap`
  - no local WIP branch content is included
- Stage 2:
  - live governance files point to `main` as the approved base
  - current workspace/user guide files describe the actual local state
- Stage 3:
  - PR base is `main`
  - CI is green before merge
  - post-merge `main` contains the approved stack and passes validation
  - `feat/ai-docs-bootstrap` is removed only after post-merge validation succeeds

## Rollout and fallback
- Use staged execution with hard stops after Stage 1 and Stage 2.
- If Stage 1 merge reveals unexpected conflicts, stop and replan instead of forcing ad hoc resolution.
- If Stage 2 governance retargeting exposes stale workspace assumptions, update only live/current guidance and preserve historical records.
- If PR checks fail in Stage 3, stop before merge and keep `feat/ai-docs-bootstrap` frozen.

## Risks and mitigations
- Risk: `main` and `feat/ai-docs-bootstrap` diverged in a way that breaks a straight merge.
  - Mitigation: create the convergence worktree from `origin/main`, use a merge commit, and stop if conflicts appear.
- Risk: docs stay split between old and new approved-base rules.
  - Mitigation: retarget only live policy/current-state surfaces and append a convergence note.
- Risk: deleting `feat/ai-docs-bootstrap` too early strands the working baseline.
  - Mitigation: keep it frozen until post-merge validation on `main` passes.

## Assumptions/defaults
- The entire accepted `feat/ai-docs-bootstrap` stack is intended to become the new `main` baseline.
- The two preserved WIP branches remain local-only and excluded from this convergence.
- Stage boundary after Stage 1 requires exact continuation token `NEXT_STAGE_2`.
- Stage boundary after Stage 2 requires exact continuation token `NEXT_STAGE_3`.

## Validation log
- Stage 1 execution log:
  - created worktree `/mnt/c/Users/FA507/.codex/legalpdf_translate_main_converge` from `origin/main`
  - created branch `chore/converge-main-approved-base`
  - added this ExecPlan under `docs/assistant/exec_plans/active/`
  - ran `git merge --no-ff --no-commit origin/feat/ai-docs-bootstrap`
    - result: merge staged cleanly with no content conflicts
  - sanity snapshot:
    - `git status --short --branch`
      - result: staged full-stack merge diff from `origin/feat/ai-docs-bootstrap` plus untracked convergence ExecPlan
    - `git diff --cached --name-only`
      - result: staged approved-stack file set from `origin/feat/ai-docs-bootstrap`
    - `git diff --cached --stat`
      - result: staged large approved-stack merge diff from `origin/main` to `origin/feat/ai-docs-bootstrap`
- Stage 1 boundary status:
  - merge commit pending
  - exact continuation token required for the next pass after Stage 1 completion: `NEXT_STAGE_2`

## Stage 2 execution log
- Implemented Stage 2 files:
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
    - retargeted `canonical_branch` and `approved_base_branch` to `main` while preserving the existing floor SHAs
  - `docs/assistant/features/WORKTREE_WORKSPACE_USER_GUIDE.md`
    - updated the current-state guide for a single default main worktree with optional side worktrees only when intentionally created
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
    - appended the convergence note and captured the Stage 2 validation results
  - `tests/test_launch_qt_build.py`
    - made the dry-run identity test branch-aware so it passes when the convergence worktree is intentionally noncanonical under the retargeted canonical-build contract
- Implemented Stage 2 local environment update:
  - `/mnt/c/Users/FA507/.codex/legalpdf_translate-worktrees.code-workspace`
    - reduced the saved VS Code workspace to the single active main worktree
- Executed Stage 2 validations:
  - `PYTHONPATH=src /mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe -m pytest -q`
    - result: `785 passed in 26.91s`
  - `python3 -m compileall src tests tooling`
    - result: pass
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
  - `dart run tooling/validate_workspace_hygiene.dart`
    - result: `PASS: workspace hygiene validation succeeded.`
- Stage 2 boundary status:
  - governance/docs retarget ready for PR stage
  - exact continuation token required for the next pass: `NEXT_STAGE_3`

## Stage 3 execution log
- Published and validated the convergence branch:
  - pushed `chore/converge-main-approved-base`
  - opened PR `#13` to `main`
  - addressed PR-check failures caused by detached-HEAD build-identity assumptions through follow-up commits:
    - `b8c1048` `test(build): isolate launch identity dry-run config`
    - `ecee94d` `fix(build): handle detached branch identity`
- Final PR CI state before merge:
  - `docs_tooling_contracts` -> pass
  - `test (3.11)` -> pass
- Merged PR `#13` into `main` with merge commit `ea91cb84d0fda719f98a559e981b1c7237345fd9`.
- Post-merge local/mainline actions:
  - fast-forwarded local `main` to `origin/main`
  - switched the canonical worktree back to `main`
  - removed the temporary convergence worktree
  - deleted `feat/ai-docs-bootstrap` locally/remotely
  - deleted `chore/converge-main-approved-base` locally/remotely
  - pruned refs
- Post-merge validations from canonical `main`:
  - `PYTHONPATH=src ./.venv311/Scripts/python.exe -m pytest -q`
    - result: `786 passed in 29.15s`
  - `python3 -m compileall src tests tooling`
    - result: pass
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
  - `dart run tooling/validate_workspace_hygiene.dart`
    - result: `PASS: workspace hygiene validation succeeded.`
  - `PYTHONPATH=src ./.venv311/Scripts/python.exe tooling/launch_qt_build.py --worktree /mnt/c/Users/FA507/.codex/legalpdf_translate --dry-run`
    - result: canonical `main` identity packet with `branch=main`, `is_canonical=true`, and `is_lineage_valid=true`
- Stage 3 completion status:
  - completed
  - `main` restored as the approved integration base and canonical branch
  - only `main` remains as the active worktree; preserved local-only WIP branches remain untouched outside this plan
