# Gmail Context Presentation

## Goal And Non-Goals

Extract Gmail context-default and simulator-default state shaping from `gmail_context_ui.js` into a focused pure presentation module. Keep the existing safe DOM renderer, field preservation behavior, routes, payloads, DOM IDs, selectors, Gmail/native-host behavior, and browser mode contracts unchanged.

This does not touch live Gmail, OAuth, native-host contracts, backend APIs, submitted values, or translation/finalization behavior.

## Scope

In scope:
- Add `gmail_context_presentation.js` with pure builders for bootstrap context defaults and simulator defaults.
- Update `gmail.js` so it gathers coordinator state, calls the builders, and passes presentation objects into the existing renderers.
- Update `gmail_context_ui.js` so it only applies safe field writes from presentation objects while preserving blank-only bootstrap fill and simulator overwrite behavior.
- Update static asset and ESM contract tests.
- Run focused validation and shadow Browser smoke.

Out of scope:
- Route, selector, payload, or Gmail extension changes.
- Live Gmail, OAuth, native-host, or draft-send testing.
- UI layout or copy changes.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_context_presentation`
- Branch name: `codex/gmail-context-presentation`
- Base branch: `main`
- Base SHA: `4a5873a144cf62af98fca0f83c3fcc1f783ade81`
- Target integration branch: `main`
- Runtime mode for browser validation: noncanonical shadow mode only.

## Interfaces And Contracts

Affected browser modules:
- `src/legalpdf_translate/shadow_web/static/gmail_context_presentation.js`
- `src/legalpdf_translate/shadow_web/static/gmail_context_ui.js`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `tests/test_shadow_web_api.py`

Contracts preserved:
- Renderer shape stays field-oriented:
  - `{ messageId, threadId, subject, accountEmail, outputDir, targetLang }`
  - `{ messageId, threadId, subject, accountEmail }`
- Bootstrap defaults continue to fill only blank fields.
- Simulator defaults continue to overwrite message/thread/subject and only replace account email when a truthy account email is present.
- Safe rendering remains renderer-owned; presentation builders do no DOM work.

## Implementation Steps

1. Add failing ESM tests for the new context presentation builders.
2. Update the context UI ownership test so `gmail.js` is expected to call presentation builders before renderers.
3. Update static asset route assertions for `/static-build/<asset_version>/gmail_context_presentation.js`.
4. Implement the pure presentation module.
5. Update `gmail.js` call sites.
6. Slim `gmail_context_ui.js` to consume presentation objects only.
7. Run targeted, focused, and full validation.
8. Run shadow Browser smoke on port `8888`.
9. Move this ExecPlan to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted red/green tests:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_context_presentation_module_builds_context_default_state tests/test_shadow_web_api.py::test_gmail_context_ui_module_owns_context_default_renderers tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow preview on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-context-smoke#gmail-intake`.
- Verify page identity, nonblank content, no framework overlay, console health, context/simulator defaults, and shadow demo load without touching live Gmail.

## Rollout And Fallback

Publish via ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, merge conflicts appear, or required checks remain unexpectedly pending.

Fallback is reverting this narrow PR; behavior should be unchanged because presentation shaping only moves modules.

## Risks And Mitigations

- Risk: default-field semantics drift. Mitigation: ESM tests assert blank-only bootstrap fill, simulator overwrite behavior, null-safe defaults, and malicious text preservation.
- Risk: unsafe rendering regression. Mitigation: presentation remains object/string-only and UI tests assert no `innerHTML` writes.
- Risk: accidental Gmail contract change. Mitigation: no route, payload, selector, DOM ID, Gmail/native-host, or backend files are touched.

## Assumptions

- No live Gmail testing is in scope.
- No docs sync is needed for this narrow internal frontend module split.
- The PR should be ready and merged after green checks under the user's standing authorization.

## Completion Notes

- Added `gmail_context_presentation.js` with pure builders for bootstrap context defaults and simulator defaults.
- Updated `gmail.js` so coordinator state is shaped by the new builders before reaching the existing context renderers.
- Kept `gmail_context_ui.js` as the safe field writer while preserving blank-only bootstrap fill and simulator account-email behavior.
- Targeted tests passed: `3 passed`.
- Focused browser/Gmail suite passed: `194 passed`.
- Full validation passed. The known `dart run` AOT launcher issue appeared for agent-docs and workspace-hygiene checks; direct-Dart fallback succeeded both times.
- Browser shadow smoke on port `8888` verified page identity, nonblank Gmail intake, no framework overlay, clean console, demo attachment load state in the DOM, and no live Gmail/OAuth/native-host flow. Browser post-demo screenshot capture timed out; fresh headless visual evidence was saved at `C:\Users\FA507\AppData\Local\Temp\legalpdf_gmail_context_smoke.png`.
