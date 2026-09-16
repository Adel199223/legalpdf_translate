# DOCS_MAINTENANCE_WORKFLOW

## What This Workflow Is For
Maintaining assistant docs contracts with minimal drift and scoped updates.

## Standing Project Authorization
Standing user authorization (2026-09-16): perform useful Docs Sync autonomously. Do not ask again. Update only touched-scope docs; no blanket rewrites. Preserve history and exact beforeimages when replacing current guidance. Publication, destructive operations and live Gmail remain separately gated.

The project manifest records this autonomous mode and its dated user authorization. The validator checks that declared policy for consistency; it does not create user authority. Legacy template prompt mode remains a separate compatibility contract, not this project's current policy. This workflow does not invoke UCBS or vendored-template application.

## Expected Outputs
- Updated docs only for touched scope.
- Preserved canonical/bridge separation.
- Successful docs and workspace validators.

## When To Use
- Useful documentation needs synchronization under the standing user authorization.
- A deferred/batched docs-maintenance pass is being run after implementation work.
- Governance/workflow/manifest contracts change.
- User-guide support content needs synchronization with feature changes.
- A major debugging session exposed reusable workflow lessons that should not remain trapped only in active ExecPlans.

## What Not To Do
- Don't use this workflow when the change is a small isolated update that does not require broad docs sync.
- Don't force immediate docs sync after every major implementation change when immediate same-task synchronization is not necessary.
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
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
```
POSIX:
```bash
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
```

## Targeted Tests
- `dart test/tooling/validate_agent_docs_test.dart`
- `dart test/tooling/validate_workspace_hygiene_test.dart`

## Failure Modes and Fallback Steps
- Canonical/bridge drift: update canonical first, then bridge summaries.
- Manifest path/contract drift: patch manifest and rerun validators.
- User guide drift after major feature changes: update only relevant sections in app/primary guides.
- Repeated debugging pattern still lives only in an ExecPlan: harvest the reusable rule into a durable workflow/playbook doc before closing the thread.
- Wrong-base worktree or ambiguous build-under-test incident repeats: add or update a durable workflow/governance doc and route it through `INDEX.md` and `manifest.json` instead of leaving the lesson only in thread history.
- Accepted functionality still lives only on a side branch despite authorized promotion: keep governance docs aligned with merge-immediately-after-acceptance within the current authorized publication scope. Testing acceptance alone does not authorize publication.
- Ambiguous `commit` or `push` shorthand caused repeated git-hygiene mistakes: harden the commit/publish workflow docs and validator rules so the shorthand has fixed semantics instead of thread-local interpretation.
- Strong repeated issue signal appears during normal work: update `ISSUE_MEMORY.md` and `ISSUE_MEMORY.json` instead of leaving the pattern only in thread history or refresh notes.
- A reusable issue may affect bootstrap maintenance: mark its bootstrap relevance in issue memory and let `update codex bootstrap` / `UCBS` decide whether it generalizes.
- Repeated live-state contamination across tests and real runtime checks: promote the durable rule into `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md` instead of leaving it as one-off cleanup.
- Repeated fragmented diagnostics across handoff/run/finalization surfaces: promote the support-packet and session-artifact guidance into `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md` instead of scattering it across refresh notes.
- Merge/cleanup drift left stale roadmap continuity or stale active-plan inventory behind:
  - fix `docs/assistant/SESSION_RESUME.md`
  - archive clearly stale `docs/assistant/exec_plans/active/` entries
  - update publish/docs workflows so the same drift does not recur
- Scratch outputs from assistant tooling polluted Source Control:
  - move the default scratch path into an ignored location
  - update the workflow/playbook commands instead of relying on manual cleanup only
- Repeated immediate docs-sync prompts interrupt active implementation even though docs can wait:
  - defer it to a later docs-maintenance pass
  - record the gap in `DOCS_REFRESH_NOTES.md` instead of forcing same-pass sync

## Handoff Checklist
1. Apply the standing authorization to useful scoped maintenance; never require a fresh Docs Sync approval question.
2. If another bounded task or package freeze must finish first, record the gap in `DOCS_REFRESH_NOTES.md` and perform a later docs-maintenance pass.
3. Keep one current handoff and architecture/validation entry layer; move superseded operation detail into dated history with beforeimages instead of repeating it across front doors.
4. Update only touched-scope docs. Preserve current operation ownership and source/test freezes; documentation work is not authority to replay provider/native operations.
5. Ensure user guides stay discoverable in `INDEX.md` and `manifest.json`.
6. Sync relevant user-guide sections when major feature behavior changes.
7. Keep template read policy and routing protections intact.
8. For parallel docs threads, use worktree isolation.
9. If external behavior facts were used, update verification dates in `EXTERNAL_SOURCE_REGISTRY.md`.
10. If a debugging thread produced reusable runbooks, move the durable guidance into workflow/playbook docs instead of leaving it only in `exec_plans/active/`.
11. If the failure involved wrong-base worktrees or ambiguous app windows, sync the durable fix into governance docs and record the workflow lesson in `DOCS_REFRESH_NOTES.md`.
12. If the failure involved ambiguous `commit` or `push` shorthand, sync the durable default semantics into governance docs and validator rules instead of relying on thread memory.
13. If strong issue-memory signals appeared, update `ISSUE_MEMORY.md` and `ISSUE_MEMORY.json` during normal work and consult them during docs sync before widening touched-scope docs.
14. When docs sync scope overlaps a repeated issue, record whether the sync changed docs because of that issue-memory entry.
15. If the repeated issue involved live-state contamination or fragmented multi-surface diagnostics, update `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md` and route it through `INDEX.md` and `manifest.json`.
16. If merge/cleanup drift exposed stale continuity state, repair `docs/assistant/SESSION_RESUME.md`, active/completed ExecPlan lifecycle state, and the relevant cleanup workflow docs during the same sync pass.
