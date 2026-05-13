# Power Tools Bootstrap Presentation

## Goal And Non-Goals

Extract Power Tools bootstrap payload presentation shaping from `power-tools.js` into a pure static presentation module while preserving existing safe DOM renderers and browser contracts.

Non-goals:
- No route, backend payload, selector, submitted value, Gmail/native-host, or extension contract changes.
- No visual redesign of the Advanced Tools surface.
- No live Gmail, OAuth, native-host, or real draft testing.

## Scope

In:
- Add `power_tools_presentation.js` with pure builders for Power Tools bootstrap sections.
- Keep `power_tools_ui.js` as the owner of DOM writes.
- Keep `power-tools.js` as coordinator: gather bootstrap payload, call the builder, pass presentation data into existing UI renderers and diagnostics helpers.
- Add direct ESM probe coverage, source-contract assertions, and static asset graph coverage.
- Validate with targeted, focused, full, and shadow browser smoke checks.

Out:
- Changing settings credential/readiness presentation already owned by `settings_presentation.js`.
- Changing form IDs, event listeners, busy states, diagnostics slots, or API routes.
- Changing visible copy except preserving exact current strings.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_power_tools_presentation`
- Branch name: `codex/power-tools-presentation`
- Base branch: `main`
- Base SHA: `446ad12122019cbc724865510ebf456ea5199512`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains stable

## Interfaces, Types, And Contracts Affected

- New internal static-browser module:
  - `src/legalpdf_translate/shadow_web/static/power_tools_presentation.js`
  - Export: `buildPowerToolsBootstrapPresentation(powerTools)`
- Existing renderer inputs stay compatible:
  - glossary form object passed to `renderPowerToolsGlossaryFormInto(...)`
  - builder defaults object passed to `renderPowerToolsBuilderDefaultsInto(...)`
  - calibration defaults object passed to `renderPowerToolsCalibrationDefaultsInto(...)`
  - latest run directories passed to `renderLatestRunDirsInto(...)`
  - diagnostics value/options passed to `setDiagnostics(...)`

## File-By-File Implementation Steps

1. Add failing tests:
   - `tests/test_power_tools_presentation.py`
   - `tests/test_shadow_web_api.py`
2. Confirm RED because the presentation module does not exist and `power-tools.js` still owns bootstrap presentation shaping.
3. Add `power_tools_presentation.js` with pure bootstrap presentation logic.
4. Update `power-tools.js` to import the builder and delegate bootstrap presentation shaping.
5. Update the static asset graph test.
6. Mark this ExecPlan complete and move it to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted RED:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_presentation.py::test_power_tools_presentation_module_builds_bootstrap_state tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_bootstrap_state`

Targeted GREEN:
- New ESM probe passes for null-safe defaults, glossary JSON fields, builder defaults with suggestions, calibration defaults, latest run folder de-duping, ready status with and without run folders, startup trace diagnostics hint, and malicious inert text.
- Source contract confirms the presentation module has no DOM/API side effects and `power-tools.js` delegates bootstrap shaping.
- Static asset graph serves `/static-build/<asset_version>/power_tools_presentation.js` as JavaScript and includes the builder export.

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

Browser smoke:
- Launch from this worktree on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=power-tools-presentation-smoke#power-tools`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, Power Tools visible controls, and normal Power Tools route interaction. Do not touch live Gmail.

## Rollout And Fallback

- Commit: `Extract Power Tools bootstrap presentation`.
- Ready PR: `[codex] Extract Power Tools bootstrap presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove this worktree only after `main` contains the merge.
- Fallback is reverting the narrow PR; existing renderer and coordinator contracts remain intact.

## Risks And Mitigations

- Risk: ready/status copy changes subtly.
  - Mitigation: exact-string ESM probe coverage.
- Risk: latest run folder de-duping changes.
  - Mitigation: tests cover diagnostics and builder source order plus case-insensitive duplicates.
- Risk: presentation module gains coordinator coupling.
  - Mitigation: source-contract test forbids DOM, renderer, fetch, state, and event APIs.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- The new export is an internal static-browser module interface.
- The user has authorized normal PR-first publish and merge flow if validation and CI pass.

## Progress

- [x] Worktree created from clean `main`.
- [x] Baseline Power Tools renderer contract tests passed.
- [x] Tests added and RED confirmed.
- [x] Implementation complete.
- [x] Targeted/focused/full validation complete.
- [x] Browser smoke complete.
- [ ] PR published, merged, and worktree cleaned up.

## Validation Outcomes

- Baseline Power Tools renderer contracts:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_builder_defaults_renderer tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_glossary_form_renderer tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_calibration_defaults_renderer tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_safe_diagnostics_rendering`
  - `4 passed`
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_presentation.py::test_power_tools_presentation_module_builds_bootstrap_state tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_bootstrap_state`
  - Failed because `power_tools_presentation.js` did not exist yet.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_power_tools_presentation.py tests/test_shadow_web_api.py::test_power_tools_presentation_module_owns_bootstrap_state tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_safe_run_directory_rendering tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_builder_defaults_renderer tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_glossary_form_renderer tests/test_shadow_web_api.py::test_power_tools_ui_module_centralizes_calibration_defaults_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `7 passed`
- Focused suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`
  - `255 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. The known Dart launcher issue appeared as `Unable to find AOT snapshot for dartdev`; the wrapper's direct-Dart fallback passed for agent-docs and workspace-hygiene validation.
- Final post-move full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed after moving this ExecPlan to `completed/`. The known Dart launcher issue appeared again; the wrapper's direct-Dart fallback passed for agent-docs and workspace-hygiene validation.
- Browser smoke:
  - Launched shadow app from this worktree on port `8888`.
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=power-tools-presentation-smoke#power-tools`
  - Browser runtime verified page identity, nonblank Power Tools content, required Power Tools controls, no framework overlay, and no console warnings/errors.
  - Browser interaction verified `New Job -> More -> Power Tools` returned to `#power-tools` with Advanced Tools and Troubleshooting content visible.
  - Browser Playwright screenshot path hit the known local `Page.captureScreenshot` timeout; Browser CUA visible screenshot capture succeeded.
  - No live Gmail, OAuth, native-host, or real draft flow was touched.
