# Validation Guide

## Default Rules
- Use the repo Python executable: `.\.venv311\Scripts\python.exe`.
- Do not run pytest through bare or global `python`.
- Run targeted tests first, then broader validation when the touched scope warrants it.
- Stop before merge if local validation, GitHub checks, branch identity, or worktree cleanliness is not clean.

## Approved formatting integration

Validate compact writer, structure/regions, source-spacing and section-furniture suites, including different/headerless/footerless sections, source/target hash binding, ambiguous evidence, all source-map aliases, readable Arabic/Latin runs, PAGE continuity, tables, legacy TXT and explicit page matching. Run local rebuild integration and production-policy isolation regressions: saved translation bytes, prior usage/costs and existing review findings must remain intact, and no new API/OCR client may be constructed by rebuilding. Keep prompt/effort/image/source-extraction regressions in the compatibility set.

Rich source-aware formatting requires complete matching structured pairs. Current production TXT output cannot be made source-associated merely by matching paragraph counts or numeric anchors. Tests must exercise this fallback rather than use the experimental translation workflow to manufacture a passing release.

Rebuild private accepted examples into new outputs; compare every DOCX package entry against the accepted Word-rendered version. Exact package equality permits reuse of its bound render evidence. Any layout/content difference requires fresh rendering and every-page inspection. Keep private PDFs/DOCXs/PNGs outside Git; use synthetic accented names in published fixtures. Translation deliverables remain DOCX.

The existing native Windows `0x8001010d` diagnostic can occur at the honorarios small-screen dialog's `app.processEvents()` even when assertions pass. Record native and isolated rerun outcomes; do not suppress the diagnostic. This layout-only test does not invoke Word export, and offscreen success is not native export acceptance. The honorarios export repair below does not claim to fix this separate Qt event-processing diagnostic.

Qt render-review subprocess tests must read the renderer's JSON artifact rather than assume stdout contains only JSON: dependency diagnostics can also appear there. Keep strict artifact parsing, successful process exit and geometry assertions; exercise noisy stdout without suppressing warnings or weakening layout checks.

## Honorarios Word-to-PDF export

Translation deliverables remain editable DOCX. Validate PDF generation only for the separate honorarios document; retain its DOCX and do not change legal wording, fees or layout to obtain a passing export.

Focused offline regressions:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_word_automation.py tests/test_word_pdf_control.py tests/test_word_pdf_artifacts.py tests/test_word_pdf_runtime.py tests/test_word_pdf_script.py tests/test_honorarios_docx.py
```

These tests must not launch Word implicitly. Keep the native-launch guards in `tests/conftest.py`; parser, compiler and fake-COM checks do not establish native export readiness. Cover process identity and reuse, existing documents, content-free durable phases, early setup/pipe failures, bounded helper cleanup, cross-process exclusion, uncertain-cleanup quarantine, stale output, atomic publication, origin/security rejection, original-file hashes and accurate cleanup metadata. Browser/Qt callers perform one export with a 45-second allowance and bounded cleanup, not an automatic timeout re-probe/re-export.

Run opt-in native acceptance on the same Windows host/interpreter as the app, only after the ownership and journal safeguards are active. Keep one original state directory across failure/recovery; changing APPDATA or deleting the journal must not bypass quarantine. Use synthetic data, an isolated shadow workspace and ignored/private artifacts. Never terminate unknown Word sessions or change Office security settings to make a test pass.

Require a real expected-text canary, translation-kind and interpretation-kind honorarios through shared caller paths, the browser export route and asynchronous Qt worker, coexistence with an unsaved synthetic Word document, and an already-open source DOCX. Check unchanged source hashes and pre-existing window/content state, fresh readable PDF pages, confirmed owned-process exit and a healthy export after a bounded startup timeout. A startup-only probe, a PDF header, or an older PDF is insufficient. Render and inspect every page of retained Word-produced PDFs; neither XML checks nor another renderer substitute for Word-native acceptance. Observe cold conditions only when safely available, without closing unknown user work.

Accepted 2026-09-07 evidence: eight successful native exports, including the two canaries, shared/browser/Qt paths and both coexistence cases; all six retained honorarios PDFs were one page and passed complete-page Poppler PNG inspection. Full pytest passed **2,176 tests** and `validate_dev.ps1 -Full` passed with the documented Dart fallback. The separate native small-screen Qt test passed its assertions but repeated `0x8001010d` on serial rerun; preserve that limitation. Browser acceptance exercised the real route with isolated data, not a claimed browser-button click. No live Gmail operation, Office repair or host-security change was part of this acceptance. See the [completed repair ExecPlan](exec_plans/completed/2026-09-07_honorarios_pdf_export_reliability.md) for exact evidence and scope.

## Common Targeted Browser And Gmail Tests
```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py
```

Add the Qt Delete-key regression when the task touches Qt Job Log behavior or merge readiness:

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py::test_joblog_window_delete_key_removes_selected_rows_when_table_has_focus
```

## Full Local Regression
```powershell
.\.venv311\Scripts\python.exe -m pytest -q
```

Use full pytest before merge, after test/code/workflow changes, or when a focused failure might be suite-order dependent.

## Validation Wrapper
```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
```

`validate_dev.ps1` runs focused browser tests, compileall, docs validation when docs changed, and workspace hygiene. `-Full` adds focused Gmail review/intake coverage.

## Dart AOT Fallback
On this machine, `dart run ...` can fail with:

```text
Unable to find AOT snapshot for dartdev
```

That is a known launcher issue, not automatically a product failure. The validation wrapper should fall back to:

```powershell
C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling\validate_agent_docs.dart
C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling\validate_workspace_hygiene.dart
```

Record both the wrapper failure and direct-Dart fallback success in validation summaries.

## Google Photos Interpretation Validation
Use this section for the Interpretation-only Google Photos Picker import feature.

Focused commands:
```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_google_photos_picker.py tests/test_interpretation_google_photos.py tests/test_metadata_autofill_photo.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_honorarios_docx.py tests/test_qt_app_state.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_runtime_service.py
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
```

Run the safe config gate before live OAuth/Picker work:
- `configured=true`
- `client_id_source=process_env` or `windows_user_env`
- `client_secret_source=process_env` or `windows_user_env`
- scope exactly `https://www.googleapis.com/auth/photospicker.mediaitems.readonly`
- shadow redirect exactly `http://127.0.0.1:8890/api/interpretation/google-photos/oauth/callback`
- live redirect exactly `http://127.0.0.1:8877/api/interpretation/google-photos/oauth/callback`

Live validation acceptance checklist:
- OAuth reaches `connected=true`.
- Token store is present.
- `Choose from Google Photos` is enabled.
- Picker session is created and polled.
- User selects exactly one non-private test photo.
- Google Photos completion screen or auto-close indicates selection finished.
- `mediaItemsSet=true` is observed.
- selected media items are listed.
- import route is called.
- selected image imports into the existing Interpretation photo/OCR autofill flow.
- `Review Case Details` opens.
- Translation controls are avoided.
- `createTime` and downloaded EXIF date are photo-date provenance only; OCR/legal dates win, and photo date may prefill service date only as an editable fallback.
- `service_city` and `case_city` remain OCR/document- or user-confirmed; Google Photos place/location is not available from the Picker API.
- Review Details does not silently default blank service city or KM to the case city.
- Recovered distinct case/service evidence stays distinct, for example case city `Beja` and service location `Serviço de Turno | Moura`.
- KM is keyed to the effective service city and refreshes from profile distances when the service city changes.
- City-aware court email options use the case city, not the service city.
- Picker session cleanup succeeds.
- No final honorários DOCX/PDF is generated unless explicitly approved and then manually reviewed.

Sanitized route logs for this flow may contain method/path only. Drop query strings immediately and normalize Picker session IDs.

## CI Expectations
GitHub CI currently runs on Windows Python 3.11 and includes:
- agent docs validation,
- localization contracts,
- workspace hygiene,
- compileall,
- targeted core regressions,
- full pytest.

Do not merge if required checks such as `test (3.11)` or `docs_tooling_contracts` are failing, pending unexpectedly, blocked, or attached to an unexpected head SHA.

## Coverage Map For PR #46 Risks
- Numeric mismatch and decimal-comma preservation: `tests/test_translation_diagnostics.py`, `tests/test_translation_report.py`, `tests/test_quality_risk_scoring.py`, and PR #46 browser state tests.
- Safe rendering: `tests/test_browser_safe_rendering.py`.
- Shadow/test-mode banner and friendly live copy: `tests/test_shadow_web_api.py`.
- Gmail prepared state: `tests/test_translation_browser_state.py` and Gmail review/intake tests.
- Profile summary/list distinction: `tests/test_profile_browser_state.py` and `tests/test_shadow_web_api.py`.
- Recent Work empty-state copy: `tests/test_translation_browser_state.py` and `tests/test_shadow_web_api.py`.
- Qt Job Log Delete-key multi-select: `tests/test_qt_app_state.py::test_joblog_window_delete_key_removes_selected_rows_when_table_has_focus`.
- Windows browser ESM UTF-8 probe behavior: `tests/browser_esm_probe.py` with Gmail/interpretation browser ESM tests.
- Validation wrapper fallback: `scripts/validate_dev.ps1` and completed validation artifacts.
