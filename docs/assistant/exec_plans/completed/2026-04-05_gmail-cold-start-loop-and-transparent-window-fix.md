# Gmail Cold-Start Loop and Transparent Window Fix

## Goal and non-goals
- Goal: stop Gmail-triggered cold-start loops from repeatedly restarting the browser app and opening stacked translucent browser surfaces, while preserving stale-listener protection and Gmail live-workspace routing.
- Non-goals:
  - redesign the Gmail extension flow beyond startup/reuse behavior
  - change OCR/translation behavior
  - change timeout constants unless the implementation proves the current values are incompatible with the new warm-up semantics

## Scope (in/out)
- In scope:
  - lightweight runtime readiness endpoint for listener reuse probes
  - stale-listener probe migration from rich runtime diagnostics to lightweight readiness
  - Gmail native-host warm-up lock semantics
  - single-surface browser tab/window reuse in the Gmail extension during warm-up
  - regression coverage and live Gmail workspace verification
- Out of scope:
  - unrelated browser shell UI changes
  - broader Gmail workflow changes after handoff completes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/inline-extraction-recovery`
- Base branch: `main`
- Base SHA: `0683f529b9adf65b7ed44051376fa21f1d6fd0b4`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree allowed by runtime policy; approved base floor `4e9d20e`

## Interfaces/types/contracts affected
- Additive browser API:
  - `GET /api/runtime/ready?mode=...&workspace=...`
- Launcher/native-host readiness contract:
  - lightweight readiness payload becomes the source of truth for listener reuse/restart decisions
- Gmail native-host response contract:
  - `launch_in_progress` is the canonical warm-up/reuse state while a launch lock is still valid
  - `launch_timeout` becomes terminal-only after the lock expires or the launched listener dies
- Extension background behavior:
  - maintain a pending browser-surface registry keyed by browser workspace URL and reuse it during warm-up

## File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/app.py`
  - add a lightweight `/api/runtime/ready` route that bypasses heavy capability/provider/native-host checks
  - return runtime mode, workspace, build identity, asset version, listener provenance, and cheap Gmail bridge readiness summary only
- `src/legalpdf_translate/shadow_runtime.py`
  - point runtime probing at `/api/runtime/ready`
  - keep existing identity matching rules intact
- `src/legalpdf_translate/gmail_focus_host.py`
  - preserve the browser auto-launch lock across initial warm-up timeouts
  - return `launch_in_progress` while the lock remains active and the launched runtime is still plausible
  - only emit terminal `launch_timeout` after lock expiry or dead launch
- `extensions/gmail_intake/background.js`
  - track and reuse one pending browser tab/window per Gmail browser workspace URL
  - on warm-up/in-progress states, focus/reuse the pending surface and avoid creating additional tabs/windows
  - keep error messaging split between warm-up and terminal failure
- Tests:
  - extend shadow runtime, shadow web API, Gmail focus host, and Gmail intake background coverage for the new readiness and warm-up semantics

## Tests and acceptance criteria
- Automated:
  - `/api/runtime/ready` responds without invoking heavy provider/capability builders
  - stale-listener decision logic reuses a healthy matching listener even if rich runtime diagnostics are slow
  - Gmail prepare flow returns `launch_in_progress` during valid warm-up instead of relaunching
  - extension warm-up reuse tests prove one pending browser surface is reused and no additional window/tab is created
- Manual acceptance:
  - from a true cold start, one Gmail extension click opens/focuses at most one LegalPDF browser surface
  - no stacked transparent localhost windows appear
  - slow startup produces a waiting notice and surface reuse, not restart storms
  - existing healthy browser app listeners are reused without unnecessary restarts

## Rollout and fallback
- Rollout locally on the current feature worktree first and verify against `mode=live&workspace=gmail-intake`
- Fallback: if the lightweight readiness endpoint regresses, revert probe callers to the previous endpoint while keeping the route additive and unused

## Risks and mitigations
- Risk: a too-light readiness payload could miss a real broken runtime
  - Mitigation: keep build identity, runtime mode, workspace id, listener ownership, and bridge readiness in the probe payload
- Risk: pending browser-surface tracking could stick after failures
  - Mitigation: clear pending records on tab closure and terminal hydration failures
- Risk: warm-up lock semantics could hide genuine launch failure too long
  - Mitigation: keep the existing lock TTL and return terminal timeout after expiry or dead listener detection

## Assumptions/defaults
- Single-window reuse during warm-up is the chosen UX default
- Existing timeout constants remain unchanged unless the implementation proves they are incompatible with the new semantics
- The fix applies to the shared browser runtime path, not just one Gmail click flow
