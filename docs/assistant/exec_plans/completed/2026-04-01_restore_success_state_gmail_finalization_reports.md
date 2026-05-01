# ExecPlan: Restore Success-State Gmail Finalization Reports

## Context
- User reproduced a live regression on April 1, 2026 where a completed Gmail batch session (`draft_ready`) no longer exposed `Generate Finalization Report`.
- The live browser app screenshots also showed a disabled `Finalize Gmail Batch Reply` button in a completed session, which made the final drawer look broken even though the draft had already been created.
- Investigation confirmed the immediate cause:
  - the live app on `127.0.0.1:8877` was still serving `main@18be21e`
  - that build preserved `draft_ready` state but did not persist `finalization_report_context` for success-state sessions
  - the browser drawer still rendered a disabled finalize button for `draft_ready`
- The durable Gmail batch session JSON already contains enough data to reconstruct a report-capable completed session.

## Goals
1. Backfill `finalization_report_context` for terminal Gmail batch sessions when missing.
2. Preserve that backfill into the in-memory session and session JSON so refresh/reopen stays fixed.
3. Make the completed-state Gmail finalization drawer prioritize report generation instead of a dead finalize action.
4. Add explicit build/asset provenance visibility so acceptance can prove the live app is serving the expected code.
5. Validate the fix against both resumed completed sessions and fresh finalization flows.

## Implementation Plan
### 1. Backend backfill and restore
- Add a helper in `gmail_browser_service.py` that repairs terminal Gmail batch sessions with missing or incomplete `finalization_report_context`.
- Invoke it from bootstrap/resume paths before serializing the active session.
- If the browser workspace has no in-memory batch session, inspect the latest persisted Gmail batch session report and restore a report-capable completed-session snapshot when safe.

### 2. Completed-state drawer UX
- Update `shadow_web/static/gmail.js` so `draft_ready` and other terminal states do not foreground a disabled finalize action.
- Show `Generate Finalization Report` whenever a backend-provided finalization report context exists, including restored/backfilled success-state sessions.
- Keep retry/finalize affordances only where retry is actually meaningful.

### 3. Provenance hardening
- Surface build/asset provenance with the Gmail/browser diagnostics data used during acceptance.
- Fail acceptance if the served browser app is not the expected branch/build/asset set.

### 4. Regression coverage and validation
- Add/extend focused tests for:
  - bootstrap backfill of legacy `draft_ready` sessions
  - completed-state report availability after restore
  - completed-state drawer behavior
  - report generation from backfilled success-state context
- Validate with focused pytest and live localhost checks on the served build.

## Exit Criteria
- A completed `draft_ready` Gmail batch session exposes `Generate Finalization Report` without rerunning finalization.
- The drawer no longer centers a disabled finalize action for already-completed batches.
- Fresh end-to-end Gmail finalization still ends in real draft creation and still exposes the report afterward.

## Outcome
- Completed on April 1, 2026.
- Backend:
  - restored/backfilled legacy `draft_ready` Gmail batch sessions now rebuild `finalization_report_context` when it is missing or incomplete
  - blank provenance (`build_sha`, `asset_version`) is now treated as incomplete and repaired during bootstrap
  - resumed batch-session JSON is rewritten once with the repaired success-state report context
- Browser UX:
  - completed `draft_ready` sessions no longer foreground a dead finalize action
  - the drawer now relies on backend-owned `finalization_report_context` and keeps report generation available after resume/reload
  - build provenance is surfaced in the drawer so live acceptance can distinguish served-build drift from repo-only fixes
- Validation:
  - focused suite passed: `47 passed`
  - live localhost verification on `127.0.0.1:8877` confirmed the served branch/asset pair as `feat/gmail-finalization-report-success@18be21e` with `asset_version=7052858987bd`
  - the resumed completed session `gmail_batch_ba9e8ea05e2d` exposed a restored `draft_ready` report context and successfully generated a report at `C:\Users\FA507\Downloads\power_tools\gmail_finalization_report_20260401_130615.md`
