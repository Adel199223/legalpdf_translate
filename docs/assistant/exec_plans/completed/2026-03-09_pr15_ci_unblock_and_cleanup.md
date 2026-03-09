# PR 15 CI Unblock and Cleanup

## 1. Title
Fix the PR 15 validator false positive, then finish merge and repo cleanup

## 2. Goal and non-goals
- Goal:
  - unblock PR `#15` by fixing the `SESSION_RESUME.md` branch-existence validator logic for detached/shallow CI checkouts
  - preserve the intended stale-branch protection for deleted feature branches
  - republish the branch, merge the PR, delete the remote branch, and return the local repo to a clean `main`
- Non-goals:
  - no broader roadmap-governance redesign
  - no app/runtime feature changes
  - no force-push or direct repair on `main`

## 3. Scope (in/out)
- In:
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`
  - this ExecPlan lifecycle
  - PR `#15` publish/merge cleanup
- Out:
  - unrelated docs/content rewrites
  - changes under `src/`
  - bootstrap/template contract changes

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/bootstrap-cleanup-continuity-hardening`
- Base branch: `main`
- Base SHA: `2691584561df52fe9cabe12fa5bc0250028adf6b`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; approved-base floor remains satisfied

## 5. Interfaces/types/contracts affected
- Agent-doc validator behavior for `SESSION_RESUME.md` branch validation in git repos
- Validator fixture coverage for detached/shallow checkout semantics
- PR `#15` merge/cleanup lifecycle only after checks are green

## 6. File-by-file implementation steps
- `tooling/validate_agent_docs.dart`
  - keep branch validation for stale deleted branches
  - allow canonical/default resume branch names in detached or shallow checkout environments
  - keep the current AD046 failure for genuinely unknown stale branches
- `test/tooling/validate_agent_docs_test.dart`
  - preserve the deleted-feature-branch failure case
  - add a detached-checkout fixture case where `SESSION_RESUME.md` still points to `main` and validation must pass
- `docs/assistant/exec_plans/active/...`
  - record validations and outcomes
  - move to `completed/` before merge

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- Acceptance:
  - validator passes locally
  - deleted-feature-branch fixture still fails with AD046
  - detached-checkout canonical-branch fixture passes
  - PR `#15` checks turn green after push
  - PR `#15` merges and both local/live repos are clean afterward

## 8. Rollout and fallback
- Land as one incremental fix commit on the existing branch.
- If CI still fails after the first fix, stop with the new exact failure and do not merge.
- After green checks, merge normally via PR and clean branch state locally/remotely.

## 9. Risks and mitigations
- Risk: over-loosening branch validation and missing stale branch drift.
  - Mitigation: only exempt canonical/default branch cases and keep the deleted-feature-branch fixture.
- Risk: CI checkout behavior differs between Linux and Windows.
  - Mitigation: design the exemption around detached/shallow semantics, not one runner path.

## 10. Assumptions/defaults
- The intended dormant-roadmap branch on this repo is `main`.
- The current CI failure is a validator environment false positive, not a real continuity error in `SESSION_RESUME.md`.
- PR merge method remains the normal merge-commit flow used earlier in this repo.

## 11. Execution log
- 2026-03-09:
  - Updated `tooling/validate_agent_docs.dart` so `AD046` still fails for stale deleted branches but allows the canonical resume branch in detached or shallow CI checkouts when it matches the canonical build config or CI branch context.
  - Added a detached-checkout regression case to `test/tooling/validate_agent_docs_test.dart` and kept the deleted-feature-branch failure case intact.
  - Validation results:
    - `dart run tooling/validate_agent_docs.dart` -> passed
    - `dart run test/tooling/validate_agent_docs_test.dart` -> `All agent docs validator tests passed (67 cases).`
  - Ready for one incremental fix commit, push, PR recheck, merge, and local/remote branch cleanup.
