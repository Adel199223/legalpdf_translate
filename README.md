# LegalPDF Translate

Windows 11 desktop app (Tkinter) and CLI for legal PDF translation:

- Input: one PDF
- Processing: strictly one page per API request
- Output: one DOCX in page order

The app uses OpenAI Responses API with `gpt-5.2`, `store=false`, no tools, and no whole-document review pass.

## Requirements

- Windows 11
- Python 3.11 or 3.12 (3.11 is recommended if packaging friction appears)
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

Set `OPENAI_API_KEY` in `.env` or your environment.

## Run Qt GUI (Recommended)

```powershell
legalpdf-translate-qt
```

You can also launch the Qt GUI directly:

```powershell
python -m legalpdf_translate.qt_main
```

## Run Tkinter GUI (Fallback)

```powershell
legalpdf-translate-gui
```

## Run CLI

```powershell
legalpdf-translate --pdf input.pdf --lang EN --outdir out --effort high --effort-policy adaptive --images off --max-pages 5 --resume true --page-breaks true --keep-intermediates true --context-file ""
```

CLI options:

- `--lang`: `EN|FR|AR`
- `--effort`: `high|xhigh`
- `--effort-policy`: `adaptive|fixed_high|fixed_xhigh`
- `--allow-xhigh-escalation`: `true|false` (default `false`)
- `--images`: `off|auto|always`
- `--analyze-only`: extraction/image preflight only (no API calls), writes `analyze_report.json`
- `--max-pages`: integer or omit for all pages
- `--workers`: `1..6` (default `3`)
- `--resume`: `true|false`
- `--page-breaks`: `true|false`
- `--keep-intermediates`: `true|false`
- `--context-file`: path or empty string

Recommended workers: `3` (default). For PDFs under ~20 pages, `5` is often faster. If you see frequent `429`/timeout retries, reduce workers.

When `--effort-policy` is omitted, legacy compatibility is kept: `--effort high` maps to `fixed_high`, and `--effort xhigh` maps to `fixed_xhigh`.

Analyze-only example:

```powershell
legalpdf-translate --pdf input.pdf --lang FR --outdir out --max-pages 10 --images auto --analyze-only
```

## Resume Behavior

Run artifacts are stored in:

`<outdir>/<pdf_stem>_<LANG>_run/`

- `pages/page_0001.txt` etc.
- `images/page_0001.jpg` (if kept)
- `run_state.json`
- `run_summary.json` (written on success/failure/cancel)
- `analyze_report.json` (analyze-only mode)

When `--resume true`, completed pages are skipped if checkpoint compatibility matches (`pdf_fingerprint`, language, context hash, key settings).

## Privacy

- API key is never hardcoded.
- No extracted source text or translated content is written to operational logs.
- Saved per-page files contain only validated translation output.

## Build Windows EXE (PyInstaller one-folder)

```powershell
pyinstaller build\pyinstaller_gui.spec
```

Qt GUI build:

```powershell
pyinstaller build\pyinstaller_qt.spec --noconfirm
```

If PyInstaller has Qt-plugin issues on your machine, fallback to the official Qt deploy tool:

```powershell
pyside6-deploy src\legalpdf_translate\qt_main.py
```

Primary artifact:

`dist\legalpdf_translate\LegalPDFTranslate.exe`

## Tests

```powershell
pytest -q
```

If `python` is not on PATH, install Python from python.org and re-open terminal.
