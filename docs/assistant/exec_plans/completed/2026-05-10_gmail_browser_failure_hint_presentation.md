# Gmail Browser Failure Hint Presentation

## Goal And Non-Goals

Extract Gmail browser/PDF failure hint copy from `gmail.js` into a pure report presentation helper while preserving existing diagnostics behavior, failure-report payloads, safe rendering, and Gmail contracts.

Non-goals: no backend route, payload, submitted value, DOM ID, dataset, Gmail/native-host, OAuth, live Gmail, or failure-report context changes.

## Scope

In scope:
- Add `buildGmailBrowserFailureHintPresentation({ error, fallbackMessage })` in `gmail_report_presentation.js`.
- Move the current browser PDF worker/module failure hint derivation out of `gmail.js`.
- Update `gmail.js` so failure handlers call the report presentation helper and no longer import `browserPdfDiagnosticsFromError` directly.
- Add red-first ESM/contract/static asset coverage.
- Validate with targeted tests, focused browser/Gmail suite, full validation, and shadow Browser smoke.
- Publish through a ready PR and merge after green checks.

Out of scope:
- Live Gmail testing, OAuth testing, native-host testing, API/report payload changes, and unrelated UI refactors.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_browser_failure_hint`
- Branch name: `codex/gmail-browser-failure-hint-presentation`
- Base branch: `main`
- Base SHA: `2b14c858348262d162ce08d9e798e4dd9518e2f7`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; shadow-mode browser validation only.

## Interfaces, Types, And Contracts Affected

- `buildGmailFailureReportActionPresentation(...)` and `buildGmailFinalizationReportActionPresentation(...)` keep their existing shapes.
- New helper returns a plain string hint only; it must not build DOM or report payloads.
- `gmail_report_context.js` continues to own report context/payload shaping.
- Existing diagnostics slots, button IDs, datasets, routes, Gmail/native-host behavior, and safe text rendering remain unchanged.

## File-By-File Implementation Steps

- `src/legalpdf_translate/shadow_web/static/gmail_report_presentation.js`: import `browserPdfDiagnosticsFromError` from `browser_pdf.js` and export `buildGmailBrowserFailureHintPresentation(...)`.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import the new report presentation helper, remove direct `browserPdfDiagnosticsFromError` import, delete local `gmailFailureHint(...)`, and replace call sites with the helper.
- `tests/test_shadow_web_api.py`: add failing export/import, ESM behavior, ownership, and static asset assertions first.
- `docs/assistant/exec_plans/active/2026-05-10_gmail_browser_failure_hint_presentation.md`: record progress, validation, review, and move to `completed/` before commit.

## Tests And Acceptance Criteria

Red first:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py -k "gmail_report_presentation or static_route_serves_current_browser_asset_graph"`
- Result: failed before implementation because `buildGmailBrowserFailureHintPresentation(...)` did not exist and the static asset did not export it.

After implementation:
- Same targeted tests pass.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Result: targeted report/static coverage passed, focused browser/Gmail suite passed with `200 passed`, and full validation passed. The full validation wrapper hit the known `dart run` AOT launcher issue, then the direct-Dart fallback passed for agent-doc and workspace-hygiene validation.

Post-PR CI follow-up:
- GitHub Actions initially failed `tests/test_action_feedback_browser_state.py::test_gmail_preview_actions_delegate_remaining_action_failure_feedback` because that full-suite contract still expected the removed local `gmailFailureHint(error, message)` helper.
- Updated the action-feedback contract to assert delegation through `buildGmailBrowserFailureHintPresentation(...)`.
- Re-ran `.\.venv311\Scripts\python.exe -m pytest -q tests/test_action_feedback_browser_state.py::test_gmail_preview_actions_delegate_remaining_action_failure_feedback`, `.\.venv311\Scripts\python.exe -m pytest -q tests/test_action_feedback_browser_state.py`, and `.\.venv311\Scripts\python.exe -m pytest -q`; result: `1433 passed`.

Browser smoke:
- Launch shadow app on port `8888`.
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-browser-failure-hint-smoke#gmail-intake`.
- Load demo attachments, confirm review/preview surfaces remain stable, console health is clean, failure-report action remains hidden unless an actual browser preview/prepare failure occurs, and no live Gmail/OAuth/native-host flow is touched.
- Result: launched the shadow app from this feature worktree on port `8888` and verified isolated workspace `gmail-browser-failure-hint-smoke-clean`. Browser confirmed page identity (`LegalPDF Translate`), meaningful Gmail demo review content, no framework overlay, clean console, preview opened for `demo-gmail-review.pdf`, and `Generate Failure Report` remained hidden in the clean preview path. In-app Browser screenshot capture timed out through CDP, so DOM/console/interaction evidence is the smoke artifact. An optional shadow prepare attempt was not used as acceptance evidence because the demo account-resolution path returned a Gmail validation diagnostic unrelated to this presentation-only change.

## Rollout And Fallback

Publish flow after validation:
- Stage only intended files.
- Commit `Extract Gmail browser failure hint presentation`.
- Push `codex/gmail-browser-failure-hint-presentation`.
- Create ready PR `[codex] Extract Gmail browser failure hint presentation`.
- Wait for green CI, merge normally, fast-forward canonical `main`, prune refs, and remove the feature worktree only after `main` contains the merge.

Fallback: stop before merge if auth fails, PR creation fails, CI is red, conflicts appear, or required checks remain unexpectedly pending.

## Risks And Mitigations

- Risk: exact browser PDF diagnostic hint copy regresses. Mitigation: ESM probes for worker/module phases, attempted URL, raw error, and fallback cases.
- Risk: import cycle between `browser_pdf.js` and report presentation. Mitigation: verify `browser_pdf.js` does not import Gmail modules and run ESM/static asset tests.
- Risk: failure report payload construction changes accidentally. Mitigation: do not touch `gmail_report_context.js`; run existing report context and browser/Gmail suites.

## Assumptions And Defaults

- No live Gmail/OAuth/native-host testing is in scope.
- The helper is pure and returns text only.
- The feature PR should be ready for review/merge after validations pass.
