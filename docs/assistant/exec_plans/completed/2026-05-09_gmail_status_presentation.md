# Gmail Status Presentation

## Goal and Non-Goals
Extract Gmail home/session panel status copy shaping from `gmail.js` into pure presentation builders while preserving the current DOM renderer, routes, IDs, event listeners, datasets, payloads, Gmail/native-host behavior, and safe text rendering.

Non-goals: no Gmail backend changes, no live Gmail/OAuth/native-host testing, no public contract changes, and no redesign of the review/session surfaces.

## Scope
In scope:
- Add pure status presentation builders to `src/legalpdf_translate/shadow_web/static/gmail_stage_presentation.js`.
- Update `src/legalpdf_translate/shadow_web/static/gmail.js` so it gathers coordinator state and delegates status message shaping.
- Add/adjust contract and ESM probe coverage for recovered-result, active-stage, click-diagnostic, default-review, inactive-session, and null-safe cases.
- Validate with focused Gmail/browser tests, full dev validation, shadow Browser smoke, then PR-first publish/merge.

Out of scope:
- Live Gmail interaction.
- Native host or extension contract changes.
- Route, payload, selector, submitted value, or backend API changes.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_status_presentation`
- Branch name: `codex/gmail-status-presentation`
- Base branch: `origin/main`
- Base SHA: `25377af965a2ff5540b4db69b059c37501e9e0ce`
- Target integration branch: `main`
- Canonical build status: feature worktree is noncanonical; canonical main remains `C:\Users\FA507\.codex\legalpdf_translate`.

## Interfaces, Types, and Contracts Affected
- Browser static asset graph gains additional exports from existing `gmail_stage_presentation.js`.
- No backend route, API payload, submitted form value, selector, Gmail/native-host, or extension contract changes.
- Status strings remain rendered through existing safe text insertion paths.

## File-by-File Implementation Steps
- `tests/test_shadow_web_api.py`: add status-presentation contract checks, ESM cases, and static asset export assertions.
- `tests/test_gmail_review_state.py`: add ESM probe assertions for the new pure status builders.
- `src/legalpdf_translate/shadow_web/static/gmail_stage_presentation.js`: add pure `buildGmailHomeStatusPresentation(...)` and `buildGmailSessionPanelStatusPresentation(...)`.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import builders and use them from `gmailHomeStatusMessage()` / `renderGmailBootstrap()`.

## Tests and Acceptance Criteria
- Targeted tests first failed for the expected missing `buildGmailPanelStatusPresentation` export before production implementation.
- Targeted green validation passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_stage_presentation_module_derives_stage_and_home_cta_state tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules`
- Focused browser/Gmail suite passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `197 passed`.
- Full validation passed:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: wrapper completed successfully; known `dart run ...` / `Unable to find AOT snapshot for dartdev` issue appeared and direct-Dart fallback passed for agent docs and workspace hygiene.
- Browser smoke from this worktree on port `8888` at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-status-smoke#gmail-intake` passed: page identity, nonblank content, no framework overlay, console health, demo attachment load, review drawer, PDF preview, and session/status surfaces verified without live Gmail. Browser screenshot capture timed out, so screenshot evidence was captured with Playwright fallback at `C:\Users\FA507\AppData\Local\Temp\gmail_status_smoke_ready.png`.

## Rollout and Fallback
Publish via ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending. If the extraction regresses any contract test, revert only this branch's changes and keep canonical `main` untouched.

## Risks and Mitigations
- Risk: accidentally changing user-visible status copy. Mitigation: ESM probes assert the exact existing strings for key states.
- Risk: weakening safe rendering. Mitigation: pure builders avoid DOM APIs and existing renderers continue to use safe text writes.
- Risk: worktree drift. Mitigation: branch is based on latest `origin/main` and publish happens through PR-first merge.

## Assumptions and Defaults
- No live Gmail testing is in scope.
- Shadow mode is sufficient for browser smoke.
- User authorization covers PR creation and merge after green CI.

## Completion Notes
- Implementation complete on `codex/gmail-status-presentation`.
- Read-only code review found no issues.
- Ready for scoped commit, ready PR, CI wait, merge, canonical main fast-forward, and feature worktree cleanup.
