# Gmail Stage Presentation

## Goal And Non-Goals

Extract Gmail stage and home CTA copy shaping from `gmail_review_state.js` into a focused pure presentation module. Keep workflow state derivation, review storage, preview state, redo actions, recovered finalization actions, routes, payloads, DOM IDs, Gmail/native-host behavior, and safe rendering unchanged.

This does not touch live Gmail, OAuth, native-host contracts, backend APIs, or submitted values.

## Scope

In scope:
- Add `gmail_stage_presentation.js` with pure builders for stage copy and home CTA state.
- Update `gmail.js` to import stage/home presentation builders from the new module while still deriving stage state from `gmail_review_state.js`.
- Update tests and static asset coverage for the new module.
- Update review-state tests so state logic remains in `gmail_review_state.js` and presentation copy is exercised from the new module.

Out of scope:
- UI renderer rewrites.
- Stage enum behavior changes.
- Route, selector, payload, native-host, or Gmail extension changes.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_stage_presentation`
- Branch name: `codex/gmail-stage-presentation`
- Base branch: `main`
- Base SHA: `89f8eed1826623e7c3447ca75bd3a65c3825571a`
- Target integration branch: `main`
- Runtime mode for browser validation: noncanonical shadow mode only.

## Interfaces And Contracts

Affected browser modules:
- `src/legalpdf_translate/shadow_web/static/gmail_stage_presentation.js`
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `tests/test_shadow_web_api.py`
- `tests/test_gmail_review_state.py`

Contracts preserved:
- `deriveGmailStage(...)` and review-state behavior remain in `gmail_review_state.js`.
- Existing renderer presentation shapes remain unchanged:
  - `{ title, description, stripTitle, stripDescription }`
  - `{ visible, label, action, title, description, tone }`
- Safe text rendering remains renderer-owned; presentation builders do no DOM work.

## Implementation Steps

1. Add failing tests for `gmail_stage_presentation.js` exports and ESM behavior.
2. Update coordinator contract tests so `gmail.js` calls the new builders and no longer imports presentation copy builders from `gmail_review_state.js`.
3. Update static asset route assertions for `/static-build/<asset_version>/gmail_stage_presentation.js`.
4. Implement the new module by moving stage/home CTA shaping into pure builders.
5. Update `gmail.js` imports and call sites.
6. Update `tests/test_gmail_review_state.py` to import stage presentation separately while keeping stage-state assertions against `gmail_review_state.js`.
7. Run targeted, focused, and full validation.
8. Run shadow Browser smoke on port `8888`.
9. Move this ExecPlan to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted red/green tests:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_stage_presentation_module_derives_stage_and_home_cta_state tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_session_cards tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_workspace_strip_card tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_gmail_review_state.py`

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow preview on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-stage-smoke#gmail-intake`.
- Verify page identity, nonblank content, no framework overlay, console health, load demo attachments, and confirm Gmail stage/session/workspace copy still renders through the review flow without touching live Gmail.

## Rollout And Fallback

Publish via ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, merge conflicts appear, or required checks remain unexpectedly pending.

Fallback is reverting this narrow PR; behavior should be unchanged because presentation shaping only moves modules.

## Risks And Mitigations

- Risk: stage copy or CTA tone drift. Mitigation: ESM tests assert current strings and action/tone outputs across stage states.
- Risk: unsafe rendering regression. Mitigation: presentation remains string-only and existing renderers keep safe text writes.
- Risk: mixing stage state and presentation again. Mitigation: tests assert `gmail.js` imports stage copy builders from `gmail_stage_presentation.js` while retaining `deriveGmailStage` from `gmail_review_state.js`.

## Assumptions

- No live Gmail testing is in scope.
- Compatibility exports from `gmail_review_state.js` are not required once local callers and tests import the new module.
- The PR should be ready and merged after green checks under the user's standing authorization.

## Completion Notes

- Added `gmail_stage_presentation.js` with pure stage copy and home CTA builders.
- Kept `deriveGmailStage(...)` and other review/preview/redo state derivation in `gmail_review_state.js`.
- Updated `gmail.js` so stage/home presentation copy comes from the new module while Gmail/native-host contracts, routes, selectors, and renderer shapes remain unchanged.
- Targeted tests passed: `5 passed`.
- Focused browser/Gmail suite passed: `193 passed`.
- Full validation passed. The known `dart run` AOT launcher issue appeared for agent-docs and workspace-hygiene checks; direct-Dart fallback succeeded both times.
- Browser shadow smoke on port `8888` verified page identity, nonblank Gmail intake, no framework overlay, clean console, initial demo action, demo attachment load, review action enablement, review-stage copy, and session/workspace strip text. No live Gmail/OAuth/native-host flow was touched.
- Optional continue-to-prepared-state smoke remained stuck on `Preparing...` with no console errors after selecting the demo attachment; this was recorded as a pre-existing shadow demo/prepare smoke limitation, not part of the presentation-copy extraction contract.
- Browser screenshot capture timed out at the CDP screenshot command; Chrome headless visual evidence was saved at `C:\Users\FA507\AppData\Local\Temp\legalpdf_gmail_stage_smoke.png`.
