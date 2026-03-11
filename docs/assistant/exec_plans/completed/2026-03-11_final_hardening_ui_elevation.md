# Final Hardening Pass: App Audit, Docs Sync, and UI Elevation

## Summary
- Completed one final late-stage hardening pass focused on concrete defects, inconsistencies, and UI polish.
- Kept the work centered on the dashboard plus core dialogs: Settings, Gmail review/preview, Save/Edit Job Log, and honorários export.
- Finished with a narrow Assistant Docs Sync so docs now match the shipped UI and settings behavior.

## Key Changes
- Audit and fix concrete late-stage issues only:
  - persisted `ui_theme` now applies live at startup and through shared-settings propagation instead of being dead state
  - removed style drift caused by inline widget-local stylesheet fragments in the main shell
  - fixed the remaining Gmail preview wording inconsistency (`Start from this page`)
  - consolidated shared panel/button/field/dialog chrome in the Qt style layer
- Elevate the visual system without changing product workflows:
  - stronger depth and hierarchy for the dashboard shell, setup/output cards, and action rail
  - more raised button, dropdown, menu, and metric styling while keeping controlled transparency
  - extended the same visual language to Settings, Gmail review/preview, Save/Edit Job Log, and honorários export through shared QSS selectors and dialog scroll/action-bar object names
- Preserve current responsive and workflow contracts:
  - no main-shell horizontal scrollbar
  - no resize-jitter regressions
  - no off-screen dialogs
  - no Gmail/interpretation/honorários workflow redesign

## Validation
- `python -m pytest tests/test_qt_main_smoke.py tests/test_qt_app_state.py -q` -> `150 passed`
- `python -m compileall src tests` -> `OK`
- `python -m pytest -q` -> `864 passed`
- `python tooling/qt_render_review.py --outdir tmp/qt_ui_review --preview reference_sample` -> generated `wide`, `medium`, and `narrow` review renders under `tmp/qt_ui_review/`
- `dart run tooling/validate_agent_docs.dart` -> `PASS`

## Notes
- `dark_futuristic` remains the default theme and gets the elevated treatment.
- `dark_simple` stays available as a lower-noise variant built from the same centralized style system.
- Shared runtime appearance now flows through `qt_app.run()` and `WorkspaceWindowController.apply_shared_settings()` via `qt_gui/styles.py`.
