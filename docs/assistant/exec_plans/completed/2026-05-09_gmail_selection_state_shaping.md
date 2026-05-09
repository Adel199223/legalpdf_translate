# Gmail Selection State Shaping

## Goal and Non-Goals
Extract pure Gmail attachment selection, start-page, and focus derivation from `gmail.js` into `gmail_review_state.js`, keeping `gmail.js` as the coordinator for form reads, state assignment, API calls, routing, and rendering.

Non-goals: no Gmail/native-host behavior changes, no route or payload shape changes, no selector or submitted value changes, no live Gmail/OAuth testing, and no visual redesign.

## Scope
In scope:
- Add pure review-state exports for attachment start editability, start-page clamping, selection-state normalization/map construction, active-session attachment ID derivation, and focused attachment ID derivation.
- Update `gmail.js` to call the pure helpers while preserving existing Map ownership and preview-reset side effects.
- Add targeted ESM and structural contract tests.
- Validate in shadow Gmail mode with the demo review/preview flow.

Out of scope:
- PDF preview rendering changes.
- Attachment renderer redesign.
- Gmail finalization, report, native host, or bridge behavior changes.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_selection_state`
- Branch name: `codex/gmail-selection-state-shaping`
- Base branch: `origin/main`
- Base SHA: `9cdee7c91f5f2c74f98a3ab6c16f762f01636581`
- Target integration branch: `main`
- Canonical build status: feature worktree is noncanonical; canonical main remains `C:\Users\FA507\.codex\legalpdf_translate`.

## Interfaces, Types, and Contracts Affected
- Browser static review-state module gains pure exports.
- `gmail.js` internal behavior should remain equivalent for selected attachments, start pages, preview state reset, and focused attachment fallback order.
- No backend route, API payload, form submitted value, DOM selector, Gmail/native-host, or extension contract changes.

## File-by-File Implementation Steps
- `tests/test_gmail_review_state.py`: add ESM probe cases for start editability, clamping, selection-state map derivation, translation and interpretation active sessions, focus fallback order, and null-safe defaults.
- `tests/test_shadow_web_api.py`: add structural assertions that `gmail.js` imports/delegates to the new helpers and no longer owns the full selection/focus derivation logic.
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`: add the pure helpers.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: replace local pure shaping with calls into `gmail_review_state.js`, preserving side effects and existing rendered output.

## Tests and Acceptance Criteria
- First confirm the targeted tests fail for missing exports/delegation.
- After implementation run:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke from this worktree on port `8888` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-selection-smoke#gmail-intake` verifies page identity, nonblank content, no framework overlay, console health, demo attachment load, review drawer, attachment selection, PDF preview/start-page controls, restore behavior, and no live Gmail/OAuth/native-host flow.

## Validation Notes
- Red test confirmed before implementation: targeted review-state/structural tests failed for missing `deriveGmailAttachmentStartEditable`.
- Code review feedback fixed before publish:
  - Preserved exact old PDF editability parity: workflow `translation` and MIME exactly `application/pdf` after trim/lowercase.
  - Preserved interpretation-session selection parity: existing selected attachments remain selected and the active interpretation notice is overlaid as selected.
  - Preserved raw attachment ID membership semantics rather than trim-normalizing IDs.
- Targeted tests passed after fixes: `2 passed`.
- Focused browser/Gmail suite passed after fixes: `198 passed`.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passed. The known `dart run` AOT launcher issue occurred for agent-docs and workspace-hygiene validation; direct Dart fallback succeeded for both.
- Browser shadow smoke used port `8888`. Browser verified page identity, nonblank Gmail review content, no framework overlay, clean console, demo attachment load, review drawer, attachment selection, and no live Gmail/OAuth/native-host flow. Browser initiated the PDF preview path but the in-app Browser pdf.js render stalled before bundle upload, so Playwright fallback verified `/api/browser-pdf/bundle`, `gmail-preview-canvas`, page/start controls, shadow-scoped preview href, and review/preview restore chips.
- Smoke screenshot: `C:\Users\FA507\AppData\Local\Temp\gmail-selection-smoke-preview.png`.

## Rollout and Fallback
Publish via a ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending. If selection or preview behavior regresses, revert only this feature branch and leave canonical `main` untouched.

## Risks and Mitigations
- Risk: start-page clamping drift. Mitigation: exact ESM cases for PDF translation, image/interpretation, invalid values, and page-count caps.
- Risk: focus fallback drift. Mitigation: tests assert valid focus, selected fallback, active-session fallback, first-attachment fallback, and empty fallback.
- Risk: interpretation multi-select behavior drift. Mitigation: tests assert interpretation sessions preserve existing selected attachments, overlay the active notice as selected, and keep start pages at `1`.

## Assumptions and Defaults
- Shadow mode is sufficient for smoke.
- No live Gmail testing is in scope.
- User authorization covers commit, ready PR creation, green-check merge, canonical main fast-forward, and feature worktree cleanup.
