# Worktree Baseline Discipline Docs Sync

## Goal and non-goals
- Goal: add durable governance guidance that prevents future mixed-up branch/worktree execution and ambiguous GUI test windows.
- Non-goal: document unrelated feature behavior or claim unmerged work as shipped.

## Scope (in/out)
- In: governance/workflow docs, workflow routing, one new active ExecPlan, refresh-note history.
- Out: product feature docs, code changes, branch cleanup, Gemini OCR state claims, GPT-5.4 state claims, unrelated honorários WIP.

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ocr-runtime-stabilization-20260306`
- Base branch: `origin/feat/ocr-runtime-stabilization-20260306`
- Base SHA: `1657079`
- Target integration branch: undecided at docs-sync time; governance-only sync on current branch

## Interfaces/types/contracts affected
- Assistant workflow routing in `docs/assistant/manifest.json`
- Governance workflow guidance in `agent.md`, `COMMIT_PUBLISH_WORKFLOW.md`, `DOCS_MAINTENANCE_WORKFLOW.md`, and `PLANS.md`

## File-by-file implementation steps
1. Add `WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md` with baseline-lock, provenance, and build-under-test rules.
2. Update governance docs to require approved baseline locks, worktree provenance, and explicit GUI handoff identity.
3. Route the new workflow through `INDEX.md` and `manifest.json`.
4. Record the incident and durable fix in `DOCS_REFRESH_NOTES.md`.
5. Run docs/workspace validators.

## Tests and acceptance criteria
- New workflow doc is present in both `INDEX.md` and `manifest.json`.
- Governance docs require:
  - latest approved baseline lock
  - worktree provenance recording
  - build-under-test identification for GUI handoffs
- `DOCS_REFRESH_NOTES.md` captures the branch/worktree mix-up incident as a workflow lesson.
- Docs validators pass.

## Rollout and fallback
- Keep this sync docs-only and scoped.
- If validator rules reject the new workflow routing, patch routing/docs only; do not expand into feature docs.

## Risks and mitigations
- Risk: docs sync accidentally implies unrelated local WIP is shipped. Mitigation: keep feature docs untouched and limit refresh notes to workflow-governance changes only.
- Risk: governance rules drift from validator expectations. Mitigation: mirror existing workflow-doc structure and rerun docs validators immediately.

## Assumptions/defaults
- `agent.md` is the canonical runbook to update, not `AGENTS.md`.
- The mixed-branch/worktree issue is best fixed with durable governance docs, not thread-local notes.
