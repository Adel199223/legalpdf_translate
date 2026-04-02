# Stage 5: Publish Blocker Resolution

## Goal and non-goals
- Goal: resolve the explicit publish blocker identified in Stage 4 by restoring the supported Qt PyInstaller spec and removing the approved scratch patch artifact.
- Goal: verify that the Qt packaging/test contract is healthy again.
- Non-goal: perform commit, push, PR, or merge work.
- Non-goal: change the Gmail finalization/report or residual tooling implementation scope.

## Scope (in/out)
- In scope:
  - `build/pyinstaller_qt.spec` restoration
  - approved scratch artifact removal
  - Qt packaging/build-script regression tests
- Out of scope:
  - broader product validation already covered in earlier stages
  - source-control staging or commit creation
  - any networked publish activity

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/gmail-finalization-report-success`
- base branch: `main`
- base SHA: `18be21ec2d2c632f12ec5da3d2e5351aa5644488`
- target integration branch: `main`
- canonical build status: noncanonical feature branch with pending local changes, still above the approved-base floor

## Interfaces/types/contracts affected
- Restored supported Windows fallback-shell packaging contract:
  - `scripts/build_qt.ps1` again has its referenced spec file available at `build/pyinstaller_qt.spec`
  - `tests/test_pyinstaller_specs.py` can assert the spec contents again
- Removed approved scratch artifact:
  - `.codex_tmp_browser_qt_parity.patch`

## File-by-file implementation steps
1. Confirm from current repo references that `build/pyinstaller_qt.spec` is still a live contract, not dead code.
2. Restore `build/pyinstaller_qt.spec` from the branch tip content expected by current tests/scripts.
3. Remove `.codex_tmp_browser_qt_parity.patch` after explicit user approval.
4. Re-run the PyInstaller spec and Windows shortcut script tests.
5. Record the resolved blocker state for the next commit/publish-prep stage.

## Tests and acceptance criteria
- Validation run:
  - `.venv311\Scripts\python.exe -m pytest -q tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py` -> PASS (`13 passed`)
- Hygiene checks:
  - `Test-Path .codex_tmp_browser_qt_parity.patch` -> `False`
  - `git status --short --branch` no longer shows the scratch patch artifact and no longer shows the spec as deleted

## Rollout and fallback
- If future work intentionally removes Qt packaging support, it must update `scripts/build_qt.ps1`, `tests/test_pyinstaller_specs.py`, and the relevant docs in the same pass rather than deleting only the spec file.
- Until then, keep the restored spec as part of the supported fallback-shell contract.

## Risks and mitigations
- Risk: restoring the spec could accidentally diverge from current branch expectations.
  - Mitigation: restored the exact current-branch tip content and validated against the packaging/script tests.
- Risk: scratch artifact removal could delete something still needed.
  - Mitigation: removal happened only after explicit user approval and after confirming it was an untracked patch snapshot.

## Assumptions/defaults
- Qt remains a supported fallback shell and therefore still needs a valid Windows packaging path.
- The untracked patch file was scratch output, not canonical repo content.

## Outcome
- Stage 5 completed on `2026-04-02`.
- `build/pyinstaller_qt.spec` was restored and the Qt packaging regression slice is green again.
- `.codex_tmp_browser_qt_parity.patch` was removed.
- The specific publish blocker from Stage 4 is resolved; the branch can now move to commit/publish preparation if desired.
