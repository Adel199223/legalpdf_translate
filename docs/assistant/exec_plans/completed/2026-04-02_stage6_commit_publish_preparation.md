# Stage 6: Commit and Publish Preparation

## Goal and non-goals
- Goal: finalize commit/publish preparation after the Stage 5 blocker resolution by confirming current validation status and locking the intended commit split.
- Goal: leave the branch ready for an explicit commit request without performing commit, push, PR, or merge actions.
- Non-goal: stage files in git or create commits automatically.
- Non-goal: perform any approval-gated external network action.

## Scope (in/out)
- In scope:
  - final regression pass over the current feature scope
  - assistant docs/workspace validator confirmation
  - exact commit-group definition
  - branch readiness packet for the next explicit commit/publish step
- Out of scope:
  - `git add`
  - `git commit`
  - `git fetch`, `git push`, PR creation, or merge

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/gmail-finalization-report-success`
- base branch: `main`
- base SHA: `18be21ec2d2c632f12ec5da3d2e5351aa5644488`
- target integration branch: `main`
- canonical build status: noncanonical feature branch prepared for commit, still above the approved-base floor in `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- No new product contract changes were introduced in this preparation stage.
- Locked source-control contract for the next step:
  - keep a two-commit split
  - do not mix product/runtime/test changes with docs/governance closeout

## Locked commit split
### Commit 1: product/runtime/tests/tooling
- `build/pyinstaller_qt.spec`
- `pyproject.toml`
- `src/legalpdf_translate/gmail_batch.py`
- `src/legalpdf_translate/gmail_browser_service.py`
- `src/legalpdf_translate/qt_gui/app_window.py`
- `src/legalpdf_translate/shadow_runtime.py`
- `src/legalpdf_translate/shadow_web/app.py`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
- `tooling/automation_preflight.dart`
- `tooling/render_docx.py`
- `test/tooling/automation_preflight_test.dart`
- `tests/test_gmail_batch.py`
- `tests/test_gmail_browser_service.py`
- `tests/test_qt_app_state.py`
- `tests/test_render_docx.py`
- `tests/test_shadow_runtime_service.py`
- `tests/test_shadow_web_api.py`

Recommended message:
- `feat(gmail): persist finalization reports and harden review tooling`

### Commit 2: docs/governance/closeout
- `APP_KNOWLEDGE.md`
- `docs/assistant/INDEX.md`
- `docs/assistant/LOCAL_CAPABILITIES.md`
- `docs/assistant/LOCAL_ENV_PROFILE.local.md`
- `docs/assistant/features/APP_USER_GUIDE.md`
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- `docs/assistant/manifest.json`
- `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`
- `docs/assistant/workflows/CI_REPO_WORKFLOW.md`
- `docs/assistant/exec_plans/completed/2026-04-01_gmail_finalization_report_artifact_durability.md`
- `docs/assistant/exec_plans/completed/2026-04-01_gmail_finalization_report_success_availability.md`
- `docs/assistant/exec_plans/completed/2026-04-01_residual_tooling_visual_docx_browser_automation.md`
- `docs/assistant/exec_plans/completed/2026-04-01_restore_success_state_gmail_finalization_reports.md`
- `docs/assistant/exec_plans/completed/2026-04-02_stage4_closeout_publish_readiness.md`
- `docs/assistant/exec_plans/completed/2026-04-02_stage5_publish_blocker_resolution.md`
- `docs/assistant/exec_plans/completed/2026-04-02_stage6_commit_publish_preparation.md`

Recommended message:
- `docs(assistant): sync gmail finalization and tooling closeout`

## Tests and acceptance criteria
- Final Python regression pass over the prepared scope:
  - `.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_batch.py tests/test_gmail_browser_service.py tests/test_shadow_web_api.py tests/test_qt_app_state.py tests/test_shadow_runtime_service.py tests/test_render_docx.py tests/test_pyinstaller_specs.py tests/test_windows_shortcut_scripts.py` -> PASS (`309 passed`)
- Dart automation regression:
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe test/tooling/automation_preflight_test.dart` -> PASS (`5 cases`)
- Docs and workspace governance:
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> PASS
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> PASS

## Rollout and fallback
- Next step for local commit only:
  - stage Commit 1 explicitly
  - validate no docs files leaked into Commit 1
  - create Commit 1
  - repeat for Commit 2
- Next step for publish:
  - requires explicit user approval because push/PR/merge are publish/network actions under repo policy

## Risks and mitigations
- Risk: `build/pyinstaller_qt.spec` restoration carries a benign encoding-only diff on the first line.
  - Mitigation: packaging/script tests are green, so keep it with Commit 1 unless a later byte-for-byte restoration is specifically required.
- Risk: the new completed ExecPlan files could be forgotten during commit.
  - Mitigation: they are all enumerated in Commit 2 above.
- Risk: accidental network action during follow-up.
  - Mitigation: keep the next step local unless the user explicitly asks for commit/push/publish.

## Assumptions/defaults
- The user’s Stage 6 continuation authorizes preparation but not implied publish.
- The current branch should preserve the two-commit split recommended in Stage 4.

## Outcome
- Stage 6 completed on `2026-04-02`.
- The branch is commit-ready with a locked two-commit split and fresh validation evidence.
- Actual commit/push/publish remains a separate explicit user decision.
