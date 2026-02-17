# docs/assistant/CLAUDE.md — Coding Agent Guardrails (LegalPDF Translate)

Short, always-on rules for coding agents working inside this repo. Optimize quality and robustness, but avoid unnecessary work that increases token usage.

## Setup (Windows + PowerShell)
Activate venv before running anything:
    .\.venv\Scripts\Activate.ps1

## Validate before saying "done"
Run these before reporting completion:
    python -m pytest -q
    python -m compileall src tests

## Token efficiency: do not read unnecessary docs
- Do not open/read docs unless required for the current task.
- Always start from the repo map: docs/assistant/APP_KNOWLEDGE.md
- Only open other knowledge packs when relevant to the task (see Read order below).
- Do NOT read these unless explicitly requested/triggered:
  - docs/assistant/PROJECT_INSTRUCTIONS.txt (user-owned; also do-not-edit)
  - docs/assistant/UPDATE_POLICY.md (read only when user requests a docs refresh)
  - docs/assistant/CODEX_PROMPT_FACTORY.md (meta prompt doc; do-not-read unless explicitly asked)
- Only open docs/assistant/AGENT_ADDONS.md when a Trigger Checklist item matches.

## Source of truth (read order)
1) docs/assistant/APP_KNOWLEDGE.md (repo map / “where is X?”)
2) Then ONLY what you need for the current task:
   - UI / Qt: docs/assistant/QT_UI_KNOWLEDGE.md, docs/assistant/QT_UI_PLAYBOOK.md
   - App→API prompts (translation pipeline): docs/assistant/API_PROMPTS.md, docs/assistant/PROMPTS_KNOWLEDGE.md
   - Glossary Builder: docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md
   - Git workflow: docs/assistant/WORKFLOW_GIT_AI.md

If you can’t prove a claim from repo files or from command output, label it Uncertain and provide exact commands to verify.

## UPDATE_POLICY (user-controlled docs refresh)
- Do NOT update docs/assistant/* automatically.
- Only when the user explicitly requests “docs refresh / update assistant docs”:
  - Read docs/assistant/UPDATE_POLICY.md and update relevant docs/assistant/* accordingly.
- Never edit docs/assistant/UPDATE_POLICY.md unless explicitly asked.

## Change policy (quality-first)
- Prefer the best maintainable solution over minimal diffs.
- You MAY refactor/optimize within the same subsystem as the requested change.
- Avoid unrelated repo-wide cleanup (mass renames/reformatting/reorganizing folders) unless explicitly requested.
- If touching many files, justify each file’s necessity in the final report.

## Trigger Checklist: when to consult AGENT_ADDONS.md
Only open docs/assistant/AGENT_ADDONS.md if the task touches ANY of:

A) Persistence / auto-save / settings storage
- GUI settings read/write, save/load, migrations, schema keys
- “Auto-save”, “Apply”, dialog close/save behavior
- Anything that must survive restart

B) Qt table editing / delegates / add-row workflows
- QTableWidget/QTableView edit lifecycle, delegates, commit timing
- Add-row UX (plus button, shortcuts, insertion position)
- Cell widgets (combos/buttons) and sizing/truncation issues

C) Normalization / validation / silent dropping
- Any normalize_* / coerce_* / validate_* path in a save pipeline
- “Empty field” handling that could drop user input
- Dedup keys / identity / “visible vs hidden” merging

D) Cross-language propagation / cross-view syncing
- One edit must appear in other target languages/tabs/views
- Sync logic across FR/EN/AR views, and persistence across restart

If ANY trigger matches:
- Open docs/assistant/AGENT_ADDONS.md and apply the relevant checklist section(s).
- Do not claim done until the add-on acceptance tests pass.
- If AGENT_ADDONS.md is missing, stop and ask the user for its path/name.

## Working rules (behavior-first)
- Prove the real user workflow end-to-end (not just internal plumbing).
- For UI/state tasks, include a manual repro script:
  - exact clicks/keystrokes
  - expected result immediately
  - expected result after closing the dialog
  - expected result after restarting the app
- If you change behavior, add/update tests that fail before and pass after when feasible.

## Repo safety / ownership (do-not-edit unless explicitly asked)
Do not modify these files unless the user explicitly requests it:
- docs/assistant/PROJECT_INSTRUCTIONS.txt
- docs/assistant/UPDATE_POLICY.md
- docs/assistant/CODEX_PROMPT_FACTORY.md (meta prompt doc)

## Secrets / safety (mandatory)
- Never request or output real secrets (API keys, auth headers, tokens).
- Never read, print, or summarize .env contents.
- Redact sensitive values from any output you share.

## Qt UI invariants (when touching UI/layout)
- Prefer layout/size policies over fixed pixel sizing; keep window responsive.
- Prevent horizontal overflow; fix layouts rather than enabling horizontal scrolling.
- Keep layout consistent with any decorative frame/margins; avoid “frame vs layout” mismatch.
- Preserve LTR UI chrome even when translating to RTL languages.

## Final report (keep it short)
Include:
- What changed + why
- Files changed (and why each was necessary)
- Manual verification steps (task-specific)
- Tests run + results (commands):
    python -m pytest -q
    python -m compileall src tests
- Repo state (commands):
    git diff --name-only
    git status --short

## PowerShell gotcha
PowerShell treats @{u} as a hashtable; quote it:
    git rev-parse --abbrev-ref --symbolic-full-name "@{u}"