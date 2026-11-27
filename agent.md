# agent.md

Operational runbook for coding agents in `legalpdf_translate`.

## Canonical Precedence
1. `APP_KNOWLEDGE.md` is canonical for app-level architecture and status.
2. `docs/assistant/APP_KNOWLEDGE.md` is a bridge summary and must defer to canonical.
3. Source code is final truth when docs conflict.

## Daily Flow
1. Read `docs/assistant/HANDOFF.md` for current work; route the task via `docs/assistant/INDEX.md` and `docs/assistant/manifest.json`.
2. Choose the correct workflow document in `docs/assistant/workflows/`.
3. Run targeted tests first, then full regression if required by workflow.
4. Keep changes scoped; avoid unrelated edits.
- In Antigravity, `.agents/skills/` provides progressive-disclosure wrappers (`legalpdf-validate`, `legalpdf-browser-review`, `legalpdf-word-review`, `legalpdf-commit-publish`) pointing back to canonical `docs/assistant/workflows/`.

## Translation quality decisions

1. Name the user-visible failure. Record the document family, expected source relationship and the first place it breaks, whether in original visible evidence, extracted reading order, translated wording, layout assignment, or Word rendering. A diagnostic copy can explain a defect. Acceptance uses the file produced by ordinary Start.
2. Keep three results visible separately: correctness of legal content and source relationships, fidelity of appearance in Word, and the build actually installed. For each result name the case, build and evidence type (synthetic test, retained-response replay, fresh run, or installed check). A later build can preserve a useful result without inheriting its fresh-run status.
3. Reproduce the failure offline when retained evidence allows it. Test a counterexample that must keep its current behavior. When the same family fails again, compare the shared representation with an unseen example before adding another document-specific rule. Use focused feedback while iterating and schedule mandatory broad validation on the candidate whose results will be used.
4. In the current handoff keep one row per case, the actual validation result, the next action and its authority. The active plan holds acceptance conditions and links back for status. Move superseded narratives to dated history. A receipt or process check supersedes a stale running label. Read old checkpoints only to answer a specific evidence question.

For release review, bind the actual case ID, file and source-to-Word page map. If a helper rejects valid reflow or a later execution, retain that failure and check a narrow successor against both accepted artifacts and false-acceptance controls before considering another provider run.

Apply stage and spending gates to the next operation. A routine offline replay, source comparison or documentation correction within an authorized scope can proceed. A genuinely new risk-triggered stage follows the staged workflow. Renew live-service, financial, destructive or publication authority where the proposed operation requires it.

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
- Parallel feature work must branch/worktree from the latest approved baseline, not an older convenient branch.
- The approved base branch and floor commit are defined in `docs/assistant/runtime/CANONICAL_BUILD.json`; do not start a new feature branch unless it contains that approved-base floor.
- Before major parallel work starts, lock and record:
  - branch name
  - base branch
  - base SHA
  - worktree path
- If multiple worktrees or visible app windows can exist, use `tooling/launch_qt_build.py` instead of an ad hoc Qt launch command.
- That launcher rule applies to Qt. For browser work, verify the actual server/worktree, mode/workspace and served asset version through the available session tools; do not require a Qt launcher for the primary browser app.
- The canonical runnable build is defined by `docs/assistant/runtime/CANONICAL_BUILD.json`; default GUI handoffs must target that canonical build.
- GUI handoffs must identify the exact build under test:
  - repo/worktree path
  - branch
  - HEAD SHA
  - canonical vs noncanonical status
  - distinguishing feature set
- For Qt, treat "the app is open" as incomplete unless it is tied to the emitted build identity packet from `tooling/launch_qt_build.py`. For the browser app, identify the actual server/worktree, mode/workspace and served asset version.
- Within the current authorized publication scope, once a feature is accepted in testing, merge it into the approved base immediately before starting the next unrelated feature branch.
- Treat an accepted feature left only on a side branch despite authorized promotion as a workflow violation; testing acceptance alone does not authorize publication.
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

## Project Harness Routing
- If the user says `implement the template files` or `sync project harness`, follow `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`.
- If the user says `audit project harness` or `check project harness`, use the same workflow in audit/validation-only mode.
- Local harness application must read vendored templates as source input and must not edit `docs/assistant/templates/*`.
- `update codex bootstrap` and `UCBS` are reserved for maintaining the reusable template system itself, not for project-local harness sync.

## Roadmap Resume Routing
- If the user says `resume master plan`, `where did we leave off`, or `what is the next roadmap step`, open `docs/assistant/SESSION_RESUME.md` first.
- If `docs/assistant/SESSION_RESUME.md` is in active-roadmap state, open the linked active roadmap tracker and then the linked active wave ExecPlan.
- If `docs/assistant/SESSION_RESUME.md` is in dormant roadmap state, do not invent a roadmap; default to normal ExecPlan flow unless the user explicitly asks for roadmap/master-plan work.
- `docs/assistant/SESSION_RESUME.md` is the stable roadmap anchor file for fresh sessions.
- During active work in a separate worktree, that worktree's `SESSION_RESUME.md`, active roadmap tracker, and active wave ExecPlan are authoritative for live roadmap state.
- `main` may legitimately carry a dormant roadmap state when no tracker/wave is active on that worktree.

## Commit/Push Shorthand Defaults
- When the user says `commit` without narrowing scope:
  - inspect the full pending Source Control tree first
  - triage modified, staged, untracked, and temp artifacts
  - decide what belongs in git vs what should be removed or ignored
  - split the result into logical grouped commits, not convenience commits
  - do not leave unrelated pending changes unreviewed
  - immediately suggest push after the commit sequence is complete
- When the user says `push` without narrowing scope:
  - treat it as approval for the standard branch lifecycle in this repo:
    - push the correct branch
    - create or update the PR
    - wait for green required checks
    - merge if clean
    - delete the merged source branch when appropriate
    - prune refs and remove stale local branch state when safe
  - stop before merge only if blocked by red checks, merge conflicts, or a higher-priority approval gate
- If the user narrows scope explicitly, such as `commit only these files` or `push branch only`, follow that narrower instruction instead of the default lifecycle.

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
Current user authorization and an explicitly approved operation scope take precedence over dated continuation text. Do not request a consumed token again or treat an old stage/credit stop as active authority. This does not waive publication, destructive-operation or live-service gates.

For risk-triggered complex work:
1. Follow `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`.
2. Stop at each stage and publish the required stage packet schema.
3. Require exact continuation token format: `NEXT_STAGE_X`.

## Docs Sync Policy
Standing user authorization (2026-09-16): perform useful Docs Sync autonomously. Do not ask again. Update only touched-scope docs; no blanket rewrites. Preserve history and exact beforeimages when replacing current guidance. Publication, destructive operations and live Gmail remain separately gated.

Follow `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`, keeping current entry points and relevant user guides aligned. Record deferred gaps rather than repeatedly asking for permission. Do not apply templates or UCBS unless explicitly requested.

## Assistant model and available tools
Rely on Antigravity's native plan/execute workflow and active session models for coding-agent tasks (historical Codex Astra Ultra / GPT-6.1 Sol routing applies only in Codex sessions). Keep coding-agent model selection separate from the app's translation, OCR, and semantic-review settings and evidence. In Antigravity, use native file/terminal tools for code/tests, `windows-desktop-control` MCP (`Screenshot` first; release via `ControlStatus(release=true)`) for live Microsoft Word or Qt visual checks, the built-in `browser` subagent / `playwright` / `chrome-devtools` MCP for isolated `mode=shadow` browser checks, and `openaiDeveloperDocs` MCP for OpenAI API citations; keep assistant-side Gmail plugins and browser automation off live Gmail without explicit user authorization. Inspect current tool documentation and actual app/build ownership; a static capability inventory or old screenshot does not establish current tool availability, model quality, credentials or live state.
