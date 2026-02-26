# LegalPDF Translate

Windows 11 desktop app (Qt/PySide6) and CLI for page-by-page legal PDF translation to DOCX.

## Docs Onboarding
- Canonical app knowledge: `APP_KNOWLEDGE.md`
- Agent runbook: `agent.md`
- Agent shim: `AGENTS.md`
- Assistant docs index: `docs/assistant/INDEX.md`
- Machine routing map: `docs/assistant/manifest.json`

## Requirements
- Windows 11
- Python 3.11 or 3.12
- OpenAI API key

## Setup
```powershell
cd legalpdf_translate
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e .
pip install -e .[dev]
copy .env.example .env
```

Set `OPENAI_API_KEY` in `.env` or environment.

## Run GUI
```powershell
python -m legalpdf_translate.qt_gui
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
