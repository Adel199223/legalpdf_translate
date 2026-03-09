# Gmail Intake Auto-Config and Extension Identity Repair

## Goal and non-goals
- Goal:
  - Remove the extension's manual token-copy dependency by sourcing Gmail bridge port/token from the Windows Edge native host during the same click path that requests focus.
  - Convert the extension options page into diagnostics-first UI so setup problems are visible without exposing the raw bridge token.
  - Keep duplicate unpacked extension IDs as detectable setup state, not runtime behavior.
- Non-goals:
  - No Chrome support in v1.
  - No auto-launch of the LegalPDF Translate app when it is closed.
  - No destructive edits to Edge `Secure Preferences` or profile records.

## Scope (in/out)
- In:
  - native host `prepare_gmail_intake` action and response contract
  - extension background flow updates for native-host auto-config with legacy storage fallback
  - extension options page diagnostics redesign
  - repair/setup tooling for native-host registration, sync, and duplicate-ID reporting
  - targeted tests covering host, extension, and tooling
- Out:
  - browser-profile cleanup automation
  - any change to the localhost `/gmail-intake` request payload
  - non-Windows foreground behavior

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `80a7312657be2ec27716edd94b7ea82f267456c4`
- Target integration branch: `feat/ai-docs-bootstrap`
- Canonical build status: canonical worktree and canonical branch per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Native host request/response contract:
  - existing: `{"action":"focus_app","bridgePort":<int>}`
  - new: `{"action":"prepare_gmail_intake"}`
  - new response: `{"ok":<bool>,"bridgePort"?:<int>,"bridgeToken"?:<string>,"focused":<bool>,"flashed":<bool>,"reason":<string>}`
- Extension config resolution contract:
  - primary source becomes native host response
  - `chrome.storage.local` remains a legacy fallback only
- Extension options page contract:
  - diagnostics-first display
  - token presence yes/no only
  - current extension ID and native-host availability shown
- Setup tooling output contract:
  - report active unpacked extension IDs and stale/orphan IDs
  - sync explicit or discovered live unpacked extension directories

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_focus_host.py`
  - add `prepare_gmail_intake` handling, settings validation, and shared response shaping
  - keep `focus_app` compatibility intact
- `extensions/gmail_intake/background.js`
  - switch click path to native-host config + focus first
  - fall back to stored token/port only when native host is unavailable
  - improve setup error messages
- `extensions/gmail_intake/options.js`
  - replace manual token editing with diagnostics-first state loading
- `extensions/gmail_intake/options.html`
  - redesign the page around diagnostics and legacy fallback disclosure
- `scripts/register_edge_native_host.ps1`
  - keep registration path aligned with the new diagnostics/setup flow
- `scripts/sync_loaded_gmail_extension.ps1`
  - add reporting for discovered extension IDs and stale duplicates while preserving safe sync behavior
- `tests/test_gmail_focus_host.py`
  - cover `prepare_gmail_intake`, disabled bridge, blank token, missing runtime metadata, and origin discovery
- `tests/test_gmail_intake.py`
  - update extension contract assertions for native-host-first config and diagnostics UI markers
- `tests/test_windows_shortcut_scripts.py`
  - cover sync/reporting and registration script markers as needed
- `extensions/gmail_intake/README.md`
  - update setup instructions to reflect auto-config and diagnostics-first behavior if still unsynced after implementation

## Tests and acceptance criteria
- Native host tests:
  - valid settings return `bridgePort`, `bridgeToken`, and focus diagnostics
  - disabled bridge, blank token, invalid port, missing runtime metadata, and app-not-running paths return `ok: false` with specific reasons
- Extension tests:
  - native host request happens before localhost POST
  - missing native host falls back to stored config if present
  - missing native host plus missing stored config shows setup-specific guidance
  - options page no longer requires raw token entry in normal use
- Tooling tests:
  - sync helper reports active/stale IDs
  - registration helper still targets the expected Edge manifest/registry path
- Acceptance:
  - clicking the live `afck...` extension no longer shows `Bridge token is missing in extension options.` when the app is configured
  - the app comes forward or flashes, and the localhost POST still succeeds

## Rollout and fallback
- Native-host auto-config becomes the default path immediately.
- Legacy extension storage remains as a fallback only when native messaging is unavailable.
- If runtime metadata is stale or the app is not listening, the extension reports a precise setup/runtime reason instead of a generic token error.

## Risks and mitigations
- Risk: native host returns a token while runtime metadata is stale.
  - Mitigation: validate settings and runtime metadata together and return specific reasons for stale or missing app state.
- Risk: duplicate unpacked extension IDs create user confusion after reloads.
  - Mitigation: surface current extension ID in diagnostics and report duplicate IDs in repair tooling.
- Risk: fallback storage path masks native-host setup issues.
  - Mitigation: keep fallback only for native-host unavailability and report degraded mode explicitly.

## Assumptions/defaults
- Windows + Edge remain the only supported native-host path.
- App settings remain the authoritative source for Gmail bridge configuration.
- Raw bridge tokens should never be displayed in extension diagnostics.
- Existing foreground activation helpers remain the focus implementation used by the native host.

## Validation log
- Implemented:
  - `src/legalpdf_translate/gmail_focus.py`
    - split bridge-owner validation from focus attempts
    - added legacy listener-owner recovery when the active app bridge predates runtime metadata writes but still owns the configured localhost port and exposes a `LegalPDF Translate` window
  - `src/legalpdf_translate/gmail_focus_host.py`
    - added `prepare_gmail_intake`
    - added optional `requestFocus` / `includeToken` flags
    - added unpacked-extension reporting helpers and CLI output-to-file support for Windows setup scripts
  - `extensions/gmail_intake/background.js`
    - switched the normal click path to native-host prepare + focus + POST
    - kept `chrome.storage.local` as legacy fallback only when native messaging is unavailable
  - `extensions/gmail_intake/options.js`
    - replaced manual token copy/paste UI logic with diagnostics-first status loading
  - `extensions/gmail_intake/options.html`
    - redesigned the options page into diagnostics-first UI with hidden raw token behavior
  - `extensions/gmail_intake/README.md`
    - updated setup/use/failure instructions for auto-config behavior
  - `scripts/sync_loaded_gmail_extension.ps1`
    - added active/stale unpacked-ID reporting and Windows-safe report-file handoff from the native-host module
  - `tests/test_gmail_focus.py`
    - added legacy listener-owner recovery coverage
  - `tests/test_gmail_focus_host.py`
    - added `prepare_gmail_intake` and unpacked-ID report coverage
  - `tests/test_gmail_intake.py`
    - updated extension contract assertions for native-host-first config and diagnostics-first options UI
  - `tests/test_windows_shortcut_scripts.py`
    - updated sync-helper marker coverage
- Executed validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_focus.py tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_windows_shortcut_scripts.py` -> PASS (`41 passed`)
  - `python3 -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m PyInstaller build/pyinstaller_qt.spec --noconfirm --clean` -> PASS
  - `./.venv311/Scripts/python.exe -m legalpdf_translate.gmail_focus_host --register --host-executable 'C:\Users\FA507\.codex\legalpdf_translate\dist\legalpdf_translate\LegalPDFGmailFocusHost.exe'` -> PASS
  - Direct host-module probe:
    - `prepare_gmail_intake(request_focus=False, include_token=False)` -> `{"ok": true, "bridgePort": 8765, "bridgeTokenPresent": true, "reason": "legacy_bridge_owner_ready"}`
  - Direct built-host EXE wire probe:
    - request: `{"action":"prepare_gmail_intake","requestFocus":false,"includeToken":false}`
    - response: `{"ok": true, "focused": false, "flashed": false, "bridgeTokenPresent": true, "bridgePort": 8765, "reason": "legacy_bridge_owner_ready"}`
- Live machine state repaired:
  - synced the actual unpacked Edge extension directory at `C:\Users\FA507\.codex\legalpdf_translate_gmail_intake\extensions\gmail_intake`
  - rebuilt and registered the native host at `C:\Users\FA507\.codex\legalpdf_translate\dist\legalpdf_translate\LegalPDFGmailFocusHost.exe`
  - confirmed the registered manifest allows both the stable `afck...` ID and the stale `hgc...` unpacked ID
  - confirmed the current localhost listener on port `8765` belongs to a running `LegalPDF Translate` window from a legacy `feat/gmail-intake...` worktree, and the new host now recovers that case without requiring a manual token in extension storage
