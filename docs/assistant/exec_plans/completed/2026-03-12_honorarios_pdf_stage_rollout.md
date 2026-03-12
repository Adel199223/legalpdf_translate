# ExecPlan: Honorarios PDF Stage Rollout

## Goal and non-goals
- Goal: implement Stage 1 of the staged honorarios rollout by adding a Windows Word-based DOCX-to-PDF export path for honorarios exports and exposing the PDF result in the export dialog contract.
- Goal: stop after Stage 1 with a stage packet and exact continuation token requirement.
- Non-goal: Stage 2 quick interpretation entrypoint.
- Non-goal: Stage 3 Gmail draft attachment migration.
- Non-goal: Stage 4 docs/user-guide sync beyond any minimal Stage 1 notes required for continuity.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/word_automation.py`
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - Stage 1 tests for Word PDF export helper and honorarios export dialog result behavior
- Out of scope:
  - `gmail_draft.py`
  - `qt_gui/app_window.py`
  - Gmail batch/interpretation session payloads
  - user-guide and canonical docs sync

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/honorarios-pdf-stage1`
- Base branch: `main`
- Base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`
- Canonical build status: Stage 1 code pass on top of an already-dirty worktree carrying the earlier deferred-docs-sync governance changes from this session

## Interfaces/types/contracts affected
- `WordAutomationResult` remains the common result contract.
- New Word automation helper for honorarios DOCX -> PDF export.
- `QtHonorariosExportDialog` gains:
  - `saved_pdf_path: Path | None`
  - `pdf_export_error: str`
- Existing `saved_path` / `requested_path` remain DOCX paths.

## File-by-file implementation steps
1. Extend `word_automation.py` with a PDF export helper built on Word COM / PowerShell `ExportAsFixedFormat`.
2. Extend `QtHonorariosExportDialog` so accepted exports generate DOCX first, then attempt sibling PDF export, then persist the new PDF result fields.
3. Surface PDF-export failure as a user-visible warning while still preserving DOCX success.
4. Add/adjust tests for:
   - Word PDF export helper command/result behavior
   - honorarios export dialog PDF success/failure result fields

## Tests and acceptance criteria
- `python -m pytest -q tests/test_word_automation.py tests/test_honorarios_docx.py tests/test_qt_app_state.py`
- `python -m compileall src tests`
- Acceptance:
  - translation and interpretation honorarios exports still save DOCX
  - a sibling PDF is attempted immediately after DOCX save
  - PDF success populates `saved_pdf_path`
  - PDF failure leaves DOCX saved and populates `pdf_export_error`
  - no Gmail draft flow changes land in this stage

## Rollout and fallback
- Rollout: Stage 1 only, then stop and publish the stage packet.
- Fallback: if Word PDF export is unavailable or unstable, preserve DOCX export and expose a deterministic PDF failure state without blocking local export.

## Risks and mitigations
- Risk: Word COM export path behaves differently from the existing open/save helper.
- Mitigation: keep the result contract identical to current Word automation helpers and unit-test the command/script shape.
- Risk: dialog callers assume only DOCX results exist.
- Mitigation: keep DOCX result fields unchanged and add PDF fields additively.

## Assumptions/defaults
- Windows Word automation is the canonical Stage 1 PDF path.
- DOCX success must remain valid even when PDF export fails.
- Existing dirty governance-doc changes in the worktree are intentionally left in place and must not be reverted during this stage.

## Stage 1 completion evidence
- Implemented isolated Word COM PDF export in `src/legalpdf_translate/word_automation.py` so honorarios export does not depend on an existing interactive Word session.
- Extended `QtHonorariosExportDialog` with `saved_pdf_path` and `pdf_export_error`, and the dialog now saves DOCX first and immediately attempts sibling PDF export.
- Added Stage 1 draft gating so Gmail draft offers are suppressed when PDF generation fails, while DOCX export still succeeds locally.
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_word_automation.py tests/test_honorarios_docx.py tests/test_qt_app_state.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
- Same-host probe completed on Windows:
  - generated a real honorarios DOCX and exported a sibling PDF successfully
  - PDF header confirmed as `%PDF-1.7`

## Stage 2 completion evidence
- Added a direct `New Interpretation Honorários...` action in the main window `Tools` menu and footer overflow menu.
- The new direct flow reuses `build_blank_interpretation_seed()` plus `_open_save_to_joblog_dialog_for_seed(..., allow_honorarios_export=False)`, so interpretation honorarios remains save-first and Job Log remains the single source of truth.
- After a successful save, the main window now builds the interpretation honorarios draft from the saved Job Log payload and opens `QtHonorariosExportDialog` automatically.
- Renamed the Job Log add-menu label to `Blank/manual interpretation entry`.
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_qt_app_state.py tests/test_honorarios_docx.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`

## Stage 3 completion evidence
- Switched honorários Gmail drafting to PDF attachments across translation batch replies, Gmail-intake interpretation replies, and new manual non-threaded interpretation drafts.
- Added `build_manual_interpretation_gmail_request(...)` plus the manual interpretation subject contract in `src/legalpdf_translate/gmail_draft.py`.
- Updated `QtSaveToJobLogDialog` and `QtJobLogWindow` so local/manual interpretation exports can offer Gmail draft creation, while translation exports now pass the honorários PDF instead of the DOCX.
- Updated `QtMainWindow` so:
  - Gmail batch reply drafts attach translated DOCX files plus the honorários PDF
  - Gmail-intake interpretation replies attach the honorários PDF only
  - `New Interpretation Honorários...` can offer a fresh non-threaded Gmail draft after export
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_gmail_draft.py tests/test_honorarios_docx.py tests/test_qt_app_state.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q`

## Stage 4 completion evidence
- Added additive honorários PDF path fields to Gmail batch session reports and introduced durable Gmail interpretation session reports with matching DOCX/PDF finalization fields.
- Updated `QtMainWindow` so Gmail interpretation prepare/finalization paths persist interpretation session status transitions, requested DOCX/PDF paths, actual DOCX/PDF paths, and draft-unavailable outcomes.
- Synced the relevant canonical/docs surfaces:
  - `APP_KNOWLEDGE.md`
  - `docs/assistant/APP_KNOWLEDGE.md`
  - `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - `docs/assistant/features/APP_USER_GUIDE.md`
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_gmail_batch.py tests/test_qt_app_state.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q`
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
- Narrow visual acceptance completed on the same Windows host:
  - generated translation and interpretation honorários DOCX/PDF pairs under `tmp/stage4_visual_acceptance/`
  - confirmed both PDFs were produced by Word export and begin with `%PDF-1.7`
  - repo render tooling fallback was required because `pdftoppm`, `pdftocairo`, and `soffice` are not available on this host
  - captured same-host PDF viewer screenshots in Chrome at:
    - `tmp/stage4_visual_acceptance/translation_pdf_window.png`
    - `tmp/stage4_visual_acceptance/interpretation_pdf_window.png`
