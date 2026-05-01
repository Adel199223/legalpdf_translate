# FEATURE_WORKFLOW (Compatibility Shim)

## What This Workflow Is For
Compatibility entrypoint for template-generic feature workflow routing.

## Expected Outputs
- Same outputs as canonical translation workflow.

## When To Use
Use only when a template/tool requests `FEATURE_WORKFLOW.md`.

## What Not To Do
- Don't use this workflow when directly authoring translation workflow changes.
- Instead use `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`.

## Primary Files
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`

## Minimal Commands
PowerShell:
```powershell
dart tooling/validate_agent_docs.dart
```
POSIX:
```bash
dart tooling/validate_agent_docs.dart
```

## Targeted Tests
- `dart test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- Shim mismatch: update this shim to point to canonical translation workflow.

## Handoff Checklist
1. Confirm canonical workflow link resolves.
2. Confirm manifest routes both generic and domain paths correctly.
