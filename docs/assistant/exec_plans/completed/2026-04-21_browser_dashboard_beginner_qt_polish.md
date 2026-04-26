# Browser Dashboard Beginner Qt Polish

## Title
Beginner-first Qt polish for the browser dashboard overview surface.

## Goal and non-goals
- Goal:
  - make the browser `ui=qt` `#dashboard` route read like a calm overview instead of a runtime/status console
  - keep technical details available without letting them dominate the beginner path
- Non-goals:
  - no backend API, route, or payload changes
  - no Gmail/native-host/translation/interpretation behavior changes
  - no `ui=legacy` behavior changes

## Scope
- In:
  - dashboard topbar copy and beginner-surface treatment
  - dashboard page headings and summary copy
  - beginner-facing dashboard cards and parity-audit wording
  - dashboard-only capability/status presentation helper
  - focused template/route/browser-state test updates
- Out:
  - Settings/Profile/Power Tools/Extension Lab rewrites
  - technical diagnostics payload changes
  - broader browser-shell naming changes outside `#dashboard`

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `main`
- Base branch: `main`
- Base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- Target integration branch: `main`
- Canonical build status: current browser-first beginner UX baseline with Dashboard still needing decluttering

## Interfaces/types/contracts affected
- Add one browser-only dashboard presentation helper module for dashboard summary/result/status-card wording.
- Extend beginner-surface routing to include `#dashboard` in `ui=qt` when operator mode is off.
- No backend, route-id, DOM ID, or payload contract changes.

## File-by-file implementation steps
- `docs/assistant/exec_plans/active/2026-04-21_browser_dashboard_beginner_qt_polish.md`
  - record the active plan and close it with validations/results
- `src/legalpdf_translate/browser_app_service.py`
  - rewrite dashboard nav description, dashboard cards, and parity-audit copy in beginner language
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - rename dashboard headings/copy to Overview/App Status/What You Can Do
- `src/legalpdf_translate/shadow_web/static/state.js`
  - treat `dashboard` as a beginner surface in qt/operator-off sessions
- `src/legalpdf_translate/shadow_web/static/dashboard_presentation.js`
  - add the pure helper for dashboard summary, dashboard-only status cards, and parity-result labels
- `src/legalpdf_translate/shadow_web/static/app.js`
  - add dashboard topbar copy and route dashboard rendering through the new helper while keeping shared technical cards for Settings and Extension Lab
- `tests/test_shadow_web_api.py`
  - update dashboard beginner-visible template assertions
- `tests/test_shadow_web_route_state.py`
  - update explicit `#dashboard` beginner-surface expectations
- `tests/test_translation_browser_state.py`
  - add helper coverage for dashboard copy

## Tests and acceptance criteria
- Validation commands:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- Acceptance:
  - dashboard reads like a calm overview
  - `#dashboard` route id stays unchanged
  - operator surfaces keep their technical wording
  - validation passes through `.venv311`

## Rollout and fallback
- Roll out as browser-only copy/presentation changes.
- If regressions appear, revert the dashboard presentation helper usage while keeping the existing dashboard payload and route handling intact.

## Risks and mitigations
- Risk: dashboard-only wording could accidentally overwrite shared operator surfaces.
  - Mitigation: keep a dedicated dashboard presentation helper and leave shared technical capability cards intact for Settings and Extension Lab.
- Risk: adding `dashboard` to the beginner-surface list could affect route-state expectations.
  - Mitigation: update the route-state tests and keep the change limited to qt/operator-off sessions.

## Assumptions/defaults
- Keep the visible nav label as `Dashboard` and use `Overview` for the page heading/topbar only.
- Avoid touching `APP_KNOWLEDGE.md` unless implementation reveals an immediate same-task mismatch that truly needs syncing.

## Implemented
- Kept the visible sidebar nav label as `Dashboard`, but changed the Qt dashboard page heading/topbar/status copy to an `Overview`-style beginner surface for operator-off sessions.
- Extended the Qt beginner-surface routing treatment to `#dashboard` so the runtime selector and Refresh button are hidden/de-emphasized there without changing route ids or operator-mode access.
- Added a small browser-only helper module, `dashboard_presentation.js`, to centralize:
  - zero/nonzero saved-work summary copy
  - dashboard-only status-card labels
  - friendlier parity/result labels for the dashboard overview
- Rewrote the dashboard template and bootstrap payload copy so the beginner-visible Overview path now emphasizes:
  - `App Status`
  - `What You Can Do`
  - saved work
  - workflow readiness
  rather than job-log/runtime console terminology.
- Kept shared technical capability cards intact for Settings and Extension Lab, so this pass only softened the Dashboard beginner path instead of rewriting operator surfaces.
- Preserved `ui=legacy` by making the dashboard template headings conditional: Qt shows `Overview`, while legacy keeps the older `Dashboard` / `Environment` / `App Readiness` wording.

## Validation results
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py` -> PASS (`8 passed`)
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` -> PASS
  - baseline pytest group: `57 passed`
  - `compileall`: PASS
  - `dart run tooling/validate_agent_docs.dart` -> failed with `Unable to find AOT snapshot for dartdev`
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> failed with `Unable to find AOT snapshot for dartdev`
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> PASS
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> PASS
  - baseline pytest group: `57 passed`
  - `compileall`: PASS
  - `tests/test_gmail_review_state.py`: `1 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - same Dart fallback path succeeded for both validators
