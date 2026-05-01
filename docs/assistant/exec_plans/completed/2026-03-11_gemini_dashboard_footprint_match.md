# Gemini Dashboard Footprint Match

## Goal and non-goals
- Goal:
  - Match the user-provided Gemini dashboard footprint more literally by shrinking and centering the outer dashboard rectangle at desktop sizes while preserving the current Qt shell behavior.
  - Make the two inner cards follow that smaller outer shell with an explicit desktop geometry contract.
  - Add deterministic render metadata and tests so the outer-shell footprint becomes regression-safe.
- Non-goals:
  - No sidebar, hero typography, background scene, or overflow-menu redesign.
  - No workflow, runtime, schema, or CLI behavior changes.
  - No broad assistant-doc rewrite in this pass.

## Scope (in/out)
- In:
  - Desktop `dashboard_frame` centering and width clamp.
  - Desktop setup/progress card spacing and ratio retune.
  - Render-review metadata for dashboard-shell geometry.
  - Qt tests that lock the new desktop footprint contract.
- Out:
  - Color, glow, and paint-scene restyling unless a geometry change causes a concrete clipping defect.
  - Responsive breakpoint redesign.

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_dashboard_geometry_gemini`
- branch name: `codex/dashboard-geometry-gemini`
- base branch: `main`
- base SHA: `ce39be35adc7c4806479cc101552e6b80cb3f65c`
- target integration branch: `main`
- canonical build status or intended noncanonical override: noncanonical implementation worktree, based on the approved `main` floor declared in `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- No user-facing interface changes.
- `tooling/qt_render_review.py` JSON metadata gains:
  - `dashboard_frame_width`
  - `dashboard_frame_x`
  - `dashboard_frame_y`
  - `footer_card_width`
- Desktop shell geometry contract becomes explicit:
  - `desktop_exact` dashboard frame width `1200`
  - `desktop_compact` dashboard frame width `1100` unless available width is smaller
  - `stacked_compact` keeps the existing full-width stacked behavior

## File-by-file implementation steps
1. Update `src/legalpdf_translate/qt_gui/app_window.py`:
   - wrap `dashboard_frame` in a centered row instead of letting it inherit the full `content_card` width
   - add an explicit dashboard-footprint sizing path inside `_apply_responsive_layout()`
   - keep the hero row and `content_card` width logic unchanged
   - retune desktop exact body spacing to `18`, setup/progress stretch to `7:6`, and hero-to-dashboard gap to `30` / `22` / `16` by layout mode
2. Update `tooling/qt_render_review.py` to emit the new dashboard-shell metadata fields from the live widget geometry.
3. Update `tests/test_qt_app_state.py` to assert the centered narrower dashboard frame and preserved two-column desktop body.
4. Update `tests/test_qt_render_review.py` to assert the `wide` render emits the new dashboard metadata contract.

## Tests and acceptance criteria
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py tests/test_qt_render_review.py`
- `.\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review --preview reference_sample --profiles wide medium narrow`
- Acceptance:
  - `wide`: dashboard rectangle is centered and materially narrower than the current near-full-width shell
  - `wide`: setup and progress cards remain side-by-side with setup wider than progress
  - `wide`: footer rail is inset under the narrower outer shell
  - `medium`: still two-column
  - `narrow`: still stacked with the existing compact footer flow

## Rollout and fallback
- Rollout:
  - geometry-only pass in the dedicated worktree
  - targeted Qt tests and deterministic render review before any wider regression run
- Fallback:
  - if the narrower desktop shell causes concrete field clipping, loosen only the dashboard-footprint clamp enough to preserve readability instead of reverting to the current full-width shell

## Risks and mitigations
- Risk: the narrower outer shell causes field chrome clipping in the setup card.
  - Mitigation: keep `content_card` width unchanged and adjust only the dashboard shell plus its internal spacing.
- Risk: desktop centering breaks medium or narrow responsive behavior.
  - Mitigation: apply the clamp only in desktop modes and preserve the current stacked compact path.
- Risk: screenshot review remains subjective.
  - Mitigation: expose dashboard-shell geometry in render metadata and assert it in tests.

## Assumptions/defaults
- The Gemini screenshot pasted in the conversation is the only visual authority for this pass.
- The deterministic `wide` render (`1800x1000`) remains the desktop exact validation size.
- Assistant docs stay untouched unless the geometry contract itself needs to be documented after the code change lands.

## Closeout
- Status: completed
- Implemented:
  - centered desktop `DashboardFrame` with explicit width contracts for `desktop_exact` and `desktop_compact`
  - state-driven source-file support cluster that hides the page-count chrome until a real source is selected
  - deterministic render metadata for dashboard-shell geometry
  - Qt regression coverage for the centered shell and source-field behavior
- Validations executed:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py tests/test_qt_render_review.py` -> `160 passed`
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review --preview reference_sample --profiles wide medium narrow` -> `wide/medium/narrow` renders regenerated with the new dashboard geometry metadata
