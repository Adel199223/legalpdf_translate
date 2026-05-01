# Dashboard Combo Popup Hover Fix

## Summary
- Fix dashboard target-language popup clipping/ellipsis.
- Fix advanced-settings combo hover/open highlighting so only the active control lights up.
- Reuse one shared combo popup/hover treatment across the relevant dashboard and shared-form `NoWheelComboBox` controls.

## Acceptance
- Target-language popup shows readable full names.
- Closed target-language field stays `EN` / `FR` / `AR`.
- Hover/open state stays local to the correct combo.
- Dashboard target-language chrome feels consistent with advanced-settings dropdowns.

## Validation
- `tests/test_qt_app_state.py`
- `tests/test_qt_main_smoke.py`

## Outcome
- Implemented shared popup-label, popup-width, and hover/open state handling in `NoWheelComboBox`.
- Target-language popup now uses full names while the closed field stays `EN` / `FR` / `AR`.
- Dashboard wrapper/caret chrome now follows the same hover/open system as the shared form combos.
- Advanced-settings combo activation now stays local to the active control instead of visually leaking to a neighbor.

## Evidence
- `PYTHONPATH=C:\Users\FA507\.codex\legalpdf_translate_combo_popup_fix\src C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest tests\test_qt_app_state.py tests\test_qt_main_smoke.py -q` -> `153 passed`
- `git diff --check` -> clean
