# APP_KNOWLEDGE

## 0. How to use this knowledge pack (for the ChatGPT Project)
- Primary source of truth for project Q&A: `docs/assistant/APP_KNOWLEDGE.md`.
- Prompt generation patterns: `docs/assistant/CODEX_PROMPT_FACTORY.md`.
- Maintenance rules: `docs/assistant/UPDATE_POLICY.md`.
- Always answer with file-path-grounded facts, then suggest a command to verify.
- If a claim cannot be proven from files/grep output, label it `Uncertain` and provide a command.
- Assistant routing hint: If asked "where does X live", inspect the "J. Where is X? index" section first, then verify with `rg -n "symbol_or_keyword" src tests`.

## A. What the app does (user workflows)
LegalPDF Translate is a Windows-focused Python app that translates legal PDFs to DOCX using a page-by-page workflow. The primary interface is a Qt GUI (`src/legalpdf_translate/qt_gui/app_window.py::QtMainWindow`) with a CLI path (`src/legalpdf_translate/cli.py::main`). Translation is executed per page (not whole-document batching) and can produce run artifacts for resume, rebuild, and diagnostics (`src/legalpdf_translate/workflow.py::TranslationWorkflow.run`, `README.md`).

Primary user workflows:
- Translate PDF to EN/FR/AR in Qt GUI (`src/legalpdf_translate/qt_gui/app_window.py::_start`, `src/legalpdf_translate/workflow.py::TranslationWorkflow.run`).
- Translate via CLI (`src/legalpdf_translate/cli.py::main`).
- Analyze-only preflight without translation API calls (`src/legalpdf_translate/cli.py` flag `--analyze-only`, `src/legalpdf_translate/workflow.py::TranslationWorkflow.analyze`).
- Rebuild DOCX from existing run pages (`src/legalpdf_translate/workflow.py::TranslationWorkflow.rebuild_docx`).
- Export run report (save Markdown or copy clipboard) (`src/legalpdf_translate/qt_gui/app_window.py::_open_run_report`, `src/legalpdf_translate/run_report.py::build_run_report_markdown`).
- Save run metadata to job log (`src/legalpdf_translate/qt_gui/dialogs.py::QtSaveToJobLogDialog`, `src/legalpdf_translate/joblog_db.py::insert_job_run`).
- Assistant routing hint: If asked "what can a user do", inspect `README.md`, then `src/legalpdf_translate/qt_gui/app_window.py`, then `src/legalpdf_translate/cli.py`.

## B. How to run it (Qt GUI / CLI / build EXE) - exact commands + exact entrypoints
Qt GUI:
```powershell
python -m legalpdf_translate.qt_gui
```
Entrypoints:
- `src/legalpdf_translate/qt_gui/__main__.py`
- `src/legalpdf_translate/qt_main.py::main`
- `src/legalpdf_translate/qt_app.py::run`

Qt GUI via installed script:
```powershell
legalpdf-translate-qt
```
Script mapping in `pyproject.toml`: `legalpdf-translate-qt = legalpdf_translate.qt_main:main`.

CLI:
```powershell
legalpdf-translate --pdf input.pdf --lang EN --outdir out --effort high --effort-policy adaptive --images off --max-pages 5 --resume true --page-breaks true --keep-intermediates true --context-file ""
```
Entrypoint:
- `src/legalpdf_translate/cli.py::main`
- `pyproject.toml`: `legalpdf-translate = legalpdf_translate.cli:main`

Analyze-only CLI:
```powershell
legalpdf-translate --pdf input.pdf --lang FR --outdir out --max-pages 10 --images auto --analyze-only
```

Rebuild DOCX CLI:
```powershell
legalpdf-translate --pdf input.pdf --lang EN --outdir out --rebuild-docx --page-breaks true
```

Build EXE:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1
```
Built artifact path:
- `dist\\legalpdf_translate\\LegalPDFTranslate.exe`

Run built EXE:
```powershell
.\dist\legalpdf_translate\LegalPDFTranslate.exe
```

Tk GUI status:
- `Uncertain` (no Tk entrypoint files found in preflight).
- Verified missing paths:
```powershell
Test-Path src/legalpdf_translate/gui_main.py
Test-Path src/legalpdf_translate/gui_app.py
```
- Additional verification:
```powershell
rg -n "tkinter|Tk|gui_main|gui_app" src tests README.md
```

Assistant routing hint: If asked "how do I launch", inspect `README.md` and `pyproject.toml`, then confirm entrypoints with `rg -n "__main__|def main\(|def run\(" src/legalpdf_translate`.

## C. Architecture map (module tree + responsibilities) - exact file paths
Core modules:
- `src/legalpdf_translate/qt_gui/app_window.py`: main window UI state machine (`QtMainWindow`) and run/report/joblog actions.
- `src/legalpdf_translate/qt_gui/dialogs.py`: settings dialog (`QtSettingsDialog`), key show/hide, debug bundle creation, job log dialogs.
- `src/legalpdf_translate/qt_gui/worker.py`: Qt thread workers for run/analyze/rebuild.
- `src/legalpdf_translate/workflow.py`: translation pipeline orchestration (`TranslationWorkflow`).
- `src/legalpdf_translate/run_report.py`: event collector, redaction/sanitization, Markdown+JSON report builder.
- `src/legalpdf_translate/openai_client.py`: transport retries/backoff wrapper around OpenAI Responses API.
- `src/legalpdf_translate/ocr_engine.py`: OCR engine policy and fallback (`local`, `local_then_api`, `api`).
- `src/legalpdf_translate/checkpoint.py`: run-state schema/persistence and resume compatibility.
- `src/legalpdf_translate/output_paths.py`: deterministic run/output paths and writable outdir checks.
- `src/legalpdf_translate/user_settings.py`: GUI/joblog settings persistence and normalization.
- `src/legalpdf_translate/secrets_store.py`: secure keyring-backed key storage wrappers.
- `src/legalpdf_translate/joblog_db.py`: SQLite job log schema/migrations/CRUD.
- `src/legalpdf_translate/docx_writer.py`: DOCX assembly from page outputs, including RTL paragraph/run direction handling and bidi-control sanitization helpers.
- `src/legalpdf_translate/cli.py`: command-line parsing and execution path.
- `src/legalpdf_translate/qt_main.py` + `src/legalpdf_translate/qt_app.py`: Qt app bootstrap.

Source-of-truth modules for behavior:
- Runtime pipeline: `src/legalpdf_translate/workflow.py`
- Settings schema/defaults: `src/legalpdf_translate/user_settings.py`
- Secret handling: `src/legalpdf_translate/secrets_store.py`
- Reporting/redaction: `src/legalpdf_translate/run_report.py`
- UI orchestration: `src/legalpdf_translate/qt_gui/app_window.py`

Assistant routing hint: If asked "which module owns behavior X", start at `workflow.py` for pipeline logic, `app_window.py` for UI events, and `dialogs.py` for settings/key UX.

## D. Translation pipeline (step-by-step) - where each stage happens (file/symbol references)
1. Config intake and validation
- Qt builds `RunConfig` in `src/legalpdf_translate/qt_gui/app_window.py::_build_config`.
- CLI builds `RunConfig` in `src/legalpdf_translate/cli.py::main`.
- Workflow normalizes/validates in `src/legalpdf_translate/workflow.py::_normalize_config` and `_validate_config`.

2. Run path + checkpoint setup
- Path resolution in `src/legalpdf_translate/output_paths.py::build_output_paths`.
- Checkpoint/run-state logic in `src/legalpdf_translate/checkpoint.py` and `src/legalpdf_translate/workflow.py::_resolve_paths_for_run` + `_load_or_initialize_run_state`.

3. Page selection
- Page count and selection in `src/legalpdf_translate/workflow.py::TranslationWorkflow.run` using `get_page_count` and `resolve_page_selection`.

4. Per-page extraction and route decision
- Extraction in `src/legalpdf_translate/workflow.py::_process_page` using `extract_ordered_page_text`.
- Route fields set per page: `source_route`, `source_route_reason`.
- OCR decision based on `RunConfig.ocr_mode` and extracted text usability.

5. Image decision and OCR path
- Image attach decision in `src/legalpdf_translate/workflow.py` with `should_include_image` and `_analyze_image_reason`.
- OCR engine build/policy in `src/legalpdf_translate/ocr_engine.py::build_ocr_engine`.

6. Translation request and retries
- OpenAI request path in `src/legalpdf_translate/workflow.py::_process_page`.
- Transport retries/backoff/rate-limit handling in `src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response`.

7. Validation and page output write
- Output parsing/validation in `src/legalpdf_translate/workflow.py::_evaluate_output` plus validators in `src/legalpdf_translate/validators.py`.
- Successful page writes to run `pages/` directory.

8. Final DOCX rebuild/export and summaries
- Final DOCX via `src/legalpdf_translate/docx_writer.py::assemble_docx` called from `TranslationWorkflow.run`.
- Run summary JSON from `src/legalpdf_translate/workflow.py::_write_run_summary`.
- Report events JSONL via `src/legalpdf_translate/run_report.py::RunEventCollector`.
- User-facing export report action in `src/legalpdf_translate/qt_gui/app_window.py::_open_run_report`.

Translation batching note:
- The app is page-by-page; not multi-page batch payloads. Source: `README.md` and per-page loop in `src/legalpdf_translate/workflow.py`.

Assistant routing hint: If asked "what happens from PDF to DOCX", inspect `workflow.py` (`run`, `_process_page`, `_write_run_summary`) first, then `docx_writer.py`, then `run_report.py`.

## E. Cost/time drivers + knobs - explain why costs/time jump (reasoning effort, image mode, retries, OCR, workers)
Key knobs and where they live:
- Effort and policy:
  - `RunConfig` fields in `src/legalpdf_translate/types.py`.
  - Policy resolution in `src/legalpdf_translate/workflow.py::_resolve_effort_policy_label`, `_resolve_attempt1_effort`, `_resolve_retry_effort`.
- Image mode:
  - `off|auto|always` via `RunConfig.image_mode` and `should_include_image` in workflow.
- OCR mode/engine:
  - `src/legalpdf_translate/types.py` + `src/legalpdf_translate/ocr_engine.py`.
- Workers/concurrency:
  - `RunConfig.workers` in workflow; page parallelism uses `ThreadPoolExecutor` in `TranslationWorkflow.run`.
- API retries/backoff/timeouts:
  - `src/legalpdf_translate/openai_client.py` (`max_transport_retries`, backoff cap, jitter, timeout).
- User-configurable perf defaults in settings:
  - `src/legalpdf_translate/user_settings.py` keys like `perf_max_transport_retries`, `perf_backoff_cap_seconds`, timeout keys.

Why cost/time can spike:
- Higher effort policy or xhigh paths increase token usage/time.
- `image_mode=auto/always` can attach images and increase processing load.
- OCR fallback adds extra work (local/API OCR).
- Transport retries/backoff from rate limits add wait time.
- High worker counts can increase throughput but can also trigger more 429/backoff in constrained environments.

Where to diagnose:
- Run summary totals + counts: `run_summary.json` written by `TranslationWorkflow._write_run_summary`.
- Admin diagnostics payload fields and per-page rollups in `run_summary.json` and `run_events.jsonl` when admin mode is on.
- Markdown report from `build_run_report_markdown`.

Assistant routing hint: If asked "why was this run expensive/slow", inspect `run_summary.json`, `run_events.jsonl`, then `workflow.py` effort/image/retry sections.

## F. Settings & secrets - where stored, how loaded, show/hide behavior, what must never be logged
Settings storage:
- Path resolver: `src/legalpdf_translate/user_settings.py::settings_path`.
- Load/save: `load_settings`, `save_settings`, `load_gui_settings`, `save_gui_settings`.
- App data dir helper: `app_data_dir`.

Secret storage:
- Keyring wrapper module: `src/legalpdf_translate/secrets_store.py`.
- Service/user keys:
  - `SERVICE = "LegalPDFTranslate"`
  - `USER_OPENAI = "openai_api_key"`
  - `USER_OCR = "ocr_api_key"`

Show/hide behavior in settings UI:
- Dialog class: `src/legalpdf_translate/qt_gui/dialogs.py::QtSettingsDialog`.
- Methods:
  - `_toggle_openai_key`
  - `_toggle_ocr_key`
  - `_refresh_key_status`
  - `_save_openai_key`, `_clear_openai_key`
  - `_save_ocr_key`, `_clear_ocr_key`

Loading/fallback behavior:
- OpenAI key resolution attempts stored key first then env fallback in `src/legalpdf_translate/openai_client.py`.
- OCR key resolution in `src/legalpdf_translate/ocr_engine.py::_resolve_api_key`.

Must never be logged or shared:
- API keys/tokens/auth headers.
- Raw secret-bearing payload fields.
- Use redaction when sharing logs/reports.
- Sanitization helpers exist in `src/legalpdf_translate/run_report.py` (`sanitize_text`, forbidden keys list).

Assistant routing hint: If asked "where is the API key stored" or "why show/hide fails", inspect `secrets_store.py` then `dialogs.py`, then key-related tests (`tests/test_secrets_store.py`, `tests/test_qt_settings_key_toggle.py`).

## G. Diagnostics & admin artifacts - logs, reports, run folders, exportable debug bundle ideas
Runtime details/logging surfaces:
- Details pane log append in `src/legalpdf_translate/qt_gui/app_window.py::_append_log`.
- Optional metadata log file path in app data logs dir (`_metadata_logs_dir`, `_metadata_log_file` in app window).

Run artifacts and folders:
- Run directory shape from `src/legalpdf_translate/output_paths.py` and workflow writes in `src/legalpdf_translate/workflow.py`.
- Typical artifacts:
  - `run_state.json`
  - `run_summary.json`
  - `run_events.jsonl` (admin diagnostics)
  - `analyze_report.json` (analyze mode)
  - `pages/` and `images/` (depending on keep settings)

Report export path:
- UI action `_open_run_report` in app window supports save Markdown and copy-to-clipboard.
- Report generation: `src/legalpdf_translate/run_report.py::build_run_report_markdown`.

Debug bundle grounding:
- Current implementation in `src/legalpdf_translate/qt_gui/dialogs.py::_create_debug_bundle`.
- Metadata path collector in `src/legalpdf_translate/qt_gui/app_window.py::collect_debug_bundle_metadata_paths`.

Safe sharing guidance:
- Share report markdown + summary/events metadata.
- Do not share secrets; redact sensitive strings before external sharing.
- Avoid sharing raw credential stores or full sensitive environment dumps.

Assistant routing hint: If asked "what should I send to debug", inspect `_create_debug_bundle`, `collect_debug_bundle_metadata_paths`, and `run_report.py` redaction behavior.

## H. Packaging/distribution - PyInstaller specs/scripts, outputs, how to run built exe
Packaging files:
- Spec: `build/pyinstaller_qt.spec`
- Build script: `scripts/build_qt.ps1`

Build command:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1
```

Output artifact:
- `dist\\legalpdf_translate\\LegalPDFTranslate.exe`

Run built exe:
```powershell
.\dist\legalpdf_translate\LegalPDFTranslate.exe
```

Common build failure points (grounded):
- Spec project-root resolution failure (see `pyinstaller_qt.spec` candidate logic and RuntimeError text).
- Missing icon/resources paths in spec/script checks.
- Missing hidden imports for keyring backends (listed in spec).
- Script-level expected output path checks in `scripts/build_qt.ps1`.

Assistant routing hint: If asked "why build failed", inspect `build/pyinstaller_qt.spec` and `scripts/build_qt.ps1`, then run `python -m pytest -q tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py`.

## I. Testing & verification - pytest, smoke checks, build checks
Primary verification commands:
```powershell
python -m pytest -q
python -m compileall src tests
```

Useful targeted checks:
```powershell
python -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py
python -m pytest -q tests/test_run_report.py tests/test_workflow_logging_safety.py
python -m pytest -q tests/test_secrets_store.py tests/test_qt_settings_key_toggle.py
python -m pytest -q tests/test_docx_writer.py tests/test_docx_writer_rtl.py
python -m pytest -q tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py
```

Quick path sanity checks:
```powershell
python -c "import legalpdf_translate, pathlib; print(pathlib.Path(legalpdf_translate.__file__).resolve())"
git status -sb
```

Assistant routing hint: If asked for "minimum QA after a change", run targeted tests for touched module plus full `python -m pytest -q`.

## J. Where is X? index - common tasks mapped to exact files/symbols
- Start Qt app: `src/legalpdf_translate/qt_gui/__main__.py`, `src/legalpdf_translate/qt_main.py::main`, `src/legalpdf_translate/qt_app.py::run`
- Main window behavior/state: `src/legalpdf_translate/qt_gui/app_window.py::QtMainWindow`
- Settings dialog: `src/legalpdf_translate/qt_gui/dialogs.py::QtSettingsDialog`
- Show/hide stored keys: `src/legalpdf_translate/qt_gui/dialogs.py::_toggle_openai_key`, `_toggle_ocr_key`, `_refresh_key_status`
- Translate pipeline orchestration: `src/legalpdf_translate/workflow.py::TranslationWorkflow.run`
- Per-page processing logic: `src/legalpdf_translate/workflow.py::_process_page`
- OCR policy and engines: `src/legalpdf_translate/ocr_engine.py::build_ocr_engine`
- OpenAI transport retries: `src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response`
- Run report rendering/redaction: `src/legalpdf_translate/run_report.py::build_run_report_markdown`, `sanitize_text`
- Export run report from UI: `src/legalpdf_translate/qt_gui/app_window.py::_open_run_report`
- Checkpoint/resume logic: `src/legalpdf_translate/checkpoint.py`, `src/legalpdf_translate/workflow.py::_load_or_initialize_run_state`
- Output/run folder naming: `src/legalpdf_translate/output_paths.py::build_output_paths`
- DOCX rebuild path: `src/legalpdf_translate/workflow.py::TranslationWorkflow.rebuild_docx`
- RTL DOCX formatting and mixed-direction run handling: `src/legalpdf_translate/docx_writer.py::assemble_docx`, `sanitize_bidi_controls`, `_segment_directional_runs`
- RTL DOCX regression tests: `tests/test_docx_writer_rtl.py`
- User settings persistence: `src/legalpdf_translate/user_settings.py::settings_path`, `load_gui_settings`, `save_gui_settings`
- Secret storage wrappers: `src/legalpdf_translate/secrets_store.py`
- Job log database path/schema: `src/legalpdf_translate/joblog_db.py::job_log_db_path`, `ensure_joblog_schema`
- CLI flags/flow: `src/legalpdf_translate/cli.py::build_arg_parser`, `main`
- Packaging/build: `build/pyinstaller_qt.spec`, `scripts/build_qt.ps1`
- Assistant routing hint: For unknown feature location, run `rg -n "keyword" src tests` and map hits to this index.
