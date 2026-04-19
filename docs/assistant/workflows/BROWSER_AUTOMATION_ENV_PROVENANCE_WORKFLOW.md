# BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW

## What This Workflow Is For
Hardening browser automation reliability with host/binary provenance and fallback semantics.

## Expected Outputs
- Automation preflight packet with toolchain and browser provenance.
- Deterministic host-selection + fallback status (`unavailable|failed`).
- Restricted-page fallback handling and machine-first/manual-last split.

## When To Use
- Browser UI/extension automation flows are in scope.
- Multi-host contexts (Windows/WSL/remote/local) or repeated automation fragility are present.
- User requests lower manual validation burden with reproducible checks.

## What Not To Do
- Don't use this workflow when tasks are API-only or do not involve browser/UI automation.
- Instead use `docs/assistant/workflows/TRANSLATION_WORKFLOW.md` or `docs/assistant/workflows/CI_REPO_WORKFLOW.md`.

## Primary Files
- `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- `tooling/automation_preflight.dart`
- `test/tooling/automation_preflight_test.dart`
- `docs/assistant/manifest.json`

## Minimal Commands
PowerShell:
```powershell
dart tooling/automation_preflight.dart
dart test/tooling/automation_preflight_test.dart
```
POSIX:
```bash
dart tooling/automation_preflight.dart
dart test/tooling/automation_preflight_test.dart
```

## Targeted Tests
- `dart test/tooling/automation_preflight_test.dart`
- `dart tooling/validate_agent_docs.dart`

## Failure Modes and Fallback Steps
- Preferred host cannot execute automation: classify as `unavailable`, run fallback host preflight.
- Assertions fail after automation starts: classify as `failed`, capture artifact packet.
- Restricted browser pages block scripted injection: switch to standard webpage/manual-input fallback path.
- On this Windows machine, prefer direct Dart script execution for browser automation preflight because the package-run launcher form can degrade through a broken `dartdev` path even when the direct script form is healthy.

## Handoff Checklist
1. Record canonical workspace path before automation.
2. Emit stale-copy audit findings and selected host.
3. Emit browser binary provenance packet:
   - `automation_browser_binary`
   - `automation_browser_version`
   - `automation_browser_source`
4. Confirm machine-first checks precede manual operator checks.
