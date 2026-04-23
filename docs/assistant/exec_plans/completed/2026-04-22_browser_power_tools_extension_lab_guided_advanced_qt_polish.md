## 1. Title
Browser Power Tools / Extension Lab Guided Advanced Qt Polish

## 2. Goal and non-goals
Goal:
- Make the Qt browser `#power-tools` and `#extension-lab` routes feel clearer and less scary without removing their advanced troubleshooting purpose.
- Keep top-level copy calmer while leaving technical details available in diagnostics, details panels, and raw data areas.
- Preserve all route, DOM, API, payload, safe-rendering, live/shadow, Gmail/browser-helper, and `ui=legacy` contracts.

Non-goals:
- No backend behavior changes.
- No route-id, DOM-id, API path, payload shape, or submitted-value changes.
- No redesign of `ui=legacy`.
- No ZIP creation, commit, or review-bundle workflow.

## 3. Scope (in/out)
In:
- Power Tools and Extension Lab nav descriptions
- Qt topbar copy for these two routes
- Visible route/template copy and status text for these two routes
- Friendly visible option labels that preserve submitted values
- Strict pass-local before-snapshot and final unified diff workflow
- Focused template, route-state, and safe-rendering tests

Out:
- Settings/Profile/Overview/Gmail daily-use route changes
- Native-host, Gmail handoff, extension diagnostics, or power-tools backend logic changes
- Route-state beginner-surface expansion for Power Tools or Extension Lab

## 4. Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- current HEAD SHA at plan start: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- target integration branch: `main`

## 5. Interfaces/types/contracts affected
- No backend or public API interface changes.
- No route-id, DOM-id, payload, select-value, or storage changes.
- No `state.js` beginner-surface change for these routes.
- Downloads-only pass artifacts:
  - implementation summary
  - validation summary
  - pass-local unified diff patch

## 6. File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - kept the calmer Power Tools / Extension Lab hero and section copy in place and aligned the remaining visible details hints
- `src/legalpdf_translate/shadow_web/static/app.js`
  - added explicit Qt topbar copy for the two operator routes
  - softened Extension Lab card/status text
  - kept the prepare-reason catalog DOM-safe while showing message first and code second
- `src/legalpdf_translate/shadow_web/static/power-tools.js`
  - softened visible Power Tools statuses, hints, latest-run helper labels, and failure text
- `tests/test_shadow_web_api.py`
  - replaced old operator-copy assertions, added calmer-copy coverage, preserved DOM-ID checks, and locked friendly option labels
- `tests/test_shadow_web_route_state.py`
  - asserted `#power-tools` and `#extension-lab` remain routable and outside the beginner-surface dataset
- `tests/test_browser_safe_rendering.py`
  - kept strict safe-rendering coverage while updating the reason-catalog text expectation to include `Code: ...`

## 7. Pass-local diff workflow
- Before editing repo files, copied each planned-to-edit file into a timestamped snapshot root outside the repo.
- Snapshot root used for this pass:
  - `C:\Users\FA507\AppData\Local\Temp\legalpdf_translate_power_tools_extension_lab_before_2026-04-22_160041`
- Snapshotted before edits:
  - `src/legalpdf_translate/shadow_web/templates/index.html`
  - `src/legalpdf_translate/shadow_web/static/app.js`
  - `src/legalpdf_translate/shadow_web/static/power-tools.js`
  - `src/legalpdf_translate/browser_app_service.py`
  - `tests/test_shadow_web_api.py`
  - `tests/test_shadow_web_route_state.py`
  - `tests/test_browser_safe_rendering.py`
- Generated the final `.patch` from the snapshot tree to final files, not from `git diff HEAD`.

## 8. Tests and validation
- Targeted:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py`
- Wrapper validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- When the known Dart `dartdev` AOT issue appeared, recorded both the wrapper failure and the successful direct Dart fallback.

## 9. Risks and mitigations
- Risk: calmer copy could accidentally remove contract-sensitive IDs or values.
  - Mitigation: kept IDs/values untouched and added explicit test assertions for them.
- Risk: operator-route topbar copy could still fall through to runtime/workspace wording.
  - Mitigation: added explicit route branches in `routeAwareTopbarStatus(...)`.
- Risk: prepare-reason catalog could regress into unsafe HTML rendering.
  - Mitigation: kept DOM-safe text helpers and maintained the strict safe-rendering test.

## 10. Assumptions/defaults
- Kept nav labels as `Power Tools` and `Extension Lab`.
- Kept both routes outside the normal beginner primary surface.
- Kept diagnostics/details/raw JSON areas present and technical.
- Did not update `APP_KNOWLEDGE.md` in this pass.

## 11. Implemented
- Power Tools now presents itself as an advanced tools surface with calmer top-level status text, friendlier latest-run helper labels, and fewer runtime-first messages.
- Extension Lab now presents itself as browser-helper checks for Gmail intake, with calmer status cards and a friendlier top-level readiness sentence while leaving raw diagnostics intact below.
- The Qt topbar now has explicit guided copy for `#power-tools` and `#extension-lab` instead of falling through to the generic runtime/workspace message.
- The prepare-reason catalog remains safely rendered with DOM text nodes only and now shows the human message first plus a secondary `Code: ...` line for troubleshooting.
- Power Tools and Extension Lab remained operator/advanced surfaces; they were not added to the normal beginner-primary dataset.

## 12. Validation results
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py`
  - PASS
  - `51 passed in 152.15s`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - PASS
  - baseline targeted wrapper suite: `58 passed`
  - `compileall` passed
  - `dart run tooling/validate_agent_docs.dart` hit `Unable to find AOT snapshot for dartdev`
  - fallback `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart` passed
  - `dart run tooling/validate_workspace_hygiene.dart` hit the same AOT issue
  - fallback `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart` passed
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - PASS
  - wrapper suite: `58 passed`
  - `compileall` passed
  - `tests/test_gmail_review_state.py`: `1 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - both Dart validators again hit the known `dartdev` AOT issue and then passed via the direct Dart fallback
