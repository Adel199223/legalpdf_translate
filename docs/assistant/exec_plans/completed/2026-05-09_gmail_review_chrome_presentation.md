# Gmail Review Chrome Presentation

## Goal and Non-Goals

Extract the Gmail Review Attachments chrome state shaping from `gmail.js` into a pure presentation module while preserving the existing safe DOM renderer, DOM IDs, selectors, event listeners, routes, payloads, Gmail/native-host behavior, and safe text rendering.

Non-goals:
- Do not change Review Attachments button behavior or label defaults.
- Do not change backend routes, API payloads, submitted values, selectors, or Gmail/native-host contracts.
- Do not touch live Gmail, OAuth, native-host, or user mailbox flows.

## Scope

In:
- Create `gmail_control_presentation.js` exporting `buildGmailReviewChromePresentation({ loadResult })`.
- Update `gmail.js` so `renderReviewSummary()` calls the builder and passes the result to `renderGmailReviewChromeInto(...)`.
- Add ESM/static contract coverage and static asset route coverage.

Out:
- Any public route, backend payload, extension, selector, or native-host change.
- Any live Gmail testing.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_review_chrome_presentation`
- Branch name: `codex/gmail-review-chrome-presentation`
- Base branch: `origin/main`
- Base SHA: `a7664236a5865c3ae1bed355570e104f062a3d67`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; browser validation must use shadow mode with isolated app data.

## Interfaces, Types, and Contracts Affected

- New pure JavaScript export:
  - `buildGmailReviewChromePresentation({ loadResult })`
- Returned shape:
  - `{ available: boolean, statusText: string }`
- Existing renderer remains:
  - `renderGmailReviewChromeInto({ status, openButton }, presentation)`

## File-by-File Implementation Steps

1. `tests/test_shadow_web_api.py`
   - Add failing ESM probe coverage for the new builder: empty/null, loaded message, `ok` without message, message without `ok`, and malicious message metadata.
   - Tighten the existing review chrome renderer ownership test so `gmail.js` imports/calls the builder and no longer inlines availability or long status copy.
   - Update the versioned static asset graph test to assert `/static-build/<asset_version>/gmail_control_presentation.js` serves JavaScript and exports the builder.

2. `src/legalpdf_translate/shadow_web/static/gmail_control_presentation.js`
   - Add the pure builder.
   - Keep it DOM-free and renderer-free.

3. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - Import `buildGmailReviewChromePresentation`.
   - Replace inline review chrome object in `renderReviewSummary()` with the builder call.

## Tests and Acceptance Criteria

Red phase:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_control_presentation_module_builds_review_chrome_state tests/test_shadow_web_api.py::test_gmail_control_ui_module_centralizes_review_chrome_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Green phase:
- Same targeted tests pass.
- Focused browser/Gmail suite passes:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation passes:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - If `dart run ...` reports the known AOT launcher issue, record it only when the direct-Dart fallback succeeds.

Browser smoke:
- Launch shadow preview from this worktree on port `8888`:
  - `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace gmail-review-chrome-smoke --port 8888`
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-chrome-smoke#gmail-intake`.
- Check page identity, nonblank content, no framework overlay, console health, screenshot evidence, demo attachment surface, and no live Gmail/OAuth/native-host flow.

## Rollout and Fallback

- Commit only intended files after validation.
- Push branch and create ready PR titled `[codex] Extract Gmail review chrome presentation`.
- Wait for green required checks, merge normally, fast-forward canonical `main`, prune refs, and remove this feature worktree only after `main` contains the merge.
- Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending.

Fallback:
- If tests or smoke reveal a behavior change, revert local feature edits in this worktree only and keep canonical `main` untouched.

## Risks and Mitigations

- Risk: Review Attachments open button availability changes.
  - Mitigation: ESM probes pin `ok && message` availability.
- Risk: status copy changes.
  - Mitigation: tests pin the exact status text.
- Risk: unsafe rendering regression.
  - Mitigation: renderer remains unchanged and tests assert no unsafe writes.

## Assumptions and Defaults

- No live Gmail/OAuth/native-host testing is in scope.
- Shadow-mode browser smoke is sufficient for UI verification.
- The PR should be ready for review and merge after local validation passes.

## Completion Notes

- Created `gmail_control_presentation.js` with `buildGmailReviewChromePresentation({ loadResult })`.
- Updated `renderReviewSummary()` in `gmail.js` to call the builder and pass the presentation to the existing `renderGmailReviewChromeInto(...)` renderer.
- Left `gmail_control_ui.js`, DOM IDs, selectors, event listeners, routes, payloads, Gmail/native-host behavior, and safe rendering behavior unchanged.
- Confirmed targeted red phase before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_control_presentation_module_builds_review_chrome_state tests/test_shadow_web_api.py::test_gmail_control_ui_module_centralizes_review_chrome_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result before implementation: 3 failed for the missing presentation module/static asset.
- Confirmed targeted green phase after implementation:
  - Same command: 3 passed.
- Focused browser/Gmail suite passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: 197 passed.
- Full validation passed:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: validation complete.
  - Known Dart AOT launcher issue occurred for `dart run tooling/validate_agent_docs.dart` and `dart run tooling/validate_workspace_hygiene.dart`; the wrapper used the direct Dart executable fallback and both validations passed.
- Browser smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-chrome-smoke#gmail-intake`.
  - Browser verified page identity (`LegalPDF Translate`), nonblank Gmail review content, no framework overlay, clean console, shadow demo attachment load, Review Attachments drawer, and the exact review chrome status copy.
  - Browser screenshot evidence captured successfully.
  - No live Gmail/OAuth/native-host flow was touched.
- Read-only subagent review found no issues.
