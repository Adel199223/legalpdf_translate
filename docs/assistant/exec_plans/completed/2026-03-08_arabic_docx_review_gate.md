# Arabic DOCX Review Gate Before Job Log / Gmail Finalization

## Goal and non-goals
- Goal: add an Arabic-only review gate that opens the translated DOCX in Word, allows one-click `Align Right + Save`, auto-detects manual save, and only then continues to Save to Job Log or Gmail batch progression.
- Non-goals:
  - fix Arabic alignment inside the generated DOCX OOXML
  - add new persistent settings
  - change non-Arabic automatic flow beyond an optional manual `Open translated DOCX` button in Save to Job Log
  - add automatic email sending

## Scope (in/out)
- In:
  - Qt completion flow for normal runs and Gmail batch runs
  - new Arabic Word review dialog
  - Windows-only Word automation helper via PowerShell COM
  - Save-to-Job-Log optional `Open translated DOCX` action
  - targeted tests for the new gate/helper behavior
- Out:
  - CLI flow changes
  - DOCX writer RTL formatting changes
  - non-Windows Word integrations
  - new database/schema/report fields

## Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/ai-docs-bootstrap`
- base branch: `feat/ai-docs-bootstrap`
- base SHA: `e57f6679389a1afc43d29f26256987db12a41078`
- target integration branch: `feat/ai-docs-bootstrap`
- canonical build status: canonical approved base branch; this is the live Windows Qt worktree

## Interfaces/types/contracts affected
- New internal Word automation helper contract:
  - open/attach exact DOCX in Word
  - run full-document paragraph `Align Right + Save`
  - return structured success/failure/message state
- New internal Arabic review dialog contract:
  - input: DOCX path, batch-vs-normal context, attachment label
  - output: accepted/cancelled only; acceptance means continuation is allowed
- Existing contract change:
  - Arabic successful runs now pause before Save to Job Log
  - Arabic Gmail batch items now pause before Save to Job Log and before draft-attachment staging
- `QtSaveToJobLogDialog` gains a non-breaking `Open translated DOCX` action

## File-by-file implementation steps
1. Add a new helper module under `src/legalpdf_translate/` for Windows Word automation through PowerShell COM.
   - Implement open/attach and align-right-save commands.
   - Keep failures non-fatal and return structured results.
2. Extend `src/legalpdf_translate/qt_gui/dialogs.py`.
   - Add the Arabic review dialog with:
     - auto-open in Word on show
     - polling of DOCX fingerprint `(mtime_ns, size)`
     - quiet-period auto-accept after first detected save
     - `Align Right + Save`, `Open in Word`, `Continue without changes`, `Continue now`, `Cancel`
   - Add `Open translated DOCX` to `QtSaveToJobLogDialog`.
3. Update `src/legalpdf_translate/qt_gui/app_window.py`.
   - Route Arabic successful normal runs through the review dialog before Save to Job Log.
   - Route Arabic Gmail batch successful items through the review dialog before Save to Job Log and before `stage_gmail_batch_translated_docx(...)`.
   - Preserve existing non-Arabic flow.
4. Update targeted tests in `tests/test_qt_app_state.py`.
   - Cover Arabic normal flow, Arabic Gmail flow, cancellation behavior, and non-Arabic regression safety.
5. Add unit coverage for the Word helper in a new focused test file if needed.

## Tests and acceptance criteria
- Automated:
  - `tests/test_qt_app_state.py`
  - helper-focused Word automation tests
  - any dialog tests added for save-detection behavior
- Acceptance:
  - Arabic normal run opens DOCX and blocks Save to Job Log until review gate accepts
  - Arabic Gmail batch item opens DOCX and blocks batch continuation until review gate accepts and Save to Job Log succeeds
  - staged Gmail draft attachment reflects the reviewed Arabic DOCX
  - non-Arabic normal and Gmail flows remain unchanged
  - Save-to-Job-Log dialog can manually open the translated DOCX for any language

## Rollout and fallback
- Roll out as built-in Arabic-only behavior with no settings gate.
- If Word automation fails:
  - keep document open/manual open path available
  - continue using save detection or explicit `Continue now`
- If the review dialog is cancelled:
  - normal run stays completed and stops before Save to Job Log
  - Gmail batch stops cleanly with a visible message

## Risks and mitigations
- Risk: save detection triggers too early while Word is still writing.
  - Mitigation: require fingerprint change plus quiet period before auto-accept.
- Risk: Word COM automation is flaky across hosts.
  - Mitigation: PowerShell COM helper returns structured failure; manual fallback remains available.
- Risk: Gmail batch stages the pre-edit file.
  - Mitigation: keep staging after Save to Job Log and move Arabic review earlier than that step.

## Assumptions/defaults
- Arabic-only automatic review behavior is desired for both normal and Gmail-triggered runs.
- The user’s actual need is easiest-manual-fix workflow, not another attempt at automatic OOXML right alignment.
- Word is available on the Windows host used for the real app flow.

## Execution outcomes
- Implemented:
  - `src/legalpdf_translate/word_automation.py`
  - Arabic review gate dialog and Save-to-Job-Log `Open translated DOCX` in `src/legalpdf_translate/qt_gui/dialogs.py`
  - Arabic-only completion routing in `src/legalpdf_translate/qt_gui/app_window.py`
  - targeted coverage in `tests/test_qt_app_state.py`
  - helper coverage in `tests/test_word_automation.py`
- Validation:
  - `python.exe -m py_compile src/legalpdf_translate/word_automation.py src/legalpdf_translate/qt_gui/dialogs.py src/legalpdf_translate/qt_gui/app_window.py tests/test_word_automation.py tests/test_qt_app_state.py`
  - `python.exe -m pytest -q tests/test_word_automation.py tests/test_qt_app_state.py -k "arabic_docx_review or word_automation or open_translation_docx or gmail_batch_run or non_arabic_normal_run_still_uses_saved_docx_prompt"` -> `15 passed`
  - `python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_word_automation.py` -> `29 passed`
  - `python.exe -m pytest -q tests/test_qt_app_state.py -k "gmail_batch_run_success_schedules_next_item_after_joblog_save or gmail_batch_run_stops_when_joblog_is_cancelled or gmail_batch_run_stops_on_consistency_mismatch or arabic_normal_run or arabic_gmail_batch_run or arabic_docx_review_dialog or save_to_joblog_dialog_open_translation_docx_uses_resolved_path or non_arabic_normal_run_still_uses_saved_docx_prompt"` -> `12 passed`
- Host note:
  - a clean solo `tests/test_qt_app_state.py` run again went idle on this Windows/PySide host after reaching `72%` with no failures emitted, so the completed validation is the focused subset above rather than a full-file green claim.
