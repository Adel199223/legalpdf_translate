# Gmail Preview Smoothness + Faster Prepare Handoff

## Title
Reduce Gmail preview scroll shake and reuse preview downloads during Prepare

## Goal and non-goals
- Goal: make Gmail PDF preview scrolling feel stable and less laggy while pages load or get evicted.
- Goal: remove the extra prepare delay by reusing already previewed Gmail attachments instead of redownloading them.
- Non-goals: change translation runtime behavior, add zoom/thumbnail UI, or alter Gmail batch reporting schemas.

## Scope (in/out)
- In: Gmail preview dialog geometry/render behavior, preview bootstrap/page worker data, review-dialog preview cache ownership, Gmail batch prepare reuse path, targeted tests and render sample.
- Out: non-Gmail previews, translation workflow internals, queue runner behavior, run-report fields.

## Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail_intake`
- branch name: `feat/gmail-intake-batch-reply`
- base branch: `feat/gmail-intake-batch-reply`
- base SHA: `0d1a66cf05222f460f2fc4384217c3e26d8cf22a`
- target integration branch: `feat/gmail-intake-batch-reply`
- canonical build status or intended noncanonical override: noncanonical worktree relative to `docs/assistant/runtime/CANONICAL_BUILD.json`; feature work is intentional and allowed by override policy

## Interfaces/types/contracts affected
- Extend `GmailAttachmentPreviewBootstrapResult` with per-page preview size metadata for stable page-card layout.
- Add an internal preview-cache transfer bundle that carries cached local paths, known page counts, and temporary-directory ownership from the review dialog to batch prepare.
- Extend `prepare_gmail_batch_session(...)` and `GmailBatchPrepareWorker` with optional cached-preview path/page-count inputs.

## File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/worker.py`: collect preview page-size metadata during bootstrap, lower preview render settings, and accept optional cached-preview reuse inputs for Gmail batch prepare.
- `src/legalpdf_translate/qt_gui/dialogs.py`: stabilize page-card geometry, debounce scroll-triggered work, enlarge/smooth preview cache handling, and transfer preview tempdir ownership out of the review dialog on Accept.
- `src/legalpdf_translate/gmail_batch.py`: reuse cached preview files during prepare by copying them into the batch temp folder, validating page counts, and falling back to Gmail download only when reuse is unavailable.
- `src/legalpdf_translate/qt_gui/app_window.py`: keep temporary preview-cache state across the review -> prepare handoff and clean it on prepare completion/failure/session reset.
- `tests/test_gmail_batch.py`, `tests/test_qt_app_state.py`, `tests/test_qt_render_review.py`: cover stable preview sizing/debouncing, preview-cache transfer, and prepare reuse/fallback behavior.

## Tests and acceptance criteria
- Preview page cards reserve stable heights before pixels arrive and keep that geometry when evicted.
- Scroll-triggered page refresh work is debounced instead of running on every scrollbar change.
- Preview rendering uses lighter settings and one-at-a-time page rendering without breaking page selection.
- Accepted review reuses previewed attachments during Prepare without redownloading them.
- Canceled review still cleans preview temp files immediately; accepted review cleans them after prepare finishes or fails.
- Existing Gmail review/prepare/render-review coverage remains green.

## Rollout and fallback
- Keep fallback download behavior intact whenever no valid preview cache is available.
- If preview metadata collection fails, treat it as preview unavailable rather than degrading into inconsistent geometry.
- If copied preview files fail validation during prepare, discard them and fall back to a fresh Gmail download before surfacing an error.

## Risks and mitigations
- Risk: preview geometry changes still feel shaky if status rows resize.
  - Mitigation: reserve page-image height from bootstrap metadata and keep the status line height stable.
- Risk: preview cache ownership leaks temp directories on cancel/error.
  - Mitigation: centralize cleanup through explicit bundle ownership and main-window/session cleanup paths.
- Risk: reuse path skips validation and starts a bad batch.
  - Mitigation: always revalidate staged copied files with `get_source_page_count(...)` before accepting them.

## Assumptions/defaults
- Priority is smoother scrolling over minimal memory use.
- Preview rendering may be slightly softer than translation-image rendering.
- Prepare-speed improvement comes from preview-cache reuse, not from bypassing validation or staging.

## Executed validations and outcomes
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m compileall src tests`
  - Outcome: passed
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m pytest -q tests/test_qt_app_state.py tests/test_gmail_batch.py tests/test_qt_render_review.py tests/test_run_report.py tests/test_checkpoint_resume.py tests/test_translation_diagnostics.py tests/test_translation_report.py`
  - Outcome: `177 passed`
