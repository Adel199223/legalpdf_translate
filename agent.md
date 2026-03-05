# agent.md

Operational runbook for coding agents in `legalpdf_translate`.

## Canonical Precedence
1. `APP_KNOWLEDGE.md` is canonical for app-level architecture and status.
2. `docs/assistant/APP_KNOWLEDGE.md` is a bridge summary and must defer to canonical.
3. Source code is final truth when docs conflict.

## Daily Flow
1. Route task via `docs/assistant/INDEX.md` and `docs/assistant/manifest.json`.
2. Choose the correct workflow document in `docs/assistant/workflows/`.
3. Run targeted tests first, then full regression if required by workflow.
4. Keep changes scoped; avoid unrelated edits.

## Approval Gates
Ask before executing any of the following:
1. Destructive operations.
2. Risky DB/schema operations.
3. Force-push/history rewrite.
4. Publish/release/deploy.
5. Non-essential external network actions.

## ExecPlans
- ExecPlans are mandatory for major or multi-file work.
- Create plan files in `docs/assistant/exec_plans/active/` using `docs/assistant/exec_plans/PLANS.md`.
- Move completed plans to `docs/assistant/exec_plans/completed/`.

## Worktree Isolation
- Use `git worktree` for parallel streams.
- Keep `main` stable.
- Major work must start on `feat/<scope-name>`.
- Apply worktree guidance in CI/repo, commit/publish, and docs-maintenance workflows.

## Support Routing
For support and non-technical explanation tasks, start with user guides:
1. `docs/assistant/features/APP_USER_GUIDE.md`
2. `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`

Use the support response shape:
- plain explanation -> numbered steps -> canonical check -> uncertainty note

## Commit/Publish Routing
Never handle commit requests blindly.
Always follow `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`.

## Inspiration/Parity Routing
If a user asks for behavior "like X", "same as X", "closest to X", or explicit parity with a named product/site/app, run `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md` before implementation decisions.

## OpenAI Docs + Citation Routing
If a task depends on OpenAI products/APIs, date-sensitive external facts, or unstable limits/pricing behavior:
1. Use `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`.
2. Prefer official primary sources.
3. Include source links and explicit verification dates (`YYYY-MM-DD`) for material external decisions.

## Browser/Cloud Module Routing
- Browser automation reliability/provenance tasks -> `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- Cloud-heavy machine evaluation tasks -> `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`

## Stage-Gate Protocol
For risk-triggered complex work:
1. Follow `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`.
2. Stop at each stage and publish the required stage packet schema.
3. Require exact continuation token format: `NEXT_STAGE_X`.

## Docs Sync Policy
After significant implementation changes, always ask exactly:
"Would you like me to run Assistant Docs Sync for this change now?"

If approved, update only the relevant docs for touched scope.
