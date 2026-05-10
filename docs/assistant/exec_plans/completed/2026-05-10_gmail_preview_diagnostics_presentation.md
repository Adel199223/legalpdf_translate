# Gmail Preview Diagnostics Presentation

## Goal and non-goals
- Extract the Gmail preview-loaded diagnostics presentation shaping from `gmail.js` into the existing pure `gmail_preview_presentation.js` module.
- Preserve the current Gmail preview renderer, API route, payload contracts, dataset names, IDs, safe rendering behavior, native-host behavior, and shadow/live routing.
- Keep this slice narrow: no live Gmail, OAuth, native-host, backend route, or preview rendering changes.

## Scope
- In scope:
  - Add a pure diagnostics helper beside the preview-panel presentation builder.
  - Update `gmail.js` so the preview coordinator gathers state, calls the helper, and passes the existing diagnostics shape into `setDiagnostics(...)`.
  - Add contract and ESM probe coverage for normal, malicious, fallback, and null-safe diagnostics inputs.
  - Validate with focused browser/Gmail tests, full dev validation, and shadow-only browser smoke.
- Out of scope:
  - Live Gmail testing, OAuth flows, native-host registration, extension handoff changes, backend API or payload changes, renderer changes, and route changes.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_preview_diagnostics_presentation`
- Branch name: `codex/gmail-preview-diagnostics-presentation`
- Base branch: `main`
- Base SHA: `e44b75e7df691676aef7969593ea1f98530c353a`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow browser mode only for GUI smoke.

## Interfaces/types/contracts affected
- No public backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes are intended.
- `gmail_preview_presentation.js` gains a new pure export:
  - `buildGmailPreviewLoadedDiagnosticsPresentation(...)`
- Existing diagnostics shape remains:
  - `{ hint, open }`

## File-by-file implementation steps
- `tests/test_shadow_web_api.py`
  - Extend the preview presentation contract and ESM probes to require the new diagnostics helper.
  - Extend the static asset graph assertion for the new export.
- `src/legalpdf_translate/shadow_web/static/gmail_preview_presentation.js`
  - Add the pure diagnostics helper with safe defaults and no DOM writes.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Import the helper and replace inline preview-loaded diagnostics shaping with a helper call.

## Tests and acceptance criteria
- First confirm the targeted contract fails before implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_presentation_module_derives_preview_panel_state`
- After implementation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_presentation_module_derives_preview_panel_state tests/test_shadow_web_api.py::test_gmail_preview_ui_module_owns_preview_panel_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke:
  - Launch shadow preview on port `8888`.
  - Verify the Gmail review demo page identity, nonblank content, console health, no framework overlay, demo attachment load, preview interaction, and no live Gmail/OAuth/native-host flow.

## Rollout and fallback
- Publish through a ready GitHub PR after local validation and browser smoke.
- Merge only after required checks are green.
- If validation fails, keep the branch open and fix before publishing or merging.
- Fallback is to revert the narrow helper import/call and leave the inline coordinator diagnostics unchanged.

## Risks and mitigations
- Risk: accidentally altering user-visible diagnostic text.
  - Mitigation: ESM probes assert the exact current hint text pattern and `open: false`.
- Risk: weakening safe rendering by moving dynamic filenames.
  - Mitigation: helper returns plain data only; existing diagnostics renderer remains the only DOM writer.
- Risk: touching live Gmail.
  - Mitigation: smoke uses `mode=shadow` with demo attachments only.

## Assumptions/defaults
- Null or missing attachment names should fall back to the existing user-facing `attachment` label.
- A passed normalized payload filename takes precedence over a fallback attachment filename.
- No docs sync is necessary for this internal presentation-only extraction unless later validation reveals user-facing docs drift.

## Closeout results
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_presentation_module_derives_preview_panel_state tests/test_shadow_web_api.py::test_gmail_preview_ui_module_owns_preview_panel_renderer`
  - Failed for the intended missing presentation export/import and coordinator helper call.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_presentation_module_derives_preview_panel_state tests/test_shadow_web_api.py::test_gmail_preview_ui_module_owns_preview_panel_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `3 passed`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `203 passed`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed.
  - Known Dart launcher issue observed for `dart run ...`: `Unable to find AOT snapshot for dartdev`.
  - Direct-Dart fallback succeeded for agent docs validation and workspace hygiene validation.
- Browser smoke:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_preview_diagnostics_presentation`
  - Branch: `codex/gmail-preview-diagnostics-presentation`
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-preview-diagnostics-smoke#gmail-intake`
  - Result: passed.
  - Verified page identity, nonblank Gmail intake content, no framework overlay, empty console warnings/errors, demo attachment load, Preview opening, preview drawer/page controls, and PDF canvas content for `demo-gmail-review.pdf`.
  - No live Gmail, OAuth, native-host, extension handoff, draft, or private mailbox flow was touched.
