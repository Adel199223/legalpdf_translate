# APP_KNOWLEDGE

This file is canonical for app-level architecture and status.

## App Summary
LegalPDF Translate is a Windows-first Python app that translates PDFs into DOCX using one-page-per-request processing for each translation job, and now also supports sequential multi-document queue execution.

- Primary UI: Qt/PySide6 desktop app.
- Secondary interface: CLI.
- Model transport: OpenAI Responses API.
- Key invariant: page-by-page translation flow, no whole-document batch request.

## Entrypoints
- GUI: `python -m legalpdf_translate.qt_app`
- GUI compatibility shim: `python -m legalpdf_translate.qt_main`
- CLI: `legalpdf-translate --pdf <file> --lang EN|FR|AR --outdir <dir>`
  - Cost guardrails (optional): `--budget-cap-usd <float> --cost-profile-id <string> --budget-on-exceed warn|block`
  - Queue mode (optional): `legalpdf-translate --queue-manifest <manifest.jsonl> --rerun-failed-only true --lang EN --outdir <dir>`
- Build: `powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1`

## Desktop UI Shell
- The desktop app now uses a dashboard-style shell instead of the older stacked utility card.
- Main visible regions:
  - left sidebar: `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, `Profile`
  - hero row: centered `LegalPDF Translate` title and right-aligned status text
  - left card: `Job Setup`
  - right card: `Conversion Output`
  - bottom action rail: `Start Translate`, `Cancel`, `...`
- `Advanced Settings` stays collapsed by default inside the setup card.
- Review Queue and Save to Job Log remain available from the `Tools` menu; the `...` menu keeps output/report/job-log actions.
- The shell uses three responsive layout modes:
  - `desktop_exact`
  - `desktop_compact`
  - `stacked_compact`

## Core Runtime Modules
- `src/legalpdf_translate/workflow.py`: translation pipeline orchestration.
- `src/legalpdf_translate/cost_guardrails.py`: deterministic pre-run/post-run cost estimation and budget decisions.
- `src/legalpdf_translate/queue_runner.py`: sequential queue execution, checkpointing, and queue summaries.
- `src/legalpdf_translate/review_export.py`: review queue export to CSV and Markdown.
- `src/legalpdf_translate/workflow_components/contracts.py`: typed workflow internal contracts.
- `src/legalpdf_translate/workflow_components/evaluation.py`: output-evaluation and retry-reason delegation.
- `src/legalpdf_translate/workflow_components/quality_risk.py`: deterministic quality risk scoring and review queue construction.
- `src/legalpdf_translate/workflow_components/ocr_advisor.py`: deterministic OCR/image recommendation logic.
- `src/legalpdf_translate/workflow_components/summary.py`: run-summary and cost/suspected-cause delegation.
- `src/legalpdf_translate/cli.py`: CLI parsing/execution.
- `src/legalpdf_translate/qt_gui/app_window.py`: main GUI workflow orchestration.
- `src/legalpdf_translate/openai_client.py`: OpenAI transport and retry handling.
- `src/legalpdf_translate/ocr_engine.py`: OCR routing and policy.
- `src/legalpdf_translate/docx_writer.py`: DOCX output construction.
- `src/legalpdf_translate/joblog_db.py`: SQLite schema and migrations for job logging.
- `src/legalpdf_translate/user_settings.py`: settings schema and persistence.

## Primary User Journeys
1. Translate a PDF to EN/FR/AR.
2. Analyze-only extraction preflight without translation API calls.
3. Resume interrupted runs from checkpoint artifacts.
4. Rebuild DOCX from existing page outputs.
5. Use glossary and diagnostics workflows for consistency and QA.
6. Optionally apply CLI budget guardrails (`warn` continue or `block` before page processing).
7. Run analyze-only first and inspect/apply an OCR advisor recommendation before translation.
8. Inspect or export a Review Queue when high-risk pages are flagged.
9. Save completed runs to the Job Log with prefilled run metrics.
10. Execute a queue manifest with checkpoint-aware resume and failed-only rerun behavior.

## Output and Run Artifacts
Run artifacts live under:
- `<outdir>/<pdf_stem>_<LANG>_run/`

Typical files:
- `pages/page_XXXX.txt`
- `run_state.json`
- `run_summary.json`
- `run_events.jsonl`
- `analyze_report.json` (analyze-only)

`run_summary.json` keeps existing totals and now also supports additive cost/risk/advisor fields:
- `cost_estimation_status`
- `cost_profile_id`
- `budget_cap_usd`
- `budget_decision`
- `budget_decision_reason`
- `budget_pre_run`
- `budget_post_run`
- `quality_risk_score`
- `review_queue_count`
- `review_queue`
- `advisor_recommendation_applied`
- `advisor_recommendation`

`analyze_report.json` now also supports additive OCR advisor keys:
- `recommended_ocr_mode`
- `recommended_image_mode`
- `recommendation_reasons`
- `confidence`
- `advisor_track`

Queue manifests create sidecar artifacts beside the manifest file:
- `<manifest_stem>.queue_checkpoint.json`
- `<manifest_stem>.queue_summary.json`

## Persistence Notes
- The job log SQLite schema now includes additive run-metric/risk columns: `run_id`, `target_lang`, `total_tokens`, `estimated_api_cost`, and `quality_risk_score`.
- Save-to-Job-Log pre-fills those values from `run_summary.json` when available, while preserving user edit control before save.

## Queue Behavior Notes
- Queue execution is sequential and checkpoint-aware.
- Queue cancellation is cooperative and leaves untouched jobs resumable instead of converting them into failures.

## Governance and Routing Docs
- Assistant docs index: `docs/assistant/INDEX.md`
- Machine routing map: `docs/assistant/manifest.json`
- Golden rules: `docs/assistant/GOLDEN_PRINCIPLES.md`
- Workflow runbooks: `docs/assistant/workflows/`
- User guides: `docs/assistant/features/`
- External-source registry: `docs/assistant/EXTERNAL_SOURCE_REGISTRY.md`

## Module Status (Bootstrap v2)
All optional modules are enabled and enforced:
- Beginner Layer
- Localization + Performance
- Reference Discovery
- Browser Automation + Environment Provenance
- Cloud Machine Evaluation + Local Acceptance Gate
- Staged Execution
- OpenAI Docs + Citation

## Canonical and Bridge Contract
- Canonical app truth lives here.
- `docs/assistant/APP_KNOWLEDGE.md` is intentionally shorter and defers here.
- Source code is final truth when documentation conflicts occur.

## Deep-Dive Supplemental References
These remain valid supplemental references for implementation detail:
- `docs/assistant/API_PROMPTS.md`
- `docs/assistant/PROMPTS_KNOWLEDGE.md`
- `docs/assistant/QT_UI_KNOWLEDGE.md`
- `docs/assistant/QT_UI_PLAYBOOK.md`
- `docs/assistant/GLOSSARY_BUILDER_KNOWLEDGE.md`
- `docs/assistant/WORKFLOW_GIT_AI.md`

## Verification Commands
PowerShell:
- `python -m pytest -q`
- `python -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

POSIX:
- `python3 -m pytest -q`
- `python3 -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

## Local Python Baseline (Windows)
- Preferred interpreter: Python `3.11`.
- Preferred local environment path: `.venv311`.
- Bootstrap/recovery script: `scripts/setup_python311_env.ps1`.

If local `pip`/`pytest` fails with import errors like `html.entities` or `idna`, treat it as a machine Python issue and rebuild `.venv311`:
- `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`
- `. .\.venv311\Scripts\Activate.ps1`
