# Browser Parity Stage 4: Power Tools and Admin Surfaces

## Goal and non-goals
- Goal: add browser parity for glossary, calibration, diagnostics, provider/preflight, and remaining advanced settings/admin tools.
- Non-goal: change the canonical business logic of those tools.

## Scope (in/out)
- In scope:
  - glossary editor/builder
  - calibration audit
  - diagnostics bundle/preflight/provider tabs
  - remaining settings/admin surfaces needed for parity
- Out of scope:
  - public deployment

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: deferred until earlier stage acceptance.

## Interfaces/types/contracts affected
- Planned APIs:
  - remaining `/api/settings/*`
  - glossary/calibration/diagnostics endpoints

## File-by-file implementation steps
1. Extract advanced-tool service contracts from Qt-owned orchestration.
2. Add browser parity surfaces for glossary, calibration, and diagnostics/admin workflows.

## Tests and acceptance criteria
- Browser power/admin tools match desktop behavior for the supported tools in this stage.

## Rollout and fallback
- Require exact continuation token `NEXT_STAGE_5` after Stage 4 closure.

## Risks and mitigations
- Risk: advanced tools grow browser-only behavior.
  - Mitigation: keep tool logic backend-owned and UI-light.

## Assumptions/defaults
- Advanced tools follow core-journey parity, not the reverse.
