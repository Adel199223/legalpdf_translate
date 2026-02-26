# PERFORMANCE_WORKFLOW

## What This Workflow Is For
Keeping workspace/editor performance predictable through canonical baseline policy.

## Expected Outputs
- Diagnosed performance bottleneck context.
- Safe `.vscode/settings.json` excludes aligned with baseline.
- Validation output from workspace hygiene tooling.

## When To Use
- VS Code slow file watching/search/indexing.
- Large generated artifacts causing editor lag.
- Workspace hygiene policy updates.

## What Not To Do
- Don't use this workflow when localization terms are the issue.
- Instead use `docs/assistant/workflows/LOCALIZATION_WORKFLOW.md`.

## Primary Files
- `docs/assistant/PERFORMANCE_BASELINES.md`
- `.vscode/settings.json`
- `tooling/validate_workspace_hygiene.dart`

## Minimal Commands
```powershell
code --status
dart run tooling/validate_workspace_hygiene.dart
```

## Targeted Tests
- `dart run test/tooling/validate_workspace_hygiene_test.dart`

## Failure Modes and Fallback Steps
- Watcher excludes missing: apply baseline entries idempotently.
- Overly broad excludes hide needed files: tighten patterns and revalidate.
- Performance issue persists: capture `code --status` and escalate with diagnostics.

## Handoff Checklist
1. Confirm excludes are sourced from `PERFORMANCE_BASELINES.md` only.
2. Confirm stack-conditional rules match repository languages.
3. Confirm no destructive environment deletion occurred.
