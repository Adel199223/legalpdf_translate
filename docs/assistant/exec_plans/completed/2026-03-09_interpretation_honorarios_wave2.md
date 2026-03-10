# Interpretation Honorarios Wave 2

## 1. Title
Notification-first interpretation import from local PDF.

## 2. Goal and non-goals
- Goal:
  - add a local PDF notification import path for interpretation cases
  - prefill `Edit Job Log Entry` with interpretation metadata extracted from court notifications
  - prefer the hearing/attendance date instead of the document issue date
- Non-goals:
  - no photo/screenshot import yet
  - no remote/WebEx branch
  - no interpretation Gmail draft flow

## 3. Scope (in/out)
- In:
  - dedicated interpretation-notification metadata extraction over full priority-page text
  - `Job Log -> Add... -> From notification PDF...`
  - prefilled interpretation `JobLogSeed` with local PDF path retained
  - focused parser and Qt flow tests
- Out:
  - Google Photos or Samsung Gallery integration
  - screenshot-visible metadata OCR import
  - automatic distance prompting from imported photos

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/interpretation-honorarios`
- Base branch: `main`
- Base SHA: `abf608f16fac69e477849b9e8b3e040502856999`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- Metadata extraction:
  - additive interpretation-notification parser for full-text priority-page extraction
- Qt:
  - Job Log notification import entrypoint becomes live
  - imported notification rows open in the existing save/edit dialog with `job_type = Interpretation`
- Roadmap continuity:
  - `SESSION_RESUME.md` should point to this wave while it is active

## 6. File-by-file implementation steps
- `src/legalpdf_translate/metadata_autofill.py`
  - add hearing-date extraction heuristics
  - add explicit GNR/PSP service-location extraction
  - add full-page PDF text extraction with OCR fallback
  - add public interpretation-notification extraction helpers
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - add a builder for interpretation seeds from notification suggestions
  - enable `Job Log -> Add... -> From notification PDF...`
  - open `QtSaveToJobLogDialog` with prefilled interpretation values
- `tests/test_metadata_autofill_header.py`
  - add notification-date and explicit-location regressions
- `tests/test_qt_app_state.py`
  - add a notification-import flow test for the prefilled dialog seed

## 7. Tests and acceptance criteria
- `tests/test_metadata_autofill_header.py`
- `tests/test_qt_app_state.py`
- Acceptance:
  - service date prefers hearing/attendance wording over issue/certification dates
  - explicit GNR/PSP service locations are suggested only when present in the notice
  - `Job Log -> Add... -> From notification PDF...` opens the save dialog with interpretation prefilled
  - imported interpretation rows keep `service_city` blank unless the notice explicitly named a service location

## 8. Rollout and fallback
- Land Wave 2 as a deterministic local-file import path before photo/screenshot import.
- If a notification yields only partial metadata, still open the interpretation edit dialog with the extracted subset rather than failing the flow entirely.

## 9. Risks and mitigations
- Risk: issue/certification date gets mistaken for hearing date.
  - Mitigation: score dates by hearing/attendance context and penalize certification/document wording.
- Risk: service-location extraction becomes too aggressive.
  - Mitigation: only auto-suggest explicit service location for clearly named GNR/PSP references in the notice text.
- Risk: import path duplicates existing header autofill logic inconsistently.
  - Mitigation: reuse shared metadata helpers and the existing `JobLogSeed`/dialog flow.

## 10. Assumptions/defaults
- Priority pages are the first two pages unless the document is shorter.
- Local PDF import is the only supported notification source in this wave.
- Service-location insertion still requires later user confirmation through the existing checkbox; import does not enable it automatically.

## 11. Current status
- Wave 2 implementation is complete in the current worktree.
- Stage 3 close-out is recorded below.
- Exact continuation token required before Wave 3 work: `NEXT_STAGE_4`

## 12. Validation log
- Implemented Wave 2 files:
  - `src/legalpdf_translate/metadata_autofill.py`
    - added interpretation-notification extraction from full priority-page text with OCR fallback
    - added deterministic service-date scoring that prefers hearing/attendance wording over issue/certification dates
    - added conservative explicit `GNR`/`PSP` service-location extraction
  - `src/legalpdf_translate/qt_gui/dialogs.py`
    - enabled `Job Log -> Add... -> From notification PDF...`
    - added interpretation seed building from notification suggestions with retained local `pdf_path`
    - kept interpretation rows valid with blank translation-only fields
    - prevented Gmail draft offering for interpretation honorarios exports
  - `tests/test_metadata_autofill_header.py`
    - added hearing-date, explicit-service-location, and priority-page PDF regressions
  - `tests/test_qt_app_state.py`
    - added notification-import dialog-seed coverage
    - added interpretation payload normalization coverage
    - added interpretation honorarios no-Gmail regression coverage
- Executed Stage 3 validations:
  - `.\.venv311\Scripts\python.exe -m pytest tests/test_metadata_autofill_header.py -q`
    - result: `12 passed in 0.64s`
  - `.\.venv311\Scripts\python.exe -m pytest tests/test_qt_app_state.py -q`
    - result: `130 passed in 7.57s`
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
- Stage 3 decision locks:
  - Wave 2 remains local-PDF notification import only.
  - Priority pages remain pages 1-2 unless the document is shorter.
  - Imported interpretation seeds retain `pdf_path` and do not auto-enable service-location insertion.
  - `service_city` stays blank unless the notice explicitly names a service location.
  - Interpretation honorarios export remains local-doc generation only; no Gmail draft flow is added in this wave.
- Residual risks after Stage 3:
  - Real-world court-notice formatting may still produce partial metadata when hearing wording is unusually indirect.
  - OCR fallback quality remains dependent on source scan quality when ordered PDF text is unavailable.
  - Wave 3 distance prompting and screenshot/photo fallback are intentionally deferred.
- Stage 3 completion status:
  - completed
  - Wave 2 acceptance criteria satisfied by current implementation and targeted validations
- Prepared next-step prompt pack:
  - `NEXT_STAGE_4`: start Wave 3 photo/screenshot fallback and saved-distance prompting without changing the locked Wave 2 notification-PDF contract
