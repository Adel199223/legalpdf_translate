# Remove Windows-Blocked PDF Startup Dependencies and Re-stabilize the Gmail Browser Flow

## Goal and non-goals
- Goal: make the browser app cold-start, Gmail handoff, Gmail preview, and Gmail-started translation work under the current Windows Smart App Control / Code Integrity policy without requiring the user to weaken Windows security.
- Goal: remove PyMuPDF (`fitz` / `pymupdf._mupdf`) from browser cold-start and browser-first Gmail/translation paths.
- Non-goal: redesign the extension/native-host model.
- Non-goal: remove PyMuPDF from every desktop/CLI path in this pass.

## Scope
- In scope:
  - browser cold-start/runtime probing
  - browser shell startup import graph
  - Gmail preview/session prep page-count handling
  - browser-side PDF metadata/raster staging for Gmail and browser translation flows
  - targeted test/runtime harness repair needed for validation
- Out of scope:
  - unrelated desktop UI cleanup
  - packaging/release work

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical override on feature branch; canonical floor preserved by `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Native-host/browser runtime validation in `gmail_focus_host.py`
- Browser shell/bootstrap routes in `shadow_web.server` and `shadow_web.app`
- Gmail preview/session prep payloads and translation launch payloads
- Additive browser PDF staging contract for page-count and per-page rendered images
- Translation/browser source handling for browser-staged PDF pages

## File-by-file implementation steps
1. `src/legalpdf_translate/gmail_focus_host.py`
   - replace the heavy browser runtime probe with a shell-safe runtime probe
   - keep native-host self-test lightweight
   - separate shell-readiness from document-runtime readiness in prepare responses
2. `src/legalpdf_translate/shadow_web/server.py` and `src/legalpdf_translate/shadow_web/app.py`
   - split shell-safe app startup from heavy feature imports
   - lazy-load translation/Gmail/interpretation services behind route-local or property-local seams
   - expose additive document-runtime diagnostics in shell/bootstrap payloads
3. `src/legalpdf_translate/gmail_batch.py` and `src/legalpdf_translate/gmail_browser_service.py`
   - remove server-side PDF page-count dependence from preview/session prep cold paths
   - accept client/browser-provided PDF metadata for Gmail prep where needed
4. `src/legalpdf_translate/shadow_web/static/*.js` and template assets
   - vendor local PDF.js assets
   - add browser-side PDF session handling for page count, preview page navigation, and page raster upload
   - build browser PDF bundles before browser/Gmail PDF translation starts
5. `src/legalpdf_translate/source_document.py`, `src/legalpdf_translate/translation_service.py`, `src/legalpdf_translate/workflow.py`, and related types
   - add additive browser-staged PDF source handling
   - keep existing file-path source handling intact
   - route OCR/image generation for browser-staged PDF pages through uploaded page images instead of PyMuPDF
6. Targeted tests / runtime harness
   - add and update tests for shell-safe startup, Gmail preview/session prep, browser PDF staging, and end-to-end Gmail translation
   - repair the damaged Python test/runtime environment enough to run the targeted suites

## Tests and acceptance criteria
- `gmail_focus_host --self-test` passes without importing PyMuPDF
- browser runtime probe passes without importing `shadow_web.server` heavy graph
- `python -m legalpdf_translate.shadow_web.server --help` and browser shell startup no longer fail under blocked PyMuPDF
- true cold state on `8877`/`8765` -> extension click opens browser app into styled `gmail-intake`
- Gmail preview works inline with browser-derived page count and page navigation
- one-page Gmail-sourced PDF translation succeeds without server-side PyMuPDF
- translation/OCR diagnostics still pass
- targeted pytest/browser/runtime suites pass from a repaired canonical environment

## Rollout and fallback
- Default behavior stays browser-first and extension-first.
- If browser document runtime is unavailable after shell start, surface explicit diagnostics instead of `launch_runtime_broken`.
- Keep existing raw attachment file route and hydration recovery behavior as compatibility anchors.

## Risks and mitigations
- Risk: widening the translation source contract could regress desktop/CLI flows.
  - Mitigation: keep browser-staged PDF support additive and leave existing file-path path intact.
- Risk: browser PDF staging can become too large or brittle.
  - Mitigation: store a manifest + page images locally per source, reuse them by `source_path`, and keep initial acceptance focused on the Gmail/browser path.
- Risk: lazy-loading can hide startup failures until later.
  - Mitigation: expose document-runtime diagnostics separately and cover route-specific activation with targeted tests.

## Assumptions/defaults
- Smart App Control / Code Integrity remains enabled.
- No manual Windows allow/whitelist step is part of the main fix.
- Local vendored PDF.js assets are preferred over a remote CDN.
- The browser app remains the primary user surface for this workflow.

## Outcome
- Completed on March 30, 2026.
- Browser cold-start/runtime probing is now shell-safe under the Windows-blocked native PDF runtime.
- Browser-first PDF handling now uses a browser-staged bundle path for Gmail preview/session prep and translation workflows, without requiring PyMuPDF during browser startup.
- Native-host cold-start validation now succeeds with the validated runtime path and no longer depends on the blocked PDF module path.

## Validation
- Targeted pytest suite in `tmp/stage3_e2e_venv`:
  - `tests/test_shadow_web_api.py`
  - `tests/test_source_document.py`
  - `tests/test_gmail_focus_host.py`
  - `tests/test_browser_gmail_bridge.py`
  - `tests/test_gmail_browser_service.py`
  - `tests/test_gmail_intake.py`
  - `tests/test_shadow_web_runtime_recovery.py`
  - `tests/test_workflow_ocr_routing.py`
  - Result: `107 passed`
- Live blocked-runtime shell smoke:
  - `python -m legalpdf_translate.shadow_web.server --port 8895`
  - `POST /api/settings/translation-test` -> `200 ok`
  - `POST /api/settings/ocr-test` -> `200 ok`
- Live browser-bundle translation smoke on `8895`:
  - uploaded a PDF source
  - staged a browser PDF bundle through `/api/browser-pdf/bundle`
  - started `/api/translation/jobs/translate`
  - completed successfully as job `tx-56b7bd08ad68`
  - output: `tmp/browser_bundle_smoke_output/20260330_150039_932926_bundle-smoke_EN_20260330_150100.docx`
- Native-host cold-start smoke:
  - closed listeners on `8877` and `8765`
  - called `prepare_gmail_intake(..., request_focus=True, include_token=False)`
  - result: `launched=True`, `ui_owner=browser_app`, `reason=bridge_owner_ready`
  - confirmed `GET /api/bootstrap/shell?mode=live&workspace=gmail-intake` on `8877` returned `200` with `shell.ready=true`
