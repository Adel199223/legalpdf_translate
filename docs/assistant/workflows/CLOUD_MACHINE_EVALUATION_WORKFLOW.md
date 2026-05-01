# CLOUD_MACHINE_EVALUATION_WORKFLOW

## What This Workflow Is For
Managing heavy machine evaluation/scoring with cloud-first execution and local acceptance gate separation.

## Expected Outputs
- Cloud preflight result packet with explicit semantics.
- Venue split decision (`cloud|local`) and heavy-run trigger reason.
- Local human acceptance status before any final apply step.

## When To Use
- External API/cost-sensitive heavy evaluation/scoring tasks.
- Large job/pair/candidate sets or meaningful budget caps.
- Multi-target or multilingual scoring runs.

## What Not To Do
- Don't use this workflow when the task is simple smoke checking or routine local testing.
- Instead use `docs/assistant/workflows/CI_REPO_WORKFLOW.md`.

## Primary Files
- `docs/assistant/workflows/CLOUD_MACHINE_EVALUATION_WORKFLOW.md`
- `tooling/cloud_eval_preflight.dart`
- `test/tooling/cloud_eval_preflight_test.dart`
- `.github/workflows/python-package.yml`

## Minimal Commands
PowerShell:
```powershell
dart tooling/cloud_eval_preflight.dart
dart test/tooling/cloud_eval_preflight_test.dart
```
POSIX:
```bash
dart tooling/cloud_eval_preflight.dart
dart test/tooling/cloud_eval_preflight_test.dart
```

## Targeted Tests
- `dart test/tooling/cloud_eval_preflight_test.dart`
- `dart tooling/validate_agent_docs.dart`

## Failure Modes and Fallback Steps
- Cloud dispatch/secrets/tooling preflight failure: classify as `unavailable` and rerun preflight after fix.
- Cloud run logic/assertion failure after start: classify as `failed` and debug run outputs.
- Cloud remains unavailable: allow local heavy fallback only after cloud retry path is exhausted.

## Handoff Checklist
1. Emit venue decision and heavy-run trigger reason.
2. Emit cloud preflight status + failure semantics (`unavailable|failed|n/a`).
3. Confirm cloud-to-local fallback status.
4. Confirm local manual acceptance gate status before final apply.
5. Confirm no-auto-apply guardrail remains enforced.
