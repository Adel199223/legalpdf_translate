# CI_REPO_WORKFLOW

## What This Workflow Is For
Managing CI and repository operations safely, including branch hygiene and required checks.

## Expected Outputs
- CI changes scoped to required policy/test coverage.
- Stable branch/repo state after operations.
- Explicit check matrix outcomes.

## When To Use
- Updating workflow automation.
- Changing repository operations policy.
- Enforcing validation/test gates.

## What Not To Do
- Don't use this workflow when the user asked only for a commit/publish action.
- Instead use `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`.

## Primary Files
- `.github/workflows/python-package.yml`
- `docs/assistant/workflows/COMMIT_PUBLISH_WORKFLOW.md`
- `docs/assistant/workflows/DOCS_MAINTENANCE_WORKFLOW.md`
- `docs/assistant/workflows/STAGED_EXECUTION_WORKFLOW.md`

## Minimal Commands
PowerShell:
```powershell
git status --short --branch
.venv311\Scripts\python.exe --version
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
.venv311\Scripts\python.exe -m pytest -q
```
POSIX:
```bash
git status --short --branch
python3 --version
dart tooling/validate_agent_docs.dart
dart tooling/validate_workspace_hygiene.dart
python3 -m pytest -q
```

## Targeted Tests
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Quick`
- `.venv311/Scripts/python.exe -m pytest -q tests/test_test_shards.py`
- `dart test/tooling/validate_agent_docs_test.dart`
- `dart test/tooling/validate_workspace_hygiene_test.dart`
- `dart test/tooling/automation_preflight_test.dart`
- `dart test/tooling/cloud_eval_preflight_test.dart`

## Test scheduling and evidence

Keep the complete collection as the merge requirement. Quick local feedback is a separate tier, not a changed-file substitute for release coverage. `tooling/test_shards.py` collects actual node IDs and balances whole files using `tooling/test_timings.json`. Unknown/new files remain included; timing data affects placement only. Keep Qt UI files in one local process and retain fresh per-worker app-data/temp/report paths and the normal provider/native/file-launch guards. The CLI defaults to one worker; explicit two/four-worker runs need their own fresh output directory. Do not share mutable workflow fixtures to reduce runtime.

The CI update runs on PRs, main pushes and manual dispatch. This avoids duplicate feature-branch push plus PR runs. A newer PR revision cancels only its superseded PR workflow; main validation is not cancelled. The four Windows partitions retain collection plans, actual per-test durations, JUnit and terminal logs as separate artifacts. Upload only these reports, never the worker's temporary fixture/app-data directories.

For reruns, name each upload `pytest-shard-N-attempt-${{ github.run_attempt }}` and download artifacts from the current workflow run only. The local `tooling/ci_test_evidence.py` selector requires all four shard indexes and selects the latest **numeric** attempt independently for each index before delegating to the strict `test_shards.verify_results` checker. This supports rerunning failed jobs while retaining unchanged successful shard evidence from that same run. Keep every older artifact; never overwrite it or choose an earlier success when the latest attempt is failed, incomplete or inconsistent. GitHub documents that `github.run_id` remains stable for reruns and `github.run_attempt` increments for each rerun; this is platform behavior, while latest-per-shard selection is our local verification policy. [GitHub contexts reference](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts), checked 2026-09-26.

`test (3.11)` is the stable required aggregate context. It must run even when a dependency fails, reject every non-success dependency result, then verify all four reports have the same complete collection/assignment and cover it exactly once with successful actual execution/JUnit. Missing, failed, cancelled or skipped partitions must not turn into a green gate. Preserve Windows docs/localization/workspace validators, validator tests, compile and targeted core regressions, plus the independent Linux `docs_tooling_contracts` job.

Refresh timing weights from a successful complete JUnit run when balance drifts. Record source revision, host and command; compare like-for-like scopes and distinguish local measured time from hosted CI elapsed time. Preserve original failures. The [test performance plan](../exec_plans/completed/2026-09-26_test_performance.md) and [validation guide](../VALIDATION.md) own the current baseline and measured results. Local Quick (87 cases), selected Full (659 cases) and complete four-worker validation (6,754 cases: all original 6,717 plus 37 runner tests) have completed. The complete comparison measured 537.941 versus 1,835.010 seconds, 3.411x faster in one local run; the baseline overlapped short Quick/tool checks. This is not a hosted-CI guarantee, and later artifact-selector tests have separate validation.

## Failure Modes and Fallback Steps
- CI false negatives: align command scope and parser expectations.
- CI runtime blow-up: run targeted regression first, then full suite.
- Branch contamination: isolate changes with worktree and scoped commits.
- Local Python import corruption (`html.entities`/`idna`/`pip`): rebuild env with `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`.

## Handoff Checklist
1. Confirm worktree isolation guidance remains explicit.
2. Confirm CI includes docs/localization/workspace validators and tests.
3. Confirm targeted core regression tests are present.
4. Confirm stage-gate workflow references are up to date.
