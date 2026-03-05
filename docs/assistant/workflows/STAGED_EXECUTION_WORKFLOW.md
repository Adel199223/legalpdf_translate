# STAGED_EXECUTION_WORKFLOW

## What This Workflow Is For
Enforcing hard stage-gate execution for risk-triggered complex tasks.

## Expected Outputs
- Stage-by-stage execution packets with evidence.
- Locked decisions and explicit carry-forward assumptions.
- Exact continuation-token gating between stages.

## When To Use
- Multi-surface complexity with medium/high workflow risk.
- External API/cost risk with optimization/research scope.
- Any task where at least two stage-gate triggers are true.

## What Not To Do
- Don't use this workflow when the task is a simple, low-risk, single-surface change.
- Instead use the relevant domain workflow directly.

## Primary Files
- `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`
- `docs/assistant/manifest.json`
- `docs/assistant/exec_plans/active/*.md`

## Minimal Commands
PowerShell:
```powershell
git status --short --branch
dart run tooling/validate_agent_docs.dart
```
POSIX:
```bash
git status --short --branch
dart run tooling/validate_agent_docs.dart
```

## Targeted Tests
- `dart run test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- Stage drift discovered late: re-adapt next-stage prompt pack before proceeding.
- Missing evidence packet fields: block stage completion and regenerate packet.
- Incorrect continuation token format: reject and request exact `NEXT_STAGE_X` phrase.

## Handoff Checklist
1. Stop at stage boundary and publish stage packet schema fields.
2. Include changed files, validations, risks, and decision locks.
3. Include prepared prompt pack for next two stages.
4. Require exact continuation token format: `NEXT_STAGE_X` (example: `NEXT_STAGE_2`).
