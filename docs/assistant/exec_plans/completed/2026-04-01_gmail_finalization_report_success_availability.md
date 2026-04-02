# Gmail Finalization Report Success Availability

## Goal and non-goals
- Goal: keep `Generate Finalization Report` available from the Gmail batch finalization drawer after successful draft creation as well as blocked/recoverable outcomes.
- Goal: move the finalization report context from browser-only reconstruction to a backend-owned, persisted session artifact.
- Goal: run scoped docs sync so operator guidance matches the new success-state reportability contract.
- Non-goal: change Gmail draft creation behavior, Word canary behavior, or translation/finalization execution flow.
- Non-goal: auto-generate report files on every success.

## Scope (in/out)
- In scope:
  - Gmail batch session/report context model
  - Gmail batch finalization backend responses and session persistence
  - Browser finalization drawer gating and report-action behavior
  - Scoped docs sync for Gmail finalization report guidance
- Out of scope:
  - interpretation finalization behavior unless shared helpers need additive compatibility
  - run-report behavior for normal translation runs
  - unrelated Gmail review/prepare/start flows

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/gmail-finalization-report-success`
- base branch: `main`
- base SHA: `18be21ec2d2c632f12ec5da3d2e5351aa5644488`
- target integration branch: `main`
- canonical build status: noncanonical feature branch on top of canonical `main`, preserving the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Additive Gmail batch session/API fields:
  - `active_session.finalization_report_context`
  - `normalized_payload.finalization_report_context` on meaningful finalization responses
- Persist the same additive snapshot into `gmail_batch_session.json`
- Keep `/api/power-tools/diagnostics/run-report` route shape unchanged

## File-by-file implementation steps
1. Extend the Gmail batch session model and serialized session/report payloads with a persisted `finalization_report_context`.
2. Add a backend helper that builds the canonical Gmail finalization report context from finalization outcome data, and populate it for blocked, recoverable, and successful `draft_ready` batch outcomes.
3. Update the browser drawer logic to show `Generate Finalization Report` whenever a backend-provided context exists, preferring the live response and falling back to persisted session state after reload.
4. Update success/failure-neutral report-action copy in the browser finalization surface without changing the existing on-demand report route.
5. Add/adjust backend and browser-facing tests for successful finalization report availability, persisted report context, and report generation from success-state payloads.
6. Run scoped docs sync for the Gmail finalization report guidance in `APP_KNOWLEDGE.md`, `docs/assistant/features/APP_USER_GUIDE.md`, and `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`.

## Tests and acceptance criteria
- Backend/service:
  - successful `finalize_batch()` returns and persists `finalization_report_context`
  - blocked/local-only/draft-failed/draft-unavailable outcomes still return/persist it
  - `generate_browser_run_report(..., gmail_finalization_context=...)` supports success-state `status="ok"` and `finalization_state="draft_ready"`
- Browser/UI:
  - success-state drawer exposes `Generate Finalization Report`
  - blocked and recoverable states still expose it
  - `ready_to_finalize` without a finalization outcome keeps it hidden
  - persisted `draft_ready` session restores the report action after reload
- Acceptance:
  - no regression to Gmail cold start, prepare, translation, or draft creation path
  - report generation remains on-demand only

## Rollout and fallback
- Keep the route contract additive so existing callers keep working.
- If persisted success-state context proves incomplete, fall back to augmenting the stored context rather than reintroducing browser-only reconstruction.

## Risks and mitigations
- Risk: success-state report visibility could accidentally show too early in preflight-only `ready_to_finalize` state.
  - Mitigation: gate on backend-provided report context, not just finalization state labels.
- Risk: report snapshots could miss enough data to make the success artifact useful after reload.
  - Mitigation: store draft request/result, export diagnostics, runtime identity, and final paths in the persisted context.
- Risk: docs drift could reintroduce the wrong operator expectation.
  - Mitigation: include same-pass docs sync for touched guidance files.

## Assumptions/defaults
- Finalization reports stay manual/on-demand.
- Gmail batch finalization is the only scope for this pass.
- Successful finalization should expose the same report action as blocked/recoverable states, but with success-neutral copy.
