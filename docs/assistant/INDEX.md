# Assistant Docs Index

## Use when you need canonical architecture/status
- `APP_KNOWLEDGE.md`: canonical app architecture and status.
- `docs/assistant/APP_KNOWLEDGE.md`: short bridge for fast routing.

## Use when you need governance rules
- `agent.md`: operational runbook.
- `AGENTS.md`: compatibility shim.
- `docs/assistant/GOLDEN_PRINCIPLES.md`: enforceable rule source-of-truth.
- `docs/assistant/exec_plans/PLANS.md`: ExecPlan format and lifecycle.

## Use when you need user-facing explanations
- `docs/assistant/features/APP_USER_GUIDE.md`: full app support guide.
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`: primary workflow support guide.
- `docs/assistant/features/PRIMARY_FEATURE_USER_GUIDE.md`: compatibility shim to primary workflow guide.

## Use when you need workflow routing
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`
- `docs/assistant/workflows/LOCALIZATION_WORKFLOW.md`
- `docs/assistant/workflows/PERFORMANCE_WORKFLOW.md`
- `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md`
- `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`
- `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`
- `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`
- `docs/assistant/workflows/CI_REPO_WORKFLOW.md`
- `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/workflows/FEATURE_WORKFLOW.md` (compat shim)
- `docs/assistant/workflows/DATA_WORKFLOW.md` (compat shim)

## Use when you need source-backed external decisions
- `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`

## Use when you need validation
- `tooling/validate_agent_docs.dart`
- `tooling/validate_workspace_hygiene.dart`
- `tooling/automation_preflight.dart`
- `tooling/cloud_eval_preflight.dart`
- `test/tooling/validate_agent_docs_test.dart`
- `test/tooling/validate_workspace_hygiene_test.dart`
- `test/tooling/automation_preflight_test.dart`
- `test/tooling/cloud_eval_preflight_test.dart`

## Use when local Python is broken
- `scripts/setup_python311_env.ps1`: rebuilds a clean `.venv311` with project dependencies.

## Legacy supplemental deep docs
- `docs/assistant/API_PROMPTS.md`
- `docs/assistant/PROMPTS_KNOWLEDGE.md`
- `docs/assistant/QT_UI_KNOWLEDGE.md`
- `docs/assistant/QT_UI_PLAYBOOK.md`
- `docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md`
- `docs/assistant/WORKFLOW_GIT_AI.md`

## Template Read Policy
`docs/assistant/templates/*` is read-on-demand only and must not be opened unless explicitly requested.
