# PDF to DOCX Translation User Guide

## Use This Guide When
- You need help with the app's main workflow: translating a PDF into DOCX.
- You are supporting users who are unfamiliar with technical tooling.
- You want plain-language troubleshooting for failed or partial runs.

## Do Not Use This Guide For
- Deep implementation details for OCR/model internals.
- Database schema migration procedures.
- CI pipeline maintenance.

## For Agents: Support Interaction Contract
Response shape:
1. Plain explanation.
2. Numbered steps.
3. Canonical check against `APP_KNOWLEDGE.md`.
4. Uncertainty note when needed.

Define unavoidable technical terms in one sentence.

## Canonical Deference Rule
This user guide is not canonical architecture truth. Defer to `APP_KNOWLEDGE.md`, and treat source code as final truth on conflict.

## Quick Start (No Technical Background)
1. Open LegalPDF Translate.
2. Select your PDF.
3. Choose target language.
4. Choose output folder.
5. Start translation.
6. Open output DOCX when run completes.

## Terms in Plain English
- Target language: The language you want the final document in.
- Analyze-only: A mode that inspects extraction quality without translating.
- Retry: The app making another attempt after a failed page response.
- OCR: Reading text from page images when normal extraction is poor.
- Run summary: A final report about what happened in the run.

## Analyze + OCR Advisor
Use Analyze when you want the app to inspect the PDF before spending translation time or money.

1. Click `Analyze`.
2. Wait for the app to generate `analyze_report.json`.
3. If the app sees weak text extraction or layout risk, it can show an OCR Advisor recommendation.
4. The recommendation can suggest a different OCR mode and image mode.
5. In the GUI, `Apply` uses that recommendation for the next run only.
6. `Ignore` keeps your current settings and records that choice in the run metadata.

If no advisor appears, that usually means the app did not see enough evidence to recommend a change.

## Review Queue
After a run, the app can mark higher-risk pages for human review.

1. Open `Review Queue` from the main window.
2. Check the flagged page numbers, scores, reasons, and suggested action.
3. Export the queue if you want review files outside the app.
4. The export creates both CSV and Markdown files for the same queue.

If the Review Queue opens empty, the app did not flag any pages for extra review in that run.

## Save to Job Log
After a successful run, the app can prefill the Job Log dialog using the latest run artifacts.

1. Finish a translation.
2. Open `Save to Job Log`.
3. Confirm the prefilled values when available:
   - run ID
   - target language
   - total tokens
   - estimated API cost
   - quality risk score
4. Edit any field you want before saving.

The prefill helps, but you still stay in control of the saved row.

## Queue Runs
Use queue mode when you want several PDFs to run in order.

### GUI queue flow
1. Open `Show Advanced`.
2. Pick a queue manifest file (`.json` or `.jsonl`).
3. Click `Run Queue`.
4. Watch `Queue status` as jobs move through `pending`, `running`, `done`, `failed`, or `skipped`.
5. If you stop the queue, completed jobs stay completed and untouched jobs remain resumable.
6. Turn on `Rerun failed only` if you want the next queue run to retry only failed jobs from checkpoint state.

### CLI queue flow
Run queue mode from terminal like this:

```bash
legalpdf-translate --queue-manifest queue.jsonl --lang EN --outdir out
legalpdf-translate --queue-manifest queue.jsonl --rerun-failed-only true --lang EN --outdir out
```

Queue mode writes these sidecar files next to the manifest:
- `<manifest_stem>.queue_checkpoint.json`
- `<manifest_stem>.queue_summary.json`

## Troubleshooting
1. If setup commands fail with `html.entities` or `idna` import errors, run `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`, then activate `. .\.venv311\Scripts\Activate.ps1`.
2. If output is missing pages, check if run stopped early and use resume.
3. If run is slow, lower worker count and retry.
4. If text quality is poor, run Analyze first and inspect OCR routing or advisor recommendations before translating again.
5. If terminology is inconsistent, review glossary settings and rerun affected pages.
6. If no advisor appears after Analyze, the app may have found no strong signal for a better OCR/image setting.
7. If queue mode will not start, confirm the manifest file exists and each job has valid PDF/output information.
8. If a queue was interrupted, rerun it with the same manifest; completed jobs should be skipped automatically.
9. If the Review Queue is empty, that means no pages crossed the app's current risk threshold.
10. OCR can improve difficult scans, but it still depends on source quality and cannot fully repair a badly scanned page.

## Cost Guardrails (CLI)
Use this when you run from terminal and want cost protection.

1. Set a budget cap:
   - `legalpdf-translate --pdf <file> --lang EN --outdir <dir> --budget-cap-usd 3.50`
2. Choose behavior if estimate exceeds cap:
   - `--budget-on-exceed warn` (default): shows warning and continues.
   - `--budget-on-exceed block`: stops before page processing.
3. Optional profile label:
   - `--cost-profile-id default_local`
4. Check the run report and `run_summary.json` for:
   - `budget_decision`, `budget_decision_reason`, `budget_pre_run`, `budget_post_run`.

## Canonical Checkpoints for Agents
- Runtime behavior: `APP_KNOWLEDGE.md`
- Workflow specifics: `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- Data/persistence behavior: `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`
