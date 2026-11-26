# Local Capabilities

## Purpose
This file records the local capabilities that materially affect work in this repo.

Keep it factual and current. Do not list aspirational tooling that is not actually usable.

## Host and Runtime
- Primary visible app runtime: Windows-local browser app server plus browser
- Secondary visible app runtime: Windows Qt desktop shell
- Secondary development/runtime host: WSL/Linux
- Canonical multi-worktree Qt launch helper: `tooling/launch_qt_build.py`
- Canonical browser-app launcher: `tooling/launch_browser_app_live_detached.py`

## Relevant Skills
- Workspace skills under `.agents/skills/` (Antigravity auto-discovered wrappers for canonical workflows):
  - `legalpdf-validate`: `.venv311` pytest tiers, `scripts/validate_dev.ps1`, direct-Dart doc/hygiene fallback, and workstation checks
  - `legalpdf-browser-review`: isolated `mode=shadow` browser review (`127.0.0.1:8888`), asset-version verification, and live-Gmail guardrails
  - `legalpdf-word-review`: headless `tooling/render_docx.py` and live Windows Word inspection via `windows-desktop-control` MCP
  - `legalpdf-commit-publish`: `commit`/`push` shorthand semantics, `CANONICAL_BUILD.json` floor checks, and worktree/branch closeout
- Installed Antigravity and migrated global skills:
  - `openai-docs`: official OpenAI docs lookup for unstable OpenAI API and model facts
  - `pdf`: PDF extraction/render/review workflows
  - `playwright` and `playwright-interactive`: terminal/REPL browser automation when a real browser flow is required
  - `chrome-devtools` and `a11y-debugging`: Chrome DevTools MCP debugging, DOM/network/performance inspection, and accessibility auditing
  - `screenshot`: OS-level screenshot capture when tool-specific capture is unavailable
  - `court-translation-drafts`, `gh-fix-ci`, `gh-address-comments`, and `agy-customizations`
- Legacy/absent Codex notes: Codex-only skills previously listed here (`doc`, `winui-app`) are not installed in Antigravity, and `browser-iab-safe-tabs` in `migrated-settings` is a legacy Codex in-app-browser helper unused by Antigravity.

## Relevant Tooling and MCP Surfaces
- `windows-desktop-control` MCP (`Screenshot` first; `Snapshot` only for UI clicks; always release via `ControlStatus(release=true)`) for live Microsoft Word page review and Qt visual checks
- Antigravity built-in `browser` subagent, `chrome-devtools` MCP, and `migrated-settings` `playwright` MCP for isolated `mode=shadow` browser UI review (never live Gmail without explicit user authorization)
- `migrated-settings` `openaiDeveloperDocs` MCP for OpenAI API citations and freshness checks
- Installed Google Workspace plugins (`gmail`, `gdrive`, `gdocs`, `gcalendar`, `gsheets`, `gslides`) are assistant-side connectors separate from the app's Windows `gog` CLI and must not touch live Gmail unless explicitly authorized
- Browser automation is part of the normal product surface because the browser app supports both real `live` mode and isolated `shadow` mode from one localhost server
- Canonical local browser-automation preflight on this machine is `dart tooling/automation_preflight.dart`; direct script execution is preferred over the package-run form because the `dartdev` launcher can misreport availability here even when Playwright and the browser are healthy
- Qt build identity enforcement exists through `tooling/launch_qt_build.py`
- PowerShell COM automation is available for host-bound Word actions when Microsoft Word is installed on Windows
- Local test isolation via pytest/temp-dir patterns and listener-ownership debugging are expected and available for host-bound workflow triage
- Visual DOCX review is available locally through `tooling/render_docx.py` using the installed LibreOffice binary plus Poppler and `.venv311` `pdf2image`
- The canonical local Python environment `.venv311` is currently healthy again for the browser/Gmail/runtime/finalization pytest suites and the assistant docs validators
- Docs/validator tooling exists through:
  - `tooling/validate_agent_docs.dart`
  - `tooling/validate_workspace_hygiene.dart`

## Relevant Local External Tools
- Windows `gog` CLI for Gmail draft creation and related Google-account operations
- Browser app localhost server on `127.0.0.1:8877` for live daily use and explicit isolated test mode
- Windows Microsoft Word for DOCX review and the Arabic `Align Right + Save` runtime assist
- Windows Python `.venv311` for canonical local execution
- Poppler `pdftoppm` installed via WinGet for PDF/page rasterization and DOCX visual review
- WSL/Linux shell tooling for pure code/docs/test work

## Constraints
- Windows-local auth and desktop integrations must be validated on Windows, not only in WSL.
- The Arabic DOCX review gate depends on Windows Word plus PowerShell COM automation; WSL-only DOCX checks are insufficient for that path.
- PATH assumptions are not enough for Windows-local tools; prefer explicit executable resolution when the app depends on them.
- Multi-worktree GUI testing must use canonical build identity rules instead of ad hoc launches.
- Host-bound tests should avoid live `%APPDATA%`/roaming settings and default user-facing ports unless the test explicitly opts into real machine state.
- Browser-app testing should prefer `mode=shadow` instead of reusing live data, and browser-app Gmail bridge checks must distinguish browser-owned live bridge state from intentionally isolated shadow state.
- The Dart-based browser automation preflight must prefer direct script execution on this machine; the package-run launcher form can still degrade through the `dartdev` launcher and should be treated as a launcher-path issue, not a product failure.
- Antigravity's installed `gmail` plugin and `browser` subagent / `playwright` / `chrome-devtools` MCP must not touch live Gmail or click the live Gmail extension without explicit user authorization; when using `windows-desktop-control`, always release control via `ControlStatus(release=true)` when finished or waiting on the user.
