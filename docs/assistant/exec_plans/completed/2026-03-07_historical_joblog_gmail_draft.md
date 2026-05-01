# 2026-03-07 Historical Job Log Gmail Draft

## Summary
Extend the Gmail draft suggestion so it also works after generating a `Requerimento de Honorários` from the Job Log window for a historical row.

## Scope
- Reuse the existing deterministic Gmail draft subject/body template.
- Keep current-run Save-to-Job-Log behavior unchanged.
- Historical row flow asks the user to pick the translated DOCX manually.
- No schema changes.

## Files
- `src/legalpdf_translate/qt_gui/dialogs.py`
- `tests/test_honorarios_docx.py`

## Validation
- Focused Qt/Gmail tests for current-run and historical-row flows.
- `python -m compileall src tests`
