# Local Capabilities

## Purpose
This file records the local capabilities that materially affect work in this repo.

Keep it factual and current. Do not list aspirational tooling that is not actually usable.

## Host and Runtime
- Primary visible app runtime: Windows desktop Python environment
- Secondary development/runtime host: WSL/Linux
- Canonical multi-worktree Qt launch helper: `tooling/launch_qt_build.py`

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
- Qt build identity enforcement exists through `tooling/launch_qt_build.py`
- Local test isolation via pytest/temp-dir patterns and listener-ownership debugging are expected and available for host-bound workflow triage
- Docs/validator tooling exists through:
  - `tooling/validate_agent_docs.dart`
  - `tooling/validate_workspace_hygiene.dart`

## Relevant Local External Tools
- Windows `gog` CLI for Gmail draft creation and related Google-account operations
- Windows Python `.venv311` for canonical local execution
- WSL/Linux shell tooling for pure code/docs/test work

## Constraints
- Windows-local auth and desktop integrations must be validated on Windows, not only in WSL.
- PATH assumptions are not enough for Windows-local tools; prefer explicit executable resolution when the app depends on them.
- Multi-worktree GUI testing must use canonical build identity rules instead of ad hoc launches.
- Host-bound tests should avoid live `%APPDATA%`/roaming settings and default user-facing ports unless the test explicitly opts into real machine state.
