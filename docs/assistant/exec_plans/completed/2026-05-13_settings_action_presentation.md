# Settings Action Presentation

## Goal And Non-Goals

Extract the remaining Settings action outcome presentation from the Power Tools coordinator into pure settings presentation builders, while preserving existing routes, payloads, IDs, safe rendering, and side effects.

Non-goals:
- No backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes.
- No visual redesign of the Settings or Advanced Tools surfaces.
- No changes to credential key save/clear/test action feedback behavior already centralized through `buildSettingsActionFeedback`.
- No live Gmail, OAuth, native-host, or real draft testing.

## Scope

In:
- Extend `settings_presentation.js` with pure builders for:
  - settings save success
  - provider/host preflight refresh
  - Gmail draft prerequisite check
- Update `power-tools.js` so the three handlers gather coordinator state, call the builders, and pass status/diagnostics to existing UI helpers.
- Add ESM probe coverage, source-contract assertions, and static asset graph coverage.
- Validate with targeted, focused, full, and shadow browser smoke checks.

Out:
- Moving repeated credential action feedback or failure feedback again.
- Changing settings form collection, provider-state rendering, busy-button wiring, or refresh/bootstrap behavior.
- Touching Gmail intake/finalization flows.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_settings_action_presentation`
- Branch name: `codex/settings-action-presentation`
- Base branch: `main`
- Base SHA: `8bdc75881dcce1eebd3acfea2c36456ab42e1913`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains stable

## Interfaces, Types, And Contracts Affected

- Internal static-browser module extended:
  - `src/legalpdf_translate/shadow_web/static/settings_presentation.js`
  - New pure exports:
    - `buildSettingsSaveActionPresentation(payload)`
    - `buildSettingsPreflightActionPresentation(payload)`
    - `buildSettingsGmailPrereqsActionPresentation(payload)`
- Existing renderer/helper inputs stay compatible:
  - `setPanelStatus(slot, tone, message)`
  - `setDiagnostics(slot, value, { hint, open })`
  - `renderProviderState(providerState, { preserveStatus })`

## File-By-File Implementation Steps

1. Add failing tests:
   - `tests/test_settings_browser_state.py`
   - `tests/test_shadow_web_api.py`
2. Confirm RED because the new settings action builders do not exist and `power-tools.js` still owns the three inline outcomes.
3. Extend `settings_presentation.js` with pure action presentation builders.
4. Update `power-tools.js` to import and call those builders inside `handleSettingsSave`, `handleSettingsPreflight`, and `handleGmailPrereqs`.
5. Update static asset graph assertions.
6. Mark this ExecPlan complete and move it to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted RED:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py::test_settings_presentation_builds_settings_action_outcomes tests/test_shadow_web_api.py::test_settings_presentation_module_owns_settings_action_outcomes`

Targeted GREEN:
- ESM probe passes for settings save, preflight ready/degraded, Gmail prereq ready/blocked, malicious text payloads, and null-safe defaults.
- Source contract confirms `settings_presentation.js` has no DOM/API side effects and `power-tools.js` delegates the three action outcomes.
- Static asset graph serves `/static-build/<asset_version>/settings_presentation.js` as JavaScript and includes the new exports.

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py tests/test_power_tools_presentation.py tests/test_power_tools_action_presentation.py tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_action_feedback_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

Browser smoke:
- Launch from this worktree on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=settings-action-presentation-smoke#power-tools`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, Advanced Tools controls, Settings preflight or refresh interaction, and no live Gmail/OAuth/native-host flow.

## Rollout And Fallback

- Commit: `Extract Settings action presentation`.
- Ready PR: `[codex] Extract Settings action presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove this worktree only after `main` contains the merge.
- Fallback is reverting the narrow PR; existing coordinator and renderer contracts remain intact.

## Risks And Mitigations

- Risk: settings success/preflight/Gmail-prereq copy or diagnostics open state changes subtly.
  - Mitigation: exact-string ESM probe coverage for every moved string and open/tone value.
- Risk: preflight provider-state rendering changes.
  - Mitigation: builder returns the same provider state that the coordinator already rendered.
- Risk: presentation module gains coordinator coupling.
  - Mitigation: source-contract test forbids DOM, renderer, fetch, state, and event APIs.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- The new exports are internal static-browser module interfaces.
- The user has authorized normal PR-first publish and merge flow if validation and CI pass.

## Progress

- [x] Worktree created from clean `main`.
- [x] Baseline settings/static tests passed.
- [x] Tests added and RED confirmed.
- [x] Implementation complete.
- [x] Targeted validation complete.
- [x] Focused/full validation complete.
- [x] Browser smoke complete.
- [ ] PR published, merged, and worktree cleaned up.

## Validation Outcomes

- Baseline settings/static tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `4 passed`
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py::test_settings_presentation_builds_settings_action_outcomes tests/test_shadow_web_api.py::test_settings_presentation_module_owns_settings_action_outcomes`
  - Failed because `buildSettingsSaveActionPresentation`, `buildSettingsPreflightActionPresentation`, and `buildSettingsGmailPrereqsActionPresentation` did not exist yet.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py::test_settings_presentation_builds_settings_action_outcomes tests/test_shadow_web_api.py::test_settings_presentation_module_owns_settings_action_outcomes tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `3 passed`
- Focused browser/static suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py tests/test_power_tools_presentation.py tests/test_power_tools_action_presentation.py tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_action_feedback_browser_state.py`
  - `259 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. Included `229 passed` for the shadow-web/route/translation suite, `compileall src tests`, Gmail focused checks, agent docs validation, and workspace hygiene validation.
  - The wrapper encountered the known `dart run` AOT launcher issue (`Unable to find AOT snapshot for dartdev`) and direct-Dart fallback succeeded for both agent docs and workspace hygiene.
- Browser smoke:
  - Launched shadow app from this worktree on port `8888` with workspace `settings-action-presentation-smoke`.
  - In-app Browser runtime verified title `LegalPDF Translate`, expected local shadow URL, nonblank Advanced Tools DOM, no framework overlay, and no console warnings/errors.
  - In-app Browser DOM control clicked `Refresh tools`; post-click DOM showed the ready Advanced Tools surface and no console warnings/errors.
  - The in-app Browser screenshot path timed out on `Page.captureScreenshot`; fallback Playwright MCP captured viewport screenshot evidence and repeated page/console checks successfully.
  - No live Gmail, OAuth, native-host, or real draft flow was touched.
