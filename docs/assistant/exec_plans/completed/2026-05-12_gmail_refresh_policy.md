# Gmail Refresh Policy Helpers

## Goal and Non-Goals

Extract Gmail warmup/passive refresh scheduling decisions from `gmail.js` into a pure static module. Preserve all current refresh timing values, DOM behavior, routes, payloads, selectors, Gmail/native-host behavior, and silent auto-refresh failure handling.

Non-goals: change Gmail bootstrap fetching, panel rendering, diagnostics, route IDs, backend APIs, live Gmail behavior, or browser UI layout.

## Scope

In scope:
- Add `gmail_refresh_policy.js` with pure helpers for warmup status classification, warmup polling scheduling decisions, and passive refresh scheduling decisions.
- Update `gmail.js` so it gathers coordinator state, calls the policy helpers, then performs the existing timer/refresh side effects.
- Add ESM contract coverage and static asset graph coverage.

Out of scope:
- Live Gmail/OAuth/native-host testing.
- Changing refresh delays, cooldowns, or timer replacement semantics.
- Changing stable-workspace detection semantics.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_refresh_policy`
- Branch name: `codex/gmail-refresh-policy`
- Base branch: `main`
- Base SHA: `57d040b8dfa9909f2419f3a35a6a79aef6ec1771`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use shadow browser mode only.

## Interfaces/Types/Contracts Affected

- New internal static browser module: `src/legalpdf_translate/shadow_web/static/gmail_refresh_policy.js`
- Existing internal imports only. No backend routes, request/response payloads, submitted values, selector names, DOM IDs, Gmail/native-host contracts, or extension contracts change.
- No dynamic text rendering is introduced.

## File-by-File Implementation Steps

1. Add a focused contract/probe test in `tests/test_shadow_web_api.py`, then confirm RED before production code.
2. Add `gmail_refresh_policy.js` with pure exports:
   - `GMAIL_REFRESH_POLICY_DEFAULTS`
   - `isGmailWarmupPendingStatus`
   - `buildGmailWarmupPollingDecision`
   - `buildGmailPassiveRefreshDecision`
3. Update `gmail.js` to import the helpers and route warmup/passive scheduling through them while keeping timer side effects local.
4. Update static asset graph coverage for `gmail_refresh_policy.js`.
5. Run targeted, focused, full validation, and shadow smoke.
6. Mark complete and move this plan to `completed/` before commit.

## Tests and Acceptance Criteria

- Targeted:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_refresh_policy_module_builds_refresh_scheduling_decisions`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow smoke on port `8888`:
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-refresh-policy-smoke#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, demo attachment load, and normal review/preview interaction. Do not touch live Gmail.

## Rollout and Fallback

Publish via ready PR after validation. If CI fails, conflicts appear, or GitHub auth is unavailable, stop before merge. Fallback is to revert this internal policy extraction before merge.

## Risks and Mitigations

- Risk: changing refresh cadence. Mitigation: keep existing timing constants and assert exact delay calculations in ESM probes.
- Risk: timer side effects leak into pure code. Mitigation: contract test forbids DOM, window timers, fetches, renderers, and diagnostics calls in the policy module.
- Risk: passive refresh accidentally starts during stable workspace states. Mitigation: test stable, cooldown, inactive view, and warmup-delegation decisions.

## Assumptions/Defaults

- No live Gmail testing is in scope.
- User authorized PR-first publish/merge flow for the next recommended modernization slice.
- Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.

## Completion Evidence

- RED confirmed: `test_gmail_refresh_policy_module_builds_refresh_scheduling_decisions` failed before implementation because `gmail_refresh_policy.js` did not exist.
- Targeted refresh-policy contract/probe passed: `1 passed`.
- Static asset graph passed: `1 passed`.
- Focused browser/Gmail suite passed: `220 passed`.
- Full validation passed:
  - wrapper suite: `216 passed`
  - `compileall src tests`: passed
  - `tests/test_gmail_review_state.py`: `2 passed`
  - `tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`: `5 passed, 9 deselected`
  - Known Dart AOT launcher issue appeared for both Dart validators; direct-Dart fallback succeeded for agent docs and workspace hygiene.
- Shadow smoke on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-refresh-policy-smoke#gmail-intake` passed:
  - page identity: `LegalPDF Translate`
  - nonblank Gmail intake content rendered
  - no framework overlay observed
  - console warnings/errors: `0`
  - demo attachment loaded as `demo-gmail-review.pdf`
  - preview opened and generated `gmail-preview-canvas` at `827x1070`
  - no live Gmail, OAuth, native-host, or real drafts touched

Status: complete.
