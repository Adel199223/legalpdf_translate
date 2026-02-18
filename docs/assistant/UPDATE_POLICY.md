# UPDATE_POLICY

Purpose
This file defines when and how to update the ChatGPT “knowledge pack” under `docs/assistant/*`.
It is a policy document (not a running history). Use Git history + `DOCS_REFRESH_NOTES.md` for change history.

## Default rule (user-controlled)
- Do NOT update `docs/assistant/*` automatically as part of code-change tasks.
- Only update `docs/assistant/*` when the user explicitly requests a “docs refresh / update assistant docs”.

## Deferred docs workflow (default for code changes)
If a task changes anything under `src/` or `tests/` AND the user did NOT request a docs refresh:
1) Append a short entry to `docs/assistant/DOCS_REFRESH_NOTES.md` (create it if missing).
2) Do not edit other `docs/assistant/*` files.

Required evidence to include in the notes entry:
- branch name + commit hash (or “working tree” if not committed yet)
- files changed
- key symbols/entrypoints affected (only what actually matters)
- user-visible behavior changes
- tests run + results

## Docs refresh workflow (only when requested by user)
When the user requests “docs refresh / update assistant docs”:
1) Read `docs/assistant/DOCS_REFRESH_NOTES.md` first (it is the queue of what drifted).
2) Update only the relevant knowledge docs under `docs/assistant/*` based on the notes + current repo state.
3) Keep edits focused on accuracy (no rewriting for style).

Typical docs to refresh (as applicable to the changes):
- `docs/assistant/APP_KNOWLEDGE.md` (repo map, entrypoints, “where is X?”)
- `docs/assistant/API_PROMPTS.md` + `docs/assistant/PROMPTS_KNOWLEDGE.md` (prompt/pipeline contract)
- `docs/assistant/QT_UI_KNOWLEDGE.md` + `docs/assistant/QT_UI_PLAYBOOK.md` (UI invariants & workflow)
- `docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md` (builder behavior and diagnostics)
- `docs/assistant/WORKFLOW_GIT_AI.md` (workflow guidance)
- `docs/assistant/CODEX_PROMPT_FACTORY.md` (prompt patterns/examples), only if prompt patterns changed

## Protected docs (do not edit unless explicitly requested)
- `docs/assistant/PROJECT_INSTRUCTIONS.txt`
- `docs/assistant/UPDATE_POLICY.md`

## Verification (required whenever you claim “done” on a change)
Run and report:
```powershell
python -m pytest -q
python -m compileall src tests
git diff --name-only
git status --short
