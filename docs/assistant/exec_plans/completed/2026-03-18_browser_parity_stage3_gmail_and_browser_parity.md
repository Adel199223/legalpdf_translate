# Browser Parity Stage 3: Gmail and Browser Parity

## Goal and non-goals
- Goal: bring Gmail intake, attachment review, batch progression, interpretation-notice intake, and draft finalization into browser parity.
- Non-goal: complete glossary/admin tools in this stage.

## Scope (in/out)
- In scope:
  - Gmail/browser intake review
  - batch progression
  - interpretation-notice Gmail path
  - Gmail draft finalization surfaces
  - deeper Extension Lab simulator coverage
- Out of scope:
  - glossary/calibration/admin tools

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: deferred until earlier stage acceptance.

## Interfaces/types/contracts affected
- Planned APIs:
  - `/api/gmail/*`
  - expanded `/api/extension/*` simulator and diagnostics contracts

## File-by-file implementation steps
1. Extract Gmail intake/batch/finalization browser-safe service contracts.
2. Add browser attachment review and batch state views.
3. Expand Extension Lab fixtures and simulator states around the real extension/native-host flow.

## Tests and acceptance criteria
- Browser Gmail flows match the supported desktop Gmail flows and keep host-bound failure states diagnosable.

## Rollout and fallback
- Require exact continuation token `NEXT_STAGE_4` after Stage 3 closure.

## Risks and mitigations
- Risk: browser UI hides host-bound Gmail prerequisites.
  - Mitigation: keep host provenance and bridge validation first-class in browser diagnostics.

## Assumptions/defaults
- The real extension remains canonical in Stage 3.
