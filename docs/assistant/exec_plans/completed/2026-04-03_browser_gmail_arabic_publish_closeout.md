# Browser Gmail Arabic Publish Closeout

## 1. Title
Browser Gmail Arabic Publish Closeout

## 2. Goal and non-goals
- Goal: publish the accepted browser Gmail + Arabic hardening wave from the isolated fix worktree using two intentional commits, then merge to `main` and restore a clean canonical local state.
- Goal: run a touched-scope Assistant Docs Sync before the docs commit so the merged baseline no longer describes stale Arabic review behavior.
- Goal: leave unrelated side worktrees alone except for restoring the configured canonical path back to a clean `main`.
- Non-goal: widen this pass into unrelated feature work or side-worktree cleanup.
- Non-goal: rewrite history or force-push any branch.

## 3. Scope (in/out)
- In scope:
  - publish-branch creation and validation
  - implementation/test commit
  - touched-scope Assistant Docs Sync
  - ExecPlan lifecycle closeout for this feature wave
  - push, PR, merge, and canonical-path cleanup
- Out of scope:
  - unrelated side worktree feature triage
  - new product behavior beyond what is already pending on this branch

## 4. Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_pdf_worker_fix`
- branch name: `feat/browser-gmail-arabic-stability`
- base branch: `main`
- base SHA: `ab70a4796e29281f09be5bcdb962ba56bd0473b3`
- target integration branch: `main`
- canonical build status: noncanonical isolated worktree that still contains the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Product/browser contracts:
  - Gmail browser PDF preview/prepare diagnostics and worker preflight
  - noncanonical live-runtime warning/continue behavior
  - browser Arabic review gate and manual Word save behavior
  - Gmail failed-translation recovery stage semantics
  - shared Arabic DOCX mixed-script run ordering
- Docs/governance contracts:
  - touched-scope Assistant Docs Sync for browser Gmail Arabic behavior
  - active/completed ExecPlan lifecycle state for this wave

## 6. File-by-file implementation steps
1. Validate the pending implementation/test slice on the publish branch.
2. Exclude generated outputs such as `test-results/.last-run.json`.
3. Stage only implementation/runtime/test files and create Commit 1.
4. Run touched-scope Assistant Docs Sync and update issue memory/refresh notes only where this wave changed supported behavior.
5. Move the feature-wave ExecPlans plus this publish-closeout plan to `docs/assistant/exec_plans/completed/`.
6. Run docs/workspace validators and create Commit 2.
7. Push the publish branch, open/update the PR, merge without squashing, then restore local canonical state.

## 7. Tests and acceptance criteria
- Commit 1 gate:
  - focused pytest bundle for browser Gmail Arabic hardening passes
  - representative Arabic DOCX render validation passes
- Commit 2 gate:
  - docs sync reflects manual-only browser Arabic review
  - docs/workspace validators pass
  - active/completed ExecPlan placement matches reality
- Publish gate:
  - PR preserves the two intended commits
  - merge target is `main`
  - local canonical path returns to clean `main` after merge

## 8. Rollout and fallback
- If the focused implementation suite fails, stop before Commit 1 and fix the failure on the publish branch.
- If docs validators fail, stop before Commit 2 and repair the touched docs/governance state first.
- If PR checks fail, repair them on the publish branch before merge.

## 9. Risks and mitigations
- Risk: docs sync could restate stale Arabic review behavior.
  - Mitigation: update only touched docs and explicitly remove the browser `Align Right + Save` wording.
- Risk: cleanup could leave the canonical launcher path pointing at the wrong branch again.
  - Mitigation: restore `C:\Users\FA507\.codex\legalpdf_translate` to clean `main` and verify the native-host launcher afterwards.
- Risk: unrelated side worktrees could be disturbed.
  - Mitigation: keep cleanup scoped to the publish branch, the temporary fix worktree, remote refs, and the configured canonical path only.

## 10. Assumptions/defaults
- The user-approved publish branch name is `feat/browser-gmail-arabic-stability`.
- `test-results/.last-run.json` is disposable generated output and will not be committed.
- The canonical path cleanup must preserve the lone LichtFeld plan note before resetting that worktree back to `main`.
