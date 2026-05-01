# Gmail Intake Regression Fixes

## Goal and non-goals
- Goal: fix the two reviewed Gmail extension regressions without disturbing the currently healthy browser-app handoff flow.
- Goal: restore the success-only browser open/focus contract on `/gmail-intake` handoff failures.
- Goal: keep the duplicate-click handoff lock valid across the full slow cold-start path.
- Non-goal: redesign the Gmail intake UX, browser-app polling flow, or provenance/integrity messaging.
- Non-goal: revert the no-reload browser-tab behavior introduced in the current extension work.

## Scope (in/out)
- In scope:
  - narrow `extensions/gmail_intake/background.js` fixes for failed POST handling and handoff lock lifetime
  - preserve the paired `extensions/gmail_intake/content.js` banner-state updates that are part of the same Gmail intake feature surface
  - targeted regression coverage in `tests/test_gmail_intake.py`
  - validating the Gmail extension test file after the fix
- Out of scope:
  - browser-app API/schema changes
  - broad docs-maintenance rewrites beyond the later touched-scope publish sync

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/gmail-intake-regression-fixes`
- base branch: `main`
- base SHA: `830f106352a2b4e23e0dcb3ec20883d0d3159fe8`
- target integration branch: `main`
- canonical build status: canonical worktree per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- `extensions/gmail_intake/background.js`
- `tests/test_gmail_intake.py`
- Additive test-only hooks under `globalThis.__LEGALPDF_TEST__` if needed

## File-by-file implementation steps
1. Narrow the failure-path logic in `extensions/gmail_intake/background.js` so failed `/gmail-intake` POST attempts notify Gmail without opening or focusing the browser app.
2. Increase the handoff stale-lock age budget to cover native launch readiness plus the full cold-start browser-tab and workspace polling path.
3. Preserve all existing success-path browser-app workspace checks, duplicate-click info banners, and launch-in-progress focus nudges.
4. Update `tests/test_gmail_intake.py`:
   - remove stale string-contract assertions for `chrome.tabs.reload` and `bypassCache: true`
   - add Node-backed behavior coverage for failed POST non-opening behavior and full-budget handoff locking

## Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_gmail_intake.py`
- Acceptance criteria:
  - failed or rejected `/gmail-intake` POSTs do not create, retarget, or focus browser-app tabs
  - successful handoff behavior remains unchanged
  - duplicate clicks stay locked through the full cold-start timeout budget and only recover after that budget expires

## Rollout and fallback
- Keep the fix scoped to the extension background script and its targeted regression tests.
- If a narrow test-hook addition is needed, keep it behind `globalThis.__LEGALPDF_TEST__` and additive only.

## Risks and mitigations
- Risk: fixing the failure path could accidentally suppress intended focus help for already-running launches.
  - Mitigation: keep the existing duplicate-click and launch-in-progress focus nudges outside `postContext()` unchanged.
- Risk: changing the lock age could alter user-facing wait messaging.
  - Mitigation: keep `buildLaunchInProgressMessage()` tied to `LAUNCH_READINESS_WAIT_MS`; only the stale-lock expiry grows.

## Assumptions/defaults
- The current browser-app success path is otherwise correct and should be preserved.
- No user-facing payload or API shape changes are required.
- Assistant Docs Sync can stay deferred until the dedicated publish pass for the touched Gmail/browser-handoff docs.

## Execution notes
- `extensions/gmail_intake/background.js`
  - restored success-only browser-app open/focus behavior on failed `/gmail-intake` POST attempts
  - widened the stale handoff lock budget to cover native launch readiness plus cold-start browser/workspace polling
  - kept launch-in-progress messaging tied to native launch readiness, not the widened stale-lock budget
  - extended the test-only hook surface additively under `globalThis.__LEGALPDF_TEST__`
- `tests/test_gmail_intake.py`
  - removed stale marker assertions for `chrome.tabs.reload` and `bypassCache: true`
  - added Node-backed regression coverage for failed POST non-opening behavior and full-budget stale-lock timing
- touched-scope Assistant Docs Sync
  - updated Gmail/browser-handoff docs to state the success-only browser-app open/focus contract
  - documented fail-closed Gmail-page banner behavior for rejected handoffs
  - documented in-progress duplicate-click focus guidance without extra browser-app windows

## Validation outcomes
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_gmail_intake.py` : passed (`9 passed`)
- `dart run tooling/validate_agent_docs.dart` : passed
- `dart run tooling/validate_workspace_hygiene.dart` : passed
