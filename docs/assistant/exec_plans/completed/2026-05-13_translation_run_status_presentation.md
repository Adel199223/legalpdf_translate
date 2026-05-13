# Translation Run Status Presentation

## Goal And Non-Goals

Extract translation run-status presentation shaping from `translation.js` into a pure static module while preserving the existing safe DOM renderer and browser contracts.

Non-goals:
- No backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes.
- No live Gmail, OAuth, native-host, or real draft testing.
- No visual redesign of the translation run-status card.

## Scope

In:
- Add a pure `translation_run_status_presentation.js` module.
- Keep the existing renderer in `translation_ui.js` unchanged.
- Update `translation.js` to gather coordinator state and delegate run-status view shaping.
- Add ESM probe and source-contract tests.
- Validate with focused browser/Gmail/translation tests, full validation, and shadow browser smoke.

Out:
- Reworking translation source-state derivation.
- Changing progress-card copy or safe text rendering behavior.
- Changing public backend/static route behavior beyond serving the new asset.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_translation_run_status_presentation`
- Branch name: `codex/translation-run-status-presentation`
- Base branch: `main`
- Base SHA: `9069011d314b05014e3d8395ceaebb407848888d`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical `main` remains clean and stable

## Interfaces, Types, And Contracts Affected

- Internal static-browser module interface:
  - New export: `deriveTranslationRunStatusView(job, options)`
- Existing exported `translation.js` compatibility surface remains available.
- Existing DOM IDs, renderer shape, text-safe rendering, backend routes, payloads, and selectors remain unchanged.

## File-By-File Implementation Steps

1. Add tests first:
   - `tests/test_translation_run_status_presentation.py`
   - `tests/test_shadow_web_api.py`
2. Confirm the new targeted tests fail because the module and contract do not exist yet.
3. Add `src/legalpdf_translate/shadow_web/static/translation_run_status_presentation.js`.
4. Move pure log-flag and task-copy shaping into the new module.
5. Update `translation.js` to import the builder, export a compatibility wrapper, gather coordinator state, and delegate to the presentation module before rendering.
6. Update static asset graph coverage for the new module.
7. Mark this ExecPlan complete and move it to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted RED:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_run_status_presentation.py::test_translation_run_status_presentation_module_builds_run_status_state tests/test_shadow_web_api.py::test_translation_run_status_presentation_module_owns_run_status_view`

Targeted GREEN:
- New presentation probe tests pass.
- New source-contract test passes.
- Static asset graph test serves `/static-build/<asset_version>/translation_run_status_presentation.js` as JavaScript and includes the builder export.

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Record the known Dart AOT launcher issue only if the wrapper reports direct-Dart fallback success.

Browser smoke:
- Launch from this feature worktree on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=translation-run-status-presentation-smoke#new-job`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, and normal translation run-status/review interaction. Do not touch live Gmail.

## Rollout And Fallback

- Publish as a ready PR titled `[codex] Extract translation run status presentation`.
- Merge only after CI is green.
- Fast-forward canonical `main`, prune refs, and remove this feature worktree only after `main` contains the merge.
- Fallback is reverting the narrow PR; renderer and coordinator contracts stay intact.

## Risks And Mitigations

- Risk: subtle copy regression in run-status text.
  - Mitigation: ESM probes assert exact existing copy for idle, prepared, running, completed, failed, and raw technical states.
- Risk: moving helpers accidentally introduces DOM or coordinator coupling.
  - Mitigation: contract test forbids DOM, renderer, and fetch usage in the presentation module.
- Risk: Browser plugin path remains flaky.
  - Mitigation: attempt Browser first; if invocation fails, record the failure and use local Playwright fallback only for smoke evidence.

## Assumptions And Defaults

- No public API changes are required.
- No live Gmail testing is in scope.
- The new module is an internal static-browser module.
- The user has authorized the normal PR-first publish and merge flow if validation and CI pass.

## Progress

- [x] Worktree created from clean `main`.
- [x] Tests added and RED confirmed.
- [x] Implementation complete.
- [x] Targeted/focused/full validation complete.
- [x] Browser smoke complete.
- [ ] PR published, merged, and worktree cleaned up.

## Validation Outcomes

- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_run_status_presentation.py::test_translation_run_status_presentation_module_builds_run_status_state tests/test_shadow_web_api.py::test_translation_run_status_presentation_module_owns_run_status_view`
  - Failed because `translation_run_status_presentation.js` did not exist yet.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_run_status_presentation.py tests/test_shadow_web_api.py::test_translation_run_status_presentation_module_owns_run_status_view tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_translation_browser_state.py::test_translation_browser_loaded_job_source_replaces_stale_summary_and_run_status_view`
  - `4 passed`
- Compatibility GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_translation_ui_module_centralizes_primary_action_renderer tests/test_shadow_web_api.py::test_translation_run_status_presentation_module_owns_run_status_view tests/test_translation_run_status_presentation.py tests/test_translation_browser_state.py::test_translation_browser_loaded_job_source_replaces_stale_summary_and_run_status_view`
  - `4 passed`
- Focused suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `230 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. Known `dart run` AOT launcher issue appeared; direct-Dart fallback succeeded for agent-docs and workspace-hygiene validation.
- Browser smoke:
  - Feature worktree server launched on port `8888`.
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=translation-run-status-presentation-smoke#new-job`
  - Browser runtime verified page identity, nonblank content, run-status idle text, source controls, no framework overlay, and no console warnings/errors.
  - Browser screenshot path hit the known local `Page.captureScreenshot` timeout; Playwright fallback captured screenshot evidence and verified `Recent Work -> New Job` interaction returned to the idle run-status state.
  - No live Gmail, OAuth, native-host, or real drafts were touched.
