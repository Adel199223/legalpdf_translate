# Interpretation Result Presentation

Status: Completed 2026-05-12

## Goal and Non-Goals

Move interpretation export/Gmail result card state shaping out of `interpretation_result_ui.js` into a pure presentation module. Keep the existing safe DOM renderer path, route flow, IDs, selectors, payload contracts, Gmail/native-host behavior, and submitted values unchanged.

This does not change backend APIs, live Gmail behavior, OAuth/native-host behavior, finalization payload shapes, or any extension contract.

## Scope

In scope:
- Create `src/legalpdf_translate/shadow_web/static/interpretation_result_presentation.js`.
- Export pure builders:
  - `buildInterpretationExportResultPresentation({ payload, presentation })`
  - `buildInterpretationGmailResultPresentation({ payload, presentation })`
- Update `app.js` to gather coordinator state, call the builders, and pass presentation objects to `interpretation_result_ui.js`.
- Update `interpretation_result_ui.js` so export/Gmail result renderers only perform safe DOM writes from already-shaped presentation objects.
- Add ESM, ownership, and static asset coverage.

Out of scope:
- Live Gmail/OAuth/native-host testing.
- Changing renderer labels, DOM IDs, routes, selectors, submitted values, backend payloads, or safe rendering helpers.
- Refactoring unrelated interpretation cards.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_interpretation_result_presentation`
- Branch name: `codex/interpretation-result-presentation`
- Base branch: `main`
- Base SHA: `0e3cd232c7cecb376a735878646c754749185df3`
- Target integration branch: `main`
- Canonical build status: feature worktree only; browser smoke must use shadow mode with isolated workspace data.

## Interfaces and Contracts Affected

- Internal browser static module interface: new `interpretation_result_presentation.js` exports two pure builders.
- Internal renderer interface changes from raw payload + global presentation to card presentation objects for export/Gmail result cards.
- `renderInterpretationExportResultInto(...)`, `renderInterpretationExportPanelResultInto(...)`, and `renderInterpretationGmailResultInto(...)` keep their names and DOM behavior.
- No public backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes.

## File-by-File Implementation Steps

1. `tests/test_interpretation_result_presentation.py`
   - Add ESM probe coverage for export result ok/local-only/failure/null-safe and Gmail result ok/local-only/warning/empty/null-safe with malicious text treated as inert data.
2. `tests/test_shadow_web_api.py`
   - Add ownership coverage proving the new presentation module is pure, exports both builders, `app.js` imports/calls them, and targeted payload/status shaping is removed from the export/Gmail renderers.
   - Extend the versioned static asset graph assertion for `interpretation_result_presentation.js`.
   - Adjust safe-rendering probe calls to pass card presentation objects instead of raw payloads.
3. `src/legalpdf_translate/shadow_web/static/interpretation_result_presentation.js`
   - Implement pure builders preserving existing title, label, tone, message, path, PDF export, and fallback behavior exactly.
4. `src/legalpdf_translate/shadow_web/static/interpretation_result_ui.js`
   - Update export/Gmail renderers to render shaped card objects and keep all writes safe.
5. `src/legalpdf_translate/shadow_web/static/app.js`
   - Import builders and call them in `renderInterpretationExportResult(...)` and `renderInterpretationGmailResult(...)`.

## Tests and Acceptance Criteria

RED target before implementation:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_result_presentation.py::test_interpretation_result_presentation_builds_export_and_gmail_cards tests/test_shadow_web_api.py::test_interpretation_result_presentation_module_owns_export_and_gmail_result_state`

Post-implementation targets:
- The RED target passes.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_interpretation_result_ui_module_centralizes_safe_interpretation_result_rendering tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_interpretation_result_presentation.py`
- Focused browser/Gmail/interpretation suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_interpretation_review_state.py tests/test_interpretation_result_presentation.py`
- Full validation:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow browser smoke on port `8888` verifies page identity, nonblank content, no framework overlay, console health, screenshot evidence, and normal interpretation review interaction without live Gmail.

## Rollout and Fallback

Publish through a ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending.

Fallback is to keep the branch/worktree intact and report the blocker; do not direct-push to `main`.

## Validation Log

- Confirmed RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_result_presentation.py::test_interpretation_result_presentation_builds_export_and_gmail_cards tests/test_shadow_web_api.py::test_interpretation_result_presentation_module_owns_export_and_gmail_result_state`
  failed because `interpretation_result_presentation.js` did not exist yet.
- Post-implementation targeted tests passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_result_presentation.py::test_interpretation_result_presentation_builds_export_and_gmail_cards tests/test_shadow_web_api.py::test_interpretation_result_presentation_module_owns_export_and_gmail_result_state`
  -> `2 passed`.
- Adjacent/static asset tests passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_interpretation_result_ui_module_centralizes_safe_interpretation_result_rendering tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_interpretation_result_presentation.py`
  -> `3 passed`.
- Focused browser/Gmail/interpretation suite passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_interpretation_review_state.py tests/test_interpretation_result_presentation.py`
  -> `230 passed in 172.64s`.
- Full validation passed:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
  The wrapper reported the known `dart run ...` AOT snapshot issue and direct-Dart fallback success for docs validation and workspace hygiene.
- Shadow smoke launched from this worktree on port `8888` with workspace `interpretation-result-presentation-smoke`.
  Browser plugin connection was attempted first and failed with `No active Codex browser pane available`; local Playwright fallback verified page identity, nonblank content, no framework overlay, clean console, screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\legalpdf_interpretation_result_presentation_smoke.png`, interpretation review interaction, and safe inert rendering for malicious export/Gmail result text.

## Risks and Mitigations

- Risk: subtle text, tone, label, or fallback behavior changes for export/Gmail result cards.
  Mitigation: ESM probes assert current status/title/message/chip/path rules exactly.
- Risk: weakening safe rendering.
  Mitigation: presentation builders are pure data only; DOM writes stay in `interpretation_result_ui.js`; malicious text remains text-only in tests.
- Risk: Browser plugin runtime instability.
  Mitigation: attempt Browser first for local smoke, then use local Playwright fallback only if Browser invocation fails and record the reason.

## Assumptions and Defaults

- No live Gmail testing is in scope.
- The new exports are internal static-browser module interfaces.
- User has authorized PR-first publish and merge for this next modernization step.
