# Docs Refresh Notes

Use this file when docs updates are deferred. Append an entry whenever `src/` or `tests/` changes and the user did NOT request a docs refresh.

## Template (copy for new entries)
## YYYY-MM-DD — <branch> (<commit>)
- Files changed:
  - <path>
- Key symbols / entrypoints changed:
  - <file>::<symbol>
- User-visible behavior:
  - <bullet>
- Tests:
  - python -m pytest -q
  - python -m compileall src tests


## Entries
## 2026-03-08 — feat/ai-docs-bootstrap (working tree)
- Files changed:
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/INDEX.md
  - docs/assistant/manifest.json
  - docs/assistant/ISSUE_MEMORY.md
  - docs/assistant/ISSUE_MEMORY.json
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/LOCAL_ENV_PROFILE.local.md
  - docs/assistant/LOCAL_CAPABILITIES.md
  - docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md
  - docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md
  - docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md
  - tooling/validate_agent_docs.dart
  - test/tooling/validate_agent_docs_test.dart
- Key symbols / entrypoints changed:
  - docs/assistant/manifest.json::harness_isolation_and_diagnostics_workflow
  - docs/assistant/manifest.json::test_live_state_isolation_policy
  - docs/assistant/manifest.json::multi_surface_diagnostics_packet_policy
  - tooling/validate_agent_docs.dart::_validateHarnessIsolationAndDiagnostics
- User-visible behavior:
  - Project docs now route host-bound listener isolation and multi-surface diagnostics through a dedicated workflow instead of leaving the rules implicit in thread history.
  - Host-integration preflight now documents listener ownership as part of readiness instead of treating any listener on the expected port as healthy.
  - Issue memory now captures repeated test/live-state contamination and fragmented diagnostics as durable project lessons that can inform future docs sync and UCBS work.
- Tests:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS
  - `dart run test/tooling/validate_workspace_hygiene_test.dart` -> PASS

## 2026-03-07 — feat/gmail-intake-batch-reply (working tree)
- Files changed:
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/ISSUE_MEMORY.md
  - docs/assistant/ISSUE_MEMORY.json
  - docs/assistant/LOCAL_CAPABILITIES.md
  - docs/assistant/LOCAL_ENV_PROFILE.local.md
  - docs/assistant/exec_plans/completed/2026-03-07_gmail_intake_reply_batch_workflow.md
  - docs/assistant/features/APP_USER_GUIDE.md
  - docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md
  - docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md
  - extensions/gmail_intake/README.md
- Key symbols / entrypoints changed:
  - APP_KNOWLEDGE.md::Gmail Intake Batch Workflow
  - docs/assistant/APP_KNOWLEDGE.md::Current-Truth Note
  - docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md::Same-Host Validation Rule
  - docs/assistant/ISSUE_MEMORY.md::workflow-windows-gog-host-auth-preflight
- User-visible behavior:
  - Assistant docs now describe the shipped Windows-only Gmail intake flow from exact-message handoff through supported-attachment review, sequential Save-to-Job-Log confirmation, one honorarios DOCX, and one threaded reply draft.
  - User-facing docs now explain the fail-closed cases for Gmail intake, including bridge/token problems, ambiguous Gmail DOM state, no supported attachments, Save-to-Job-Log cancellation, metadata mismatch, and skipped/failed honorarios finalization.
  - Same-host Gmail preflight docs were tightened because of the new `workflow-windows-gog-host-auth-preflight` issue-memory entry, so WSL keyring-prompt blocks are now documented as `unavailable` host/auth failures instead of passed Windows smoke.
- Tests:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS
  - `dart run test/tooling/validate_workspace_hygiene_test.dart` -> PASS

## 2026-03-08 — feat/gmail-intake-batch-reply (e204376)
- Files changed:
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/features/APP_USER_GUIDE.md
  - docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md
  - docs/assistant/workflows/TRANSLATION_WORKFLOW.md
  - docs/assistant/exec_plans/completed/2026-03-08_gmail_attachment_review_preview_start_page.md
  - docs/assistant/exec_plans/completed/2026-03-08_gmail_attachment_preview_lazy_scroll.md
  - docs/assistant/exec_plans/completed/2026-03-08_gmail_preview_smoothness_prepare_handoff.md
- Key symbols / entrypoints changed:
  - APP_KNOWLEDGE.md::Gmail Intake Batch Workflow
  - APP_KNOWLEDGE.md::gmail_batch_context
  - docs/assistant/features/APP_USER_GUIDE.md::Gmail Intake Batch Replies
  - docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md::Gmail Intake Batch Replies
  - docs/assistant/workflows/TRANSLATION_WORKFLOW.md::gmail_batch_context
- User-visible behavior:
  - Gmail attachment review now supports per-attachment start-page selection with an in-app preview before preparation begins.
  - PDF preview now uses a lazy continuous-scroll viewer with `Use this page as start`, while image attachments remain fixed to page `1`.
  - `Prepare selected attachments` now reuses previously previewed files when possible instead of redownloading them.
  - Gmail run/report context now documents the selected start page for each translated attachment.
- Tests:
  - `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m compileall src tests` -> PASS
  - `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m pytest -q tests/test_qt_app_state.py tests/test_gmail_batch.py tests/test_qt_render_review.py tests/test_run_report.py tests/test_checkpoint_resume.py tests/test_translation_diagnostics.py tests/test_translation_report.py` -> `177 passed`
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
## 2026-03-07 — feat/ai-docs-bootstrap (working tree)
- Files changed:
  - agent.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/exec_plans/PLANS.md
  - docs/assistant/runtime/CANONICAL_BUILD.json
  - docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md
  - docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md
  - docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md
  - docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md
  - docs/assistant/exec_plans/active/2026-03-07_accepted_feature_promotion_canonical_enforcement.md
  - src/legalpdf_translate/build_identity.py
  - tooling/launch_qt_build.py
  - tooling/validate_agent_docs.dart
  - test/tooling/validate_agent_docs_test.dart
  - tests/test_launch_qt_build.py
  - tests/test_qt_app_state.py
- Key symbols / entrypoints changed:
  - docs/assistant/runtime/CANONICAL_BUILD.json::approved_base_branch
  - docs/assistant/runtime/CANONICAL_BUILD.json::approved_base_head_floor
  - src/legalpdf_translate.build_identity.RuntimeBuildIdentity::summary_text
  - tooling/launch_qt_build.py::_build_identity_packet
  - tooling/launch_qt_build.py::main
  - tooling/validate_agent_docs.dart::_validateApprovedBasePromotionDiscipline
- User-visible behavior:
  - The canonical build policy now records the approved base branch/floor explicitly instead of relying only on canonical-worktree memory.
  - Noncanonical side-branch launches are now blocked entirely if the branch does not contain the approved-base floor, even when an override is requested.
  - Governance docs now make merge-immediately-after-acceptance the default lifecycle instead of leaving accepted features stranded on side branches.
- Tests:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_launch_qt_build.py tests/test_qt_main_smoke.py tests/test_qt_app_state.py` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS

## 2026-03-07 — feat/ai-docs-bootstrap (working tree)
- Files changed:
  - agent.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/exec_plans/PLANS.md
  - docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md
  - docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md
  - docs/assistant/exec_plans/active/2026-03-07_commit_push_semantics_hardening.md
  - tooling/validate_agent_docs.dart
  - test/tooling/validate_agent_docs_test.dart
- Key symbols / entrypoints changed:
  - tooling/validate_agent_docs.dart::_validateCommitPushShorthandDiscipline
- User-visible behavior:
  - Governance docs now lock shorthand git semantics so bare `commit` means full pending-tree triage with logical grouped commits, and bare `push` means Push+PR+Merge+Cleanup by default.
  - Commit flows now explicitly require an immediate push suggestion after commit unless the user narrowed scope.
  - Docs maintenance and ExecPlan rules now treat ambiguous commit/push shorthand as a durable workflow concern that must be enforced by validators.
- Tests:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS

## 2026-03-07 — feat/ai-docs-bootstrap (working tree)
- Files changed:
  - agent.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/INDEX.md
  - docs/assistant/exec_plans/PLANS.md
  - docs/assistant/runtime/CANONICAL_BUILD.json
  - docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md
  - docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md
  - docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md
  - docs/assistant/exec_plans/active/2026-03-07_qt_build_identity_hardening.md
  - src/legalpdf_translate/build_identity.py
  - src/legalpdf_translate/qt_app.py
  - src/legalpdf_translate/qt_gui/app_window.py
  - src/legalpdf_translate/qt_gui/dialogs.py
  - tooling/launch_qt_build.py
  - tooling/validate_agent_docs.dart
  - test/tooling/validate_agent_docs_test.dart
  - tests/test_launch_qt_build.py
  - tests/test_qt_app_state.py
  - tests/test_qt_main_smoke.py
- Key symbols / entrypoints changed:
  - src/legalpdf_translate/build_identity.py::detect_runtime_build_identity
  - src/legalpdf_translate.build_identity.RuntimeBuildIdentity::window_title
  - src/legalpdf_translate.qt_gui.dialogs.QtSettingsDialog::_refresh_build_identity
  - tooling/launch_qt_build.py::build_identity_packet
  - tooling/launch_qt_build.py::main
  - tooling/validate_agent_docs.dart::_validateQtLaunchIdentityDiscipline
- User-visible behavior:
  - Existing baseline-discipline docs are now reinforced with a canonical runnable-build policy in `docs/assistant/runtime/CANONICAL_BUILD.json` and a canonical Qt launch helper for ambiguous multi-worktree GUI situations.
  - GUI handoffs must now include worktree path, branch, HEAD SHA, canonical vs noncanonical status, and distinguishing feature labels from the helper-emitted build identity packet.
  - Noncanonical builds now identify themselves in the app via the window title suffix and the Settings diagnostics “Build under test” summary.
  - The durable fix for wrong-window launches is canonical-build enforcement plus helper-emitted build identity, not ad hoc launch narration.
- Tests:
  - `./.venv311/Scripts/python.exe -m compileall src tests tooling` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_launch_qt_build.py` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS
  - `dart run test/tooling/validate_agent_docs_test.dart` -> PASS
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS

## 2026-03-07 — feat/ocr-runtime-stabilization-20260306 (working tree)
- Files changed:
  - agent.md
  - docs/assistant/INDEX.md
  - docs/assistant/manifest.json
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/exec_plans/PLANS.md
  - docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md
  - docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md
  - docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md
  - docs/assistant/exec_plans/active/2026-03-07_worktree_baseline_docs_sync.md
- Key symbols / entrypoints changed:
  - docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md::Handoff Checklist
  - docs/assistant/exec_plans/PLANS.md::Required Plan Template
  - docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md::Handoff Checklist
  - docs/assistant/manifest.json::worktree_baseline_discipline_workflow
- User-visible behavior:
  - Governance docs now require parallel work to start from the latest approved baseline branch/SHA instead of an older convenient worktree base.
  - Active ExecPlans must now record worktree provenance and, for GUI work, the exact build under test.
  - Docs routing now includes a dedicated workflow for preventing mixed-up branches/worktrees and ambiguous app windows.
- Tests:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS

## 2026-03-06 — feat/ocr-runtime-stabilization-20260306 (working tree)
- Files changed:
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/DB_DRIFT_KNOWLEDGE.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/QT_UI_KNOWLEDGE.md
  - docs/assistant/QT_UI_PLAYBOOK.md
  - docs/assistant/features/APP_USER_GUIDE.md
  - docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md
  - docs/assistant/workflows/TRANSLATION_WORKFLOW.md
  - docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md
  - docs/assistant/exec_plans/active/2026-03-06_ocr_runtime_stabilization_auto1.md
  - docs/assistant/exec_plans/active/2026-03-06_safe_ocr_defaults_no_wheel.md
  - docs/assistant/exec_plans/active/2026-03-06_joblog_output_word_count_fix.md
- Key symbols / entrypoints changed:
  - src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.call
  - src/legalpdf_translate/workflow.py::failure_context
  - src/legalpdf_translate/qt_gui/app_window.py::_show_ocr_heavy_runtime_warning
  - src/legalpdf_translate/qt_gui/guarded_inputs.py::NoWheelComboBox
  - src/legalpdf_translate/qt_gui/guarded_inputs.py::NoWheelSpinBox
  - src/legalpdf_translate/qt_gui/dialogs.py::count_words_from_output_artifacts
- User-visible behavior:
  - OCR-heavy runs now use bounded request deadlines and a bounded cooperative `Cancel and wait` flow instead of effectively unbounded waiting.
  - The GUI now offers a non-persistent `Apply safe OCR profile` action for risky OCR-heavy runs and `Switch to fixed high` for the EN/FR xhigh cost/time warning.
  - Run-critical selectors now ignore accidental mouse-wheel changes when closed.
  - Save to Job Log now treats `Words` as translated output words using DOCX-first precedence, which fixes `Words: 0` on successful OCR-heavy runs.
- Tests:
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `556 passed`
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS

## 2026-03-06 — feat/ocr-runtime-stabilization-20260306 (working tree)
- Files changed:
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/INDEX.md
  - docs/assistant/QT_UI_PLAYBOOK.md
  - docs/assistant/manifest.json
  - docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md
  - docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md
  - docs/assistant/workflows/TRANSLATION_WORKFLOW.md
  - docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md
  - docs/assistant/exec_plans/active/2026-03-06_workflow_hardening_ui_ocr.md
  - tooling/qt_render_review.py
  - tooling/ocr_translation_probe.py
  - tooling/validate_agent_docs.dart
  - test/tooling/validate_agent_docs_test.dart
  - tests/test_qt_render_review.py
  - tests/test_ocr_translation_probe.py
- Key symbols / entrypoints changed:
  - tooling/qt_render_review.py::render_profiles
  - tooling/qt_render_review.py::apply_reference_sample
  - tooling/ocr_translation_probe.py::collect_probe_packet
  - tooling/validate_agent_docs.dart::_validateWorkflowDocs
- User-visible behavior:
  - Assistant workflow docs now include a reusable reference-locked Qt UI workflow and a reusable OCR-heavy translation triage workflow.
  - The docs/index/manifest routing now makes those workflows and their helper tools discoverable instead of leaving the lessons only in historical ExecPlans.
  - Internal helper tooling now supports deterministic Qt wide/medium/narrow render review and small-slice OCR-heavy probe packets for urgent document triage.
- Tests:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_render_review.py tests/test_ocr_translation_probe.py tests/test_qt_app_state.py tests/test_workflow_ocr_availability.py` -> `32 passed`
  - `dart run test/tooling/validate_agent_docs_test.dart` -> `29 cases passed`
  - `./.venv311/Scripts/python.exe -m compileall src tests tooling` -> PASS
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS

## 2026-03-06 — chore/import-optmax-2026-03-05 (85250eb + working tree)
- Files changed:
  - src/legalpdf_translate/qt_app.py
  - src/legalpdf_translate/qt_gui/app_window.py
  - src/legalpdf_translate/qt_gui/styles.py
  - tests/test_qt_app_state.py
  - tests/test_qt_main_smoke.py
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/QT_UI_KNOWLEDGE.md
  - docs/assistant/QT_UI_PLAYBOOK.md
  - docs/assistant/INDEX.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/features/APP_USER_GUIDE.md
  - docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md
  - docs/assistant/exec_plans/active/2026-03-05_ui_screenshot_match_rollout.md
- Key symbols / entrypoints changed:
  - src/legalpdf_translate/qt_app.py::run
  - src/legalpdf_translate/qt_app.py::__main__ guard
  - src/legalpdf_translate/qt_gui/app_window.py::QtMainWindow
  - src/legalpdf_translate/qt_gui/app_window.py::_apply_responsive_layout
  - src/legalpdf_translate/qt_gui/app_window.py::_refresh_lang_badge
  - src/legalpdf_translate/qt_gui/app_window.py::_install_overflow_menu
- User-visible behavior:
  - The Qt desktop shell now uses the screenshot-driven dashboard layout with a left sidebar, centered hero title, setup/output cards, and bottom action rail.
  - The GUI launch path is now documented correctly as `python -m legalpdf_translate.qt_app`, and the module can be run directly because `qt_app.py` now has a `__main__` guard.
  - Assistant docs now reflect the real visible menu split: `...` for output/report actions, `Tools` for Review Queue and Save to Job Log.
- Tests:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `508 passed`

## 2026-03-05 — chore/import-optmax-2026-03-05 (d29c163)
- Files changed:
  - APP_KNOWLEDGE.md
  - docs/assistant/APP_KNOWLEDGE.md
  - docs/assistant/DB_DRIFT_KNOWLEDGE.md
  - docs/assistant/DOCS_REFRESH_NOTES.md
  - docs/assistant/INDEX.md
  - docs/assistant/QT_UI_KNOWLEDGE.md
  - docs/assistant/audits/RELIABILITY_SIGNOFF_2026-03-05.md
  - docs/assistant/exec_plans/active/2026-03-05_assistant_docs_sync_catchup.md
  - docs/assistant/exec_plans/active/2026-03-05_ocr_first_stage_rollout.md
  - docs/assistant/exec_plans/active/2026-03-05_product_workflow_benchmark_upgrade.md
  - docs/assistant/exec_plans/active/2026-03-05_remaining_top5_stage_rollout.md
  - docs/assistant/features/APP_USER_GUIDE.md
  - docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md
  - docs/assistant/workflows/TRANSLATION_WORKFLOW.md
- Key symbols / entrypoints changed:
  - docs-only sync for shipped features through final signoff `d29c163`
- User-visible behavior:
  - Synced assistant docs for cost guardrails, job-log auto-sync, quality risk/review export, review queue GUI, OCR advisor backend + GUI, queue runner + failed-only rerun, and final queue hardening/signoff.
  - Preserved dated benchmark/audit packets as historical snapshots instead of rewriting them as current state.
- Tests:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `497 passed`

## 2026-02-17 — fix/qt-settings-claude-guardrails (eb6f84e)
- Files changed:
  - CLAUDE.md
  - src/legalpdf_translate/qt_gui/app_window.py
  - src/legalpdf_translate/qt_gui/dialogs.py
  - tests/test_qt_app_state.py
- Key symbols / entrypoints changed:
  - src/legalpdf_translate/qt_gui/app_window.py::<fill using the command in step 2>
  - src/legalpdf_translate/qt_gui/dialogs.py::<fill using the command in step 2>
  - tests/test_qt_app_state.py::<fill using the command in step 2>
- User-visible behavior:
  - Qt settings UI/app-state behavior adjusted (see commit eb6f84e).
  - Coding-agent guardrails updated in CLAUDE.md (token efficiency + triggers + safety).
- Tests:
  - python -m pytest -q (443 passed)
  - python -m compileall src tests (success)

## 2026-02-17 — Migrated legacy log entries from UPDATE_POLICY.md
Date: 2026-02-13
Code change summary:
- Finalized Arabic DOCX RTL output handling in `src/legalpdf_translate/docx_writer.py` with run-level directional segmentation, RTL paragraph defaults, and placeholder cleanup before write.
- Added regression coverage for mixed RTL/LTR output and isolate-control stripping in `tests/test_docx_writer_rtl.py`.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, I, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - added Example 9)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 121 passed in 5.24s
- python -m compileall src tests -> success
- git status --short -- src tests -> M src/legalpdf_translate/docx_writer.py; ?? tests/test_docx_writer_rtl.py

Date: 2026-02-13
Code change summary:
- Added minimal glossary enforcement for AR legal phrasing with file-based JSON rules and built-in defaults (`src/legalpdf_translate/glossary.py`).
- Integrated glossary loading/application into workflow output finalization and added config wiring across Qt settings, CLI, and checkpoint fingerprinting.
- Added regression coverage for glossary behavior, workflow integration, CLI precedence, settings defaults, and resume compatibility.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 132 passed in 6.88s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added per-language glossary table support with normalization helpers and prompt formatting in `src/legalpdf_translate/glossary.py`.
- Added settings schema support for `glossaries_by_lang` + one-time AR seed tracking in `src/legalpdf_translate/user_settings.py`.
- Added a dedicated Glossary tab in Qt Settings with language selector and editable source/target/match rows in `src/legalpdf_translate/qt_gui/dialogs.py`.
- Added workflow glossary prompt injection via `src/legalpdf_translate/workflow.py::_append_glossary_prompt` while keeping legacy deterministic fallback behavior.
- Added regression tests for glossary normalization, settings migration/roundtrip, prompt injection, and glossary-table UI logic.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 156 passed in 5.99s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Updated glossary entry schema to source-keyed canonical fields with per-row source language (`source_text`, `preferred_translation`, `match_mode`, `source_lang`) in `src/legalpdf_translate/glossary.py`.
- Switched workflow glossary enforcement to prompt-only guidance and added source-language detection/filtering in `src/legalpdf_translate/workflow.py` (`_append_glossary_prompt` path); removed blind post-output glossary rewriting from `_evaluate_output`.
- Updated Qt Settings Glossary tab table to include `Source lang` and renamed source column to `Source phrase (PDF text)` in `src/legalpdf_translate/qt_gui/dialogs.py`.
- Updated settings normalization/seeding compatibility for the new schema and seed versioning in `src/legalpdf_translate/user_settings.py`.
- Extended glossary/settings/workflow/Qt-table tests for source-language-aware behavior and backward-compatible migration.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 160 passed in 4.86s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added tiered glossary entries (`tier` 1..6), per-target active tiers, tier-aware prompt filtering/sorting/capping, and backward-compatible tier migration defaults.
- Added searchable glossary UI with `Ctrl+F`, tier selector view, active tier checkboxes, tier counts, and non-blocking glossary hygiene warnings in Settings.
- Added workflow tier-aware token-efficient glossary injection (active tiers only, sorted, capped at 50 entries / 6000 chars).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 173 passed in 5.09s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added learning-only Study Glossary core logic in `src/legalpdf_translate/study_glossary.py` (term mining, scoring, 20-80 coverage selection, merge helpers, language expansion, review-date helpers, translation fill helper).
- Added Study Glossary settings schema + normalization in `src/legalpdf_translate/user_settings.py` (`study_glossary_entries`, snippets/corpus/coverage keys).
- Added a dedicated Study Glossary settings tab in `src/legalpdf_translate/qt_gui/dialogs.py` with run-folder builder, search/filters, suggestions table, review statuses, and translation refresh/quiz actions.
- Added regression tests for Study Glossary algorithm/settings/prompt isolation and Qt method-level table behaviors.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, F, J)
- docs/assistant/PROJECT_INSTRUCTIONS.txt (routing rule for Study Glossary)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 194 passed in 5.20s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Hardened Study Glossary coverage to use non-overlapping longest-match assignment (`tri->bi->uni`) in `src/legalpdf_translate/study_glossary.py` (`tokenize_pt`, `build_ngram_index`, `count_non_overlapping_matches`, `compute_non_overlapping_tier_assignment`).
- Added subsumption suppression for noisy short suggestions (`apply_subsumption_suppression`) and wired deterministic coverage+tiering in Study Glossary candidate finalization path (`src/legalpdf_translate/qt_gui/dialogs.py::_on_study_candidate_finished`).
- Added content-only Markdown export for consistency glossary in Qt settings (`src/legalpdf_translate/qt_gui/dialogs.py::_export_consistency_glossary_markdown`, `src/legalpdf_translate/glossary.py::build_consistency_glossary_markdown`).
- Kept consistency glossary dynamic language expansion robust by making `serialize_glossaries(...)` accept caller-provided supported languages and using that in `src/legalpdf_translate/user_settings.py::load_gui_settings`.
- Added regression coverage for non-overlapping coverage behavior, subsumption demotion, consistency export format, future-language glossary expansion, and prompt-isolation lock tests.

Docs updated:
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 205 passed in 5.10s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added Study Glossary corpus source modes in Qt settings (`run_folders`, `current_pdf`, `select_pdfs`, `joblog_runs` unavailable) with persisted settings keys and UI state/validation paths.
- Wired active main-window PDF into settings dialog (`src/legalpdf_translate/qt_gui/app_window.py::_open_settings_dialog`) for `Current PDF only` Study corpus mode.
- Extended Study candidate worker inputs in `src/legalpdf_translate/qt_gui/dialogs.py::_StudyCandidateWorker` to support direct PDF sources while preserving streaming/cancel behavior and keeping Study prompt-isolated.
- Added optional manual `Copy selected to AI Glossary...` action in Study tab with explicit confirmation, defaults (`exact`, `PT`, `tier 2`), duplicate-skip behavior, and conflict skip/replace prompt.
- Added regression tests for new study settings keys/normalization, corpus source input resolution, and Study-to-AI merge semantics.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: F)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 211 passed in 5.37s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Added integrated consistency Glossary Builder and Calibration Audit backends:
  - `src/legalpdf_translate/glossary_builder.py` (frequency mining, thresholds, deterministic suggestions, markdown/json rendering).
  - `src/legalpdf_translate/calibration_audit.py` (deterministic sampling, forced OCR comparison path, verifier JSON retry handling, audit artifacts).
- Added project+personal consistency glossary scope support and merge helpers in `src/legalpdf_translate/glossary.py` (`load_project_glossaries`, `merge_glossary_scopes`, `save_project_glossaries`) and wired runtime merge in `src/legalpdf_translate/workflow.py::TranslationWorkflow.run`.
- Added optional per-language prompt addendum path (`prompt_addendum_by_lang`) with deterministic append marker block in `src/legalpdf_translate/workflow.py::_append_prompt_addendum`.
- Added Qt actions/dialogs for both tools in:
  - `src/legalpdf_translate/qt_gui/app_window.py` (`Glossary Builder...`, `Calibration Audit...`)
  - `src/legalpdf_translate/qt_gui/tools_dialogs.py` (`QtGlossaryBuilderDialog`, `QtCalibrationAuditDialog`, worker/cancel/progress/apply flows).
- Kept Study Glossary prompt-isolated and consistency prompt injection path unchanged (`_append_glossary_prompt` still consumes only consistency glossary source).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (builder/audit architecture + settings/scope merge + addendum + navigation entries)
- docs/assistant/API_PROMPTS.md (addendum insertion + calibration verifier prompt/retry templates)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 218 passed in 5.79s
- python -m compileall src tests -> success
- git status --short -- src tests -> modified/untracked files present for this in-progress change set

Date: 2026-02-13
Code change summary:
- Implemented OCR auto-mode quality routing in `src/legalpdf_translate/workflow.py` with `classify_extracted_text_quality(...)`, explicit `ocr_request_reason` (`required|helpful|not_requested`), and conservative signal-based helpful detection.
- Switched OCR initialization to lazy on-demand preflight (no run-start preflight), added `ocr_preflight_checked` tracking, and added explicit events `ocr_preflight_checked`, `ocr_required_but_unavailable`, `ocr_helpful_but_unavailable`.
- Enforced cost guardrail for helpful OCR: local-only attempts in auto mode; if unavailable, direct-text fallback with info-only event and `ocr_failed_reason="helpful_unavailable"`.
- Extended summary/report payloads in `src/legalpdf_translate/workflow.py` and `src/legalpdf_translate/run_report.py` with additive OCR fields (`ocr_required_pages`, `ocr_helpful_pages`, `ocr_preflight_checked`) and non-misleading warning semantics.
- Added deterministic OCR routing coverage in `tests/test_workflow_ocr_routing.py` and expanded `tests/test_run_report.py` for required-vs-helpful unavailable reporting behavior.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: D, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - added Example 12)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 232 passed in 5.50s
- python -m compileall src tests -> success
- git status --short -- src tests -> M src/legalpdf_translate/ocr_engine.py; M src/legalpdf_translate/run_report.py; M src/legalpdf_translate/workflow.py; M tests/test_run_report.py; ?? tests/test_workflow_ocr_routing.py

Date: 2026-02-13
Code change summary:
- Hardened Arabic sensitive-value locking in `src/legalpdf_translate/arabic_pre_tokenize.py` by tokenizing full `Nome`/`Morada`/`IBAN`/case-value spans as single `[[...]]` tokens and adding `extract_locked_tokens(...)`.
- Extended Arabic normalization in `src/legalpdf_translate/output_normalize.py` with deterministic expected-token auto-fix before isolate wrapping (`normalize_output_text_with_stats`, `autofix_expected_ar_tokens`).
- Extended `src/legalpdf_translate/validators.py::validate_ar` to accept `expected_tokens` and fail on locked-token mismatch with count diagnostics (`missing_count`, `altered_count`, `unexpected_count`).
- Wired expected-token enforcement through `src/legalpdf_translate/workflow.py` for both initial and retry evaluation, with diagnostics-only events `ar_locked_token_autofix_applied` and `ar_locked_token_violation`.
- Hardened Arabic system prompt constraints in `resources/system_instructions_ar.txt` with explicit label-value preservation examples and anti-splitting guidance for Word-stable LTR runs.
- Added/updated regression coverage for pretokenization locks, normalize/validator enforcement, workflow auto-fix/fail behavior, and RTL DOCX mixed-direction stability.

Docs updated:
- docs/assistant/API_PROMPTS.md (sections: A, E)
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - added Example 13)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 243 passed in 5.72s
- python -m compileall src tests -> success
- git status --short -- src tests -> M src/legalpdf_translate/arabic_pre_tokenize.py; M src/legalpdf_translate/output_normalize.py; M src/legalpdf_translate/validators.py; M src/legalpdf_translate/workflow.py; M tests/test_docx_writer_rtl.py; M tests/test_output_normalize.py; M tests/test_validators_ar.py; ?? tests/test_arabic_pre_tokenize.py; ?? tests/test_workflow_ar_token_lock.py

Date: 2026-02-13
Code change summary:
- Split shared EN/FR system instructions into language-specific resources:
  - `resources/system_instructions_en.txt` (new)
  - `resources/system_instructions_fr.txt` (new)
- Updated `src/legalpdf_translate/resources_loader.py::load_system_instructions` routing:
  - EN -> `system_instructions_en.txt`
  - FR -> `system_instructions_fr.txt`
  - AR unchanged -> `system_instructions_ar.txt`
- Updated `src/legalpdf_translate/prompt_builder.py::build_retry_prompt` to include language-specific retry compliance hints for EN/FR while keeping wrapper markers and payload shape unchanged.
- Added/updated tests:
  - `tests/test_resources_loader.py` (new)
  - `tests/test_resource_path_resolution.py`
  - `tests/test_prompt_builder.py`
- Updated prompt-contract docs/pointers:
  - `docs/assistant/API_PROMPTS.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/CODEX_PROMPT_FACTORY.md` (added worked EN/FR hardening example)

Verification commands/results:
- python -m pytest -q tests/test_resource_path_resolution.py tests/test_resources_loader.py tests/test_prompt_builder.py -> 9 passed in 0.08s
- python -m pytest -q -> 252 passed in 5.71s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Added Portuguese month-date token classifier `is_portuguese_month_date_token(...)` in `src/legalpdf_translate/arabic_pre_tokenize.py`.
- Updated Arabic workflow enforcement in `src/legalpdf_translate/workflow.py::_process_page` to keep strict token-lock for sensitive values while excluding Portuguese month-name date tokens from strict expected-token matching.
- Added deterministic AR date normalization in `src/legalpdf_translate/output_normalize.py`:
  - recognized month-name dates (`[[10 de fevereiro de 2026]]` or plain `10 de fevereiro de 2026`) normalize to `[[10]] فبراير [[2026]]`,
  - uncertain month parsing falls back to one protected token `[[...]]`,
  - slash dates remain single-token style.
- Updated Arabic instruction contract in `resources/system_instructions_ar.txt` to remove date-rule contradiction and define month-name date behavior + fallback.
- Added/updated tests for month-date classification, AR date normalization/fallback, workflow token-lock compatibility for month-date transformation, and DOCX mixed-direction date stability.

Docs updated:
- docs/assistant/API_PROMPTS.md (sections: A, E)
- docs/assistant/APP_KNOWLEDGE.md (sections: C, D, J)
- docs/assistant/CODEX_PROMPT_FACTORY.md (sections: 2 - updated Example 13)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_arabic_pre_tokenize.py tests/test_output_normalize.py tests/test_workflow_ar_token_lock.py tests/test_docx_writer_rtl.py -> 24 passed in 1.07s
- python -m pytest -q -> 259 passed in 6.89s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Fixed EN/FR Portuguese month-date leakage by extending `src/legalpdf_translate/output_normalize.py` normalization:
  - Added deterministic PT month-name date conversion for EN (`10 February 2026`) and FR (`10 février 2026`) in `normalize_output_text_with_stats`.
  - Kept slash numeric dates unchanged.
  - Kept unknown/typo month names unchanged (non-fatal).
- Kept AR/RTL behavior unchanged; AR date/token-lock path remains isolated.
- Updated EN/FR system instruction contracts:
  - `resources/system_instructions_en.txt`: removed dates from verbatim-only list and added explicit month-name date translation rule + example.
  - `resources/system_instructions_fr.txt`: removed dates from verbatim-only list and added explicit month-name date translation rule + example.
- Added/updated regression tests:
  - `tests/test_output_normalize.py` for EN/FR month-date conversion, slash-date unchanged, unknown-month unchanged.
  - `tests/test_resources_loader.py` assertions for updated EN/FR instruction content.

Docs updated:
- docs/assistant/API_PROMPTS.md (section: E normalization contract)
- docs/assistant/APP_KNOWLEDGE.md (section: D pipeline normalization notes)
- docs/assistant/CODEX_PROMPT_FACTORY.md (section: 2 - added Example 15)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_output_normalize.py tests/test_resources_loader.py tests/test_prompt_builder.py -> 24 passed in 0.09s
- python -m pytest -q -> 263 passed in 6.02s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Extended EN/FR date normalization in `src/legalpdf_translate/output_normalize.py` from year-only month-name dates to both forms:
  - `DD de <PT_MONTH> de YYYY`
  - `DD de <PT_MONTH>`
  with deterministic conversion to EN (`DD Month [YYYY]`) and FR (`DD mois [YYYY]`), while preserving slash numeric dates.
- Kept AR date/token-lock behavior unchanged and isolated.
- Extended `src/legalpdf_translate/validators.py::validate_enfr` to support `lang`-aware month-date leak checks after normalization, with address-context exemptions to avoid false positives (e.g., `Rua 1.º de Dezembro`).
- Wired EN/FR validator language context through:
  - `src/legalpdf_translate/workflow.py::_evaluate_output`
  - `src/legalpdf_translate/calibration_audit.py`
  - `src/legalpdf_translate/study_glossary.py`
- Updated EN/FR system instructions to:
  - translate institution/court names when stable equivalents exist,
  - keep originals only when uncertain/no stable equivalent,
  - allow dual form only for acronyms (first mention),
  - include anti-calque guidance (`illustre défenseur`, `office de notification`).
- Added/updated tests:
  - `tests/test_output_normalize.py` (no-year month-date conversion + address no-rewrite)
  - `tests/test_validators_enfr.py` (leak rejection + address exemption + legacy no-lang behavior)
  - `tests/test_retry_reason_mapping.py` (workflow evaluate pass/fail for EN/FR month-date guardrail)
  - `tests/test_resources_loader.py` (new EN/FR instruction policy assertions)

Docs updated:
- docs/assistant/API_PROMPTS.md (section: E validator + normalization contract)
- docs/assistant/APP_KNOWLEDGE.md (section: D pipeline validation/normalization notes)
- docs/assistant/CODEX_PROMPT_FACTORY.md (section: 2 - updated Example 15 acceptance criteria)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_output_normalize.py tests/test_validators_enfr.py tests/test_resources_loader.py tests/test_prompt_builder.py -> 33 passed in 0.11s
- python -m pytest -q -> 271 passed in 6.02s
- python -m compileall src tests -> success

Date: 2026-02-13
Code change summary:
- Aligned Arabic prompt contract in `resources/system_instructions_ar.txt` for institution/court/prosecution naming:
  - translate full names to Arabic when a stable equivalent exists (default),
  - keep Portuguese full names only when uncertain/no stable equivalent,
  - allow dual form only for acronyms on first mention,
  - removed deprecated forced full-name bilingual template rule.
- Extended AR resource contract test in `tests/test_resources_loader.py` to assert the new naming-policy text and absence of the old mandatory dual template line.
- Updated prompt/docs references for this AR naming policy:
  - `docs/assistant/API_PROMPTS.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/CODEX_PROMPT_FACTORY.md` (added Example 16)

Verification commands/results:
- python -m pytest -q tests/test_resources_loader.py tests/test_prompt_builder.py -> 8 passed in 0.05s
- python -m pytest -q -> 271 passed in 5.81s
- python -m compileall src tests -> success

Date: 2026-02-14
Code change summary:
- Added `openai_reasoning_effort_lemma` setting (medium/high, default medium) in `src/legalpdf_translate/user_settings.py` with coercion validation.
- Added "Translation effort" / "Lemma / utility effort" dropdowns in Settings dialog (`src/legalpdf_translate/qt_gui/dialogs.py`).
- Added `effort` parameter to `translate_term_for_lang` and `fill_translations_for_entry` in `src/legalpdf_translate/study_glossary.py`, wired through Study translation worker.
- Created `src/legalpdf_translate/lemma_normalizer.py` with `LemmaCache` (persistent JSON cache), `LemmaBatchResult`, and `batch_normalize_lemmas` (batch OpenAI API normalization with surface-form fallback).
- Extended `src/legalpdf_translate/glossary_diagnostics.py::GlossaryDiagnosticsAccumulator` with `set_lemma_mapping()` and lemma-grouped PKG Pareto computation in `finalize_pkg_pareto()`.
- Extended Glossary Builder dialog/worker (`src/legalpdf_translate/qt_gui/tools_dialogs.py`) with opt-in lemma grouping checkbox, lemma normalization phase after page scanning, and `lemma_normalization_summary` event emission.
- Extended `src/legalpdf_translate/run_report.py` with lemma normalization subsection rendering and lemma-grouped PKG Pareto table (surface forms column).
- Added `tests/test_effort_settings.py` (6 tests) and `tests/test_lemma_normalizer.py` (22 tests).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: C, F, G, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_effort_settings.py tests/test_lemma_normalizer.py -> 28 passed
- python -m pytest -q -> 355 passed in 7.98s
- python -m compileall src tests -> success

Date: 2026-02-14
Code change summary:
- Enhanced translation admin run report with Document Coverage Proof table, enriched event emitters, per-page cost breakdown, numeric mismatch samples, and strengthened sanity warnings.
- Enriched `emit_run_config_event()` with `effort_resolved`, `page_breaks`, `workers`, `resume` params in `src/legalpdf_translate/translation_diagnostics.py`.
- Enriched `emit_validation_summary_event()` with `numeric_missing_sample`, `source_paragraphs`, `output_paragraphs`, `bidi_control_count`, `replacement_char_count`.
- Enriched `emit_docx_write_event()` with `paragraph_count`, `run_count`.
- Added `stats` parameter to `assemble_docx()` in `src/legalpdf_translate/docx_writer.py` for paragraph/run counting (non-breaking).
- Added `prompt_build_ms` timing and enriched `api_call_done` events with `model`/`effort_used` in `src/legalpdf_translate/workflow.py`.
- Enriched per-page rollup extraction with `extracted_text_chars`, `extracted_text_lines`, `prompt_build_ms`, `attempt1_effort`, `attempt2_effort`.
- Enhanced `_render_translation_diagnostics_markdown()` with Document Coverage Proof table, numeric mismatch samples, Output Construction paragraph/run counts, per-page cost breakdown.
- Strengthened Sanity Warnings with rollup/pages_processed mismatch and api_calls/tokens consistency checks.
- Gated legacy Per-Page Rollups section (only shows when no translation diagnostics present).
- Added `tests/test_translation_report.py` (11 tests).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: G, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_translation_report.py -> 11 passed in 0.59s
- python -m pytest -q -> 366 passed in 7.14s
- python -m compileall src tests -> success

Date: 2026-02-14
Code change summary:
- Filled remaining gaps in translation admin run report: wrapper heading `## Translation Diagnostics` with `### A–F` lettered sub-sections.
- Added `keep_intermediates` to `emit_run_config_event()` in `translation_diagnostics.py`; capped `numeric_missing_sample` to 3.
- Passed `keep_intermediates=getattr(config, "keep_intermediates", True)` in `workflow.py`.
- Enhanced `run_report.py::_render_translation_diagnostics_markdown()`: wrapper heading, heading demotion, Route Reason ("Why") column in Coverage Proof table, chunking note (1 chunk per page), flagged page snippets gated to quality warnings (truncated 120 chars), text-only pipeline note in Output Construction, max_output_tokens/temperature as "API default" in Run Config.
- Added 2 new sanity checks: status=completed but timeline empty, done_pages < total_pages (gated on per_page_count > 0).
- Added `report_sanity_summary` to payload for programmatic consumers.
- Gated legacy Sanitized Snippets section when translation diagnostics present.
- Updated `tests/test_translation_report.py`: 20 tests (11 updated + 9 new covering wrapper heading, route reason, sanity warnings, numeric cap, snippet gating, text-only note, chunking note, report_sanity_summary in payload).
- Updated `tests/test_translation_diagnostics.py` and `tests/test_qt_glossary_builder_diagnostics.py` heading assertions.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: G, J)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q tests/test_translation_report.py -> 20 passed in 1.19s
- python -m pytest -q -> 375 passed in 8.87s
- python -m compileall src tests -> success

Date: 2026-02-14
Code change summary:
- Fixed hardcoded zero totals in Glossary Builder run_summary — lemma API token usage (input/output/total, API calls) now populates from `self._lemma_result` in `src/legalpdf_translate/qt_gui/tools_dialogs.py`.
- Added `compute_selection_metadata()` to `src/legalpdf_translate/glossary_builder.py` — pure function reporting TF/DF filter pipeline stats (candidates, thresholds, pass counts, final count, cap policy).
- Wired selection metadata through worker → dialog → `suggestion_selection_summary` event in `src/legalpdf_translate/qt_gui/tools_dialogs.py`.
- Added "Suggestion Selection Diagnostics" section in `src/legalpdf_translate/run_report.py` rendering TF/DF filtering pipeline with explicit analytics-only note for lemma grouping.
- Added analytics-only note to Lemma Normalization section in report.
- Expanded `openai_reasoning_effort_lemma` allowed values to include `xhigh` and changed default from `medium` to `high` in `src/legalpdf_translate/user_settings.py`.
- Added effort dropdown (`high`/`xhigh`) next to lemma checkbox in Glossary Builder dialog and updated Settings dialog combo in `src/legalpdf_translate/qt_gui/dialogs.py`.
- Added/updated tests: `tests/test_glossary_builder.py` (selection metadata), `tests/test_effort_settings.py` (default/invalid/xhigh), `tests/test_qt_glossary_builder_diagnostics.py` (lemma tokens, suggestion selection section, analytics-only note).

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (sections: F, G)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 380 passed in 12.54s
- python -m compileall src tests -> success

Date: 2026-02-14
Code change summary:
- Replaced layout-invalidation approach with QScrollArea in all three Qt dialogs to fix controls collapsing to 1-2px, empty space after Show Advanced toggle, and clipped/inaccessible buttons.
- Main window (`src/legalpdf_translate/qt_gui/app_window.py`): wrapped content_card in transparent QScrollArea; changed vertical policy from `Maximum` to `Preferred`; simplified `_refresh_canvas()` to repaint-only (no layout hacks).
- Glossary Builder (`src/legalpdf_translate/qt_gui/tools_dialogs.py`): wrapped all content in QScrollArea; kept column stretches `(1,0,0,0)`.
- Settings dialog (`src/legalpdf_translate/qt_gui/dialogs.py`): wrapped tabs+buttons in QScrollArea.
- Added dark-theme QScrollBar styling in `src/legalpdf_translate/qt_gui/styles.py`.

Docs updated:
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 396 passed in 7.95s
- python -m compileall src tests -> success

Date: 2026-02-15
Code change summary:
- Added Inno Setup installer script (`installer/legalpdf_translate.iss`): per-user install, stable AppId GUID, Start Menu + optional Desktop shortcuts, file exclusions for secrets/logs/artifacts.
- Added secret scanner (`scripts/scan_secrets.ps1`): ripgrep-based scan for API-key-like patterns in dist or installed folders.
- Added simple mode toggle in `src/legalpdf_translate/qt_gui/app_window.py`: `_is_simple_mode()` function + `self._simple_mode` instance attribute; hides Glossary Builder and Calibration Audit buttons/menus in release builds (frozen EXE); overrideable via `LEGALPDF_SIMPLE_MODE` env var.
- Re-applied drift-proof `_FRAME_INSETS` constant in `app_window.py`.

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (section J: installer, simple mode, secret scanner pointers)
- docs/assistant/UPDATE_POLICY.md (sections: Mini Changelog)

Verification commands/results:
- python -m pytest -q -> pending
- python -m compileall src tests -> pending
- git diff --name-only -> pending
- git status --short -> pending

### 2026-02-15 — Glossary tab productivity improvements

Code changes:
- Auto-save glossary edits via 500 ms debounced `QTimer` calling `save_gui_settings()` with glossary-only keys (no Apply required)
- `+` button beside search box + `Ctrl+N` / `Insert` keyboard shortcuts for adding rows with auto-focus
- New rows default Source lang to `PT` instead of `AUTO`
- Cross-language propagation: new source phrases auto-propagated to all target languages with `"..."` placeholder translation
- Fixed in-table QComboBox clipping via `GlossaryTableCombo` objectName + targeted QSS override (`padding: 2px 4px; border-radius: 4px`) + `setSizeAdjustPolicy(AdjustToContents)`

Docs updated:
- docs/assistant/APP_KNOWLEDGE.md (section F: glossary UI — auto-save, shortcuts, default PT, propagation)
- docs/assistant/QT_UI_KNOWLEDGE.md (objectName table: GlossaryTableCombo)
- docs/assistant/UPDATE_POLICY.md (Mini Changelog)

Verification commands/results:
- python -m pytest -q -> 427 passed
- python -m compileall src tests -> OK
- git diff --name-only -> pending
- git status --short -> pending
# 2026-03-07
- Hardened docs-sync prompt semantics across project governance and bootstrap templates.
- The exact prompt remains unchanged, but it is now conditional: ask it only when relevant touched-scope docs still remain unsynced.
- If the relevant docs sync already ran during the same task/pass, the prompt should not be asked again.

# 2026-03-07
- Instantiated the bootstrap local operational layer into this project.
- Added tracked project-local runtime/capability docs:
  - `docs/assistant/LOCAL_ENV_PROFILE.local.md`
  - `docs/assistant/LOCAL_CAPABILITIES.md`
- Added `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md` so Windows-bound/local-auth integrations route through installation/auth/same-host/live-smoke preflight instead of thread memory.
- Routed those files through `APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, `docs/assistant/INDEX.md`, and `docs/assistant/manifest.json`.

# 2026-03-07
- Historical Gmail draft attachment reuse now prefers stored translation artifact paths before prompting the user.
- Job Log rows gained additive artifact-path semantics:
  - `output_docx_path`
  - `partial_docx_path`
- Historical honorarios Gmail draft flow now resolves translated attachments in this order:
  1. stored final DOCX
  2. stored partial DOCX
  3. exact `run_id` recovery
  4. manual picker only as a last resort
- Legacy rows are self-healing: if one manual translated-DOCX selection is needed, that path is saved back into the row so the same row should not prompt again.

# 2026-03-08
- Ran a narrow Assistant Docs Sync for the Gmail-intake worktree after repeated same-day Gmail intake, Arabic, run-report, and draft-finalization debugging loops.
- Added one durable observability layer: app-owned `gmail_batch_session.json` under the effective output directory, and linked it from Gmail-intake `run_summary.json` / `run_report.md` via additive `gmail_batch_context`.
- Synced durable troubleshooting guidance for:
  - extension self-healing and visible banner errors instead of silent no-ops
  - visible `Gmail intake bridge unavailable` state on localhost bind conflicts
  - Gmail batch target-language selection in the review dialog
  - stale output-folder recovery and stale-checkpoint fail-closed behavior
  - honorários auto-rename on save collisions
  - duplicate/contaminated Gmail draft attachment blocking
  - Arabic failure fields `validator_defect_reason`, `ar_violation_kind`, and sample snippets
- Tightened the documented Gmail support packet order so future triage starts from:
  1. Gmail banner text/screenshot
  2. app window title + visible bridge status
  3. `run_report.md` / `run_summary.json`
  4. `gmail_batch_session.json`
- Updated `ISSUE_MEMORY.md` / `ISSUE_MEMORY.json` because of two new repeated issue-memory entries:
  - pytest/live Gmail bridge cross-contamination through real `%APPDATA%` and port `8765`
  - fragmented Gmail-intake diagnostics across extension/app/run/finalization surfaces

# 2026-03-08
- Ran a scoped Assistant Docs Sync for the shipped Arabic DOCX review-gate feature and its durable issue-memory follow-up.
- Synced current-truth and user-facing docs for:
  - the Arabic Word review gate before `Save to Job Log` in both normal runs and Arabic Gmail batch items
  - `Align Right + Save`, save-detection auto-resume, and manual `Continue now` / `Continue without changes` fallback behavior
  - the `Open translated DOCX` action inside `Save to Job Log`
  - Windows Word + PowerShell COM plus same-host Windows validation as the runtime contract for this feature
- Updated `ISSUE_MEMORY.md` / `ISSUE_MEMORY.json` because of two new issue classes:
  - repeated Arabic DOCX right-alignment back-and-forth where multiple OOXML-only fixes failed or regressed mixed Arabic/LTR rendering before the Word review gate became the accepted mitigation
  - a reverted Gmail post-save finalization experiment that made the flow worse and established a higher validation bar for future changes in that area
- Superseding note:
  - the older historical Arabic writer-only refresh notes from `2026-02-13` should not be treated as the current supported mitigation for user-facing Arabic right alignment in Word
  - the current supported mitigation is the Arabic Word review gate plus manual-or-assisted save before continuation
