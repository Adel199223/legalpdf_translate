# Shell Bootstrap Status Presentation

## Goal And Non-Goals

Move shell bootstrap status and label shaping out of `app.js` into the pure `shell_presentation.js` module. Keep bootstrap fetches, app state assignment, DOM lookup, diagnostics rendering, route IDs, payload shapes, selectors, Gmail/native-host behavior, and safe text rendering unchanged.

Non-goals: no backend route changes, no live Gmail/OAuth/native-host testing, no UX copy changes, no renderer rewrites.

## Scope

In scope:
- Add pure shell presentation builders for shell bootstrap snapshots and staged bootstrap retry status.
- Update `app.js` to gather coordinator state, call the builders, and pass returned labels/status text to the existing safe renderers.
- Add ESM and source-contract tests for the new builders.
- Add static asset coverage for the new exports.

Out of scope:
- Browser route contract changes.
- Gmail payload or extension contract changes.
- Live Gmail operations.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_shell_bootstrap_status_presentation`
- Branch name: `codex/shell-bootstrap-status-presentation`
- Base branch: `main`
- Base SHA: `b9a33d047fe6278bb876a63697d7551b0958f3ee`
- Target integration branch: `main`
- Build status: noncanonical feature worktree for shadow-mode validation only.

## Interfaces And Contracts

The new exports are internal browser static module interfaces:
- `buildShellBootstrapSnapshotPresentation(...)`
- `buildStagedBootstrapRetryPresentation(...)`

No public backend API, selector, submitted value, route, Gmail/native-host, or extension contract changes are allowed.

## Implementation Steps

1. Add failing tests in `tests/test_shadow_web_api.py` for the shell bootstrap presentation builders and source contracts.
2. Confirm the targeted test fails before implementation.
3. Add pure builders to `src/legalpdf_translate/shadow_web/static/shell_presentation.js`.
4. Update `src/legalpdf_translate/shadow_web/static/app.js` so `applyShellBootstrapSnapshot(...)` and `applyStagedBootstrapRetryStatus(...)` call those builders, while retaining existing renderer calls and side effects.
5. Update the versioned static asset test to assert the new exports are served.
6. Run targeted tests, focused browser/shell/Gmail suites, full validation, and shadow browser smoke.

## Tests And Acceptance Criteria

Targeted:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_shell_presentation_module_builds_bootstrap_status_state`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Focused:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`

Full:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow app from this worktree on port `8888`.
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=shell-bootstrap-status-smoke#new-job`.
- Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, and a normal interaction. Do not touch live Gmail.

Acceptance criteria:
- New builders return the exact existing labels, hints, tones, slots, and messages.
- Builders are DOM-free and renderer-free.
- `app.js` no longer owns the moved inline bootstrap diagnostic/status copy.
- All targeted, focused, and full validations pass.
- PR is created, checks pass, and branch is merged normally unless a gate blocks publication.

## Rollout And Fallback

Roll out through a ready PR. If validation or CI fails, fix on the feature branch and rerun focused checks. If a GitHub/auth/CI/merge gate blocks completion, stop at the highest clean point and report the blocker.

## Risks And Mitigations

- Risk: accidentally changing status copy or tone. Mitigation: exact ESM assertions for all branches.
- Risk: moving coordinator logic into presentation. Mitigation: source contract checks forbid DOM/renderers in the pure module and keep side effects in `app.js`.
- Risk: Browser screenshot runtime timeout. Mitigation: attempt Browser first; use the existing local Playwright fallback only if the Browser screenshot runtime hits the known limitation, and record the limitation.

## Assumptions

- Shadow-mode browser validation is sufficient for this internal UI modernization slice.
- No live Gmail, OAuth, native-host, or real draft operation is in scope.
- The known Dart AOT launcher issue is only recorded if `validate_dev.ps1 -Full` reports direct-Dart fallback success.

## Completion Notes

Implemented:
- Added `buildShellBootstrapSnapshotPresentation(...)` and `buildStagedBootstrapRetryPresentation(...)` to `shell_presentation.js`.
- Updated `app.js` bootstrap snapshot and staged retry flows to call the pure builders, then pass the returned labels/status objects to the existing safe renderers.
- Added ESM/source contract coverage and static asset coverage.

Validation:
- Targeted builder test failed red on the missing export, then passed after implementation.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_shell_presentation_module_builds_bootstrap_status_state` passed.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` passed.
- Focused suite passed: `258 passed`.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passed. The known `Unable to find AOT snapshot for dartdev` issue appeared for docs and workspace hygiene validators; both direct-Dart fallbacks succeeded.

Browser smoke:
- Launched shadow app from the feature worktree on port `8888`.
- Verified `http://127.0.0.1:8888/?mode=shadow&workspace=shell-bootstrap-status-smoke#new-job`.
- Browser verified page identity (`LegalPDF Translate`), nonblank content, no framework overlay, clean console, and DOM-based navigation from New Job to Recent Work and back.
- Browser `Page.captureScreenshot` still timed out in the in-app runtime, so screenshot evidence used the local loopback Edge fallback: `C:\Users\FA507\AppData\Local\Temp\iab-screenshot-fallback-1778672449046.png`.
- No live Gmail, OAuth, native-host, or real draft flow was touched.
