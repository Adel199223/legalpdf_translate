# Calendar Picker Across Relevant Date Fields

## Summary
- add one shared guarded date control with manual ISO typing plus calendar popup
- wire it into the relevant editable date fields in job-log and honorarios dialogs
- keep existing validation and stored values unchanged

## Scope
- `src/legalpdf_translate/qt_gui/guarded_inputs.py`
- `src/legalpdf_translate/qt_gui/dialogs.py`
- `src/legalpdf_translate/qt_gui/styles.py`
- targeted Qt tests

## Validation
- `python -m pytest -q tests/test_qt_app_state.py tests/test_honorarios_docx.py tests/test_qt_main_smoke.py`
- `git diff --check`

## Result
- added one shared guarded date field with manual ISO typing plus a calendar popup
- wired it into the relevant job-log and interpretation honorários date fields
- validation passed: `193 passed`
