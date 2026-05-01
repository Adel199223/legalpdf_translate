# 2026-03-11 Stage 3 Qt Docs Sync

## 1. Title
Stage 3 Qt assistant-doc sync for the shipped settings/admin/tool UI state.

## 2. Goal and non-goals
- Goal:
  - sync the touched assistant docs to the shipped Stage 3 Qt UI state already present on this worktree
  - keep the scope limited to canonical/bridge/Qt UI knowledge plus refresh notes
- Non-goals:
  - no runtime code changes
  - no manifest, index, user-guide, roadmap, or issue-memory edits unless validation proves they are required
  - no documentation claims about broader `PrimaryButton` / `DangerButton` or no-wheel rollout that are not supported by the current code

## 3. Scope (in/out)
- In scope:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Out of scope:
  - `docs/assistant/manifest.json`
  - `docs/assistant/INDEX.md`
  - user guides
  - source code and tests

## 4. Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `main`
- base branch: `main`
- base SHA: `f3a3850dcc698170307b509a5c4c3cc2067b04c0`
- target integration branch: `main`
- canonical build status: canonical `main` worktree; docs-only sync, no GUI handoff build packet required
- provenance note: local branch `codex/core-ui-rollout` currently resolves to the same SHA as `main`, so there is no divergent rollout branch to sync against

## 5. Interfaces/types/contracts affected
- Assistant-doc contract only:
  - canonical app truth remains `APP_KNOWLEDGE.md`
  - bridge remains shorter and deferential to canonical
  - Qt UI knowledge remains implementation-facing and must match the shipped widget/objectName/guarded-input behavior
- No runtime API, schema, persistence, or CLI contracts change

## 6. File-by-file implementation steps
1. Re-audit the shipped Qt code for:
   - shared dialog/tool styling scope
   - `PrimaryButton` / `DangerButton` objectName usage
   - guarded combo coverage vs plain `QComboBox` exceptions
2. Update `APP_KNOWLEDGE.md` to reflect the broader shared Stage 3 Qt dialog/tool styling footprint and the validated guarded-combo scope.
3. Update `docs/assistant/APP_KNOWLEDGE.md` current-truth bullets to match canonical without duplicating detail.
4. Update `docs/assistant/QT_UI_KNOWLEDGE.md` so the objectName table and guard invariants match the shipped code, including explicit plain-`QComboBox` exceptions for dense table editors and suggestion-scope cells.
5. Append one dated touched-scope entry to `docs/assistant/DOCS_REFRESH_NOTES.md`.

## 7. Tests and acceptance criteria
- Run:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance criteria:
  - validators pass
  - only the four scoped docs files change, plus this ExecPlan lifecycle file
  - `docs/assistant/manifest.json` and `docs/assistant/INDEX.md` remain unchanged
  - docs language matches the shipped Qt code on this worktree

## 8. Rollout and fallback
- Rollout:
  - patch docs in canonical -> bridge -> Qt knowledge -> refresh-notes order
- Fallback:
  - if validation reveals wider docs drift, stop at the smallest additional touched scope required and record why
  - if code and prior plan assumptions disagree, prefer code truth and note the corrected contract in the docs/plan

## 9. Risks and mitigations
- Risk: documenting aspirational Stage 3 behavior that is not actually shipped on `main`
  - Mitigation: ground every doc change in direct code audit before editing
- Risk: widening docs scope unnecessarily
  - Mitigation: leave manifest/index/user guides untouched unless a validator forces expansion
- Risk: leaving stale active-plan inventory behind
  - Mitigation: move this ExecPlan to `completed/` after validations and close-out

## 10. Assumptions/defaults
- The shipped Stage 3 Qt state to document is the code currently on `main`.
- The earlier crashed draft overstated part of the rollout; direct code inspection is authoritative for this pass.
- `docs/assistant/DOCS_REFRESH_NOTES.md` is the durable record for this touched-scope sync.

## 11. Execution log and outcomes
- Code audit outcomes:
  - `codex/core-ui-rollout` resolves to the same SHA as `main` on this machine
  - shared Qt chrome/sizing does extend across the Stage 3 settings/admin/tool surfaces
  - `PrimaryButton` / `DangerButton` usage is still narrower than the earlier draft assumed
  - guarded combo coverage is mixed: main-shell, Gmail review, settings defaults/provider, and Job Log fixed-vocabulary editors use guarded inputs, while glossary/study/tool selectors and dense table editors still rely on plain `QComboBox`
- Files updated:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Executed validations:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
- Final scope check:
  - `docs/assistant/manifest.json` unchanged
  - `docs/assistant/INDEX.md` unchanged
- Completion status:
  - complete; move this ExecPlan to `docs/assistant/exec_plans/completed/`
