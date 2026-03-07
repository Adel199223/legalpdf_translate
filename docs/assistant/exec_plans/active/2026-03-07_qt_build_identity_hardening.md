# Qt Build Identity Hardening

## Goal and Non-Goals
- Goal: eliminate ambiguous Qt GUI handoffs across multiple worktrees by adding a canonical launcher that emits a build identity packet, a tracked canonical-build policy file, and runtime identity surfaces for noncanonical builds.
- Non-goals: user-facing product features, schema changes, or docs sync for unrelated feature branches.

## Scope
- In scope:
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
  - `src/legalpdf_translate/build_identity.py`
  - `src/legalpdf_translate/qt_app.py`
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `tooling/launch_qt_build.py`
  - governance/workflow doc updates for GUI handoffs in multi-worktree situations
  - validator/test coverage enforcing the new helper-based discipline
- Out of scope:
  - Gemini/Gmail/ocr feature docs
  - feature-specific schema or provider behavior changes

## Worktree Provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/ai-docs-bootstrap`
- Base branch: `feat/ai-docs-bootstrap`
- Base SHA: `1d63121`
- Target integration branch: `feat/ai-docs-bootstrap`

## Interfaces / Contracts Affected
- Canonical build policy:
  - `docs/assistant/runtime/CANONICAL_BUILD.json`
  - canonical worktree path
  - canonical branch
  - canonical head floor
  - noncanonical override policy
- Canonical GUI launch helper:
  - `python tooling/launch_qt_build.py --worktree <path> [--labels "..."] [--identity-out <json>] [--dry-run]`
- Build identity packet fields:
  - `worktree_path`
  - `branch`
  - `head_sha`
  - `launch_command`
  - `labels`
  - `timestamp_utc`
- Runtime build identity surfaces:
  - noncanonical window title suffix: `[branch@sha]`
  - Settings/Diagnostics “Build under test” summary

## File-by-File Steps
1. Add `tooling/launch_qt_build.py` with:
   - required `--worktree`
   - optional `--labels`
   - optional identity JSON output
   - fail-fast validation for invalid worktree, detached HEAD, missing `qt_app.py`, and noncanonical launches without explicit override
2. Add `docs/assistant/runtime/CANONICAL_BUILD.json` as the canonical runnable-build policy file.
3. Add `src/legalpdf_translate/build_identity.py` and wire it into:
   - `src/legalpdf_translate/qt_app.py`
   - `src/legalpdf_translate/qt_gui/app_window.py`
   - `src/legalpdf_translate/qt_gui/dialogs.py`
   so noncanonical builds visibly identify themselves in the window title and Settings diagnostics.
4. Add `tests/test_launch_qt_build.py` smoke coverage for:
   - dry-run identity packet emission
   - invalid worktree rejection
   - noncanonical rejection without override
   - noncanonical dry-run with explicit override
5. Update governance/workflow docs:
   - `agent.md`
   - `docs/assistant/workflows/WORKTREE_BASELINE_DISCIPLINE_WORKFLOW.md`
   - `docs/assistant/workflows/REFERENCE_LOCKED_QT_UI_WORKFLOW.md`
   - `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
   - `docs/assistant/exec_plans/PLANS.md`
   - `docs/assistant/INDEX.md`
   - `docs/assistant/DOCS_REFRESH_NOTES.md`
6. Extend `tooling/validate_agent_docs.dart` and its test to enforce:
   - helper presence
   - helper mention in the required governance/workflow docs
   - `HEAD SHA` + canonical/noncanonical status requirement for GUI handoffs

## Tests and Acceptance Criteria
- Helper smoke test:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_launch_qt_build.py`
- Runtime identity wiring:
  - `./.venv311/Scripts/python.exe -m pytest -q tests/test_qt_main_smoke.py tests/test_qt_app_state.py`
- Validator test:
  - `dart run test/tooling/validate_agent_docs_test.dart`
- Helper dry-run acceptance:
  - `./.venv311/Scripts/python.exe tooling/launch_qt_build.py --worktree /mnt/c/Users/FA507/.codex/legalpdf_translate --labels "canonical,gemini,gmail" --dry-run`
  - `./.venv311/Scripts/python.exe tooling/launch_qt_build.py --worktree /mnt/c/Users/FA507/.codex/legalpdf_translate_integration --labels "gemini-ocr,honorarios,gmail-draft" --allow-noncanonical --dry-run`
- Governance validators:
  - `dart run tooling/validate_agent_docs.dart`
  - `dart run tooling/validate_workspace_hygiene.dart`

## Rollout and Fallback
- Rollout is internal-only: use the helper immediately for ambiguous multi-worktree GUI launches.
- If the helper fails in a given environment, fall back to dry-run identity emission first, then fix the launcher/git path rather than returning to ad hoc GUI launch commands.

## Risks and Mitigations
- Risk: docs drift back to soft guidance.
  - Mitigation: validator enforcement plus dedicated helper mention in required docs.
- Risk: helper assumes the wrong Windows interpreter path.
  - Mitigation: resolve `.venv311/Scripts/pythonw.exe` first, then `python.exe`, and fail fast if neither exists.
- Risk: Windows `git` cannot resolve WSL-authored worktree metadata.
  - Mitigation: `build_identity.py` falls back to `wsl.exe --exec git` when the worktree `.git` pointer uses `/mnt/...`.

## Assumptions and Defaults
- Multi-worktree GUI handoffs are the only scenarios that require the helper.
- The canonical machine-readable build identity plus the noncanonical runtime title/diagnostics marker is the minimum needed to prevent wrong-window handoffs.
- The canonical runnable build for this pass is the repo-root worktree on `feat/ai-docs-bootstrap` at `4e9d20e`.
