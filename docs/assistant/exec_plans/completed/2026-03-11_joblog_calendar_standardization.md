# Calendar Standardization and Job-Log Dialog Cleanup

## Summary
- standardize all current app calendar popups to Monday-first
- extend the shared guarded date control into Job Log inline row editing
- hide the translation-only irrelevant service section in the edit/save dialog
- keep the dialog primary action rounded while preserving Enter-key submit

## Validation
- `python -m pytest -q tests/test_qt_app_state.py tests/test_honorarios_docx.py tests/test_qt_main_smoke.py`
- `git diff --check`

## Result
- standardized guarded calendar popups to Monday-first
- extended the shared date control into Job Log inline row editing
- hid the service section for translation rows in the edit/save dialog
- removed native-default-button dependence from the dialog primary action while keeping Enter-key submit
- validation passed: `194 passed`
