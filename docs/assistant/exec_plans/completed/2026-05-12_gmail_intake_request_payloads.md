# Gmail Intake Request Payload Extraction

## Goal And Non-Goals

Extract the remaining Gmail intake/report/runtime-reset request body shaping from `gmail.js` into the existing pure request payload module, while keeping `gmail.js` responsible for DOM reads, route calls, UI state, diagnostics, and side effects.

Non-goals:
- No backend route, payload shape, selector, DOM ID, dataset, submitted value, Gmail/native-host, or extension contract changes.
- No live Gmail, OAuth, native-host, or real draft testing.
- No renderer, presentation copy, browser-PDF, or route behavior changes.

## Scope

In scope:
- Extend `gmail_request_payloads.js` with pure builders for Gmail load-message, empty POST, browser-failure report, finalization report, and canonical-runtime restart request bodies.
- Update `gmail.js` to call those builders before `JSON.stringify(...)`.
- Add contract and ESM probe coverage.
- Extend the versioned static asset graph test for the new exports.

Out of scope:
- Moving fetch calls, route names, diagnostics, state updates, or event handling out of `gmail.js`.
- Changing the already-extracted session/finalization builders.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_intake_request_payloads`
- Branch name: `codex/gmail-intake-request-payloads`
- Base branch: `main`
- Base SHA: `591f98302129e5631d9c32f2aab4b4950dd64394`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow-mode browser smoke only

## Interfaces, Types, And Contracts

Preserve request routes:
- `/api/gmail/runtime/restart-canonical`
- `/api/gmail/load-message`
- `/api/gmail/demo-review`
- `/api/power-tools/diagnostics/run-report`
- `/api/gmail/reset`

Preserve existing JSON object keys and values:
- `mode`
- `workspace_id`
- `message_context`
- `browser_failure_context`
- `gmail_finalization_context`
- empty object payloads for demo review/reset

Keep the request payload module free of DOM reads/writes, fetch calls, renderers, diagnostics, and app state.

## File-By-File Steps

1. `tests/test_shadow_web_api.py`
   - Add a failing contract/probe test for the additional `gmail_request_payloads.js` builders.
   - Extend the versioned static asset graph test for the new exports.
2. `src/legalpdf_translate/shadow_web/static/gmail_request_payloads.js`
   - Add pure payload builder exports.
   - Preserve references for passed report/context objects where the old inline payload did.
3. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - Import the added builders.
   - Replace the remaining targeted inline request object literals with builder calls.
   - Leave routes, fetch options, state updates, diagnostics, and UI behavior unchanged.
4. Move this ExecPlan to `completed/` after validation and before commit.

## Tests And Acceptance Criteria

- Confirm RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_intake_report_and_runtime_payloads`
- After implementation:
  - Run the targeted intake/report request payload test.
  - Run `tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`.
  - Run the focused browser/Gmail suite:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Run `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
- Browser smoke:
  - Launch shadow app on port `8888`.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-intake-request-payloads-smoke#gmail-intake`.
  - Check page identity, nonblank content, no framework overlay, console health, screenshot evidence, load demo attachments, select/preview demo PDF, and no live Gmail/OAuth/native-host flow.

## Rollout And Fallback

- Commit only intended files after validation.
- Push `codex/gmail-intake-request-payloads`, open ready PR `[codex] Extract Gmail intake request payload builders`, wait for green checks, merge normally, fast-forward canonical `main`, prune refs, and remove the worktree after `main` contains the merge.
- If GitHub auth, PR creation, CI, conflicts, or checks block the flow, stop before merge and report the blocker.
- Fallback is reverting this narrow extraction; no persisted data migration is involved.

## Risks And Mitigations

- Risk: payload semantics drift. Mitigation: ESM probes assert exact payloads, malicious string preservation, object references, and null-safe defaults.
- Risk: helper grows side effects. Mitigation: contract test forbids `document`, `innerHTML`, `fetchJson`, `setDiagnostics`, `renderGmail`, and `appState`.
- Risk: empty payload builders feel unnecessary. Mitigation: include them only for existing Gmail POST bodies that already send `{}`, keeping route-side behavior explicit and test-locked.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- The new exports are internal static-browser module interfaces only, not public backend APIs.
- The user authorized PR-first implementation, validation, publish, merge, and cleanup flow.

## Completion Log

Status: Complete.

Validation:
- RED confirmed before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_intake_report_and_runtime_payloads`
  failed on the missing `buildGmailRestartCanonicalRuntimeRequestPayload` export.
- Targeted payload tests:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_session_and_finalization_payloads tests/test_shadow_web_api.py::test_gmail_request_payloads_module_builds_intake_report_and_runtime_payloads`
  passed, `2 passed in 4.02s`.
- Static asset graph:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  passed, `1 passed in 2.11s`.
- Focused browser/Gmail suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  passed, `216 passed in 164.34s`.
- Diff hygiene:
  `git diff --check` passed.
- Full validation:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  completed successfully. The wrapper hit the known `Unable to find AOT snapshot for dartdev` issue for agent-docs and workspace-hygiene validation, then direct-Dart fallback succeeded for both.

Browser smoke:
- Launched the feature worktree shadow app on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-intake-request-payloads-smoke#gmail-intake`.
- Browser verified page identity (`LegalPDF Translate`), nonblank Gmail intake content, no framework overlay, and no warning/error console logs.
- Browser Playwright click on the local page timed out, so the same browser tooling's Playwright fallback was used for interaction proof against fresh workspace `gmail-intake-request-payloads-smoke-pw`.
- Interaction proof loaded demo attachments, selected `demo-gmail-review.pdf`, opened preview, and rendered `gmail-preview-canvas` at `827x1070` with status `Previewing page 1 of 1. Use current page if you want the translation to start later in the document.`
- No live Gmail, OAuth, native-host, or real draft flow was touched.
