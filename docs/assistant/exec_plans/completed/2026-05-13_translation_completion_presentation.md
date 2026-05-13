# Translation Completion Presentation

## Goal And Non-Goals
- Extract the Translation Finish/Completion drawer presentation shaping from `translation.js` into a pure static browser module.
- Keep translation coordinator behavior, safe DOM rendering, Gmail/native-host hooks, route IDs, DOM IDs, payload shapes, selectors, and submitted values unchanged.
- Do not redesign the finish drawer, translation workflow, Gmail handoff, or Arabic review behavior.

## Scope
- In:
  - Add `src/legalpdf_translate/shadow_web/static/translation_completion_presentation.js`.
  - Move `deriveTranslationCompletionPresentation(...)` plus its pure Arabic-review normalization and save-seed availability helpers out of `translation.js`.
  - Update `translation.js` to import the moved helpers for coordinator use and re-export the public compatibility helper.
  - Update `app.js` to import `deriveTranslationCompletionPresentation` directly from the new pure module before passing the Gmail hook.
  - Add ESM, source-contract, compatibility, and static-asset coverage.
- Out:
  - Backend API changes.
  - Renderer rewrites.
  - Live Gmail, OAuth, native-host, or real draft testing.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_translation_completion_presentation`
- Branch name: `codex/translation-completion-presentation`
- Base branch: `main`
- Base SHA: `9eb28d728a00de77aef4c3ecfc71ac210ac68e04`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains at `C:\Users\FA507\.codex\legalpdf_translate`.

## Interfaces And Contracts Affected
- Internal static-browser module graph gains `translation_completion_presentation.js`.
- `deriveTranslationCompletionPresentation` remains available to existing `translation.js` importers through a compatibility re-export.
- Existing completion presentation object keys and copy are preserved exactly.
- Existing Arabic review normalization semantics are preserved for translation coordinator use.

## File-By-File Steps
- `tests/test_translation_completion_presentation.py`: add direct ESM probes for idle, analysis complete, translation complete with seed, loaded row, rebuild complete, Arabic review required/resolved/missing status, Gmail current attachment, Gmail finalization ready, malicious inert text, and null-safe defaults.
- `tests/test_shadow_web_api.py`: assert the new module owns completion drawer copy, forbidden DOM/side-effect APIs are absent, `translation.js` imports/re-exports the helper instead of defining it inline, and the static route serves the new module.
- `tests/test_translation_browser_state.py`: point the completion presentation probe at the new module while preserving compatibility checks through `translation.js`.
- `src/legalpdf_translate/shadow_web/static/translation_completion_presentation.js`: add pure helpers and exported builder.
- `src/legalpdf_translate/shadow_web/static/translation.js`: remove inline builder/helper definitions, import the moved helpers, and keep compatibility re-export.
- `src/legalpdf_translate/shadow_web/static/app.js`: import the completion builder from the new module.

## Tests And Acceptance Criteria
- Confirm RED before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_completion_presentation.py::test_translation_completion_presentation_module_builds_finish_drawer_state tests/test_shadow_web_api.py::test_translation_completion_presentation_module_owns_finish_drawer_copy`
- After implementation:
  - Targeted completion-presentation tests pass.
  - Static asset graph test passes.
  - Focused browser/Gmail/translation suite passes:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passes.
- Browser smoke from this worktree on port `8888` verifies `#new-job` page identity, nonblank content, no framework overlay, console health, screenshot evidence, and the finish drawer/Recent Work compatibility path in shadow mode. No live Gmail/OAuth/native-host touch.

## Rollout And Fallback
- Publish via ready PR `[codex] Extract translation completion presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove the feature worktree after verifying `main` contains the merge.
- Fallback is to revert the narrow import/re-export changes and leave the inline `translation.js` helper unchanged.

## Risks And Mitigations
- Risk: Gmail hook consumers still import through `translation.js`.
  - Mitigation: preserve the compatibility re-export and add direct-module coverage.
- Risk: Arabic review normalization is used by coordinator flows outside presentation.
  - Mitigation: export/import the pure normalization helper from the new module instead of duplicating behavior.
- Risk: completion drawer copy drift.
  - Mitigation: direct ESM probes assert exact existing strings and object keys.

## Assumptions
- No live Gmail testing is in scope.
- Existing finish-drawer strings and presentation object keys are the contract.
- Browser runtime may require the known local Playwright fallback if the in-app pane blocks localhost automation.

## Validation Log
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_completion_presentation.py::test_translation_completion_presentation_module_builds_finish_drawer_state tests/test_shadow_web_api.py::test_translation_completion_presentation_module_owns_finish_drawer_copy`
  - Failed on missing `translation_completion_presentation.js`, as intended.
- Targeted checks passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_completion_presentation.py tests/test_translation_browser_state.py::test_translation_completion_presentation_helper_uses_beginner_finish_copy tests/test_shadow_web_api.py::test_translation_completion_presentation_module_owns_finish_drawer_copy tests/test_shadow_web_api.py::test_translation_ui_module_centralizes_completion_surface_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `5 passed`.
- Focused browser/Gmail/translation suite passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `229 passed`.
- Full validation passed:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Wrapper tests passed (`224 passed`, compileall passed, Gmail review/intake focused checks passed).
  - Known `dartdev` AOT snapshot launcher issue occurred; direct-Dart fallback succeeded for agent-docs and workspace-hygiene validation.
- Browser smoke passed with fallback:
  - Browser plugin path attempted first, but the runtime reported `No active Codex browser pane available`.
  - Used Playwright fallback for local shadow smoke on `http://127.0.0.1:8888/?mode=shadow&workspace=translation-completion-presentation-smoke#new-job`.
  - Verified page identity, nonblank New Job content, no framework overlay, zero console warnings/errors, finish-drawer idle copy, task-tab interaction, and full-page screenshot evidence (`translation-completion-presentation-smoke.png` from the Playwright tool).
  - No live Gmail, OAuth, native-host, or real draft flow was touched.
