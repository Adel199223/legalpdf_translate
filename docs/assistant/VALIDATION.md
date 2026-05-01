# Validation Guide

## Default Rules
- Use the repo Python executable: `.\.venv311\Scripts\python.exe`.
- Do not run pytest through bare or global `python`.
- Run targeted tests first, then broader validation when the touched scope warrants it.
- Stop before merge if local validation, GitHub checks, branch identity, or worktree cleanliness is not clean.

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
