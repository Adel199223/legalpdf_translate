# Stage 2 ExecPlan: Beginner-First Interpretation Job Log Cleanup

## 1. Title
Apply the shared declutter primitives to the interpretation Save/Edit Job Log dialog.

## 2. Goal and non-goals
- Goal:
  - make the interpretation Save/Edit Job Log dialog quieter by default for new users
  - collapse the `SERVICE` section when it is redundant and auto-expand it when the service location becomes relevant
  - replace visible `Add...` buttons with compact `+` actions
  - shorten visible interpretation copy and move secondary explanation into info affordances
- Non-goals:
  - no main-shell, Gmail-review, or honorarios-dialog cleanup yet
  - no persistence, schema, or workflow-contract changes
  - no changes to Job Log save payload shape or honorários export handoff

## 3. Scope (in/out)
- In:
  - `QtSaveToJobLogDialog` interpretation-mode section chrome
  - state-driven `SERVICE` section expansion/collapse behavior
  - interpretation autofill handling for distinct imported service data
  - deterministic render-review metadata for the updated interpretation dialog
  - Qt state coverage for the new declutter behavior
- Out:
  - primary shell cleanup
  - Gmail attachment review cleanup
  - honorarios export cleanup beyond Stage 0/1 coverage

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- `QtSaveToJobLogDialog`
  - `SERVICE` now uses `DeclutterSection`
  - `INTERPRETATION` now uses `DeclutterSection`
  - case/service row add actions now use `CompactAddButton`
  - interpretation copy now uses shorter visible labels plus info affordances
- Interpretation autofill behavior
  - distinct imported service entity/city values now break out of the mirror state instead of being discarded while `Service same as Case` is checked
- Render-review metadata
  - interpretation-dialog sample now records section expansion state, section summary text, compact-add object names, and shortened labels

## 6. File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - replace interpretation `SERVICE` and `INTERPRETATION` group boxes with `DeclutterSection`
  - wire compact add buttons into case/service rows
  - add state helpers for default collapse, auto-expansion, summary text, and validation reveal
  - shorten visible interpretation wording and move secondary explanation into info buttons
  - preserve save, autofill, distance reuse, and honorários behavior
- `tooling/qt_render_review.py`
  - extend interpretation-dialog metadata so the new UI state is deterministic and assertable
- `tests/test_qt_app_state.py`
  - cover default collapse, auto-expand triggers, imported distinct service data, compact add buttons, and validation-driven reveal
- `tests/test_qt_render_review.py`
  - assert the updated interpretation-dialog render metadata

## 7. Tests and acceptance criteria
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_edit_joblog_dialog_keeps_header_autofill_available_without_pdf_path tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_mode_hides_translation_only_fields tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_city_switches_to_saved_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_section_expands_when_location_is_mentioned tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_header_autofill_reveals_distinct_service_location tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_validation_error_expands_service_section tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_uses_repaired_legacy_primary_profile_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_save_persists_manual_distance_for_service_city tests/test_qt_app_state.py::test_edit_joblog_dialog_pdf_header_autofill_allows_manual_pdf_pick_when_seed_has_no_pdf tests/test_qt_app_state.py::test_save_to_joblog_dialog_small_screen_uses_scrollable_body_and_collapsed_sections`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage2_joblog_cleanup --themes dark_futuristic dark_simple`
- `dart run tooling/validate_agent_docs.dart`
- Acceptance:
  - `SERVICE` starts collapsed only when it is redundant in interpretation mode
  - `SERVICE` auto-expands when the service location becomes relevant
  - compact add buttons replace the long `Add...` affordance in case/service rows
  - imported distinct service locations are preserved and revealed in interpretation mode
  - interpretation save/autofill/distance/honorários behavior remains unchanged in targeted regression coverage

## 8. Rollout and fallback
- Stop after the interpretation dialog validates and publish the stage packet.
- If later stages expose layout friction, keep the shared primitives and this dialog behavior as the accepted floor and iterate only on the next surfaces.

## 9. Risks and mitigations
- Risk: collapsing `SERVICE` hides an important override path.
  - Mitigation: keep the section header visible at all times, summarize the current state, and auto-expand when the location becomes relevant.
- Risk: imported distinct service values still get lost inside the mirror state.
  - Mitigation: interpretation autofill now breaks out of `Service same as Case` when imported data differs from the case.
- Risk: validation errors feel disconnected from hidden fields.
  - Mitigation: save-path validation now expands the relevant declutter section before showing the error.

## 10. Assumptions/defaults
- The beginner-first default is a collapsed `SERVICE` section when service equals case and location wording is off.
- Auto-expansion is stronger than a prior collapsed default when the location becomes relevant.
- Section summaries should stay short and scannable instead of repeating full field labels.

## 11. Current status
- Completed.
- Stage completion packet is ready for publication.
- The next step is blocked on the exact user continuation token `NEXT_STAGE_3`.

## 12. Executed validations and outcomes
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
  - PASS
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
  - PASS (`13 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_edit_joblog_dialog_keeps_header_autofill_available_without_pdf_path tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_mode_hides_translation_only_fields tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_city_switches_to_saved_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_section_expands_when_location_is_mentioned tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_header_autofill_reveals_distinct_service_location tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_validation_error_expands_service_section tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_uses_repaired_legacy_primary_profile_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_save_persists_manual_distance_for_service_city tests/test_qt_app_state.py::test_edit_joblog_dialog_pdf_header_autofill_allows_manual_pdf_pick_when_seed_has_no_pdf tests/test_qt_app_state.py::test_save_to_joblog_dialog_small_screen_uses_scrollable_body_and_collapsed_sections`
  - PASS (`11 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage2_joblog_cleanup --themes dark_futuristic dark_simple`
  - PASS
  - Updated render artifacts written under `tmp/stage2_joblog_cleanup/`
- `dart run tooling/validate_agent_docs.dart`
  - PASS
