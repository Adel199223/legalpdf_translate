# ROADMAP_WORKFLOW

## What This Workflow Is For
Running complex multi-wave work with one stable resume anchor, one active roadmap tracker, and one active wave ExecPlan so continuity does not depend on chat history.

## Expected Outputs
- A justified decision for roadmap mode instead of defaulting every task into a roadmap.
- `docs/assistant/SESSION_RESUME.md` as the stable first resume stop.
- Either:
  - one active roadmap tracker and one active wave ExecPlan linked from the resume anchor
  - or a dormant roadmap state on `main` that explicitly says no roadmap is currently open
- Explicit authority and update-order rules for live roadmap state.

## When To Use
- The user explicitly says `resume master plan`.
- The work is likely to span multiple waves or PRs.
- Fresh-session resume continuity is required.
- Detours and return-to-sequence handling are likely.
- Separate worktrees or parallel feature isolation are likely.
- The work coordinates multiple product surfaces.
- The user explicitly asks for a roadmap or master plan.

Don't use this workflow when:
- the task is a single-file fix
- the task is a narrow bug fix
- the task is a small UI text tweak
- the work is a one-shot docs cleanup
- a bounded major task can land safely as one merge under a normal ExecPlan

Instead use:
- `docs/assistant/exec_plans/PLANS.md` and a single ExecPlan for bounded major work
- `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md` when the task is local harness application rather than multi-wave execution governance

## What Not To Do
- Do not treat roadmap mode as the default for every major task.
- Do not use issue memory as normal roadmap history.
- Do not let resume continuity depend on thread memory alone.
- Do not update the roadmap tracker or `SESSION_RESUME.md` before updating the active wave ExecPlan.
- Do not leave `SESSION_RESUME.md` pointing at a merged or deleted feature branch after roadmap closeout.

## Primary Files
- `docs/assistant/SESSION_RESUME.md`
- `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
- `docs/assistant/exec_plans/active/`
- `docs/assistant/exec_plans/PLANS.md`
- `agent.md`
- `docs/assistant/manifest.json`

## Minimal Commands
PowerShell:
```powershell
Get-Content docs/assistant/SESSION_RESUME.md
dart run tooling/validate_agent_docs.dart
```

POSIX:
```bash
sed -n '1,220p' docs/assistant/SESSION_RESUME.md
dart run tooling/validate_agent_docs.dart
```

## Targeted Tests
- `dart run test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- The work does not actually need roadmap mode:
  - fall back to ExecPlan-only
  - close or supersede the roadmap artifacts instead of leaving fake complexity behind
- Fresh-session resume is ambiguous:
  - open `docs/assistant/SESSION_RESUME.md` first
  - if it is in active-roadmap state, then open the linked active roadmap tracker
  - then open the linked active wave ExecPlan
  - if it is in dormant roadmap state, do not invent a roadmap; use normal ExecPlan flow unless the user explicitly asks for roadmap/master-plan work
- Live roadmap state is split across worktrees:
  - treat the active worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan as authoritative
  - treat `main` as the stable merged baseline, not the live in-progress source
- A detour forces resequencing:
  - update the active wave ExecPlan first
  - update the active roadmap tracker second
  - update `docs/assistant/SESSION_RESUME.md` third
- Roadmap closeout is vague:
  - update the active wave ExecPlan first
  - update the active roadmap tracker second
  - update `docs/assistant/SESSION_RESUME.md` third
  - then either archive the roadmap artifacts or leave a dormant roadmap state on `main`
  - state the exact next step after closeout instead of leaving stale branch references behind

## Handoff Checklist
1. State why roadmap mode is justified instead of ExecPlan-only.
2. Confirm `docs/assistant/SESSION_RESUME.md` is the first resume stop.
3. If roadmap mode is active, name the active roadmap tracker.
4. If roadmap mode is active, name the active wave ExecPlan.
5. Confirm the authority model:
   - `docs/assistant/SESSION_RESUME.md` is the roadmap anchor file
   - the active roadmap tracker is the sequence source
   - the active wave ExecPlan is the implementation-detail source
6. Confirm the update order:
   1. active wave ExecPlan
   2. active roadmap tracker
   3. `docs/assistant/SESSION_RESUME.md`
7. If roadmap mode is dormant on `main`, say that explicitly and confirm normal ExecPlan flow is the default until a new roadmap is justified.
