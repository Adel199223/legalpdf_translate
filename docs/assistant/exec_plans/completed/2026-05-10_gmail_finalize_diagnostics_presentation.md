# Gmail Finalization Diagnostics Presentation

## Goal and non-goals
- Move Gmail finalization diagnostics presentation shaping out of `gmail.js` into pure builders in `gmail_finalize_presentation.js`.
- Preserve existing diagnostics shapes, Gmail/native-host behavior, backend routes, payloads, DOM IDs, selectors, submitted values, and safe rendering.
- Keep the slice narrow: no live Gmail, OAuth, native-host, backend API, renderer, or finalization workflow changes.

## Scope
- In scope:
  - Add pure builders for batch preflight, batch finalize, and interpretation finalize diagnostics.
  - Update the Gmail coordinator to call those builders before `setDiagnostics(...)`.
  - Add contract and ESM probe coverage for success, warning/failure, malicious text, fallback, and null-safe defaults.
  - Validate with targeted tests, focused browser/Gmail suite, full dev validation, and shadow-only Browser smoke.
- Out of scope:
  - Live Gmail testing, real drafts, OAuth, native-host registration, extension handoff, backend route or payload changes, and UI renderer changes.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_finalize_diagnostics_presentation`
- Branch name: `codex/gmail-finalize-diagnostics-presentation`
- Base branch: `main`
- Base SHA: `609c4fd5ceae18def26094537288f98d96e2c6b4`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow browser mode only for GUI smoke.

## Interfaces/types/contracts affected
- No public backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes are intended.
- `gmail_finalize_presentation.js` gains internal static-browser exports:
  - `buildGmailBatchFinalizePreflightDiagnosticsPresentation({ payload })`
  - `buildGmailBatchFinalizeDiagnosticsPresentation({ payload })`
  - `buildGmailInterpretationFinalizeDiagnosticsPresentation({ payload })`
- Existing diagnostics shape remains:
  - `{ hint, open }`

## Implementation steps
- `tests/test_shadow_web_api.py`
  - Add the failing finalization diagnostics presentation contract and ESM probes.
  - Extend the versioned static asset test for the new exports.
- `src/legalpdf_translate/shadow_web/static/gmail_finalize_presentation.js`
  - Add the three pure builders.
  - Keep the builders data-only, with no DOM or renderer references.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Import the builders.
  - Replace inline diagnostics shaping in `refreshBatchFinalizePreflight()`, `finalizeBatch()`, and `finalizeInterpretation()` with builder calls.

## Tests and acceptance criteria
- RED:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_finalize_presentation_module_builds_finalize_diagnostics_state`
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_finalize_presentation_module_builds_finalize_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
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
- Fallback is to revert the helper imports/calls and leave the existing inline diagnostics unchanged.

## Risks and mitigations
- Risk: user-visible diagnostics text changes accidentally.
  - Mitigation: ESM probes assert exact current hint/open shapes.
- Risk: dynamic text rendering weakens.
  - Mitigation: builders return plain data only; existing diagnostics renderer remains the DOM writer.
- Risk: live Gmail impact.
  - Mitigation: smoke uses `mode=shadow` and demo attachments only.

## Assumptions/defaults
- Null or missing payloads fall back to the existing warning/fallback text and `open: true` for non-success finalization states.
- No docs sync is needed for this internal presentation-only extraction unless later validation reveals user-facing docs drift.

## Closeout results
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_finalize_presentation_module_builds_finalize_diagnostics_state`
  - Result: failed for the intended missing `buildGmailBatchFinalizePreflightDiagnosticsPresentation` export before implementation.
- Environment note:
  - The shared `.venv311` had partial package installs during this pass (`jinja2`, `pip`, `pydantic`, `fastapi`, `httpx`, and `Pillow` files missing at different times). Repaired the venv only; no repo-tracked dependency files changed.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_finalize_presentation_module_builds_finalize_diagnostics_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `2 passed`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `204 passed`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed.
  - Known Dart launcher issue observed for `dart run ...`: `Unable to find AOT snapshot for dartdev`.
  - Direct-Dart fallback succeeded for agent docs validation and workspace hygiene validation.
- Browser smoke:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_finalize_diagnostics_presentation`
  - Branch: `codex/gmail-finalize-diagnostics-presentation`
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-finalize-diagnostics-smoke#gmail-intake`
  - Result: passed with local Playwright fallback after the Browser plugin refused to allocate an owned disposable in-app tab.
  - Verified page identity, nonblank hydrated Gmail intake content, no framework overlay, empty console warnings/errors, demo attachment load, Preview opening, preview drawer/page controls, and PDF canvas content for `demo-gmail-review.pdf`.
  - Screenshot evidence saved outside the repo: `C:\Users\FA507\AppData\Local\Temp\gmail-finalize-diagnostics-smoke.png`.
  - No live Gmail, OAuth, native-host, extension handoff, draft, or private mailbox flow was touched.
