# Assistant Docs Sync Catch-Up Plan (2026-03-05)

## 1) Title
Assistant Docs Sync Catch-Up for the 2026-03-05 staged rollout

## 2) Goal and non-goals
- Goal:
  - Bring assistant documentation up to the actual shipped state on `chore/import-optmax-2026-03-05` at final signoff commit `d29c163`.
  - Update only current-truth docs, active execution history, and the live reliability signoff packet.
- Non-goals:
  - No code changes.
  - No schema or manifest rewrites unless validators force a minimal routing fix.
  - Do not rewrite dated benchmark/audit snapshots as current truth.

## 3) Scope (in/out)
- In:
  - Canonical app knowledge and bridge docs.
  - User guides for OCR advisor, review queue, job-log sync, and queue runner.
  - Workflow/DB knowledge docs.
  - Active ExecPlans and live signoff packet.
  - Refresh-notes entry for this catch-up sync.
- Out:
  - Historical benchmark/audit packets other than the live signoff record.
  - Runtime/source-code modifications.

## 4) Interfaces/types/contracts affected
- Docs-only sync for already shipped additive interfaces:
  - CLI flags for cost guardrails, review export, and queue execution.
  - Additive `run_summary.json` cost/risk/review/advisor keys.
  - Additive `analyze_report.json` advisor keys.
  - Additive `job_runs` columns for run metrics and quality risk.

## 5) File-by-file implementation steps
1. Update `APP_KNOWLEDGE.md` with queue runner, advisor, review queue, and job-log sync truth.
2. Update bridge/user/workflow/DB docs for shipped support surfaces.
3. Refresh `RELIABILITY_SIGNOFF_2026-03-05.md` to final SHA `d29c163`.
4. Backfill execution history in the active rollout ExecPlans.
5. Append a dated catch-up entry to `docs/assistant/DOCS_REFRESH_NOTES.md`.
6. Run docs validators, workspace hygiene, compileall, and full pytest.

## 6) Tests and acceptance criteria
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- `./.venv311/Scripts/python.exe -m compileall src tests`
- `./.venv311/Scripts/python.exe -m pytest -q`
- `git diff --name-only`
- `git status --short`

## 7) Rollout and fallback
- Rollout:
  - Patch docs in place on `chore/import-optmax-2026-03-05`.
  - Keep historical benchmark/audit packets unchanged.
- Fallback:
  - If validators show routing drift, make only the smallest required follow-up doc fix.

## 8) Risks and mitigations
- Risk: reintroducing drift by documenting the plan instead of the shipped code.
  - Mitigation: verify GUI layout, commit history, and final CI/signoff evidence before patching docs.
- Risk: overstating historical stage evidence.
  - Mitigation: use exact commit/CI identifiers where known; otherwise explicitly defer to final authoritative validation on `d29c163`.

## 9) Assumptions/defaults
- Branch remains `chore/import-optmax-2026-03-05`.
- Dated benchmark/audit files remain historical snapshots.
- `docs/assistant/audits/RELIABILITY_SIGNOFF_2026-03-05.md` is the live signoff record.
- No manifest change is intended by default.

## 10) Execution status
- Status: completed.
- Validation outcomes:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `497 passed`
- Outcome:
  - Current-truth assistant docs now match the shipped staged rollout through final signoff `d29c163`.
  - Historical benchmark/audit snapshots were preserved, with only the live reliability signoff packet refreshed.
