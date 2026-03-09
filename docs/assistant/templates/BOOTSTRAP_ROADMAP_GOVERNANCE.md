# Bootstrap Roadmap Governance

## What This Module Is For
This module adds adaptive roadmap governance to generated project harnesses for complex work that needs more than a single ExecPlan.

Use it to generate one consistent system for:
- deciding when roadmap mode is justified
- keeping fresh-session resume safe through one roadmap anchor file
- preserving live-state authority during active worktree execution
- handling detours and roadmap closeout without relying on chat memory

## Activation Rule
Activate this module only when at least one of these is true:
- the work is likely to span multiple waves or PRs
- fresh-session resume continuity is required
- detours and return-to-sequence handling are likely
- separate worktrees or parallel feature isolation are likely
- the work coordinates multiple product surfaces
- the user explicitly asks for a roadmap or master plan

Do not activate it by default for:
- single-file fixes
- narrow bug fixes
- small UI text tweaks
- one-shot docs cleanup
- bounded multi-file work that can safely land as one merge

For bounded major work, prefer ExecPlan-only instead of roadmap mode.

## Terminology
- `roadmap`: a multi-wave or stage-plus-wave program for a complex improvement
- `master plan`: equivalent to `roadmap`
- `wave`: one implementation slice inside a roadmap
- `stage`: an optional research/specification phase before implementation
- `ExecPlan`: the execution plan for either a roadmap wave or a standalone major task

## Generated Harness Artifacts
When this module is activated, generated repos should include:
- `docs/assistant/workflows/ROADMAP_WORKFLOW.md`
- `docs/assistant/SESSION_RESUME.md`
- an active roadmap tracker in `docs/assistant/exec_plans/active/`
- an active wave ExecPlan in `docs/assistant/exec_plans/active/`

Generated manifest/routing docs should also point fresh sessions to:
- `docs/assistant/SESSION_RESUME.md`

`docs/assistant/SESSION_RESUME.md` is the roadmap anchor file and the stable resume anchor for fresh sessions.

## Generated Routing Rules
Generated repos should route fresh resume intent like this:
- open `docs/assistant/SESSION_RESUME.md` first
- use `resume master plan` as the explicit trigger phrase
- also route equivalent intents like:
  - `where did we leave off`
  - `what is the next roadmap step`
- after `docs/assistant/SESSION_RESUME.md`, open:
  1. the linked active roadmap tracker
  2. the linked active wave ExecPlan

## Artifact Authority Rule
Generated repos should document one authority model:
- `docs/assistant/SESSION_RESUME.md` is the roadmap anchor file and stable first resume stop
- the active roadmap tracker is the sequence source
- the active wave ExecPlan is the implementation-detail source
- issue memory is only for repeatable governance/workflow failures, not normal roadmap history

Generated repos should also allow the active roadmap tracker to resequence future stages or waves when new discoveries, blockers, or detours force a better order.

If a wave is active in a separate worktree:
- that worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan are authoritative for live roadmap state
- `main` remains the stable merged baseline, not the live source of in-progress wave state

## Update Order Rule
Generated repos using this module should require this update order after roadmap changes or detours:
1. active wave ExecPlan
2. active roadmap tracker
3. `docs/assistant/SESSION_RESUME.md`

Resume from `docs/assistant/SESSION_RESUME.md` unless the active roadmap tracker explicitly records a new sequence.

## Closeout Rule
Generated repos using this module should require roadmap closeouts to report:
- current roadmap status
- exact next step

If research stages are already complete, closeout wording should allow:
- `All research stages are complete; implementation continues by wave.`

If the next action is a closeout step instead of a new wave, the closeout should say that explicitly.

## Generalization Rule
This module must stay universal.

Do not encode:
- app-specific dates
- branch names
- tracker filenames
- domain-specific feature names
- project-specific roadmap history

Only encode reusable governance/process patterns that can be applied to future apps.

## Reusable Issue Classes
Do not seed these as live incidents in generated repos.
Treat them as valid reusable issue classes that future generated repos may record if they actually occur:
- `roadmap_trigger_granularity_ambiguity`
- `active_worktree_resume_authority_confusion`
- `roadmap_resume_state_fragmentation_across_trackers`
- `user_support_guide_density_after_multi_wave_growth`

Environment-specific issues like local Flutter lockfile churn or test bootstrap races should stay examples of local workflow issues, not universal roadmap defaults.
