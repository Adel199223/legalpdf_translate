# Browser Interpretation Beginner Qt Polish

## Title
Beginner-first Qt polish for the browser interpretation intake, review, export, and Gmail finalization flow.

## Goal and non-goals
- Goal:
  - make the browser `ui=qt` interpretation flow read like a guided app flow instead of a workflow/operator console
  - keep the beginner path clear across intake, review, save, export, and Gmail reply finalization
- Non-goals:
  - no backend API, payload, or route changes
  - no Gmail bridge/native-host contract changes
  - no translation, interpretation save/export semantics, or `ui=legacy` behavior changes

## Scope
- In:
  - browser interpretation copy/layout polish in the Qt shell
  - browser-only interpretation presentation helpers
  - markup and browser-state test updates for the new beginner-visible copy
- Out:
  - backend interpretation logic
  - Gmail finalization semantics
  - translation, settings, recent jobs, or extension-lab redesign

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-new-job-qt-polish`
- Base branch: `feat/browser-new-job-qt-polish`
- Base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- Target integration branch: `main`
- Canonical build status: noncanonical browser-shell worktree carrying the approved browser UX floor from the current branch baseline

## Interfaces/types/contracts affected
- `src/legalpdf_translate/shadow_web/static/interpretation_review_state.js`
  - add a browser-only interpretation presentation helper for beginner-visible copy and action labels
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - adjust interpretation-stage presentation copy only
- No backend, route, DOM ID, or payload contract changes

## File-by-file implementation steps
- `docs/assistant/exec_plans/active/2026-04-21_browser_interpretation_beginner_qt_polish.md`
  - record the active plan and close it with validations/results
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - replace interpretation workflow wording with beginner-facing labels in the Qt shell and drawer
- `src/legalpdf_translate/shadow_web/static/interpretation_review_state.js`
  - add the pure interpretation presentation helper while keeping guard/workspace/drawer behavior unchanged
- `src/legalpdf_translate/shadow_web/static/app.js`
  - route interpretation session, review, export, and Gmail-result copy through the new presentation helper
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - update interpretation-stage titles/descriptions to match the new beginner Gmail tone
- `tests/test_interpretation_review_state.py`
  - add helper coverage for blank/manual/Gmail/completed interpretation presentation
- `tests/test_gmail_review_state.py`
  - update interpretation-stage wording assertions
- `tests/test_shadow_web_api.py`
  - update beginner-visible markup assertions for the interpretation Qt surface

## Tests and acceptance criteria
- Validation commands:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- Acceptance:
  - the interpretation flow reads like a guided app path for beginners
  - technical diagnostics remain reachable but secondary
  - interpretation save/export/finalize behavior remains unchanged
  - validation passes through `.venv311`

## Rollout and fallback
- Roll out as browser-only copy/presentation changes.
- If regressions appear, revert the new interpretation presentation helper usage while preserving existing interpretation guards and workspace-mode behavior.

## Risks and mitigations
- Risk: copy changes could drift across template and runtime-rendered surfaces.
  - Mitigation: centralize dynamic interpretation wording in one pure helper and cover it with browser-state tests.
- Risk: Gmail interpretation wording changes could break existing stage assertions.
  - Mitigation: limit Gmail changes to interpretation-stage presentation text and update focused tests only.

## Assumptions/defaults
- `Review Interpretation Request` is the clearest beginner-facing drawer title.
- `Create fee-request document` is acceptable visible wording while the `/api/interpretation/export-honorarios` route remains unchanged.
- `Amounts (EUR)` can stay visible as-is unless a wording conflict appears during implementation.

## Implemented
- Added `deriveInterpretationReviewPresentation(...)` in the browser interpretation state helper to centralize beginner-facing interpretation session/review/export/Gmail labels.
- Updated the Qt interpretation shell and drawer copy so the beginner flow now reads as:
  - start interpretation request
  - review case details
  - review details
  - save case record
  - create fee-request document
  - create Gmail reply
- Updated Gmail interpretation stage wording to match the new beginner tone without changing Gmail stage logic or actions.
- Kept all interpretation DOM IDs, form field names, backend routes, guard behavior, workspace modes, and Gmail finalization semantics unchanged.

## Validation results
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections` -> PASS (`1 passed`)
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` -> PASS
  - baseline pytest group: `55 passed`
  - `compileall`: PASS
  - `dart run tooling/validate_agent_docs.dart` -> failed with `Unable to find AOT snapshot for dartdev`
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` -> PASS
  - `dart run tooling/validate_workspace_hygiene.dart` -> failed with `Unable to find AOT snapshot for dartdev`
  - `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` -> PASS
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> PASS
  - baseline pytest group: `55 passed`
  - `compileall`: PASS
  - `tests/test_gmail_review_state.py`: `1 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - same Dart fallback path succeeded for both validators
