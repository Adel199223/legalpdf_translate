# TRANSLATION_WORKFLOW

## What This Workflow Is For
Implementing or modifying the core PDF-to-DOCX translation product flow.

## Expected Outputs
- Scoped code/doc changes for translation behavior.
- Updated targeted tests for affected translation path.
- Validation summary with commands/results.

## When To Use
- Changes to per-page processing, prompt orchestration, validation, retry, or output assembly.
- Changes to analyze/report schema outputs.
- Changes to OCR advisor behavior or OCR/image recommendation logic.
- Changes to quality-risk scoring, review queue construction, or review export behavior.
- Changes to queue orchestration when it affects translation/report behavior.
- OCR-heavy runtime triage only after the dedicated triage workflow has isolated whether the failure is OCR, transport, or UI-close related.

## What Not To Do
- Don't use this workflow when the task is primarily DB/schema lifecycle work.
- Instead use `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`.
- Don't use this workflow when the task is primarily OCR-heavy runtime troubleshooting on a real failing document.
- Instead use `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`.

## Primary Files
- `src/legalpdf_translate/workflow.py`
- `src/legalpdf_translate/cost_guardrails.py`
- `src/legalpdf_translate/workflow_components/contracts.py`
- `src/legalpdf_translate/workflow_components/evaluation.py`
- `src/legalpdf_translate/workflow_components/quality_risk.py`
- `src/legalpdf_translate/workflow_components/ocr_advisor.py`
- `src/legalpdf_translate/workflow_components/summary.py`
- `src/legalpdf_translate/review_export.py`
- `src/legalpdf_translate/queue_runner.py`
- `src/legalpdf_translate/prompt_builder.py`
- `src/legalpdf_translate/validators.py`
- `src/legalpdf_translate/docx_writer.py`

## Minimal Commands
PowerShell:
```powershell
python -m pytest -q tests/test_workflow_parallel.py tests/test_prompt_builder.py
python -m pytest -q tests/test_run_report.py tests/test_cost_guardrails.py tests/test_quality_risk_scoring.py
python -m pytest -q tests/test_ocr_advisor_backend.py tests/test_review_export.py tests/test_queue_runner.py
```
POSIX:
```bash
python3 -m pytest -q tests/test_workflow_parallel.py tests/test_prompt_builder.py
python3 -m pytest -q tests/test_run_report.py tests/test_cost_guardrails.py tests/test_quality_risk_scoring.py
python3 -m pytest -q tests/test_ocr_advisor_backend.py tests/test_review_export.py tests/test_queue_runner.py
```

## Targeted Tests
- `tests/test_workflow_parallel.py`
- `tests/test_workflow_logging_safety.py`
- `tests/test_prompt_builder.py`
- `tests/test_translation_diagnostics.py`
- `tests/test_cost_guardrails.py`
- `tests/test_quality_risk_scoring.py`
- `tests/test_review_export.py`
- `tests/test_ocr_advisor_backend.py`
- `tests/test_ocr_advisor_backward_compat.py`
- `tests/test_ocr_language_profile_policy.py`
- `tests/test_ocr_local_pass_selection.py`
- `tests/test_ocr_policy_routing.py`
- `tests/test_workflow_ocr_availability.py`
- `tests/test_queue_runner.py`
- `tests/test_queue_failed_only_rerun.py`

## Failure Modes and Fallback Steps
- Regression in page-level routing: revert to last known-good route decision block and rerun targeted tests.
- Prompt-format drift: validate prompt builder tests and restore expected delimiters.
- Output validation breakage: run validator test subset and inspect failing gate details.

## Handoff Checklist
1. List touched files and rationale.
2. Include targeted test commands and outcomes.
3. Confirm no unrelated runtime behavior changed.
4. Ask docs sync prompt if change is significant.
