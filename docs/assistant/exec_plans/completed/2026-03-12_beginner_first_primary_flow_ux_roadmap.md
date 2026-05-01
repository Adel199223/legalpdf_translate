# Beginner-First Primary-Flow UX Cleanup Roadmap

## 1. Title
Beginner-first cleanup roadmap for the main desktop flows.

## 2. Goal and non-goals
- Goal:
  - reduce visual overload across the primary desktop flows without changing underlying workflow contracts
  - introduce reusable declutter primitives so the cleanup stays consistent across dialogs and the main shell
  - run the work through staged roadmap governance with deterministic render evidence at each boundary
- Non-goals:
  - no settings/admin/glossary/study cleanup in this roadmap
  - no persistence, schema, or workflow-behavior changes
  - no external design-reference discovery in this pass

## 3. Scope (in/out)
- In:
  - main shell default chrome and support copy
  - Save/Edit Job Log interpretation flow
  - interpretation honorarios export dialog
  - Gmail attachment review flow
  - shared Qt declutter primitives
  - deterministic render-review coverage for the interpretation Job Log dialog
- Out:
  - settings tabs
  - glossary/study/admin tools
  - translation/runtime transport, persistence, and document-generation behavior

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- Shared Qt UI internals:
  - compact icon-only add buttons
  - inline info/help affordances
  - collapsible form sections with state-driven default expansion
- Deterministic render-review tooling:
  - new Save/Edit Job Log interpretation dialog sample
- No public data/storage contract changes

## 6. Wave plan
- Stage 0:
  - activate roadmap artifacts
  - add baseline render sample for the interpretation Job Log dialog
  - capture baseline deterministic render evidence
- Stage 1:
  - build shared declutter primitives and styling hooks
- Stage 2:
  - apply cleanup to the interpretation Save/Edit Job Log dialog
- Stage 3:
  - apply cleanup to the main shell and Gmail attachment review
- Stage 4:
  - align the honorarios export dialog and finish the primary-flow audit

## 7. Tests and acceptance criteria
- Deterministic render-review coverage includes:
  - main shell profiles
  - Gmail review dialog
  - honorarios export dialog
  - interpretation Job Log dialog
- Qt state coverage includes:
  - service section collapsed/expanded defaults and triggers
  - compact add-button presence
  - interpretation-mode visibility rules after decluttering
  - Gmail review simplified-state behavior
- Acceptance:
  - primary flows show less default text and fewer always-visible controls
  - all current actions remain reachable
  - interpretation save/edit/export behavior remains unchanged
  - wide/medium/narrow layouts remain stable

## 8. Rollout and fallback
- Execute through hard stage gates.
- If a stage regresses clarity or discoverability, stop at that stage, keep the prior accepted stage as the floor, and revise the next-stage prompt pack before continuing.

## 9. Risks and mitigations
- Risk: visual cleanup hides task-critical guidance.
  - Mitigation: balanced-help rule; critical requirements stay visible, secondary explanations move behind info affordances.
- Risk: one-off dialog tweaks drift from the shared visual language.
  - Mitigation: Stage 1 creates reusable primitives first.
- Risk: UI polish breaks responsive stability.
  - Mitigation: every stage includes deterministic render review plus Qt state regression tests.

## 10. Assumptions/defaults
- Cleaner default for everyone; no separate beginner mode.
- Primary flows only in this roadmap.
- Balanced help density: visible essentials, hidden secondary detail.

## 11. Current status
- Stage 0 is complete with baseline render evidence captured.
- Stage 1 is complete with shared declutter primitives validated in isolation.
- Stage 2 is complete with the interpretation Save/Edit Job Log dialog decluttered and validated.
- Stage 3 is complete with the main shell and Gmail attachment review decluttered and validated.
- Stage 4 is complete with the interpretation honorários dialog aligned to the shared disclosure/help pattern and the primary-flow audit closed.
- The active implementation-detail source at closeout was `docs/assistant/exec_plans/completed/2026-03-13_beginner_first_primary_flow_ux_stage4_honorarios_final_audit.md`.
- The roadmap is closed in this worktree.
- No further continuation token is required.
