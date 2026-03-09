# Gmail Attachment Preview: Lazy Continuous Scroll

## Title
Replace single-page Gmail attachment preview with lazy continuous scroll

## Goal and non-goals
- Goal: let Gmail PDF preview show all pages in one vertical scrolling dialog without eagerly rendering the whole document.
- Goal: keep preview responsive by downloading once, rendering lazily, and bounding preview cache/memory.
- Non-goals: add zoom controls, thumbnail strips, non-Gmail preview changes, or Gmail batch/session schema changes.

## Scope (in/out)
- In: Gmail attachment preview workers, Gmail preview dialog UI/behavior, Qt preview tests, deterministic preview render sample.
- Out: Gmail review selection contract, Gmail batch prepare/report behavior, non-Gmail source preview flows.

## Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail_intake`
- branch name: `feat/gmail-intake-batch-reply`
- base branch: `feat/gmail-intake-batch-reply`
- base SHA: `0d1a66cf05222f460f2fc4384217c3e26d8cf22a`
- target integration branch: `feat/gmail-intake-batch-reply`
- canonical build status or intended noncanonical override: noncanonical worktree relative to `docs/assistant/runtime/CANONICAL_BUILD.json`; feature work is intentional and allowed by override policy

## Interfaces/types/contracts affected
- Replace the single preview worker result with:
  - a bootstrap result carrying `attachment`, `local_path`, and `page_count`
  - a page-render result carrying `attachment`, `local_path`, `page_count`, `page_number`, and rendered image payload
- Keep `QtGmailAttachmentPreviewDialog` input/output contract stable for the Gmail review dialog:
  - input: attachment, preview temp dir, cached local path, initial start page
  - output: `selected_start_page`, `resolved_local_path`, `resolved_page_count`

## File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/worker.py`: split preview download/bootstrap from per-page rendering and expose page-specific error handling.
- `src/legalpdf_translate/qt_gui/dialogs.py`: replace pager UI with a scrollable stack of page cards, jump-to-page control, lazy render queue, and bounded page cache; preserve single-image behavior.
- `tooling/qt_render_review.py`: add a fake-backed Gmail preview dialog sample for deterministic render capture.
- `tests/test_qt_app_state.py`, `tests/test_qt_render_review.py`: cover scroll preview setup, page selection, jump behavior, duplicate render suppression, and render sample output.

## Tests and acceptance criteria
- PDF preview opens into a continuous-scroll dialog with per-page actions instead of Previous/Next.
- Initial start page is scrolled into view after bootstrap.
- Clicking `Use this page as start` accepts the preview and returns that page number.
- Jump-to-page scrolls to the requested page and queues that page for rendering.
- Duplicate queue refreshes do not start multiple renders for the same page while it is cached, queued, or inflight.
- Image attachments still preview as a single image and force page `1`.
- Deterministic render tooling can capture the Gmail preview dialog without Gmail/network access.

## Rollout and fallback
- Keep Gmail review integration unchanged so the preview dialog remains a drop-in replacement.
- If preview bootstrap fails, show the existing warning path and leave review state unchanged.
- If individual PDF page renders fail, show an error placeholder on that page card and allow other pages to continue rendering.

## Risks and mitigations
- Risk: rendering too many pages at once causes lag or memory growth.
  - Mitigation: queue only visible pages plus a small buffer, cap concurrent renders at 2, cap pixmap cache at 8 pages.
- Risk: page eviction causes visible flicker.
  - Mitigation: prefer evicting non-visible cached pages first and rerender only when revisited.
- Risk: dirty worktree overlaps in `dialogs.py` and `worker.py`.
  - Mitigation: patch current content in place and verify with targeted tests only.

## Assumptions/defaults
- PDFs fully switch to scroll preview; Previous/Next are removed for PDFs only.
- Start-page selection is explicit per page card, not inferred from scroll position.
- Existing render DPI/compression defaults remain unchanged in this pass.

## Executed validations and outcomes
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m compileall src/legalpdf_translate/qt_gui/dialogs.py src/legalpdf_translate/qt_gui/worker.py tooling/qt_render_review.py tests/test_qt_app_state.py tests/test_qt_render_review.py`
  - Outcome: passed
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m pytest -q tests/test_qt_app_state.py`
  - Outcome: `85 passed`
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m pytest -q tests/test_qt_render_review.py`
  - Outcome: `5 passed`
- `"/mnt/c/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe" -m pytest -q tests/test_qt_app_state.py tests/test_gmail_batch.py tests/test_qt_render_review.py tests/test_run_report.py tests/test_checkpoint_resume.py tests/test_translation_diagnostics.py tests/test_translation_report.py`
  - Outcome: `177 passed`
