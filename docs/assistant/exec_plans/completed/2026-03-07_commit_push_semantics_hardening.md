# Commit/Push Semantics Hardening

## Goal and Non-Goals
- Goal: lock shorthand `commit` and `push` semantics in governance docs and validators so future git-hygiene behavior is deterministic.
- Non-goals: product code changes, PR creation, or branch cleanup during this docs-only pass.

## Scope
- In scope:
  - `agent.md`
  - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/exec_plans/PLANS.md`
  - `docs/assistant/DOCS_REFRESH_NOTES.md`
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`
- Out of scope:
  - product feature code
  - feature docs unrelated to git workflow semantics

## Worktree Provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `4e9d20e`
- Target integration branch: `feat/ai-docs-bootstrap`
- Canonical build status: canonical repo-root worktree; no noncanonical override required

## Interfaces / Contracts Affected
- Shorthand command contract:
  - bare `commit`
  - bare `push`
- Docs validator contract:
  - required governance docs must mention hardened shorthand semantics

## File-by-File Steps
1. Update `agent.md` with concise shorthand defaults for bare `commit` and bare `push`.
2. Make `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md` decision-complete for full pending-tree triage, grouped commits, immediate push suggestion, and Push+PR+Merge+Cleanup defaults.
3. Update `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md` and `docs/assistant/exec_plans/PLANS.md` so shorthand git semantics are treated as durable governance defaults.
4. Append a narrow governance entry to `docs/assistant/DOCS_REFRESH_NOTES.md`.
5. Extend `tooling/validate_agent_docs.dart` and `test/tooling/validate_agent_docs_test.dart` to enforce the new shorthand semantics.

## Tests and Acceptance Criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- Acceptance:
  - required governance docs define bare `commit` and bare `push`
  - validator fails if those semantics are removed

## Rollout and Fallback
- Rollout is docs/governance only.
- If wording proves too rigid for validator coverage, tighten or relax marker phrases without changing the underlying default semantics.

## Risks and Mitigations
- Risk: shorthand semantics conflict with narrower user requests.
  - Mitigation: docs must state explicit narrower wording overrides the defaults.
- Risk: drift back into ad hoc behavior.
  - Mitigation: validator enforcement plus refresh-note record.

## Assumptions and Defaults
- Bare `commit` means full pending-tree triage plus logical grouped commits.
- Bare `push` means Push+PR+Merge+Cleanup by default.
- Narrower user wording overrides the defaults.
