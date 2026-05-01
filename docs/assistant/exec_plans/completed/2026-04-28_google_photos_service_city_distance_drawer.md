# Google Photos Service City, Distance, and Review Details Follow-up

## Goal and non-goals
- Goal: keep Google Photos/photo Interpretation imports from silently treating an unproven service city as the case city.
- Goal: recover explicit service-city evidence from OCR text, keep Google Photos Picker place/location unavailable, and make Review Details city/email/distance editing usable.
- Goal: support city-aware court email options, controlled service-entity selection, editable photo-date fallback, and profile-backed service-city distance refresh.
- Non-goal: change Translation, Gmail finalization, route IDs, final honorários generation, or claim Google Photos place/location support.

## Scope
- In scope:
  - Google Photos/photo seed handling for Interpretation only
  - OCR service-location extraction and ranking
  - Review Details city, email, service entity, date, distance, and Add city/email behavior
  - profile distance defaults and destination deletion UI
  - focused regression coverage and shadow-mode live validation
- Out of scope:
  - live Gmail
  - Translation
  - final DOCX/PDF generation
  - OAuth/Picker/media/private data in artifacts

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_worktrees\google-photos-service-city-distance-drawer`
- Branch name: `feat/google-photos-service-city-distance-drawer`
- Base branch: `origin/main`
- Base SHA: `24c30fe63d2237657e941d0cfb792e7836c62d03`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree used only for shadow-mode validation

## Interfaces/types/contracts affected
- Added safe Google Photos disconnect/reconnect support and stale Picker UI cleanup.
- Added city-aware `court_emails_by_city` settings support while preserving the flat `vocab_court_emails` list.
- Added Interpretation reference data for city-aware court email options and service entity options.
- Preserved existing route paths and form field names; added only Interpretation-scoped recovery routes/fields.
- Google Photos diagnostics remain sanitized and do not expose raw OAuth URLs, Picker URLs, query strings, media IDs, media base URLs, account identifiers, private text, or credentials.

## Implementation summary
- Google Photos/photo imports no longer default blank `service_city` or KM to the case city.
- OCR extraction rejects placeholders and address/title fragments such as generic venue text, then ranks official case evidence and service-turn/address evidence field by field.
- The accepted live image shape now resolves to case city `Beja`, case entity `Ministério Público de Beja`, court email from Beja options, service entity `Serviço de Turno`, service city `Moura`, service date `2026-04-25`, KM `26`, and `service_same=false`.
- Google Photos `createTime` and downloaded EXIF date are safe photo-date provenance only; OCR/legal text wins, and photo date may prefill service date only as an editable fallback.
- Google Photos place/location remains unavailable from the Picker API and is not used for service city.
- Review Details now uses city-aware court email dropdowns, top-level Add city/Add email dialogs, a service-entity dropdown, fixed service-same layout, and service-city distance refresh.
- Profile defaults include the accepted city distances, including `Moura=26` and `Brinches=23`, and remove the `Mora` typo from defaults/workspace data.

## Validation results
- Google Photos/photo OCR tests: passed.
- Review state and shadow web API tests: passed.
- Honorários and Qt app state regressions: passed.
- Shadow runtime service regressions: passed.
- `scripts/validate_dev.ps1`: passed; when the local Dart wrapper reported `Unable to find AOT snapshot for dartdev`, the direct Dart fallback passed.
- Live shadow validation on `127.0.0.1:8890` imported the selected Google Photos image into Review Details and the user accepted the final Beja/Moura behavior.
- No Gmail, Translation, or final DOCX/PDF generation was run.

## Acceptance criteria
- Google Photos selected-image import reaches Review Details.
- Case and service city remain distinct when OCR proves distinct locations.
- Blank or unknown service city stays blank/provisional and prompts instead of inheriting case city.
- KM uses the selected service city profile distance, refreshes when service city changes, and blocks save/export when transport is enabled without a distance.
- Court email options are keyed to case city, not service city.
- Add city and Add email work above the Review Details drawer without closing it.
- Google Photos place/location remains unavailable and unclaimed.

## Rollout and fallback
- Merge through PR after GitHub Actions pass.
- If live Google Photos Picker fails in a future environment, use the reconnect path and sanitized method/path-only route diagnostics.
- If OCR cannot recover service city, leave service fields blank/provisional and require user selection; never silently default to case city.

## Risks and mitigations
- Risk: Google Photos UI shows a place label that Picker does not expose.
  - Mitigation: docs and diagnostics explicitly distinguish UI place labels from Picker payload fields.
- Risk: OCR variability misses service-turn evidence.
  - Mitigation: multi-pass/header recovery, field ranking, known-city filtering, and blank/provisional fallback.
- Risk: distance refresh overwrites user edits.
  - Mitigation: auto-refresh replaces only auto-filled values and preserves manual KM.

## Assumptions/defaults
- Service city source is OCR/document text or explicit user selection only.
- Photo date fallback is allowed for editable service date when OCR/legal date is missing.
- Google Photos place/location remains unavailable from the Picker API.
- User-accepted shadow validation is the release acceptance signal for this feature branch.
