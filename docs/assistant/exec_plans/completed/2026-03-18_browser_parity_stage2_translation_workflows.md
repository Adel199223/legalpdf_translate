# Browser Parity Stage 2: Translation Workflows

## Goal and non-goals
- Goal: add browser parity for translation-centric workflows after the Stage 1 shell is accepted.
- Non-goal: complete Gmail batch parity in this stage.

## Scope (in/out)
- In scope:
  - upload/select source PDF
  - analyze-only
  - start/cancel/monitor translation
  - resume and rebuild DOCX
  - review queue
  - Save/Edit Job Log for translation rows
  - artifact/download handling and recent-job reopen
- Out of scope:
  - Gmail batch execution/finalization
  - admin/power tools

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: deferred until Stage 1 acceptance.

## Interfaces/types/contracts affected
- Planned APIs:
  - `/api/translation/*`
  - translation-oriented `/api/joblog/*` edit/reopen helpers

## File-by-file implementation steps
1. Extract translation workflow orchestration behind shared service contracts.
2. Expose long-running translation job status via durable job ids and polling endpoints.
3. Add browser surfaces for translation setup, progress, review queue, and save/edit flows.

## Tests and acceptance criteria
- Browser translation flow matches the latest desktop translation behavior for the supported Stage 2 journeys.

## Rollout and fallback
- Require exact continuation token `NEXT_STAGE_3` after Stage 2 closure.

## Risks and mitigations
- Risk: long-running translation orchestration becomes browser-specific.
  - Mitigation: keep orchestration in shared backend services and make the browser a polling client only.

## Assumptions/defaults
- Stage 2 begins only after Stage 1 is accepted.
