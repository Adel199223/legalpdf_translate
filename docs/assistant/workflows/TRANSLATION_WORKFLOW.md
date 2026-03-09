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
- Changes to Gmail-intake run/report linkage such as `gmail_batch_context` in `run_summary.json` or `run_report.md`.
- Changes to Gmail attachment-review prepare behavior such as per-attachment start-page selection, preview-backed staging, or review-to-prepare handoff.
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
- `src/legalpdf_translate/openai_client.py`
- `src/legalpdf_translate/cost_guardrails.py`
- `src/legalpdf_translate/workflow_components/contracts.py`
- `src/legalpdf_translate/workflow_components/evaluation.py`
- `src/legalpdf_translate/workflow_components/quality_risk.py`
- `src/legalpdf_translate/workflow_components/ocr_advisor.py`
- `src/legalpdf_translate/workflow_components/summary.py`
- `src/legalpdf_translate/review_export.py`
- `src/legalpdf_translate/queue_runner.py`
- `src/legalpdf_translate/gmail_batch.py`
- `src/legalpdf_translate/prompt_builder.py`
- `src/legalpdf_translate/validators.py`
- `src/legalpdf_translate/docx_writer.py`

## Minimal Commands
PowerShell:
```powershell
python -m pytest -q tests/test_workflow_parallel.py tests/test_prompt_builder.py
python -m pytest -q tests/test_run_report.py tests/test_cost_guardrails.py tests/test_quality_risk_scoring.py
python -m pytest -q tests/test_ocr_advisor_backend.py tests/test_review_export.py tests/test_queue_runner.py
python -m pytest -q tests/test_gmail_batch.py tests/test_translation_report.py tests/test_workflow_ar_token_lock.py
```
POSIX:
```bash
python3 -m pytest -q tests/test_workflow_parallel.py tests/test_prompt_builder.py
python3 -m pytest -q tests/test_run_report.py tests/test_cost_guardrails.py tests/test_quality_risk_scoring.py
python3 -m pytest -q tests/test_ocr_advisor_backend.py tests/test_review_export.py tests/test_queue_runner.py
python3 -m pytest -q tests/test_gmail_batch.py tests/test_translation_report.py tests/test_workflow_ar_token_lock.py
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
- `tests/test_gmail_batch.py`
- `tests/test_run_report.py`
- `tests/test_translation_report.py`
- `tests/test_workflow_ar_token_lock.py`

## Failure Modes and Fallback Steps
- Regression in page-level routing: revert to last known-good route decision block and rerun targeted tests.
- Prompt-format drift: validate prompt builder tests and restore expected delimiters.
- Output validation breakage: run validator test subset and inspect failing gate details.
- Gmail-intake translation failure: inspect `run_report.md` / `run_summary.json` first. For Arabic, check additive `validator_defect_reason`, `ar_violation_kind`, and sampled snippets before changing prompts or validators.
- Gmail batch finalization/draft failure: inspect the durable `gmail_batch_session.json` under `<effective_outdir>/_gmail_batch_sessions/<session_id>/` before debugging Gmail transport or attachments ad hoc.
- Arabic DOCX visual-alignment complaint: treat the Word review gate as the current supported runtime behavior first. Verify the Windows Word/manual-or-assisted review path before attempting more OOXML-writer changes.
- Arabic review-gate automation failure: validate on the same Windows host with installed Word and PowerShell COM. WSL-only checks are insufficient for this feature.
- Repeated Gmail intake “accepted but idle” reports: verify the listener on `127.0.0.1:<gmail_intake_port>` belongs to `python.exe -m legalpdf_translate.qt_app`, not to `pytest`.
- OCR-heavy transport stall: check the authoritative request budgets first. The app now owns total budgets and disables SDK implicit retries, so a text-only OCR-success page should fail or complete within the text-page deadline instead of drifting into an hour-long wait.
- Suspected rate-limit report with `rate_limit_hits=0`: treat it as transport instability until proven otherwise. Current failure classification distinguishes `transport_instability` from true rate limiting.

## Runtime Contracts Added By OCR Stabilization
- Request deadlines are authoritative and owned by the app, not the SDK:
  - text-only translation page: `480s`
  - image-backed translation page: `720s`
  - OCR API request: `240s`
  - metadata/header AI request: `120s`
- SDK implicit retries are disabled; app-level retries consume the remaining page/request budget.
- `run_summary.json` now carries `failure_context` for bounded runtime failures:
  - `request_type`
  - `request_timeout_budget_seconds`
  - `request_elapsed_before_failure_seconds`
  - `cancel_requested_before_failure`
  - `exception_class`
- Gmail-intake runs now also carry additive `gmail_batch_context` with:
  - `session_id`
  - `message_id`
  - `thread_id`
  - selected attachment filename/count
  - selected target language
  - selected start page
  - durable `gmail_batch_session.json` path
- OCR-success pages remain text-first. Image attachment should stay off unless a concrete layout/quality signal justifies it.

## Handoff Checklist
1. List touched files and rationale.
2. Include targeted test commands and outcomes.
3. Confirm no unrelated runtime behavior changed.
4. Ask the docs sync prompt only if the change is significant and relevant touched-scope docs still remain unsynced.
