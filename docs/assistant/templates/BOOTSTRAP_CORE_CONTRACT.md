# Bootstrap Core Contract

## What This Module Is For
This is the universal, project-agnostic contract layer for new Codex-managed repositories.

It defines the minimum governance, documentation architecture, validation rules, and shorthand workflow semantics that should be inherited by new projects unless a project has a documented reason to opt out.

## Required Architecture
Create or update these core artifacts in new projects:
- `AGENTS.md` as a short compatibility shim
- `agent.md` as the operational runbook
- `APP_KNOWLEDGE.md` as the canonical architecture/status document
- `README.md` with entry links
- `docs/assistant/APP_KNOWLEDGE.md` as the bridge to canonical app knowledge
- `docs/assistant/INDEX.md` as the human routing index
- `docs/assistant/manifest.json` as the machine routing map
- `docs/assistant/ISSUE_MEMORY.md` as the human-readable project issue registry
- `docs/assistant/ISSUE_MEMORY.json` as the machine-readable project issue registry
- `docs/assistant/GOLDEN_PRINCIPLES.md`
- `docs/assistant/exec_plans/PLANS.md`
- `docs/assistant/exec_plans/active/.gitkeep`
- `docs/assistant/exec_plans/completed/.gitkeep`
- at least one docs validator under `tooling/`
- validator tests under `test/tooling/`

## Canonical and Bridge Rules
- `APP_KNOWLEDGE.md` is canonical for app-level architecture and status.
- Bridge docs must be intentionally shorter and defer to canonical docs.
- Source code remains final truth when docs and code disagree.
- The bootstrap should generate routing, not duplicate the same operational text in many files.

## Approval and Safety Rules
- Approval gates remain mandatory for destructive operations, history rewrites, risky DB work, deploy/release, and non-essential external network actions.
- Major or multi-file work requires an ExecPlan.
- Parallel work requires explicit branch/worktree isolation.
- After significant implementation changes, generated repos must keep the exact docs-sync prompt:
  - `Would you like me to run Assistant Docs Sync for this change now?`
- Generated repos must ask that prompt only when relevant touched-scope docs still remain unsynced.
- If the relevant docs sync already ran during the same task/pass, generated repos must not ask the prompt again.

## Commit and Push Shorthand Defaults
These are default meanings unless the user narrows scope explicitly.

### Bare `commit`
Treat `commit` as a full pending-tree triage command:
- inspect modified tracked files, staged files, untracked files, and temp artifacts
- decide what belongs in git and what should be removed or ignored
- split the result into logical grouped commits
- avoid mixing unrelated scopes like product code, docs, tooling, and tests without a concrete reason
- validate each commit scope before committing
- immediately suggest push when the commits are complete

### Bare `push`
Treat `push` as Push+PR+Merge+Cleanup:
- push the correct branch
- create or update the PR
- ensure the latest SHA is under review
- wait for required checks or CI
- merge when green and clean
- delete the merged source branch when appropriate
- prune refs and remove stale local branch state when safe
- stop before merge only when blocked by red checks, conflicts, approval gates, or review blockers

### Override Rule
If the user says `commit only these files`, `push branch only`, or otherwise narrows scope, follow the narrower scope instead of the default lifecycle.

## OpenAI / Codex Freshness Rule
OpenAI-specific behavior is temporally unstable and must be routed through official docs.

As of 2026-03-07, current official OpenAI docs indicate:
- GPT-5.4 powers Codex and Codex CLI
- GPT-5.4 supports configurable reasoning effort including `xhigh`

These facts are dated assumptions, not permanent invariants.
Generated repos should route all unstable OpenAI product/API behavior through official OpenAI docs or the `openai-docs` capability when available.

## Output Contract For New Repos
A generated bootstrap should always leave the new repo with:
- one canonical app knowledge path
- one bridge/routing model
- one always-on issue memory subsystem
- one validator path
- one commit/publish workflow
- one docs maintenance workflow
- explicit approval gates and ExecPlan policy
- explicit commit/push shorthand semantics
- explicit OpenAI docs freshness routing
