# WORKTREE_BASELINE_DISCIPLINE_WORKFLOW

## What This Workflow Is For
Preventing mixed-up branches, stale worktree bases, and ambiguous GUI test windows when parallel work happens in more than one worktree.

## Expected Outputs
- One declared approved baseline before new parallel work starts.
- Every active ExecPlan records worktree provenance and integration target.
- Every GUI handoff identifies the exact build under test.
- One canonical runnable build declared in `docs/assistant/runtime/CANONICAL_BUILD.json`.
- One approved base branch/floor declared in `docs/assistant/runtime/CANONICAL_BUILD.json`.

## When To Use
- Parallel feature work uses more than one branch or worktree.
- A newer approved branch exists and new work is about to start from it.
- More than one visible app window/build can exist on the same machine.

## What Not To Do
- Don't use this workflow when the task stays on a single branch/worktree and build identity is not ambiguous.
- Don't start a new worktree from an older convenient branch when a newer approved baseline already exists.
- Don't keep building on a side branch after the user has accepted that feature; promote it into the approved base first.
- Don't hand off "the app is open" without identifying which build/window is under test.
- Instead use the relevant domain workflow for feature implementation itself, then return to this workflow when branch/worktree lineage or GUI handoff identity is at risk.

## Primary Files
- `agent.md`
- `docs/assistant/exec_plans/PLANS.md`
- `docs/assistant/runtime/CANONICAL_BUILD.json`
- `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
- `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md`
- `tooling/launch_qt_build.py`

## Minimal Commands
PowerShell:
```powershell
git status --short --branch
git rev-parse --short HEAD
git merge-base --is-ancestor <approved-base-sha> HEAD
git worktree list
```
POSIX:
```bash
git status --short --branch
git rev-parse --short HEAD
git merge-base --is-ancestor <approved-base-sha> HEAD
git worktree list
python ./tooling/launch_qt_build.py --worktree /abs/path/to/worktree --labels "feature-a,feature-b" --dry-run
```

## Targeted Tests
- `dart run test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- New worktree is based on the wrong SHA or does not contain the approved-base floor: stop feature work, transplant/rebase onto the approved baseline, then continue.
- A feature branch is the only branch with user-approved working functionality: promote/merge it into the approved base immediately before more feature work proceeds on other branches.
- Multiple app windows exist and the build is ambiguous: relaunch via `tooling/launch_qt_build.py` and use the emitted build identity packet instead of relying on memory or screenshots.
- A noncanonical build is launched without explicit intent: stop and relaunch via `tooling/launch_qt_build.py`; require `--allow-noncanonical` for source-only worktrees that still contain the approved-base floor.
- ExecPlan is missing provenance: update the active plan before more implementation or testing happens.

## Handoff Checklist
1. Lock the latest approved baseline before starting new parallel work:
   - branch name
   - base branch
   - exact base SHA
   - approved base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`
2. Create the new worktree from that baseline, not from an older integration branch.
3. Record this provenance in the active ExecPlan:
   - worktree path
   - branch name
   - base branch
   - base SHA
   - intended feature scope
   - target integration branch
4. Before GUI testing, identify the build under test:
   - repo/worktree path
   - branch
   - HEAD SHA
   - canonical vs noncanonical status
   - distinguishing feature set
5. In ambiguous multi-worktree GUI scenarios, use `tooling/launch_qt_build.py` and include the emitted build identity packet in the handoff.
6. Treat `docs/assistant/runtime/CANONICAL_BUILD.json` as the source of truth for the canonical runnable build.
7. Treat a feature branch as valid for testing only if it still contains the approved-base floor recorded in `docs/assistant/runtime/CANONICAL_BUILD.json`.
8. Once a feature is accepted, merge it into the approved base before starting the next unrelated feature branch.
9. Treat "open the app" as incomplete unless the opened window is tied to a specific build identity packet.
