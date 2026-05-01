# Job Log Dialog UI Polish

## Summary
- Carry the latest dashboard visual language into the save/edit job-log dialog where relevant.
- Make fixed-option combos selection-only instead of free-typing.
- Remove hover/glow-driven layout nudges while keeping the elevated visual effect.

## Scope
- `src/legalpdf_translate/qt_gui/dialogs.py`
- `src/legalpdf_translate/qt_gui/styles.py`
- `src/legalpdf_translate/qt_gui/guarded_inputs.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- focused Qt tests only

## Validation
- `python -m pytest -q tests/test_qt_app_state.py`

## Outcome
- Carried the newer dashboard typography into the edit/save job-log dialog by promoting form labels and the top summary card into the shared style language.
- Switched fixed vocab fields (`Job type`, case/service entity, case/service city) to guarded selection-only combos.
- Kept `Court Email` editable, but moved it to the guarded combo helper for consistent hover/popup behavior.
- Added a shared embedded-combo hover override so the dashboard target-language field keeps its glow without the inner control adding a second border.

## Result
- `153 passed` in the focused Qt slice on 2026-03-11.
