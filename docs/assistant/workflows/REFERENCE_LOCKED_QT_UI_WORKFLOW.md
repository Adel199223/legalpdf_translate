# REFERENCE_LOCKED_QT_UI_WORKFLOW

## What This Workflow Is For
Implementing screenshot-driven Qt desktop UI changes where the desktop app window must match a visual reference closely.

## Expected Outputs
- Fixed desktop validation size and explicit region-by-region acceptance contract.
- Deterministic render evidence for desktop, medium, and narrow window sizes.
- Clear separation between desktop exactness and responsive stability checks.

## When To Use
- A named image, mock, or generated reference is the acceptance target for the Qt dashboard shell.
- The task requires binary visual checks instead of approximate layout review.
- The task includes repeated desktop vs narrow-window tradeoffs and the desktop view must remain authoritative.

## What Not To Do
- Don't use this workflow when the task is primarily a translation/runtime behavior change.
- Instead use `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`.

## Primary Files
- `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`
- `docs/assistant/QT_UI_PLAYBOOK.md`
- `tooling/qt_render_review.py`
- `tooling/launch_qt_build.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- `src/legalpdf_translate/qt_gui/styles.py`

## Minimal Commands
PowerShell:
```powershell
python .\tooling\qt_render_review.py --outdir .\tmp_ui_review --preview reference_sample
python -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py
```
POSIX:
```bash
python ./tooling/qt_render_review.py --outdir ./tmp_ui_review --preview reference_sample
python ./tooling/launch_qt_build.py --worktree /abs/path/to/worktree --labels "qt-ui" --dry-run
python -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py
```

## Targeted Tests
- `tests/test_qt_render_review.py`
- `tests/test_qt_app_state.py`

## Failure Modes and Fallback Steps
- Desktop shell still drifts from the reference: stop and fail the current region instead of advancing with “close enough” notes.
- Desktop exactness fixes break medium/narrow layouts: keep desktop exact authoritative, then reflow responsive layout without weakening the desktop contract.
- GUI launch is ambiguous on Windows: use `tooling/launch_qt_build.py` so the build under test is emitted as a machine-readable identity packet instead of relying on an ad hoc launch command.
- A noncanonical worktree is accidentally used for review: relaunch the canonical build first; only use `--allow-noncanonical` when you are intentionally reviewing a source-only branch that still contains the approved-base floor.

## Handoff Checklist
1. Freeze one desktop validation size and do not change it mid-pass.
2. Review these regions independently: sidebar, hero row, setup card, output card, footer rail, overflow menu, background scene.
3. Mark each region pass/fail. Do not use vague acceptance language.
4. Treat desktop exact as the source of truth; medium/narrow are stability checks only.
5. Attach deterministic render outputs for wide, medium, and narrow sizes.
6. If multiple worktrees/builds can exist, launch the GUI through `tooling/launch_qt_build.py` and include:
   - worktree path
   - branch
   - HEAD SHA
   - canonical vs noncanonical status
   - distinguishing feature labels
7. Treat the canonical build declared in `docs/assistant/runtime/CANONICAL_BUILD.json` as the default review target unless an explicit noncanonical override is required.
8. Do not review a branch that is missing the approved-base floor; rebase/merge/transplant it first.
