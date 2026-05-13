# Power Tools Action Result Presentation

## Goal And Non-Goals

Extract Power Tools action-result status, diagnostics, and result-field shaping from `power-tools.js` into the pure `power_tools_presentation.js` module while preserving existing safe DOM renderers and browser contracts.

Non-goals:
- No route, backend payload, selector, submitted value, Gmail/native-host, or extension contract changes.
- No visual redesign of the Advanced Tools surface.
- No changes to settings credential actions, form collection, parse validation, or click/busy behavior.
- No live Gmail, OAuth, native-host, or real draft testing.

## Scope

In:
- Extend `power_tools_presentation.js` with pure builders for Power Tools action results:
  - glossary save/export
  - glossary-builder run/apply
  - calibration run
  - troubleshooting bundle/run report/startup trace
- Keep `power_tools_ui.js` as the owner of DOM writes.
- Keep `power-tools.js` as coordinator: collect form data, call APIs, call builders, pass status/diagnostics/result fields into existing UI helpers, and refresh bootstrap where already required.
- Add direct ESM probe coverage, source-contract assertions, and static asset graph coverage.
- Validate with targeted, focused, full, and shadow browser smoke checks.

Out:
- Settings-admin save/preflight/Gmail-prereq action presentation.
- Reworking repeated action feedback or busy-button plumbing.
- Changing visible copy except preserving exact current strings.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_power_tools_action_presentation`
- Branch name: `codex/power-tools-action-presentation`
- Base branch: `main`
- Base SHA: `00fd0d06f74a1ca1f99818f6aa305cb5fca36957`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains stable

## Interfaces, Types, And Contracts Affected

- Internal static-browser module extended:
  - `src/legalpdf_translate/shadow_web/static/power_tools_presentation.js`
  - New pure exports:
    - `buildPowerToolsGlossarySavePresentation(payload)`
    - `buildPowerToolsGlossaryExportPresentation(payload)`
    - `buildPowerToolsBuilderRunPresentation(payload)`
    - `buildPowerToolsBuilderApplyPresentation(payload)`
    - `buildPowerToolsCalibrationRunPresentation(payload)`
    - `buildPowerToolsDebugBundlePresentation(payload)`
    - `buildPowerToolsRunReportPresentation(payload)`
    - `buildPowerToolsArmWindowTracePresentation(payload)`
- Existing renderer/helper inputs stay compatible:
  - `setPanelStatus(slot, tone, message)`
  - `setDiagnostics(slot, value, { hint, open })`
  - `renderPowerToolsResultFieldsInto(nodes, result)`

## File-By-File Implementation Steps

1. Add failing tests:
   - `tests/test_power_tools_action_presentation.py`
   - `tests/test_shadow_web_api.py`
2. Confirm RED because the new action-result builders do not exist and `power-tools.js` still owns action-result presentation shaping.
3. Extend `power_tools_presentation.js` with pure action-result builders.
4. Update `power-tools.js` to import and call the builders inside the existing action handlers.
5. Update static asset graph assertions.
6. Mark this ExecPlan complete and move it to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted RED:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_action_presentation.py::test_power_tools_action_presentation_module_builds_action_results tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_action_result_state`

Targeted GREEN:
- New ESM probe passes for each builder, including fallback hints, malicious inert path/text payloads, builder suggestion JSON, calibration diagnostics-run-dir derivation, and null-safe defaults.
- Source contract confirms the presentation module has no DOM/API side effects and `power-tools.js` delegates action-result status/diagnostics/result-field shaping.
- Static asset graph serves `/static-build/<asset_version>/power_tools_presentation.js` as JavaScript and includes the new action builders.

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_action_presentation.py tests/test_power_tools_presentation.py tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

Browser smoke:
- Launch from this worktree on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=power-tools-action-presentation-smoke#power-tools`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, Power Tools visible controls, and normal route interaction. Do not touch live Gmail.

## Rollout And Fallback

- Commit: `Extract Power Tools action result presentation`.
- Ready PR: `[codex] Extract Power Tools action result presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove this worktree only after `main` contains the merge.
- Fallback is reverting the narrow PR; existing renderer and coordinator contracts remain intact.

## Risks And Mitigations

- Risk: action success copy or diagnostics hints change subtly.
  - Mitigation: exact-string ESM probe coverage for every moved string.
- Risk: calibration run directory derivation changes.
  - Mitigation: tests cover Windows and POSIX-like report paths plus missing path fallback.
- Risk: presentation module gains coordinator coupling.
  - Mitigation: source-contract test forbids DOM, renderer, fetch, state, and event APIs.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- The new exports are internal static-browser module interfaces.
- The user has authorized normal PR-first publish and merge flow if validation and CI pass.

## Progress

- [x] Worktree created from clean `main`.
- [x] Baseline Power Tools presentation/static tests passed.
- [x] Tests added and RED confirmed.
- [x] Implementation complete.
- [x] Targeted validation complete.
- [x] Focused/full validation complete.
- [x] Browser smoke complete.
- [ ] PR published, merged, and worktree cleaned up.

## Validation Outcomes

- Baseline Power Tools presentation/static tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_presentation.py tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_bootstrap_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `3 passed`
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_action_presentation.py::test_power_tools_action_presentation_module_builds_action_results tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_action_result_state`
  - Failed because the action-result builders did not exist yet.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_action_presentation.py tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_action_result_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `3 passed`
- Focused browser/static suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_action_presentation.py tests/test_power_tools_presentation.py tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`
  - `258 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. Included `228 passed` for the shadow-web/route/translation suite, `compileall src tests`, Gmail focused checks, agent docs validation, and workspace hygiene validation.
  - The wrapper encountered the known `dart run` AOT launcher issue (`Unable to find AOT snapshot for dartdev`) and direct-Dart fallback succeeded for both agent docs and workspace hygiene.
- Browser smoke:
  - Launched shadow app from this worktree on port `8888` with workspace `power-tools-action-presentation-smoke`.
  - In-app Browser runtime verified title `LegalPDF Translate`, expected local shadow URL, nonblank Advanced Tools DOM, no framework overlay, and no console warnings/errors.
  - In-app Browser DOM control clicked `Refresh tools`; post-click DOM still showed the Advanced Tools surface and no console warnings/errors.
  - The in-app Browser Playwright/CUA screenshot path timed out on `Page.captureScreenshot`; fallback Playwright MCP captured viewport screenshots and repeated DOM/console/interaction checks successfully.
  - No live Gmail, OAuth, native-host, or real draft flow was touched.
