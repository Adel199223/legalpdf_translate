# Gmail Request Payload Extraction

## Goal And Non-Goals

Extract Gmail session/finalization request payload shaping from `gmail.js` into a pure static module, while keeping `gmail.js` responsible for route calls, UI state, diagnostics, and side effects.

Non-goals:
- No backend route, payload shape, selector, DOM ID, dataset, submitted value, Gmail/native-host, or extension contract changes.
- No live Gmail, OAuth, native-host, or real draft testing.
- No UI rendering, presentation copy, or browser-PDF behavior changes.

## Scope

In scope:
- Add `gmail_request_payloads.js` with pure builders for Gmail session/finalization request bodies in `gmail.js`.
- Update `gmail.js` to call those builders before `JSON.stringify(...)`.
- Add contract and ESM probe coverage.
- Extend the versioned static asset graph test for the new module.

Out of scope:
- Moving fetch calls or route selection out of `gmail.js`.
- Changing report context construction, preview bundle behavior, finalization presentation, or action planning.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_request_payloads`
- Branch name: `codex/gmail-request-payloads`
- Base branch: `main`
- Base SHA: `769d110cf45748413349c6df9f689b5e9eafc582`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow-mode browser smoke only

## Interfaces, Types, And Contracts

- Preserve request routes:
  - `/api/gmail/prepare-session`
  - `/api/gmail/batch/finalize-preflight`
  - `/api/gmail/batch/confirm-current`
  - `/api/gmail/batch/finalize`
  - `/api/gmail/interpretation/finalize`
- Preserve existing JSON object keys and values for all extracted payloads.
- Keep the new module free of DOM reads/writes, fetch calls, renderers, diagnostics, and app state.

## File-By-File Steps

1. `tests/test_shadow_web_api.py`
   - Add a failing contract/probe test for `gmail_request_payload.js`.
   - Extend the versioned static asset graph test.
2. `src/legalpdf_translate/shadow_web/static/gmail_request_payloads.js`
   - Add pure payload builder exports.
   - Preserve null-safe defaults only where existing `gmail.js` already supplied fallback values.
3. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - Import the builders.
   - Replace inline request object literals with builder calls.
   - Leave routes, fetch options, state updates, diagnostics, and UI behavior unchanged.
4. Move this ExecPlan to `completed/` after validation and before commit.

## Tests And Acceptance Criteria

- Confirm RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_session_and_finalization_payloads`
- After implementation:
  - Run the targeted request payload test.
  - Run `tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`.
  - Run the focused browser/Gmail suite:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Run `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
- Browser smoke:
  - Launch shadow app on port `8888`.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-request-payloads-smoke#gmail-intake`.
  - Check page identity, nonblank content, no framework overlay, console health, screenshot evidence, load demo attachments, and normal review/preview interaction without live Gmail.

## Rollout And Fallback

- Commit only intended files after validation.
- Push `codex/gmail-request-payloads`, open ready PR `[codex] Extract Gmail request payload builders`, wait for green checks, merge normally, fast-forward canonical `main`, prune refs, and remove the worktree after `main` contains the merge.
- If GitHub auth, PR creation, CI, conflicts, or checks block the flow, stop before merge and report the blocker.
- Fallback is reverting this narrow extraction; no persisted data migration is involved.

## Risks And Mitigations

- Risk: payload semantics drift. Mitigation: ESM probes assert exact payloads, malicious string preservation, and null-safe defaults.
- Risk: helper grows side effects. Mitigation: contract test forbids `document`, `innerHTML`, `fetchJson`, `setDiagnostics`, `renderGmail`, and `appState`.
- Risk: Browser runtime has known local PDF preview limitation. Mitigation: use in-app Browser first, then record local Playwright fallback only if that limitation appears again.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- `main` at `769d110cf45748413349c6df9f689b5e9eafc582` is the clean approved base.
- The new module is an internal static-browser module, not a public backend API.

## Validation Log

- 2026-05-12 RED confirmed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_session_and_finalization_payloads` failed before implementation because `gmail_request_payloads.js` did not exist.
- 2026-05-12 Targeted request-payload contract passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_session_and_finalization_payloads` -> 1 passed.
- 2026-05-12 Static asset graph passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` -> 1 passed.
- 2026-05-12 Focused browser/Gmail suite passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py` -> 215 passed.
- 2026-05-12 Full validation passed: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`. The wrapper reported the known `dart run` / `dartdev` AOT snapshot issue for agent docs and workspace hygiene validation, then direct-Dart fallback succeeded for both.
- 2026-05-12 Browser shadow smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-request-payloads-smoke-ui#gmail-intake`: page title `LegalPDF Translate`, nonblank Gmail intake content, no framework overlay, in-app Browser screenshot evidence captured with the loopback screenshot shim, console had 0 warnings/errors on the clean smoke tab, `Load demo attachments` succeeded, selecting `demo-gmail-review.pdf` showed `1 selected`, PDF preview opened with `gmail-preview-canvas` 827x1070, preview href stayed under `/api/gmail/attachment/demo-gmail-review-pdf?mode=shadow&workspace=gmail-request-payloads-smoke-ui#page=1`, and no live Gmail/OAuth/native-host flow was touched.
- 2026-05-12 Read-only reviewer found no contract regressions. Residual test gap noted: tests lock builder outputs and static graph coverage, while the smoke covers review/preview UI rather than a successful prepare-session because the shadow demo account is not a live Gmail account.

## Completion

- Completed 2026-05-12.
