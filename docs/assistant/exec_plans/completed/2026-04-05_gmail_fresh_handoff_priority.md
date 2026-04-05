## Title
Gmail Fresh-Handoff Priority Over Restored Finalization

## Goal and non-goals
- Goal: let a fresh Gmail extension handoff take priority over any restored completed batch so the browser app opens into new intake/review work by default.
- Non-goals: removing report-based recovery of prior finalized batches, changing Gmail finalization/report semantics, or altering Arabic review/translation behavior.

## Scope (in/out)
- In scope: Gmail bootstrap payload shape for restored completed batches, Gmail frontend stage/CTA/rendering logic, bounded refresh behavior, and focused regression coverage.
- Out of scope: new Gmail endpoints, Gmail draft/finalization contracts, translation run/report generation logic, and docs sync in this implementation pass.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_fresh_handoff`
- Branch name: `feat/gmail-fresh-handoff-priority`
- Base branch: `main`
- Base SHA: `804ef487424d16c7cb53654dc806a2b593e8cca5`
- Target integration branch: `main`
- Canonical build status: noncanonical implementation worktree; intended to merge back into canonical `main`

## Interfaces/types/contracts affected
- Additive Gmail bootstrap field: `restored_completed_session`
- Existing `active_session` contract narrows to in-memory/live workspace state only.
- Gmail frontend state/rendering derives fresh intake behavior when only `restored_completed_session` exists.

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_browser_service.py`
  - Return report-restored terminal translation batches under `restored_completed_session` instead of `active_session`.
  - Preserve existing report-context repair/backfill behavior and suppression after explicit reset.
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - Add recovered-session-aware stage/CTA logic so restored-only state no longer becomes `translation_finalize`.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Store/render `restored_completed_session` separately from `activeSession`.
  - Show recovered finalization as a secondary result/action.
  - Keep bounded refresh alive when restored-only state is present.
- `tests/test_gmail_browser_service.py`
  - Update restore/bootstrap expectations to assert `restored_completed_session`.
  - Add coverage for fresh handoff superseding restored-only state.
- `tests/test_gmail_review_state.py`
  - Add recovered-only stage/CTA coverage.

## Tests and acceptance criteria
- Bootstrap returns report-restored terminal sessions under `restored_completed_session`, not `active_session`.
- `clear_workspace()` still suppresses restore until new activity.
- Recovered-only Gmail state behaves like fresh intake, not `translation_finalize`.
- Recovered-only Gmail state shows a secondary recovered result/action instead of `Resume Current Step`.
- Recovered-only state does not stop passive refresh as stable.
- New Gmail bridge intake supersedes the recovered-only state without manual reset.
- Existing finalization report recovery remains available when intentionally opened.

## Rollout and fallback
- Ship as an additive bootstrap/UI contract change only.
- If needed, operators can still use `Reset Gmail Workspace` to clear the workspace explicitly; no destructive data changes are introduced.

## Risks and mitigations
- Risk: previously restored completed-session affordances disappear entirely.
  - Mitigation: keep a secondary recovered-session surface with explicit result access/report generation.
- Risk: refresh logic could start polling too aggressively again.
  - Mitigation: only treat restored-only state as unstable; keep existing bounded warmup/passive polling rules otherwise.
- Risk: tests or consumers implicitly assume restored completed sessions come back as `active_session`.
  - Mitigation: update focused backend/frontend tests and keep the field additive rather than deleting recovery data.

## Assumptions/defaults
- Fresh Gmail handoff should win automatically over restored finalized state.
- Prior finalized batch details should remain accessible as secondary recovered context.
- No new user choice dialog is required for this pass.
