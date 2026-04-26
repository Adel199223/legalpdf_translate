# AGENTS.md

Quick guardrails for Codex/agent work in `legalpdf_translate`.

- Primary runbook: `agent.md`
- Canonical app architecture/status: `APP_KNOWLEDGE.md`
- Fresh-session handoff: `docs/assistant/HANDOFF.md`
- Validation guide: `docs/assistant/VALIDATION.md`
- Live Gmail guide: `docs/assistant/GMAIL_LIVE_TESTING.md`
- Machine routing map: `docs/assistant/manifest.json`

## Project Snapshot
- Canonical repo path: `C:\Users\FA507\.codex\legalpdf_translate`
- Canonical branch for live Gmail: `main`
- PR #46 merge commit on `main`: `dbca0ca536429f3c92edfb503f461da21b5909f8`
- Primary UI: local browser app; live/Gmail port `8877`; Gmail bridge port `8765`
- Development UI review mode: browser `mode=shadow` with isolated app data

## Approval Gates
Ask before executing any of the following:
1. Destructive operations (delete/reset/overwrite data or history).
2. Risky DB/schema operations (migration edits, backfills, destructive SQL).
3. Force-push or history rewrite.
4. Publish/release/deploy actions.
5. Non-essential external network actions.

## Contract Rules
- Do not change backend route paths, API payload shapes, submitted select values, Gmail/native-host/extension contracts, or browser route IDs unless the task explicitly requires that contract change.
- Do not weaken safe rendering. Browser UI changes that render dynamic text must preserve safe text insertion patterns.
- Do not print secrets, tokens, `.env` values, app-data dumps, live Gmail content, or private config contents.
- Do not create full repo ZIPs or review bundles unless explicitly requested.

## Validation Defaults
- Use `.\.venv311\Scripts\python.exe` for pytest. Do not use bare/global Python for project tests.
- Standard docs/product validation:
  - `.\.venv311\Scripts\python.exe -m pytest -q <targeted tests>`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` before merge or when code/test/workflow files changed.
- If `dart run ...` fails with `Unable to find AOT snapshot for dartdev`, record it and rely on the direct-Dart fallback when the wrapper reports fallback success.

## ExecPlans
- Major or multi-file work requires an ExecPlan under `docs/assistant/exec_plans/active/`.
- Use lifecycle rules in `docs/assistant/exec_plans/PLANS.md`.
- Small isolated changes may skip ExecPlan when risk is low and scope is single-purpose.

## Worktree Isolation
- For concurrent threads, isolate work with `git worktree` before coding.
- Keep `main` stable as integration branch.
- For major work on `main`, branch to `feat/<scope-name>` first.
- Do not switch branches in the primary canonical worktree while a LegalPDF browser server launched from that worktree is running.
- If the canonical live server is active on `8877`/`8765`, modify files in a separate worktree or stop only clearly identified LegalPDF `python.exe`/`pythonw.exe -m legalpdf_translate.shadow_web.server` processes when the task permits it.

## Live vs Shadow Mode
- Live Gmail extension intake must use canonical `main` at `C:\Users\FA507\.codex\legalpdf_translate`.
- Feature branches and review worktrees should use browser `mode=shadow` and isolated workspaces for UI review.
- Codex must not click the live Gmail extension or operate live Gmail unless the user explicitly authorizes that scope.
- Generated DOCX/PDF files must be manually reviewed before any Gmail draft is sent.

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
- Post-PR #46 continuity starts with:
  - `docs/assistant/HANDOFF.md`
  - `docs/assistant/PR46_POST_MERGE_SUMMARY.md`

## Stage-Gate Protocol
- For risk-triggered complex work, enforce staged execution via:
  - `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`
- Stop at stage boundaries and require exact continuation token format:
  - `NEXT_STAGE_X`

## Docs Sync Policy
After significant implementation changes, ask exactly:
"Would you like me to run Assistant Docs Sync for this change now?"

Ask it only when relevant touched-scope docs still remain unsynced and immediate same-task synchronization is necessary.
If immediate same-task synchronization is not necessary, defer it to a later docs-maintenance pass.
If the relevant docs sync already ran during the same task/pass, do not ask again.
If approved, update only relevant docs for touched scope (no blanket rewrites).
