# Translation Numeric Warning Presentation

## Goal And Non-Goals

Extract translation numeric-mismatch warning derivation from `translation.js` into a pure browser presentation module while keeping the existing public wrapper, renderers, selectors, Gmail finalization consumption, routes, payloads, and safe rendering unchanged.

Non-goals: no route changes, no Gmail/native-host changes, no selector changes, no warning copy changes, no renderer rewrites, no live Gmail testing.

## Scope

In scope:
- Create `src/legalpdf_translate/shadow_web/static/translation_numeric_warning_presentation.js`.
- Move pure numeric-warning parsing and shaping into exported helpers.
- Keep `translation.js` as the coordinator for cached warning lookup, job state, DOM rendering, API calls, and notification side effects.
- Add ESM/source contract tests and static asset coverage.

Out of scope:
- Changing warning UI markup or selectors.
- Changing Gmail finalization numeric warning presentation.
- Changing translation job/run-report API behavior.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_translation_numeric_warning_presentation`
- Branch name: `codex/translation-numeric-warning-presentation`
- Base branch: `main`
- Base SHA: `3b08bcbd19f51866242e8674ffa44a6e009770f3`
- Target integration branch: `main`
- Build status: noncanonical feature worktree for shadow-mode validation only.

## Interfaces And Contracts

New internal static-browser module exports:
- `NUMERIC_MISMATCH_WARNING_MESSAGE`
- `blankTranslationNumericMismatchWarning(...)`
- `deriveTranslationNumericMismatchWarning(...)`

Existing public coordinator export remains:
- `deriveNumericMismatchWarning(job, extra)`

The warning shape must remain exactly:
`{ visible, checked, message, lines, pages }`.

Preserve:
- `translation-numeric-warning`
- `translation-completion-numeric-warning`
- `translation-save-numeric-warning`
- `translation-gmail-step-numeric-warning`
- `gmail-batch-finalize-numeric-warning`

## Implementation Steps

1. Add failing tests in `tests/test_shadow_web_api.py`.
2. Confirm the new targeted test fails before implementation.
3. Create `translation_numeric_warning_presentation.js` with pure derivation helpers.
4. Update `translation.js` to import helpers, keep cache lookup in the wrapper, and preserve all existing renderer calls.
5. Update static asset graph coverage.
6. Run targeted, focused, full validation, Browser smoke, and publish through PR.

## Tests And Acceptance Criteria

Targeted:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_translation_numeric_warning_presentation_module_derives_warning_state`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Focused:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`

Full:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow app from this worktree on port `8888`.
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=translation-numeric-warning-smoke#new-job`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, and a normal navigation/control interaction. Do not touch live Gmail.

Acceptance:
- Pure module has no DOM, renderer, fetch, diagnostics, or app-state dependencies.
- Existing `deriveNumericMismatchWarning(...)` keeps its public behavior and cached-warning fallback.
- Structured rows, preview markdown rows, malicious text, recursive skip rules, depth guard, and null defaults are covered.
- Local validation, Browser smoke, and GitHub CI pass before merge.

## Rollout And Fallback

Roll out through a ready PR. If CI, mergeability, or auth blocks publication, stop at the highest clean point and report the blocker. If Browser screenshot capture hits the known in-app limitation, use the local loopback screenshot fallback and record it.

## Risks And Mitigations

- Risk: cached-warning fallback changes. Mitigation: keep cache lookup in `translation.js` wrapper and test it through existing browser-state coverage.
- Risk: Gmail finalization warning shape changes. Mitigation: preserve `{ visible, checked, message, lines, pages }` and run Gmail-focused tests.
- Risk: preview text parsing loses support. Mitigation: ESM probe covers markdown preview extraction.

## Assumptions

- This is an internal static-browser module extraction only.
- Shadow-mode smoke is sufficient.
- Known Dart AOT launcher issue is recorded only if direct-Dart fallback succeeds.

## Completion Notes

Implemented:
- Created `translation_numeric_warning_presentation.js`.
- Moved numeric mismatch warning parsing/normalization into pure helpers.
- Kept `translation.js` as the cache-aware wrapper and renderer coordinator.
- Preserved existing public `deriveNumericMismatchWarning(...)` and all numeric warning selectors.
- Added ESM/source contract coverage and static asset coverage.

Validation:
- Targeted test failed red on the missing pure module, then passed after implementation.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_translation_numeric_warning_presentation_module_derives_warning_state` passed.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_translation_browser_state.py::test_translation_browser_idle_and_prepared_action_states` passed.
- Focused suite passed: `259 passed`.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passed. The known `Unable to find AOT snapshot for dartdev` issue appeared for docs and workspace hygiene validators; both direct-Dart fallbacks succeeded.

Browser smoke:
- Launched shadow app from this feature worktree on port `8888`.
- Verified `http://127.0.0.1:8888/?mode=shadow&workspace=translation-numeric-warning-smoke#new-job`.
- Browser verified page identity (`LegalPDF Translate`), nonblank New Job content, no framework overlay, clean console, DOM-based navigation from New Job to Recent Work and back, and screenshot evidence.
- In-app Browser screenshot succeeded for this smoke.
- No live Gmail, OAuth, native-host, or real draft flow was touched.
