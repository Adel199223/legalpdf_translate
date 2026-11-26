# Coding Agent Environment Notes (Antigravity & Codex)

Use this file to make Antigravity and other coding agents easier to work with in this repo. (Filename `CODEX_ENVIRONMENT.md` is retained for harness and validator compatibility.)

## Antigravity Workspace Integration

- **Workspace rules**: Antigravity automatically discovers and loads root `AGENTS.md` (currently kept compact under Antigravity's 24 KB per-file cap). Do not create a duplicate `GEMINI.md`.
- **Workspace skills**: Antigravity discovers `.agents/skills/*/SKILL.md` via progressive disclosure (`legalpdf-validate`, `legalpdf-browser-review`, `legalpdf-word-review`, `legalpdf-commit-publish`), which wrap canonical `docs/assistant/workflows/` procedures without duplicating them.
- **MCP servers and plugins**: In Antigravity, MCP servers live in global `~/.gemini/config/mcp_config.json` or enabled plugins under `~/.gemini/config/plugins/<name>/mcp_config.json`:
  - `migrated-settings` provides `openaiDeveloperDocs` and `playwright`
  - `windows-desktop-control` provides native Windows desktop/Word/Qt screenshot and UI inspection (`ControlStatus(release=true)` when done)
  - `chrome-devtools-plugin` provides Chrome DevTools inspection
  - Google Workspace plugins (`gmail`, `gdrive`, `gdocs`, etc.) are assistant connectors only—never use `gmail` against live Gmail unless explicitly authorized

## Goals

- make setup expectations explicit
- reduce repeated environment discovery
- keep OpenAI-related docs lookup easy when relevant
- avoid unsafe or overly broad MCP defaults

## Safe default MCP posture

- prefer official, read-only documentation MCP servers when possible
- do not assume custom MCP servers are safe just because they are convenient
- keep project and plugin MCP configs minimal, reviewable, and free of leaked credentials

## VS Code / Codex Fallback Reference

If using VS Code or Codex instead of Antigravity, copy `.vscode/mcp.json.example` to `.vscode/mcp.json` only if the repo benefits from it (for Antigravity, `openaiDeveloperDocs` is already configured via the `migrated-settings` plugin).

## Suggested agent instruction snippet

Keep this rule in agent instructions when the project uses OpenAI APIs heavily:

> Always use the OpenAI developer documentation MCP server if you need to work with the OpenAI API, ChatGPT Apps SDK, Codex, or related docs without me having to explicitly ask.

## Exact Setup, Run, Validation & Recovery Pointers

- Workstation check: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check_dev_workstation.ps1 -ConfigurationOnly` (`docs/assistant/WORKSTATION_SETUP.md`)
- Primary browser app: `.\.venv311\Scripts\python.exe -m legalpdf_translate.shadow_web.server --open` (`README.md`)
- Validation tiers & direct-Dart fallbacks: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick` (`docs/assistant/VALIDATION.md`)
- Environment recovery: `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate` (`README.md`)
