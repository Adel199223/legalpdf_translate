# Target Language Alignment And Typography Refresh

## Summary
- Center the compact `EN` / `FR` / `AR` badge in the dashboard target-language field.
- Refresh the main-window/dashboard typography to a more polished modern-professional stack.

## Scope
- `src/legalpdf_translate/qt_gui/guarded_inputs.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- `src/legalpdf_translate/qt_gui/styles.py`
- `src/legalpdf_translate/qt_app.py`
- focused Qt tests only

## Validation
- `python -m pytest -q tests/test_qt_app_state.py tests/test_qt_main_smoke.py`

## Outcome
- Centered the compact target-language badge via shared combo alignment metadata while keeping popup labels unchanged.
- Swapped the main dashboard typography to Aptos-first body and Aptos Display-first heading stacks with explicit fallbacks.
- Updated focused Qt tests for alignment and stylesheet font-stack coverage.

## Result
- `153 passed` in the focused Qt slice on 2026-03-11.
