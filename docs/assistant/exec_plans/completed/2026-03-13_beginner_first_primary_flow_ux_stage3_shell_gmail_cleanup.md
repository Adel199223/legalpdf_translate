# Stage 3 ExecPlan: Beginner-First Shell and Gmail Review Cleanup

## 1. Title
Declutter the main shell defaults and compress the Gmail attachment review surface.

## 2. Goal and non-goals
- Goal:
  - keep the main shell easier to scan for new users by trimming always-visible support copy and hiding non-critical status text
  - keep `Advanced Settings` collapsed by default while leaving expert controls easy to discover
  - compress the Gmail attachment review summary/details so the visible text is shorter and secondary context lives behind info affordances
- Non-goals:
  - no honorários-dialog cleanup yet
  - no persistence, schema, workflow, or Gmail-prepare behavior changes
  - no Stage 4 consistency sweep outside the main shell and Gmail review

## 3. Scope (in/out)
- In:
  - `QtMainWindow` default shell chrome and visible status copy
  - `QtGmailBatchReviewDialog` top summary and detail row copy
  - deterministic render-review metadata for the updated shell and Gmail review surfaces
  - targeted Qt state coverage for the new copy/state contracts
- Out:
  - honorários export dialog consistency pass
  - settings/admin/glossary/study surfaces
  - Gmail preview dialog behavior

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- `QtMainWindow`
  - shell now exposes lightweight info affordances for advanced settings and run-status context
  - run-status copy is shorter (`Run Status`, `ETA ...`)
  - non-critical `Output Format: DOCX` text is hidden from the default view
- `QtGmailBatchReviewDialog`
  - summary is compressed into a short banner plus info tooltip
  - output folder display is shortened to a compact folder label
  - attachment/detail labels and button text are shorter
  - interpretation workflow still hides translation-only controls through the existing state-driven path
- Render-review metadata
  - shell profile sample now records collapsed advanced state, help affordances, shorter status copy, and hidden output-format state
  - Gmail review sample now records compact summary/detail strings and help affordance presence

## 6. File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/app_window.py`
  - add inline help buttons for advanced settings and run status
  - shorten always-visible run-status wording
  - hide the redundant output-format line from the default shell
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - compact the Gmail attachment review summary into a short banner
  - move sender/account/output-folder detail into an info tooltip
  - shorten review table/detail labels and action text
- `tooling/qt_render_review.py`
  - record the new shell and Gmail-review metadata
- `tests/test_qt_render_review.py`
  - assert the new shell/Gmail-review render metadata
- `tests/test_qt_app_state.py`
  - assert the new shell help controls, hidden output-format label, and compact Gmail-review copy

## 7. Tests and acceptance criteria
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_stage_two_shell_smoke tests/test_qt_app_state.py::test_main_window_uses_guarded_run_critical_controls tests/test_qt_app_state.py::test_advanced_settings_hover_and_open_state_stays_local_to_active_combo tests/test_qt_app_state.py::test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang tests/test_qt_app_state.py::test_gmail_batch_review_dialog_interpretation_mode_hides_translation_controls_and_requires_one_attachment tests/test_qt_app_state.py::test_gmail_batch_review_dialog_preview_updates_start_page tests/test_qt_app_state.py::test_gmail_batch_review_dialog_transfers_preview_cache_on_accept tests/test_qt_app_state.py::test_gmail_batch_review_dialog_reject_cleans_preview_cache`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage3_shell_gmail_cleanup --themes dark_futuristic dark_simple --include-gmail-review`
- `dart run tooling/validate_agent_docs.dart`
- Acceptance:
  - the main shell shows less always-visible explanatory/status text by default
  - advanced settings remain collapsed by default and discoverable
  - Gmail review shows shorter visible summary/detail copy without losing message/output context
  - interpretation review stays simpler than translation via the existing visibility rules
  - no Gmail review selection/preview/prepare behavior regresses in targeted coverage

## 8. Rollout and fallback
- Stop after shell and Gmail review validation and publish the stage packet.
- If Stage 4 consistency work reveals stronger reusable patterns, keep these Stage 3 defaults as the floor and iterate only on the remaining honorários-adjacent surfaces.

## 9. Risks and mitigations
- Risk: the shell becomes too minimal and hides expert overrides.
  - Mitigation: advanced settings stay one click away and now include a compact help affordance.
- Risk: Gmail review hides message provenance too aggressively.
  - Mitigation: full sender/account/output details remain available through the summary info tooltip.
- Risk: shorter labels become ambiguous in interpretation mode.
  - Mitigation: the workflow-driven hide/show rules remain unchanged, so interpretation still removes the translation-only controls entirely.

## 10. Assumptions/defaults
- The default shell should privilege active-run state over static explanatory labels.
- Gmail review should show the subject and immediate file context first; provenance and folder detail can move behind help.
- The `Advanced Settings` label stays explicit even if adjacent copy is shortened elsewhere.

## 11. Current status
- Completed.
- Stage completion packet is ready for publication.
- The next step is blocked on the exact user continuation token `NEXT_STAGE_4`.

## 12. Executed validations and outcomes
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
  - PASS
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
  - PASS (`13 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_stage_two_shell_smoke tests/test_qt_app_state.py::test_main_window_uses_guarded_run_critical_controls tests/test_qt_app_state.py::test_advanced_settings_hover_and_open_state_stays_local_to_active_combo tests/test_qt_app_state.py::test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang tests/test_qt_app_state.py::test_gmail_batch_review_dialog_interpretation_mode_hides_translation_controls_and_requires_one_attachment tests/test_qt_app_state.py::test_gmail_batch_review_dialog_preview_updates_start_page tests/test_qt_app_state.py::test_gmail_batch_review_dialog_transfers_preview_cache_on_accept tests/test_qt_app_state.py::test_gmail_batch_review_dialog_reject_cleans_preview_cache`
  - PASS (`8 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage3_shell_gmail_cleanup --themes dark_futuristic dark_simple --include-gmail-review`
  - PASS
  - Updated render artifacts written under `tmp/stage3_shell_gmail_cleanup/`
- `dart run tooling/validate_agent_docs.dart`
  - PASS
