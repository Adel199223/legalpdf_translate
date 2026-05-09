# Gmail Report Context Shaping

## Goal and Non-Goals
Extract pure Gmail diagnostic report-context shaping from `gmail.js` into a focused static module while preserving report routes, submitted payload keys, Gmail/native-host behavior, and safe rendering.

Non-goals: no report endpoint changes, no finalization behavior changes, no Gmail preview/PDF rendering changes, no live Gmail/OAuth/native-host testing, and no visual redesign.

## Scope
In scope:
- Add `src/legalpdf_translate/shadow_web/static/gmail_report_context.js`.
- Export pure builders for attachment snapshots, browser failure report context, and finalization report context.
- Update `gmail.js` so it gathers coordinator state, calls the pure builders, and keeps API calls/diagnostics side effects local.
- Add ESM, structural, and versioned static asset tests.
- Validate in shadow Gmail mode with the demo review/preview flow.

Out of scope:
- Report button UI/presentation behavior, already owned by `gmail_report_ui.js` and `gmail_report_presentation.js`.
- Backend report generation, power-tools diagnostics, Gmail finalization API behavior, or native-host contracts.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_report_context`
- Branch name: `codex/gmail-report-context-shaping`
- Base branch: `origin/main`
- Base SHA: `0e0ac754a7c2ecff16dcef4a225e0558eee3c393`
- Target integration branch: `main`
- Canonical build status: feature worktree is noncanonical; canonical main remains `C:\Users\FA507\.codex\legalpdf_translate`.

## Interfaces, Types, and Contracts Affected
- Browser static report-context module gains pure exports.
- `gmail.js` internal report context construction delegates to the new module.
- `/api/power-tools/diagnostics/run-report` payload shape must remain unchanged for `browser_failure_context` and `gmail_finalization_context`.
- No backend route, API payload, DOM selector, Gmail/native-host, or extension contract changes.

## File-by-File Implementation Steps
- `tests/test_shadow_web_api.py`: add ESM probes for report-context builders, structural ownership checks, and versioned static asset coverage.
- `src/legalpdf_translate/shadow_web/static/gmail_report_context.js`: add pure builders without DOM writes.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: replace inline report context shaping with calls into the new module while preserving state reads, timestamps, API calls, diagnostics rendering, and report-button updates.

## Tests and Acceptance Criteria
- First confirm the targeted report-context tests fail for missing module/exports/delegation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_context_module_builds_diagnostic_payloads tests/test_shadow_web_api.py::test_gmail_report_context_module_owns_report_context_shaping`
- After implementation run:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_context_module_builds_diagnostic_payloads tests/test_shadow_web_api.py::test_gmail_report_context_module_owns_report_context_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke from this worktree on port `8888` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-report-context-smoke#gmail-intake` verifies page identity, nonblank content, no framework overlay, console health, demo attachment load, review drawer, attachment selection, successful PDF preview path or documented Browser fallback, and no live Gmail/OAuth/native-host flow.

## Validation Record
- Red check confirmed before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_context_module_builds_diagnostic_payloads tests/test_shadow_web_api.py::test_gmail_report_context_module_owns_report_context_shaping`
  - Result: failed because `gmail_report_context.js` was missing.
- Targeted report-context/static asset checks after implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_context_module_builds_diagnostic_payloads tests/test_shadow_web_api.py::test_gmail_report_context_module_owns_report_context_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `3 passed in 2.57s`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `200 passed in 178.44s`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed. The wrapper hit the known `dartdev` AOT snapshot issue for agent-docs and workspace-hygiene validators, then both direct-Dart fallbacks succeeded.
- Browser smoke:
  - Browser plugin loaded `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-report-context-smoke#gmail-intake`, confirmed page identity, nonblank Gmail review content, no framework overlay, empty console warnings/errors, demo attachment load, attachment selection, and the PDF preview drawer path.
  - Browser screenshot capture timed out on `Page.captureScreenshot`; Playwright fallback was used only for screenshot evidence and reproduced the same shadow demo flow at `workspace=gmail-report-context-smoke-pw11`.
  - Screenshot evidence: `C:\Users\FA507\AppData\Local\Temp\gmail-report-context-smoke-playwright.png`.
- Review:
  - Independent reviewer found no implementation logic blockers. The only important finding was that the new module and ExecPlan were untracked before staging; this is handled by explicit staging during publish.

## Rollout and Fallback
Publish via a ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending. If diagnostic report payload behavior regresses, revert only this feature branch and leave canonical `main` untouched.

## Risks and Mitigations
- Risk: report payload key drift. Mitigation: ESM tests pin exact top-level keys, nested message/preview/runtime fields, and finalization context precedence.
- Risk: losing browser PDF diagnostics details. Mitigation: tests assert diagnostics are merged from normalized browser error diagnostics and error payload diagnostics.
- Risk: accidental DOM/rendering coupling in pure module. Mitigation: structural tests assert no `document.` or `innerHTML` and `gmail.js` no longer owns the full report context assembly.

## Assumptions and Defaults
- Shadow mode is sufficient for smoke.
- No live Gmail testing is in scope.
- User authorization covers commit, ready PR creation, green-check merge, canonical main fast-forward, and feature worktree cleanup.
