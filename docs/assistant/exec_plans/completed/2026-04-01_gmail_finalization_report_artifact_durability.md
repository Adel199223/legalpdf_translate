# ExecPlan: Harden Gmail Finalization Report Artifact Durability

## Context
- The live Gmail/browser/Word finalization flow is working end to end.
- The generated Gmail finalization report is broadly correct, but it records the confirmed translated DOCX through the Gmail draft staging copy in the batch temp workspace.
- A durable translated DOCX also exists in the user output area, so the report is currently pointing at the less trustworthy long-term artifact.

## Goals
1. Preserve the current Gmail draft creation flow exactly as-is.
2. Distinguish the durable translated DOCX from the staged Gmail draft attachment copy in Gmail batch state.
3. Make restored sessions and finalization reports prefer the durable translated DOCX path for operator-facing references.
4. Add path-source/existence diagnostics so the report stays explicit when fallback is required.
5. Validate that the end-to-end Gmail finalization path and success-state reporting still work unchanged.

## Implementation Plan
### 1. Batch model split
- Extend the Gmail batch confirmed-item model to carry both the durable translated DOCX path and the staged draft DOCX path.
- Keep the staged copy as the attachment source for Gmail draft creation.
- Keep the durable path as the report/session source of truth.

### 2. Session/report serialization
- Update Gmail batch/session serializers and restored-session builders to persist both paths.
- Prefer the durable translated DOCX path in confirmed-item payloads and finalization report contexts.
- Add additive path audit metadata describing source selection and file existence.

### 3. Regression coverage
- Extend service and API tests to cover:
  - fresh confirmation storing both durable and staged DOCX paths
  - restored completed sessions preferring the durable path
  - report generation including durable-path references and path diagnostics
  - draft attachment flow still using the staged path

### 4. Acceptance
- Run focused pytest for Gmail batch/session/report paths.
- Re-run live localhost finalization report generation from the resumed completed session and verify the report references the durable translated DOCX path under `Downloads` when available.

## Outcome
- Completed on 2026-04-01.
- Gmail batch confirmed items now persist both:
  - `translated_docx_path` as the durable operator-facing translated DOCX
  - `staged_translated_docx_path` as the Gmail draft attachment copy
- Gmail batch session payload `runs` now persist `durable_translated_docx_path` for future restores.
- Restored legacy sessions now repair finalization report contexts by preferring, in order:
  1. an existing durable run artifact
  2. an existing durable output-directory artifact
  3. any explicit durable path already present
  4. the staged temp copy only as explicit fallback
- Finalization report payloads now carry source/existence metadata for translated DOCX and honorários outputs.

## Validation
- `.venv311\Scripts\python.exe -m py_compile src/legalpdf_translate/gmail_batch.py src/legalpdf_translate/gmail_browser_service.py tests/test_gmail_batch.py tests/test_gmail_browser_service.py tests/test_qt_app_state.py tests/test_shadow_web_api.py`
- `.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_batch.py tests/test_gmail_browser_service.py tests/test_qt_app_state.py tests/test_shadow_web_api.py`
  - Result: `254 passed`
- Live localhost acceptance on `127.0.0.1:8877`
  - Runtime serving `feat/gmail-finalization-report-success@18be21e`
  - Resumed completed Gmail batch session repaired to:
    - `translated_docx_path = C:\Users\FA507\Downloads\sentença 305_EN_20260401_141119.docx`
    - `translated_docx_path_source = durable`
    - `translated_docx_path_exists = true`
  - Fresh generated report:
    - `C:\Users\FA507\Downloads\power_tools\gmail_finalization_report_20260401_135932.md`
    - references the durable translated DOCX as primary and the staged temp copy only as diagnostic context
