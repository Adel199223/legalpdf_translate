# Worktree Workspace Docs Sync

## Goal and non-goals
- Goal:
  - Sync assistant docs for the new local worktree workspace organization and the resulting repeated support-routing lesson.
- Non-goals:
  - No source-code changes.
  - No branch/worktree topology changes.
  - No commit/push unless explicitly requested.

## Scope (in/out)
- In:
  - update touched-scope routing docs so the new worktree workspace guide is discoverable where agents actually route support
  - update issue memory for the repeated worktree/workspace confusion signal from this pass
  - validate docs/workspace hygiene
- Out:
  - unrelated product docs refresh
  - broad governance rewrites

## Worktree provenance
- worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- branch name: `feat/ai-docs-bootstrap`
- base branch: `origin/feat/ai-docs-bootstrap`
- base SHA: `73261de`
- target integration branch: `main`
- canonical build status: canonical approved-base worktree for docs-only maintenance

## Interfaces/types/contracts affected
- Assistant docs routing:
  - `docs/assistant/APP_KNOWLEDGE.md`
- Repeated-issue registry:
  - `docs/assistant/ISSUE_MEMORY.md`
  - `docs/assistant/ISSUE_MEMORY.json`

## File-by-file implementation steps
- `docs/assistant/APP_KNOWLEDGE.md`
  - add support-routing entry for local worktree/workspace organization questions
- `docs/assistant/ISSUE_MEMORY.md`
  - update the mixed-worktree confusion entry with this pass as new evidence and mitigation
- `docs/assistant/ISSUE_MEMORY.json`
  - mirror the human-readable issue-memory update in machine-readable form

## Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- acceptance:
  - new workspace guide is routed from assistant bridge docs
  - issue memory reflects this repeated local support issue
  - docs validators pass

## Rollout and fallback
- Rollout is immediate because these are assistant docs only.
- If a docs validator fails, patch only the specific touched-scope docs until validation is green.

## Risks and mitigations
- Risk: broadening docs scope unnecessarily.
  - Mitigation: patch only routing + issue-memory surfaces directly touched by this pass.

## Assumptions/defaults
- The new user-facing workspace guide itself is already committed.
- This sync pass should remain uncommitted unless the user later asks for another commit.

## Validation log
- Updated `docs/assistant/APP_KNOWLEDGE.md` so local worktree/workspace organization questions route to the new user guide first.
- Updated `docs/assistant/ISSUE_MEMORY.md` and `docs/assistant/ISSUE_MEMORY.json` to record the repeated mixed-worktree confusion signal from this pass and the new workspace-guide mitigation.
- `dart run tooling/validate_agent_docs.dart` -> PASS.
- `dart run tooling/validate_workspace_hygiene.dart` -> PASS.
