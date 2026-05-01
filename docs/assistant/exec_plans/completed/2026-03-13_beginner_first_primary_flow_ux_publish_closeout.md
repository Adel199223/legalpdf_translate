# Beginner-First Primary-Flow UX Publish Closeout

## Goal
- publish the completed beginner-first primary-flow Qt cleanup as two commits
- archive the closed roadmap artifacts so they do not remain in `active/`
- run a narrow Assistant Docs Sync for the shipped shell, Gmail review, Job Log interpretation, and interpretation honorários UI changes

## Commit plan
1. `feat(qt): declutter beginner-first primary flows`
2. `docs(assistant): sync beginner-first primary-flow UI cleanup`

## Required closeout work
- move the Stage 0-4 roadmap tracker and stage ExecPlans from `docs/assistant/exec_plans/active/` to `completed/`
- rewrite `docs/assistant/SESSION_RESUME.md` into a post-merge-safe non-roadmap state
- update touched-scope assistant docs only:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/QT_UI_KNOWLEDGE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`

## Validation
- `python -m compileall src tests tooling/qt_render_review.py`
- `python -m pytest -q tests/test_qt_render_review.py`
- targeted Qt state slice for shell, Gmail review, Save/Edit Job Log interpretation, and interpretation honorários
- `python tooling/qt_render_review.py --outdir tmp/stage4_primary_flow_final_audit --themes dark_futuristic dark_simple --include-gmail-review`
- `dart run tooling/validate_agent_docs.dart`
- `python -m pytest -q` one final time; document the known Windows Qt access violation if it still reproduces

## Publish/cleanup
- push with upstream creation
- create/update PR to `main`
- merge if required checks are green
- delete merged branch, prune refs, update canonical `main`, and remove the dedicated worktree if clean

## Status
- Completed locally; the branch is validated and ready for push/PR/merge cleanup under the same publish pass.

## Executed validations and outcomes
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m compileall src tests tooling/qt_render_review.py`
  - PASS
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
  - PASS (`13 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py::test_stage_two_shell_smoke tests/test_qt_app_state.py::test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang tests/test_qt_app_state.py::test_gmail_batch_review_dialog_interpretation_mode_hides_translation_controls_and_requires_one_attachment tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_service_section_expands_when_location_is_mentioned tests/test_qt_app_state.py::test_edit_joblog_dialog_interpretation_header_autofill_reveals_distinct_service_location tests/test_qt_app_state.py::test_honorarios_export_dialog_interpretation_defaults_to_collapsed_service_and_recipient_sections tests/test_qt_app_state.py::test_honorarios_export_dialog_service_section_expands_for_explicit_location tests/test_qt_app_state.py::test_honorarios_export_dialog_distinct_service_values_start_expanded tests/test_qt_app_state.py::test_honorarios_export_dialog_recipient_section_expands_after_manual_edit`
  - PASS (`10 passed`)
- `$env:QT_QPA_PLATFORM='offscreen'; & 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage4_primary_flow_final_audit --themes dark_futuristic dark_simple --include-gmail-review`
  - PASS
- `dart run tooling/validate_agent_docs.dart`
  - PASS
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q`
  - PASS (`947 passed`)
