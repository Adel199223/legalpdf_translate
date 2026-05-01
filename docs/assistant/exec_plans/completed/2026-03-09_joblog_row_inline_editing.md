# 2026-03-09 Job Log Row Inline Editing

## 1. Title
Job Log row editing, action icons, delete, and column sizing

## 2. Goal and non-goals
- Goal: allow existing Job Log rows to be edited from the Job Log window via both a per-row full-form editor and row-scoped inline editing.
- Goal: replace text row actions with compact icon actions and add confirmed row deletion.
- Goal: make Job Log columns auto-fit sensibly, remain manually resizable, persist widths, and overflow via horizontal scrolling.
- Goal: preserve stable row identity by updating rows in place.
- Non-goal: add schema migrations or revision-history copies.
- Non-goal: make internal artifact-path fields general inline-edit targets.

## 3. Scope (in/out)
- In:
  - DB update API for existing Job Log rows.
  - DB delete API for existing Job Log rows.
  - Edit mode for `QtSaveToJobLogDialog`.
  - Fixed `Actions` column with compact edit/delete icon controls plus row-scoped save/cancel.
  - Inline editors with combo/text/numeric controls as appropriate.
  - Shared Job Log payload normalization between dialog-save and inline-save.
  - Job Log column-width persistence and horizontal overflow behavior.
  - Small dedicated Job Log action SVG assets.
  - Targeted Qt/DB regression tests.
- Out:
  - Job Log schema changes.
  - New revision/audit history model.
  - Editing artifact paths directly from the table.

## 4. Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/joblog-inline-editing`
- base branch: `main`
- base SHA: `674098c`
- target integration branch: `main`
- canonical build status or intended noncanonical override: noncanonical feature branch based on approved base `main`

## 5. Interfaces/types/contracts affected
- Add `update_job_run(...)` in `src/legalpdf_translate/joblog_db.py`.
- Add `delete_job_run(...)` in `src/legalpdf_translate/joblog_db.py`.
- Extend `JobLogSeed` usage so historical edit mode can operate with missing `pdf_path`.
- Extend `QtSaveToJobLogDialog` constructor/contracts for edit mode and row updates.
- Add shared Job Log payload normalization helpers used by dialog-save and inline-save.
- Extend Job Log settings with persisted per-column widths.
- Extend `QtJobLogWindow` UI contract with a fixed `Actions` column, icon actions, row-scoped inline edit state, and interactive horizontal sizing/scrolling.

## 6. File-by-file implementation steps
- `src/legalpdf_translate/joblog_db.py`
  - add row update API for editable Job Log fields.
  - add row delete API.
  - preserve `output_docx_path` / `partial_docx_path` unless explicit values are supplied.
- `src/legalpdf_translate/user_settings.py`
  - add additive persisted `joblog_column_widths` settings support.
- `resources/icons/dashboard/*.svg`
  - add small edit/delete action icons for Job Log rows.
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - factor shared parsing/normalization for Job Log payloads.
  - add `QtSaveToJobLogDialog` edit mode with update-vs-insert branching.
  - tolerate historical edit rows with no source PDF path.
  - replace text row actions with compact icon actions.
  - add confirmed row delete behavior.
  - switch Job Log sizing away from all-column stretch to interactive widths with horizontal overflow, auto-fit defaults, and persisted widths.
  - keep inline edit save/cancel flow intact.
- `tests/test_column_visibility_persistence.py`
  - add coverage for persisted width settings.
- `tests/test_qt_app_state.py`
  - cover edit-mode dialog behavior, icon actions, delete flow, row save/cancel behavior, width persistence, and create-mode regression.
- `tests/test_honorarios_docx.py`
  - confirm historical Job Log row actions still preserve existing honorarios flow.
- `tests/test_db_migration_joblog_v2.py`
  - cover in-place Job Log row updates, row deletion, and output-path preservation.

## 7. Tests and acceptance criteria
- `python -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_honorarios_docx.py tests/test_qt_app_state.py -k "joblog"`
- Acceptance:
  - existing rows update in place with stable ids.
  - existing rows can be deleted only after confirmation.
  - full dialog edit path opens from Job Log and saves via update.
  - normal rows use compact icon actions instead of text edit buttons.
  - inline edit uses correct widget types and explicit save/cancel.
  - only one row can be inline-edited at a time.
  - Job Log columns auto-fit readable headers, can be manually resized, and overflow via horizontal scrolling.
  - column visibility persistence, width persistence, and honorarios flow remain intact.

## 8. Rollout and fallback
- Keep the feature local to Job Log surfaces.
- If inline editing proves unstable, the full-form pen editor remains the fallback path without data-model churn.

## 9. Risks and mitigations
- Risk: inline widget state drifts from persisted row values.
  - Mitigation: use row-scoped edit snapshots and explicit save/cancel only.
- Risk: dialog edit mode breaks normal Save-to-Job-Log inserts.
  - Mitigation: keep insert and update paths explicit and regression-test create mode.
- Risk: historical rows missing `pdf_path` break autofill controls.
  - Mitigation: disable only header autofill when no PDF path is available and keep other actions enabled when possible.
- Risk: auto-fit widths fight manual widths.
  - Mitigation: apply saved widths after default auto-fit and persist manual resize events.
- Risk: destructive delete action causes accidental row removal.
  - Mitigation: require explicit confirmation before delete.

## 10. Assumptions/defaults
- `translation_date` is editable; `completed_at` remains internal and stable.
- Hidden columns remain non-inline-editable until shown.
- New categorical values should continue to populate existing vocab settings.
- Horizontal scrolling is the intended overflow behavior when visible columns exceed the Job Log viewport.
- No docs sync is performed during implementation unless later requested.

## 11. Executed validations and outcomes
- Executed validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_column_visibility_persistence.py tests/test_qt_app_state.py tests/test_honorarios_docx.py -k "joblog or honorarios or column_visibility"` -> `54 passed, 98 deselected`
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
- Outcomes:
  - Historical Job Log rows can now be edited from the Job Log window through both the full dialog and inline row editing.
  - Job Log rows now support confirmed delete, icon actions, persisted column widths, and horizontal overflow scrolling.
  - Follow-up project-local docs sync completed in the same worktree pass, so this ExecPlan is ready to move to `completed/`.
