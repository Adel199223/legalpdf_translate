# Gmail Runtime Guard Diagnostics Presentation

## Goal and Non-Goals
- Extract Gmail noncanonical-runtime guard diagnostics presentation shaping out of `gmail.js`.
- Keep the existing runtime guard derivation, safe DOM renderer, backend routes, payloads, selectors, Gmail/native-host behavior, and live Gmail safety contract unchanged.
- Do not touch live Gmail, OAuth, native-host registration, real drafts, or public backend APIs.

## Scope
- In scope:
  - Add pure diagnostics presentation builders for the Gmail live-runtime guard blocked and restart flows.
  - Update `gmail.js` so the two runtime guard flows gather state, call the builders, and pass the resulting diagnostics shape to `setDiagnostics(...)`.
  - Add ESM probe and static asset coverage.
  - Validate in shadow browser mode.
- Out of scope:
  - Changing `deriveGmailLiveRuntimeGuard(...)` semantics.
  - Changing runtime restart behavior, route paths, POST bodies, DOM IDs, or renderer behavior.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_runtime_guard_presentation`
- Branch name: `codex/gmail-runtime-guard-presentation`
- Base branch: `main`
- Base SHA: `4105ac3f966f04eed31968e3b5979992b9ad1759`
- Target integration branch: `main`
- Runtime status: feature worktree is noncanonical; browser validation must use `mode=shadow`.

## Interfaces and Contracts Affected
- Internal static-browser module interface:
  - `gmail_runtime_guard_presentation.js`
  - `buildGmailRuntimeGuardBlockedDiagnosticsPresentation(...)`
  - `buildGmailRuntimeGuardRestartDiagnosticsPresentation(...)`
- No public backend API, route, submitted value, selector, Gmail/native-host, or extension contract changes.

## File-by-File Implementation Steps
- `src/legalpdf_translate/shadow_web/static/gmail_runtime_guard_presentation.js`
  - Add pure builders returning the existing `setDiagnostics(...)` details and presentation shape.
  - Keep malicious/user-provided text as data only; no DOM access or rendering.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Import the builders.
  - Replace inline diagnostics/presentation literals in `maybeBlockGmailReviewAction(...)` and `restartCanonicalRuntimeGuidance(...)`.
- `tests/test_shadow_web_api.py`
  - Add contract and ESM probe coverage for blocked, restart, malicious guard text, blank operation, custom diagnostics, and null-safe defaults.
  - Update the versioned static asset graph for `gmail_runtime_guard_presentation.js`.
- ExecPlan
  - Mark this plan complete and move it to `completed/` after validation.

## Tests and Acceptance Criteria
- Confirm RED before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_guard_presentation_module_builds_diagnostics_state`
- After implementation:
  - Targeted runtime guard tests:
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_guard_presentation_module_builds_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Focused browser/Gmail suite:
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Full validation:
    - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
    - Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.
- Browser smoke:
  - Launch shadow browser app from this worktree on port `8888`.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-runtime-guard-smoke#gmail-intake`.
  - Check page identity, nonblank content, no framework overlay, console health, demo attachment load, review/preview interaction, and no live Gmail/OAuth/native-host/drafts touched.

## Validation Results
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_guard_presentation_module_builds_diagnostics_state`
  - Failed for the intended missing `gmail_runtime_guard_presentation.js` module.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_runtime_guard_presentation_module_builds_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `2 passed in 2.13s`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `207 passed in 167.02s`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. The wrapper reported the known `Unable to find AOT snapshot for dartdev` issue for both agent docs and workspace hygiene, and direct-Dart fallback succeeded both times.
- Shadow browser smoke:
  - Launched from this feature worktree on port `8888`.
  - Browser plugin connected, but disposable-tab allocation failed, so Playwright fallback was used without driving the existing in-app browser tab.
  - Verified `LegalPDF Translate` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-runtime-guard-smoke#gmail-intake`.
  - Demo attachment load produced one safe PDF row, Review drawer visible, Preview drawer visible, `gmail-preview-canvas` present, preview status showed page `1 of 1`, no framework overlay, and no relevant console errors/warnings observed.
  - Screenshots saved outside the repo:
    - `C:\Users\FA507\AppData\Local\Temp\gmail-runtime-guard-smoke.png`
    - `C:\Users\FA507\AppData\Local\Temp\gmail-runtime-guard-smoke-preview.png`
  - No live Gmail, OAuth, native-host, or real drafts touched.

## Completion
- Implementation and validation complete.
- Ready for commit, PR, CI, merge, fast-forward of canonical `main`, and feature worktree cleanup.

## Rollout and Fallback
- Publish as a ready PR after validation.
- Wait for green GitHub checks before merge.
- Merge normally, fast-forward canonical `main`, prune refs, and remove the feature worktree only after `main` contains the merge.
- Fallback is straightforward revert of the presentation import/calls plus the new test/module.

## Risks and Mitigations
- Risk: accidentally altering live Gmail runtime safety copy or diagnostics payload.
  - Mitigation: builder tests assert existing diagnostic values and `gmail.js` still builds runtime diagnostics from coordinator state.
- Risk: safe rendering regression.
  - Mitigation: presentation module must not touch DOM or `innerHTML`; existing UI renderer remains unchanged.
- Risk: shadow smoke cannot exercise live-runtime guard.
  - Mitigation: pure ESM probes cover guard diagnostics; smoke verifies Gmail intake remains healthy without live Gmail.

## Assumptions and Defaults
- No live Gmail testing is in scope.
- The current existing stash on canonical `main` is unrelated and must remain untouched.
- The Browser plugin is preferred for in-app smoke; if disposable-tab allocation is blocked, record the blocker and use the established Playwright fallback for local shadow verification.
