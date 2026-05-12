# Interpretation Review Presentation

## Goal And Non-Goals
- Extract interpretation-review presentation shaping from `interpretation_review_state.js` into a pure browser presentation module.
- Keep the existing interpretation-review state helpers, DOM renderers, routes, selectors, payloads, Gmail/native-host behavior, and safe text rendering unchanged.
- Do not touch live Gmail, OAuth, native-host flows, or real drafts.

## Scope
- In:
  - Add `src/legalpdf_translate/shadow_web/static/interpretation_review_presentation.js`.
  - Move/re-export the review presentation builders used by `app.js`.
  - Update contract and ESM probe tests for the new module ownership.
  - Update the static asset graph test.
- Out:
  - Backend API or route changes.
  - UI selector, DOM ID, submitted value, Gmail/native-host, or extension contract changes.
  - Visual redesign or copy changes beyond preserving the existing strings.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_interpretation_review_presentation`
- Branch name: `codex/interpretation-review-presentation`
- Base branch: `main`
- Base SHA: `b564f72276f624644661093bfc04289cc6455b6e`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains at `C:\Users\FA507\.codex\legalpdf_translate`.

## Interfaces And Contracts Affected
- Internal static-browser module graph gains `interpretation_review_presentation.js`.
- `app.js` imports presentation builders from the new module while continuing to import domain/state helpers from `interpretation_review_state.js`.
- Existing safe renderers in `interpretation_review_ui.js` and `interpretation_result_ui.js` remain the only DOM writers for these surfaces.

## File-By-File Steps
- `tests/test_interpretation_review_presentation.py`: add ESM probe coverage for review presentation, session chip, completion card, drawer layout, malicious text, and null-safe defaults.
- `tests/test_shadow_web_api.py`: add/adjust contract assertions so the new module owns the builders and the static asset route serves it.
- `src/legalpdf_translate/shadow_web/static/interpretation_review_presentation.js`: add pure exports for:
  - `deriveInterpretationReviewPresentation`
  - `buildInterpretationSessionChip`
  - `buildInterpretationCompletionCardPresentation`
  - `deriveInterpretationDrawerLayout`
- `src/legalpdf_translate/shadow_web/static/interpretation_review_state.js`: keep domain/state exports and import/re-export any moved builders needed for compatibility.
- `src/legalpdf_translate/shadow_web/static/app.js`: import moved builders from `interpretation_review_presentation.js`.

## Tests And Acceptance Criteria
- Confirm RED before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_presentation.py::test_interpretation_review_presentation_module_builds_review_surfaces tests/test_shadow_web_api.py::test_interpretation_review_presentation_module_owns_review_surface_state`
- After implementation:
  - targeted new/adjusted tests pass
  - `tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` passes
  - focused browser/Gmail suite passes:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passes.
- Browser smoke from this worktree on port `8888` verifies page identity, nonblank content, no framework overlay, console health, screenshot evidence, interpretation review flow, and no live Gmail/OAuth/native-host touch.

## Rollout And Fallback
- Publish via ready PR `[codex] Extract interpretation review presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove the feature worktree after verifying `main` contains the merge.
- Fallback: revert the PR; behavior should be unchanged because this is a pure module ownership extraction.

## Risks And Mitigations
- Risk: moving helpers could create a circular import with state helpers.
  - Mitigation: move only presentation helpers that depend on small state/domain functions and import those functions from `interpretation_review_state.js`; keep state helpers free of presentation imports unless a compatibility re-export is safe.
- Risk: safe rendering regression.
  - Mitigation: contract tests forbid DOM APIs, renderers, and `innerHTML` inside builders; ESM probes include malicious text as inert data.
- Risk: hidden app wiring changes.
  - Mitigation: preserve all app call sites and renderer payload shapes.

## Assumptions
- No public backend API changes are in scope.
- Existing copy and result shapes are the contract.
- The Browser plugin may still have in-app pane limitations; local Playwright fallback is acceptable for smoke evidence if the Browser pane is unavailable.

## Validation Log
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_presentation.py::test_interpretation_review_presentation_module_builds_review_surfaces tests/test_shadow_web_api.py::test_interpretation_review_presentation_module_owns_review_surface_state`
  - Failed as expected because `interpretation_review_presentation.js` did not exist.
- Targeted after implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_presentation.py::test_interpretation_review_presentation_module_builds_review_surfaces tests/test_shadow_web_api.py::test_interpretation_review_presentation_module_owns_review_surface_state`
  - Result: `2 passed`.
- Adjacent/static:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_presentation.py tests/test_interpretation_review_state.py tests/test_shadow_web_api.py::test_interpretation_review_presentation_module_owns_review_surface_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `6 passed`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `227 passed`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed. Known Dart AOT launcher issue occurred; direct-Dart fallback succeeded for agent docs and workspace hygiene validation.
- Browser smoke:
  - Launched `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace interpretation-review-presentation-smoke --port 8888`.
  - Verified `http://127.0.0.1:8888/?mode=shadow&workspace=interpretation-review-presentation-smoke#new-job`.
  - Confirmed page identity, nonblank content, no framework overlay, zero console warnings/errors, interpretation tab and drawer interaction, disclosure summary update, screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\legalpdf_interpretation_review_presentation_smoke.png`, and no live Gmail/OAuth/native-host touch.
  - Stopped the shadow server after smoke.
