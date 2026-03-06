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

## Handoff Checklist
1. Ask exact prompt after significant implementation changes:
   - "Would you like me to run Assistant Docs Sync for this change now?"
2. If approved, update only touched-scope docs.
3. Ensure user guides stay discoverable in `INDEX.md` and `manifest.json`.
4. Sync relevant user-guide sections when major feature behavior changes.
5. Keep template read policy and routing protections intact.
6. For parallel docs threads, use worktree isolation.
7. If external behavior facts were used, update verification dates in `EXTERNAL_SOURCE_REGISTRY.md`.
8. If a debugging thread produced reusable runbooks, move the durable guidance into workflow/playbook docs instead of leaving it only in `exec_plans/active/`.
