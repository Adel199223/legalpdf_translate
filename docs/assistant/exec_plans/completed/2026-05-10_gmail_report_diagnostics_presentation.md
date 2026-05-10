# Gmail Report Diagnostics Presentation

## Goal and non-goals
- Move Gmail report-generation diagnostics presentation shaping out of `gmail.js` into the existing pure `gmail_report_presentation.js` module.
- Preserve existing diagnostics shapes, report-generation behavior, backend routes, payloads, selectors, submitted values, Gmail/native-host behavior, and safe rendering.
- Keep the slice narrow: no live Gmail, OAuth, native-host, backend API, renderer, or finalization workflow changes.

## Scope
- In scope:
  - Add pure builders for Gmail browser-failure report diagnostics and Gmail finalization report diagnostics.
  - Update `handleGmailFailureReport()` and `handleGmailFinalizationReport()` to call those builders before `setDiagnostics(...)`.
  - Add contract and ESM probe coverage for report path, fallback, malicious text, and null-safe defaults.
  - Validate with targeted tests, focused browser/Gmail suite, full dev validation, and shadow-only Browser smoke.
- Out of scope:
  - Live Gmail testing, real drafts, OAuth, native-host registration, extension handoff, backend route or payload changes, and UI renderer changes.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_report_diagnostics_presentation`
- Branch name: `codex/gmail-report-diagnostics-presentation`
- Base branch: `main`
- Base SHA: `83d4f8a2aa105f62bd4fc442d81707ae01f4fe8d`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow browser mode only for GUI smoke.

## Interfaces/types/contracts affected
- No public backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes are intended.
- `gmail_report_presentation.js` gains internal static-browser exports:
  - `buildGmailBrowserFailureReportDiagnosticsPresentation({ payload })`
  - `buildGmailFinalizationReportDiagnosticsPresentation({ payload })`
- Existing diagnostics shape remains:
  - `{ hint, open }`

## Implementation steps
- `tests/test_shadow_web_api.py`
  - Add the failing report diagnostics presentation contract and ESM probes.
  - Extend the versioned static asset test for the new exports.
- `src/legalpdf_translate/shadow_web/static/gmail_report_presentation.js`
  - Add the two pure diagnostics builders.
  - Keep the builders data-only, with no DOM or renderer references.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Import the builders.
  - Replace inline diagnostics shaping in `handleGmailFailureReport()` and `handleGmailFinalizationReport()` with builder calls.

## Tests and acceptance criteria
- RED:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_presentation_module_builds_report_diagnostics_state`
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_presentation_module_builds_report_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke:
  - Launch shadow preview on port `8888`.
  - Verify Gmail intake page identity, nonblank content, no framework overlay, console health, screenshot evidence, demo attachment load, and normal review/preview interaction.

## Rollout and fallback
- Publish through a ready GitHub PR after local validation and Browser smoke.
- Merge only after required checks are green.
- If validation fails, keep the branch open and fix before publishing or merging.
- Fallback is to revert the helper imports/calls and leave the existing inline report diagnostics unchanged.

## Risks and mitigations
- Risk: report-generated diagnostics text changes accidentally.
  - Mitigation: ESM probes assert exact current hint/open shapes.
- Risk: dynamic text rendering weakens.
  - Mitigation: builders return plain data only; existing diagnostics renderer remains the DOM writer.
- Risk: live Gmail impact.
  - Mitigation: smoke uses `mode=shadow` and demo attachments only.

## Assumptions/defaults
- Null or missing payloads fall back to the existing report-generated messages and `open: true`.
- No docs sync is needed for this internal presentation-only extraction unless later validation reveals user-facing docs drift.

## Closeout results
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_presentation_module_builds_report_diagnostics_state`
  - Result: failed for the intended missing `buildGmailBrowserFailureReportDiagnosticsPresentation` export before implementation.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_report_presentation_module_builds_report_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `2 passed`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `206 passed`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed.
  - Known Dart launcher issue observed for `dart run ...`: `Unable to find AOT snapshot for dartdev`.
  - Direct-Dart fallback succeeded for agent docs validation and workspace hygiene validation.
- Browser smoke:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_report_diagnostics_presentation`
  - Branch: `codex/gmail-report-diagnostics-presentation`
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-report-diagnostics-smoke-fallback#gmail-intake`
  - Result: passed with local Playwright fallback after the Browser plugin refused to allocate an owned disposable in-app tab.
  - Verified page identity, nonblank hydrated Gmail intake content, no framework overlay, empty console warnings/errors, demo attachment load, Preview opening, preview drawer visibility, preview status, and PDF canvas content for `demo-gmail-review.pdf`.
  - Screenshot evidence saved outside the repo:
    - `C:\Users\FA507\AppData\Local\Temp\gmail-report-diagnostics-smoke.png`
    - `C:\Users\FA507\AppData\Local\Temp\gmail-report-diagnostics-smoke-preview.png`
  - No live Gmail, OAuth, native-host, extension handoff, draft, or private mailbox flow was touched.
