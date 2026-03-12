# Gemini Main-Shell Color and Effects Pass

## Goal and non-goals
- Goal: retune the Qt main-shell `dark_futuristic` theme so the main app window reads much closer to the Gemini reference image through stronger cyan glass, warmer top chrome, brighter glow, and more atmospheric background lighting.
- Non-goals: no dialog/tool-window redesign, no new theme mode, no dashboard geometry redesign, no workflow or feature changes.

## Scope (in/out)
- In: `qt_gui/styles.py`, `qt_gui/app_window.py`, deterministic render-review metadata/tests, and this ExecPlan lifecycle.
- Out: `dark_simple` redesign, dialog-specific styling work, commit/push/publish steps, and unrelated worktrees.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gemini_shell_visual_pass`
- Branch name: `codex/gemini-shell-visual-pass`
- Base branch: `main`
- Base SHA: `167679778b1f3f60a369ffb4c6f87d7b76b84117`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree that contains the canonical build floor from `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- `dark_futuristic` palette/effect tokens in `qt_gui/styles.py`
- theme-aware shell effect reapply path in `QtMainWindow`
- render-review JSON metadata gains named color-probe fields for the `wide` shell
- Qt visual regression tests gain relational assertions for shell color/effect behavior

## File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/styles.py`
  - retune `dark_futuristic` palette toward the Gemini reference
  - add explicit theme effect tokens for shell shadow/glow colors
  - update helpers so shell effects can be applied from theme-aware tokens instead of fixed hard-coded colors
- `src/legalpdf_translate/qt_gui/app_window.py`
  - add `_apply_theme_effects()` for shell widgets and call it after UI construction plus on shared theme reload
  - retune `_FuturisticCanvas.paintEvent()` for warmer top chrome, larger left dome glow, brighter divider/circuit treatment, and geometry-aware halo behind `DashboardFrame` and `ActionRail`
- `tooling/qt_render_review.py`
  - keep `reference_sample` deterministic
  - add named shell color probes from the rendered image
  - keep `wide` in `desktop_exact`
- `tests/test_qt_render_review.py`
  - assert relational visual contracts on the new shell color probes
- `tests/test_qt_app_state.py`
  - assert theme reload reapplies shell graphics-effect colors
- `tests/test_qt_main_smoke.py`
  - update only if needed for any new style/helper contract

## Tests and acceptance criteria
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py tests/test_qt_render_review.py`
- `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review --preview reference_sample --profiles wide medium narrow`
- Manual acceptance:
  - warm smoky menu bar
  - larger atmospheric left glow
  - visible title/dashboard bloom
  - glass-like setup/output cards
  - luminous footer slab
  - intentionally lit cyan primary button
  - intentionally lit salmon/red cancel button
  - overflow menu matches the same shell language

## Rollout and fallback
- Rollout is limited to the existing `dark_futuristic` theme.
- Fallback is to locally reduce effect intensity while preserving the new theme-aware effect plumbing if any render or readability regression appears.

## Risks and mitigations
- Risk: stronger glow can clip or muddy contrast.
  - Mitigation: keep layout geometry stable, sample deterministic renders, and use relational probe assertions instead of subjective-only review.
- Risk: theme switching leaves stale graphics effects.
  - Mitigation: centralize shell effect reapplication in `_apply_theme_effects()` and test `reload_shared_settings()`.
- Risk: stylesheet-only tuning misses the reference.
  - Mitigation: split work between stylesheet palette, effect tokens, and `_FuturisticCanvas` paint changes.

## Assumptions/defaults
- The Gemini screenshot in this thread is the only visual authority for this pass.
- `dark_simple` stays available as the lower-noise variant and does not need parity tuning beyond staying visually coherent after shared helper changes.
- Existing dashboard footprint/geometry contracts remain unchanged.

## Stage notes
- Stage 1 target: create worktree, create ExecPlan, capture baseline deterministic render.
- Stage 2 target: implement palette/effect/canvas changes and validation coverage.
- Stage 3 target: final validation, live review notes, and ExecPlan closeout updates.

## Stage 1 evidence
- Stage 1 status: complete on `2026-03-11`
- Baseline render command:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review_stage1_baseline --preview reference_sample --profiles wide`
- Baseline artifacts:
  - `tmp/qt_ui_review_stage1_baseline/wide.png`
  - `tmp/qt_ui_review_stage1_baseline/wide.json`
- Baseline geometry snapshot:
  - `layout_mode=desktop_exact`
  - `dashboard_frame_width=1200`
  - `dashboard_frame_x=280`
  - `setup_panel_width=608`
  - `progress_panel_width=500`
  - `footer_card_width=1126`

## Stage 2 evidence
- Stage 2 status: complete on `2026-03-11`
- Implemented shell-theme plumbing:
  - added theme-aware shell effect tokens and access in `qt_gui/styles.py`
  - added `_apply_theme_effects()` in `QtMainWindow`
  - reapply path now runs after UI build, after settings dialog changes, and after shared theme reload
  - `_FuturisticCanvas.paintEvent()` now adds a warm top band, larger left glow, stronger circuit/divider treatment, and geometry-aware backlights behind `DashboardFrame` and `ActionRail`
- Preview render command:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review_stage2_preview --preview reference_sample --profiles wide`
- Preview artifacts:
  - `tmp/qt_ui_review_stage2_preview/wide.png`
  - `tmp/qt_ui_review_stage2_preview/wide.json`
- Runtime theme-flip validation:
  - a direct Qt check confirmed `title_label.graphicsEffect().color()` and `footer_card.graphicsEffect().color()` change for `dark_simple` and restore for `dark_futuristic`
- Interim validation:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_main_smoke.py -q`

## Stage 3 evidence
- Stage 3 status: complete on `2026-03-11`
- Final deterministic validation:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py tests/test_qt_render_review.py`
  - Result: `165 passed`
- Final render-review command:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review --preview reference_sample --profiles wide medium narrow`
- Final render artifacts:
  - `tmp/qt_ui_review/wide.png`
  - `tmp/qt_ui_review/medium.png`
  - `tmp/qt_ui_review/narrow.png`
- Final probe snapshot (`wide`):
  - `menu_bar_mid_rgb=[52, 41, 33]`
  - `left_glow_rgb=[42, 101, 123]`
  - `left_glow_control_rgb=[24, 76, 105]`
  - `dashboard_border_rgb=[158, 251, 255]`
  - `dashboard_fill_rgb=[17, 61, 94]`
  - `footer_halo_rgb=[64, 135, 161]`
  - `footer_fill_rgb=[7, 31, 55]`
  - `primary_button_rgb=[87, 182, 206]`
  - `danger_button_rgb=[255, 154, 169]`
  - `sidebar_active_rgb=[19, 87, 113]`
  - `sidebar_inactive_rgb=[9, 32, 52]`
- Live-build verification:
  - launched the exact feature worktree build with `tooling/launch_qt_build.py`
  - captured the active Qt window to `C:\Users\FA507\AppData\Local\Temp\codex-shot-2026-03-11_23-10-38.png`
  - visual check confirmed the warm smoky top band, larger left-side glow, brighter cyan shell bloom, stronger footer slab halo, cyan primary button treatment, and salmon danger button treatment in the live app window
- Closeout notes:
  - the dashboard geometry contract from the previous pass remains intact (`wide` stays `desktop_exact` with a `1200px` dashboard shell)
  - the render-review harness now samples relational shell color probes so future regressions in glow/fill/border behavior are testable without brittle image hashes
