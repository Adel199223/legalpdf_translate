# Stage 0 ExecPlan: Beginner-First Primary-Flow UX Baseline

## 1. Title
Roadmap activation and deterministic baseline evidence.

## 2. Goal and non-goals
- Goal:
  - activate the roadmap and resume anchor for this UX-cleanup stream
  - establish deterministic baseline renders before user-facing UI changes start
  - add render-review coverage for the interpretation Save/Edit Job Log dialog
- Non-goals:
  - no declutter primitives yet
  - no user-facing layout or copy changes yet
  - no persistence or workflow changes

## 3. Scope (in/out)
- In:
  - roadmap tracker and resume-anchor activation
  - Stage 0 ExecPlan creation
  - render-review tooling/test updates for the interpretation Job Log dialog sample
  - baseline render artifact generation
- Out:
  - any UI decluttering implementation
  - settings/admin surfaces
  - docs sync beyond roadmap/resume artifacts required for continuity

## 4. Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- `docs/assistant/SESSION_RESUME.md`
  - roadmap anchor flips from dormant to active for this worktree
- `tooling/qt_render_review.py`
  - new deterministic interpretation Job Log dialog sample
- `tests/test_qt_render_review.py`
  - sample coverage for the new render artifact

## 6. File-by-file implementation steps
- `docs/assistant/exec_plans/completed/2026-03-12_beginner_first_primary_flow_ux_roadmap.md`
  - create the active roadmap tracker
- `docs/assistant/exec_plans/completed/2026-03-12_beginner_first_primary_flow_ux_stage0_baseline.md`
  - record Stage 0 implementation scope and boundary
- `docs/assistant/SESSION_RESUME.md`
  - point to the active roadmap tracker and Stage 0 ExecPlan
- `tooling/qt_render_review.py`
  - add `render_joblog_interpretation_dialog_sample(...)`
  - include it in the default render batch output
- `tests/test_qt_render_review.py`
  - assert the new sample writes PNG/JSON metadata

## 7. Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py`
- `.\\.venv311\\Scripts\\python.exe tooling/qt_render_review.py --outdir tmp/stage0_beginner_first_baseline`
- Acceptance:
  - roadmap files resolve from `SESSION_RESUME.md`
  - the new interpretation Job Log sample renders deterministically
  - baseline artifacts exist for main shell, Gmail review, honorarios export, and interpretation Job Log dialog
  - no user-facing UI behavior changes land in Stage 0

## 8. Rollout and fallback
- Stop after Stage 0 and publish a stage packet.
- If the new render sample is unstable, keep the roadmap artifacts and fix determinism before any UI cleanup starts.

## 9. Risks and mitigations
- Risk: Stage 0 accidentally leaks user-facing UI tweaks while wiring the render sample.
  - Mitigation: limit runtime changes to synthetic render-review inputs only.
- Risk: roadmap anchor points at the wrong worktree.
  - Mitigation: lock the exact worktree path, branch, and active artifact filenames in `SESSION_RESUME.md`.
- Risk: render output depends on live machine geometry.
  - Mitigation: reuse the existing deterministic screen-geometry override path.

## 10. Assumptions/defaults
- Stage 0 owns only governance plus render-baseline setup.
- The interpretation dialog sample uses edit-mode Save/Edit Job Log state because that is the closest match to the target cleanup surface.

## 11. Current status
- Completed.
- Stage completion packet is ready for publication.
- The next step is blocked on the exact user continuation token `NEXT_STAGE_1`.

## 12. Executed validations and outcomes
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py`
  - PASS (`12 passed`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_app_state.py -k "test_edit_joblog_dialog_keeps_header_autofill_available_without_pdf_path or test_edit_joblog_dialog_interpretation_mode_hides_translation_only_fields or test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance or test_edit_joblog_dialog_interpretation_service_city_switches_to_saved_distance or test_save_to_joblog_dialog_small_screen_uses_scrollable_body_and_collapsed_sections"`
  - PASS (`5 passed, 163 deselected`)
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py`
  - FAIL due existing Windows Qt access-violation in `tests/test_qt_app_state.py::test_save_to_joblog_dialog_return_key_save_shortcut_is_stable_across_repeated_runs`
- `& 'C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe' tooling/qt_render_review.py --outdir tmp/stage0_beginner_first_baseline --include-gmail-review`
  - PASS
  - Baseline artifacts written under `tmp/stage0_beginner_first_baseline/`
