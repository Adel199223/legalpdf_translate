# Stage 4 ExecPlan: Honorários Consistency Pass and Final Primary-Flow Audit

## 1. Title
Finish the beginner-first roadmap by aligning the interpretation honorários dialog with the new declutter patterns and closing the primary-flow audit.

## 2. Goal and non-goals
- Goal:
  - make the interpretation honorários export dialog easier to scan by default without changing export behavior
  - carry the shared disclosure/help patterns through the remaining primary flow so the app feels consistent end-to-end
  - close the roadmap with deterministic render evidence, focused Qt coverage, and a final full-suite attempt
- Non-goals:
  - no cleanup of settings/admin/glossary/study/Profile Manager surfaces
  - no persistence, schema, or workflow-contract changes
  - no redesign of the Word/PDF export pipeline beyond visible copy and layout

## 3. Scope (in/out)
- In:
  - `QtHonorariosExportDialog` interpretation layout and visible wording
  - final render-review metadata for the honorários dialog and refreshed primary-flow bundle
  - final cross-surface validation across shell, Job Log interpretation, Gmail review, and honorários export
  - small safety fix discovered during final validation for interpretation photo autofill null service fields
- Out:
  - secondary/admin surfaces
  - Gmail preview dialog behavior
  - the pre-existing Windows Qt teardown/access-violation issue outside this roadmap

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- `QtHonorariosExportDialog`
  - the interpretation flow now uses sectioned disclosure for `SERVICE`, `TEXT`, and `RECIPIENT`
  - `SERVICE` collapses when redundant and summarizes service date plus location state
  - the recipient block collapses when it is still auto-derived from the case
  - visible helper copy is shorter and secondary detail moves to inline info affordances
  - success/failure message-box copy is shorter
- `QtSaveToJobLogDialog`
  - imported interpretation photo metadata now tolerates missing `service_entity`/`service_city` values instead of crashing during autofill
- Render-review metadata
  - honorários sample now records section states, summaries, help affordances, and shortened interpretation text labels

## 6. File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - refactor the interpretation honorários dialog into a general panel plus declutter sections
  - add state-driven service and recipient summaries/expansion logic
  - shorten visible interpretation wording and success/failure dialog copy
  - harden interpretation imported-service autofill against `None` values
- `tooling/qt_render_review.py`
  - capture honorários section/summarization metadata
- `tests/test_qt_render_review.py`
  - assert the new honorários metadata contract
- `tests/test_qt_app_state.py`
  - add interpretation honorários dialog state tests
  - update one legacy shell assertion to the Stage 3 `Run Status` copy

## 7. Tests and acceptance criteria
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_stage_two_shell_smoke tests/test_qt_app_state.py::test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang tests/test_qt_app_state.py::test_gmail_batch_review_dialog_interpretation_mode_hides_translation_controls_and_requires_one_attachment tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_section_expands_when_location_is_mentioned tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_header_autofill_reveals_distinct_service_location tests/test_qt_app_state.py::test_honorarios_export_dialog_interpretation_defaults_to_collapsed_service_and_recipient_sections tests/test_qt_app_state.py::test_honorarios_export_dialog_service_section_expands_for_explicit_location tests/test_qt_app_state.py::test_honorarios_export_dialog_distinct_service_values_start_expanded tests/test_qt_app_state.py::test_honorarios_export_dialog_recipient_section_expands_after_manual_edit`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage4_primary_flow_final_audit --themes dark_futuristic dark_simple --include-gmail-review`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q`
- `dart run tooling/validate_agent_docs.dart`
- Acceptance:
  - the interpretation honorários dialog shows less default visual weight while keeping all current actions reachable
  - the primary-flow render bundle reflects the new disclosure/help pattern consistently
  - no targeted shell/Gmail/Job Log interpretation regressions appear in focused coverage
  - the only remaining full-suite blocker is the existing Windows Qt access violation outside this roadmap

## 8. Rollout and fallback
- Close the roadmap after this stage.
- If follow-up work is needed, restart under normal ExecPlan flow instead of reopening staged roadmap execution by default.

## 9. Risks and mitigations
- Risk: hiding honorários recipient/service details makes the export feel too opaque.
  - Mitigation: summaries stay visible, help buttons explain the collapsed sections, and validation/errors re-open the needed context.
- Risk: the new dialog height still forces an immediate scroll on small screens.
  - Mitigation: interpretation preferred height increased so the default viewport now shows the main controls without relying on the first scroll.
- Risk: final validation uncovers unrelated pre-existing failures.
  - Mitigation: fix small adjacent defects when low-risk; otherwise record the exact blocker and stop scope creep.

## 10. Assumptions/defaults
- Primary-flow clarity matters more than keeping every optional text block permanently visible.
- The honorários interpretation flow should mirror the Job Log interpretation cleanup rather than invent a separate pattern.
- Secondary/admin surfaces remain intentionally deferred.

## 11. Current status
- Completed.
- The roadmap is closed in this worktree.
- No further `NEXT_STAGE_X` continuation token is required.

## 12. Executed validations and outcomes
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
  - PASS
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
  - PASS (`13 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_stage_two_shell_smoke tests/test_qt_app_state.py::test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang tests/test_qt_app_state.py::test_gmail_batch_review_dialog_interpretation_mode_hides_translation_controls_and_requires_one_attachment tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_section_expands_when_location_is_mentioned tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_header_autofill_reveals_distinct_service_location tests/test_qt_app_state.py::test_honorarios_export_dialog_interpretation_defaults_to_collapsed_service_and_recipient_sections tests/test_qt_app_state.py::test_honorarios_export_dialog_service_section_expands_for_explicit_location tests/test_qt_app_state.py::test_honorarios_export_dialog_distinct_service_values_start_expanded tests/test_qt_app_state.py::test_honorarios_export_dialog_recipient_section_expands_after_manual_edit`
  - PASS (`10 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage4_primary_flow_final_audit --themes dark_futuristic dark_simple --include-gmail-review`
  - PASS
  - Updated render artifacts written under `tmp/stage4_primary_flow_final_audit/`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q`
  - PARTIAL PASS
  - `947` tests completed before the run hit the known Windows Qt access violation in `tests/test_qt_app_state.py::test_save_to_joblog_dialog_return_key_save_shortcut_is_stable_across_repeated_runs`
  - No remaining ordinary assertion failures were left after the Stage 4 updates and the null-safe imported-service fix

## 13. Residual issues outside roadmap scope
- `QtSettingsDialog`, glossary/study tooling, and admin/profile-management surfaces still expose denser expert-facing copy than the primary flows.
- The Job Log table and inline-edit grid remain information-dense by design; this roadmap only simplified the interpretation entry/edit surfaces around it.
- The Windows Qt access violation in the repeated Return-key save-shortcut test remains a separate reliability issue for a future stability pass.
