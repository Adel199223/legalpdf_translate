# Requerimento de Honorarios DOCX Feature

## 1) Title
Add deterministic DOCX export for a completed "Requerimento de Honorarios" from Save-to-Job-Log and Job Log.

## 2) Goal and non-goals
- Goal:
  - generate a Microsoft Word `.docx` in European Portuguese using the locked template text
  - make it available from the Save-to-Job-Log dialog and the Job Log window
  - keep wording deterministic and fixed
  - match the reference screenshot structure closely using `python-docx`
- Non-goals:
  - no LLM generation or validation in the shipped path
  - no schema changes
  - no CLI changes
  - no translation workflow/model changes

## 3) Scope (in/out)
- In:
  - `src/legalpdf_translate/honorarios_docx.py`
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - relevant Qt tests
  - visual acceptance via rendered DOCX
- Out:
  - GPT-5.4 integration for this feature
  - billing schema changes
  - generic document-template engine work

## 4) Interfaces/types/contracts affected
- Add internal `HonorariosDraft` document model
- Add additive GUI actions:
  - Save-to-Job-Log dialog: `Gerar Requerimento de Honorarios...`
  - Job Log window: `Gerar Requerimento de Honorarios...`
- `Words` source remains translated output words from current corrected Job Log/current seed values

## 5) File-by-file implementation steps
- Add deterministic DOCX generator with Portuguese date helper and safe filename helper
- Add shared generator dialog that validates required fields and exports via `QFileDialog`
- Wire generator button into Save-to-Job-Log dialog using current form values
- Wire generator button into Job Log window using selected-row values
- Add tests for exact wording, DOCX structure, validation, and UI entrypoints
- Run visual acceptance render against the reference structure

## 6) Tests and acceptance criteria
- Exact template wording preserved except for the required placeholders
- Portuguese final date rendered as `Beja, DD de <mes> de AAAA`
- Save-to-Job-Log flow can generate without saving the row first
- Job Log selected-row flow can generate from historical data
- Missing required fields block export until corrected
- DOCX render matches the intended layout closely enough for client use

## 7) Rollout and fallback
- Local feature on current branch only
- If DOCX generation fails, surface a normal export error and leave Job Log/save flows intact

## 8) Risks and mitigations
- Risk: layout drift from screenshot
  - Mitigation: render and inspect generated DOCX during acceptance
- Risk: word-count confusion
  - Mitigation: use existing corrected translated-output word count only

## 9) Assumptions/defaults
- Feature is always in European Portuguese
- Fixed constants remain hardcoded until the user explicitly asks to change them
- No AI is used in v1
