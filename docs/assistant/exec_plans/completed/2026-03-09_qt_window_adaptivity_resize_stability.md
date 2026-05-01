# Qt Window Adaptivity and Resize Stability

## 1. Title
Qt window adaptivity and resize stability pass

## 2. Goal and non-goals
- Goal: make the main window and major dialogs open within the current screen bounds, resize smoothly, and keep the Edit Job Log dialog usable on smaller displays.
- Goal: collapse Job Log dialog sections from `Run Metrics` downward by default while keeping the action row accessible.
- Goal: remove obvious resize jitter in the main shell and Gmail attachment preview.
- Non-goal: redesign the app visual language or change product workflows.
- Non-goal: add new persistence formats or change job-log/database schemas.

## 3. Scope (in/out)
- In scope:
  - shared Qt helper for screen-bounded initial sizing and deferred resize callbacks
  - `QtMainWindow`
  - `QtSaveToJobLogDialog`
  - `QtJobLogWindow`
  - `QtGmailAttachmentPreviewDialog`
  - `QtHonorariosExportDialog`
  - `QtReviewQueueDialog`
  - `QtGmailBatchReviewDialog`
  - `QtGlossaryEditorDialog`
  - `QtSettingsDialog`
  - `QtGlossaryBuilderDialog`
  - `QtCalibrationAuditDialog`
  - audit `QtArabicDocxReviewDialog` and adapt only if needed to satisfy the new sizing contract
  - targeted Qt regression tests
- Out of scope:
  - docs sync in this implementation pass
  - new feature behavior outside window sizing/collapse/resize stability

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/joblog-inline-editing`
- Base branch: `main`
- Base SHA: `674098c5aec8a711368b3653c6a4364fb7b01a8c`
- Target integration branch: `main`
- Canonical build status: noncanonical branch on the canonical worktree path; approved base floor satisfied by `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Add an internal shared Qt sizing helper for:
  - screen-bounded initial window sizing
  - screen-clamped minimum sizing
  - deferred resize callbacks for jitter-prone windows
- Add an internal collapsible-section helper used by the Save/Edit Job Log dialog.
- No public API, CLI, DB schema, or settings schema changes.

## 6. File-by-file implementation steps
- Add a new shared helper module under `src/legalpdf_translate/qt_gui/` for responsive top-level sizing and deferred resize scheduling.
- Update `src/legalpdf_translate/qt_gui/app_window.py` to:
  - use the shared window helper
  - reduce resize churn in the responsive shell path
  - keep hero/status content readable during narrow-width layouts
- Update `src/legalpdf_translate/qt_gui/dialogs.py` to:
  - convert `QtSaveToJobLogDialog` to a scrollable form body with a fixed action bar
  - add collapsible Job Log sections with `Run Metrics` and lower sections collapsed by default
  - stabilize preview resize behavior in `QtGmailAttachmentPreviewDialog`
  - apply shared sizing rules to the other major dialogs in this file
- Update `src/legalpdf_translate/qt_gui/tools_dialogs.py` to apply the shared sizing rules to glossary/calibration dialogs.
- Update targeted Qt tests in `tests/test_qt_app_state.py` and related dialog tests to cover screen-bounded sizing, collapsed defaults, and resize-stability behavior.

## 7. Tests and acceptance criteria
- Automated:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py tests/test_honorarios_docx.py tests/test_qt_review_queue_panel.py`
  - `./.venv311/Scripts/python.exe -m compileall src tests`
- Acceptance:
  - `QtSaveToJobLogDialog` fits smaller screens by using a scrollable body
  - `Run Metrics` and `Amounts` start collapsed on open
  - the Save/Edit Job Log action row stays visible
  - the main window no longer clips short hero-status text in normal narrow/wide states
  - resize churn in the main window and preview is visibly reduced by deferred/coalesced updates
  - major dialogs open within the current screen bounds and remain resizable

## 8. Rollout and fallback
- Rollout in one pass because the shared sizing helper and the critical window fixes are tightly coupled.
- If preview or shell resize behavior regresses, keep the shared sizing helper and revert only the local deferred-refresh logic in the affected window.

## 9. Risks and mitigations
- Risk: new sizing helpers can destabilize dialogs that rely on `sizeHint`.
  - Mitigation: keep per-window preferred sizes and use screen bounds as caps rather than forcing every dialog to fill the same fraction.
- Risk: deferred resize logic can leave stale layout while dragging.
  - Mitigation: use short single-shot timers and flush immediately on show/bootstrap completion paths.
- Risk: collapsible Job Log sections can hide important actions.
  - Mitigation: keep the action row outside the scrollable/collapsible region.

## 10. Assumptions/defaults
- `Run Metrics` and `Amounts` are the sections that should start collapsed by default.
- Dense table windows may keep horizontal scrolling; the main shell should not gain a horizontal scrollbar.
- This pass will not persist per-user collapse state for the Job Log dialog.

## 11. Executed validations and outcomes
- `./.venv311/Scripts/python.exe -m compileall src tests`
  - Passed.
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py tests/test_honorarios_docx.py tests/test_qt_review_queue_panel.py`
  - Passed: `153 passed in 10.16s`.
- `./.venv311/Scripts/python.exe tooling/qt_render_review.py --outdir tmp_ui_review --preview reference_sample --include-gmail-review`
  - Passed. Deterministic dashboard renders completed for `wide`, `medium`, and `narrow` plus the Gmail review dialog sample.
