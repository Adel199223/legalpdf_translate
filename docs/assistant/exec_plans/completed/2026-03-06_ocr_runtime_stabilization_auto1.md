# OCR Timeout and Cancellation Stabilization for `auto (1).pdf`

## Summary
Stabilize OCR-heavy translation for `auto (1).pdf` by making request deadlines real, bounding cancel-wait behavior, and improving OCR-heavy operator safety guidance.

Acceptance fixture:
- `C:\Users\FA507\Downloads\auto (1).pdf`

Locked urgent operator runbook until all stages are complete:
- OCR mode `always`
- OCR engine `api`
- Image mode `off`
- Workers `1`
- Effort policy `fixed_high`
- Resume `off`
- Keep intermediates `on`
- Run slices `1-2`, then `3-4`, then `5-7`

## Scope
In scope:
- authoritative request deadlines for translation/OCR/metadata AI
- bounded SDK retry behavior
- bounded cancel-wait UX
- OCR-heavy warnings and clearer failure reporting

Out of scope:
- prompt rewrites
- model/default migration work
- installing local OCR runtimes
- broad OCR quality retuning

## Stages
### Stage 0: Reproduction Lock
Status: completed

Confirmed facts:
- OCR succeeded on the failing document.
- The page image was already correctly suppressed on OCR-success text routes.
- The remaining defect is runtime control: a translation request ran for ~45 minutes before surfacing `APITimeoutError`.
- `Cancel and wait` could only wait for the in-flight request to return.

### Stage 1: Real Request Deadlines
Status: completed
Gate token: `NEXT_STAGE_2`

Implemented:
- SDK implicit retries disabled with `max_retries=0` for translation, OCR API, and metadata AI clients.
- Added authoritative timeout constants:
  - text-only translation `480s`
  - image-backed translation `720s`
  - OCR API `240s`
  - metadata/header AI `120s`
- Translation workflow now chooses request budgets from the effective request type and consumes that budget across retries.
- GUI settings timeout fields now migrate legacy defaults `90/120` to `480/720` only when those values still match untouched legacy defaults.
- Settings dialog now displays the new timeout defaults instead of stale `90/120` placeholders.
- Page metadata and diagnostics now capture:
  - `request_type`
  - `request_timeout_budget_seconds`
  - `request_elapsed_before_failure_seconds`
  - `cancel_requested_before_failure`

Files touched in Stage 1:
- `src/legalpdf_translate/config.py`
- `src/legalpdf_translate/user_settings.py`
- `src/legalpdf_translate/openai_client.py`
- `src/legalpdf_translate/ocr_engine.py`
- `src/legalpdf_translate/metadata_autofill.py`
- `src/legalpdf_translate/workflow.py`
- `src/legalpdf_translate/qt_gui/dialogs.py`
- `tests/test_openai_transport_retries.py`
- `tests/test_user_settings_schema.py`
- `tests/test_workflow_ocr_routing.py`
- `tests/test_ocr_policy_routing.py`
- `tests/test_metadata_autofill_header.py`

Validation:
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_openai_transport_retries.py tests/test_user_settings_schema.py tests/test_workflow_ocr_routing.py tests/test_ocr_policy_routing.py tests/test_metadata_autofill_header.py` -> `43 passed`
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py tests/test_workflow_ocr_availability.py` -> `25 passed`
- `./.venv311/Scripts/python.exe -m compileall src tests` -> pass
- docs/workspace validators -> pass

Residual risks after Stage 1:
- `Cancel and wait` is still cooperative until Stage 2 lands; it is now bounded by the request deadline plumbing but the dedicated wait-state UX and halt reasons are not finished yet.
- Failure classification/report refinement is deferred to Stage 3.

### Stage 2: Cancellation and Close Semantics
Status: completed
Gate token: `NEXT_STAGE_3`

Implemented:
- `Cancel and wait` now shows bounded wait state using the active page request budget.
- The cancel-wait UI now surfaces:
  - current page
  - elapsed wait
  - maximum remaining wait before timeout handling
- Close/cancel status is refreshed on a timer instead of remaining static.
- Active request tracking is cleared when runs stop or reset.
- Cancelled runs now persist clearer halt reasons:
  - `cancelled_after_request_timeout`
  - `cancelled_during_transport_retry`
  - fallback `cancelled_by_user`
- `run_cancelled` events now record the resolved halt reason.
- Existing abandoned-run detection on relaunch was preserved.

Files touched in Stage 2:
- `src/legalpdf_translate/workflow.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- `tests/test_qt_app_state.py`
- `tests/test_workflow_ocr_routing.py`

Validation:
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py tests/test_workflow_ocr_routing.py tests/test_workflow_ocr_availability.py tests/test_summary_signal_classification.py` -> `41 passed`
- `./.venv311/Scripts/python.exe -m compileall src tests` -> pass

Residual risks after Stage 2:
- The cancel wait is now bounded and visible, but risky OCR-heavy settings are still only partially warned about until Stage 3 lands.
- Failure report wording in the final dialog still needs refinement in Stage 3.

### Stage 3: OCR-Heavy Warnings and Failure Reporting
Status: completed
Gate token: `NEXT_STAGE_4`

Implemented:
- OCR-heavy runs with no local OCR now use a stronger warn-only dialog instead of silently auto-switching settings.
- The warning now lists the risky settings that increase stall risk:
  - non-`api` OCR engine
  - `image_mode != off`
  - `fixed_xhigh`
  - `workers > 1`
  - `resume = on`
  - `keep_intermediates = off`
- The dialog now shows the exact safer profile for OCR-heavy triage and offers:
  - `Review settings`
  - `Continue anyway`
  - `Cancel`
- Failed runs now persist top-level `failure_context` in `run_summary.json` with:
  - `request_type`
  - `request_timeout_budget_seconds`
  - `request_elapsed_before_failure_seconds`
  - `cancel_requested_before_failure`
  - `exception_class`
- Workflow logs now emit explicit failure-context lines for request type, deadline, elapsed time, and cancel timing.
- The GUI stop dialog now surfaces richer failure details from `run_summary.json`:
  - suspected cause
  - halt reason
  - request type
  - request deadline
  - elapsed time before failure
  - whether cancel had already been requested
  - failure class
- Later UI follow-up on the same branch changed the warning actions to the final stable form:
  - `Apply safe OCR profile`
  - `Continue anyway`
  - `Cancel`
  The safe profile is applied to the current run only and does not overwrite saved defaults.

Files touched in Stage 3:
- `src/legalpdf_translate/workflow.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- `tests/test_qt_app_state.py`
- `tests/test_workflow_ocr_routing.py`

Validation:
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py tests/test_workflow_ocr_routing.py tests/test_workflow_ocr_availability.py tests/test_summary_signal_classification.py` -> `44 passed`
- `./.venv311/Scripts/python.exe -m compileall src tests` -> pass
- docs/workspace validators -> pass

Residual risks after Stage 3:
- Stage 4 still needs live acceptance on `auto (1).pdf` slices before treating the runtime fix as operationally proven.
- The branch still contains uncommitted OCR stabilization WIP and helper probe artifacts outside this ExecPlan.

### Stage 4: Final Validation and Live Acceptance
Status: completed

Validation bundle:
- `./.venv311/Scripts/python.exe -m compileall src tests` -> pass
- `./.venv311/Scripts/python.exe -m pytest -q` -> `541 passed`
- docs/workspace validators -> pass

Live acceptance on `C:\Users\FA507\Downloads\auto (1).pdf`:
- Locked safe profile used:
  - OCR mode `always`
  - OCR engine `api`
  - Image mode `off`
  - Workers `1`
  - Effort policy `fixed_high`
  - Resume `off`
  - Keep intermediates `on`
- Slice acceptance `1-2` succeeded:
  - output docx `C:\Users\FA507\Downloads\ocr_timeout_stage4_probe\auto (1)_AR_20260306_150526.docx`
  - run summary `C:\Users\FA507\Downloads\ocr_timeout_stage4_probe\auto (1)_AR_run\run_summary.json`
- Full acceptance `1-7` succeeded:
  - output docx `C:\Users\FA507\Downloads\ocr_timeout_stage4_full\auto (1)_AR_20260306_150828.docx`
  - run summary `C:\Users\FA507\Downloads\ocr_timeout_stage4_full\auto (1)_AR_run\run_summary.json`
  - total wall time `477.328s`
  - total input tokens `22540`
  - total output tokens `21207`
  - total reasoning tokens `16543`
  - estimated cost `0.34708 USD`

Acceptance evidence:
- OCR succeeded on every page through the API path.
- Translation stayed text-only on OCR-success pages (`image_used=false`).
- No transport retries were recorded on the accepted full run.
- The earlier multi-page stall pattern did not reproduce under the locked safe profile.

Operational result:
- The runtime is now operationally stable for this document class when run with the locked safe OCR-heavy profile.
- Remaining caution: this branch still contains broader OCR stabilization WIP and is not committed yet.

User-verified outcome after live app testing:
- The same 7-page OCR-heavy document completed cleanly in the GUI under the safe profile.
- The accepted run stayed text-only after OCR success, advanced page-by-page, and no longer reproduced the earlier long cancel-wait stall.

## Notes
- `python -m legalpdf_translate.qt_app` is the canonical launch command for docs.
- `python -m legalpdf_translate.qt_gui` remains a valid GUI entrypoint and was not the cause of the runtime defect.
