# Restore Reliable First-Open Gmail Handoff Hydration

## Goal
- Make the Gmail extension land on the fully hydrated browser app on the first open, without requiring a manual refresh and without regressing the existing cold-start, preview, translation, or Gmail finalization flows.

## Non-goals
- No new launch mechanism beyond the existing native-host/browser-app path.
- No workflow redesign for Gmail intake, translation, or finalization.
- No broad refactor of unrelated browser-app or Qt surfaces.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch: `feat/browser-gmail-autostart-repair`
- Base branch: `main`
- Base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch carrying the currently approved browser Gmail handoff floor

## Interfaces and contracts
- Add a browser-page client-ready contract exposed on the opened localhost tab:
  - `window.LEGALPDF_BROWSER_CLIENT_READY`
  - `document.body.dataset.clientReady`
  - related dataset fields for workspace, runtime mode, active view, and hydration status
- Keep `/api/bootstrap` and `/api/bootstrap/shell` route shapes additive-only.
- Add only build-SHA cache-busting query params to the static asset URLs in the browser shell template.

## Implementation outline
1. Browser shell/bootstrap hardening
   - Version `style.css` and `app.js` URLs in the browser shell template by build SHA.
   - Split first-load startup into staged shell-first bootstrap:
     - fast `/api/bootstrap/shell`
     - bounded retries of full `/api/bootstrap`
     - explicit warmup state while hydration is pending
   - Keep route hash/workspace stable and publish/clear the client-ready marker only after full render success.
2. Extension-side hydration enforcement
   - Extend the background handoff flow to inspect the client-ready marker on the localhost tab after server-side workspace readiness passes.
   - If the workspace is ready server-side but client hydration is missing, reload the exact localhost tab once and retry the client-ready check.
   - Fail with a dedicated hydration reason if the browser tab still does not hydrate after the one reload.
3. Regression and live verification
   - Extend browser API/template tests for staged bootstrap and cache-busted asset URLs.
   - Extend extension/background coverage for client-ready detection, one-reload recovery, and no-loop behavior.
   - Re-run focused Gmail/browser/bootstrap suites and repeat the live cold-start acceptance path from extension click through Gmail intake hydration.

## Tests and acceptance criteria
- Browser bootstrap regressions:
  - initial `gmail-intake` load hits shell bootstrap first, then hydrates through bounded `/api/bootstrap` retries
  - client-ready marker is absent before hydration, present after success, and cleared on failure
  - template serves build-versioned static asset URLs
- Extension regressions:
  - server ready + client ready => success with no reload
  - server ready + client not ready initially => one reload => success
  - server ready + client never ready => one reload only => targeted hydration failure
  - native-host unavailable, bridge integrity failure, and workspace warming flows stay unchanged
- Windows live acceptance:
  - true cold state on `8877` and `8765`
  - reload extension and Gmail page
  - click extension
  - browser app opens straight into the styled `gmail-intake` UI without manual refresh
  - inline preview still works
  - translation auth/OCR tests still pass
  - one-page translation still succeeds
  - save-row and Gmail draft finalization still succeed

## Rollout and fallback
- Keep the existing server-side shell/bootstrap endpoints intact while tightening client hydration checks.
- Limit automated recovery to one reload of the exact localhost tab per handoff key; no reopen loops and no extra windows.
- If hydration still fails, surface a precise hydration failure instead of claiming success or falling back to misleading bridge errors.

## Risks and mitigations
- Risk: staged bootstrap could leave the shell permanently warming.
  - Mitigation: bounded retries, explicit failure state, and focused regression coverage for failure exit paths.
- Risk: extension-side client probing could destabilize existing success cases.
  - Mitigation: preserve current server-side readiness checks first, then layer the client-ready proof only after them.
- Risk: stale asset caches could continue to mask fixes after reloads.
  - Mitigation: build-SHA query busting on the template asset URLs.

## Assumptions and defaults
- Default recovery behavior is one automatic reload of the exact localhost browser-app tab when server readiness succeeds but client hydration does not.
- The current failure is treated as a first-load hydration/cache race unless implementation verification proves a distinct browser-side interference path.
