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
- `dart test/tooling/validate_agent_docs_test.dart`
- `dart test/tooling/validate_workspace_hygiene_test.dart`
- `dart test/tooling/automation_preflight_test.dart`
- `dart test/tooling/cloud_eval_preflight_test.dart`

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
