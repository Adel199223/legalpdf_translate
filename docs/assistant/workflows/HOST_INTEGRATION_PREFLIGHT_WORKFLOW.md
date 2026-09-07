# HOST_INTEGRATION_PREFLIGHT_WORKFLOW

## What This Workflow Is For
Use this workflow when a feature depends on a host-bound integration such as a locally installed CLI, browser/account-linked tooling, or a same-host desktop/auth runtime.

## Expected Outputs
- A verified installation/auth/host preflight result before implementation proceeds
- A clear `unavailable` vs `failed` classification when the integration is not ready
- A verified localhost listener ownership result when the integration depends on a local bridge/listener
- A verified real-path canary result when a launch-only probe is weaker than the user-visible operation
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
- Do not treat shell-only startup or launch-only Word readiness as sufficient when the user-visible path later loads browser module workers, opens documents, or exports PDFs.
- Do not run a legacy Word probe that can attach to, hide or close an existing user session. Read-only installation/process evidence comes first; ownership, bounded execution and durable diagnostics must be in place before native experiments.

## Primary Files
- `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- `docs/assistant/LOCAL_CAPABILITIES.md`
- `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
- any feature-specific integration helper or settings file

## Minimal Commands
PowerShell:
```powershell
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
```

POSIX:
```bash
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
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
5. live smoke check passes
   - run a minimal real operation before building the full feature
   - if the integration has a lighter startup probe and a heavier real operation, prove the heavier path explicitly inside that live smoke
   - examples in this repo:
     - browser-app Gmail handoff should prove server readiness, same-tab redirect commit, `/gmail-intake` post, and current click diagnostics
     - Gmail finalization should prove Word DOCX-to-PDF export through an export canary, not only Word launch/COM reachability

## Same-Host Validation Rule
If the app runs on Windows and the integration depends on Windows-local auth or desktop state, validate it on Windows.

For this repo, Gmail draft creation through `gog` is the clearest example: the desktop app and the authenticated `gog` runtime must be validated on the same Windows host.

The browser app now makes this stricter for Gmail intake:
- validate the browser app in `live` mode, not isolated `shadow` mode
- confirm the live Gmail bridge owner and handoff URL, not just that some localhost listener is up
- confirm the registered native-host target is the no-console EXE for live Gmail; a `.cmd` target is diagnostic fallback only and can create visible console-window churn
- treat browser-owned bridge readiness as the normal green path and Qt ownership as fallback/coexistence, not the default assumption
- for Gmail same-tab intake, prove the current Gmail tab redirected to `gmail-intake`, diagnostics show `bridge_context_posted=true`, `source_gmail_url` is present, and the workspace is not stuck in `Pending load`

For this repo's Gmail finalization path:
- a shallow Word launch probe is not sufficient
- `finalization_ready` must come from a real DOCX-to-PDF export canary that uses the same export path as the final reply step

## Word PDF Export Safety and Diagnostic Contract

The shared implementation is `word_automation.py` with `word_pdf_control.py`, `word_pdf_artifacts.py` and `word_pdf_script.py`. It exports the app-generated honorarios document, not the translation. Preserve the editable original and any previous good PDF while producing a unique staged output; parse every PDF page and promote only verified fresh output. A canary must also contain its expected text.

Before a native call, acquire the cross-process export slot and persist a content-free phase journal. Keep helper/Word PID plus creation-time evidence, primary phase/HRESULT and cleanup evidence distinct. Do not dump scripts, document text or raw PowerShell errors. A timeout may stop only the retained app-owned helper handle, not a process-name tree or an unknown Word process. Unconfirmed cleanup quarantines further attempts; preserve the original state directory/journal during recovery. Save user work before asking the user to close Word normally; manual DOCX-to-PDF export and reviewed existing-PDF selection remain fallbacks. Do not delete quarantine state, change APPDATA or weaken security to obtain another attempt.

Retain these same-host compatibility decisions established by the 2026-09-07 repair:

- Launch the resolved Word executable with the single `/w` switch and retain its exact process identity. Bind that process's document window and verify ownership before changing visibility/security or opening the staged document. Do not attach through `GetActiveObject` or equate COM construction with ownership.
- Keep `Documents.Open` to the common first **12 positional arguments**, ending in `Visible=false`, including `ReadOnly=true` and `AddToRecentFiles=false`. VBA and Interop document different optional tails; adding unused tail placeholders produced a real `0x80070057` failure on this host.
- Keep `ExportAsFixedFormat` to **14 explicit arguments**, including print quality, all pages, `IncludeDocProps=true` and `KeepIRM=true`. Omit the unnecessary optional `FixedFormatExtClassPtr`; passing a missing-value sentinel there also failed natively.
- Close only the exact staged document, then require exactly the original, unchanged, identity-verified blank bootstrap and no Protected View windows before `Quit(0)`. Keep that blank document/window as the live automation anchor through Quit. Closing the final blank first disconnected Word's native collection surface; do not weaken the document guard to accept an arbitrary remaining document.
- Release owned COM references and confirm the recorded process exited. The normal browser/Qt callers make one attempt with a 45-second export allowance and bounded cleanup, without automatic re-probe/re-export after timeout. Passing helper startup is not passing export.

Require opt-in native canary and real shared/browser-route/Qt-worker exports with synthetic data, complete-page Word-PDF visual inspection, unchanged original hashes, unsaved-document coexistence and healthy bounded-timeout recovery. Keep private evidence outside Git. The eight accepted native exports and exact failure/repair evidence are recorded in the [completed repair ExecPlan](../exec_plans/completed/2026-09-07_honorarios_pdf_export_reliability.md). That acceptance included no live Gmail test, Office repair or security-setting change; it does not establish arbitrary-host readiness. The pre-existing Qt small-screen `0x8001010d` event-loop diagnostic remains separate from Word export and must not be suppressed or described as fixed.

## Failure Modes and Fallback Steps
- `unavailable`
  - install missing
  - auth/account missing
  - wrong host/runtime
  - localhost bind conflict or unexpected listener ownership
  - shell/launch probe passes but the real browser-document or Word-export canary fails
- `failed`
  - preflight passed, but the feature behavior itself failed

Fallback order:
1. Establish whether the evidence shows installation/auth/host mismatch, a helper defect, or an uncertain in-progress operation. Do not infer Office corruption from a COM/argument error.
2. Correct only the demonstrated issue within the approved scope. Preserve user work, quarantine and security settings; installation/auth changes require their own authorization.
3. Rerun the same-host smoke check through the safe shared path after recovery, then proceed with implementation or feature debugging. A Word export canary does not authorize Gmail draft creation or sending.

## Handoff Checklist
1. State which host is authoritative for the integration.
2. State whether the app and integration are on the same host/runtime.
3. Record the listener ownership result when a localhost bridge/listener is part of the integration.
4. Record the smoke-check command/result.
5. Classify failures as `unavailable` or `failed`.
6. Route future work back through this workflow if the same host-bound integration appears again.
