# Interpretation Honorarios Wave 3

## 1. Title
Photo/screenshot fallback and saved-distance prompting for interpretation intake.

## 2. Goal and non-goals
- Goal:
  - add a local photo/screenshot import path for interpretation cases
  - use interpretation-specific photo metadata extraction when importing screenshot-like evidence
  - prompt once for a missing saved one-way distance and persist it to the primary profile during interpretation photo import
- Non-goals:
  - no Google Photos or Samsung Gallery integration
  - no EXIF GPS or geocoding
  - no changes to the locked Wave 2 notification-PDF import contract
  - no remote/WebEx branch

## 3. Scope (in/out)
- In:
  - `Job Log -> Add... -> From photo/screenshot...`
  - interpretation-specific image metadata extraction path
  - profile-backed saved-distance prompt during interpretation photo import when no city distance exists yet
  - focused photo parser and Qt flow tests
- Out:
  - cloud photo providers
  - background OCR redesign
  - any Gmail draft flow for interpretation

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/interpretation-honorarios`
- Base branch: `main`
- Base SHA: `abf608f16fac69e477849b9e8b3e040502856999`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- Metadata extraction:
  - activate interpretation-specific photo metadata extraction helpers for screenshot-like imports
- Qt:
  - Job Log photo/screenshot import entrypoint becomes live
  - interpretation photo autofill uses interpretation defaults instead of the generic photo extractor
- Profile settings:
  - missing one-way city distance can be prompted once and persisted during interpretation photo import

## 6. File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - add an interpretation seed builder for photo/screenshot imports
  - enable `Job Log -> Add... -> From photo/screenshot...`
  - route interpretation photo autofill through the interpretation-specific extractor
  - prompt for a missing saved one-way distance and persist it during interpretation photo import
- `tests/test_metadata_autofill_photo.py`
  - add interpretation-photo metadata regression coverage
- `tests/test_qt_app_state.py`
  - add Job Log photo import flow coverage
  - add interpretation photo autofill distance-persistence coverage

## 7. Tests and acceptance criteria
- `tests/test_metadata_autofill_photo.py`
- `tests/test_qt_app_state.py`
- Acceptance:
  - `Job Log -> Add... -> From photo/screenshot...` opens the save dialog with interpretation-prefilled values
  - interpretation photo autofill uses interpretation defaults for case entity/city
  - missing city distance prompts once and persists to the primary profile
  - locked Wave 2 notification-PDF behavior remains unchanged

## 8. Rollout and fallback
- Land Wave 3 as a local-file fallback path after Wave 2.
- If photo OCR yields only partial metadata, still open the interpretation dialog with the extracted subset instead of failing the flow.
- If the distance prompt is canceled, leave the KM fields blank and allow later manual completion.

## 9. Risks and mitigations
- Risk: photo import accidentally regresses the generic translation photo autofill path.
  - Mitigation: switch only interpretation jobs to the interpretation-specific extractor and keep tests around that branch.
- Risk: saved-distance prompting writes the wrong contract field or prompts repeatedly.
  - Mitigation: prompt only when interpretation city exists, KM fields are blank, and no saved distance exists yet.
- Risk: photo import falsely implies a PDF-backed source entry.
  - Mitigation: keep imported photo rows non-PDF-backed and preserve existing PDF-header autofill gating.

## 10. Assumptions/defaults
- The primary profile is the persistence target for import-time distance prompting in the save-to-joblog dialog.
- Photo/screenshot import remains local-file based only.
- Stage boundary after Wave 3 requires exact continuation token `NEXT_STAGE_5`.

## 11. Current status
- Wave 3 implementation is complete in the current worktree.
- Exact continuation token required before Wave 4 work: `NEXT_STAGE_5`

## 12. Validation log
- Implemented Wave 3 files:
  - `src/legalpdf_translate/qt_gui/dialogs.py`
    - enabled the Job Log photo/screenshot interpretation import entrypoint
    - switched interpretation photo autofill to interpretation-specific metadata extraction
    - added one-shot saved-distance prompting and persistence for imported interpretation cities
  - `tests/test_metadata_autofill_photo.py`
    - added interpretation-photo case-default regression coverage
  - `tests/test_qt_app_state.py`
    - added Job Log photo import dialog-seed coverage
    - added interpretation photo autofill distance-persistence coverage
- Executed Stage 4 validations:
  - `.\.venv311\Scripts\python.exe -m pytest tests/test_metadata_autofill_photo.py -q`
    - result: `3 passed in 1.08s`
  - `.\.venv311\Scripts\python.exe -m pytest tests/test_qt_app_state.py -q`
    - result: `132 passed in 9.30s`
- Stage 4 decision locks:
  - Wave 3 remains local photo/screenshot import only.
  - Interpretation photo imports do not create a PDF-backed row contract.
  - Distance persistence remains primary-profile scoped during import-time prompting.
- Residual risks after Stage 4:
  - screenshot OCR quality may still vary significantly across device overlays and cropped captures
  - Wave 4 remote/WebEx and external photo-source integrations remain deferred
- Stage 4 completion status:
  - completed
  - Wave 3 acceptance criteria satisfied by current implementation and targeted validations
- Prepared next-step prompt pack:
  - `NEXT_STAGE_5`: start Wave 4 planning for remote/WebEx and any future external photo-source integrations without changing the locked Wave 2 and Wave 3 local-file contracts
