# LegalPDF Translate

Windows-first Python app with a primary local browser interface, a secondary Qt/PySide6 shell, CLI helpers, and Gmail browser-extension/native-host bridge support for page-by-page legal PDF translation to DOCX.

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

## Quick Start (Recommended Browser App)
1. Activate the environment:
```powershell
. .\.venv311\Scripts\Activate.ps1
```
2. Start the primary local browser app:
```powershell
python -m legalpdf_translate.shadow_web.server --open
```
3. Use the normal daily-work URL:
`http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job`
4. If you want the live browser app without keeping the terminal attached, run:
```powershell
.\.venv311\Scripts\python.exe tooling/launch_browser_app_live_detached.py
```
5. Gmail browser-extension/native-host handoff uses:
`http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`

The browser app is the normal day-to-day interface. The Qt shell remains supported as a secondary fallback, and the CLI remains available for scripted or batch work.

## If Python/Pytest Suddenly Breaks
If you see import errors like `html.entities` or `idna` during `pip`/`pytest`, your machine Python install is corrupted.

Run:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate
. .\.venv311\Scripts\Activate.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
```

## Run Qt Shell (Secondary / Fallback)
```powershell
python -m legalpdf_translate.qt_app
```

Or, on Windows, double-click `Launch LegalPDF Translate.bat` in the repo root for the same canonical Qt launch path without typing the command manually.

## Run CLI (Secondary)
```powershell
legalpdf-translate --pdf input.pdf --lang EN --outdir out --effort high --effort-policy adaptive --images off --max-pages 5 --resume true --page-breaks true --keep-intermediates true --context-file ""
```

## Build EXE
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1
```

## Validate
```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
```

For normal work, do not install or run project dev validation through bare/global Python. Keep validation inside `.venv311`.

## Create Clean Review ZIP
```powershell
powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1
```

This writes a clean review ZIP to your Windows Downloads folder, keeps `.env.example`, and excludes local `.env`, virtualenvs, caches, generated DOCX/PDF outputs, and other local clutter.

## Project Harness Commands
- `implement the template files` / `sync project harness`: apply the vendored templates in `docs/assistant/templates/` to this repo's local harness without editing the template folder itself.
- `audit project harness`: inspect vendored-template drift without editing files.
- `check project harness`: run harness validation only.
- `resume master plan`: open `docs/assistant/SESSION_RESUME.md` first. If it shows active-roadmap state, continue into the linked tracker and wave; if it shows dormant roadmap state, default to normal ExecPlan flow unless the user explicitly asks to open a new roadmap.
- `update codex bootstrap` / `UCBS`: maintain the reusable template system itself. Do not use this when you only want to sync this repo to its vendored templates.
