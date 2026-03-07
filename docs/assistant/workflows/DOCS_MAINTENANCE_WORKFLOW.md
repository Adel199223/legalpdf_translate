# DOCS_MAINTENANCE_WORKFLOW

## What This Workflow Is For
Maintaining assistant docs contracts with minimal drift and scoped updates.

## Expected Outputs
- Updated docs only for touched scope.
- Preserved canonical/bridge separation.
- Successful docs and workspace validators.

## When To Use
- User approves docs sync.
- Governance/workflow/manifest contracts change.
- User-guide support content needs synchronization with feature changes.
- A major debugging session exposed reusable workflow lessons that should not remain trapped only in active ExecPlans.

## What Not To Do
- Don't use this workflow when the change is a small isolated update that does not require broad docs sync.
- Instead use selective updates to only impacted docs.

## Primary Files
- `APP_KNOWLEDGE.md`
- `docs/assistant/APP_KNOWLEDGE.md`
- `docs/assistant/manifest.json`
- `docs/assistant/INDEX.md`
- `docs/assistant/ISSUE_MEMORY.md`
- `docs/assistant/ISSUE_MEMORY.json`
- `docs/assistant/features/*.md`
- `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`

## Minimal Commands
PowerShell:
```powershell
dart run tooling/validate_agent_docs.dart
dart run tooling/validate_workspace_hygiene.dart
```
POSIX:
```bash
dart run tooling/validate_agent_docs.dart
dart run tooling/validate_workspace_hygiene.dart
```

## Targeted Tests
- `dart run test/tooling/validate_agent_docs_test.dart`
- `dart run test/tooling/validate_workspace_hygiene_test.dart`

## Failure Modes and Fallback Steps
- Canonical/bridge drift: update canonical first, then bridge summaries.
- Manifest path/contract drift: patch manifest and rerun validators.
- User guide drift after major feature changes: update only relevant sections in app/primary guides.
- Repeated debugging pattern still lives only in an ExecPlan: harvest the reusable rule into a durable workflow/playbook doc before closing the thread.
- Wrong-base worktree or ambiguous build-under-test incident repeats: add or update a durable workflow/governance doc and route it through `INDEX.md` and `manifest.json` instead of leaving the lesson only in thread history.
- Accepted functionality still lives only on a side branch: update governance docs so merge-immediately-after-acceptance remains the enforced default before more feature work proceeds.
- Ambiguous `commit` or `push` shorthand caused repeated git-hygiene mistakes: harden the commit/publish workflow docs and validator rules so the shorthand has fixed semantics instead of thread-local interpretation.
- Strong repeated issue signal appears during normal work: update `ISSUE_MEMORY.md` and `ISSUE_MEMORY.json` instead of leaving the pattern only in thread history or refresh notes.
- A reusable issue may affect bootstrap maintenance: mark its bootstrap relevance in issue memory and let `update codex bootstrap` / `UCBS` decide whether it generalizes.

## Handoff Checklist
1. Ask exact prompt after significant implementation changes only when relevant touched-scope docs still remain unsynced:
   - "Would you like me to run Assistant Docs Sync for this change now?"
2. If the relevant docs sync already ran during the same task/pass, do not ask the prompt again.
3. If approved, update only touched-scope docs.
4. Ensure user guides stay discoverable in `INDEX.md` and `manifest.json`.
5. Sync relevant user-guide sections when major feature behavior changes.
6. Keep template read policy and routing protections intact.
7. For parallel docs threads, use worktree isolation.
8. If external behavior facts were used, update verification dates in `EXTERNAL_SOURCE_REGISTRY.md`.
9. If a debugging thread produced reusable runbooks, move the durable guidance into workflow/playbook docs instead of leaving it only in `exec_plans/active/`.
10. If the failure involved wrong-base worktrees or ambiguous app windows, sync the durable fix into governance docs and record the workflow lesson in `DOCS_REFRESH_NOTES.md`.
11. If the failure involved ambiguous `commit` or `push` shorthand, sync the durable default semantics into governance docs and validator rules instead of relying on thread memory.
12. If strong issue-memory signals appeared, update `ISSUE_MEMORY.md` and `ISSUE_MEMORY.json` during normal work and consult them during docs sync before widening touched-scope docs.
13. When docs sync scope overlaps a repeated issue, record whether the sync changed docs because of that issue-memory entry.
