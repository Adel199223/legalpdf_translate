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
- Build consistency glossary suggestions from corpus pages (`src/legalpdf_translate/qt_gui/app_window.py::_open_glossary_builder_dialog`, `src/legalpdf_translate/qt_gui/tools_dialogs.py::QtGlossaryBuilderDialog`).
- Run calibration QA audit on sampled pages (`src/legalpdf_translate/qt_gui/app_window.py::_open_calibration_audit_dialog`, `src/legalpdf_translate/qt_gui/tools_dialogs.py::QtCalibrationAuditDialog`).
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
- `src/legalpdf_translate/qt_gui/tools_dialogs.py`: Glossary Builder and Calibration Audit dialogs/workers.
- `src/legalpdf_translate/qt_gui/worker.py`: Qt thread workers for run/analyze/rebuild.
- `src/legalpdf_translate/workflow.py`: translation pipeline orchestration (`TranslationWorkflow`).
- `docs/assistant/API_PROMPTS.md`: canonical assistant-facing catalog of system/user prompt templates and API payload shapes (grounded to code symbols).
- `src/legalpdf_translate/run_report.py`: event collector, redaction/sanitization, Markdown+JSON report builder.
- `src/legalpdf_translate/glossary.py`: glossary schema/normalization helpers (`GlossaryEntry`, `normalize_glossaries`), tier controls (`tier`, `normalize_enabled_tiers_by_target_lang`), source-language detection/filtering for prompt guidance (`detect_source_lang_for_glossary`, `filter_entries_for_prompt`), prompt sort/cap helpers, and legacy file-rule compatibility helpers.
- `src/legalpdf_translate/glossary_builder.py`: consistency glossary suggestion mining (frequency/dispersion thresholds + markdown/json suggestion rendering).
- `src/legalpdf_translate/study_glossary.py`: learning-only glossary mining/scoring/coverage helpers (`mine_study_candidates`, `compute_non_overlapping_tier_assignment`, `apply_subsumption_suppression`, `normalize_study_entries`) and translation-fill helpers for short term cards.
- `src/legalpdf_translate/calibration_audit.py`: deterministic page sampling, forced-OCR QA checks, verifier-LLM JSON retry handling, calibration artifact writing.
- `src/legalpdf_translate/openai_client.py`: transport retries/backoff wrapper around OpenAI Responses API.
- `src/legalpdf_translate/ocr_engine.py`: OCR engine policy and fallback (`local`, `local_then_api`, `api`).
- `src/legalpdf_translate/checkpoint.py`: run-state schema/persistence and resume compatibility.
- `src/legalpdf_translate/output_paths.py`: deterministic run/output paths and writable outdir checks.
- `src/legalpdf_translate/user_settings.py`: GUI/joblog settings persistence and normalization.
- `src/legalpdf_translate/qt_gui/dialogs.py::_build_tab_study`: Study Glossary settings-tab UI (run-folder builder, streaming generation worker, cancel, search/Ctrl+F, quiz/review, Markdown export).
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
- Per-language glossary prompt guidance is injected in `src/legalpdf_translate/workflow.py::_process_page` via `TranslationWorkflow._append_glossary_prompt` + `src/legalpdf_translate/glossary.py::format_glossary_for_prompt`.
- Source-language-aware + tier-aware filtering happens before prompt injection (`detect_source_lang_for_glossary`, `filter_entries_for_prompt`) so rows can target source language (`PT|EN|FR|ANY|AUTO`) and only active tiers are injected.
- Injection is token-controlled: entries are sorted by tier/impact and capped (`max 50` entries and `max 6000` chars) before prompt append.
- Optional per-language addendum text is appended after glossary block in `src/legalpdf_translate/workflow.py::TranslationWorkflow._append_prompt_addendum` (settings key `prompt_addendum_by_lang`).
- Workflow output finalization keeps parser/normalizer/validator behavior and no longer applies glossary blind post-replacements in `_evaluate_output`.
- Study Glossary is intentionally isolated from translation prompt injection: its data lives in `study_glossary_entries` (settings) and UI/helpers under `src/legalpdf_translate/study_glossary.py` + `src/legalpdf_translate/qt_gui/dialogs.py`; translation still only uses `glossaries_by_lang` in `TranslationWorkflow._append_glossary_prompt`.
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
- Glossary settings keys:
  - `personal_glossaries_by_lang` (personal consistency glossary, per target language)
  - `glossaries_by_lang` (per-target-language table rows)
  - `prompt_addendum_by_lang` (optional per-target-language prompt addendum text)
  - `enabled_glossary_tiers_by_target_lang` (per-target-language active tiers for prompt injection)
  - `glossary_seed_version` (one-time AR seed tracking)
  - `glossary_file_path` (legacy file-path fallback)
- Calibration settings keys:
  - `calibration_sample_pages_default`
  - `calibration_user_seed`
  - `calibration_enable_excerpt_storage`
  - `calibration_excerpt_max_chars`
- Consistency glossary scopes:
  - Personal scope in settings: `personal_glossaries_by_lang`
  - Project/shared scope from file: `glossary_file_path` loaded by `src/legalpdf_translate/glossary.py::load_project_glossaries`
  - Merge policy in runtime: `src/legalpdf_translate/glossary.py::merge_glossary_scopes` (personal overrides conflict rows)
- Study Glossary settings keys (learning-only, not injected into translation prompts):
  - `study_glossary_entries`
  - `study_glossary_include_snippets`
  - `study_glossary_snippet_max_chars`
  - `study_glossary_last_run_dirs`
  - `study_glossary_corpus_source`
  - `study_glossary_pdf_paths`
  - `study_glossary_default_coverage_percent`
- Glossary UI now has a dedicated table editor tab in `src/legalpdf_translate/qt_gui/dialogs.py::_build_tab_glossary` with rows keyed on source phrase:
  - `Source phrase (PDF text)`
  - `Preferred translation`
  - `Match`
  - `Source lang` (`AUTO|ANY|PT|EN|FR`)
  - `Tier` (`1..6`)
  - Search filter + `Ctrl+F` focus shortcut
  - Active tier checkboxes (`T1..T6`) controlling prompt injection
  - content-only Markdown export (`Export...`) for consistency glossary review (`AI_Glossary_YYYY-MM-DD.md`)
- Study Glossary UI lives in `src/legalpdf_translate/qt_gui/dialogs.py::_build_tab_study` and is separate from AI Glossary:
  - candidate builder supports corpus source modes:
    - `Run folders` (default; reuses `pages/page_*.txt` when present)
    - `Current PDF only` (active PDF from main window)
    - `Select PDFs...` (explicit multi-file list)
    - `From Job Log runs` (shown but unavailable in current version; no joblog run/pdf-path migration)
  - streaming candidate generation with cancel support (no full corpus text list in memory)
  - search + category/status/coverage filters + `Ctrl+F`
  - non-overlapping 20/80 coverage assignment (longest-match-first: tri->bi->uni) for tiering stability
  - subsumption suppression demotes short noisy terms to `LongTail` when longer phrases already account for most matches
  - learning statuses (`new|learning|known|hard`) and review dates
  - optional snippet storage (capped, opt-in)
  - optional manual action `Copy selected to AI Glossary...`:
    - explicit confirmation required
    - defaults: `match=exact`, `source_lang=PT`, `tier=2`
    - copies only non-empty target-language translations
    - duplicate rows skipped; conflicts prompt for skip vs replace (never silent overwrite)
  - content-only Markdown export (`Export...`) with tier sections (`Core80`, `Next15`, `LongTail`) and columns `PT/AR/FR/EN/TF/Pages/Docs/Tier/Category/Status`
- Glossary Builder / Calibration Audit dialogs are launched from main window actions in `src/legalpdf_translate/qt_gui/app_window.py` and implemented in `src/legalpdf_translate/qt_gui/tools_dialogs.py`:
  - `QtGlossaryBuilderDialog` mines candidates and writes `glossary_builder_suggestions.json/.md`
  - `QtCalibrationAuditDialog` writes `calibration_report.json/.md` and `calibration_suggestions.json`
  - Both use explicit Apply/Cancel flows and do not auto-modify prompt templates.

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
- Glossary path resolution: CLI `--glossary-file` (`src/legalpdf_translate/cli.py`) overrides settings `glossary_file_path`; literal legacy rules are imported as prompt guidance rows for compatibility.

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
- Glossary table + prompt guidance: `src/legalpdf_translate/qt_gui/dialogs.py::_build_tab_glossary`, `_set_glossaries_from_settings`, `_read_glossary_table_rows`, `_export_consistency_glossary_markdown`; `src/legalpdf_translate/glossary.py::normalize_glossaries`, `normalize_enabled_tiers_by_target_lang`, `build_consistency_glossary_markdown`, `detect_source_lang_for_glossary`, `filter_entries_for_prompt`, `sort_entries_for_prompt`, `cap_entries_for_prompt`, `format_glossary_for_prompt`; `src/legalpdf_translate/workflow.py::_append_glossary_prompt`
- Glossary scope merge/project loading: `src/legalpdf_translate/glossary.py::load_project_glossaries`, `merge_glossary_scopes`, `save_project_glossaries`; runtime use in `src/legalpdf_translate/workflow.py::TranslationWorkflow.run`
- Prompt addendum append point: `src/legalpdf_translate/workflow.py::_append_prompt_addendum`; settings key `prompt_addendum_by_lang`
- Glossary Builder dialog/actions: `src/legalpdf_translate/qt_gui/app_window.py::_open_glossary_builder_dialog`, `src/legalpdf_translate/qt_gui/tools_dialogs.py::QtGlossaryBuilderDialog`, `_GlossaryBuilderWorker`
- Calibration Audit dialog/actions: `src/legalpdf_translate/qt_gui/app_window.py::_open_calibration_audit_dialog`, `src/legalpdf_translate/qt_gui/tools_dialogs.py::QtCalibrationAuditDialog`, `_CalibrationAuditWorker`; backend `src/legalpdf_translate/calibration_audit.py::run_calibration_audit`, `pick_sample_pages`
- Study Glossary (learning-only): `src/legalpdf_translate/qt_gui/dialogs.py::_build_tab_study`, `_generate_study_candidates`, `_cancel_study_generation`, `_export_study_glossary_markdown`, `_add_selected_candidates_to_study_glossary`; `src/legalpdf_translate/study_glossary.py::tokenize_pt`, `build_ngram_index`, `count_non_overlapping_matches`, `compute_non_overlapping_tier_assignment`, `apply_subsumption_suppression`, `update_candidate_stats_from_page`, `finalize_study_candidates`, `build_study_glossary_markdown`, `normalize_study_entries`, `merge_study_entries`
- Study Glossary settings keys/normalization: `src/legalpdf_translate/user_settings.py::load_gui_settings` (`study_glossary_entries`, snippet/corpus/coverage keys)
- Legacy glossary file fallback: `src/legalpdf_translate/glossary.py::load_glossary`, `entries_from_legacy_rules`; setting key `glossary_file_path`
- AR glossary integration point: `src/legalpdf_translate/workflow.py::_process_page` (prompt block injection)
- RTL DOCX formatting and mixed-direction run handling: `src/legalpdf_translate/docx_writer.py::assemble_docx`, `sanitize_bidi_controls`, `_segment_directional_runs`
- RTL DOCX regression tests: `tests/test_docx_writer_rtl.py`
- User settings persistence: `src/legalpdf_translate/user_settings.py::settings_path`, `load_gui_settings`, `save_gui_settings`
- Secret storage wrappers: `src/legalpdf_translate/secrets_store.py`
- Job log database path/schema: `src/legalpdf_translate/joblog_db.py::job_log_db_path`, `ensure_joblog_schema`
- CLI flags/flow: `src/legalpdf_translate/cli.py::build_arg_parser`, `main`
- Packaging/build: `build/pyinstaller_qt.spec`, `scripts/build_qt.ps1`
- API prompts/templates catalog: `docs/assistant/API_PROMPTS.md`; implementation paths: `src/legalpdf_translate/prompt_builder.py::build_page_prompt`, `src/legalpdf_translate/prompt_builder.py::build_retry_prompt`, `src/legalpdf_translate/openai_client.py::OpenAIResponsesClient.create_page_response`, `src/legalpdf_translate/workflow.py::_process_page`
- Retry formatting prompt location: `docs/assistant/API_PROMPTS.md` section `F`; implementation: `src/legalpdf_translate/prompt_builder.py::build_retry_prompt`
- System instruction files location: `docs/assistant/API_PROMPTS.md` section `A`; files: `resources/system_instructions_enfr.txt`, `resources/system_instructions_ar.txt`; loader: `src/legalpdf_translate/resources_loader.py::load_system_instructions`
- Assistant routing hint: For unknown feature location, run `rg -n "keyword" src tests` and map hits to this index.
