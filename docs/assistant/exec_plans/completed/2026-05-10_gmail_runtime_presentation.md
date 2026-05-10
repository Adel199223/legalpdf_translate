# Gmail Runtime Provenance Presentation

## Goal and Non-Goals
- Extract pure Gmail runtime payload, build identity, provenance label, runtime guard storage-key, and runtime guard diagnostics shaping out of `gmail.js`.
- Keep `gmail.js` responsible for coordinator state, `window`/bootstrap access, `appState`, session storage, fetches, restart behavior, rendering, and all Gmail/native-host side effects.
- Do not change route paths, payload shapes, DOM IDs, submitted values, Gmail/native-host behavior, extension behavior, or safe rendering.

## Scope
- In scope:
  - Add `src/legalpdf_translate/shadow_web/static/gmail_runtime_presentation.js`.
  - Export pure helpers:
    - `buildGmailRuntimePayload(...)`
    - `buildGmailBuildIdentity(...)`
    - `buildGmailBuildProvenance(...)`
    - `buildGmailRuntimeGuardSessionKey(...)`
    - `buildGmailRuntimeGuardDiagnostics(...)`
  - Update `gmail.js` to call those helpers while preserving existing wrapper function names and side-effect boundaries.
  - Add contract and ESM probe coverage in `tests/test_shadow_web_api.py`.
  - Update the versioned static asset graph for the new module.
- Out of scope:
  - Changing `deriveGmailLiveRuntimeGuard(...)` behavior.
  - Moving session storage or runtime restart flow out of `gmail.js`.
  - Live Gmail, OAuth, native-host, or real draft testing.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_runtime_presentation`
- Branch name: `codex/gmail-runtime-presentation`
- Base branch: `main`
- Base SHA: `aa8e57a750dc00ef4c6a989142bc8b4517e01ecd`
- Target integration branch: `main`
- Runtime status: feature worktree is noncanonical; browser validation must use `mode=shadow`.

## Interfaces and Contracts Affected
- Internal static-browser module interface:
  - `gmail_runtime_presentation.js`
  - Pure runtime/provenance helper exports listed above.
- No public backend API, route, submitted value, selector, Gmail/native-host, or extension contract changes.

## File-by-File Implementation Steps
- `src/legalpdf_translate/shadow_web/static/gmail_runtime_presentation.js`
  - Implement pure shaping helpers with null-safe defaults and no DOM, storage, fetch, `window`, or renderer access.
  - Preserve existing precedence:
    - runtime payload values win, browser bootstrap values fill missing build branch/SHA/asset version, live mode forces `live_data`.
    - runtime `build_identity` wins over shell `build_identity`, which wins over browser bootstrap `buildIdentity`.
    - identity branch/SHA fall back to normalized runtime branch/SHA.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Import the helper exports.
  - Keep existing local wrapper names (`currentGmailRuntimePayload`, `currentGmailBuildIdentity`, etc.) but delegate pure shaping to the new module.
  - Keep session storage and runtime restart side effects in `gmail.js`.
- `tests/test_shadow_web_api.py`
  - Add RED-first contract and ESM probe coverage.
  - Assert `gmail.js` imports/calls the new helpers.
  - Assert pure module has no DOM, storage, fetch, `window`, `appState`, renderers, `setDiagnostics`, or `innerHTML`.
  - Add static asset graph assertions.
- ExecPlan
  - Mark complete and move to `completed/` after validation.

## Tests and Acceptance Criteria
- Confirm RED before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_presentation_module_builds_runtime_context_and_diagnostics`
- After implementation:
  - Targeted:
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_presentation_module_builds_runtime_context_and_diagnostics tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Focused browser/Gmail suite:
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Full validation:
    - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
    - Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.
- Browser smoke:
  - Launch shadow browser app from this worktree on port `8888`.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-runtime-presentation-smoke#gmail-intake`.
  - Check page identity, nonblank content, no framework overlay, console health, demo attachment load, review/preview interaction, and no live Gmail/OAuth/native-host/drafts touched.

## Validation Results
- Baseline check:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_guard_presentation_module_builds_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `2 passed in 5.09s`.
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_presentation_module_builds_runtime_context_and_diagnostics`
  - Failed for the intended missing `gmail_runtime_presentation.js` module.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_presentation_module_builds_runtime_context_and_diagnostics tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `2 passed in 5.10s`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `208 passed in 170.61s`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. The wrapper reported the known `Unable to find AOT snapshot for dartdev` issue for both agent docs and workspace hygiene, and direct-Dart fallback succeeded both times.
- Shadow browser smoke:
  - Launched from this feature worktree on port `8888`.
  - Browser plugin connected, but disposable-tab allocation failed, so Playwright fallback was used without driving the existing in-app browser tab.
  - Verified `LegalPDF Translate` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-runtime-presentation-smoke#gmail-intake`.
  - Demo attachment load produced one safe PDF row, Review drawer visible, Preview drawer visible, `gmail-preview-canvas` present, preview status showed page `1 of 1`, no framework overlay, and no relevant console errors/warnings observed.
  - Screenshots saved outside the repo:
    - `C:\Users\FA507\AppData\Local\Temp\gmail-runtime-presentation-smoke.png`
    - `C:\Users\FA507\AppData\Local\Temp\gmail-runtime-presentation-smoke-preview.png`
  - No live Gmail, OAuth, native-host, or real drafts touched.

## Completion
- Implementation and validation complete.
- Ready for commit, PR, CI, merge, fast-forward of canonical `main`, and feature worktree cleanup.

## Rollout and Fallback
- Publish as a ready PR after validation.
- Wait for green GitHub checks before merge.
- Merge normally, fast-forward canonical `main`, prune refs, and remove the feature worktree only after `main` contains the merge.
- Fallback is a straight revert of the helper module import/calls plus tests.

## Risks and Mitigations
- Risk: live Gmail guard safety drift if build identity precedence changes.
  - Mitigation: tests cover runtime, shell, and bootstrap precedence plus exact guard key/diagnostics fields.
- Risk: over-extracting side effects.
  - Mitigation: keep `window`, `appState`, session storage, fetch, restart, and render calls in `gmail.js`.
- Risk: shadow smoke does not exercise noncanonical live guard directly.
  - Mitigation: ESM probes cover pure guard context/diagnostics; smoke verifies Gmail intake remains healthy without live Gmail.

## Assumptions and Defaults
- No live Gmail testing is in scope.
- The existing canonical stash `pre-pr255-canonical-main-deletions-2026-05-10` is unrelated and must remain untouched.
- Browser plugin is preferred for smoke; if disposable-tab allocation is blocked, record the blocker and use the established Playwright fallback for local shadow verification.
