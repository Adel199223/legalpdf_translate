# CODEX Project Bootstrap Prompt (Entrypoint)

## Purpose
This file is the canonical entrypoint for bootstrapping a new Codex-managed project or upgrading an existing repo harness.

It is intentionally small. Detailed policy now lives in read-on-demand sub-bootstrap files under `docs/assistant/templates/`.

## Read Policy
- `docs/assistant/templates/*` is read-on-demand only.
- Load only the sub-bootstrap files required by the project and its triggers.
- Do not bulk-load every template file by default unless the task is to refactor the bootstrap system itself.
- Template maintenance is protected work. Do not edit `docs/assistant/templates/*` during normal project work unless the user explicitly invokes a canonical bootstrap maintenance trigger from `BOOTSTRAP_UPDATE_POLICY.md`.

## Bootstrap Execution Order
1. Read this entrypoint.
2. Read `BOOTSTRAP_TEMPLATE_MAP.json`.
3. Load `BOOTSTRAP_CORE_CONTRACT.md`.
4. Load `BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`.
5. Load `BOOTSTRAP_MODULES_AND_TRIGGERS.md`.
6. If the task is bootstrap maintenance, load `BOOTSTRAP_UPDATE_POLICY.md` and follow its trigger semantics.
7. If bootstrap maintenance is active, inspect `docs/assistant/ISSUE_MEMORY.md` and `docs/assistant/ISSUE_MEMORY.json` and use only generalized issue entries marked `possible` or `required`.
8. Activate additional sub-bootstrap files only when their trigger conditions apply.
9. Generate or update the project harness.
10. Run validator coverage so the harness cannot silently drift.

## Template Files
- `BOOTSTRAP_CORE_CONTRACT.md`: universal governance, docs architecture, shorthand workflow semantics, OpenAI freshness routing.
- `BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`: always-on issue memory generation, capture triggers, docs-sync wiring, and bootstrap filtering.
- `BOOTSTRAP_MODULES_AND_TRIGGERS.md`: optional module trigger matrix and staged-execution behavior.
- `BOOTSTRAP_LOCAL_ENV_OVERLAY.md`: machine-local overlay for host profile and Windows/WSL routing.
- `BOOTSTRAP_CAPABILITY_DISCOVERY.md`: dynamic skill, MCP, and local-tool discovery.
- `BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md`: approved baseline, worktree provenance, canonical runnable build, build-under-test identity.
- `BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md`: host-bound integration preflight and same-host validation.
- `BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md`: test isolation from live state, listener ownership checks, and durable app-owned session diagnostics for multi-surface workflows.
- `BOOTSTRAP_UPDATE_POLICY.md`: protected bootstrap-maintenance policy and canonical update triggers.
  - accepted shorthand alias: `UCBS` for `update codex bootstrap`

## Trigger Matrix
| Need | Load These Modules |
|---|---|
| Every project | `BOOTSTRAP_CORE_CONTRACT.md`, `BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`, `BOOTSTRAP_MODULES_AND_TRIGGERS.md` |
| Personal machine or dual-host optimization | `BOOTSTRAP_LOCAL_ENV_OVERLAY.md` |
| Skills, MCPs, or local tools may change workflows | `BOOTSTRAP_CAPABILITY_DISCOVERY.md` |
| Runnable app/GUI project or explicit parallel-worktree risk | `BOOTSTRAP_WORKTREE_BUILD_IDENTITY.md` |
| Local auth / browser / CLI integration is in scope | `BOOTSTRAP_HOST_INTEGRATION_PREFLIGHT.md` |
| Host-bound workflows span more than one failure surface, or tests can collide with live machine state | `BOOTSTRAP_HARNESS_ISOLATION_AND_DIAGNOSTICS.md` |
| The user explicitly wants to maintain the global Codex bootstrap harness | `BOOTSTRAP_UPDATE_POLICY.md` |

## Compact Master Prompt (Copy/Paste)
```md
You are bootstrapping a new project harness.

Read `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json` first.
Then load:
- `docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md`
- `docs/assistant/templates/BOOTSTRAP_ISSUE_MEMORY_SYSTEM.md`
- `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`

After reading those two files, decide which optional sub-bootstrap files are needed for this project. Load only the relevant ones.

Build a deterministic AI-first project harness that includes:
- canonical + bridge documentation
- machine-readable routing in `docs/assistant/manifest.json`
- validator tooling and tests
- `docs/assistant/ISSUE_MEMORY.md` and `docs/assistant/ISSUE_MEMORY.json` as standard generated project files
- explicit approval gates, ExecPlan rules, docs-sync policy, and worktree isolation
- shorthand semantics where bare `commit` means full pending-tree triage plus logical grouped commits and immediate push suggestion
- shorthand semantics where bare `push` means Push+PR+Merge+Cleanup unless the user explicitly narrows scope
- official-doc freshness routing for unstable OpenAI facts

If the project is being bootstrapped for a specific personal machine, encode that in a local environment overlay, not in the universal core contract.
If skills, MCPs, or local tools may affect workflows, dynamically discover and record them instead of hardcoding stale assumptions.
If local host/auth integrations are in scope, require installation, auth, same-host validation, and a live smoke check before building the feature.
If host-bound workflows span more than one failure surface, or tests could collide with live user state, require test isolation from live settings/ports, visible listener-conflict handling, and one durable app-owned session artifact for multi-stage diagnostics.
Issue memory should be generated by default in every project harness and used for Assistant Docs Sync and generalized bootstrap maintenance decisions.
If the project has a runnable app, GUI, local desktop workflow, or explicit multi-worktree testing risk, automatically activate the worktree/build identity protections and require latest-approved-baseline locking, worktree provenance, a canonical runnable build, merge-immediately-after-acceptance discipline, and build-under-test identity packets.
If the task is maintaining the global Codex bootstrap harness itself, load `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md` and follow its canonical triggers instead of assuming generic docs maintenance behavior.
When bootstrap maintenance is active, consult `docs/assistant/ISSUE_MEMORY.md` and `docs/assistant/ISSUE_MEMORY.json` but promote only generalized lessons whose bootstrap relevance is `possible` or `required`.
`UCBS` is an accepted shorthand alias for `update codex bootstrap`, but the long form remains canonical.

Return:
1. changed/added files
2. the selected module set and why
3. validator commands and results
4. assumptions and dated external facts
5. any generated local-overlay or capability-inventory recommendations
```

## Design Rules
- Keep the bootstrap general for new apps.
- Generate issue memory as a standard subsystem for every project.
- Use optional overlays for personal machine facts.
- Prefer dynamic capability discovery over hardcoded skills or MCP assumptions.
- Generalize repeated workflow failures only where they become reusable rules, and prefer prevention rules over seeding fake project incidents.
- Prefer harness isolation and durable session diagnostics over ad hoc debugging guidance when a project spans multiple host-bound failure surfaces.
- Preserve existing strong governance, stage-gates, docs-sync policy, and validator-first behavior.

## Maintenance Rule
If the template system changes materially, update both:
- the entrypoint/template map
- validator coverage that proves the template system is still self-consistent
- the bootstrap-specific update policy when maintenance semantics or protected-surface rules change
