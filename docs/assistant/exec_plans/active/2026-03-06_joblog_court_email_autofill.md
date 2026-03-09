# Job Log Court Email Autofill

## 1) Title
Add court-email autofill to the Job Log save flow and table model

## 2) Goal and non-goals
- Goal:
  - Capture a court email from the PDF header area and store it with new Job Log rows.
  - Keep the field editable in Save to Job Log and available in the Job Log table/column chooser.
- Non-goals:
  - No backfill of existing DB rows.
  - No AI-based email guessing.
  - No CLI/workflow artifact schema changes.

## 3) Scope (in/out)
- In:
  - metadata extraction
  - JobLogSeed/save dialog wiring
  - SQLite additive schema update
  - Job Log table column support
  - targeted tests
- Out:
  - existing row backfill
  - non-Job-Log product surfaces

## 4) Interfaces/types/contracts affected
- Additive `job_runs.court_email` column
- Additive `MetadataSuggestion.court_email`
- Additive `JobLogSeed.court_email`
- Additive Job Log table column label `Court Email`

## 5) File-by-file implementation steps
1. Extend metadata autofill to parse court-nearest email candidates from page 1, then page 2.
2. Add Job Log seed/dialog/table support for the new `court_email` field.
3. Add additive DB migration and table-query support.
4. Update tests for metadata extraction, seed prefills, dialog save payload, and migration safety.

## 6) Tests and acceptance criteria
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_metadata_autofill_header.py tests/test_qt_app_state.py tests/test_db_migration_joblog_v2.py`
- `./.venv311/Scripts/python.exe -m compileall src tests`
- `./.venv311/Scripts/python.exe -m pytest -q`
- Acceptance:
  - page 1 first, page 2 fallback
  - no duplicate/AI email guessing
  - DB migration is additive/idempotent
  - Job Log table supports the hidden-by-default column

## 7) Rollout and fallback
- Rollout:
  - ship as additive schema + UI field
  - no default-visible column change
- Fallback:
  - blank `court_email` is acceptable when nothing reliable is found

## 8) Risks and mitigations
- Risk: false-positive email selection in noisy headers.
  - Mitigation: prefer court-nearest candidates first; otherwise deterministic page-order fallback only.
- Risk: schema drift for existing local DBs.
  - Mitigation: additive migration only; no backfill of historical rows.

## 9) Assumptions/defaults
- `Court Email` is the user-facing label.
- New/future saves only.
- OCR fallback is allowed for header extraction when text extraction is empty.
