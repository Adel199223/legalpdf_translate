# agent.md

Operational runbook for coding agents in `legalpdf_translate`.

## Canonical Precedence
1. `APP_KNOWLEDGE.md` is canonical for app-level architecture and status.
2. `docs/assistant/APP_KNOWLEDGE.md` is a bridge summary and must defer to canonical.
3. Source code is final truth when docs conflict.

## Daily Flow
1. Route task via `docs/assistant/INDEX.md` and `docs/assistant/manifest.json`.
2. Choose the correct workflow document in `docs/assistant/workflows/`.
3. Run targeted tests first, then full regression if required by workflow.
4. Keep changes scoped; avoid unrelated edits.

## Approval Gates
Ask before executing any of the following:
1. Destructive operations.
2. Risky DB/schema operations.
3. Force-push/history rewrite.
4. Publish/release/deploy.
5. Non-essential external network actions.

## ExecPlans
- ExecPlans are mandatory for major or multi-file work.
- Create plan files in `docs/assistant/exec_plans/active/` using `docs/assistant/exec_plans/PLANS.md`.
- Move completed plans to `docs/assistant/exec_plans/completed/`.

## Worktree Isolation
- Use `git worktree` for parallel streams.
- Keep `main` stable.
- Major work must start on `feat/<scope-name>`.
- Parallel feature work must branch/worktree from the latest approved baseline, not an older convenient branch.
- The approved base branch and floor commit are defined in `docs/assistant/runtime/CANONICAL_BUILD.json`; do not start a new feature branch unless it contains that approved-base floor.
- Before major parallel work starts, lock and record:
  - branch name
  - base branch
  - base SHA
  - worktree path
- If multiple worktrees or visible app windows can exist, use `tooling/launch_qt_build.py` instead of an ad hoc Qt launch command.
- The canonical runnable build is defined by `docs/assistant/runtime/CANONICAL_BUILD.json`; default GUI handoffs must target that canonical build.
- GUI handoffs must identify the exact build under test:
  - repo/worktree path
  - branch
  - HEAD SHA
  - canonical vs noncanonical status
  - distinguishing feature set
- Treat "the app is open" as incomplete unless it is tied to the emitted build identity packet from `tooling/launch_qt_build.py`.
- Once a feature is accepted in testing, merge it into the approved base immediately before starting the next unrelated feature branch.
- Treat "accepted feature still living only on a side branch" as a workflow violation until it is promoted into the approved base.
- Apply worktree guidance in CI/repo, commit/publish, and docs-maintenance workflows.

## Support Routing
For support and non-technical explanation tasks, start with user guides:
1. `docs/assistant/features/APP_USER_GUIDE.md`
2. `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`

Use the support response shape:
- plain explanation -> numbered steps -> canonical check -> uncertainty note

## Commit/Publish Routing
Never handle commit requests blindly.
Always follow `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`.

## Project Harness Routing
- If the user says `implement the template files` or `sync project harness`, follow `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`.
- If the user says `audit project harness` or `check project harness`, use the same workflow in audit/validation-only mode.
- Local harness application must read vendored templates as source input and must not edit `docs/assistant/templates/*`.
- `update codex bootstrap` and `UCBS` are reserved for maintaining the reusable template system itself, not for project-local harness sync.

## Roadmap Resume Routing
- If the user says `resume master plan`, `where did we leave off`, or `what is the next roadmap step`, open `docs/assistant/SESSION_RESUME.md` first.
- After `docs/assistant/SESSION_RESUME.md`, open the linked active roadmap tracker and then the linked active wave ExecPlan.
- `docs/assistant/SESSION_RESUME.md` is the stable roadmap anchor file for fresh sessions.
- During active work in a separate worktree, that worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan are authoritative for live roadmap state.

## Commit/Push Shorthand Defaults
- When the user says `commit` without narrowing scope:
  - inspect the full pending Source Control tree first
  - triage modified, staged, untracked, and temp artifacts
  - decide what belongs in git vs what should be removed or ignored
  - split the result into logical grouped commits, not convenience commits
  - do not leave unrelated pending changes unreviewed
  - immediately suggest push after the commit sequence is complete
- When the user says `push` without narrowing scope:
  - treat it as approval for the standard branch lifecycle in this repo:
    - push the correct branch
    - create or update the PR
    - wait for green required checks
    - merge if clean
    - delete the merged source branch when appropriate
    - prune refs and remove stale local branch state when safe
  - stop before merge only if blocked by red checks, merge conflicts, or a higher-priority approval gate
- If the user narrows scope explicitly, such as `commit only these files` or `push branch only`, follow that narrower instruction instead of the default lifecycle.

## Inspiration/Parity Routing
If a user asks for behavior "like X", "same as X", "closest to X", or explicit parity with a named product/site/app, run `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md` before implementation decisions.

## OpenAI Docs + Citation Routing
If a task depends on OpenAI products/APIs, date-sensitive external facts, or unstable limits/pricing behavior:
1. Use `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`.
2. Prefer official primary sources.
3. Include source links and explicit verification dates (`YYYY-MM-DD`) for material external decisions.

## Browser/Cloud Module Routing
- Browser automation reliability/provenance tasks -> `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- Cloud-heavy machine evaluation tasks -> `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`

## Stage-Gate Protocol
For risk-triggered complex work:
1. Follow `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`.
2. Stop at each stage and publish the required stage packet schema.
3. Require exact continuation token format: `NEXT_STAGE_X`.

## Docs Sync Policy
After significant implementation changes, ask exactly:
"Would you like me to run Assistant Docs Sync for this change now?"

Ask it only when relevant touched-scope docs still remain unsynced.
If the relevant docs sync already ran during the same task/pass, do not ask again.
If approved, update only the relevant docs for touched scope.
