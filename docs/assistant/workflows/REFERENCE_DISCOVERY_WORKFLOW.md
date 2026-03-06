# REFERENCE_DISCOVERY_WORKFLOW

## What This Workflow Is For
Discovering external references when users request parity/inspiration against named products/sites/apps.

## Expected Outputs
- Curated reference list with links.
- Rationale for each selected reference.
- Explicit adopted pattern vs local adaptation split.
- Safety/licensing notes and fallback when references are insufficient.

## When To Use
Trigger on phrases like:
- "like X"
- "same as X"
- "closest to X"
- explicit parity/inspiration requests against named products/sites/apps.

## What Not To Do
- Don't use this workflow when the request is fully local and has no external parity/inspiration intent.
- Instead use the domain workflow directly (`TRANSLATION_WORKFLOW` or `PERSISTENCE_DATA_WORKFLOW`).

## Primary Files
- `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md`
- `docs/assistant/manifest.json`
- `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`

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
- Weak/low-quality references: report insufficiency and use conservative local design.
- License ambiguity: reject direct reuse and request legal-safe alternative patterns.
- Source mismatch for model/data/inference tasks: include Hugging Face only when scope requires it.

## Handoff Checklist
1. Prioritize official product docs/repos first.
2. Then use actively maintained high-quality repositories.
3. Include links, rationale, and adaptation notes.
4. Include no blind code copying statement.
