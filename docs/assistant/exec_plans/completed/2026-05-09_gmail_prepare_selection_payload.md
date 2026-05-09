# Gmail Prepare Selection Payload

## Goal and Non-Goals
Extract pure Gmail prepare-session selection payload shaping from `gmail.js` into the existing `gmail_review_state.js` module while preserving the `/api/gmail/prepare-session` payload contract.

Non-goals: no backend route changes, no submitted field/value changes, no attachment list rendering redesign, no Gmail/native-host behavior changes, no live Gmail/OAuth/native-host testing, and no selector or DOM ID changes.

## Scope
In scope:
- Add a pure `buildGmailPrepareSelectionsPayload(...)` export to `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`.
- Update `gmail.js` so `collectSelections()` only gathers coordinator state and delegates payload shaping to the pure builder.
- Add ESM coverage for selected, stale, invalid, malicious, image/non-editable, page-count, and null-safe defaults.
- Add structural ownership checks and static asset export coverage.
- Validate in shadow Gmail mode using the demo review/preview flow.

Out of scope:
- Selection-state map construction, already extracted.
- Attachment list/detail rendering, already owned by presentation/UI modules.
- Prepare-session backend validation or Gmail batch/session behavior.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_prepare_selection_payload`
- Branch name: `codex/gmail-prepare-selection-payload`
- Base branch: `main`
- Base SHA: `a5755c0b36ae9d1ace451272794cc0ae9d3998b8`
- Target integration branch: `main`
- Canonical worktree remains: `C:\Users\FA507\.codex\legalpdf_translate`

## Contracts Affected
- Browser static module `gmail_review_state.js` gains a pure exported builder.
- `gmail.js` continues to send the same `selections` array to `/api/gmail/prepare-session`.
- No backend route, API payload key, submitted select value, selector, Gmail/native-host, or extension contract changes are allowed.

## Implementation Steps
- `tests/test_gmail_review_state.py`: add ESM cases for the new builder.
- `tests/test_shadow_web_api.py`: add structural checks that `gmail.js` delegates selection payload shaping and update versioned static asset coverage.
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`: implement the pure builder by iterating selected state entries, ignoring stale IDs, clamping start pages with existing helpers, and preserving `page_count: undefined` for zero/invalid page counts.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import the builder and delegate `collectSelections()`.

## Tests and Acceptance Criteria
- First confirm the targeted tests fail before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- After implementation run:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke from this worktree on port `8888` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-prepare-selection-payload-smoke#gmail-intake` verifies page identity, nonblank content, no framework overlay, console health, demo attachment load, attachment selection, prepare button enablement, PDF preview path, and no live Gmail/OAuth/native-host flow.

## Validation Record
- Red check before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: failed for the missing `buildGmailPrepareSelectionsPayload` export and missing `gmail.js` delegation.
- Targeted checks after implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `3 passed in 2.29s`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `200 passed in 191.84s`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed. The wrapper hit the known `dartdev` AOT snapshot issue for agent-docs and workspace-hygiene validators, then both direct-Dart fallbacks succeeded.
- Review:
  - Independent read-only review found no issues. Reviewer targeted checks passed: `5 passed`.
- Browser smoke:
  - Browser plugin loaded `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-prepare-selection-payload-smoke#gmail-intake`, confirmed page identity, nonblank Gmail review content, no framework overlay, hydrated `Isolated Test Data` mode, visible demo-load affordance, and empty console warnings/errors.
  - Browser interaction timed out on the demo button with a CDP evaluation timeout. Playwright fallback exercised the same shadow-only flow at `workspace=gmail-prepare-selection-payload-smoke-pw`, confirming demo load, attachment selection, enabled prepare action, PDF preview readiness, no framework overlay, and no warnings.
  - Screenshot evidence: `C:\Users\FA507\AppData\Local\Temp\gmail-prepare-selection-payload-smoke.png`.

## Rollout and Fallback
Publish via a ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending. If prepare-session selection behavior regresses, revert only this branch and leave canonical `main` untouched.

## Risks and Mitigations
- Risk: selected payload order drift. Mitigation: builder iterates selection-state entries like the old coordinator code.
- Risk: `page_count` omission changes. Mitigation: tests pin zero/invalid page counts as `undefined`, matching the old JSON omission behavior.
- Risk: non-PDF start pages leak into prepare payloads. Mitigation: tests cover image/non-editable clamping to page 1.

## Assumptions
- Shadow mode is sufficient for smoke.
- No live Gmail testing is in scope.
- User authorization covers ready PR creation, green-check merge, canonical main fast-forward, and feature worktree cleanup.
