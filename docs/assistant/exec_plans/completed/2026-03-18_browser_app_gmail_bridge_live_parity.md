# Browser-App Gmail Bridge Ownership for Live Parity

## Goal and non-goals
- Goal: make the browser app the primary real Gmail bridge owner for the live desktop data path while keeping `shadow` mode fully isolated.
- Goal: let the native host and real Gmail extension recognize browser-owned bridge readiness without requiring a visible Qt window.
- Goal: route successful bridge intake directly into a fixed live browser workspace so the browser app opens in a ready Gmail review state.
- Goal: make Qt back off cleanly when a healthy browser-owned live bridge already exists.
- Non-goal: forcibly steal or kill an already healthy Qt-owned bridge.
- Non-goal: enable a real Gmail bridge for isolated shadow mode.

## Scope (in/out)
- In scope:
  - browser-server lifecycle management for the live Gmail bridge
  - additive bridge runtime metadata and native-host response fields for browser ownership
  - browser extension handoff changes so successful intake opens/focuses the browser app
  - Qt coexistence/backoff for browser-owned live bridge sessions
  - targeted regression tests and browser/host validation
- Out of scope:
  - replacing the real Gmail extension with a simulator
  - public or remote web deployment
  - destructive takeover of an existing Qt-owned bridge

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Current HEAD: `5c9842e3fbec`
- Target integration branch: `main`

## Interfaces/types/contracts affected
- `src/legalpdf_translate/browser_gmail_bridge.py`
- `src/legalpdf_translate/gmail_browser_service.py`
- `src/legalpdf_translate/gmail_focus.py`
- `src/legalpdf_translate/gmail_focus_host.py`
- `src/legalpdf_translate/browser_app_service.py`
- `src/legalpdf_translate/shadow_web/app.py`
- `src/legalpdf_translate/qt_gui/window_controller.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- `extensions/gmail_intake/background.js`
- `extensions/gmail_intake/options.js`
- `tests/test_gmail_focus.py`
- `tests/test_gmail_focus_host.py`
- `tests/test_shadow_web_api.py`
- `tests/test_shadow_runtime_service.py`
- `tests/test_qt_app_state.py`

## File-by-file implementation steps
1. Add a browser live-bridge manager that reads live settings, starts/stops `LocalGmailIntakeBridge`, writes browser-owned runtime metadata, and seeds a fixed live Gmail workspace.
2. Extend `GmailBrowserSessionManager` with a direct bridge-intake method that stores loaded Gmail message state for `mode=live`, `workspace=gmail-intake`.
3. Extend Gmail bridge runtime metadata and validation results with additive browser-owner fields and relax validation so browser-owned sessions do not require a visible Qt window.
4. Update the native host prepare flow so it prefers browser launch, returns browser-owner context, and treats browser-owned bridge readiness as healthy without foreground-window focus.
5. Update the extension background/options flows so successful handoff opens or focuses the browser-app URL and diagnostics surface browser-owned readiness cleanly.
6. Update browser bootstrap/extension diagnostics to expose bridge owner provenance.
7. Update Qt bridge sync logic so Qt backs off when a healthy browser-owned bridge already owns the live port.
8. Revalidate with targeted Python tests, JS syntax checks, and a live browser/native-host smoke on the main preview port.

## Tests and acceptance criteria
- The browser server starts the live bridge from live settings when enabled and clears browser-owned runtime metadata on shutdown.
- `validate_bridge_owner()` accepts browser-owned runtime metadata without `window_not_found`.
- `prepare_gmail_intake()` returns additive browser-owner fields (`ui_owner`, `browser_url`, `workspace_id`, `runtime_mode`) and prefers browser launch before Qt fallback.
- A successful extension-style POST can seed the `gmail-intake` live browser workspace without a manual reload.
- Qt bridge sync backs off cleanly when browser-owned metadata already validates as healthy.
- Targeted tests, syntax checks, and a live smoke on `127.0.0.1:8877` pass cleanly.

## Rollout and fallback
- Keep the default browser preview on `127.0.0.1:8877`.
- If browser-owned bridge startup regresses, fall back to the current Qt-owned bridge path by disabling browser bridge sync logic while preserving additive runtime metadata support.

## Risks and mitigations
- Risk: browser startup could clear or override a healthy Qt-owned bridge.
  - Mitigation: validate existing live ownership first and back off instead of preempting.
- Risk: extension flow opens a stale browser tab before intake succeeds.
  - Mitigation: only open/focus the browser app after a successful `/gmail-intake` POST.
- Risk: native-host auto-launch breaks current Qt fallback behavior.
  - Mitigation: keep Qt fallback intact when browser launch is unavailable or fails to produce a healthy bridge owner.

## Assumptions/defaults
- Browser app is the primary real bridge owner when available.
- `shadow` mode remains isolated and never runs a real Gmail bridge.
- The canonical browser handoff workspace is `gmail-intake`.
- No destructive takeover of a healthy Qt-owned bridge is allowed.
