# Recent Work Presentation

## Goal And Non-Goals
- Extract saved-work/recent-run presentation shaping from `translation.js` into a pure static browser module.
- Keep recent-work safe DOM rendering, route IDs, backend payloads, selectors, submitted values, Gmail/native-host behavior, and translation coordinator behavior unchanged.
- Do not redesign Recent Work, Gmail, translation, or interpretation flows.

## Scope
- In:
  - Add `src/legalpdf_translate/shadow_web/static/recent_work_presentation.js`.
  - Move `deriveRecentWorkPresentation(...)` and `formatRecentRunTitle(...)` plus private label helpers out of `translation.js`.
  - Update `app.js` and `recent_work_ui.js` to import from the new presentation module.
  - Keep compatibility re-exports from `translation.js` if existing browser tests or callers still import them there.
  - Add ESM, source-contract, and static-asset coverage.
- Out:
  - Backend API changes.
  - DOM renderer changes beyond import source.
  - Gmail/live/native-host testing.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_recent_work_presentation`
- Branch name: `codex/recent-work-presentation`
- Base branch: `main`
- Base SHA: `e7460371bfe608d59ef3e07e9d58fbfe344f5f30`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains at `C:\Users\FA507\.codex\legalpdf_translate`.

## Interfaces And Contracts Affected
- Internal static-browser module graph gains `recent_work_presentation.js`.
- `deriveRecentWorkPresentation` and `formatRecentRunTitle` remain internal browser helpers; no public backend API changes.
- Recent Work UI continues to render through `recent_work_ui.js` and safe rendering helpers.

## File-By-File Steps
- `tests/test_recent_work_presentation.py`: add ESM probes for null/default copy, interpretation records, translation records, translation runs, unknown status/kind, path fallback, and malicious text as inert data.
- `tests/test_shadow_web_api.py`: assert the new module owns saved-work copy, forbidden DOM APIs are absent, app/UI import the new module, and the static asset route serves it.
- `tests/test_translation_browser_state.py`: point recent-work presentation probes at the new module while preserving existing expected copy.
- `src/legalpdf_translate/shadow_web/static/recent_work_presentation.js`: move pure helpers and exports from `translation.js`.
- `src/legalpdf_translate/shadow_web/static/translation.js`: remove inline helpers and re-export the moved exports for compatibility.
- `src/legalpdf_translate/shadow_web/static/app.js`: import `deriveRecentWorkPresentation` from the new module.
- `src/legalpdf_translate/shadow_web/static/recent_work_ui.js`: import `deriveRecentWorkPresentation` from the new module.

## Tests And Acceptance Criteria
- Confirm RED before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_recent_work_presentation.py::test_recent_work_presentation_module_builds_saved_work_copy tests/test_shadow_web_api.py::test_recent_work_presentation_module_owns_saved_work_copy`
- After implementation:
  - Targeted recent-work tests pass.
  - Static asset graph test passes.
  - Focused browser/Gmail suite passes:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passes.
- Browser smoke from this worktree on port `8888` verifies `#recent-jobs` page identity, nonblank content, no framework overlay, console health, screenshot evidence, and safe Recent Work rendering. No live Gmail/OAuth/native-host touch.

## Rollout And Fallback
- Publish via ready PR `[codex] Extract recent work presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove the feature worktree after verifying `main` contains the merge.
- Fallback is to revert the narrow helper import/re-export changes and leave the inline translation coordinator helper unchanged.

## Risks And Mitigations
- Risk: import cycle through `recent_work_ui.js` and `translation.js`.
  - Mitigation: point app/UI imports directly at the pure presentation module and keep any `translation.js` compatibility as a re-export only.
- Risk: safe rendering regression for saved-work text.
  - Mitigation: keep `recent_work_ui.js` renderer behavior unchanged and retain safe-rendering probes.
- Risk: stale tests still import from `translation.js`.
  - Mitigation: preserve re-exports while contract tests require source ownership in `recent_work_presentation.js`.

## Assumptions
- No live Gmail testing is in scope.
- Existing saved-work strings and presentation object keys are the contract.
- Browser plugin may require the known local Playwright fallback if the in-app pane runtime blocks localhost automation.

## Validation Log
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_recent_work_presentation.py::test_recent_work_presentation_module_builds_saved_work_copy tests/test_shadow_web_api.py::test_recent_work_presentation_module_owns_saved_work_copy`
  - Failed on missing `recent_work_presentation.js`, as intended.
- Targeted checks passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_recent_work_presentation.py tests/test_translation_browser_state.py::test_recent_work_presentation_helper_uses_beginner_saved_work_copy tests/test_shadow_web_api.py::test_recent_work_presentation_module_owns_saved_work_copy tests/test_shadow_web_api.py::test_shadow_web_tiny_presentation_cleanup_copy_is_distinct tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `5 passed`.
- Focused browser/Gmail suite passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `228 passed`.
- Full validation passed:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Wrapper tests passed (`223 passed`, compileall passed, Gmail review/intake focused checks passed).
  - Known `dartdev` AOT snapshot launcher issue occurred; direct-Dart fallback succeeded for agent-docs and workspace-hygiene validation.
- Browser smoke passed:
  - Launched shadow app from this worktree on port `8888`.
  - Browser URL: `http://127.0.0.1:8888/?mode=shadow&workspace=recent-work-presentation-smoke#recent-jobs`.
  - Verified page identity, nonblank Recent Work content, no framework overlay, zero console warnings/errors, Recent Work empty-state copy, accordion interaction, and full-page screenshot evidence (`recent-work-presentation-smoke.png` from the Browser/Playwright tool).
  - No live Gmail, OAuth, native-host, or real draft flow was touched.
