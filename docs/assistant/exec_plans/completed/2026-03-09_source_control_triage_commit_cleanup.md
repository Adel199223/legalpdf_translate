# Source Control Triage and Commit Cleanup

## Goal and non-goals
- Goal:
  - Triage the pending Source Control tree into repo hygiene, the Gmail intake feature, and assistant execution records.
  - End with logical local commits only, without changing the existing outgoing commit history.
- Non-goals:
  - No push, PR, merge, or history rewrite.
  - No commit of generated `tmp/` artifacts or machine-specific runtime output.

## Scope (in/out)
- In:
  - add `tmp/` ignore coverage
  - validate and commit the Gmail intake foreground/auto-config feature set
  - move the two Gmail ExecPlans from `active/` to `completed/`
- Out:
  - deleting local scratch/build output
  - touching live extension folders or AppData files outside the repo

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `80a7312657be2ec27716edd94b7ea82f267456c4`
- Target integration branch: `feat/ai-docs-bootstrap`
- Canonical build status: canonical worktree and canonical branch per `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Repo hygiene:
  - `.gitignore` gains `tmp/` so scratch/build artifacts stop polluting SCM counts.
- Git history:
  - commit split is locked to:
    1. `chore(repo): ignore tmp scratch artifacts`
    2. `feat(mail): add Edge auto-config and foreground activation for Gmail intake`
    3. `docs(assistant): record Gmail intake execution plans`

## File-by-file implementation steps
- `.gitignore`
  - ignore `tmp/`.
- Gmail feature files
  - stage the current app/runtime, extension, installer/build, and test files as one cohesive feature commit.
- ExecPlan files
  - move the two Gmail plans to `docs/assistant/exec_plans/completed/`.
  - add this cleanup ExecPlan to `active/` during execution; decide at the end whether it remains active or moves to `completed/` with the pass record.

## Tests and acceptance criteria
- Run before the feature commit:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_focus.py tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py tests/test_installer_native_host.py`
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py -k "gmail_intake_bridge_starts_when_enabled or gmail_intake_bridge_restarts_and_stops_with_settings_changes or gmail_intake_bridge_stops_on_window_close or gmail_intake_bridge_runtime_metadata_is_written_and_cleared or gmail_intake_acceptance_updates_visible_ui_without_starting_translation or gmail_intake_acceptance_skips_message_load_while_busy or open_gmail_batch_review_dialog_takes_preview_cache_transfer"`
  - `python3 -m compileall src tests`
- Run after docs move:
  - `dart run tooling/validate_agent_docs.dart`
- Final acceptance:
  - `git status --short` is clean
  - `tmp/` no longer appears in Source Control
  - branch remains ahead locally with new commits only

## Rollout and fallback
- If a validation fails, stop before committing the feature commit and keep the tree intact for targeted correction.
- If doc validation fails after moving plans, fix the docs state before the final docs commit.

## Risks and mitigations
- Risk: accidental commit of scratch artifacts from `tmp/`.
  - Mitigation: ignore `tmp/` first and stage paths explicitly for later commits.
- Risk: mixing docs records into the feature commit.
  - Mitigation: keep ExecPlan moves in the final docs-only commit.

## Assumptions/defaults
- The current `364` Source Control count is mostly untracked `tmp/` noise and should not be committed.
- The existing outgoing two commits on `feat/ai-docs-bootstrap` stay untouched.

## Validation log
- Executed validations:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_gmail_focus.py tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py tests/test_installer_native_host.py` -> PASS (`47 passed`)
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_app_state.py -k "gmail_intake_bridge_starts_when_enabled or gmail_intake_bridge_restarts_and_stops_with_settings_changes or gmail_intake_bridge_stops_on_window_close or gmail_intake_bridge_runtime_metadata_is_written_and_cleared or gmail_intake_acceptance_updates_visible_ui_without_starting_translation or gmail_intake_acceptance_skips_message_load_while_busy or open_gmail_batch_review_dialog_takes_preview_cache_transfer"` -> PASS (`7 passed, 94 deselected`)
  - `python3 -m compileall src tests` -> PASS
- Commit outcomes:
  - `9ec610f` -> `chore(repo): ignore tmp scratch artifacts`
  - `75bafe4` -> `feat(mail): add Edge auto-config and foreground activation for Gmail intake`
- Tree triage outcome:
  - `tmp/` was removed from Source Control noise by `.gitignore`
  - the Gmail feature files were committed as one cohesive product change
  - the Gmail ExecPlans and this cleanup ExecPlan are ready to be archived under `docs/assistant/exec_plans/completed/`
