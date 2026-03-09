# OPENAI_DOCS_CITATION_WORKFLOW

## What This Workflow Is For
Ensuring OpenAI product/API decisions are based on official docs with explicit freshness and citation records.

## Expected Outputs
- Official-source links for all material OpenAI behavior/capability decisions.
- Explicit verification dates (`YYYY-MM-DD`) for unstable facts.
- Updated `EXTERNAL_SOURCE_REGISTRY.md` entries for new/revised decisions.

## When To Use
- Any task involving OpenAI APIs, model behavior, limits, pricing, schedules, or capability assumptions.
- Any date-sensitive external fact referenced in implementation or governance docs.

## What Not To Do
- Don't use this workflow when official OpenAI product/API sourcing is not relevant to the task.
- Instead use official OpenAI docs and API references first.

## Primary Files
- `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`
- `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`
- `docs/assistant/manifest.json`

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
- Missing official citation for a material claim: block merge and add source + date.
- Citation date stale for unstable topic: re-verify source and update registry date.
- Conflicting external docs: prefer official OpenAI API/docs and note uncertainty explicitly.

## Handoff Checklist
1. Record source URLs in `EXTERNAL_SOURCE_REGISTRY.md`.
2. Record verification date for each entry.
3. Separate confirmed facts from inference/assumptions in output narratives.
4. Re-run docs validator before completion.
