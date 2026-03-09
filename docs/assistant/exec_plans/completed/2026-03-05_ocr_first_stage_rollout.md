# OCR-First Stage Rollout (From NEXT_STAGE_4)

## Scope
- Stage 4: OCR foundation + preflight + observability.
- Stage 5: OCR engine hardening.
- Stage 6: OCR advisor backend.
- Stage 7: OCR advisor GUI.
- Stage 8: queue runner.
- Stage 9: final hardening/signoff.

## Locked Defaults
- Branch: `chore/import-optmax-2026-03-05`
- One commit per stage.
- Full local validation each stage.
- Strict stage gates using `NEXT_STAGE_X` tokens.

## Stage Packet — Stage 4
- Status: completed.
- Commit: `ae98ef2` (`feat(ocr): add preflight and OCR observability foundation`)
- Work items:
  - Add `tooling/ocr_preflight.py` + tests.
  - Add OCR observability fields/events in workflow payloads.
  - Surface OCR observability in run report output.
  - Register OCR fallback reference in external-source registry.
- Validation:
  - `dart run tooling/validate_agent_docs.dart` -> pass.
  - `dart run tooling/validate_workspace_hygiene.dart` -> pass.
  - `./.venv311/Scripts/python.exe -m compileall src tests tooling/ocr_preflight.py` -> pass.
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `472 passed`.
- Continuation token after completion: `NEXT_STAGE_5`.

## Stage Packet — Stage 5
- Status: completed.
- Commit: `24a9514` (`feat(ocr): harden local pass strategy and required-only fallback policy`)
- Work items:
  - Decouple OCR hinting from target language.
  - Add deterministic local OCR pass selection and acceptance scoring.
  - Keep API fallback restricted to required OCR paths.
- Validation:
  - Full local bundle and targeted OCR suites passed during stage execution.
  - Stage-specific CI evidence was not preserved in this file.
  - Final authoritative validation later completed on `d29c163`.
- Continuation token after completion: `NEXT_STAGE_6`.

## Stage Packet — Stage 6
- Status: completed.
- Commit: `aed4bd2` (`feat(ocr): add deterministic OCR/image advisor backend`)
- Work items:
  - Add advisor engine for analyze/report output.
  - Persist recommendation metadata into run artifacts.
  - Extend run-report rendering for advisor details.
- Validation:
  - Full local bundle and targeted advisor/report suites passed during stage execution.
  - Stage-specific CI evidence was not preserved in this file.
  - Final authoritative validation later completed on `d29c163`.
- Continuation token after completion: `NEXT_STAGE_7`.

## Stage Packet — Stage 7
- Status: completed.
- Commit: `0e7afe9` (`feat(gui): add OCR advisor apply-ignore workflow`)
- Work items:
  - Add advisor banner to the Qt main window.
  - Add Apply and Ignore actions for the next run only.
  - Persist applied vs ignored choice into run metadata.
- Validation:
  - Full local bundle and targeted Qt/advisor/report suites passed during stage execution.
  - Stage-specific CI evidence was not preserved in this file.
  - Final authoritative validation later completed on `d29c163`.
- Continuation token after completion: `NEXT_STAGE_8`.

## Stage Packet — Stage 8
- Status: completed.
- Commit: `28d1b59` (`feat(queue): add local queue runner with checkpoint and failed-only rerun`)
- Work items:
  - Add queue manifest parsing and queue checkpoint/summary artifacts.
  - Add CLI queue execution and failed-only rerun support.
  - Add Qt queue controls and queue-status reporting.
- Validation:
  - `dart run tooling/validate_agent_docs.dart` -> pass.
  - `dart run tooling/validate_workspace_hygiene.dart` -> pass.
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> pass.
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_queue_runner.py tests/test_queue_failed_only_rerun.py tests/test_cli_flags.py tests/test_qt_app_state.py tests/test_checkpoint_resume.py` -> `35 passed`
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `495 passed`
- Cloud evidence:
  - CI URL: https://github.com/Adel199223/legalpdf_translate/actions/runs/22733929659
  - Status: `completed`
  - Conclusion: `success`
- Continuation token after completion: `NEXT_STAGE_9`.

## Stage Packet — Stage 9
- Status: completed.
- Commit: `d29c163` (`chore(reliability): finalize OCR-first staged rollout and signoff`)
- Work items:
  - Run final local and cloud validation on the latest SHA.
  - Perform final OCR/queue/workflow reliability sweep.
  - Close remaining queue reliability issues before signoff.
- Queue hardening notes:
  1. GUI queue runs no longer require the main PDF/output fields when the manifest already provides them.
  2. Queue cancellation now leaves untouched jobs resumable instead of marking them failed.
- Validation:
  - `dart run tooling/validate_agent_docs.dart` -> pass.
  - `dart run tooling/validate_workspace_hygiene.dart` -> pass.
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> pass.
  - `./.venv311/Scripts/python.exe -m pytest -q` -> `497 passed`
- Cloud evidence:
  - CI URL: https://github.com/Adel199223/legalpdf_translate/actions/runs/22734369973
  - Status: `completed`
  - Conclusion: `success`
- Final status: `GO`
