# Restore Reliable First-Open Gmail Handoff Hydration

## Goal
- Make the Gmail extension cold/open path land on the fully hydrated browser app UI on the first load, without requiring a manual refresh.

## Why this pass exists
- The live server, static assets, and shell/bootstrap routes are healthy.
- The current failure is the last-mile readiness contract:
  - the browser app still relies on a single heavy first-load bootstrap,
  - the extension treats server-side workspace readiness as success,
  - neither side proves that the opened localhost tab actually hydrated into the real app UI.

## Implementation outline
1. Add cache-busted static asset URLs to the browser shell template so stale Edge session assets cannot survive extension/server reloads.
2. Harden browser-side first-load bootstrap:
   - shell-first warmup,
   - bounded full-bootstrap retries,
   - explicit client-ready marker lifecycle,
   - stable `gmail-intake` route preservation.
3. Harden extension-side success criteria:
   - keep current native-host and server readiness checks,
   - add localhost-tab hydration inspection via `chrome.scripting.executeScript`,
   - perform one auto-reload of the exact localhost tab if the tab is still shell-only after server readiness.
4. Add regressions for:
   - template asset versioning,
   - client-ready marker lifecycle,
   - extension hydration success/fallback/failure paths,
   - no-loop reload behavior.
5. Re-run focused tests and perform live localhost acceptance on the same Gmail handoff path the user is using.

## Acceptance target
- Reload extension, reload the Gmail email page, click the extension, and land directly on the styled `gmail-intake` UI with no manual refresh.
- Preserve existing preview, translation, save-row, and Gmail draft finalization behavior.

## Implemented
- Added build-SHA cache busting and an initial warming marker to the browser shell template.
- Added a staged shell-first bootstrap helper for first-load hydration, plus browser-side client-ready marker updates.
- Added extension-side client hydration inspection and a one-reload recovery path before success is declared.
- Added regression coverage for the HTML shell contract, staged bootstrap helper behavior, and extension hydration success/failure paths.

## Executed validations and outcomes
- `node --check` passed for:
  - `src/legalpdf_translate/shadow_web/static/app.js`
  - `src/legalpdf_translate/shadow_web/static/bootstrap_hydration.js`
  - `extensions/gmail_intake/background.js`
- Direct module probes passed:
  - staged bootstrap helper returns the expected warming/default route state and bounded retry sequence for `gmail-intake`
  - extension background logic succeeds after exactly one reload when the client marker warms then becomes ready
  - extension background logic fails with `client_shell_not_hydrated` after exactly one reload when the client marker never becomes ready
- Live localhost checks passed on the running browser app:
  - `/` serves the versioned `style.css` / `app.js` URLs and the `LEGALPDF_BROWSER_CLIENT_READY` shell marker
  - `/api/bootstrap/shell?mode=live&workspace=gmail-intake` returns `status=ok`, `shell.ready=true`, and `native_host_ready=true`
  - the active unpacked Edge extension copy at `C:\Users\FA507\.codex\legalpdf_translate_gmail_auto_launch\extensions\gmail_intake\background.js` matches the patched repo `background.js`
- Environment note:
  - local `pytest` execution is currently blocked by a damaged Python environment on this machine (`pygments.lexers._mapping` missing in the test runner environment and `typing_extensions` missing from `.venv311`), so validation used direct probes against the changed modules and the live localhost app instead of the broken test runner.
