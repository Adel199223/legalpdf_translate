# Desktop Stability For Honorarios + Qt Reliability

## Goal and non-goals
- Goal: stabilize the honorarios export path so Word PDF failures do not freeze the Qt UI, surface structured diagnostics, and leave a usable local DOCX when PDF export fails.
- Goal: execute this as staged work with hard stop points.
- Non-goal: redesign the app or complete the later visual/theme cleanup in the same stage.
- Non-goal: add a second PDF backend in Stage 1.

## Stage status
- Stage 1: completed
- Stage 2: completed
- Stage 3: completed
- Stage 4: completed

## Scope (in/out)
- In scope for Stage 1:
  - async Word PDF export for honorarios
  - structured Word/PDF failure codes and elapsed timing
  - concise PDF failure dialog text with expandable details
  - Stage 1 tests and validations
- In scope for Stage 2:
  - a single deterministic export-result flow after honorarios DOCX/PDF generation
  - manual fallback actions for partial success: open DOCX, open folder, retry PDF, select an existing PDF
  - caller-side suppression of duplicate Gmail missing-PDF warnings when the export dialog already explained the failure
- In scope for Stage 3:
  - reduce the glow/shadow strengths that soften the futuristic theme
  - make theme-effect application deterministic and idempotent across repeated theme reloads
  - strengthen disabled/modal contrast without redesigning the shell
  - extend `tooling/qt_render_review.py` to cover honorarios/export-error states under both themes
- In scope for Stage 4:
  - harden the Qt shortcut/focus harness around the save-to-Job-Log Return/Enter path
  - add repeated-run coverage for the focus-sensitive save-dialog shortcut flow
  - clean up leaked Qt popups/windows between tests so shortcut tests do not inherit stale modal state
  - audit the remaining focus-sensitive honorarios/export tests for the same harness assumptions
- Deferred to later stages:
  - none within this staged stabilization plan

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/honorarios-pdf-stage1`
- Base branch: `main`
- Base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`
- Canonical build status: noncanonical branch worktree build under active staged stabilization

## Interfaces/types/contracts affected
- `WordAutomationResult` gains structured PDF diagnostic fields.
- `word_automation.py` adds a lightweight PDF preflight entrypoint.
- `QtHonorariosExportDialog` gains async PDF-export state fields while preserving current `saved_path`, `saved_pdf_path`, and `pdf_export_error` compatibility.
- `QtHonorariosExportDialog` now owns the post-export result flow and can accept a validated user-selected replacement PDF.
- `qt_gui.worker` gains a dedicated honorarios PDF export worker/result surface.
- `qt_gui.styles` now exposes theme effect specs in addition to effect colors.

## File-by-file implementation steps
- `src/legalpdf_translate/word_automation.py`
  - classify PDF failures
  - add preflight probe
  - record elapsed time and sanitized details
- `src/legalpdf_translate/qt_gui/worker.py`
  - add a dedicated PDF export worker/result type
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - move honorarios PDF export off the GUI thread
  - expose structured dialog result fields
  - replace raw PowerShell dump warnings with concise text plus details
  - add the single export-result flow with retry/manual-PDF recovery
  - stop stacking duplicate Gmail missing-PDF warnings after the export dialog already handled the partial-success state
- `src/legalpdf_translate/qt_gui/app_window.py`
  - suppress duplicate manual-interpretation Gmail missing-PDF warnings when the export dialog already explained the block
- `src/legalpdf_translate/qt_gui/styles.py`
  - lower blur/alpha effect strengths
  - improve disabled/modal contrast
  - reuse widget effect objects by role instead of recreating them on every theme reapply
- `tooling/qt_render_review.py`
  - add theme-aware render runs
  - add deterministic honorarios export, PDF-failure, and Gmail PDF-unavailable samples
- `tests/test_word_automation.py`
  - cover failure classification, preflight, and sanitized details
- `tests/test_honorarios_docx.py`
  - cover async dialog state/result behavior and structured failure fields
  - cover retry/manual-PDF partial-success paths
- `tests/test_qt_app_state.py`
  - cover no-duplicate-warning behavior for manual interpretation and Job Log interpretation exports
  - cover deterministic theme-effect reuse on repeated reloads
- `tests/test_qt_render_review.py`
  - cover new render states and theme resolution
- `tests/conftest.py`
  - add global Qt cleanup between tests so leaked popups/windows do not contaminate focus-sensitive cases

## Tests and acceptance criteria
- Focused tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py tests/test_qt_main_smoke.py`
  - `.\.venv311\Scripts\python.exe -m compileall src tests tooling`
- Stage 4 focused tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py -k "save_to_joblog_dialog_return_key or delete_key_removes_selected_rows"`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_qt_app_state.py`
- Full regression after focused pass:
  - `.\.venv311\Scripts\python.exe -m pytest -q`
- Acceptance:
  - generating honorarios no longer blocks the UI thread during PDF export
  - the dialog still returns a saved DOCX on PDF failure
  - PDF failures expose failure code/message/details without dumping the raw command in the main warning body
  - partial-success export no longer cascades into a second generic Gmail PDF-unavailable warning
  - the user can retry PDF export or select an existing validated PDF without regenerating the DOCX
  - repeated theme reloads do not create fresh shell-effect objects or drift the effect profile
  - render review outputs exist for dashboard, honorarios export, honorarios PDF-failure, and Gmail PDF-unavailable states under both themes
  - the save-to-Job-Log Return shortcut remains stable across repeated dialog runs without relying on a default button
  - leaked Qt popup/modal state is cleaned between tests so focus-sensitive coverage does not flake due to prior dialogs

## Executed validations and outcomes
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_word_automation.py tests/test_honorarios_docx.py` -> passed (`67 passed`)
- `.\.venv311\Scripts\python.exe -m compileall src tests` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q` -> passed (`916 passed`)
- `dart run tooling/validate_agent_docs.dart` -> passed
- `dart run tooling/validate_workspace_hygiene.dart` -> passed
- Host probe: `probe_word_pdf_export_support()` -> passed on this machine
- Host probe: temporary DOCX -> PDF export via `export_docx_to_pdf_in_word(...)` -> passed on this machine
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_qt_app_state.py` -> passed (`224 passed`)
- `.\.venv311\Scripts\python.exe -m compileall src tests` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q` -> passed (`920 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py tests/test_qt_main_smoke.py` -> passed (`182 passed`)
- `.\.venv311\Scripts\python.exe -m compileall src tests tooling` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q` -> passed (`924 passed`)
- `.\.venv311\Scripts\python.exe tooling/qt_render_review.py --outdir tmp/qt_ui_review_stage3 --profiles wide --themes dark_futuristic dark_simple` -> passed and wrote Stage 3 render artifacts
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py -k "save_to_joblog_dialog_return_key or delete_key_removes_selected_rows"` -> passed (`3 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_qt_app_state.py` -> passed (`225 passed`)
- `.\.venv311\Scripts\python.exe -m compileall src tests tooling` -> passed
- `.\.venv311\Scripts\python.exe -m pytest -q` -> passed (`925 passed`)
- `dart run tooling/validate_workspace_hygiene.dart` -> passed

## Rollout and fallback
- Stage 1 stops after async export + structured failure reporting.
- Stage 2 stops after the calmer export-result flow, retry/manual-PDF fallback, and duplicate-warning suppression.
- Stage 3 stops after the visual stability pass and render-review expansion.
- If Word still fails on this host, keep the DOCX local fallback, allow the user to attach an existing validated PDF, and keep Gmail blocked until a PDF exists.
- Stage 4 completes the staged stabilization plan.

## Risks and mitigations
- Risk: worker-thread ownership leaks in modal dialogs.
  - Mitigation: explicit thread cleanup and close blocking while export is in flight.
- Risk: existing callers depend on old dialog field names.
  - Mitigation: keep compatibility aliases alongside new fields.
- Risk: flaky Qt tests around nested dialog event loops.
  - Mitigation: keep Stage 1 tests focused and leave harness hardening to Stage 4.

## Assumptions/defaults
- DOCX generation remains synchronous because it is fast enough compared with Word PDF export.
- Word COM launch failure on this host is a real environment/runtime issue, not a fake-test artifact.
- Later stages will clean up duplicate modal warnings and visual drift; Stage 1 will not broaden into those changes.
- Later stages will still cover Qt harness hardening and repeated-run shortcut reliability; Stage 3 intentionally did not broaden into those areas.
- The staged stabilization plan is complete; follow-on work should use normal ExecPlan flow instead of stage tokens unless a new staged plan is explicitly requested.
