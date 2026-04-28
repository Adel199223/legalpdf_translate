# Google Photos Interpretation Import

## 1. Title
Google Photos Picker import for Interpretation honorarios.

## 2. Goal and non-goals
Goal: add an Interpretation-only Google Photos Picker import path that lets a user select one photo, recover safe metadata through the existing photo autofill pipeline, review the imported fields, and then use the existing honorarios export flow after normal manual confirmation.

Non-goals:
- No Translation routing or translation document generation.
- No Gmail OAuth reuse or Gmail draft sending.
- No broad Google Photos Library API integration.
- No service-account access to Google Photos user libraries.
- No assumption that Google Photos UI place labels or downloaded EXIF GPS are available.
- No final honorarios DOCX/PDF generation during Google Photos live validation.

## 3. Scope
In:
- Google Photos Picker OAuth/token helpers with separate storage from Gmail.
- Process-env and Windows User-env credential lookup with safe source labels.
- Strict client-secret validation for empty, placeholder, too-short, or client-ID-shaped values.
- Safe OAuth callback diagnostics with whitelisted failure categories and no secrets.
- Picker session create/get/list/delete client.
- Browser-side visible fallbacks for Google sign-in and Google Photos Picker launch.
- Interpretation-specific import service that downloads selected bytes and feeds existing photo autofill.
- Browser API routes under `/api/interpretation/google-photos/...`.
- Browser UI affordance near Photo / Screenshot and metadata provenance display.
- Targeted tests for mocked OAuth, Picker, import, UI, and route behavior.

Out:
- Creating or storing production Google OAuth credentials.
- Live Picker probing with private legal/case photos.
- Claiming Google Photos place/location support.
- Claiming downloaded EXIF GPS support.
- Final document generation beyond the existing deterministic honorarios path after user review.

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/google-photos-interpretation`
- Base branch: `main`
- Base SHA: `8a4cd7f38085ea60a7b79c2104346d284b4de401`
- Target integration branch: `main`
- Status at docs sync: feature branch dirty/uncommitted; no commit, push, PR, merge, rebase, or force-push was performed.

## 5. Interfaces/types/contracts affected
- Adds new browser routes under `/api/interpretation/google-photos/...`.
- Keeps existing `/api/interpretation/autofill-photo` and `/api/interpretation/export-honorarios` contracts unchanged.
- Adds provenance-only seed/diagnostic fields for Google Photos selection; final honorarios payload remains the existing reviewed Interpretation form contract.
- Adds settings keys for Google Photos OAuth connection state/token storage path/client configuration, separate from Gmail/gog.
- Adds safe status fields such as `client_id_source`, `client_secret_source`, and `last_callback_diagnostic`; no credential values are returned.

## 6. File-by-file implementation summary
- `src/legalpdf_translate/google_photos_oauth.py`: OAuth configuration, source-aware env resolution, token storage, safe callback diagnostics, and redaction-safe connection helpers.
- `src/legalpdf_translate/google_photos_picker.py`: Picker REST client and metadata normalization.
- `src/legalpdf_translate/interpretation_google_photos.py`: import orchestration into existing photo autofill.
- `src/legalpdf_translate/shadow_web/app.py`: Interpretation Google Photos routes.
- `src/legalpdf_translate/shadow_web/templates/index.html`: Google Photos controls, sign-in fallback, Picker fallback, and provenance area near Photo / Screenshot.
- `src/legalpdf_translate/shadow_web/static/app.js`: connect/session/poll/import UI behavior, busy guard fix, fallback behavior, and `/autoclose` navigation handling.
- `src/legalpdf_translate/user_settings.py`: non-secret Google Photos settings defaults/allowed keys.
- `src/legalpdf_translate/gmail_focus_host.py`: Edge unpacked-extension discovery suffix-based guard retained so bootstrap does not hang on arbitrary browser profile paths.
- Tests: focused route/service/UI tests and shadow web assertions.

## 7. Live validation evidence
Final manual Picker completion validation passed on `2026-04-28`:
- config gate passed
- OAuth `connected=true`
- token store present
- `Choose from Google Photos` enabled
- Picker session created
- user reached Google Photos `Done! Continue in the other app or device` completion screen
- `mediaItemsSet=true` observed through media-items route transition
- media-items listing called
- import route called
- selected photo imported
- existing `Review Case Details` drawer opened
- Translation controls avoided
- Google Photos `createTime` present and kept as provenance only
- Google Photos place/location absent or unproven
- downloaded EXIF date absent
- downloaded EXIF GPS absent or unproven
- OCR recovered fields present
- user confirmation still required
- no final DOCX/PDF generated during Google Photos validation
- Picker cleanup succeeded
- sanitized artifact scan passed

Manual validation artifact:
- `C:\Users\FA507\Downloads\legalpdf_translate_google_photos_picker_manual_completion_report_20260428_155740.md`

## 8. Tests and acceptance criteria
Focused validation from the final manual completion report:
- Google Photos / interpretation / photo metadata tests: `22 passed`
- Shadow API tests: `66 passed`
- Interpretation review and honorarios tests: `60 passed`
- `scripts/validate_dev.ps1`: passed; Dart wrapper AOT issue appeared and direct Dart fallback passed

Docs-sync validation reruns the current requested commands:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_google_photos_picker.py tests/test_interpretation_google_photos.py tests/test_metadata_autofill_photo.py`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_honorarios_docx.py`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`

## 9. Rollout and fallback
- Roll out behind connection/config checks: disconnected UI remains safe and local upload keeps working.
- If Picker credentials are absent or invalid, show a clear disconnected/unconfigured state.
- If OAuth tab does not open, show `Open Google sign-in` without printing or persisting the raw URL.
- If Picker tab does not open, show `Open Google Photos Picker` without printing or persisting the raw Picker URL.
- If Picker place/location or EXIF GPS remains unavailable, continue requiring OCR/user confirmation for city/date fields.
- Fallback: manual local photo/screenshot upload remains unchanged.

## 10. Risks and mitigations
- Temporary OAuth credential exposure: delete or rotate the OAuth client before production-like use and rerun the config gate.
- Token/baseUrl leakage: token storage is separate; diagnostics and artifacts must not include tokens, raw OAuth URLs, Picker URLs, media IDs, or media base URLs.
- Process environment inheritance: app supports process env first and Windows User env fallback.
- Client secret mistakes: strict reset/checklist rejects placeholders, too-short values, and client-ID-shaped secrets.
- Popup/noopener behavior: visible browser-only fallbacks prevent OAuth/Picker launch from stranding the user.
- Picker session cleanup can fail: attempt deletion after import and report sanitized cleanup failure only.

## 11. Metadata invariants
- Google Photos `createTime` is `photo_taken_at` provenance only.
- Downloaded EXIF date is provenance only when present.
- `service_date`, `service_city`, and `case_city` remain OCR- or user-confirmed.
- Do not claim Google Photos place/location support from the current validation.
- Do not claim downloaded EXIF GPS support from the current validation.
