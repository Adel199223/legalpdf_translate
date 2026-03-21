# Browser-to-Qt UX Alignment Stage 5

## Stage goal
- Align the remaining secondary browser routes with Qt-style bounded dialog, table, and preview behavior.
- Keep `Recent Jobs` as the main secondary production page while de-emphasizing operator/admin/testing routes behind `More`.
- Finish the whole-app cleanup pass across wide and narrow layouts without changing the existing browser runtime contracts.

## Completed implementation
- Reframed `Recent Jobs` into a calmer secondary production route with a bounded overview sheet and collapsed deeper history sections for translation runs, translation job-log rows, and interpretation history.
- Reworked `Settings` into a bounded operator sheet with three grouped collapsibles:
  - `Defaults`
  - `OCR and Gmail`
  - `Diagnostics and Job Log`
- Reworked `Profiles` into a bounded management route where the list and primary profile stay on-page and the editor now opens in a dedicated same-tab drawer.
- Reframed `Power Tools` and `Extension Lab` as bounded operator stacks instead of product-level home pages while preserving their existing controls and direct hashes.
- Fixed the interpretation-to-Gmail follow-up path so opening Gmail session actions from interpretation review closes the interpretation drawer first instead of leaving Gmail hidden under another drawer.

## Files changed in this stage
- `docs/assistant/SESSION_RESUME.md`
- `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage5.md`
- `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage4.md`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `src/legalpdf_translate/shadow_web/static/app.js`
- `src/legalpdf_translate/shadow_web/static/style.css`
- `tests/test_shadow_web_api.py`

## Validation completed
- `python -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py tests/test_browser_gmail_bridge.py`
  - `24 passed`
- `python -m compileall src tests`
  - passed
- `dart run tooling/validate_agent_docs.dart`
  - passed
- `dart run tooling/validate_workspace_hygiene.dart`
  - passed
- Playwright smoke on `http://127.0.0.1:8894/?mode=shadow&workspace=workspace-preview`
  - `#profile` opens the new bounded profile editor drawer
  - `#recent-jobs` shows the calmer overview plus collapsed deeper histories
  - `#settings` reads as a grouped bounded operator sheet
  - live-mode narrow-width smoke on `?mode=live&workspace=workspace-preview#settings` stays readable with the stacked bounded layout
  - the interpretation-to-Gmail follow-up action now closes the interpretation drawer before dispatching Gmail-session open behavior

## Decision locks
- `Recent Jobs` remains the only prominent secondary production page in normal navigation.
- `Settings`, `Profile`, `Power Tools`, and `Extension Lab` remain reachable through direct hashes and `More`, but they are intentionally treated as secondary/operator surfaces.
- Same-tab drawers and bounded sheets remain the default browser-native secondary-surface model.
- The browser app keeps `ui=legacy` only as a temporary internal fallback while the aligned shell is reviewed and accepted.

## Stage result
- The staged browser-to-Qt UX alignment program is complete at the implementation level.
- No further stage token is required.
- The next concrete step is human review, PR review, or publish flow rather than another staged implementation wave.
