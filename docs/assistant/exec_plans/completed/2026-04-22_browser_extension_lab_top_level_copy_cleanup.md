## 1. Title
Browser Extension Lab Top-Level Copy Cleanup

## 2. Goal and non-goals
Goal:
- Remove the remaining technical/internal wording from the Extension Lab top-level browser helper cards.
- Keep the top-level card layer friendly while preserving all raw technical data in diagnostics/details.
- Preserve route, DOM, payload, safe-rendering, and live/shadow contracts.

Non-goals:
- No backend behavior changes.
- No route-id, DOM-id, API-path, payload-shape, or submitted-value changes.
- No Power Tools changes.
- No ZIP creation, commit, or review-bundle workflow.

## 3. Scope (in/out)
In:
- `src/legalpdf_translate/shadow_web/static/app.js` Extension Lab card-text helpers
- one focused static-JS contract test in `tests/test_shadow_web_api.py`
- pass-local before-snapshot and final unified diff workflow

Out:
- template copy
- route-state behavior
- safe prepare-reason catalog structure
- backend Gmail/native-host/extension logic

## 4. Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- current HEAD SHA at plan start: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`

## 5. Interfaces/types/contracts affected
- No backend or public API changes.
- No route-id, DOM-id, payload, storage, select-value, or diagnostics-shape changes.
- Downloads-only pass artifacts:
  - implementation summary
  - validation summary
  - pass-local unified diff patch

## 6. File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/static/app.js`
  - tightened `extensionReadinessCardText(...)` to deterministic friendly strings only
  - tightened `extensionInstallCardText(...)` to friendly installation-status strings only
  - left `extensionModeCardText(...)` unchanged
  - kept `renderExtensionLab(...)` diagnostics payload unchanged
- `tests/test_shadow_web_api.py`
  - added one focused static-source contract test for the cleaned Extension Lab helper behavior

## 7. Pass-local diff workflow
- Before editing repo files, copied each planned-to-edit file into a timestamped snapshot root outside the repo.
- Snapshot root used for this pass:
  - `C:\Users\FA507\AppData\Local\Temp\legalpdf_translate_extension_lab_top_level_copy_cleanup_before_2026-04-22_164751`
- Snapshotted before edits:
  - `src/legalpdf_translate/shadow_web/static/app.js`
  - `tests/test_shadow_web_api.py`
  - `tests/test_browser_safe_rendering.py`
  - `tests/test_shadow_web_route_state.py`
  - `docs/assistant/exec_plans/active/2026-04-22_browser_extension_lab_top_level_copy_cleanup.md`
- Generated the final `.patch` from the snapshot tree to final files, not from `git diff HEAD`.

## 8. Tests and validation
- Targeted:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py`
- Wrapper validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- When the known Dart `dartdev` AOT issue appeared, recorded both the wrapper failure and the successful direct Dart fallback.

## 9. Risks and mitigations
- Risk: friendly card copy could accidentally hide technical data completely.
  - Mitigation: kept `setDiagnostics("extension", ...)` payload unchanged and tested for it statically.
- Risk: cleanup could regress safe rendering.
  - Mitigation: left `renderExtensionPrepareReasonCatalogInto(...)` untouched and kept the safe-rendering regression suite.

## 10. Assumptions/defaults
- Kept the cleanup frontend-only.
- Did not touch `index.html`.
- Used the existing static-source assertion pattern instead of adding a new browser ESM render probe for this tiny pass.

## 11. Implemented
- Extension Lab top-level readiness copy no longer surfaces `bridgeSummary.message` and now uses deterministic friendly strings only:
  - `Ready for Gmail intake in this mode.`
  - `This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting.`
  - `Needs attention before Gmail intake can start here. Open technical details below when troubleshooting.`
- Extension Lab top-level installation copy no longer surfaces `Stable ID:` or raw install identifiers and now uses friendly deterministic strings only:
  - `Browser helper details were found. Open technical details below for installation IDs.`
  - `Older browser helper details were found. Open technical details below when troubleshooting.`
  - `No browser helper installation details were reported.`
- Raw `prepare_response`, `extension_report`, `bridge_summary`, and `notes` remained available in the diagnostics/details payload passed to `setDiagnostics("extension", ...)`.
- The safe prepare-reason catalog was left unchanged and still renders the human message first plus a `Code: ...` line through DOM-safe text helpers only.

## 12. Validation results
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py`
  - PASS
  - `52 passed in 150.53s`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - PASS
  - wrapper pytest suite: `59 passed`
  - `compileall` passed
  - `dart run tooling/validate_agent_docs.dart` hit `Unable to find AOT snapshot for dartdev`
  - fallback `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` passed
  - `dart run tooling/validate_workspace_hygiene.dart` hit the same AOT issue
  - fallback `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` passed
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - PASS
  - wrapper pytest suite: `59 passed`
  - `compileall` passed
  - `tests/test_gmail_review_state.py`: `1 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - both Dart validators again hit the known `dartdev` AOT issue and then passed via the direct Dart fallback
