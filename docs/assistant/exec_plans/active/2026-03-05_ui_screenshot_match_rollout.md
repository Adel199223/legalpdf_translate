# Exact Screenshot-Match UI Redesign Rollout

## 1) Title
Exact screenshot-match UI redesign rollout for the Qt dashboard

## 2) Goal and non-goals
- Goal:
  - Rebuild the main Qt window to match the provided dashboard screenshot as closely as possible while keeping the current translation workflows functional.
  - Deliver the redesign in hard-gated stages with manual app review between stages.
- Non-goals:
  - No `.ui` migration in this pass.
  - No CLI, workflow, or schema changes.
  - No fake OS chrome, taskbar, or watermark recreation inside the app.

## 3) Scope (in/out)
- In:
  - Stage 1: shell/layout parity and visual direction.
  - Stage 2: live data wiring and action remapping.
  - Stage 3: pixel-polish, exactness pass, and hardening.
- Out:
  - New product features beyond the UI redesign.
  - Packaging/deployment changes unless required by validation.

## 4) Interfaces/types/contracts affected
- Existing Qt widget object references must remain stable for runtime logic.
- One internal Qt-only dashboard metrics layer is allowed for live right-panel rendering.

## 5) File-by-file implementation steps
1. Add this ExecPlan and keep it updated stage by stage.
2. Introduce local icon assets for the new dashboard shell.
3. Rebuild `src/legalpdf_translate/qt_gui/app_window.py` shell/layout for Stage 1.
4. Update `src/legalpdf_translate/qt_gui/styles.py` for the new visual system.
5. Extend Qt tests/smoke coverage for the redesigned shell.
6. Validate, launch app, publish stage packet, and stop for the next continuation token.

## 6) Tests and acceptance criteria
- `./.venv311/Scripts/python.exe -m compileall src tests`
- `./.venv311/Scripts/python.exe -m pytest -q`
- Visual/manual review against the reference screenshot after each stage.

## 7) Rollout and fallback
- Rollout:
  - Stage-gated execution with exact `NEXT_STAGE_X` continuation tokens.
  - Stop after each stage with changed files, validations, risks, and test checklist.
- Fallback:
  - Keep widget object references stable so shell refactors can be adjusted without workflow rewrites.

## 8) Risks and mitigations
- Risk: breaking existing action wiring during shell rebuild.
  - Mitigation: keep existing widget attributes and handlers, hide/remap rather than remove.
- Risk: visual parity causing loss of access to advanced flows.
  - Mitigation: preserve advanced/settings/tools access behind collapsible or overflow surfaces.
- Risk: desktop-only screenshot parity hurting resize behavior.
  - Mitigation: use layouts and size policies only; avoid fixed geometry.

## 9) Assumptions/defaults
- Native menu bar stays real.
- Live app data replaces screenshot sample values.
- Sidebar uses mixed real actions plus explicit `Coming soon` for unsupported destinations.
- Stage 1 begins now; later stages require exact continuation tokens.

## Stage Packet — Stage 1
- Status: completed.
- Scope:
  - Rebuild the main shell to match the screenshot composition.
  - Add sidebar, hero/title row, two-panel dashboard frame, and bottom action rail.
  - Preserve current behaviors behind the same widget references.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
  - `resources/icons/dashboard/*`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`10 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`498 passed`)
  - manual shell smoke instantiation via `QtMainWindow()` -> PASS
- Notes:
  - The redesign remains Python-built; no `.ui` migration was introduced.
  - Stage 1 focuses on shell/layout parity only. The right-side progress panel is still driven by existing runtime fields and will be refined in Stage 2.
- Continuation token:
  - `NEXT_STAGE_2`

## Stage Packet — Stage 2
- Status: completed.
- Scope:
  - Wire the dashboard shell to live translation/analyze/queue runtime state.
  - Move non-mock surfaces behind the existing advanced section and Tools menu without breaking the screenshot-driven main shell.
  - Correct the largest visual mismatches discovered during Stage 1 review: compressed proportions, oversized top glow band, and weak action/menu parity.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`12 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`500 passed`)
- Notes:
  - The right panel now uses an internal dashboard snapshot model for progress percent, ETA text, task text, and queue-mode remapping.
  - Tools menu now exposes `Review Queue`, `Save to Job Log`, and `View Job Log` so those flows remain reachable without polluting the screenshot-driven dashboard.
  - Visual adjustments in this stage target the deltas seen in the manual screenshot comparison; final pixel polish remains Stage 3.
- Continuation token:
  - `NEXT_STAGE_3`

## Stage Packet — Stage 3
- Status: completed.
- Scope:
  - Remove the remaining compression and “desktop screenshot wallpaper” feel from the dashboard.
  - Tighten the layout grid, equalize footer action heights, and widen the primary content region.
  - Upgrade the visual quality of the flag asset, retry presentation, typography, and progress/control polish.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
  - `resources/icons/dashboard/flag_en.svg`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`13 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`501 passed`)
- Notes:
  - The dashboard width clamp was raised so the shell can use large desktop screens properly.
  - Footer actions now share identical heights and fixed secondary widths.
  - Retry counts now render with a dedicated retry glyph badge in the metrics grid.
  - This completes the planned 3-stage UI rollout.

## Stage Packet — Stage 3 Follow-Up
- Status: completed.
- Scope:
  - Rebuild the dashboard around explicit size classes so large windows stay close to the reference image and smaller windows adapt intentionally instead of drifting.
  - Remove the remaining structural compression that came from centering the content card with a restrictive alignment path.
  - Slim the sidebar further, widen the desktop card, and make stacked compact mode a first-class layout.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`15 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`503 passed`)
- Notes:
  - Three explicit layout modes now drive geometry: `desktop_exact`, `desktop_compact`, and `stacked_compact`.
  - Large-window width is now computed directly and centered cleanly instead of being capped by a size-hint alignment path.
  - Small-window behavior is now intentionally stacked: setup above output, primary CTA on the first footer row, and secondary actions on the second row.

## Stage Packet — Fidelity Correction Stage 1
- Status: completed.
- Scope:
  - Correct the large-window shell so it matches the Gemini reference more literally without hardcoding sample values.
  - Widen and re-rhythm the sidebar so nav labels are fully readable at desktop sizes.
  - Add the missing `Conversion Output` heading and rebalance the setup/output panel proportions.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`15 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`503 passed`)
- Notes:
  - Desktop exact mode now uses a wider sidebar with readable labels and larger nav items.
  - The right panel now includes the missing `Conversion Output` heading while keeping live runtime values.
  - Large, medium, and narrow offscreen renders were regenerated for manual comparison.

## Stage Packet — Reference-Locked Reset Stage A
- Status: completed.
- Scope:
  - Replace approximate desktop-shell acceptance with a reference-locked desktop contract.
  - Make the desktop sidebar wide enough for full labels and refresh the `Dashboard` and `Recent Jobs` line-art icons.
  - Rebalance the setup/output desktop proportions while keeping the right-panel `Conversion Output` heading fixed in place.
- Region pass/fail checks:
  - `Sidebar`: full `Dashboard` and `Recent Jobs` labels with no truncation.
  - `Hero row`: centered title and right-aligned `Idle`.
  - `Right card shell`: `Conversion Output` heading present and desktop two-column balance restored.
  - `Overflow menu`: closed by default in the desktop idle view.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
  - `resources/icons/dashboard/home.svg`
  - `resources/icons/dashboard/recent.svg`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`16 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`504 passed`)
  - Deterministic renders regenerated -> `tmp_ui_check/wide_stageA.png`, `tmp_ui_check/medium_stageA.png`, `tmp_ui_check/narrow_stageA.png`
- Notes:
  - Desktop sidebar and nav item widths are now driven by the reference-locked desktop contract instead of the earlier compressed shell defaults.
  - Desktop panel balance now uses a tighter setup/output ratio while keeping `Conversion Output` fixed in the right shell.
  - Stage B still needs to correct field logic/chrome, including the target-language duplicate-text bug and the desktop field structure.

## Stage Packet — Reference-Locked Reset Stage B
- Status: completed.
- Scope:
  - Correct field logic and field chrome so the desktop shell uses live data without duplicate language rendering.
  - Simplify the right-card retries column to heading-only while keeping retry tracking internal.
  - Rebuild the footer/action rail proportions and keep the disabled state intentional.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
  - `tests/test_qt_app_state.py`
  - `resources/icons/dashboard/globe.svg`
  - `resources/icons/dashboard/pdf_search.svg`
  - `resources/icons/dashboard/folder_search.svg`
  - `resources/icons/dashboard/pages.svg`
  - `resources/icons/dashboard/images.svg`
  - `resources/icons/dashboard/caret_down.svg`
  - `resources/icons/dashboard/flag_fr.svg`
  - `resources/icons/dashboard/flag_ar.svg`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`19 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`507 passed`)
  - Deterministic renders regenerated -> `tmp_ui_check/wide_stageB.png`, `tmp_ui_check/medium_stageB.png`, `tmp_ui_check/narrow_stageB.png`
- Notes:
  - Target-language rendering now shows one live code and one matching flag only; the duplicate raw-text fallback has been removed.
  - The Source PDF support cluster now keeps `Pages: -` readable and separated from the browse affordance.
  - The desktop metrics grid now keeps the `Retries` heading only; row-level retry badges are no longer rendered in that grid.
  - Stage C remains for background/glow/typography refinement and responsive hardening only.

## Stage Packet — Reference-Locked Reset Stage C
- Status: completed.
- Scope:
  - Retune the background scene, glow hierarchy, frame translucency, and typography for the final desktop visual pass.
  - Preserve the responsive size classes while cleaning temporary UI verification artifacts from the repo state.
- Changed files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/styles.py`
- Validation results:
  - `dart run tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> PASS
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py` -> PASS (`19 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q` -> PASS (`507 passed`)
  - Off-repo renders regenerated -> `%TEMP%\\legalpdf_ui_stagec\\wide.png`, `medium.png`, `narrow.png`
- Notes:
  - The scene now uses a broader left cyan wash, lower-noise circuit overlays, and a softer right-side glow so the shell reads closer to the target image.
  - Title glow and body typography were separated more aggressively: stronger hero emphasis, less halo on supporting text.
  - `tmp_ui_check/` was removed from the working tree so only source changes remain.

## Post-Rollout Patch — GUI Launch Entry Point
- Status: completed.
- Scope:
  - Fix direct module launch so `python -m legalpdf_translate.qt_app` actually starts the GUI event loop.
  - Add regression coverage for the `qt_app.py` module entrypoint contract.
- Changed files:
  - `src/legalpdf_translate/qt_app.py`
  - `tests/test_qt_main_smoke.py`
- Validation results:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_main_smoke.py` -> PASS (`3 passed`)
  - `./.venv311/Scripts/python.exe -m compileall src tests` -> PASS
- Notes:
  - Root cause was a missing `if __name__ == "__main__": raise SystemExit(run())` guard in `qt_app.py`.
  - Assistant docs sync for this rollout must document `legalpdf_translate.qt_app` as the real GUI launch path.
