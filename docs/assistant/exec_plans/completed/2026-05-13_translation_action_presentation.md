# Translation Primary Action Presentation

## Goal And Non-Goals

Extract translation primary action helper/button state shaping from `translation.js` into a pure static presentation module while preserving the existing safe DOM renderer and browser contracts.

Non-goals:
- No route, backend payload, selector, submitted value, Gmail/native-host, or extension contract changes.
- No visual redesign of the New Job action controls.
- No live Gmail, OAuth, native-host, or real draft testing.

## Scope

In:
- Add `translation_action_presentation.js` with a pure `deriveTranslationActionState(...)` export.
- Keep `translation_ui.js` as the only owner of DOM writes for primary action controls.
- Keep `translation.js` as coordinator: gather current job/source/current job id, call the presentation builder, pass results into the existing renderer.
- Add direct ESM probe coverage, source-contract assertions, and static asset graph coverage.
- Validate with targeted, focused, full, and shadow browser smoke checks.

Out:
- Changing source-state derivation.
- Changing button IDs, event listeners, busy states, or action routes.
- Changing visible copy except preserving exact current strings.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_translation_action_presentation`
- Branch name: `codex/translation-action-presentation`
- Base branch: `main`
- Base SHA: `9116fd262305c7aa3a5b951a5daf97c70652a5b1`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains stable

## Interfaces, Types, And Contracts Affected

- New internal static-browser module:
  - `src/legalpdf_translate/shadow_web/static/translation_action_presentation.js`
  - Export: `deriveTranslationActionState(job, options)`
- Existing `translation.js` export `deriveTranslationActionState(...)` remains available as a coordinator wrapper.
- Existing renderer shape remains:
  - `{ sourceState, helperText, startEnabled, analyzeEnabled, cancelEnabled, resumeEnabled, rebuildEnabled }`

## File-By-File Implementation Steps

1. Add failing tests:
   - `tests/test_translation_action_presentation.py`
   - `tests/test_shadow_web_api.py`
2. Confirm RED because the presentation module does not exist and `translation.js` still owns action state shaping.
3. Add `translation_action_presentation.js` with pure action-state logic.
4. Update `translation.js` to import the builder and delegate from its existing exported wrapper.
5. Update the static asset graph test.
6. Mark this ExecPlan complete and move it to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted RED:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_action_presentation.py::test_translation_action_presentation_module_builds_primary_action_state tests/test_shadow_web_api.py::test_translation_action_presentation_module_owns_primary_action_state`

Targeted GREEN:
- New ESM probe passes for idle, uploading, prepared Gmail, prepared local, manual ready, manual error with malicious text, active job actions, current-job-id fallback, and null-safe defaults.
- Source contract confirms the presentation module has no DOM/API side effects and `translation.js` delegates action shaping.
- Static asset graph serves `/static-build/<asset_version>/translation_action_presentation.js` as JavaScript and includes the builder export.

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

Browser smoke:
- Launch from this worktree on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=translation-action-presentation-smoke#new-job`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, idle action-helper text, disabled start/analyze controls, and normal route/tab interaction. Do not touch live Gmail.

## Rollout And Fallback

- Commit: `Extract translation primary action presentation`.
- Ready PR: `[codex] Extract translation primary action presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove this worktree only after `main` contains the merge.
- Fallback is reverting the narrow PR; existing renderer and coordinator contracts remain intact.

## Risks And Mitigations

- Risk: action helper copy changes subtly.
  - Mitigation: exact-string ESM probe coverage for every existing state.
- Risk: action enablement changes for active jobs.
  - Mitigation: tests cover job ID and action flags for cancel/resume/rebuild.
- Risk: presentation module gains coordinator coupling.
  - Mitigation: source-contract test forbids DOM, renderer, fetch, and translation-state references.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- The new export is an internal static-browser module interface.
- The user has authorized normal PR-first publish and merge flow if validation and CI pass.

## Progress

- [x] Worktree created from clean `main`.
- [x] Tests added and RED confirmed.
- [x] Implementation complete.
- [x] Targeted/focused/full validation complete.
- [x] Browser smoke complete.
- [ ] PR published, merged, and worktree cleaned up.

## Validation Outcomes

- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_action_presentation.py::test_translation_action_presentation_module_builds_primary_action_state tests/test_shadow_web_api.py::test_translation_action_presentation_module_owns_primary_action_state`
  - Failed because `translation_action_presentation.js` did not exist yet.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_action_presentation.py tests/test_shadow_web_api.py::test_translation_action_presentation_module_owns_primary_action_state tests/test_shadow_web_api.py::test_translation_ui_module_centralizes_primary_action_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_translation_browser_state.py`
  - `12 passed`
- Focused suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `231 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. Known `dart run` AOT launcher issue appeared; direct-Dart fallback succeeded for agent-docs and workspace-hygiene validation.
- Browser smoke:
  - Feature worktree server launched on port `8888`.
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=translation-action-presentation-smoke#new-job`
  - Browser runtime verified page identity, nonblank content, idle action-helper text, Start Translate presence/disabled state, no framework overlay, no console warnings/errors, and `Recent Work -> New Job` interaction returning to idle helper state.
  - Browser screenshot path hit the known local `Page.captureScreenshot` timeout; Playwright fallback captured screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\translation-action-presentation-smoke.png`.
  - No live Gmail, OAuth, native-host, or real drafts were touched.
