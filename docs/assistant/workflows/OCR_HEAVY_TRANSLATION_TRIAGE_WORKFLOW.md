# OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW

## What This Workflow Is For
Troubleshooting OCR-heavy translation failures, stalls, or partial runs on real PDFs before widening the investigation.

## Expected Outputs
- A clear preflight packet showing local OCR availability and API dependency.
- A small-slice acceptance result before any full-document rerun.
- Failure classification that distinguishes OCR/runtime transport problems from rate limiting and UI-close behavior.

## When To Use
- A document depends on OCR and fails, stalls, or reports partial completion.
- Local OCR is unavailable or unreliable and the workflow may need API-only OCR.
- The user needs a production-safe runbook for an urgent document before a deeper code change.

## What Not To Do
- Don't use this workflow when the task is primarily screenshot-driven Qt UI replication.
- Instead use `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`.

## Primary Files
- `docs/assistant/workflows/OCR_HEAVY_TRANSLATION_TRIAGE_WORKFLOW.md`
- `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- `tooling/ocr_preflight.py`
- `tooling/ocr_translation_probe.py`
- `src/legalpdf_translate/workflow.py`

## Minimal Commands
PowerShell:
```powershell
python .\tooling\ocr_preflight.py --compact
python .\tooling\ocr_translation_probe.py --pdf "<path-to-pdf>" --lang AR --pages 1-2
```
POSIX:
```bash
python ./tooling/ocr_preflight.py --compact
python ./tooling/ocr_translation_probe.py --pdf "<path-to-pdf>" --lang AR --pages 1-2
```

## Targeted Tests
- `tests/test_ocr_translation_probe.py`
- `tests/test_workflow_ocr_availability.py`
- `tests/test_workflow_ocr_routing.py`

## Failure Modes and Fallback Steps
- Local OCR unavailable: switch the triage runbook to `ocr_mode=always`, `ocr_engine=api`, `image_mode=off`, `workers=1`, `keep_intermediates=on`.
- Full-document OCR run stalls: prove page `1-2` first, then continue in small page slices instead of repeating the same 7-page failure.
- OCR succeeds but translation still stalls: verify that the effective OCR text path is being used without redundant image attachment.
- Partial failure leaves the user thinking the app froze: surface report/run-summary paths and treat cancel/close behavior as a separate UI/runtime symptom.

## Handoff Checklist
1. Run OCR preflight before diagnosing the document.
2. Record whether local OCR is available and whether the document is effectively API-only.
3. Start with a one-page or `1-2` page probe before any full rerun.
4. Keep OCR-success pages text-first unless there is a concrete reason to retain image attachment.
5. Distinguish transport instability from true rate limiting and capture summary/report artifacts when available.
