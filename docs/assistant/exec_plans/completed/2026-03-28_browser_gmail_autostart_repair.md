# Browser Gmail Autostart Repair

## Goal and non-goals
- Goal: restore browser-app auto-open from the Gmail extension when the app is closed.
- Goal: stop isolated pytest/temp-APPDATA runs from rewriting the real Edge native-host registry.
- Goal: preserve browser-first launch semantics and keep desktop fallback only as a real fallback.
- Non-goal: redesign the Gmail intake workflow or browser UI.
- Non-goal: remove extension provenance checks or desktop fallback support entirely.

## Scope (in/out)
- In scope:
  - native-host registration hardening for real vs isolated runtimes
  - browser/Qt startup registration guardrails
  - Gmail extension fallback behavior when native messaging is unavailable
  - focused regression coverage for registry contamination and degraded bridge fallback
- Out of scope:
  - broader Gmail UX changes
  - installer/release changes beyond existing runtime registration paths
  - unrelated browser-shell or translation workflow changes

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-gmail-autostart-repair`
- base branch: `main`
- base SHA: `6e823b23f3f800254ec328e11a061f7f11c5d500`
- target integration branch: `main`
- canonical build status: canonical worktree per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- `prepare_gmail_intake()` browser-first launch contract
- Gmail extension toolbar-click fallback contract in `background.js`
- automatic native-host registration behavior for browser/Qt startup
- additive diagnostics only for stale native-host registration / native-host unavailability

## File-by-file implementation steps
1. Harden native-host registration helpers and startup callers so real launches still repair the stable app-data wrapper, while pytest/temp-isolated runtimes skip real registry writes.
2. Update the Gmail extension background fallback so native-host failure no longer blindly posts to stored bridge config unless a live bridge is already reachable.
3. Keep browser-first auto-launch intact and preserve desktop fallback only for genuine browser-launch unavailability.
4. Add focused tests for:
   - registration skip behavior in isolated runtimes
   - browser/Qt real registration behavior
   - native-host unavailable toolbar-click behavior with and without a reachable live bridge

## Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_browser_gmail_bridge.py`
- Acceptance criteria:
  - with the app closed, a valid extension click can auto-start the browser app
  - native-host unavailability without a live bridge surfaces a repair message instead of a dead-port message
  - isolated pytest/temp-APPDATA runs do not leave the Edge registry pointing at temp manifests
  - browser-first behavior remains the normal green path

## Rollout and fallback
- Keep the fix scoped to runtime registration, extension fallback, and focused tests.
- Treat the current machine registry state as poisoned legacy state; one manual app launch after the fix is an acceptable repair step.
- If browser autostart remains unavailable after repair, keep existing desktop fallback behavior.

## Risks and mitigations
- Risk: over-broad registration skipping could prevent real launches from repairing the native host.
  - Mitigation: gate only isolated/test runtimes and keep normal live/browser/Qt launches registering normally.
- Risk: removing blind stored-config fallback could break already-running flows when native messaging is temporarily unavailable.
  - Mitigation: preserve degraded fallback only when a live bridge is already reachable.
- Risk: browser-first changes could regress current fallback semantics.
  - Mitigation: keep `prepare_gmail_intake()` launch order intact and cover both browser-ready and browser-unavailable cases.

## Assumptions/defaults
- Browser-first behavior remains the primary contract.
- Desktop fallback remains supported but secondary.
- No broad docs sync is required unless implementation changes user-facing diagnostics materially.

## Execution notes
- Added auto-registration guardrails so pytest/isolation runtimes skip real Edge native-host registration, while explicit/manual registration and real app launches still target the stable app-data wrapper.
- Updated browser and Qt startup callers to use the guarded registration path without changing normal live behavior.
- Tightened Gmail extension degraded fallback so stored bridge config is used only when the live bridge is already reachable; otherwise the extension now shows a repair-focused native-host message instead of blindly posting to a dead port.
- Preserved the browser-first `prepare_gmail_intake()` launch path and verified it still autostarts the browser app when bridge ownership metadata is stale.

## Validation outcomes
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_browser_gmail_bridge.py` -> passed (`40 passed`)
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_qt_app_state.py -k "test_gmail_intake_bridge_starts_when_enabled or test_gmail_intake_bridge_skips_native_host_registration_in_pytest_runtime"` -> passed (`2 passed`)
- `.\\.venv311\\Scripts\\python.exe -m legalpdf_translate.gmail_focus_host --register` -> rewrote the Edge native-host registration to `C:\\Users\\FA507\\AppData\\Roaming\\LegalPDFTranslate\\native_messaging\\com.legalpdf.gmail_focus.edge.json`
- Windows host smoke:
  - `prepare_gmail_intake(base_dir=app_data_dir(), request_focus=True, include_token=False)` -> `ok=true`, `launched=true`, `ui_owner=browser_app`
  - `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake` -> HTTP `200`
  - `http://127.0.0.1:8765/gmail-intake` -> HTTP `405` on `GET`, confirming the bridge listener is live
  - `validate_bridge_owner(8765, app_data_dir())` -> `bridge_owner_ready` with `owner_kind=browser_app`
