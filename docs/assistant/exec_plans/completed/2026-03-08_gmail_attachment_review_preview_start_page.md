# Gmail Attachment Review: Start Page + In-App Preview

## Title
Gmail Attachment Review per-attachment start page and in-app preview

## Goal and non-goals
- Goal: let the Gmail Attachment Review dialog choose a start page per selected attachment and preview attachment contents before batch preparation.
- Non-goals: add end-page/max-page controls, replace the main translation form, or add a system-viewer shortcut in this pass.

## Scope (in/out)
- In: Gmail review dialog, Gmail batch types/session payload, Gmail prepare/preview workers, Gmail batch app flow, run report metadata, targeted tests, deterministic Qt render sample.
- Out: non-Gmail source selection flow, queue manifest behavior, honorarios flow behavior unrelated to attachment selection.

## Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail_intake`
- branch name: `feat/gmail-intake-batch-reply`
- base branch: `feat/gmail-intake-batch-reply`
- base SHA: `0d1a66cf05222f460f2fc4384217c3e26d8cf22a`
- target integration branch: `feat/gmail-intake-batch-reply`
- canonical build status or intended noncanonical override: noncanonical worktree relative to `docs/assistant/runtime/CANONICAL_BUILD.json`; feature work is intentional and allowed by override policy

## Interfaces/types/contracts affected
- Add `GmailAttachmentSelection`.
- Change `GmailBatchReviewResult` to return selections rather than raw attachments.
- Extend `DownloadedGmailAttachment` with `start_page` and `page_count`.
- Add Gmail-only `start_page_override` handling in the main-window config builder.
- Extend Gmail batch context/report payload with selected start page metadata.

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_batch.py`: add selection type, validate start pages against downloaded file page counts, persist start-page/page-count session metadata.
- `src/legalpdf_translate/qt_gui/worker.py`: update Gmail batch prepare worker for selections and add preview fetch/render worker.
- `src/legalpdf_translate/qt_gui/dialogs.py`: expand Gmail review dialog UI and add in-app attachment preview dialog.
- `src/legalpdf_translate/qt_gui/app_window.py`: pass default start page into review, consume selections, and apply per-attachment start-page overrides during Gmail batch translation.
- `src/legalpdf_translate/run_report.py`: surface selected start page in Gmail batch context.
- `tests/test_gmail_batch.py`, `tests/test_qt_app_state.py`, `tests/test_run_report.py`, `tests/test_qt_render_review.py`: add/update targeted coverage.

## Tests and acceptance criteria
- Gmail review dialog returns `GmailAttachmentSelection` with correct per-row start pages.
- Preview can open a PDF/image attachment, navigate pages where applicable, and push the chosen page back into the dialog.
- Gmail batch preparation rejects invalid start pages and records valid page counts/start pages.
- Each Gmail batch translation item uses its own start page without mutating the main form field.
- Run report/render-review coverage passes for the new metadata and UI sample.

## Rollout and fallback
- Keep Gmail-specific override logic isolated to the Gmail intake path.
- If preview download/render fails, show a dialog error and keep review dialog state intact.
- If per-attachment validation fails during prepare, stop before translation begins.

## Risks and mitigations
- Risk: current worktree is already dirty in touched files.
  - Mitigation: patch current content in place, do not revert unrelated edits, verify via targeted tests.
- Risk: preview rendering could block UI.
  - Mitigation: perform download/render in a worker thread and only update UI from signals.
- Risk: start-page override leaks into non-Gmail runs.
  - Mitigation: use an explicit override argument only in Gmail batch calls.

## Assumptions/defaults
- Preview is in-app only.
- Preview downloads are temporary and may be re-downloaded during prepare.
- Gmail review seeds start page from the main form’s current start page, defaulting to `1`.

## Executed validations and outcomes
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m compileall src tests`
  - Outcome: passed
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m pytest -q tests/test_qt_app_state.py tests/test_gmail_batch.py tests/test_qt_render_review.py tests/test_run_report.py tests/test_checkpoint_resume.py tests/test_translation_diagnostics.py tests/test_translation_report.py`
  - Outcome: `177 passed`
