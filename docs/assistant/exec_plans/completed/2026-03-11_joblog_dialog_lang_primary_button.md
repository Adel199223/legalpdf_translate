# Job-Log Dialog Lang And Primary Button Polish

## Summary
- Make the `Lang` field in the save/edit job-log dialog a fixed-option guarded combo.
- Keep the bottom-right save/update action rounded and primary-styled even when Qt treats it as the default button.

## Scope
- `src/legalpdf_translate/qt_gui/dialogs.py`
- `src/legalpdf_translate/qt_gui/styles.py`
- focused Qt tests only

## Validation
- `python -m pytest -q tests/test_qt_app_state.py tests/test_qt_main_smoke.py`

## Outcome
- Replaced the top-row `Lang` field with the guarded supported-language combo while preserving legacy current values.
- Made `Pages` read-only because it is captured metadata in this dialog rather than a user-tuned field.
- Added explicit `PrimaryButton:default` styling and default-button wiring so the save/update action keeps the rounded app look.

## Result
- `153 passed` in the focused Qt slice on 2026-03-11.
