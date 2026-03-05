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
