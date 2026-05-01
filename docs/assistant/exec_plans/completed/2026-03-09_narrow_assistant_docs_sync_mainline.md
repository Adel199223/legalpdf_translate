# Narrow Assistant Docs Sync for Fresh Mainline Sessions

## Goal and non-goals
- Goal:
  - sync the narrow March 9 docs surfaces that a fresh Codex session needs after the `main` convergence
  - document the shipped multi-window Qt behavior in canonical, bridge, user-guide, and Qt verification docs
  - close the completed March 9 ExecPlans so `active/` reflects real in-flight work only
- Non-goals:
  - no product code changes
  - no broad assistant-docs re-audit
  - no manifest, index, or workflow rewrites unless a validator exposes a concrete mismatch

## Scope (in/out)
- In:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
  - March 9 ExecPlan lifecycle cleanup
- Out:
  - source-code or runtime changes
  - broader governance/worktree rewrites already landed on `main`
  - issue-memory or routing-map expansion unless validation forces it

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `main`
- Base branch: `origin/main`
- Base SHA: `ea91cb84d0fda719f98a559e981b1c7237345fd9`
- Target integration branch: `main`
- Canonical build status: canonical `main` worktree per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Canonical app/current-truth docs:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
- User-facing support docs:
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Qt verification guide:
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
- ExecPlan lifecycle:
  - March 9 completed plans move from `active/` to `completed/`

## File-by-file implementation steps
- `APP_KNOWLEDGE.md`
  - add multi-window behavior to app summary, desktop shell, primary journeys, persistence notes, and operational guidance
- `docs/assistant/APP_KNOWLEDGE.md`
  - add one support-routing line and one current-truth line for multi-window workspaces
- `docs/assistant/features/APP_USER_GUIDE.md`
  - add plain-language multi-window instructions and duplicate-target explanation
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - add the detailed multi-window workflow and Gmail intake workspace-routing expectations
- `docs/assistant/QT_UI_KNOWLEDGE.md`
  - add multi-window architecture/verification notes where they materially affect future UI work
- `docs/assistant/DOCS_REFRESH_NOTES.md`
  - append a narrow docs-sync entry from `main`
- `docs/assistant/exec_plans/active/2026-03-09_converge_branch_governance_main.md`
  - add the missing Stage 3 completion log
- plan lifecycle
  - move the March 9 convergence plan, the March 9 multi-window plan, and this sync plan to `completed/` after validation

## Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- acceptance:
  - multi-window support is discoverable from canonical, bridge, user-guide, and Qt verification docs
  - the March 9 convergence and multi-window ExecPlans are no longer in `active/`
  - completed March 9 plans record final outcomes accurately

## Rollout and fallback
- This docs sync lands immediately once validators pass.
- If a validator fails, patch only the smallest touched-scope docs needed to restore green validation.

## Risks and mitigations
- Risk: broadening the sync into a general docs rewrite.
  - Mitigation: limit edits to the explicitly unsynced March 9 surfaces.
- Risk: a fresh Codex session still sees stale ExecPlan state.
  - Mitigation: move the completed March 9 plans out of `active/` in this pass.

## Assumptions/defaults
- The `main` governance/worktree convergence docs are already sufficient and should not be redone.
- The detached-HEAD CI hardening needs only refresh-note/plan evidence in this pass, not a broader knowledge-doc expansion.

## Validation log
- Updated canonical/current-truth docs:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
- Updated user/support docs:
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Updated Qt verification docs:
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
- Recorded the sync in:
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Completed March 9 plan lifecycle cleanup:
  - finalized `docs/assistant/exec_plans/active/2026-03-09_converge_branch_governance_main.md`
  - prepared March 9 docs-sync, convergence, and multi-window plans for move to `completed/`
- Executed validations:
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
  - `dart run tooling/validate_workspace_hygiene.dart`
    - result: `PASS: workspace hygiene validation succeeded.`
