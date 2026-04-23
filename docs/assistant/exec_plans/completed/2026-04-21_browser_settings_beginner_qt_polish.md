# Browser Settings Beginner Qt Polish

## 1. Title
Browser Settings Beginner Qt Polish

## 2. Goal and non-goals
Goal:
- Make the `ui=qt` `#settings` route read like a clear app setup page rather than an operator/admin console.
- Keep advanced diagnostics and recovery controls available but secondary.
- Close the remaining safe-rendering gap in the Extension Lab prepare-reason catalog.

Non-goals:
- No backend API, settings persistence, route-id, Gmail, translation, interpretation, profile, native-host, or `ui=legacy` behavior changes.
- No broad redesign of Power Tools or Extension Lab.

## 3. Scope (in/out)
In:
- Settings topbar/beginner-surface treatment for `ui=qt`
- Settings page headings, field labels, option labels, button labels, and helper text
- Browser-only Settings presentation helper for summary/status/capability cards
- Small shell-description cleanup for Settings, Power Tools, and Extension Lab
- Extension Lab prepare-reason catalog safe rendering
- Focused template/route/browser-state/safe-rendering tests

Out:
- Backend settings payload changes
- Power Tools workflow redesign
- Extension Lab workflow redesign beyond the small safe-rendering fix and shell-description copy

## 4. Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- target integration branch: `main`
- canonical build status or intended noncanonical override: current browser beginner-polish feature worktree continuing the accepted Qt browser UX line

## 5. Interfaces/types/contracts affected
- Add browser-only module:
  - `src/legalpdf_translate/shadow_web/static/settings_presentation.js`
- Add browser-only exported helper from `app.js`:
  - `renderExtensionPrepareReasonCatalogInto(container, items)`
- Extend beginner-surface treatment to include `#settings` for `ui=qt` operator-off sessions.
- No backend, route-id, field-ID, select-value, or payload changes.

## 6. File-by-file implementation steps
- `docs/assistant/exec_plans/active/2026-04-21_browser_settings_beginner_qt_polish.md`
  - record the active plan and close it with validations/outcomes
- `src/legalpdf_translate/browser_app_service.py`
  - soften visible shell descriptions for Settings, Power Tools, and Extension Lab
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - rewrite the beginner-visible Settings copy, labels, option text, and helper text while preserving IDs and submitted values
- `src/legalpdf_translate/shadow_web/static/state.js`
  - add `settings` to qt/operator-off beginner-surface routing
- `src/legalpdf_translate/shadow_web/static/settings_presentation.js`
  - add pure helpers for Settings summary labels, friendly readiness status, and Settings-only capability cards
- `src/legalpdf_translate/shadow_web/static/app.js`
  - add Settings topbar/beginner-surface treatment
  - route Settings summary/capability rendering through the new helper
  - export and use a safe DOM helper for the Extension Lab prepare-reason catalog
- `src/legalpdf_translate/shadow_web/static/power-tools.js`
  - delegate Settings readiness messaging to the new helper so refresh/preflight/save/test actions keep the friendlier wording
- `tests/test_shadow_web_api.py`
  - assert friendly Settings template copy and absence of old operator wording in the Settings slice
- `tests/test_shadow_web_route_state.py`
  - assert `#settings` remains routable and is a beginner surface in qt/operator-off mode
- `tests/test_settings_browser_state.py`
  - add pure helper coverage for Settings summary/status/capability output
- `tests/test_browser_safe_rendering.py`
  - extend coverage for the Extension Lab prepare-reason catalog

## 7. Tests and acceptance criteria
- Validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_safe_rendering.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- Acceptance:
  - Settings reads like a clear setup page for daily defaults and tool checks
  - beginner-visible Settings copy no longer centers bounded/operator/runtime/bridge/job-log wording
  - Settings route id and backend behavior remain unchanged
  - Extension Lab prepare reasons render safely as literal text
  - validation passes through `.venv311`

## 8. Rollout and fallback
- Roll out as browser-only copy/presentation changes with one additive helper module.
- If the new Settings helper creates regressions, fall back to the existing render flow while keeping the beginner-facing template copy and Extension Lab safe-rendering fix.

## 9. Risks and mitigations
- Risk: Settings could stay in operator chrome because route-state and app-shell logic diverge.
  - Mitigation: update both `state.js` and `app.js`, then cover `#settings` in route-state tests.
- Risk: power-tools refresh/test actions could overwrite the new friendlier Settings status.
  - Mitigation: share a pure Settings status helper between `app.js` and `power-tools.js`.
- Risk: safe-rendering cleanup could disturb Extension Lab layout.
  - Mitigation: keep the same card structure and class usage while switching to text-node rendering.

## 10. Assumptions/defaults
- Keep the visible nav label as `Settings` and use `App Settings` for the page/topbar.
- Make `settings` a beginner surface only in `ui=qt` when operator mode is off.
- Keep advanced diagnostics available on the page instead of hiding them.
- No `APP_KNOWLEDGE.md` sync is required unless implementation reveals a same-scope wording mismatch that truly needs immediate docs alignment.

## 11. Implemented
- Added a browser-only `settings_presentation.js` helper module to centralize:
  - friendlier Settings summary labels
  - the beginner-facing Settings status sentence
  - Settings-only readiness cards for translation, OCR, Gmail replies, browser helper, and Word/PDF output
- Updated the Qt browser shell so `#settings` is treated like the other beginner setup surfaces when operator mode is off:
  - beginner-surface dataset now includes `settings`
  - route-aware topbar copy now uses `App Settings`
  - runtime selector and global Refresh de-emphasize automatically through the existing beginner-surface shell treatment
- Rewrote the Settings template copy, section labels, field labels, button labels, option text, and helper text so the page reads like app setup instead of an operator/admin console, while keeping all IDs and submitted values unchanged.
- Rewired `renderSettings(...)` in `app.js` to use the new Settings presentation helpers, and switched the Settings right-side card grid away from the shared technical capability cards.
- Updated `power-tools.js` so Settings refresh/preflight/save/test flows keep the same friendlier Settings status sentence after actions complete.
- Softened the visible shell descriptions for:
  - `Settings`
  - `Power Tools`
  - `Extension Lab`
- Closed the remaining Extension Lab prepare-reason safe-rendering gap by replacing dynamic `innerHTML` usage with DOM-safe text rendering via `renderExtensionPrepareReasonCatalogInto(...)`.

## 12. Validation results
- Focused checks:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections` -> PASS (`1 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_safe_rendering.py` -> PASS (`1 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_settings_browser_state.py` -> PASS (`1 passed`)
- Wrapper validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` -> PASS
    - baseline pytest group: `57 passed`
    - `compileall`: PASS
    - `dart run tooling/validate_agent_docs.dart` -> failed with known `Unable to find AOT snapshot for dartdev`
    - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> PASS
    - `dart run tooling/validate_workspace_hygiene.dart` -> failed with known `Unable to find AOT snapshot for dartdev`
    - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> PASS
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> PASS
    - baseline pytest group: `57 passed`
    - `compileall`: PASS
    - `tests/test_gmail_review_state.py`: `1 passed`
    - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
    - same direct-Dart fallback passed for both validators
- Bundle:
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1` -> PASS
  - ZIP created in Downloads and reported generated DOCX/PDF exclusions as expected
