# Gmail Shell Sync State Helpers

Status: Complete on 2026-05-12.

## Goal and Non-Goals

Extract the remaining Gmail shell-sync payload shaping out of `gmail.js` into a pure internal browser module. Preserve every Gmail bootstrap key, route, payload shape, selector, DOM ID, submitted value, Gmail/native-host contract, and safe rendering path.

Non-goals: change Gmail review behavior, shell event dispatching, pending-review semantics, hydration markers, backend APIs, live Gmail, OAuth, native-host, or real draft flows.

## Scope

In scope:
- Add `src/legalpdf_translate/shadow_web/static/gmail_shell_state.js` exporting `buildGmailShellSyncState(...)`.
- Update `gmail.js` so `syncShellState()` gathers coordinator state and delegates only the Gmail payload object construction to the builder.
- Add contract/ESM/static asset coverage.

Out of scope:
- Moving `renderWorkspaceStrip()`, refresh scheduling, or `legalpdf:shell-state-updated` side effects.
- Any public backend or extension contract changes.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_shell_state`
- Branch name: `codex/gmail-shell-state`
- Base branch: `main`
- Base SHA: `c257eb27eeb4d48398bab638861a7175e27276eb`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use shadow browser mode only.

## Interfaces/Contracts Affected

- New internal static browser module:
  - `buildGmailShellSyncState({ existingGmail, bootstrap, loadResult, activeSession, restoredCompletedSession, interpretationSeed, suggestedTranslationLaunch, pendingStatus, pendingIntakeContext, pendingReviewOpen, stage })`
- Output shape must match the existing inline shell Gmail patch exactly:
  - previous Gmail payload fields are preserved
  - bootstrap fields overlay previous fields
  - current coordinator values overlay both
  - key names remain `load_result`, `active_session`, `restored_completed_session`, `interpretation_seed`, `suggested_translation_launch`, `pending_status`, `pending_intake_context`, `pending_review_open`, and `stage`

## File-by-File Implementation Steps

1. Add a focused contract/ESM test in `tests/test_shadow_web_api.py`; confirm RED before production code.
2. Add `gmail_shell_state.js` with only pure state-shaping helpers.
3. Update `gmail.js` to import and call `buildGmailShellSyncState(...)` from `syncShellState()`.
4. Update static asset graph coverage for `gmail_shell_state.js`.
5. Run targeted, focused, full validation, and shadow Browser smoke.
6. Mark complete and move this plan to `completed/` before commit.

## Tests and Acceptance Criteria

- RED first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_shell_state_module_owns_shell_sync_payload`
- Targeted after implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_shell_state_module_owns_shell_sync_payload`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_handoff_state_module_owns_pending_review_and_launch_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow smoke on port `8888`:
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-shell-state-smoke#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, demo attachment load, and normal review/preview interaction. Do not touch live Gmail.

Completion evidence:
- RED confirmed first for `tests/test_shadow_web_api.py::test_gmail_shell_state_module_owns_shell_sync_payload` before adding `gmail_shell_state.js`.
- Targeted shell-state contract passed: `1 passed`.
- Adjacent handoff/static asset checks passed: `2 passed`.
- Focused browser/Gmail suite passed: `223 passed in 173.04s`.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passed; `dart run` hit the known AOT snapshot issue and the wrapper's direct-Dart fallback succeeded for agent docs and workspace hygiene validators.
- Shadow browser smoke passed on port `8888` in `gmail-shell-state-smoke`: LegalPDF page identity, nonblank content, no framework overlay text, demo attachment load, preview canvas `gmail-preview-canvas`, open-tab href, and zero console warnings/errors verified. No live Gmail/OAuth/native-host flow was touched.

## Rollout and Fallback

Publish via ready PR after validation. Stop before merge if CI fails, conflicts appear, or GitHub auth is unavailable. Fallback is to revert this internal extraction before merge.

## Risks and Mitigations

- Risk: changing Gmail bootstrap field precedence. Mitigation: ESM probes assert previous < bootstrap < current coordinator precedence.
- Risk: changing raw `pending_status` preservation. Mitigation: tests cover malicious mixed-case whitespace status as data.
- Risk: moving side effects into the pure module. Mitigation: contract test forbids DOM, event, renderer, fetch, `appState`, and `innerHTML` markers.

## Assumptions/Defaults

- User authorized PR-first publish/merge flow for the next recommended modernization slice.
- No live Gmail testing is in scope.
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.
