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
   - canonical build status or intended noncanonical override
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
   - HEAD SHA
   - canonical vs noncanonical status
   - distinguishing feature set
   - prefer the build identity packet emitted by `tooling/launch_qt_build.py` when multiple worktrees/builds can exist
4. If a side branch becomes the only branch with approved working functionality, promote it into the approved base before starting unrelated new feature work.
5. If the user accepts a feature in testing, merge it into the approved base as the default next step before starting the next unrelated feature branch.
6. A feature branch is not a valid routine test target unless it still contains the approved-base floor declared in `docs/assistant/runtime/CANONICAL_BUILD.json`.
7. If the plan includes commit/push steps and the user does not narrow scope explicitly:
   - assume `commit` means full pending-tree triage plus logical grouped commits
   - assume `push` means Push+PR+Merge+Cleanup
   - record any intentional override when the task says `commit only ...` or `push branch only`
8. Close with executed validations and outcomes.
9. Move to `completed/` after merge or completion.

## Worktree Link
If running parallel initiatives, pair each active ExecPlan with dedicated `git worktree` isolation.
