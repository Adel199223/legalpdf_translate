# ExecPlan: Codex Bootstrap Update Policy

## Problem
The bootstrap template system needs its own protected update flow. The general docs update policy is too broad, and bare phrases like `update bootstrap` are ambiguous when projects also contain project-specific bootstrap files.

## Chosen Fix
- add `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
- make `update codex bootstrap` the canonical trigger
- wire the policy into the bootstrap entrypoint and template map
- extend validator coverage so the trigger semantics and protected-surface rules cannot drift

## Files To Update
- `docs/assistant/templates/BOOTSTRAP_UPDATE_POLICY.md`
- `docs/assistant/templates/CODEX_PROJECT_BOOTSTRAP_PROMPT.md`
- `docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json`
- `docs/assistant/templates/BOOTSTRAP_MODULES_AND_TRIGGERS.md`
- `tooling/validate_agent_docs.dart`
- `test/tooling/validate_agent_docs_test.dart`

## Validation Gates
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `dart run test/tooling/validate_agent_docs_test.dart`
