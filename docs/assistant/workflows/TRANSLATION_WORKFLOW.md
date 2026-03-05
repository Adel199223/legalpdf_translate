# TRANSLATION_WORKFLOW

## What This Workflow Is For
Implementing or modifying the core PDF-to-DOCX translation product flow.

## Expected Outputs
- Scoped code/doc changes for translation behavior.
- Updated targeted tests for affected translation path.
- Validation summary with commands/results.

## When To Use
- Changes to per-page processing, prompt orchestration, validation, retry, or output assembly.

## What Not To Do
- Don't use this workflow when the task is primarily DB/schema lifecycle work.
- Instead use `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`.

## Primary Files
- `src/legalpdf_translate/workflow.py`
- `src/legalpdf_translate/cost_guardrails.py`
- `src/legalpdf_translate/workflow_components/contracts.py`
- `src/legalpdf_translate/workflow_components/evaluation.py`
- `src/legalpdf_translate/workflow_components/summary.py`
- `src/legalpdf_translate/prompt_builder.py`
- `src/legalpdf_translate/validators.py`
- `src/legalpdf_translate/docx_writer.py`

## Minimal Commands
PowerShell:
```powershell
python -m pytest -q tests/test_workflow_parallel.py tests/test_prompt_builder.py
python -m pytest -q tests/test_translation_report.py tests/test_run_report.py
```
POSIX:
```bash
python3 -m pytest -q tests/test_workflow_parallel.py tests/test_prompt_builder.py
python3 -m pytest -q tests/test_translation_report.py tests/test_run_report.py
```

## Targeted Tests
- `tests/test_workflow_parallel.py`
- `tests/test_workflow_logging_safety.py`
- `tests/test_prompt_builder.py`
- `tests/test_translation_diagnostics.py`
- `tests/test_cost_guardrails.py`

## Failure Modes and Fallback Steps
- Regression in page-level routing: revert to last known-good route decision block and rerun targeted tests.
- Prompt-format drift: validate prompt builder tests and restore expected delimiters.
- Output validation breakage: run validator test subset and inspect failing gate details.

## Handoff Checklist
1. List touched files and rationale.
2. Include targeted test commands and outcomes.
3. Confirm no unrelated runtime behavior changed.
4. Ask docs sync prompt if change is significant.
