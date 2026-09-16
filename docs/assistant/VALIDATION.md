# Validation guide

Use the smallest meaningful check first. Do not claim a test passed until its process and terminal result are known. [HANDOFF.md](HANDOFF.md) and the [ordinary integration plan](exec_plans/completed/2026-09-16_ordinary_browser_integration.md) identify the current build and latest outcomes; this page defines the validation tiers.

## Interpreter and isolation

Project tests use `C:/Users/FA507/.codex/legalpdf_translate/.venv311/Scripts/python.exe`, available as `.\.venv311\Scripts\python.exe` in a configured worktree. Do not use bare/global Python for pytest. Run from the intended worktree and record its path, branch and HEAD.

Use fresh temporary settings/output roots and existing synthetic fixtures. Never point tests at live Gmail, credentials, the user's app data or private outputs by default. Browser `shadow` mode alone does not disable provider, auth or native operations. A named isolated acceptance runner can have a stricter socket boundary than the ordinary browser/API test harness; do not weaken that boundary to make a different test fit it.

## 1. Targeted tests

```powershell
.\.venv311\Scripts\python.exe -m pytest -q tests/test_source_review_browser_state.py tests/test_formatting_review_browser_state.py
.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_source_review_api.py tests/test_shadow_web_formatting_review_api.py
```

Choose affected modules and real regression cases rather than repeating broad suites without a new change or unresolved concern. Source/accounting changes need guard, resume and failure-path coverage. Formatting changes need content/mapping/package checks, including Arabic where relevant. A synthetic SDK/Word test is not a real-provider/native acceptance result.

## 2. Complete repository pytest

```powershell
.\.venv311\Scripts\python.exe -m pytest -q -ra tests
```

Use the complete collection before merge and after integrated code/test/workflow changes when required. Retain the full terminal count, failures, skips, duration and JUnit when available. For a long run, use a bounded owned launcher, capture logs and freeze its named source/test snapshot. Do not duplicate collection or start another full run merely because the active run is quiet.

## 3. Standard validation wrapper

```powershell
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1
powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full
```

The wrapper runs focused browser tests, compileall, relevant docs validation and workspace hygiene. `-Full` adds Gmail unit coverage and separate groups of seven source-review and six formatting-review test files. **Full is not the complete repository pytest collection.** Preserve its existing Gmail filters and interpreter selection; it does not authorize live Gmail or native Word operations.

## 4. Documentation and policy checks

After docs/manifest/policy-validator changes, run the direct Dart tools on this machine (or the same current runtime resolved by the wrapper):

```powershell
& 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' test/tooling/validate_agent_docs_test.dart
& 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_agent_docs.dart
& 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/validate_workspace_hygiene.dart
```

The known `Unable to find AOT snapshot for dartdev` wrapper error is distinct from the direct-Dart fallback. Record the wrapper failure and an actual successful fallback; do not infer success if the fallback did not finish. Standing Docs Sync authorization does not waive docs/manifest consistency checks.

## 5. Browser and rendered-document evidence

For browser checks, record the actual build/asset version and owned isolated workspace, use fictional inputs where possible, and test the real UI path. Source review, exact operation recovery and artifact download should use the public APIs rather than injected accepted commits. A new CSS file on disk does not change an old server's immutable static snapshot; verify the served asset.

For a perceptual DOCX change, retain exact source/output identities and inspect the actual relevant pages. Programmatic package/text checks and visual/native acceptance answer different questions. Translation DOCX creation does not require automatic Word export. Any necessary native or paid operation must follow its current explicit scope, retained ownership and one-shot recovery rules; failed/consumed helpers are not reusable.

## Readiness and historical results

A passing targeted suite, Full wrapper, full pytest run, real browser check and real-document acceptance are separate evidence. Report unexecuted or unavailable checks plainly. Before publication, use [COMMIT_PUBLISH_WORKFLOW.md](workflows/COMMIT_PUBLISH_WORKFLOW.md), exact-head required CI and the user's current scope.

Detailed historical validation, Google Photos/native cases and old PR-specific coverage are retained in the [dated public guide](history/2026-09-16_front_doors/VALIDATION.md), which discloses one fictional personal-name substitution. The exact original remains privately preserved. Its old budgets, pending instructions and stage tokens are historical, not active execution authority.
