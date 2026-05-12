# Gmail Handoff State Helpers

## Goal and Non-Goals

Extract Gmail pending-review and extension handoff state shaping into a pure internal browser module while preserving every route, payload shape, selector, DOM ID, submitted value, Gmail/native-host contract, and safe rendering path.

Non-goals: change Gmail review behavior, live Gmail/OAuth/native-host flows, hydration marker dataset names, source Gmail URL precedence, browser routing, or UI text.

## Scope

In scope:
- Add `src/legalpdf_translate/shadow_web/static/gmail_handoff_state.js`.
- Move pure client launch/handoff marker derivation out of `app.js`.
- Move pure Gmail pending-review bootstrap selectors out of `gmail.js`.
- Move `deriveGmailSourceUrl` out of `gmail_action_presentation.js`, with a compatibility re-export.
- Add contract/ESM/static asset coverage.

Out of scope:
- Backend API, route, request/response, or extension contract changes.
- Live Gmail, OAuth, native-host, or real draft testing.
- Broader Gmail review-state or renderer refactors.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_handoff_state`
- Branch name: `codex/gmail-handoff-state`
- Base branch: `main`
- Base SHA: `f89761f79b45f5fda26477a41e0babefe7997b6d`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use shadow browser mode only.

## Interfaces/Contracts Affected

- New internal static browser module:
  - `deriveClientLaunchSessionUrlState({ href })`
  - `deriveClientGmailHandoffState({ payload, workspaceId })`
  - `deriveClientLaunchSessionId({ payload, href })`
  - `deriveClientHandoffSessionId({ payload, href })`
  - `deriveClientLaunchSessionSchemaVersion({ payload, href })`
  - `deriveGmailBootstrapMessageContext({ bootstrap })`
  - `deriveGmailPendingIntakeContext({ bootstrap })`
  - `deriveGmailClickDiagnostics({ bootstrap })`
  - `deriveGmailPendingStatus({ bootstrap })`
  - `deriveGmailPendingReviewOpen({ bootstrap })`
  - `deriveGmailSourceUrl(context)`
- Compatibility re-export from `gmail_action_presentation.js` preserves existing internal imports for `deriveGmailSourceUrl`.

## File-by-File Implementation Steps

1. Add a focused contract/ESM test in `tests/test_shadow_web_api.py`; confirm RED before production code.
2. Add `gmail_handoff_state.js` with only pure state-shaping helpers.
3. Update `app.js` to gather `href`, `payload`, and workspace state, then call the client handoff helpers.
4. Update `gmail.js` to call the Gmail pending/source helpers instead of shaping bootstrap state inline.
5. Update `gmail_action_presentation.js` to import/re-export `deriveGmailSourceUrl`.
6. Update static asset graph coverage.
7. Run targeted, focused, full validation, and shadow Browser smoke.
8. Mark complete and move this plan to `completed/` before commit.

## Tests and Acceptance Criteria

- RED first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_handoff_state_module_owns_pending_review_and_launch_state`
- Targeted after implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_handoff_state_module_owns_pending_review_and_launch_state`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_action_presentation_module_derives_prepare_action_state`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_client_prefers_url_launch_session_state_over_stale_bootstrap`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow smoke on port `8888`:
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-handoff-state-smoke#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, demo attachment load, return/source controls remain inert in shadow, and normal review/preview interaction. Do not touch live Gmail.

## Rollout and Fallback

Publish via ready PR after validation. Stop before merge if CI fails, conflicts appear, or GitHub auth is unavailable. Fallback is to revert this internal extraction before merge.

## Risks and Mitigations

- Risk: changing extension handoff marker precedence. Mitigation: ESM probes for URL, Gmail payload, shell, and runtime precedence.
- Risk: changing pending-review warmup state. Mitigation: exact pending status/open probes and existing workspace-stability tests.
- Risk: moving source Gmail URL behavior from an action presentation module. Mitigation: compatibility re-export and exact source URL precedence probes.
- Risk: accidentally adding DOM or rendering behavior to the state module. Mitigation: contract test forbids DOM, renderer, fetch, `appState`, and `innerHTML` markers.

## Assumptions/Defaults

- User authorized PR-first publish/merge flow for the next recommended modernization slice.
- No live Gmail testing is in scope.
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

## Completion Evidence

- RED confirmed first: `tests/test_shadow_web_api.py::test_gmail_handoff_state_module_owns_pending_review_and_launch_state` failed because `gmail_handoff_state.js` did not exist.
- Targeted tests passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_handoff_state_module_owns_pending_review_and_launch_state`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_action_presentation_module_derives_prepare_action_state tests/test_shadow_web_api.py::test_shadow_web_client_prefers_url_launch_session_state_over_stale_bootstrap tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite passed: `222 passed in 178.71s`.
- Full validation passed with `218 passed`, compileall success, Gmail review tests success, Gmail intake focused success, and the known Dart AOT launcher issue handled by direct-Dart fallback success for both docs and workspace hygiene validators.
- Shadow smoke passed on port `8888` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-handoff-state-smoke#gmail-intake`: page identity was `LegalPDF Translate`, meaningful Gmail review content rendered, no framework overlay text appeared, console warnings/errors were zero, demo attachments loaded, the review drawer opened, the PDF preview rendered `gmail-preview-canvas`, the shadow attachment URL stayed in shadow mode, and return-to-source stayed hidden/inert without a source URL. No live Gmail, OAuth, native-host, or real draft flow was touched.
