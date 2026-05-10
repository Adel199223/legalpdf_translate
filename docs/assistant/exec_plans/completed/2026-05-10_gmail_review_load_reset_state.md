# Gmail Review Load Reset State

## Goal

Extract the repeated Gmail review-load reset state shaping from `gmail.js` into a pure helper while preserving all Gmail/browser contracts, DOM IDs, routes, payloads, datasets, native-host behavior, and safe rendering.

## Provenance

- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_review_load_reset_state`
- Branch: `codex/gmail-review-load-reset-state`
- Base branch: `main`
- Base SHA: `8a280c308417f2a4f0f9e97a3bb2e07f2bc026e7`
- Validation mode: shadow browser only; no live Gmail/OAuth/native-host testing.

## Scope

- Add a pure `buildGmailReviewLoadResetState(...)` export to `gmail_review_state.js`.
- Refactor `loadMessage()` and `loadDemoReview()` in `gmail.js` so they gather the load payload, call the helper, and apply the returned coordinator reset state.
- Keep `clearGmailFailureReportContext()`, `ensureSelectionState(...)`, `resetPreviewState()`, render calls, panel status, diagnostics, and review drawer behavior in the coordinator.
- Add red-first ESM/static/contract coverage.

## Tests

- Red first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_builds_review_load_reset_state tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_review_load_reset_state`
  - Result: failed as expected because `buildGmailReviewLoadResetState` was not exported.
- After implementation:
  - Same targeted tests.
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: targeted tests passed, focused browser/Gmail suite passed with `202 passed`, full validation passed with the known `dart run` AOT launcher issue followed by successful direct-Dart fallbacks, and full local CI-equivalent `.\.venv311\Scripts\python.exe -m pytest -q` passed with `1435 passed`.
- Browser smoke:
  - Launch shadow app on port `8888` from this feature worktree.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-load-reset-smoke#gmail-intake`.
  - Use shadow demo attachments only; confirm page identity, nonblank Gmail intake content, no framework overlay, clean console, demo load opens review, preview still works, and no live Gmail is touched.
  - Result: Browser verified `LegalPDF Translate` on the shadow Gmail intake URL, nonblank Gmail review content, no framework overlay, empty console warnings/errors, demo attachments loaded, Review opened, and Preview rendered `demo-gmail-review.pdf` page 1 with visible PDF canvas content. No live Gmail/OAuth/native-host flow was touched.

## Review

- Independent diff review: no findings; reviewer confirmed the helper extraction preserves load-message/demo-review behavior and does not alter routes, POST payloads, DOM IDs/datasets, Gmail/native-host contracts, or safe rendering.

## Acceptance

- `gmail.js` no longer repeats the same active session/restored session/seed/finalization reset assignments in both review load paths.
- The helper is pure: no DOM, no `fetch`, no render calls, no route/payload changes.
- Intended files only are staged for publish.
