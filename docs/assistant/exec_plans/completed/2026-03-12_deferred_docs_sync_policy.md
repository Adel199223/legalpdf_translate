# ExecPlan: Deferred Docs Sync Policy

## Goal and non-goals
- Goal: change the project and bootstrap governance so Assistant Docs Sync is deferred by default after major implementation work unless immediate same-task synchronization is actually required.
- Goal: preserve the exact docs-sync prompt for the cases where it is still appropriate.
- Non-goal: change app/product behavior.
- Non-goal: broaden into unrelated governance cleanup.

## Scope (in/out)
- In scope:
  - project runbooks and docs-maintenance policy
  - machine-readable manifest contract text
  - bootstrap template contract/policy docs
  - validator/test coverage for the new deferred-default rule
- Out of scope:
  - app source code
  - user-facing product guides unrelated to docs-sync governance
  - publish or release steps

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/deferred-docs-sync-policy`
- Base branch: `main`
- Base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`
- Canonical build status: no GUI/runtime build change; docs-governance-only pass

## Interfaces/types/contracts affected
- Assistant Docs Sync prompt policy in:
  - `AGENTS.md`
  - `agent.md`
  - `docs/assistant/GOLDEN_PRINCIPLES.md`
  - `docs/assistant/PROJECT_INSTRUCTIONS.txt`
  - `docs/assistant/UPDATE_POLICY.md`
  - `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
  - `docs/assistant/manifest.json`
- Bootstrap propagation surface in:
  - `docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md`
  - `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
  - `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
- Enforcement surface in:
  - `tooling/validate_agent_docs.dart`
  - `test/tooling/validate_agent_docs_test.dart`

## File-by-file implementation steps
1. Update the project-local policy docs so they say:
   - defer docs sync by default when immediate sync is not necessary
   - use the exact prompt only when relevant docs remain unsynced and immediate same-task sync is required
   - batch deferred docs sync later via a dedicated docs-maintenance pass
2. Update manifest contract text so machine-readable governance matches the human docs.
3. Update bootstrap template docs so future harness sync/bootstrap maintenance keeps the same deferred-default behavior.
4. Update validator/test expectations so the new policy cannot silently drift.

## Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
- Acceptance:
  - validators pass
  - prompt string remains exact where applicable
  - docs explicitly permit deferred/batched docs sync
  - immediate-sync wording is limited to necessary same-task cases

## Executed validation and outcomes
- `dart run tooling/validate_agent_docs.dart` -> passed
- `dart run tooling/validate_workspace_hygiene.dart` -> passed
- `dart run test/tooling/validate_agent_docs_test.dart` -> passed
- `python -m compileall src tests` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q` -> passed (`882 passed`)

## Rollout and fallback
- Rollout: land as a narrow governance/docs branch.
- Fallback: if validator coupling is broader than expected, tighten the wording while preserving the deferred-default semantics.

## Risks and mitigations
- Risk: policy text drifts between runbooks, workflow docs, manifest, and bootstrap templates.
- Mitigation: update all surfaces in one pass and run validator/test coverage.
- Risk: the new rule becomes too vague and weakens required same-task governance updates.
- Mitigation: keep explicit immediate-sync exceptions for governance-sensitive or closeout-required cases.

## Assumptions/defaults
- The user is referring to Assistant Docs Sync, not product runtime behavior.
- End-of-day or later batched docs maintenance is acceptable as long as deferred work is recorded and immediate-sync exceptions remain explicit.
