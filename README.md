# LegalPDF Translate

Windows 11 desktop app (Qt/PySide6) and CLI for page-by-page legal PDF translation to DOCX.

## Docs Onboarding
- Canonical app knowledge: `APP_KNOWLEDGE.md`
- Agent runbook: `agent.md`
- Agent shim: `AGENTS.md`
- Assistant docs index: `docs/assistant/INDEX.md`
- Machine routing map: `docs/assistant/manifest.json`
- Fresh-session roadmap resume: `docs/assistant/SESSION_RESUME.md`
- Local harness sync from vendored templates: `docs/assistant/workflows/PROJECT_HARNESS_SYNC_WORKFLOW.md`

## Requirements
- Windows 11
- Python 3.11 (recommended)
- OpenAI API key

## Beginner Safe Setup (Recommended)
Use the recovery-safe setup script. It creates `.venv311`, installs dependencies, and verifies Python health.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1
. .\.venv311\Scripts\Activate.ps1
copy .env.example .env
```

## Manual Setup
```powershell
cd legalpdf_translate
py -3.11 -m venv .venv311
.venv311\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .
pip install -e .[dev]
copy .env.example .env
```

Set `OPENAI_API_KEY` in `.env` or environment.

## If Python/Pytest Suddenly Breaks
If you see import errors like `html.entities` or `idna` during `pip`/`pytest`, your machine Python install is corrupted.

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate
. .\.venv311\Scripts\Activate.ps1
python -m pytest -q
```

## Run GUI
```powershell
python -m legalpdf_translate.qt_app
```

## Run CLI
```powershell
legalpdf-translate --pdf input.pdf --lang EN --outdir out --effort high --effort-policy adaptive --images off --max-pages 5 --resume true --page-breaks true --keep-intermediates true --context-file ""
```

## Build EXE
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1
```

## Validate
```powershell
python -m pytest -q
python -m compileall src tests
dart run tooling/validate_agent_docs.dart
dart run tooling/validate_workspace_hygiene.dart
```

## Project Harness Commands
- `implement the template files` / `sync project harness`: apply the vendored templates in `docs/assistant/templates/` to this repo's local harness without editing the template folder itself.
- `audit project harness`: inspect vendored-template drift without editing files.
- `check project harness`: run harness validation only.
- `resume master plan`: open `docs/assistant/SESSION_RESUME.md` first, then the linked active roadmap tracker and active wave ExecPlan.
- `update codex bootstrap` / `UCBS`: maintain the reusable template system itself. Do not use this when you only want to sync this repo to its vendored templates.
