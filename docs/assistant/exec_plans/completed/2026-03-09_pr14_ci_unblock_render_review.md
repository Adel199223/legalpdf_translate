# PR 14 CI Unblock and Publish Cleanup

## 1. Title
Unblock PR 14 by stabilizing Qt render-review captures, then merge and clean the thread

## 2. Goal and non-goals
- Goal: fix the deterministic Qt render-review harness so GitHub Actions and local runs produce the same `wide` layout metadata.
- Goal: republish PR `#14`, wait for green checks, merge it, and leave both the local thread and remote branch clean.
- Non-goal: redesign runtime Qt layout thresholds or change user-facing adaptive behavior.
- Non-goal: change the render contract to accept weaker or multiple layout-mode results.

## 3. Scope (in/out)
- In scope:
  - tooling-only render-review determinism fix
  - targeted regression coverage for the tooling contract
  - validation reruns
  - one follow-up commit, push, PR merge, and thread cleanup
- Out of scope:
  - any product layout-threshold retuning in `app_window.py`
  - changes to `window_adaptive.py`
  - unrelated branch/worktree cleanup outside this feature thread

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/joblog-inline-editing`
- Base branch: `main`
- Base SHA: `674098c5aec8a711368b3653c6a4364fb7b01a8c`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; approved base floor satisfied by `docs/assistant/runtime/CANONICAL_BUILD.json`

## 5. Interfaces/types/contracts affected
- Internal tooling contract only:
  - `tooling/qt_render_review.py` must render against a fixed virtual screen budget during capture.
  - `tests/test_qt_render_review.py` must keep `wide` locked to `desktop_exact`.
- No public API, settings schema, or runtime UI contract changes.

## 6. File-by-file implementation steps
- Update `tooling/qt_render_review.py` to temporarily override `legalpdf_translate.qt_gui.window_adaptive.available_screen_geometry` during render-review captures.
- Update `tests/test_qt_render_review.py` with regression coverage proving the render harness remains deterministic even if the live screen geometry would otherwise clamp the window.
- Record executed validations and merge/cleanup outcomes in this plan, then move it to `completed/` after merge.

## 7. Tests and acceptance criteria
- Local:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py tests/test_honorarios_docx.py tests/test_qt_review_queue_panel.py`
  - `./.venv311/Scripts/python.exe -m pytest -q`
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run test/tooling/validate_agent_docs_test.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`
- Acceptance:
  - `tests/test_qt_render_review.py` passes locally
  - GitHub `CI / test (3.11)` passes on PR `#14`
  - PR `#14` merges into `main`
  - remote branch is deleted
  - local branch is deleted after syncing `main`
  - `tmp_ui_review/` is removed and `git status --short --branch` is clean on `main`

## 8. Rollout and fallback
- Roll out as a single follow-up commit on the existing feature branch because the PR is already open.
- If the tooling-only override is insufficient, stop before merge and inspect whether a second deterministic-capture fix is needed; do not relax the render assertion as fallback.

## 9. Risks and mitigations
- Risk: the harness override leaks into runtime behavior.
  - Mitigation: scope the override to a context manager used only during render capture.
- Risk: local tests pass but CI still fails due to another render path.
  - Mitigation: run the full suite locally after targeted render tests before repushing.
- Risk: cleanup removes artifacts outside this thread.
  - Mitigation: restrict deletion to `tmp_ui_review/` and the merged feature branch only.

## 10. Assumptions/defaults
- `wide` should remain `desktop_exact`; the CI failure is a determinism bug, not a product change.
- “Both local and live repos clean” applies to this feature thread only.

## 11. Executed validations and outcomes
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_render_review.py`
  - Passed: `6 passed in 2.28s`.
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_render_review.py tests/test_qt_app_state.py tests/test_honorarios_docx.py tests/test_qt_review_queue_panel.py`
  - Passed: `159 passed in 13.30s`.
- `./.venv311/Scripts/python.exe -m pytest -q`
  - Passed: `803 passed in 35.05s`.
- `dart run tooling/validate_agent_docs.dart`
  - Passed.
- `dart run test/tooling/validate_agent_docs_test.dart`
  - Passed: `53 cases`.
- `dart run tooling/validate_workspace_hygiene.dart`
  - Passed.
- `git commit -m "fix(ci): stabilize qt render review profiles"`
  - Passed: follow-up commit `e705c20`.
- `git push origin feat/joblog-inline-editing`
  - Passed: PR `#14` updated to `e705c2097584af75127c5992011cfbafc3ac21d6`.
- GitHub Actions rerun for PR `#14`
  - Passed:
    - `CI / test (3.11)` pull_request run `22859381682`
    - `CI / test (3.11)` push run `22859378910`
    - both `docs_tooling_contracts` checks
- `gh pr merge 14 --merge --delete-branch`
  - Passed: PR `#14` merged into `main` at merge commit `cccf13e31a4db3ed4e0d7fe931c645fd8d55d47c`.
- `git fetch --prune origin`
  - Passed: remote branch `origin/feat/joblog-inline-editing` removed.
- Local cleanup
  - Passed: repository returned to `main`, local feature branch no longer present, `tmp_ui_review/` removed, and `git status --short --branch` is clean.
