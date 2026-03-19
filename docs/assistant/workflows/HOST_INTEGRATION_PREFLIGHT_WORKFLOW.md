# HOST_INTEGRATION_PREFLIGHT_WORKFLOW

## What This Workflow Is For
Use this workflow when a feature depends on a host-bound integration such as a locally installed CLI, browser/account-linked tooling, or a same-host desktop/auth runtime.

## Expected Outputs
- A verified installation/auth/host preflight result before implementation proceeds
- A clear `unavailable` vs `failed` classification when the integration is not ready
- A verified localhost listener ownership result when the integration depends on a local bridge/listener
- A minimal live smoke check result from the same host/runtime as the app

## When To Use
- Gmail draft creation through Windows `gog`
- browser/account-linked tooling that must share the desktop app’s auth state
- future Windows-bound auth or GUI integrations
- any feature where “tool works somewhere” is not enough because the app must consume it on a specific host

## Don't use this workflow when
- the task is pure code/docs/tooling with no same-host auth, browser, or desktop runtime dependency
- the integration has no local installation or account-state dependency

Instead use:
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md` for normal translation behavior
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md` for docs-only updates
- the feature-specific workflow when the integration is not host-bound

## What Not To Do
- Do not build the feature first and check environment/auth later.
- Do not assume WSL success proves the Windows app can use the same integration.
- Do not treat installation-only as sufficient readiness.
- Do not treat any process already listening on the expected port as proof the real integration is healthy.

## Primary Files
- `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- `docs/assistant/LOCAL_CAPABILITIES.md`
- `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
- any feature-specific integration helper or settings file

## Minimal Commands
PowerShell:
```powershell
dart run tooling/validate_agent_docs.dart
dart run tooling/validate_workspace_hygiene.dart
```

POSIX:
```bash
dart run tooling/validate_agent_docs.dart
dart run tooling/validate_workspace_hygiene.dart
```

## Targeted Tests
- integration-specific smoke checks in the same host/runtime as the app
- docs/validator checks that the host-bound workflow remains routed and current

## Preflight Sequence
1. Installation exists
   - verify the required tool/CLI is installed on the target host
2. Auth/account exists
   - verify the required auth, account, or local credential state is present
3. Host matches app runtime
   - verify the app and the integration run in the same host/runtime environment when required
4. Localhost listener ownership is correct
   - when a localhost listener is part of the integration, verify the port is free or owned by the expected process
   - if the integration supports both live and isolated browser-app modes, verify which mode owns the listener and whether that owner is supposed to be live-capable
5. Live smoke check passes
   - run a minimal real operation before building the full feature

## Same-Host Validation Rule
If the app runs on Windows and the integration depends on Windows-local auth or desktop state, validate it on Windows.

For this repo, Gmail draft creation through `gog` is the clearest example: the desktop app and the authenticated `gog` runtime must be validated on the same Windows host.

The browser app now makes this stricter for Gmail intake:
- validate the browser app in `live` mode, not isolated `shadow` mode
- confirm the live Gmail bridge owner and handoff URL, not just that some localhost listener is up
- treat browser-owned bridge readiness as the normal green path and Qt ownership as fallback/coexistence, not the default assumption

## Failure Modes and Fallback Steps
- `unavailable`
  - install missing
  - auth/account missing
  - wrong host/runtime
  - localhost bind conflict or unexpected listener ownership
- `failed`
  - preflight passed, but the feature behavior itself failed

Fallback order:
1. fix installation/auth/host mismatch
2. rerun the smoke check
3. only then proceed with implementation or feature debugging

## Handoff Checklist
1. State which host is authoritative for the integration.
2. State whether the app and integration are on the same host/runtime.
3. Record the listener ownership result when a localhost bridge/listener is part of the integration.
4. Record the smoke-check command/result.
5. Classify failures as `unavailable` or `failed`.
6. Route future work back through this workflow if the same host-bound integration appears again.
