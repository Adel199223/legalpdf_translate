# Gmail Intake Foreground Activation

## Goal and non-goals
- Goal:
  - Add a staged Gmail-intake foreground activation path that first improves app-side window attention, then adds an Edge native-messaging focus helper, then closes with Windows same-host validation.
- Non-goals:
  - No Chrome support in v1.
  - No Gmail intake queueing while a translation is already running.
  - No replacement of the existing localhost Gmail intake POST contract.

## Scope (in/out)
- In:
  - Stage 1 app-side attention helper and bridge runtime metadata.
  - Stage 2 Edge native-messaging focus helper, extension call path, packaging, and installer registration.
  - Stage 3 Windows canonical-build smoke validation and final evidence packet.
- Out:
  - Chrome native-host registration.
  - Any redesign of the Gmail fetch/review/translation workflow semantics.

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `80a7312657be2ec27716edd94b7ea82f267456c4`
- Target integration branch: `feat/ai-docs-bootstrap`
- Canonical build status: canonical worktree and canonical branch per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- New app-side foreground/attention helper contract for Windows window restore, focus attempt, and flash fallback.
- New app-owned Gmail intake bridge runtime metadata file contract:
  - path under app data
  - `port`
  - `pid`
  - `window_title`
  - `build_identity`
  - `updated_at`
  - `running`
- Future Stage 2 native host request/response contract:
  - request: `{"action":"focus_app","bridgePort":<int>}`
  - response: `{"ok":<bool>,"focused":<bool>,"flashed":<bool>,"reason":<string>}`

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_focus.py`
  - Add Windows attention helper and bridge runtime metadata read/write helpers.
- `src/legalpdf_translate/qt_gui/app_window.py`
  - Stage 1: invoke the attention helper on Gmail intake receipt, busy blocked intake, and before the review dialog opens.
  - Stage 1: write/refresh bridge runtime metadata when the localhost bridge is active and clear it when this window stops the bridge.
  - Stage 2: wire runtime metadata into the native focus helper compatibility path.
- `extensions/gmail_intake/background.js`
  - Stage 2: call Edge native messaging before the localhost POST and surface degraded-focus warnings when unavailable.
- `extensions/gmail_intake/manifest.json`
  - Stage 2: add `nativeMessaging` permission and stable manifest `key`.
- `installer/legalpdf_translate.iss`
  - Stage 2: install the native host manifest and per-user registry entry.
- `build/pyinstaller_qt.spec`
  - Stage 2: ship the native host as a second executable.
- `tests/test_gmail_focus.py`
  - Add focused unit coverage for the Stage 1 helper and metadata helpers.
- `tests/test_qt_app_state.py`
  - Extend Gmail intake tests for attention requests and runtime metadata lifecycle.
- `tests/test_gmail_intake.py`
  - Stage 2: extend extension/native-host marker coverage as needed.
- `tests/test_pyinstaller_specs.py`
  - Stage 2: verify second executable packaging markers.

## Tests and acceptance criteria
- Stage 1:
  - unit tests for focus success, blocked-focus flash fallback, and non-Windows no-op
  - Qt app tests for idle intake attention, busy blocked intake attention, and review-dialog pre-attention
  - metadata file create/refresh/clear coverage for the active localhost bridge
- Stage 2:
  - native-host framing and metadata validation tests
  - extension tests that native messaging happens before localhost POST
  - packaging and installer coverage for the host executable and Edge registration
- Stage 3:
  - Windows same-host smoke on the canonical build with verified listener ownership, minimized restore, and review dialog visibility

## Rollout and fallback
- Stage 1 ships app-side attention only and stops for review.
- Stage 2 adds the reliable Edge focus lane without changing the existing Gmail intake POST payload.
- If Windows still blocks actual foreground after Stage 1, taskbar flash remains the fallback signal until Stage 2 is approved and completed.

## Risks and mitigations
- Risk: app-side `SetForegroundWindow` is not always allowed by Windows.
  - Mitigation: flash fallback in Stage 1, native-messaging helper in Stage 2.
- Risk: bridge metadata could be cleared by the wrong window during a port-conflict scenario.
  - Mitigation: only clear metadata when this window stops a bridge instance it owns.
- Risk: multiple visible worktrees/windows could make focus ambiguous.
  - Mitigation: persist build identity in runtime metadata and keep canonical-build validation in Stage 3.

## Assumptions/defaults
- Windows-only focus behavior is acceptable for this feature.
- Busy-case behavior is `front + explain`.
- The localhost bridge remains the authoritative Gmail context transport.
- The native host will be Edge-first and per-user installed.
- Stage gates are mandatory:
  - stop after Stage 1 and require `NEXT_STAGE_2`
  - stop after Stage 2 and require `NEXT_STAGE_3`

## Validation log
- Stage 1 implemented:
  - added `src/legalpdf_translate/gmail_focus.py`
  - updated `src/legalpdf_translate/qt_gui/app_window.py`
  - added/updated targeted tests in `tests/test_gmail_focus.py` and `tests/test_qt_app_state.py`
- Stage 2 implemented:
  - added `src/legalpdf_translate/gmail_focus_host.py`
  - updated `extensions/gmail_intake/background.js` and `extensions/gmail_intake/manifest.json`
  - updated `build/pyinstaller_qt.spec`, `installer/legalpdf_translate.iss`, and `scripts/build_qt.ps1`
  - added/updated targeted tests in `tests/test_gmail_focus.py`, `tests/test_gmail_focus_host.py`, `tests/test_gmail_intake.py`, `tests/test_pyinstaller_specs.py`, `tests/test_windows_shortcut_scripts.py`, and `tests/test_installer_native_host.py`
- Stage 3 hardening:
  - updated `src/legalpdf_translate/gmail_focus.py` so bridge-owner PID validation uses the Windows TCP ownership table first, then falls back to `netstat.exe` with a short retry window
  - extended `tests/test_gmail_focus.py` to cover the TCP-table-first path and the retry/fallback path
- Executed validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_focus.py` -> PASS (`4 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py -k "gmail_intake_bridge_starts_when_enabled or gmail_intake_bridge_restarts_and_stops_with_settings_changes or gmail_intake_bridge_stops_on_window_close or gmail_intake_bridge_runtime_metadata_is_written_and_cleared or gmail_intake_acceptance_updates_visible_ui_without_starting_translation or gmail_intake_acceptance_skips_message_load_while_busy or open_gmail_batch_review_dialog_takes_preview_cache_transfer"` -> PASS (`7 passed, 94 deselected`)
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_intake.py` -> PASS (`7 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_focus.py tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py tests/test_installer_native_host.py` -> PASS (`28 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_focus.py tests/test_gmail_focus_host.py` -> PASS (`14 passed`)
  - `python3 -m compileall src tests` -> PASS
  - `dart run tooling/validate_agent_docs.dart` -> PASS
- Stage boundary:
  - Stage 1 complete
  - Stage 2 complete
  - Stage 3 complete
- Stage 3 live evidence:
  - rebuilt the canonical-worktree Windows bundle into `tmp/stage3_dist` with `./.venv311/Scripts/python.exe -m PyInstaller build/pyinstaller_qt.spec --noconfirm --clean --distpath tmp/stage3_dist --workpath tmp/stage3_build` -> PASS
  - ran the Windows same-host smoke harness with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tmp/stage3_run_smoke.ps1` -> PASS
  - smoke report: `tmp/stage3_smoke_report.json`
    - runtime metadata matched the live app PID and configured bridge port
    - native host response: `{"ok": true, "focused": true, "flashed": false, "reason": "foreground_set"}`
    - minimized window restore verified: `restored: true`
    - foreground verification passed: `foreground_title == "LegalPDF Translate"`
    - idle Gmail intake POST accepted and dispatched to `_start_gmail_message_load`
    - busy Gmail intake POST accepted and surfaced the blocked explanation
    - Gmail review dialog path raised, activated, executed, and transferred preview cache
