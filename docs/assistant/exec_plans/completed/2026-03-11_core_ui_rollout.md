# Core UI Rollout

## Goal and non-goals
- Goal: deliver a staged core-first UI rollout with Stage 1 focused on shared interaction stability plus Job Log multi-select and bulk delete.
- Non-goals for Stage 1:
  - app-wide style rollout beyond the Job Log window
  - Gmail review selection redesign
  - review-queue multi-select
  - the deferred out-of-month weekend-color calendar edge case

## Scope (in/out)
- In:
  - `QtJobLogWindow` row selection mode and bulk delete behavior
  - single-row-only action gating in Job Log
  - shared calendar foundation verification (Monday-first stays the only calendar path)
  - Stage 1 evidence and continuation packet
- Out:
  - Stage 2 core dialog/window polish
  - Stage 3 knowledge/admin tools rollout
  - Assistant Docs Sync

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_core_ui_rollout`
- branch name: `codex/core-ui-rollout`
- base branch: `main`
- base SHA: `f3a3850`
- target integration branch: `main`
- canonical build status: noncanonical isolated worktree; expected to use the canonical repo `.venv311`

## Interfaces/types/contracts affected
- Job Log UI contract:
  - row selection becomes extended selection
  - bulk delete is supported
  - honorarios export remains single-row-only
  - inline editing continues to block conflicting row actions
- DB helper contract:
  - add a bulk delete helper for multiple Job Log row IDs in one transaction
- Shared calendar contract:
  - all existing `GuardedDateEdit` popups stay Monday-first

## File-by-file implementation steps
- `src/legalpdf_translate/joblog_db.py`
  - add a multi-row delete helper that deletes a set of IDs in one transaction
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - switch `QtJobLogWindow` to extended row selection
  - add `Delete selected...` toolbar action
  - add shared helpers for selected row indices/IDs and exact-one-row gating
  - wire keyboard `Delete` for bulk deletion when not inline editing
  - preserve per-row delete icons for single-row convenience
- `tests/test_db_migration_joblog_v2.py`
  - add DB-level regression for bulk delete removing only requested rows
- `tests/test_qt_app_state.py`
  - add Job Log multi-select/bulk-delete regressions
  - lock single-row-only honorarios behavior under extended selection

## Tests and acceptance criteria
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_qt_app_state.py`
- `git diff --check`
- Acceptance:
  - Shift/Ctrl row selection works in Job Log
  - bulk delete removes all selected rows with one confirmation
  - inline edit still blocks conflicting actions
  - honorarios button only enables for exactly one selected row

## Rollout and fallback
- Stop after Stage 1 and publish the evidence packet here.
- Require exact continuation token `NEXT_STAGE_2` before any Stage 2 work.

## Risks and mitigations
- Risk: extended selection accidentally breaks single-row-only flows.
  - Mitigation: add exact-one-row helper and explicit button/action gating.
- Risk: keyboard Delete conflicts with inline editors.
  - Mitigation: handle Delete only when not inline editing and when the table itself is active.

## Assumptions/defaults
- Job Log is the only Stage 1 bulk-delete surface.
- Existing extended-selection windows stay unchanged in Stage 1.
- Monday-first calendars are already the shared foundation and only need preservation, not redesign.

## Stage 1 execution status
- Status: completed on `codex/core-ui-rollout`; no Stage 2 work started.
- Changed files:
  - `src/legalpdf_translate/joblog_db.py`
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `tests/test_db_migration_joblog_v2.py`
  - `tests/test_qt_app_state.py`
- Implemented results:
  - Job Log row selection is now `ExtendedSelection`
  - added `Delete selected...` bulk action plus keyboard `Delete` when the table has focus and no inline edit is active
  - per-row delete icons still work for single-row convenience, but now reuse the same shared confirmation/delete path
  - bulk delete removes all selected rows in one DB helper call and one confirmation flow
  - single-row-only actions are explicitly gated:
    - `Gerar Requerimento de Honorários...` only enables for exactly one selected row
    - row double-click inline edit blocks multi-selection conflicts
  - inline edit still hard-locks the active row and disables conflicting actions while editing
  - shared calendar foundation remains Monday-first; no new calendar path was introduced in Stage 1

## Stage 1 validation evidence
- `git diff --check` -> clean
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_db_migration_joblog_v2.py::test_delete_job_runs_removes_only_selected_rows tests/test_qt_app_state.py::test_joblog_window_action_cell_uses_icon_buttons_and_delete_removes_row tests/test_qt_app_state.py::test_joblog_window_honorarios_requires_exactly_one_selected_row tests/test_qt_app_state.py::test_joblog_window_bulk_delete_selected_rows_removes_all_selected_rows tests/test_qt_app_state.py::test_joblog_window_delete_is_blocked_during_inline_edit_and_other_row_actions_disable tests/test_qt_app_state.py::test_joblog_window_delete_key_removes_selected_rows_when_table_has_focus tests/test_qt_app_state.py::test_joblog_window_inline_edit_uses_combo_and_text_editors_and_saves tests/test_qt_app_state.py::test_joblog_window_inline_edit_cancel_restores_values_and_blocks_other_row tests/test_qt_app_state.py::test_joblog_window_edit_action_opens_historical_row_in_edit_mode tests/test_qt_app_state.py::test_joblog_window_interpretation_honorarios_skips_gmail_offer tests/test_honorarios_docx.py -k "joblog_window and honorarios"` -> `12 passed, 38 deselected in 1.32s`

## Locked decisions carried forward
- Job Log is the only Stage 1 bulk-delete surface.
- Review Queue stays single-select.
- Gmail review keeps existing workflow-driven selection semantics.
- Monday-first calendars remain the shared control contract, but the out-of-month weekend-color edge case stays deferred.
- Assistant Docs Sync remains deferred until the later roadmap closeout stage.

## Residual risks / deferred items
- Deferred: out-of-month weekend day coloring in calendar popups (for example visible prior-month weekend cells) is still not fully correct.
- Not yet implemented: Stage 2 rollout of polished combos/buttons/calendars across the core dialogs and windows outside Job Log.
- Not yet implemented: Stage 3 rollout into glossary/calibration/settings-admin surfaces.

## Continuation packet
- Next stage scope: Stage 2 core workflow dialogs/windows only
- Keep Stage 1 behavior stable; do not redesign Job Log selection semantics further unless Stage 2 exposes a concrete regression.
- Exact continuation token: `NEXT_STAGE_2`

## Stage 2 execution status
- Status: completed on `codex/core-ui-rollout`; no Stage 3 work started.
- Additional changed files for Stage 2:
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `tests/test_honorarios_docx.py`
  - `tests/test_qt_app_state.py`
- Stage 2 implementation results:
  - core workflow dialogs/windows now use the shared rounded action hierarchy more consistently:
    - `QtHonorariosExportDialog.generate_btn` -> `PrimaryButton`
    - `QtProfileManagerDialog.save_btn` -> `PrimaryButton`
    - `QtProfileManagerDialog.delete_profile_btn` / `delete_distance_btn` -> `DangerButton`
    - `QtGmailBatchReviewDialog.prepare_btn` -> `PrimaryButton`
    - `QtGmailAttachmentPreviewDialog.use_page_btn` -> `PrimaryButton`
    - per-page preview card `Start from this page` buttons -> `PrimaryButton`
    - `QtReviewQueueDialog.open_page_btn` -> `PrimaryButton`
    - `QtSettingsDialog.save_btn` -> `PrimaryButton`
  - fixed-vocabulary core controls are now explicitly locked as selection-only where they already use shared guarded combos:
    - Gmail review `workflow_combo`
    - Gmail review `target_lang_combo`
    - Settings appearance/default-option combos
    - honorários export `profile_combo`
  - existing shared-control behavior remains intact:
    - Job Log dialog fixed-vocab combos remain guarded/non-editable except `court_email`
    - shared `GuardedDateEdit` remains the calendar path for touched core date fields
    - no new plain-combo/date-widget path was introduced in the Stage 2 windows

## Stage 2 validation evidence
- `git diff --check` -> clean
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_db_migration_joblog_v2.py::test_delete_job_runs_removes_only_selected_rows tests/test_qt_app_state.py::test_joblog_window_bulk_delete_selected_rows_removes_all_selected_rows tests/test_qt_app_state.py::test_joblog_window_honorarios_requires_exactly_one_selected_row tests/test_qt_app_state.py::test_save_to_joblog_dialog_small_screen_uses_scrollable_body_and_collapsed_sections tests/test_qt_app_state.py::test_settings_dialog_uses_guarded_run_critical_controls tests/test_qt_app_state.py::test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang tests/test_qt_app_state.py::test_gmail_attachment_preview_dialog_builds_scroll_cards_and_accepts_selected_page tests/test_qt_app_state.py::test_gmail_attachment_preview_dialog_image_preview_uses_page_one tests/test_qt_app_state.py::test_review_queue_dialog_keeps_single_select_and_primary_open_action tests/test_honorarios_docx.py::test_honorarios_dialog_small_screen_uses_scrollable_body_and_fixed_action_bar tests/test_honorarios_docx.py::test_profile_manager_can_set_primary_and_prevents_last_profile_delete tests/test_qt_main_smoke.py` -> `15 passed in 1.96s`

## Locked decisions carried forward after Stage 2
- Stage 2 stays scoped to the core workflow windows only.
- Review Queue remains single-select.
- Gmail review keeps its existing mixed selection semantics by workflow.
- Settings glossary/study/admin table editors remain out of scope until Stage 3.
- The out-of-month weekend-color calendar edge case remains deferred and is still not a blocker.

## Residual risks / deferred items after Stage 2
- Not yet implemented: Stage 3 rollout into glossary, calibration, and other knowledge/admin surfaces that still use older form/table controls.
- Not yet implemented: Stage 4 docs sync and publish closeout.
- Deferred visual issue remains: out-of-month weekend calendar cells may still not pick up weekend color consistently.

## Continuation packet after Stage 2
- Next stage scope: Stage 3 knowledge/admin tools surfaces only
- Keep the core-window contracts from Stages 1-2 stable; Stage 3 should extend the shared control/style system only where it does not destabilize dense table editors.
- Exact continuation token: `NEXT_STAGE_3`

## Stage 3 execution status
- Status: completed on `codex/core-ui-rollout`; no Stage 4 work started.
- Additional changed files for Stage 3:
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `src/legalpdf_translate/qt_gui/tools_dialogs.py`
  - `tests/test_qt_app_state.py`
  - `tests/test_qt_settings_glossary_editor.py`
  - `tests/test_qt_tools_dialogs_ui.py`
- Stage 3 implementation results:
  - `QtSettingsDialog` now finishes the guarded-control rollout for remaining knowledge/admin selectors:
    - OCR provider/default selectors are explicit non-editable `NoWheelComboBox` controls
    - glossary language/tier selectors are explicit non-editable `NoWheelComboBox` controls
    - study filter/source/mode selectors are explicit non-editable `NoWheelComboBox` controls
    - study coverage and snippet-length selectors are now `NoWheelSpinBox`
  - `QtSettingsDialog` button hierarchy now classifies the remaining Stage 3 actions:
    - `openai_clear_btn`, `ocr_clear_btn`, `glossary_remove_rows_btn`, `glossary_builtin_btn`, `restore_defaults_btn`, and study remove/clear list buttons -> `DangerButton`
    - `study_generate_btn`, `study_add_selected_btn`, `study_copy_to_ai_btn`, and `create_bundle_btn` -> `PrimaryButton`
  - `QtGlossaryEditorDialog.save_btn` now uses `PrimaryButton`
  - `QtGlossaryBuilderDialog` now uses guarded top-level fixed selectors without changing table editors:
    - `source_combo`, `target_lang_combo`, `mode_combo`, and `lemma_effort_combo` -> non-editable `NoWheelComboBox`
    - `generate_btn` / `apply_btn` -> `PrimaryButton`
    - run-folder and PDF remove/clear actions -> `DangerButton`
    - table-embedded scope combos remain plain `QComboBox`
  - `QtCalibrationAuditDialog` now uses guarded numeric selectors without changing table editors:
    - `sample_pages_spin` and `excerpt_chars_spin` -> `NoWheelSpinBox`
    - `run_btn` / `apply_btn` -> `PrimaryButton`
    - table-embedded suggestion scope combos remain plain `QComboBox`

## Stage 3 validation evidence
- `git diff --check` -> clean
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py tests/test_qt_settings_glossary_editor.py tests/test_qt_settings_glossary_table.py tests/test_qt_study_glossary_tab.py tests/test_qt_glossary_builder_diagnostics.py tests/test_qt_tools_dialogs_ui.py` -> `207 passed in 11.84s`

## Locked decisions carried forward after Stage 3
- Stage 3 remains a UI-consistency pass only; no glossary/study/calibration workflow semantics changed.
- Dense table-cell editors stay on their existing table-local combo contract:
  - `GlossaryTableCombo` remains unchanged
  - glossary-builder/calibration suggestion scope combos remain plain `QComboBox`
- Core-window behavior from Stages 1-2 remains locked and should not be reopened during Stage 4 closeout.
- Assistant Docs Sync is still deferred until the closeout/publish stage.

## Residual risks / deferred items after Stage 3
- Not yet implemented: Stage 4 docs-sync and publish closeout.
- Deferred visual issue remains: out-of-month weekend calendar cells may still not pick up weekend color consistently.

## Continuation packet after Stage 3
- Next stage scope: Stage 4 closeout only
- Keep Stage 1-3 UI contracts stable; Stage 4 should be continuity/docs/publish work, not another visual rollout.
- Exact continuation token: `NEXT_STAGE_4`

## Stage 4 execution status
- Status: completed on `codex/core-ui-rollout`.
- Branch/base closeout:
  - preserved the full dirty tree in a reversible snapshot at `C:\Users\FA507\AppData\Local\Temp\core-ui-rollout-snapshot-20260312-063003`
  - fast-forwarded `codex/core-ui-rollout` from `f3a3850` to current local `main` at `1676797`
  - reapplied the staged rollout on top of current `main` and resolved only touched-scope docs overlap
- Commit split:
  - implementation commit: `2c128a4` `feat(qt): roll out guarded controls across core dialogs`
  - docs/closeout commit: pending in the working tree at the time this completed ExecPlan was written
- Stage 4 docs sync scope:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
- Stage 4 validation evidence:
  - `git diff --check` -> clean before and after the base move
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_honorarios_docx.py tests/test_qt_app_state.py tests/test_qt_settings_glossary_editor.py tests/test_qt_settings_glossary_table.py tests/test_qt_study_glossary_tab.py tests/test_qt_glossary_builder_diagnostics.py tests/test_qt_tools_dialogs_ui.py tests/test_qt_main_smoke.py` -> `258 passed in 14.77s`
  - `dart run tooling/validate_agent_docs.dart` -> `PASS`
  - `dart run tooling/validate_workspace_hygiene.dart` -> `PASS`
- Closeout decisions:
  - kept the rollout on one branch but split implementation from docs/continuity updates
  - preserved the Stage 3 dense-editor exception: table-local editors such as `GlossaryTableCombo` and suggestion-scope combos remain plain `QComboBox`
  - did not publish, merge, or delete any worktree as part of this closeout
