# Stabilize Interpretation Notice Autofill and Honorarios Export

## 1. Title
Stabilize interpretation notice autofill, OCR fallback diagnostics, and honorarios PDF export recovery.

## 2. Goal and non-goals
Goal:
- Make interpretation notice intake recover metadata reliably from native PDF text or OCR.
- Use one interpretation-aware autofill path across Gmail intake and manual/edit dialog recovery.
- Surface actionable OCR failure diagnostics instead of silently opening mostly empty forms.
- Make honorarios PDF export more resilient and make local-only completion explicit.

Non-goals:
- Rework the Gmail browser extension transport contract.
- Allow Gmail draft creation without a valid PDF.
- Redesign translation-mode header autofill semantics.

## 3. Scope (in/out)
In:
- Interpretation notice metadata extraction and diagnostics.
- Job Log interpretation autofill button behavior and copy.
- OCR provider default/env compatibility for OpenAI.
- Gmail interpretation session reporting.
- Honorarios PDF export timeout/retry and local-only UX.
- Focused tests for the above behavior.

Out:
- Translation pipeline OCR behavior outside interpretation notice metadata recovery.
- Browser extension message shape changes.
- Broad UI styling changes unrelated to these flows.

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; canonical build remains `C:\Users\FA507\.codex\legalpdf_translate` on `main` per `docs/assistant/runtime/CANONICAL_BUILD.json`
- Current HEAD SHA: `5c9842e3fbec1ca2351507f1f31bbf8b5b7ffa02`
- Distinguishing feature set: beginner-first primary-flow UX worktree currently used for latest interpretation UX

## 5. Interfaces/types/contracts affected
- Add additive interpretation metadata diagnostics type/helper in `src/legalpdf_translate/metadata_autofill.py`.
- Add additive `metadata_extraction` and `pdf_export` sections to Gmail interpretation session report payload in `src/legalpdf_translate/gmail_batch.py`.
- Make Save/Edit Job Log autofill button contract job-type aware in `src/legalpdf_translate/qt_gui/dialogs.py`.
- Keep existing high-level extractors callable for compatibility where practical.

## 6. File-by-file implementation steps
- `src/legalpdf_translate/metadata_autofill.py`
  - Add notice extraction diagnostics structure and helper that returns suggestion plus diagnostics.
  - Record embedded-text hits, OCR attempts, local/API availability, page list, and failure reason.
  - Force OCR-capable interpretation notice recovery on pages 1-2 even when generic OCR mode is off.
- `src/legalpdf_translate/ocr_engine.py`
  - Change OpenAI default OCR env name to `OPENAI_API_KEY`.
  - Keep legacy `DEEPSEEK_API_KEY` fallback compatibility in effective key resolution.
- `src/legalpdf_translate/user_settings.py`
  - Normalize OpenAI OCR env defaults to `OPENAI_API_KEY`.
  - Treat legacy `DEEPSEEK_API_KEY` as a compatible old default rather than a required new value.
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - Make interpretation-mode autofill use full notice extraction and a notice-oriented label.
  - Keep translation mode on header-only autofill.
  - Surface extraction diagnostics in the UI when metadata is missing.
  - Stop defaulting interpretation notice `service_date` to today when extraction fails.
  - Improve OCR settings summary/test to report effective env-backed credentials and local Tesseract availability.
  - Improve honorarios PDF export local-only outcome messaging.
- `src/legalpdf_translate/qt_gui/app_window.py`
  - Use diagnostic-aware interpretation extraction in Gmail finalization.
  - Persist metadata and PDF export outcomes into the Gmail interpretation session.
  - Show explicit local-only outcome when Gmail draft is skipped because PDF is unavailable.
- `src/legalpdf_translate/gmail_batch.py`
  - Extend Gmail interpretation session data/report payload with additive metadata extraction and PDF export fields.
- `src/legalpdf_translate/word_automation.py`
  - Increase PDF export timeout and add one retry for timeout failures.
- Tests:
  - `tests/test_metadata_autofill_header.py`
  - `tests/test_qt_app_state.py`
  - `tests/test_honorarios_docx.py`
  - `tests/test_user_settings_schema.py`
  - `tests/test_word_automation.py`

## 7. Tests and acceptance criteria
- Interpretation-mode dialog autofill uses notice extraction and populates body-derived service dates.
- Blank/scanned notice with OCR unavailable shows actionable diagnostics rather than a silent blank result.
- OpenAI OCR settings resolve `OPENAI_API_KEY` by default and still accept `DEEPSEEK_API_KEY`.
- OCR settings summary/test report env-backed credentials and missing local Tesseract accurately.
- Gmail interpretation session report contains metadata extraction and PDF export diagnostics.
- Honorarios PDF export retries once on timeout.
- After `Continue local-only`, the user gets an explicit local-ready outcome and Gmail draft remains blocked.

## 8. Rollout and fallback
- Keep additive report fields optional so old reports remain readable.
- Keep legacy OCR env aliasing during migration to avoid breaking existing environments.
- Preserve translation-mode header autofill behavior to limit regression surface.

## 9. Risks and mitigations
- Risk: forcing OCR in interpretation metadata flow could surprise users who keep OCR off for translation.
  - Mitigation: scope the override only to interpretation notice metadata pages and surface the reason in diagnostics.
- Risk: changing OCR env defaults could break users who adapted to the legacy name.
  - Mitigation: support both `OPENAI_API_KEY` and legacy `DEEPSEEK_API_KEY`.
- Risk: longer/retried Word export could delay failure dialogs.
  - Mitigation: keep export off the UI thread and report retry status clearly.

## 10. Assumptions/defaults
- Interpretation notice metadata recovery should automatically attempt OCR on the first 1-2 pages when embedded text is blank.
- Gmail drafts still require a valid PDF attachment.
- Existing unrelated dirty worktree state in `docs/assistant/SESSION_RESUME.md` is not part of this task and will remain untouched.
