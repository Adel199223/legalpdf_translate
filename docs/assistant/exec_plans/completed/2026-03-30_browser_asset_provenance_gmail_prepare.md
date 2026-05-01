# Rebuild Browser Asset Provenance so Gmail Prepare Uses the New Code

## Goal and non-goals
- Goal: make the browser app load the current JS module graph after local edits/restarts so Gmail `Prepare selected` cannot keep executing stale `browser_pdf.js`.
- Goal: add asset-version integrity checks across server bootstrap, client hydration, and extension handoff.
- Goal: preserve Gmail/browser failure reporting while making stale-asset failures explicit and recoverable.
- Non-goal: redesign Gmail handoff, translation startup, or browser-app architecture.
- Non-goal: introduce a full frontend bundler unless the versioned-static route proves impossible.

## Scope
- In scope:
  - runtime browser asset fingerprinting
  - versioned static route for the browser ES-module graph
  - HTML bootstrap, client marker, and shell payload asset-version propagation
  - extension-side stale-asset detection/reload behavior
  - Gmail/browser failure-report enrichment
  - targeted regression and live localhost validation
- Out of scope:
  - unrelated translation/auth/runtime fixes
  - packaging/release changes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical feature-branch override; approved-base floor preserved

## Interfaces/types/contracts affected
- Browser bootstrap HTML contract in `shadow_web/templates/index.html`
- Browser shell/runtime payloads from `shadow_web/app.py`
- Client-ready marker in `shadow_web/static/app.js`
- Extension hydration contract in `extensions/gmail_intake/background.js`
- Gmail/browser pre-run failure report context in `shadow_web/static/gmail.js`

## File-by-file implementation steps
1. `src/legalpdf_translate/shadow_web/app.py`
   - compute a runtime `asset_version` fingerprint from the browser static tree
   - add a versioned static asset route and propagate `asset_version` into HTML/bootstrap/shell payloads
2. `src/legalpdf_translate/shadow_web/templates/index.html`
   - load CSS and module entrypoint from the versioned static route
   - publish `assetVersion` and versioned `staticBasePath` in the bootstrap object
3. `src/legalpdf_translate/shadow_web/static/app.js` and `src/legalpdf_translate/shadow_web/static/bootstrap_hydration.js`
   - include `assetVersion` in the client-ready marker/dataset
   - detect server/client asset-version mismatches and classify them as stale browser assets
4. `extensions/gmail_intake/background.js`
   - require server/client asset-version agreement during hydration checks
   - reload the localhost tab once on stale-asset mismatch and fail explicitly if the mismatch persists
5. `src/legalpdf_translate/shadow_web/static/gmail.js`
   - include `asset_version` and stale-asset details in pre-run failure report context
6. `tests/test_shadow_web_api.py` and `tests/test_gmail_intake.py`
   - add regressions for asset fingerprinting, versioned static routing, bootstrap assetVersion emission, and extension stale-asset recovery/failure behavior

## Tests and acceptance criteria
- Browser bootstrap emits a runtime `assetVersion` and versioned static base.
- Versioned static route serves `app.js`, `gmail.js`, `browser_pdf.js`, `pdf.mjs`, and `pdf.worker.mjs`.
- Browser PDF worker URL resolves under the versioned static root and never to the doubled nested vendor path.
- Extension hydration succeeds when client/server asset versions match.
- Extension reloads once and succeeds when the client asset version is stale.
- Extension fails explicitly with stale-asset messaging if the mismatch persists after one reload.
- Live localhost app on `127.0.0.1:8877` reflects the new versioned asset contract after restart.

## Rollout and fallback
- Keep `/static/*` mounted for compatibility, but move browser-app HTML to the versioned static route.
- Treat stale-asset mismatch as recoverable once via reload, then explicit failure.
- Keep Gmail/browser failure report generation available even for stale-asset failures.

## Risks and mitigations
- Risk: versioned static routing could break browser imports or pdf.js worker loading.
  - Mitigation: route the full module graph through the same versioned base and cover `pdf.worker.mjs` explicitly in tests.
- Risk: stale existing tabs may keep old assets long enough to confuse users.
  - Mitigation: extension compares server/client asset versions and auto-reloads once.
- Risk: dirty worktree edits could still reuse an old cache key.
  - Mitigation: fingerprint runtime static files directly instead of relying on git SHA.

## Assumptions/defaults
- The browser app remains an unbundled local ES-module app.
- Runtime asset fingerprinting at server startup is sufficient; a full live file watcher is not required.
- A one-time automatic reload of the localhost app tab is acceptable when stale assets are detected.

## Outcome
- Completed.

## Validation
- `node --check` passed for:
  - `src/legalpdf_translate/shadow_web/static/browser_pdf.js`
  - `src/legalpdf_translate/shadow_web/static/app.js`
  - `src/legalpdf_translate/shadow_web/static/bootstrap_hydration.js`
  - `src/legalpdf_translate/shadow_web/static/gmail.js`
  - `extensions/gmail_intake/background.js`
- `tmp/stage3_e2e_venv/Scripts/python.exe -m pytest tests/test_gmail_intake.py -q`
  - `12 passed`
- `tmp/stage3_e2e_venv/Scripts/python.exe -m pytest tests/test_shadow_web_api.py -k "asset_version or versioned_static or index_renders_static_base_bootstrap or bootstrap_shell or browser_failure_report or browser_pdf_bundle_route" -q`
  - `4 passed`
- Live localhost verification on `127.0.0.1:8877`:
  - `/api/bootstrap/shell?mode=live&workspace=gmail-intake` returned `asset_version=33808f3d8f4d`, `ready=true`, `native_host_ready=true`
  - `/` returned `Cache-Control: no-store` and loaded CSS/app entrypoint from `/static-build/33808f3d8f4d/...`
  - `/static-build/33808f3d8f4d/browser_pdf.js` served the new `assetVersion`-aware worker resolver
  - `/static-build/33808f3d8f4d/vendor/pdfjs/pdf.worker.mjs` returned `200`
  - `/api/power-tools/diagnostics/run-report` generated a browser failure report that now includes `asset_version`
  - Replayed the real Gmail intake context for message/thread `19d0bf7e8dccffc0`, loaded the exact two-attachment message into `workspace=gmail-intake`, staged a browser PDF bundle for `sentença 305.pdf`, and `POST /api/gmail/prepare-session` returned `status=ok`
  - Started a live one-page translation from the prepared Gmail attachment and job `tx-c60d07fb7097` completed successfully with output `C:\Users\FA507\.codex\legalpdf_translate\tmp\assetprov_translate_output\sentença 305_EN_20260330_182113.docx`
