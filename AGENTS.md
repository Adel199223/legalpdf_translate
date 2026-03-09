# AGENTS.md

This file is a compatibility shim.

- Primary runbook: `agent.md`
- Canonical app architecture/status: `APP_KNOWLEDGE.md`
- Machine routing map: `docs/assistant/manifest.json`

## Approval Gates
Ask before executing any of the following:
1. Destructive operations (delete/reset/overwrite data or history).
2. Risky DB/schema operations (migration edits, backfills, destructive SQL).
3. Force-push or history rewrite.
4. Publish/release/deploy actions.
5. Non-essential external network actions.

## ExecPlans
- Major or multi-file work requires an ExecPlan under `docs/assistant/exec_plans/active/`.
- Use lifecycle rules in `docs/assistant/exec_plans/PLANS.md`.
- Small isolated changes may skip ExecPlan when risk is low and scope is single-purpose.

## Worktree Isolation
- For concurrent threads, isolate work with `git worktree` before coding.
- Keep `main` stable as integration branch.
- For major work on `main`, branch to `feat/<scope-name>` first.

## Routing Rules
- For support or non-technical explanations, route to:
  - `docs/assistant/features/APP_USER_GUIDE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- If the user says `implement the template files` or `sync project harness`, run:
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- If the user says `audit project harness` or `check project harness`, use:
  - `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`
- If the user says `resume master plan`, `where did we leave off`, or `what is the next roadmap step`, open:
  - `docs/assistant/SESSION_RESUME.md`
- If `docs/assistant/SESSION_RESUME.md` shows a dormant roadmap state, default to normal ExecPlan flow unless the user explicitly asks for roadmap/master-plan work.
- `update codex bootstrap` / `UCBS` means template-system maintenance only, not project-local harness sync.
- If user asks for parity/inspiration against a named product/site/app, run:
  - `docs/assistant/workflows/REFERENCE_DISCOVERY_WORKFLOW.md`
- If task involves OpenAI products/APIs or unstable external facts, run:
  - `docs/assistant/workflows/OPENAI_DOCS_CITATION_WORKFLOW.md`
- If task involves browser automation reliability/provenance, run:
  - `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- If task involves heavy cloud machine evaluation, run:
  - `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`
- Commit/push requests must follow:
  - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`

## Stage-Gate Protocol
- For risk-triggered complex work, enforce staged execution via:
  - `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`
- Stop at stage boundaries and require exact continuation token format:
  - `NEXT_STAGE_X`

## Docs Sync Policy
After significant implementation changes, ask exactly:
"Would you like me to run Assistant Docs Sync for this change now?"

Ask it only when relevant touched-scope docs still remain unsynced.
If the relevant docs sync already ran during the same task/pass, do not ask again.
If approved, update only relevant docs for touched scope (no blanket rewrites).
