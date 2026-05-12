# Gmail Preview Bundle Extraction

## Goal And Non-Goals

Extract Gmail attachment preview bundle readiness from `gmail.js` into a narrow helper module while preserving browser/Gmail behavior.

Non-goals:
- No backend route, payload shape, selector, DOM ID, dataset, submitted value, Gmail/native-host, or extension contract changes.
- No live Gmail, OAuth, native-host, or real draft testing.
- No UI redesign or safe-rendering changes.

## Scope

In scope:
- Add `gmail_preview_bundle.js` for preview payload fetching and PDF browser-bundle readiness.
- Update `gmail.js` to delegate preview payload/bundle work and keep DOM/action orchestration.
- Add contract and ESM probe coverage.
- Verify static asset serving for the new module.

Out of scope:
- Changing preview-panel presentation or renderer contracts.
- Changing browser-PDF worker API semantics.
- Touching non-Gmail modernization areas.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_preview_bundle`
- Branch name: `codex/gmail-preview-bundle`
- Base branch: `main`
- Base SHA: `c08d2af0b8ca24b0e97daf5082c2bc8b36ac27b6`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow-mode browser smoke only

## Interfaces, Types, And Contracts

- Preserve POST `/api/gmail/preview-attachment` with payload `{ attachment_id: attachmentId }`.
- Preserve browser-PDF bundle request behavior through `ensureBrowserPdfBundleFromUrl(...)`.
- Preserve `preview_path`, `preview_href`, and `page_count` semantics from preview payloads.
- Preserve the failure text when preview download data is missing: `Preview download for <filename> is unavailable.`
- Keep `gmail.js` responsible for drawer state, preview rendering, diagnostics, and user interactions.
- Keep `gmail_preview_bundle.js` free of DOM writes, renderers, route changes outside the existing fetch call, and unsafe HTML rendering.

## File-By-File Steps

1. `tests/test_shadow_web_api.py`
   - Add a failing contract/probe test for `gmail_preview_bundle.js`.
   - Extend the versioned static asset graph test for the new module.
2. `src/legalpdf_translate/shadow_web/static/gmail_preview_bundle.js`
   - Add helper exports for fetching preview payloads and ensuring browser-PDF bundles.
   - Keep dependencies injectable so ESM probes can run without browser DOM.
3. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - Import the preview bundle helpers.
   - Replace inline preview fetch/bundle functions with coordinator calls.
   - Leave DOM, drawer, diagnostics, render, and state ownership unchanged.
4. `docs/assistant/exec_plans/active/2026-05-12_gmail_preview_bundle.md`
   - Update with validation results and move to `completed/` before commit.

## Tests And Acceptance Criteria

- Confirm RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_bundle_module_owns_preview_payload_and_pdf_bundle_readiness`
- After implementation:
  - Run the targeted preview-bundle test.
  - Run `tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`.
  - Run the focused browser/Gmail suite:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Run `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
- Browser smoke:
  - Launch shadow app on port `8888`.
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-preview-bundle-smoke#gmail-intake`.
  - Check page identity, nonblank content, no framework overlay, console health, screenshot evidence, load demo attachments, open Preview, and confirm normal PDF preview interaction without live Gmail.

## Executed Validation

- RED confirmed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_bundle_module_owns_preview_payload_and_pdf_bundle_readiness`
  failed on missing `gmail_preview_bundle.js`.
- Targeted contract/probe:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_preview_bundle_module_owns_preview_payload_and_pdf_bundle_readiness`
  passed.
- Static asset graph:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  passed.
- Focused browser/Gmail suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  passed: 214 tests.
- Full validation:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  completed. Known `dart run ...` AOT launcher issue appeared for agent-docs and workspace-hygiene validators; both direct-Dart fallbacks passed.
- Browser smoke:
  - Shadow app launched from this feature worktree on port `8888`.
  - In-app Browser verified page identity, nonblank Gmail intake content, no framework overlay, console health, screenshot capture, and demo attachment loading.
  - In-app Browser Playwright click path timed out on the local page; DOM-CUA click worked for `Load demo attachments` and `Preview`.
  - In-app Browser PDF preview remained in `Loading...`, consistent with the separate Browser-runtime PDF limitation.
  - Local Playwright fallback against `gmail-preview-bundle-smoke-playwright` verified demo load, Preview action, attached preview-loaded diagnostics, visible `gmail-preview-canvas`, no console/page errors, and saved screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\gmail-preview-bundle-smoke.png`.
  - No live Gmail, OAuth, native-host, or real draft flow was touched.

## Rollout And Fallback

- Commit only intended files after validation.
- Push `codex/gmail-preview-bundle`, open ready PR `[codex] Extract Gmail preview bundle helper`, wait for green checks, merge normally, fast-forward canonical `main`, prune refs, and remove the worktree after `main` contains the merge.
- If GitHub auth, PR creation, CI, conflicts, or checks block the flow, stop before merge and report the blocker.
- Fallback is reverting this narrow helper extraction; no backend or persisted data migration is involved.

## Risks And Mitigations

- Risk: payload or page-count semantics drift. Mitigation: ESM probes assert exact payload/request behavior and page-count state updates.
- Risk: helper accidentally performs DOM/rendering work. Mitigation: contract test forbids `document`, `innerHTML`, `renderGmail`, and `setDiagnostics`.
- Risk: Browser screenshot timeout recurs. Mitigation: use the in-app Browser path first and local screenshot fallback if the known loopback capture limitation appears.

## Assumptions And Defaults

- No live Gmail testing is in scope.
- `main` at `c08d2af0b8ca24b0e97daf5082c2bc8b36ac27b6` is the clean approved base.
- The new module is an internal browser static module, not a public backend API.
