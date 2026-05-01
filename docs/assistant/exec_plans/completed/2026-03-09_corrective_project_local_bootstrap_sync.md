# 2026-03-09 Corrective Project-Local Bootstrap Sync

## 1. Title
Correct bootstrap rollback and project-local docs sync

## 2. Goal and non-goals
- Goal: undo the mistaken bootstrap-template and validator edits by restoring the committed bootstrap system from `HEAD`.
- Goal: sync only project-local assistant docs/governance to the current shipped Job Log behavior.
- Goal: preserve the implemented Job Log feature work and avoid unrelated code churn.
- Non-goal: modify bootstrap templates beyond restoring them to `HEAD`.
- Non-goal: introduce new runtime behavior, schema changes, or new governance modules.

## 3. Scope (in/out)
- In:
  - restoring the mistaken bootstrap-template/validator files to `HEAD`
  - removing mistaken roadmap/bootstrap artifacts from the misunderstood pass
  - updating project-local canonical, bridge, support, and Qt UI docs for Job Log edit/delete/resize/scroll behavior
  - adding one corrective docs refresh note
  - closing the Job Log feature ExecPlan if this docs pass completes its lifecycle
- Out:
  - app/runtime/source changes
  - unrelated docs rewrites
  - manifest/index/issue-memory edits unless validation exposes real drift

## 4. Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/joblog-inline-editing`
- base branch: `main`
- base SHA: `674098c`
- target integration branch: `main`
- canonical build status or intended noncanonical override: noncanonical feature branch based on approved base `main`

## 5. Interfaces/types/contracts affected
- Bootstrap template/validator layer returns to the committed `HEAD` contract.
- `APP_KNOWLEDGE.md` and `docs/assistant/APP_KNOWLEDGE.md` gain current-truth coverage for Job Log row editing, deletion, and column-width behavior.
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md` and `docs/assistant/features/APP_USER_GUIDE.md` gain user-facing Job Log guidance for edit/delete/resize/scroll behavior.
- `docs/assistant/QT_UI_PLAYBOOK.md` and `docs/assistant/QT_UI_KNOWLEDGE.md` narrow the no-horizontal-scroll rule so dense data tables like Job Log are an explicit exception.

## 6. File-by-file implementation steps
- Restore the mistaken bootstrap files to `HEAD`:
  - `docs/assistant/templates/BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md`
  - `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
  - `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
  - `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
  - `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md`
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`
- Remove mistaken artifacts:
  - `docs/assistant/templates/BOOTSTRAP_ROADMAP_GOVERNANCE.md`
  - `docs/assistant/exec_plans/active/2026-03-09_bootstrap_template_system_hardening.md`
- Update project-local docs:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/QT_UI_PLAYBOOK.md`
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Move `docs/assistant/exec_plans/active/2026-03-09_joblog_row_inline_editing.md` to `completed/` if validations succeed and the docs sync completes the feature pass.

## 7. Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance:
  - mistaken bootstrap diff is gone
  - roadmap bootstrap artifact files are removed
  - unrelated Job Log implementation changes remain intact
  - project-local docs consistently describe Job Log edit/delete/resize/scroll behavior
  - no blanket local-doc rule still forbids horizontal scroll where Job Log now intentionally uses it

## 8. Rollout and fallback
- Keep rollback scoped to the mistaken bootstrap layer only.
- If validation exposes unexpected local-governance drift, patch only the minimal additional project-local files needed to satisfy the committed bootstrap contract.

## 9. Risks and mitigations
- Risk: rollback accidentally discards unrelated project-local docs work.
  - Mitigation: restore only the listed bootstrap/template/validator files and remove only the two mistaken artifacts.
- Risk: user-facing docs and Qt UI playbook remain inconsistent on scrolling behavior.
  - Mitigation: update both support docs and Qt guidance in the same pass.
- Risk: the active Job Log ExecPlan remains misleading after implementation is already done.
  - Mitigation: move it to `completed/` if this pass closes the remaining docs lifecycle work.

## 10. Assumptions/defaults
- The committed bootstrap system in `HEAD` is the intended source of truth.
- The Job Log implementation already in the worktree is correct and should be documented, not reverted.
- Issue memory is unchanged unless rollback reveals a broader repeated workflow failure.

## 11. Executed validations and outcomes
- Executed validations:
  - `git diff --name-status -- docs/assistant/templates/BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md tooling/validate_agent_docs.dart test/tooling/validate_agent_docs_test.dart` -> no output
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> `All agent docs validator tests passed (48 cases).`
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
- Outcomes:
  - The mistaken bootstrap-template and validator detour was rolled back to the committed `HEAD` bootstrap system.
  - Project-local canonical, bridge, support, and Qt UI docs now reflect the shipped Job Log edit/delete/resize/scroll behavior.
  - This corrective pass is complete and ready to move to `completed/`.
