# HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW

## What This Workflow Is For
Use this workflow when tests or host-bound runtime flows can accidentally collide with live machine state, or when a larger workflow spans handoff, per-run execution, and finalization surfaces that become expensive to debug from thread memory alone.

## Expected Outputs
- Default test isolation rules that keep live user state, auth, and ports out of normal test runs.
- Visible listener/runtime conflict handling instead of silent bind/log failures.
- One compact support-packet order for multi-surface debugging.
- Policy-level guidance for layering durable session diagnostics on top of existing per-run artifacts.

## When To Use
- localhost listeners or same-host background workers are part of the feature
- browser/app, CLI/app, or desktop/app bridges span more than one failure surface
- tests could accidentally reuse live settings, auth state, caches, or user-facing ports
- a workflow needs both per-run artifacts and a higher-level session/finalization view

Don't use this workflow when:
- the task is a normal single-surface feature or docs change with no live-state or cross-surface reliability risk
- the workflow does not involve listeners, bridges, or multi-stage diagnostics

Instead use:
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md` for normal translation/runtime behavior
- `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md` for install/auth/same-host smoke checks only
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md` for docs-only sync work

## What Not To Do
- Do not let tests reuse live roaming/profile settings, authenticated machine state, or default production ports unless the test explicitly opts in.
- Do not treat any process listening on the expected port as proof the real runtime is healthy.
- Do not let stale browser module assets, stale extension service workers, or old localhost tabs masquerade as the current browser build under test.
- Do not let deterministic acceptance tooling leave helper `cmd.exe`/Playwright MCP processes behind and then confuse those helpers with product native-host console churn.
- Do not replace per-run reports with a session artifact; layer them.
- Do not create separate browser or extension report files by default when transient banner/UI/console evidence is enough.

## Primary Files
- `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`
- `docs/assistant/workflows/HOST_INTEGRATION_PREFLIGHT_WORKFLOW.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- `docs/assistant/LOCAL_CAPABILITIES.md`
- `docs/assistant/manifest.json`

## Minimal Commands
PowerShell:
```powershell
python -m pytest -q
dart tooling/validate_agent_docs.dart
```

POSIX:
```bash
python3 -m pytest -q
dart tooling/validate_agent_docs.dart
```

## Default Test Isolation Rules
- pytest-style temporary filesystem and environment state is the default for tests that touch settings, caches, or runtime-owned files.
- Live user settings paths, roaming profile files, auth state, and caches must be explicit opt-in for tests, never inherited silently.
- When one localhost browser app supports both daily-use and testing, keep an explicit isolated mode with separate state roots instead of spinning up ad hoc near-live harnesses.
- Tests should use non-live or ephemeral ports by default instead of the user-facing runtime port.
- Listeners, windows, background workers, and service processes must have explicit teardown even when a test fails.
- Focus-sensitive desktop tests must explicitly activate the target window/control and close leaked popups or modal dialogs between cases instead of relying on inherited focus state.

## Listener Ownership and Runtime Conflict Rules
- If a feature depends on a localhost listener, verify the expected port is free or owned by the expected process before treating the integration as healthy.
- Classify unexpected listener ownership or bind conflicts as preflight `unavailable`, not as product `failed`.
- Runtime listener startup failures must surface visible status, not silent logs only.
- If one browser app serves both live and isolated modes, diagnostics must show the active mode, data root, workspace, and listener owner so shadow/test state cannot be mistaken for live readiness.
- If a localhost browser tab is part of the handoff contract, diagnostics must also prove client hydration and client/server `asset_version` agreement so stale tabs or stale assets are not mistaken for a fresh successful launch.
- For Gmail same-tab intake, the primary acceptance proof is the correlated click/session state: current `handoff_session_id`, same-tab redirect URL, `bridge_context_posted=true`, `source_gmail_url` present, `runtime_state_root_compatible=true`, and no `Pending load`/unavailable IDs.
- For Google Photos Interpretation OAuth/Picker diagnostics, use shadow mode first, normally on `127.0.0.1:8890`, and log only method/path with query strings removed. Stop OAuth diagnostics after `connected=true` before opening Picker. For Picker diagnostics, continue only after the user confirms a non-private selection, then expect session polling -> `mediaItemsSet=true` -> media-items list -> import -> `Review Case Details` -> cleanup.

## Durable Diagnostics and Support Packet Rules
- Keep existing per-run artifacts as the main run evidence.
- When a run belongs to a larger multi-stage session, add a compact `workflow_context`-style block instead of replacing the run report.
- If the workflow spans handoff, per-item execution, and finalization, keep one durable app-owned session artifact with:
  - `session_id`
  - `started_at`
  - `status`
  - `halt_reason`
  - handoff/source context
  - per-item run linkage
  - finalization state
  - final output names when relevant
- Browser-side failures remain transient UI/banner/console evidence unless the feature has a strong reason to persist them.
- When a browser/Gmail failure happens before a run directory exists, a compact browser failure report is an acceptable additive artifact. It should capture the browser/build context, `asset_version`, and the attempted browser-module or worker URL that failed.
- Extension/native-host launch debugging should distinguish product helper windows from harness helpers. If automation starts `playwright-mcp` or similar test helpers, clean those up before making claims about CMD/PseudoConsole churn.

## Support Packet Order
1. User-visible browser/banner/UI error if handoff failed before app intake, plus a browser failure report when the flow failed before `run_dir` existed and the UI offered one.
2. App build identity and visible runtime status.
3. Per-run report plus machine-readable run summary for the affected execution.
4. App-owned session artifact for multi-stage or finalization issues.

## Targeted Tests
- test isolation from live settings, auth, caches, and default ports
- listener ownership and bind-conflict handling
- stale browser asset-version mismatch detection and bounded exact-tab reload recovery
- focus-sensitive dialog shortcut paths with explicit activation/cleanup
- long-running host automation staying off the GUI thread when the feature is user-facing
- per-run artifact integrity
- finalization/export/draft integrity
- diagnostics rendering and report linkage
- docs validator coverage for workflow routing and contract drift

## Failure Modes and Fallback Steps
- Tests touched live user state or ports:
  - redirect settings/env/filesystem state to temp locations
  - switch to non-live or ephemeral test ports
  - rerun after explicit teardown
- Expected localhost port is owned by the wrong process:
  - classify as `unavailable`
  - stop feature debugging until ownership is corrected
- Browser shell is up but the tab is stale or only partially hydrated:
  - classify stale client/server asset-version or hydration mismatch as preflight `unavailable`
  - allow one exact localhost tab reload when the product contract supports it
  - if the mismatch persists, preserve the browser failure packet instead of masking it as a generic product error
- Gmail same-tab click redirects but intake remains pending:
  - treat `bridge_context_posted=false`, missing `source_gmail_url`, or unavailable message/thread IDs as handoff failure evidence
  - clear stale click/session state before retrying
  - do not repeatedly click the toolbar or switch back to a separate-tab launch model
- Console-window churn appears during Gmail acceptance:
  - verify the live native-host manifest targets `LegalPDFGmailFocusHost.exe`, not `LegalPDFGmailFocusHost.cmd`
  - scan for test harness helpers separately from LegalPDF native-host/server processes
  - fail closed rather than falling back to generic OS/browser or `.cmd` launch paths
- Multi-surface issue lacks enough evidence:
  - collect the support packet in the documented order
  - add or repair `workflow_context` / session-artifact linkage rather than inventing ad hoc notes
- Historical polluted artifacts are discovered:
  - fail closed and rerun to create clean artifacts
  - do not silently substitute partial or guessed outputs
- Google Photos Picker session is created but `mediaItemsSet` remains false:
  - confirm whether the Picker tab opened, whether the visible fallback was used, whether the same/expected Google account was active without recording the email, and whether the Google Photos completion screen appeared
  - do not log Picker URLs, query strings, media IDs, base URLs, account identifiers, or raw photos
  - if the user sees `Done! Continue in the other app or device`, treat selection as complete and continue LegalPDF polling before declaring failure
- Host-bound desktop automation freezes the visible UI or dumps raw technical commands into the main warning text:
  - move the long-running step off the GUI thread
  - keep the main warning concise and place raw diagnostics in expandable details only
  - preserve any usable local artifact and offer one calm recovery path instead of stacking follow-up warnings

## Handoff Checklist
1. State whether the test/runtime used isolated state or explicit live-state opt-in.
2. State the expected listener port/process ownership when localhost runtime is involved.
3. Name the primary per-run artifact for the issue.
4. State whether a larger workflow/session artifact exists and where it lives.
5. Provide the support packet in the documented order.
6. If the issue class repeated, update `docs/assistant/ISSUE_MEMORY.md` and `docs/assistant/ISSUE_MEMORY.json`.
7. For Gmail extension acceptance, include the latest `launch_session_id`, `handoff_session_id`, `bridge_context_posted`, `source_gmail_url` presence, native-host path kind, and any helper-process cleanup performed.
