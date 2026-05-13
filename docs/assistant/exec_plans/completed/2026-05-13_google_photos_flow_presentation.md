# Google Photos Flow Presentation

## Provenance
- Branch: `codex/google-photos-flow-presentation`
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_google_photos_flow_presentation`
- Base: `main@36d2f983526afa8ff41760e30b9af1e87ef924bb`
- Scope: narrow browser/Google Photos modernization PR.

## Goal
Move Google Photos flow message/status shaping out of `app.js` into a pure presentation module while preserving existing OAuth, Picker, session cleanup, routes, payloads, selectors, diagnostics slots, and safe rendering behavior.

## Planned Changes
- Add `src/legalpdf_translate/shadow_web/static/google_photos_flow_presentation.js`.
- Export pure builders for:
  - disconnect/reconnect feedback
  - connection success/pending/sign-in feedback
  - Picker waiting/launch feedback
  - selected-photo/import feedback
  - connect/choose busy labels
- Update `app.js` to gather state and call the builders before existing `setPanelStatus(...)`, `setDiagnostics(...)`, `renderGooglePhotosSummary(...)`, and `runWithBusy(...)` calls.
- Keep `google_photos_ui.js` as the safe DOM/fallback-link owner.

## Validation Plan
- Add the contract/probe test first and confirm it fails before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_google_photos_flow_presentation_module_builds_flow_messages`
- Update the static asset graph test for `/static-build/<asset_version>/google_photos_flow_presentation.js`.
- Run targeted tests, then the focused browser suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_settings_browser_state.py tests/test_action_feedback_browser_state.py`
- Run `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
- Smoke the shadow browser app without touching live Gmail, OAuth, native-host, or private Google Photos data.

## Completion Notes
- Added `google_photos_flow_presentation.js` as a pure Google Photos flow message/status builder module.
- Updated `app.js` to keep OAuth, Picker, API, session cleanup, interpretation seeding, diagnostics slots, and safe rendering in their existing owners while using the new presentation builders for flow copy and busy labels.
- Confirmed RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_google_photos_flow_presentation_module_builds_flow_messages`
- Targeted validation passed:
  `tests/test_shadow_web_api.py::test_google_photos_flow_presentation_module_builds_flow_messages`
  `tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  nearby Google Photos safe rendering/fallback/busy/action-feedback tests.
- Focused browser/Google Photos suite passed:
  `281 passed in 183.05s`.
- Full validation passed:
  `232 passed`, compileall passed, Gmail review/intake checks passed.
- Known Dart AOT launcher issue appeared during docs/hygiene validation; direct-Dart fallback succeeded for both validators.
- Shadow browser smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=google-photos-flow-smoke#new-job`; verified page identity, nonblank Interpretation surface, Google Photos pre-connect controls, no framework overlay, no warning/error console logs, and screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\legalpdf_google_photos_flow_smoke.png`.
- Did not touch live Gmail, OAuth, native-host, or private Google Photos data.
