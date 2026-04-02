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
- `openai-docs`: official OpenAI docs lookup for unstable OpenAI/Codex facts
- `doc`: DOCX-focused editing/review workflows
- `pdf`: PDF-focused extraction/render/review workflows
- `playwright`: browser automation when a real browser is required
- `playwright-interactive`: iterative browser/Electron debugging
- `screenshot`: OS-level screenshot capture when needed
- `winui-app`: relevant for Windows desktop app design/development guidance

## Relevant Tooling and MCP Surfaces
- OpenAI docs MCP/doc tooling is available for OpenAI-specific freshness checks
- Browser automation tooling is available for web/UI validation when appropriate
- Browser automation is now part of the normal product surface because the browser app supports both real `live` mode and isolated `shadow` mode from one localhost server.
- Canonical local browser-automation preflight on this machine is `dart tooling/automation_preflight.dart`; direct script execution is preferred over `dart run ...` because the `dartdev` launcher can misreport availability here even when Playwright and the browser are healthy.
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
- The Dart-based browser automation preflight must prefer direct script execution on this machine; `dart run tooling/automation_preflight.dart` can still degrade through the `dartdev` launcher and should be treated as a launcher-path issue, not a product failure.
