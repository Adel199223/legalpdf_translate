# Docs Sync Prompt Relevance Hardening

## Summary
- Problem: the docs-sync prompt was treated as unconditional, so it could still be asked after the relevant docs sync had already been completed in the same task.
- Fix: narrow the rule across project governance and bootstrap templates so the exact prompt is asked only when relevant touched-scope docs remain unsynced.

## Files To Update
- `AGENTS.md`
- `agent.md`
- `docs/assistant/UPDATE_POLICY.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/GOLDEN_PRINCIPLES.md`
- `docs/assistant/PROJECT_INSTRUCTIONS.txt`
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- `docs/assistant/manifest.json`
- `docs/assistant/DOCS_REFRESH_NOTES.md`
- `docs/assistant/templates/BOOTSTRAP_CORE_CONTRACT.md`
- `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
- `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
- `tooling/validate_agent_docs.dart`
- `test/tooling/validate_agent_docs_test.dart`

## Validation Gate
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
