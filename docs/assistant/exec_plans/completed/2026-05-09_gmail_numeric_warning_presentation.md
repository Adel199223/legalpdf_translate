# Gmail Numeric Warning Presentation

## Goal And Non-Goals

Extract Gmail finalization numeric-warning text shaping from the safe DOM renderer into the existing Gmail finalization presentation module. Keep the warning visibility, safe text rendering, DOM IDs, selectors, routes, payloads, Gmail/native-host behavior, and translation numeric-warning contracts unchanged.

This does not touch live Gmail, OAuth, native-host registration, backend APIs, submitted values, or finalization behavior.

## Scope

In scope:
- Add `buildGmailNumericMismatchWarningPresentation(...)` to `gmail_finalize_presentation.js`.
- Update `gmail.js` so `renderGmailFinalizeNumericMismatchWarning(...)` builds presentation state before calling the renderer.
- Update `gmail_finalize_ui.js` so `renderGmailNumericMismatchWarningInto(...)` only writes the already-shaped presentation text safely.
- Update focused ESM/static tests for the builder, renderer contract, and versioned asset graph.
- Run focused validation and shadow Browser smoke.

Out of scope:
- Translation warning renderer changes.
- Numeric mismatch detection rules.
- Gmail finalization routes, payloads, or draft behavior.
- Live Gmail testing.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_numeric_warning_presentation`
- Branch name: `codex/gmail-numeric-warning-presentation`
- Base branch: `main`
- Base SHA: `e2c424de43ea7a6d5029dc4db0fd25a5bec1eea8`
- Target integration branch: `main`
- Runtime mode for browser validation: noncanonical shadow mode only.

## Interfaces And Contracts

Affected browser modules:
- `src/legalpdf_translate/shadow_web/static/gmail_finalize_presentation.js`
- `src/legalpdf_translate/shadow_web/static/gmail_finalize_ui.js`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `tests/test_shadow_web_api.py`

Contracts preserved:
- Existing warning DOM target remains `gmail-batch-finalize-numeric-warning`.
- The renderer still toggles `hidden`, writes `textContent`, and uses `role="note"` for visible warnings.
- Dynamic warning text remains inserted as text, never HTML.
- Gmail/native-host and backend route contracts are untouched.

## Implementation Steps

1. Add failing tests expecting `buildGmailNumericMismatchWarningPresentation(...)`.
2. Update the coordinator contract assertions so `gmail.js` calls the builder and passes presentation into the renderer.
3. Update static asset assertions for the new export.
4. Implement the pure builder in `gmail_finalize_presentation.js`.
5. Slim `gmail_finalize_ui.js` numeric-warning renderer to consume presentation text only.
6. Run targeted, focused, and full validation.
7. Run shadow Browser smoke on port `8888`.
8. Move this ExecPlan to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted red/green tests:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_finalize_ui_module_owns_numeric_warning_renderer tests/test_shadow_web_api.py::test_shadow_web_live_mode_and_gmail_runtime_copy_stay_beginner_safe tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow preview on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-numeric-warning-smoke#gmail-intake`.
- Verify page identity, nonblank content, no framework overlay, console health, and shadow-only Gmail review demo load without touching live Gmail.

## Rollout And Fallback

Publish via ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, merge conflicts appear, or required checks remain unexpectedly pending.

Fallback is reverting this narrow PR; behavior should be unchanged because text shaping only moves modules.

## Risks And Mitigations

- Risk: warning text drift. Mitigation: ESM tests assert custom text, default text, filtered detail lines, hidden state, and malicious text preservation.
- Risk: unsafe rendering regression. Mitigation: renderer continues using `textContent`; tests assert no `innerHTML` writes or created HTML children.
- Risk: accidental route or Gmail contract changes. Mitigation: only static JS and tests/docs are touched.

## Assumptions

- No live Gmail testing is in scope.
- No docs sync is needed for this narrow internal frontend module split.
- The PR should be ready and merged after green checks under the user's standing authorization.

## Completion Notes

- Added `buildGmailNumericMismatchWarningPresentation(...)` to `gmail_finalize_presentation.js`.
- Updated `gmail.js` so Gmail finalization numeric warnings are shaped before reaching the renderer.
- Kept `gmail_finalize_ui.js` as the safe DOM writer, using `textContent` and preserving the existing hidden/visible behavior.
- Targeted tests passed: `3 passed`.
- Focused browser/Gmail suite passed: `194 passed`.
- Full validation passed. The known `dart run` AOT launcher issue appeared for agent-docs and workspace-hygiene checks; direct-Dart fallback succeeded both times.
- Browser shadow smoke on port `8888` verified page identity, nonblank Gmail intake, no framework overlay, clean console, demo attachment load state in the DOM, and no live Gmail/OAuth/native-host flow. Browser screenshot capture timed out; fresh headless visual evidence was saved at `C:\Users\FA507\AppData\Local\Temp\legalpdf_gmail_numeric_warning_smoke.png`.
