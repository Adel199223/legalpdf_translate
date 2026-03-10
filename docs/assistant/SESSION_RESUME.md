# SESSION_RESUME

## First Resume Stop
Open this file first for:
- `resume master plan`
- `where did we leave off`
- `what is the next roadmap step`

This file is the roadmap anchor file and the stable first resume stop for fresh sessions.

## Authoritative Worktree
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch: `main`
- Live roadmap authority: `main` is the authoritative merged baseline for this worktree until a future roadmap-scoped task activates a new tracker and wave

## Roadmap State
- Dormant roadmap state
- No active roadmap currently open on this worktree.
- No active roadmap tracker is currently linked from this file.
- No active wave ExecPlan is currently linked from this file.

## Next Concrete Action
- If the user explicitly asks for roadmap/master-plan work, create a new roadmap tracker and active wave ExecPlan on the active feature branch, then update this file.
- Otherwise default to normal ExecPlan flow for the current task.

## Resume Order
1. Read this file.
2. If this file declares an active roadmap state, open the linked active roadmap tracker.
3. Then open the linked active wave ExecPlan.
4. If this file declares a dormant roadmap state, do not invent a roadmap; use normal ExecPlan flow unless the user explicitly asks for roadmap/master-plan work.

## Authority Notes
- Issue memory is only for repeatable governance/workflow failures. It is not normal roadmap history.
- During active roadmap work in a separate worktree, that worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan become authoritative for live roadmap state.
- When roadmap work is dormant on `main`, this file must say so explicitly instead of pointing at stale feature-branch artifacts.
