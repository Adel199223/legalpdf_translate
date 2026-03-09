# LOCALIZATION_WORKFLOW

## What This Workflow Is For
Managing localization terminology consistency and localized behavior contracts.

## Expected Outputs
- Localization updates aligned with glossary source-of-truth.
- Updated localization-sensitive docs/tests as needed.
- Validation run for localization scope.

## When To Use
- Changing localization term policy.
- Adjusting localized prompts/messages/contracts.
- Auditing localization routing contracts.

## What Not To Do
- Don't use this workflow when performance tuning is the primary task.
- Instead use `docs/assistant/workflows/PERFORMANCE_WORKFLOW.md`.

## Primary Files
- `docs/assistant/LOCALIZATION_GLOSSARY.md`
- `docs/assistant/manifest.json`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`

## Minimal Commands
PowerShell:
```powershell
dart run tooling/validate_agent_docs.dart --scope localization
dart run tooling/validate_agent_docs.dart
```
POSIX:
```bash
dart run tooling/validate_agent_docs.dart --scope localization
dart run tooling/validate_agent_docs.dart
```

## Targeted Tests
- `dart run test/tooling/validate_agent_docs_test.dart`

## Failure Modes and Fallback Steps
- Term drift across docs: update glossary first, then relink dependent docs.
- Missing localization contract keys: patch manifest contracts and revalidate.

## Handoff Checklist
1. Confirm glossary is the only term-table source.
2. Confirm manifest localization contracts remain valid.
3. Include localization validator command output.
