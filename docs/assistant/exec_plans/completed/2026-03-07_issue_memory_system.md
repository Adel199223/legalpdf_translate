# ExecPlan: Issue Memory System

## Goal
Add a per-project issue memory registry that captures repeated workflow/product issues and feeds both Assistant Docs Sync and `update codex bootstrap` / `UCBS`.

## Non-Goals
- Do not turn issue memory into a full incident log or thread transcript.
- Do not generalize every local issue into the global bootstrap.
- Do not change product behavior.

## Scope
### In
- `docs/assistant/ISSUE_MEMORY.md`
- `docs/assistant/ISSUE_MEMORY.json`
- docs-maintenance and bootstrap-maintenance workflow wiring
- validator enforcement
- seeded initial repeated issue entry for wrong-build/wrong-window launches

### Out
- product code changes
- broad user-guide rewrites
- automated issue-memory generation from threads

## Worktree Provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/ai-docs-bootstrap`
- base branch: `feat/ai-docs-bootstrap`
- base SHA: `1d63121`
- target integration branch: `feat/ai-docs-bootstrap`
- canonical build status: canonical approved-base worktree

## Interfaces / Contracts Affected
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
- `tooling/validate_agent_docs.dart`
- `test/tooling/validate_agent_docs_test.dart`
- `docs/assistant/manifest.json`

## File-by-File Implementation Steps
1. Add `ISSUE_MEMORY.md` as the concise human-readable registry.
2. Add `ISSUE_MEMORY.json` as the machine-readable registry with required fields.
3. Update docs maintenance workflow to require issue-memory updates/consultation.
4. Update bootstrap update policy so `update codex bootstrap` consumes only generalized issue-memory entries.
5. Update routing/index/manifest where needed so issue memory is discoverable and contractual.
6. Extend docs validator and validator tests for file presence and required issue-memory semantics.
7. Seed the repeated wrong-build/wrong-window issue entry.

## Tests and Acceptance Criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- validator fails if issue-memory files are missing or malformed
- docs-maintenance and bootstrap policy both reference issue memory correctly

## Rollout and Fallback
- keep issue memory local to the project first
- let `UCBS` decide what generalizes into the bootstrap
- if the structure proves too verbose, trim entries instead of removing the registry

## Risks and Mitigations
- Risk: issue memory becomes a narrative dump
  - Mitigation: keep required fields concise and validator-driven
- Risk: every minor friction point gets escalated
  - Mitigation: operational triggers first, wording triggers second
- Risk: bootstrap gets polluted with local quirks
  - Mitigation: only `possible`/`required` entries with repeats or regressions feed `UCBS`

## Assumptions / Defaults
- markdown + JSON is the right balance
- issue memory is always on, but only for meaningful issue classes
- `DOCS_REFRESH_NOTES.md` remains evidence/history, not the reusable issue registry
