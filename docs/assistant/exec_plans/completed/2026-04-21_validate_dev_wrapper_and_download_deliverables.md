# Beginner-Safe `.venv311` Validation Wrapper And Download Deliverables

## Goal and non-goals
- Goal: add a Windows-first validation wrapper that always uses `.\.venv311\Scripts\python.exe` instead of bare/global `python`.
- Goal: update beginner-facing validation docs so they point to the wrapper instead of the machine-global Python install.
- Goal: produce the requested implementation summary, validation summary, and clean repo ZIP directly in the user's Downloads folder after implementation and validation.
- Non-goal: change app behavior, browser/Gmail workflows, backend APIs, test selection semantics beyond the requested wrapper modes, or install anything into bare/global Python.

## Scope (in/out)
- In:
  - new `scripts/validate_dev.ps1`
  - README and app-knowledge validation instructions
  - Downloads deliverables: implementation summary, validation summary, updated ZIP
  - ExecPlan lifecycle and validation logging
- Out:
  - application runtime behavior
  - backend/browser/Gmail contracts
  - dependency installation into bare/global Python
  - unrelated dirty worktree files from prior passes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-new-job-qt-polish`
- Base branch: `main`
- Base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- Target integration branch: `main`
- Canonical build status or intended noncanonical override: noncanonical feature-branch worktree used for local browser/validation iteration only; no runtime contract change intended.

## Interfaces/types/contracts affected
- New developer-facing wrapper:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- No backend, browser, Gmail, translation, route, or API contract changes.

## File-by-file implementation steps
- `scripts/validate_dev.ps1`
  - resolve repo root from `$PSScriptRoot`
  - require `.\.venv311\Scripts\python.exe`
  - run baseline validation through `.venv311`
  - optionally run broader browser/web validation with `-Full`
  - print each command before execution and pass/fail after execution
  - stop on first failure with nonzero exit
  - detect touched docs/ExecPlans from `git status --porcelain`
  - run Dart validators when relevant, with direct-Dart fallback for the known `dartdev` AOT error
- `README.md`
  - replace bare-`python` validation instructions with wrapper usage
  - keep `.venv311` setup/recovery guidance
- `APP_KNOWLEDGE.md`
  - update verification commands to prefer the wrapper on Windows
  - keep local Python baseline guidance and `.venv311` recovery notes
- Downloads deliverables
  - create implementation summary after code/docs changes
  - run wrapper baseline and full validation
  - create validation summary from actual command results
  - create clean ZIP in Downloads with source/tests/docs/scripts and normal exclusions

## Tests and acceptance criteria
- Run:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Confirm:
  - wrapper uses `.\.venv311\Scripts\python.exe`
  - missing `.venv311` path emits the setup command and exits nonzero
  - wrapper prints commands and pass/fail status honestly
  - README and APP_KNOWLEDGE point beginners to the wrapper
  - implementation summary exists in Downloads
  - validation summary exists in Downloads
  - ZIP exists in Downloads, roots at `legalpdf_translate/`, and excludes `.git`, `.venv*`, caches, temp outputs, generated DOCX/PDF outputs, and build/dist artifacts

## Rollout and fallback
- Keep validation behavior explicit and fail-fast.
- If `dart run` hits the known `Unable to find AOT snapshot for dartdev` issue, rerun the same validators with `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe` and record both commands/results.
- If validation is partial/failed but the worktree remains coherent, still create the requested validation summary and ZIP.

## Risks and mitigations
- Risk: docs-trigger detection misses untracked ExecPlans or doc edits.
  - Mitigation: parse `git status --porcelain` and include both tracked and untracked paths.
- Risk: wrapper silently falls back to bare/global Python.
  - Mitigation: hardcode `.venv311\Scripts\python.exe` and fail immediately if missing.
- Risk: packaging accidentally includes local clutter or sensitive local env state.
  - Mitigation: build the ZIP from explicit inclusion rules with exclusions for `.git`, `.venv*`, caches, temp run folders, generated outputs, build/dist artifacts, and local `.env` variants while preserving `.env.example`.

## Assumptions/defaults
- Use `.venv311` as the only supported validation interpreter in this Windows wrapper.
- Stop on the first failed validation command instead of continuing through a broken validation stack.
- Treat `README.md`, `APP_KNOWLEDGE.md`, and `docs/assistant/` as docs-triggering paths for agent-doc validation.
- Use `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe` as the direct Dart fallback path.

## Validation results
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - exit code: `0`
  - result: passed
  - notes:
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py` -> `55 passed in 129.38s (0:02:09)`
    - `.\.venv311\Scripts\python.exe -m compileall src tests` -> passed
    - `dart run tooling/validate_agent_docs.dart` -> failed with `Unable to find AOT snapshot for dartdev`
    - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> `PASS: agent docs validation succeeded.`
    - `dart run tooling/validate_workspace_hygiene.dart` -> failed with `Unable to find AOT snapshot for dartdev`
    - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> `PASS: workspace hygiene validation succeeded.`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - exit code: `0`
  - result: passed
  - notes:
    - baseline pytest group -> `55 passed in 130.44s (0:02:10)`
    - baseline compileall -> passed
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> `1 passed in 0.18s`
    - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"` -> `5 passed, 9 deselected in 0.44s`
    - broader pytest group -> `55 passed in 140.09s (0:02:20)`
    - final compileall -> passed
    - `dart run` hit the same known `dartdev` AOT issue for both validators, and both direct-Dart fallbacks passed
