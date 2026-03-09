# DATA_WORKFLOW (Compatibility Shim)

## What This Workflow Is For
Compatibility entrypoint for template-generic data workflow routing.

## Expected Outputs
- Same outputs as canonical persistence/data workflow.

## When To Use
Use only when a template/tool requests `DATA_WORKFLOW.md`.

## What Not To Do
- Don't use this workflow when implementing persistence changes directly.
- Instead use `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`.

## Primary Files
- `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`

## Minimal Commands
PowerShell:
```powershell
dart run tooling/validate_agent_docs.dart
```
POSIX:
```bash
dart run tooling/validate_agent_docs.dart
```

## Targeted Tests
- `dart run test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- Shim mismatch: update this shim to point to canonical persistence workflow.

## Handoff Checklist
1. Confirm canonical workflow link resolves.
2. Confirm manifest routes both generic and domain paths correctly.
