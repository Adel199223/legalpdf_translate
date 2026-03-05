# APP_KNOWLEDGE

This file is canonical for app-level architecture and status.

## App Summary
LegalPDF Translate is a Windows-first Python app that translates one PDF into one DOCX using one-page-per-request processing.

- Primary UI: Qt/PySide6 desktop app.
- Secondary interface: CLI.
- Model transport: OpenAI Responses API.
- Key invariant: page-by-page translation flow, no whole-document batch request.

## Entrypoints
- GUI: `python -m legalpdf_translate.qt_gui`
- CLI: `legalpdf-translate --pdf <file> --lang EN|FR|AR --outdir <dir>`
  - Cost guardrails (optional): `--budget-cap-usd <float> --cost-profile-id <string> --budget-on-exceed warn|block`
- Build: `powershell -ExecutionPolicy Bypass -File scripts/build_qt.ps1`

## Core Runtime Modules
- `src/legalpdf_translate/workflow.py`: translation pipeline orchestration.
- `src/legalpdf_translate/cost_guardrails.py`: deterministic pre-run/post-run cost estimation and budget decisions.
- `src/legalpdf_translate/workflow_components/contracts.py`: typed workflow internal contracts.
- `src/legalpdf_translate/workflow_components/evaluation.py`: output-evaluation and retry-reason delegation.
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

## Output and Run Artifacts
Run artifacts live under:
- `<outdir>/<pdf_stem>_<LANG>_run/`

Typical files:
- `pages/page_XXXX.txt`
- `run_state.json`
- `run_summary.json`
- `run_events.jsonl`
- `analyze_report.json` (analyze-only)

`run_summary.json` keeps existing totals and now also supports additive cost-guardrail fields:
- `cost_estimation_status`
- `cost_profile_id`
- `budget_cap_usd`
- `budget_decision`
- `budget_decision_reason`
- `budget_pre_run`
- `budget_post_run`

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
