# Multi-Window Translation Workspaces

## Goal and non-goals
- Goal:
  - Add true multi-window Qt workspaces under one `QApplication`.
  - Keep run execution window-local while centralizing window creation and collision arbitration.
  - Complete Stage 1 in this pass: controller bootstrap, workspace identity, new-window entrypoints, and run-target reservation blocking.
- Non-goals:
  - No tabbed or MDI shell.
  - No run/artifact naming migration.
  - No CLI changes.
  - No Stage 2 Gmail-controller routing or Stage 3 session-local form persistence in this pass.

## Scope (in/out)
- In:
  - app-level window controller
  - `qt_app.run()` controller ownership of top-level workspaces
  - `File > New Window`, `Ctrl+Shift+N`, and overflow/menu entrypoints
  - workspace numbering/title refresh
  - duplicate run-target blocking for translate, analyze, rebuild, and queue
  - Stage 1 tests and validation
- Out:
  - controller-owned Gmail bridge lifecycle
  - per-window session-local draft state persistence split
  - docs sync beyond this ExecPlan unless requested after implementation

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `f264b6f6eae179c10efcc23710465852b44dfb8d`
- Target integration branch: `feat/ai-docs-bootstrap`
- Canonical build status: canonical worktree and canonical branch per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- New controller contract:
  - create/open/focus workspace windows
  - assign workspace indices
  - track last active workspace
  - reserve/release run targets keyed by resolved run dir
- `QtMainWindow` additive constructor contract:
  - optional `controller`
  - optional `workspace_index`
- `QtMainWindow` additive hooks:
  - title refresh using workspace identity
  - controller callback for `New Window`
  - controller-aware reservation acquire/release around run lifecycles

## File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/window_controller.py`
  - add window registry, index assignment, last-active tracking, focus helper, and run-target reservation map
- `src/legalpdf_translate/qt_app.py`
  - instantiate the controller and initial workspace instead of a single raw window
- `src/legalpdf_translate/qt_gui/app_window.py`
  - add controller/workspace constructor args
  - add `New Window` action and shortcut
  - refresh titles with workspace identity
  - reserve/release run targets for translate, analyze, rebuild, and queue
  - keep `New Run` semantics scoped to the current workspace only
- `tests/test_qt_main_smoke.py`
  - cover controller-based bootstrap and initial workspace creation
- `tests/test_qt_app_state.py`
  - cover menu/shortcut surface, titles, reservation conflicts, and release behavior
- `tests/test_qt_window_controller.py`
  - add focused controller tests if needed for cleaner coverage

## Tests and acceptance criteria
- Starting the app creates a controller-owned initial workspace and keeps the app alive until the last workspace closes.
- `New Window` opens a blank workspace even while another workspace is busy.
- Multiple windows have distinguishable titles/workspace numbers.
- Starting a run is blocked when another workspace already owns the same resolved run dir.
- Queue starts are blocked if any manifest job collides with a reserved run dir.
- Reservation ownership is released on completion, failure, or cancel cleanup.

## Rollout and fallback
- Stage 1 ships behind the existing window model with no artifact migration.
- Standalone `QtMainWindow()` construction remains supported for tests/tooling without requiring the controller.
- Stage 2 and Stage 3 remain follow-up stages gated by continuation tokens.

## Risks and mitigations
- Risk: reservation cleanup leaks after worker teardown.
  - Mitigation: centralize release in cleanup/finish/error paths and cover with tests.
- Risk: new-window actions become disabled by the current busy-state logic.
  - Mitigation: keep `New Window` controller action independent from per-window busy gating and test it explicitly.
- Risk: direct `QtMainWindow()` tests break.
  - Mitigation: make controller integration optional and preserve current defaults.

## Assumptions/defaults
- New workspaces open blank only.
- Duplicate targets are blocked, not auto-isolated.
- Stage boundary after Stage 1 requires exact continuation token `NEXT_STAGE_2`.

## Validation log
- Implemented Stage 1 files:
  - `src/legalpdf_translate/qt_gui/window_controller.py`
    - added the workspace controller, last-active tracking, focus helper, and run-target reservation lifecycle
  - `src/legalpdf_translate/qt_app.py`
    - switched app startup to controller-owned initial workspace bootstrap
  - `src/legalpdf_translate/qt_gui/app_window.py`
    - added optional controller/workspace wiring, workspace title refresh, `New Window` actions, activation tracking, and reservation acquire/release for translate, analyze, rebuild, and queue
  - `tests/test_qt_main_smoke.py`
    - updated startup coverage for controller bootstrap
  - `tests/test_qt_app_state.py`
    - added Stage 1 coverage for workspace titles, last-active tracking, busy-state `New Window`, and reservation conflicts
- Executed Stage 1 validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py`
    - result: `108 passed in 10.76s`
  - `python3 -m compileall src tests`
    - result: pass
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
- Stage 1 boundary status:
  - completed and ready for handoff
  - exact continuation token required for the next pass: `NEXT_STAGE_2`

## Stage 2 execution log
- Implemented Stage 2 files:
  - `src/legalpdf_translate/qt_gui/window_controller.py`
    - added controller-owned Gmail intake bridge lifecycle, main-thread intake routing, shared-settings propagation, and last-window bridge cleanup
  - `src/legalpdf_translate/qt_gui/app_window.py`
    - added `accept_gmail_intake`, `is_workspace_reusable_for_gmail`, active-bridge resolution, shared-settings refresh without draft-field overwrite, and controller-aware Gmail attention/metadata wiring
  - `tests/test_qt_app_state.py`
    - added Stage 2 coverage for pristine-workspace reuse, occupied-workspace auto-window routing, and controller bridge reconfiguration without overwriting another workspace's draft form fields
- Executed Stage 2 validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py`
    - result: `111 passed in 9.42s`
  - `python3 -m compileall src tests`
    - result: pass
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
- Stage 2 boundary status:
  - completed and ready for handoff
  - exact continuation token required for the next pass: `NEXT_STAGE_3`

## Stage 3 execution log
- Implemented Stage 3 files:
  - `src/legalpdf_translate/qt_gui/app_window.py`
    - stopped auto-saving draft form edits
    - limited committed persistence to explicit launch fields only on task starts
    - stopped restoring queue draft inputs from shared settings
    - kept settings-dialog updates out of the live workspace form controls
  - `src/legalpdf_translate/qt_gui/window_controller.py`
    - filtered shared-settings propagation so settings-dialog updates no longer leak launch-field state across workspaces
  - `tests/test_qt_app_state.py`
    - added Stage 3 coverage for queue draft non-restore, current-window draft preservation across settings saves, close-without-persist, and explicit-commit-only draft propagation to newly opened workspaces
- Executed Stage 3 validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py`
    - result: `115 passed in 8.16s`
  - `python3 -m compileall src tests`
    - result: pass
  - `dart run tooling/validate_agent_docs.dart`
    - result: `PASS: agent docs validation succeeded.`
- Stage 3 completion status:
  - completed
  - multi-window translation workspace plan implemented through the final staged scope
