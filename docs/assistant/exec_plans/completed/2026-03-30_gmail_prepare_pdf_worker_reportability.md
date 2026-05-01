# Fix Gmail Prepare Failures and Restore Reportability for Pre-Run Browser Errors

## Goal and non-goals
- Goal: make Gmail `Preview` and `Prepare selected` work again in the browser app when PDF attachments are staged through the browser PDF path.
- Goal: restore a visible, useful report flow for browser/Gmail failures that happen before a normal translation run directory exists.
- Non-goal: redesign Gmail handoff, translation startup, or Power Tools architecture.
- Non-goal: reintroduce server-side native PDF rendering into the browser-first path.

## Scope
- In scope:
  - browser PDF.js module/worker URL resolution
  - Gmail preview and prepare failure handling
  - browser/Gmail diagnostics capture for pre-run failures
  - run-report endpoint/UI extension for browser-side failure reports
  - targeted regression and live browser validation
- Out of scope:
  - unrelated translation/runtime/auth flows unless directly touched by this repair
  - release/packaging changes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical feature-branch override; canonical floor preserved by `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Browser PDF staging loader in `shadow_web/static/browser_pdf.js`
- Gmail review/prepare client flow in `shadow_web/static/gmail.js`
- Browser diagnostics/run-report API in `shadow_web/app.py` and `power_tools_service.py`
- Additive browser failure-report request/response contract for `/api/power-tools/diagnostics/run-report`

## File-by-file implementation steps
1. `src/legalpdf_translate/shadow_web/static/browser_pdf.js`
   - replace relative PDF.js asset resolution with absolute/versioned URLs derived from a static-root-safe resolver
   - apply the same resolver to both `pdf.mjs` and `pdf.worker.mjs`
   - normalize worker boot failures into structured diagnostics data
2. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - capture structured Gmail/browser PDF failure context for preview and prepare
   - preserve review state on failure
   - add a direct failure-report action near the failing Gmail diagnostics surface
3. `src/legalpdf_translate/power_tools_service.py` and `src/legalpdf_translate/shadow_web/app.py`
   - extend the existing run-report route to support both real `run_dir` reports and browser failure reports
   - return additive metadata (`report_kind`, `report_path`, preview text)
   - keep Power Tools compatibility intact
4. `src/legalpdf_translate/shadow_web/templates/index.html` and `src/legalpdf_translate/shadow_web/static/translation.js`
   - surface report-generation affordances in Gmail/translation failure surfaces without removing existing run-summary/download actions
5. `tests/test_shadow_web_api.py`, `tests/test_gmail_intake.py`, and related targeted suites
   - add regressions for correct worker URL resolution, Gmail prepare success after bundling, and failure-report generation without a run directory

## Tests and acceptance criteria
- Browser PDF loader requests:
  - `/static/vendor/pdfjs/pdf.mjs?...`
  - `/static/vendor/pdfjs/pdf.worker.mjs?...`
  - and never the doubled `/static/vendor/pdfjs/vendor/pdfjs/...` path
- Gmail PDF preview succeeds and page count/page navigation remain intact
- `Prepare selected` succeeds for Gmail PDF attachments after browser bundle staging
- Browser-side prepare/preview failures produce structured diagnostics and allow generating a report without a run directory
- Existing run-report route still works for real run directories
- Existing translation completion actions still expose run summary/download paths
- Live browser acceptance on `127.0.0.1:8877` confirms end-to-end Gmail preview + prepare works without manual refresh or hidden Power Tools detours

## Rollout and fallback
- Preserve the existing Power Tools report flow as the secondary/operator path.
- Make Gmail/browser failure reporting additive; do not remove classic run-report behavior.
- If browser PDF loading fails again, surface the structured failure and report action instead of leaving the user with only the raw pdf.js worker error.

## Risks and mitigations
- Risk: changing PDF.js URL resolution could regress the working preview/translation bundle path.
  - Mitigation: keep the resolver narrowly scoped, cover both module and worker URLs together, and validate live on `8877`.
- Risk: new failure-report mode could blur true run reports and pre-run browser reports.
  - Mitigation: return explicit `report_kind` metadata and label the UI/report copy accordingly.
- Risk: direct Gmail failure actions could diverge from Power Tools diagnostics behavior.
  - Mitigation: keep one backend route and one artifact format family, with Gmail as a context-aware entry point.

## Assumptions/defaults
- Windows security policy stays unchanged.
- The browser-managed PDF path remains the only supported browser-first PDF pipeline.
- The existing report output location under browser Power Tools outputs remains the artifact destination for both report kinds.

## Outcome
- Completed.

## Validation
- `node --check src/legalpdf_translate/shadow_web/static/browser_pdf.js`
- `node --check src/legalpdf_translate/shadow_web/static/gmail.js`
- `node --check src/legalpdf_translate/shadow_web/static/translation.js`
- `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage3_e2e_venv\Scripts\python.exe -m pytest tests/test_gmail_intake.py -k "browser_pdf_asset_urls" -q` -> `2 passed`
- `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage3_e2e_venv\Scripts\python.exe -m pytest tests/test_gmail_intake.py tests/test_shadow_web_api.py tests/test_source_document.py -k "browser_pdf or prepare_session or run_report or attachment_file or index_renders_static_base_bootstrap or gmail_session_routes_flow" -q` -> `6 passed`
- `C:\Users\FA507\.codex\legalpdf_translate\tmp\stage3_e2e_venv\Scripts\python.exe -m pytest tests/test_gmail_intake.py tests/test_gmail_browser_service.py tests/test_browser_gmail_bridge.py -q` -> `23 passed`
- Live localhost validation on `127.0.0.1:8877`:
  - `GET /api/bootstrap/shell?mode=live&workspace=gmail-intake` -> `200` with `shell.ready=true`
  - browser shell HTML includes versioned static assets plus direct Gmail/translation report actions
  - `GET /static/vendor/pdfjs/pdf.mjs?v=6e823b2` -> `200`
  - `GET /static/vendor/pdfjs/pdf.worker.mjs?v=6e823b2` -> `200`
  - `POST /api/power-tools/diagnostics/run-report` with `browser_failure_context` -> `200`, `report_kind=browser_failure_report`, artifact written to `C:\Users\FA507\Downloads\power_tools\browser_failure_report_20260330_152303.md`
- Important live contract note:
  - the browser PDF loader now accepts both relative static roots (`/static/`) and the absolute bootstrap static root emitted by the live server (`http://127.0.0.1:8877/static/`), preventing the browser-managed PDF worker path from regressing under the real HTML bootstrap shape.
