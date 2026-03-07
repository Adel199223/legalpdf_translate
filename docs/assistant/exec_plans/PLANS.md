# ExecPlans

## Purpose
ExecPlans make major work deterministic, reviewable, and handoff-safe.

## When Required
- Required for major/multi-file changes.
- Optional for small, isolated, low-risk edits.

## Locations
- Active: `docs/assistant/exec_plans/active/`
- Completed: `docs/assistant/exec_plans/completed/`

## Required Plan Template
Use this structure:
1. Title
2. Goal and non-goals
3. Scope (in/out)
4. Worktree provenance:
   - worktree path
   - branch name
   - base branch
   - base SHA
   - target integration branch
5. Interfaces/types/contracts affected
6. File-by-file implementation steps
7. Tests and acceptance criteria
8. Rollout and fallback
9. Risks and mitigations
10. Assumptions/defaults

## Lifecycle Rules
1. Create plan file in `active/` before major implementation starts.
2. Keep it updated as decisions are made.
3. For GUI/app handoffs, record the canonical build under test:
   - repo/worktree path
   - branch
   - HEAD commit
   - distinguishing feature set
4. Close with executed validations and outcomes.
5. Move to `completed/` after merge or completion.

## Worktree Link
If running parallel initiatives, pair each active ExecPlan with dedicated `git worktree` isolation.
