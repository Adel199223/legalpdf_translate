# Browser Recent Work Beginner Qt Polish

## Title
Beginner-first Qt polish for the browser recent-work and saved-records surface.

## Goal and non-goals
- Goal:
  - make the browser `ui=qt` `#recent-jobs` route read like a saved-work screen instead of a job-log console
  - keep recent saved cases, translation runs, and older history sections easy to understand for beginners
- Non-goals:
  - no backend API, database, or route-id changes
  - no translation, interpretation, Gmail, native-host, or `ui=legacy` behavior changes

## Scope
- In:
  - visible recent-work nav label and recent-jobs shell copy
  - route-aware topbar/beginner-surface treatment for `#recent-jobs`
  - browser-only recent-work presentation helpers
  - recent saved-record/history/run action labels and status messages
  - focused markup/route/browser-state test updates
- Out:
  - backend job-log semantics
  - operator/dashboard/settings/profile/power-tools wording cleanup
  - translation/interpretation load/delete/open behavior changes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-new-job-qt-polish`
- Base branch: `feat/browser-new-job-qt-polish`
- Base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- Target integration branch: `main`
- Canonical build status: noncanonical browser-shell worktree carrying the approved Qt beginner UX baseline

## Interfaces/types/contracts affected
- `src/legalpdf_translate/shadow_web/static/translation.js`
  - add a browser-only recent-work presentation helper and title formatter
- `src/legalpdf_translate/shadow_web/static/state.js`
  - extend beginner-surface routing to include `#recent-jobs` in `ui=qt` when operator mode is off
- No backend, route, DOM ID, or payload contract changes

## File-by-file implementation steps
- `docs/assistant/exec_plans/active/2026-04-21_browser_recent_work_beginner_qt_polish.md`
  - record the active plan and close it with validations/results
- `src/legalpdf_translate/browser_app_service.py`
  - rename the visible `recent-jobs` nav label/description to saved-work wording only
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - update `#recent-jobs` static copy and bootstrap beginner-surface gating for recent-work
- `src/legalpdf_translate/shadow_web/static/state.js`
  - treat `recent-jobs` as a beginner surface in qt/operator-off sessions
- `src/legalpdf_translate/shadow_web/static/app.js`
  - add recent-work topbar copy and route recent-work status/delete/load messages through beginner-friendly wording
- `src/legalpdf_translate/shadow_web/static/translation.js`
  - add the pure recent-work presentation helper and apply it to translation history/run renderers
- `tests/test_shadow_web_api.py`
  - update recent-work markup assertions and beginner-surface bootstrap expectation
- `tests/test_shadow_web_route_state.py`
  - update recent-jobs beginner-surface expectations
- `tests/test_translation_browser_state.py`
  - add helper coverage for recent-work copy and recent translation-run title formatting

## Tests and acceptance criteria
- Validation commands:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- Acceptance:
  - the primary `#recent-jobs` screen reads like saved work, not job-log storage
  - `#recent-jobs` route id stays unchanged
  - open/delete/load/resume/rebuild behavior remains unchanged
  - validation passes through `.venv311`

## Rollout and fallback
- Roll out as browser-only copy and presentation changes.
- If regressions appear, revert the recent-work helper usage while keeping the existing route ids and data flow untouched.

## Risks and mitigations
- Risk: recent-work copy could drift between template HTML and hydrated JS renderers.
  - Mitigation: centralize dynamic recent-work strings in one small pure helper and cover it with browser-state tests.
- Risk: extending beginner-surface gating to `#recent-jobs` could unintentionally affect operator-mode access.
  - Mitigation: keep the gate limited to `ui=qt` and operator-off sessions only, and update route-state tests.

## Assumptions/defaults
- `Recent Work` is the clearest visible nav/page label while the route id remains `#recent-jobs`.
- Hiding the topbar runtime controls on `#recent-jobs` for qt/operator-off sessions matches the beginner treatment already used on `#new-job`.

## Implemented
- Renamed the visible `#recent-jobs` Qt navigation/shell copy from job-log wording to beginner-facing saved-work wording:
  - `Recent Jobs` -> `Recent Work`
  - `Job Log Overview` -> `Saved Cases`
  - `Bounded Review Flow` -> `Open saved work`
- Extended the Qt beginner-surface shell treatment to `#recent-jobs` so normal users see the calmer topbar copy and technical runtime controls stay de-emphasized there.
- Added a small browser-only recent-work presentation helper in `translation.js` to keep recent saved-record, history, and translation-run labels consistent across template and hydrated UI.
- Updated recent saved-record/history/run actions and status messages to use beginner-friendly labels such as:
  - `Open`
  - `Delete record`
  - `Open run`
  - `Rebuild DOCX`
  - `Saved case record loaded. Review the details below.`
  - `Saved record deleted.`
  - `Saved work refreshed.`
- Kept all route ids, API endpoints, job-log/delete semantics, translation/interpretation behavior, Gmail behavior, native-host behavior, and `ui=legacy` behavior unchanged.

## Validation results
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_browser_state.py` -> PASS (`7 passed`)
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` -> PASS
  - baseline pytest group: `56 passed`
  - `compileall`: PASS
  - `dart run tooling/validate_agent_docs.dart` -> failed with `Unable to find AOT snapshot for dartdev`
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> failed with `Unable to find AOT snapshot for dartdev`
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> PASS
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> PASS
  - baseline pytest group: `56 passed`
  - `compileall`: PASS
  - `tests/test_gmail_review_state.py`: `1 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - same Dart fallback path succeeded for both validators
