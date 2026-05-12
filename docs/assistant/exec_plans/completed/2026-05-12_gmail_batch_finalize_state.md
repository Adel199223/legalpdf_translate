# Gmail Batch Finalize State Extraction

## Goal And Non-Goals

Move Gmail batch-finalization state selection out of `gmail.js` and into a pure static browser module, preserving the existing renderer, presentation builders, routes, payloads, selectors, diagnostics, and Gmail/native-host behavior.

Non-goals:
- No backend route, payload shape, submitted value, DOM ID, dataset, Gmail/native-host, extension contract, or safe-rendering changes.
- No live Gmail, OAuth, native-host, or real draft testing.
- No renderer, UI copy, finalization diagnostics, request payload, or browser-PDF behavior changes.

## Scope

In scope:
- Create `src/legalpdf_translate/shadow_web/static/gmail_batch_finalize_state.js`.
- Export pure helpers for displayed-session selection, preflight selection, finalization-state derivation, and batch-finalize surface input shaping.
- Update `gmail.js` so report context, batch-finalize surface rendering, and batch finalization preflight fallback call those helpers.
- Add contract and ESM probe coverage.
- Add versioned static asset coverage for the new module.

Out of scope:
- Moving fetch calls, event listeners, drawer toggles, diagnostics rendering, or presentation rendering out of `gmail.js`.
- Changing `gmail_finalize_presentation.js` or `gmail_finalize_ui.js`.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_batch_finalize_state`
- Branch name: `codex/gmail-batch-finalize-state`
- Base branch: `main`
- Base SHA: `4632b519db6c0b8f52abe6b0154a654a66b6d5c6`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow-mode browser smoke only

## Interfaces And Contracts

New pure module exports:
- `selectGmailDisplayedBatchFinalizeSession({ drawerSource, activeSession, restoredCompletedSession })`
- `selectGmailBatchFinalizePreflight({ drawerSource, batchFinalizePreflight, displayedSession })`
- `deriveGmailBatchFinalizeState({ payload, displayedSession, preflight })`
- `buildGmailBatchFinalizeSurfaceState({ activeSessionOverride, drawerSource, activeSession, restoredCompletedSession, batchFinalizePreflight, batchFinalizeResult, batchFinalizePreflightInFlight })`

Preserve behavior:
- Restored drawer source uses a restored completed translation session only.
- Active drawer source uses an active completed translation session only.
- Restored drawer source suppresses preflight (`null`).
- Explicit `batchFinalizePreflight` wins over session preflight and is shallow-cloned.
- Session preflight is shallow-cloned when no explicit preflight exists.
- Finalization-state precedence stays payload normalized state, displayed session state, derived preflight state, empty string.
- Surface state keeps the active-session override fallback for the rendered session while deriving preflight/finalization from the displayed-session selector.

## File-By-File Steps

1. `tests/test_shadow_web_api.py`
   - Add a failing contract/probe test for the new `gmail_batch_finalize_state.js` module.
   - Extend the versioned static asset graph test for the new module and exports.
2. `src/legalpdf_translate/shadow_web/static/gmail_batch_finalize_state.js`
   - Add pure state selector exports.
   - Keep the module free of DOM, fetch, diagnostics, app state, renderers, and unsafe rendering.
3. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - Import the new helpers.
   - Remove the inline selector functions.
   - Use the helpers in `currentGmailFinalizationReportContext`, `renderBatchFinalizeSurface`, and `finalizeBatch`.
4. Move this ExecPlan to `completed/` after validation and before commit.

## Tests And Acceptance Criteria

- Confirm RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_batch_finalize_state_module_owns_batch_finalize_state_shaping`
- After implementation:
  - Run the targeted batch-finalize state test.
  - Run `tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`.
  - Run the focused browser/Gmail suite:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Run `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
- Browser smoke:
  - Launch shadow app on port `8888`.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-batch-finalize-state-smoke#gmail-intake`.
  - Check page identity, nonblank content, no framework overlay, console health, screenshot evidence, load demo attachments, select/preview demo PDF, and no live Gmail/OAuth/native-host flow.

## Rollout And Fallback

- Commit only intended files after validation.
- Push `codex/gmail-batch-finalize-state`, open ready PR `[codex] Extract Gmail batch finalize state selectors`, wait for green checks, merge normally, fast-forward canonical `main`, prune refs, and remove the worktree after `main` contains the merge.
- If GitHub auth, PR creation, CI, conflicts, or checks block the flow, stop before merge and report the blocker.
- Fallback is reverting this narrow extraction; no persisted data migration is involved.

## Risks And Mitigations

- Risk: restored-mode finalization behavior changes. Mitigation: tests lock restored-session selection and restored preflight suppression.
- Risk: object identity changes unexpectedly. Mitigation: tests assert selected sessions keep identity while preflight objects are shallow clones.
- Risk: surface-state extraction accidentally absorbs side effects. Mitigation: contract test forbids `document`, `innerHTML`, `fetch`, diagnostics, renderers, and `appState`.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- The new exports are internal static-browser module interfaces only, not public backend APIs.
- The user authorized PR-first implementation, validation, publish, merge, and cleanup flow.

## Completion Log

Status: Complete.

Validation:
- RED confirmed before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_batch_finalize_state_module_owns_batch_finalize_state_shaping`
  failed because `gmail_batch_finalize_state.js` did not exist.
- Targeted state contract:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_batch_finalize_state_module_owns_batch_finalize_state_shaping`
  passed, `1 passed in 3.52s`.
- Static asset graph:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  passed, `1 passed in 1.97s`.
- Focused browser/Gmail suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  passed, `217 passed in 165.13s`.
- Full validation:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  completed successfully. The wrapper hit the known `Unable to find AOT snapshot for dartdev` issue for agent-docs and workspace-hygiene validation, then direct-Dart fallback succeeded for both.

Browser smoke:
- Launched the feature worktree shadow app on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-batch-finalize-state-smoke#gmail-intake`.
- The in-app Browser runtime was attempted first but reported no active Codex browser pane, so the browser tooling's Playwright fallback was used against fresh workspace `gmail-batch-finalize-state-smoke-pw`.
- Verified page identity (`LegalPDF Translate`), nonblank Gmail intake content, no framework overlay, and no warning/error console logs.
- Interaction proof loaded demo attachments, selected `demo-gmail-review.pdf`, opened preview, and rendered `gmail-preview-canvas` at `827x1070` with status `Previewing page 1 of 1. Use current page if you want the translation to start later in the document.`
- No live Gmail, OAuth, native-host, or real draft flow was touched.
