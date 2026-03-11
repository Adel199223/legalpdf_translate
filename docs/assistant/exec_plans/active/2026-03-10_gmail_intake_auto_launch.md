# Gmail Intake Auto-Launch

## Goal and non-goals
- Goal: let the Gmail extension start LegalPDF Translate automatically when the Gmail bridge is configured but the app is not already running, while keeping the same one-click Gmail intake flow.
- Non-goals: browser-side process launching, localhost payload changes, editable launcher settings, or packaged-app-first behavior.

## Scope (in/out)
- In:
  - native host `prepare_gmail_intake` auto-launch path
  - launch-target derivation from the current repo checkout
  - extension failure mapping and diagnostics updates
  - Gmail extension README and touched user/knowledge docs
  - targeted native-host / extension tests
- Out:
  - app-side Gmail bridge UI redesign
  - release/publish/install workflow changes beyond whatever is needed to refresh the local native host binary
  - Chrome-specific behavior beyond the existing shared extension surface

## Worktree provenance
- worktree path: `c:\Users\FA507\.codex\legalpdf_translate_gmail_auto_launch`
- branch name: `codex/gmail-intake-auto-launch`
- base branch: `feat/gmail-interpretation-honorarios`
- base SHA: `2fb140b0584479ee737638674fbc21f588f4d842`
- target integration branch: `feat/gmail-interpretation-honorarios`
- canonical build status: noncanonical isolated feature worktree; approved-base floor still present via the current source tree lineage

## Interfaces/types/contracts affected
- Native host `prepare_gmail_intake` response grows launch diagnostics:
  - `launched: bool`
  - `autoLaunchReady: bool`
  - `launchTarget?: string`
- Native host behavior contract:
  - request-focus click path may auto-launch the app when the bridge is missing/not running
  - diagnostics path (`requestFocus=false`) never auto-launches
- Extension behavior contract:
  - one click still performs native-host prepare first and localhost POST second
  - when auto-launch is possible, the same click completes without requiring a retry
- Launcher/runtime contract:
  - when the target worktree has no local `.venv311`, the launcher may reuse the canonical worktree venv
  - the launched process still runs the target checkout by setting `PYTHONPATH=<worktree>\\src`

## Implementation steps
- `src/legalpdf_translate/gmail_focus_host.py`
  - derive the repo worktree from the registered host/runtime location
  - add an internal auto-launch helper that runs `tooling/launch_qt_build.py --worktree <repo> --allow-noncanonical`
  - attempt auto-launch only for missing/not-running bridge states and only on request-focus calls
  - poll bridge readiness after launch, then continue with the normal focus/token response
- `extensions/gmail_intake/background.js`
  - add failure messages for auto-launch target/timeout errors
  - preserve current native-host-first click flow
- `extensions/gmail_intake/options.js` and `extensions/gmail_intake/options.html`
  - surface auto-launch readiness and launch target in diagnostics
  - keep diagnostics refresh non-launching
- Docs
  - update Gmail extension README and touched user/knowledge docs so they no longer require manual keep-open/token-copy behavior for normal use

## Tests and acceptance criteria
- `tests/test_gmail_focus_host.py`
  - bridge already ready -> no launch attempt
  - bridge missing/not running + launch target ready -> launch + wait + success
  - disabled bridge / blank token / invalid port -> no launch
  - missing launch target / launch timeout -> specific failure reason
  - diagnostics path reports auto-launch readiness without launching
- `tests/test_gmail_intake.py`
  - new background failure strings exist
  - options page exposes auto-launch readiness/target text
- Validation:
  - `.\.venv311\Scripts\python.exe -m pytest tests\test_gmail_focus_host.py tests\test_gmail_intake.py -q`
  - `dart run tooling/validate_agent_docs.dart`

## Rollout and fallback
- After implementation, refresh the local native host binary/registration so the live extension uses the new host behavior.
- If auto-launch cannot resolve a valid repo target, the extension should fail clearly and leave the existing manual app-open path usable.

## Progress / evidence
- Implemented:
  - native-host auto-launch path in `src/legalpdf_translate/gmail_focus_host.py`
  - worktree-aware Python discovery plus `PYTHONPATH` launch wiring in `tooling/launch_qt_build.py`
  - extension diagnostics/failure messaging updates in `extensions/gmail_intake/background.js`, `options.js`, and `options.html`
  - Gmail extension/user docs sync for the new auto-launch behavior
- Validation run:
  - `.\.venv311\Scripts\python.exe -m pytest tests\test_gmail_focus_host.py tests\test_gmail_intake.py tests\test_launch_qt_build.py -q` -> `35 passed`
  - `dart run tooling/validate_agent_docs.dart` -> `PASS`
- Local runtime refresh completed:
  - rebuilt `dist\legalpdf_translate\LegalPDFGmailFocusHost.exe` from this worktree with PyInstaller
  - re-registered the Edge native host manifest to point at the rebuilt EXE
  - current live `prepare_gmail_intake(request_focus=False)` reports `autoLaunchReady=true`, `launchTarget=C:\Users\FA507\.codex\legalpdf_translate_gmail_auto_launch`, `bridgePort=8765`

## Risks and mitigations
- Risk: diagnostics accidentally launch the app.
  - Mitigation: auto-launch only when `requestFocus=true`.
- Risk: launch helper path resolves to the wrong checkout.
  - Mitigation: derive from the native host runtime/repo layout and expose the resolved target in diagnostics.
- Risk: launching a second app instance while another process owns the port.
  - Mitigation: only auto-launch for missing/not-running reasons, never for owner-mismatch conditions.

## Assumptions/defaults
- One click should complete when auto-launch is possible.
- The current repo checkout is the default launch target.
- No new user-editable launcher setting is added.
