# Gmail Review Persistence Helpers

## Goal and Non-Goals

Extract Gmail consumed-review persistence and auto-open gating from `gmail_review_state.js` into a focused internal module. Preserve all existing storage keys, review-event semantics, drawer auto-open behavior, routes, payloads, selectors, Gmail/native-host behavior, and safe rendering paths.

Non-goals: change review drawer UX, Gmail handoff semantics, session storage values, message signature comparison, backend APIs, or live Gmail behavior.

## Scope

In scope:
- Add `gmail_review_persistence.js` with focused exports for consumed-review storage and auto-open gating.
- Re-export those helpers from `gmail_review_state.js` for compatibility with existing tests/importers.
- Update `gmail.js` to import the persistence helpers from the focused module while leaving other review state helpers in `gmail_review_state.js`.
- Add ESM contract/probe coverage and static asset graph coverage.

Out of scope:
- Live Gmail/OAuth/native-host testing.
- Any change to DOM IDs, dataset names, routes, submitted values, payload shapes, or renderer text insertion.
- Broader review-state refactors.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_review_persistence`
- Branch name: `codex/gmail-review-persistence`
- Base branch: `main`
- Base SHA: `666462470a5692bd66743b413832cb803dd8e89e`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use shadow browser mode only.

## Interfaces/Types/Contracts Affected

- New internal static browser module: `src/legalpdf_translate/shadow_web/static/gmail_review_persistence.js`
- Compatibility re-exports from `gmail_review_state.js` keep existing internal import contracts available.
- No backend routes, request/response payloads, submitted values, selector names, DOM IDs, Gmail/native-host contracts, or extension contracts change.

## File-by-File Implementation Steps

1. Add a focused contract/probe test in `tests/test_shadow_web_api.py`, then confirm RED before production code.
2. Add `gmail_review_persistence.js` with pure/session-storage-safe exports:
   - `gmailReviewStorageKey`
   - `readConsumedReviewState`
   - `writeConsumedReviewState`
   - `clearConsumedReviewState`
   - `shouldAutoOpenReview`
3. Update `gmail_review_state.js` to import/re-export those helpers and remove their inline definitions.
4. Update `gmail.js` to import these helpers from `gmail_review_persistence.js`.
5. Update static asset graph coverage for `gmail_review_persistence.js`.
6. Run targeted, focused, full validation, and shadow smoke.
7. Mark complete and move this plan to `completed/` before commit.

## Tests and Acceptance Criteria

- Targeted:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_review_persistence_module_owns_review_consumption_state`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow smoke on port `8888`:
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-persistence-smoke#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, demo attachment load, and normal review/preview interaction. Do not touch live Gmail.

## Rollout and Fallback

Publish via ready PR after validation. If CI fails, conflicts appear, or GitHub auth is unavailable, stop before merge. Fallback is to revert this internal module extraction before merge.

## Risks and Mitigations

- Risk: changing session storage keys and causing repeated or missing auto-open behavior. Mitigation: exact key/value and invalid JSON probes plus existing review-state storage tests.
- Risk: breaking existing internal imports from `gmail_review_state.js`. Mitigation: compatibility re-exports and targeted legacy test.
- Risk: accidentally moving DOM or rendering behavior into persistence. Mitigation: contract test forbids DOM, renderer, fetch, app state, and `innerHTML` markers.

## Assumptions/Defaults

- No live Gmail testing is in scope.
- User authorized PR-first publish/merge flow for the next recommended modernization slice.
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

## Completion Evidence

- RED confirmed first: `tests/test_shadow_web_api.py::test_gmail_review_persistence_module_owns_review_consumption_state` failed before `gmail_review_persistence.js` existed.
- Targeted tests passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_review_persistence_module_owns_review_consumption_state`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite passed: `221 passed in 172.66s`.
- Full validation passed with the known Dart AOT launcher issue handled by direct-Dart fallback success for both docs and workspace hygiene validators.
- Shadow smoke passed on port `8888` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-persistence-smoke#gmail-intake`: page identity was `LegalPDF Translate`, meaningful Gmail review content rendered, no framework overlay text appeared, console warnings/errors were zero, demo attachments loaded, the review drawer opened, and the PDF preview rendered `gmail-preview-canvas` with a shadow-mode attachment URL. No live Gmail, OAuth, native-host, or real draft flow was touched.
