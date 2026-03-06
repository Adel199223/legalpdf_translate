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
python -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py
```

## Targeted Tests
- `tests/test_qt_render_review.py`
- `tests/test_qt_app_state.py`

## Failure Modes and Fallback Steps
- Desktop shell still drifts from the reference: stop and fail the current region instead of advancing with “close enough” notes.
- Desktop exactness fixes break medium/narrow layouts: keep desktop exact authoritative, then reflow responsive layout without weakening the desktop contract.
- GUI launch is ambiguous on Windows: use `python -m legalpdf_translate.qt_app` for attached launch or `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'` for detached launch.

## Handoff Checklist
1. Freeze one desktop validation size and do not change it mid-pass.
2. Review these regions independently: sidebar, hero row, setup card, output card, footer rail, overflow menu, background scene.
3. Mark each region pass/fail. Do not use vague acceptance language.
4. Treat desktop exact as the source of truth; medium/narrow are stability checks only.
5. Attach deterministic render outputs for wide, medium, and narrow sizes.
