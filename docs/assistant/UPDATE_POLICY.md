# UPDATE_POLICY

Purpose
This file defines when and how to update the assistant knowledge pack under `docs/assistant/*`.
It is policy guidance (not a running history). Use Git history + `DOCS_REFRESH_NOTES.md` for change history.

## Default rule (user-controlled)
- Do NOT perform blanket docs rewrites automatically.
- Use scoped docs updates when the user approves docs sync or when governance contracts require same-task synchronization.
- Do not force Assistant Docs Sync after every major change; when immediate same-task synchronization is not necessary, defer it to a later docs-maintenance pass.

## Significant-change docs sync decision
After significant implementation changes, ask exactly:
- "Would you like me to run Assistant Docs Sync for this change now?"

Only ask it when relevant touched-scope docs still remain unsynced and immediate same-task synchronization is necessary.
If immediate same-task synchronization is not necessary, defer it to a later docs-maintenance pass instead of prompting automatically during implementation flow.
If the relevant docs sync already ran during the same task/pass, do not ask again.

Immediate same-task synchronization is usually reserved for:
- governance/workflow/manifest contract changes that would leave routing wrong if deferred
- task closeout or handoff points where stale assistant docs would break continuity
- explicit user requests to make docs current now

If approved:
1. Update only touched-scope docs.
2. Keep canonical-first order (`APP_KNOWLEDGE.md` -> bridge/workflows/user guides).
3. Re-run docs validators before completion.
4. If the sync discovers stale continuity state from merge/cleanup drift, repair the relevant live anchors during the same pass:
   - `docs/assistant/SESSION_RESUME.md`
   - stale `docs/assistant/exec_plans/active/` vs `completed/` lifecycle state
   - assistant-facing scratch-path guidance when temp artifacts pollute Source Control

## Project harness apply vs bootstrap maintenance
- `implement the template files` / `sync project harness` is project-local harness application, not a docs-only sync and not global bootstrap maintenance.
- That flow may read vendored files under `docs/assistant/templates/*`, but it must not edit them.
- `update codex bootstrap` / `UCBS` is the protected trigger for maintaining the reusable template system itself.
- Do not collapse these three scopes together:
  - touched-scope docs sync
  - project-local harness application
  - global bootstrap/template maintenance

## Deferred docs workflow (when docs sync is postponed)
If a task changes `src/` or `tests/` and immediate docs sync is not required or approved:
1. Append a short entry to `docs/assistant/DOCS_REFRESH_NOTES.md`.
2. Avoid unrelated `docs/assistant/*` rewrites.
3. If merge/cleanup drift leaves stale continuity state behind, do not pretend the repo is clean; record the gap and fix it in the next approved docs-maintenance pass.

Required evidence in deferred notes:
- branch name + commit hash (or "working tree")
- files changed
- key symbols/entrypoints affected
- user-visible behavior changes
- tests run + results

## OpenAI / external fact freshness
When decisions depend on external or unstable facts:
1. Prefer official primary sources.
2. Record sources and verification dates (`YYYY-MM-DD`) in `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`.
3. Separate confirmed facts from assumptions in summaries.

## Stage-gate alignment
For risk-triggered complex work using staged execution:
1. Keep stage packet evidence in active ExecPlan notes.
2. Preserve exact continuation token format `NEXT_STAGE_X` in workflow docs.

## Protected docs
These files are governance-sensitive and should be edited only with explicit user intent or contract-alignment need:
- `docs/assistant/PROJECT_INSTRUCTIONS.txt`
- `docs/assistant/UPDATE_POLICY.md`

## Verification (required whenever claiming done)
PowerShell:
```powershell
python -m pytest -q
python -m compileall src tests
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
git diff --name-only
git status --short
```
POSIX:
```bash
python3 -m pytest -q
python3 -m compileall src tests
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
git diff --name-only
git status --short
```
