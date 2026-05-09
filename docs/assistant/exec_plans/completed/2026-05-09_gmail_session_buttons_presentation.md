# Gmail Session Button Rules Presentation

## Goal and Non-Goals

Extract the Gmail session button enablement rules from `gmail.js` into a pure presentation builder while preserving the existing renderer, DOM IDs, event listeners, routes, payloads, Gmail/native-host behavior, and safe rendering contracts.

Non-goals:
- Do not change `gmail_session_ui.js` renderer behavior.
- Do not change backend route paths, API payload shapes, submitted values, selectors, or Gmail/native-host contracts.
- Do not touch live Gmail, OAuth, or native-host flows.

## Scope

In:
- Add `buildGmailSessionButtonRules(...)` to `gmail_session_presentation.js`.
- Update `gmail.js` so `updateSessionButtons()` gathers coordinator state, calls the builder, maps IDs to elements, and delegates to `renderGmailSessionButtonsInto(...)`.
- Add contract and ESM probe tests for the pure builder and updated ownership boundary.
- Validate shadow Gmail/browser behavior only.

Out:
- Any public API, route, extension, or selector contract changes.
- Any live Gmail testing.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_session_buttons_presentation`
- Branch name: `codex/gmail-session-buttons-presentation`
- Base branch: `origin/main`
- Base SHA: `4a0ba8cb33ee3edc88568f68014ce0844485a705`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; browser validation must use shadow mode with isolated app data.

## Interfaces, Types, and Contracts Affected

- New pure JavaScript export:
  - `buildGmailSessionButtonRules({ activeSession, translationReady, interpretationReady })`
- Returned presentation shape:
  - `{ sessionAvailable: boolean, rules: Array<[buttonId: string, enabled: boolean]> }`
- Existing renderer contract remains:
  - `renderGmailSessionButtonsInto(Array<[HTMLElement | null, boolean]>)`
- Existing button IDs remain unchanged:
  - `gmail-load-translation-launch`
  - `gmail-confirm-translation`
  - `gmail-finalize-batch`
  - `gmail-load-interpretation-seed`
  - `gmail-finalize-interpretation`

## File-by-File Implementation Steps

1. `tests/test_shadow_web_api.py`
   - Add failing ESM probe coverage for the builder: no session, translation waiting, translation ready, completed translation, interpretation waiting, interpretation ready, invalid kind, and null-safe defaults.
   - Tighten the existing session button renderer ownership test so `gmail.js` must call the builder and must not inline the rule predicates.
   - Update the versioned static asset graph test to assert the builder export is served.

2. `src/legalpdf_translate/shadow_web/static/gmail_session_presentation.js`
   - Add `buildGmailSessionButtonRules(...)`.
   - Keep it pure: no DOM access, no renderer calls, no unsafe HTML writes.

3. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - Import `buildGmailSessionButtonRules`.
   - Update `updateSessionButtons()` to gather state, call the builder, map IDs through `qs(...)`, call `renderGmailSessionButtonsInto(...)`, and close the session drawer only when the presentation reports no active session.

## Tests and Acceptance Criteria

Red phase:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_session_button_rules tests/test_shadow_web_api.py::test_gmail_session_ui_module_owns_session_buttons_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Green phase:
- Same targeted tests pass.
- Focused browser/Gmail suite passes:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation passes:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - If `dart run ...` reports the known AOT launcher issue, record it only when the direct-Dart fallback succeeds.

Browser smoke:
- Launch shadow preview from this worktree on port `8888`:
  - `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace gmail-session-buttons-smoke --port 8888`
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-session-buttons-smoke#gmail-intake`.
- Check page identity, nonblank content, no framework overlay, console health, screenshot evidence, demo attachment surface, and session button behavior without live Gmail.

## Rollout and Fallback

- Commit only intended files after validation.
- Push branch and create ready PR titled `[codex] Extract Gmail session button presentation`.
- Wait for green required checks, merge normally, fast-forward local canonical `main`, prune refs, and remove this feature worktree only after `main` contains the merge.
- Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending.

Fallback:
- If tests or smoke reveal a behavior change, revert the local feature edits in the worktree only and keep canonical `main` untouched.

## Risks and Mitigations

- Risk: moving rule predicates changes button enablement.
  - Mitigation: ESM probes cover all active session kinds and readiness combinations.
- Risk: unsafe rendering regression.
  - Mitigation: builder is pure and renderer remains the existing safe DOM writer.
- Risk: accidental public contract drift.
  - Mitigation: tests assert IDs and static asset exports; code changes avoid routes, payloads, selectors, and Gmail/native-host code.

## Assumptions and Defaults

- No live Gmail/OAuth/native-host testing is in scope.
- Shadow-mode browser smoke is sufficient for UI verification.
- The PR should be ready for review and merge after local validation passes.

## Completion Notes

- Added `buildGmailSessionButtonRules(...)` to `gmail_session_presentation.js`.
- Updated `updateSessionButtons()` in `gmail.js` to gather coordinator state, call the builder, map rule IDs through `qs(...)`, pass element/boolean pairs to `renderGmailSessionButtonsInto(...)`, and close the session drawer only when `sessionAvailable` is false.
- Left `gmail_session_ui.js`, IDs, event listeners, routes, payloads, Gmail/native-host behavior, and safe rendering contracts unchanged.
- Confirmed targeted red phase before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_session_button_rules tests/test_shadow_web_api.py::test_gmail_session_ui_module_owns_session_buttons_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result before implementation: 3 failed for the missing builder/export/call-site.
- Confirmed targeted green phase after implementation:
  - Same command: 3 passed.
- Focused browser/Gmail suite passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: 196 passed.
- Full validation passed:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: validation complete.
  - Known Dart AOT launcher issue occurred for `dart run tooling/validate_agent_docs.dart` and `dart run tooling/validate_workspace_hygiene.dart`; the wrapper used the direct Dart executable fallback and both validations passed.
- Browser smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-session-buttons-smoke#gmail-intake`.
  - Browser verified page identity (`LegalPDF Translate`), nonblank Gmail review content, no framework overlay, clean console, hydration completion, demo attachment load, and selection/continue interaction.
  - The continue action reached the existing shadow demo Gmail account resolution guard and did not touch live Gmail/OAuth/native-host flows.
  - Browser screenshot capture timed out on local CDP `Page.captureScreenshot`; Playwright fallback captured `gmail-session-buttons-smoke.png` for screenshot evidence.
- Read-only subagent review found no issues.
