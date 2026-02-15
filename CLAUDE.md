# Claude Guidance for this repo (legalpdf_translate)

This file is intentionally SHORT: entrypoint + hard guardrails.
Follow the code and docs; 

## Validation (always run)
```powershell
python -m pytest -q
python -m compileall src tests
```

## Read-first docs (source of truth)
- docs/assistant/APP_KNOWLEDGE.md (repo map / “where is X?”)
- docs/assistant/UPDATE_POLICY.md (if src/ or tests/ change, update docs too)
- docs/assistant/WORKFLOW_GIT_AI.md (Git + PowerShell workflow + common errors)

### UI / Qt layout / resizing
- docs/assistant/QT_UI_KNOWLEDGE.md
- docs/assistant/QT_UI_PLAYBOOK.md
Primary code: src/legalpdf_translate/qt_gui/

### Glossary Builder behavior
- docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md
Primary code:
- src/legalpdf_translate/glossary_builder.py
- src/legalpdf_translate/qt_gui/tools_dialogs.py
- src/legalpdf_translate/glossary_diagnostics.py
- src/legalpdf_translate/run_report.py

### Prompt construction / optimization
- docs/assistant/PROMPTS_KNOWLEDGE.md
Primary code:
- src/legalpdf_translate/prompt_builder.py
- src/legalpdf_translate/workflow.py
- src/legalpdf_translate/glossary.py
- src/legalpdf_translate/validators.py

## Hard engineering rules
- Add/update tests for any behavior change.
- If src/ or tests/ change, update relevant docs/assistant/* per UPDATE_POLICY.md.
- - Always READ docs/assistant/UPDATE_POLICY.md, but DO NOT modify it unless explicitly asked.
- DO NOT modify docs/assistant/PROJECT_INSTRUCTIONS.txt unless explicitly asked.

## UI invariants (do not break)
- Avoid hard-coded fixed window sizes; prefer screen-adaptive sizing and resize responsiveness.
- Keep content centered within decorative frame; margins/insets must match frame geometry.
- Prevent horizontal overflow; restructure layouts (wrap/grid) rather than using horizontal scrolling.
- If RTL/layout direction issues appear in the main window, enforce LTR at the appropriate container.

## PowerShell gotcha
PowerShell treats @{u} as a hashtable; quote it:
```powershell
git rev-parse --abbrev-ref --symbolic-full-name "@{u}"
```
## Secrets / safety (mandatory)
- Never request or output real secrets (API keys, auth headers).
- Never run `rg --hidden --no-ignore` across the whole repo unless explicitly asked.
- Never read, print, or summarize `.env` contents. Treat `.env` as sensitive.
- If a secret might be present, instruct the user to rotate/revoke it and verify with `git grep` (tracked files only).
