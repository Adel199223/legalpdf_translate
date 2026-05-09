# Gmail Action Presentation

## Goal And Non-Goals

Extract the remaining Gmail action state shaping from `gmail.js` into the existing pure `gmail_action_presentation.js` module. Keep the safe DOM renderer, selectors, dataset names, routes, payloads, Gmail/native-host behavior, and visible action semantics unchanged.

This does not touch live Gmail, OAuth, backend APIs, native-host contracts, or submitted form values.

## Scope

In scope:
- Add pure builders for demo-review and return-to-source action presentations.
- Update `gmail.js` so action update functions gather coordinator state, call builders, and pass presentation objects into the existing renderer.
- Extend browser ESM contract coverage and static asset route coverage.

Out of scope:
- Renderer rewrites beyond accepting the same presentation shape.
- Route, payload, selector, event listener, or native-host behavior changes.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_action_presentation`
- Branch name: `codex/gmail-action-presentation`
- Base branch: `main`
- Base SHA: `678079f67755f251b75d93059e2db01c5c2ff20e`
- Target integration branch: `main`
- Runtime mode for browser validation: noncanonical shadow mode only.

## Interfaces And Contracts

Affected browser modules:
- `src/legalpdf_translate/shadow_web/static/gmail_action_presentation.js`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `tests/test_shadow_web_api.py`

Contracts preserved:
- Public browser route IDs and static asset routes.
- Gmail/native-host/extension payloads and event listeners.
- Existing renderer shape for `renderGmailDemoReviewActionInto(...)` and `renderGmailReturnToSourceActionInto(...)`.
- Safe text rendering with no `innerHTML` writes.

## Implementation Steps

1. Add failing tests for `buildGmailDemoReviewActionPresentation(...)` and `buildGmailReturnToSourceActionPresentation(...)`.
2. Update ownership tests so `gmail.js` calls presentation builders before the renderers.
3. Add static asset route assertions for the new exports.
4. Implement the builders in `gmail_action_presentation.js`.
5. Import and use the builders in `gmail.js`.
6. Run targeted, focused, and full validation.
7. Run a shadow browser smoke on port `8888`.
8. Move this ExecPlan to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted red/green tests:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_action_ui_module_owns_demo_review_action_renderer tests/test_shadow_web_api.py::test_gmail_action_ui_module_owns_return_to_source_action_renderer tests/test_shadow_web_api.py::test_gmail_action_presentation_module_derives_prepare_action_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow preview on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-action-smoke#gmail-intake`.
- Verify page identity, nonblank content, no framework overlay, console health, and action behavior in the shadow Gmail review demo without touching live Gmail.

## Rollout And Fallback

Publish via ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, merge conflicts appear, or required checks remain unexpectedly pending.

Fallback is reverting this narrow PR; behavior should be unchanged because only presentation shaping moves.

## Risks And Mitigations

- Risk: Changing action visibility/disabled semantics. Mitigation: ESM probes cover enabled, disabled, hidden, missing source URL, and malicious source text.
- Risk: Unsafe rendering regression. Mitigation: renderer contract tests continue to assert no `innerHTML` writes.
- Risk: Shadow-only browser smoke drift. Mitigation: use isolated workspace and avoid live Gmail/OAuth/native-host flows.

## Assumptions

- No live Gmail testing is in scope.
- The existing action renderer shapes are the target compatibility contract.
- The PR should be ready and merged after green checks under the user's standing authorization.

## Completion Notes

- Added `buildGmailDemoReviewActionPresentation(...)` and `buildGmailReturnToSourceActionPresentation(...)` to `gmail_action_presentation.js`.
- Updated `gmail.js` so demo-review and return-to-source action updates gather coordinator state, call builders, and pass presentation objects to the existing safe renderer.
- Targeted tests passed: `4 passed`.
- Focused browser/Gmail suite passed: `192 passed`.
- Full validation passed. The known `dart run` AOT launcher issue appeared for agent-docs and workspace-hygiene checks; direct-Dart fallback succeeded both times.
- Shadow browser smoke passed on port `8888` with workspace `gmail-action-smoke`. Browser verified page identity, nonblank Gmail intake content, no framework overlay, clean console, initial demo action visible, demo action hidden after shadow demo load, review action enabled, and return-to-source hidden without a source URL. No live Gmail/OAuth/native-host flow was touched.
- Browser screenshot capture timed out at the CDP screenshot command; Chrome headless visual evidence was saved at `C:\Users\FA507\AppData\Local\Temp\legalpdf_gmail_action_smoke.png`.
