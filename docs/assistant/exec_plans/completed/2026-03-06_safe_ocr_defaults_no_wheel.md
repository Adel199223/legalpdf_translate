# Optional OCR-Heavy Safe Profile and No-Wheel Selectors

## Summary
Keep the app's normal defaults for normal documents, provide an optional per-run OCR-heavy safe profile in the warning flow, and prevent accidental wheel-based changes on run-critical selectors inside the app only.

## Scope
In scope:
- preserve normal/global defaults for ordinary documents
- optional per-run OCR-heavy safe-profile application from the warning dialog
- no-wheel guards on run-critical combo/spin controls
- EN/FR xhigh warning action corrected to `fixed_high`
- focused persistence behavior so the safe profile does not overwrite saved defaults
- focused Qt/settings tests

Out of scope:
- translation logic changes
- OCR runtime stabilization logic changes
- any OS-level or system-wide scrolling/input behavior
- docs sync in this pass

## Implemented Result
- Normal/global defaults stay general for ordinary documents; the branch does not force the OCR-heavy safe profile as a new app-wide baseline.
- OCR-heavy runs now offer an optional per-run `Apply safe OCR profile` action instead of silently changing saved defaults.
- The EN/FR `fixed_xhigh` warning now offers `Switch to fixed high` and actually applies `fixed_high`.
- Run-critical combo boxes now ignore wheel changes when closed, and the workers spin box ignores wheel changes entirely.
- Matching settings-dialog controls use the same no-wheel guard.
- Unrelated inputs such as the editable Job Log `Court Email` combo are intentionally left alone.

## Validation
- `python -m compileall src tests` -> pass
- `python -m pytest -q tests/test_user_settings_schema.py` -> `12 passed`
- `python -m pytest -q tests/test_qt_app_state.py -k "no_wheel or guarded or safe_profile or fixed_xhigh"` -> `9 passed`
- `python -m pytest -q` -> `551 passed`
- docs/workspace validators -> pass

## Operational Notes
- The OCR-heavy safe profile is temporary for the current run only:
  - OCR mode `always`
  - OCR engine `api`
  - Image mode `off`
  - Workers `1`
  - Effort policy `fixed_high`
  - Resume `off`
  - Keep intermediates `on`
- This work does not touch OS-level or system-wide scrolling behavior.
