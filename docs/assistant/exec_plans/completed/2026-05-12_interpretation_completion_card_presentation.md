# Interpretation Completion Card Presentation

## Goal and Non-Goals

Extract the interpretation completion-card presentation shaping from `app.js` into the pure interpretation review state module. Keep the current safe DOM renderer, route flow, Gmail/native-host contracts, payload handling, IDs, selectors, and submitted values unchanged.

This does not change live Gmail behavior, OAuth/native-host behavior, backend routes, or finalization payload shapes.

## Scope

In scope:
- Add a pure `buildInterpretationCompletionCardPresentation(...)` export to `interpretation_review_state.js`.
- Update `renderInterpretationCompletionCard(...)` in `app.js` to gather coordinator state, call the builder, and pass the resulting card data to `renderInterpretationCompletionCardInto(...)`.
- Add ESM and static contract coverage.

Out of scope:
- Gmail live/OAuth/native-host testing.
- Renderer rewrites beyond passing the existing data shape.
- Backend API or route changes.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_interpretation_completion_card`
- Branch name: `codex/interpretation-completion-card-presentation`
- Base branch: `main`
- Base SHA: `40464b4a7884c3ebcd323a8e504b7ee0c480a8a3`
- Target integration branch: `main`
- Canonical build status: feature worktree only; browser smoke must use shadow mode with isolated workspace data.

## Interfaces and Contracts Affected

- Internal browser static module interface: `interpretation_review_state.js` gains `buildInterpretationCompletionCardPresentation`.
- Existing renderer input shape for `renderInterpretationCompletionCardInto(...)` remains `{ title, message, chip, docxPath, pdfPath, caseLocation, serviceLocation }`.
- No public backend routes, payloads, selectors, submitted values, Gmail/native-host, or extension contracts change.

## File-by-File Implementation Steps

1. `tests/test_interpretation_review_state.py`
   - Add ESM probe coverage for completion-card states: null-safe, hidden/not completed, ok draft, local-only with prereq message, draft unavailable/failure, session-derived success/failure, paths, and malicious text as inert data.
2. `tests/test_shadow_web_api.py`
   - Add contract coverage proving the builder is exported, pure, called by `app.js`, and that the targeted inline completion-card decision literals are removed from `app.js`.
   - Extend the versioned static asset graph assertion for `interpretation_review_state.js`.
3. `src/legalpdf_translate/shadow_web/static/interpretation_review_state.js`
   - Implement the pure builder using the same existing title/message/path/chip rules.
4. `src/legalpdf_translate/shadow_web/static/app.js`
   - Import the builder and simplify `renderInterpretationCompletionCard(...)` to coordination plus safe renderer call.

## Tests and Acceptance Criteria

RED target before implementation:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py::test_interpretation_review_state_builds_completion_card_presentation tests/test_shadow_web_api.py::test_interpretation_review_state_module_owns_completion_card_presentation`

Post-implementation targets:
- The RED target above passes.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py tests/test_interpretation_review_state.py`
- Full validation:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow browser smoke on port `8888` verifies page identity, nonblank content, no framework overlay, console health, screenshot evidence, and normal interpretation review/preview interaction without live Gmail.

Executed outcomes:
- RED target failed before implementation because `buildInterpretationCompletionCardPresentation` was missing.
- RED target passed after implementation: `2 passed`.
- Static asset graph passed: `1 passed`.
- Adjacent interpretation review-state and safe-rendering checks passed.
- Focused browser/Gmail/interpretation suite passed: `228 passed`.
- `validate_dev.ps1 -Full` passed. The known `dartdev` AOT snapshot issue appeared, and the wrapper's direct-Dart fallback succeeded for agent docs and workspace hygiene validation.
- Shadow browser app launched from this feature worktree on port `8888`.
- Browser plugin path was attempted first and failed with `No active Codex browser pane available`; local Playwright-backed fallback verified `http://127.0.0.1:8888/?mode=shadow&workspace=interpretation-completion-card-smoke#new-job`.
- Smoke evidence: title `LegalPDF Translate`, nonblank content, no framework overlay, no console warnings/errors, interpretation review drawer opened, case details were present, and `#interpretation-completion-card` stayed `result-card hidden` in the incomplete state.

## Rollout and Fallback

Publish through a ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, conflicts appear, or required checks stay unexpectedly pending.

Fallback is to keep the branch/worktree intact and report the blocker; do not direct-push to `main`.

## Risks and Mitigations

- Risk: subtle text or chip behavior changes in completed Gmail interpretation state.
  Mitigation: ESM probes assert existing status/title/message/chip/path rules exactly.
- Risk: weakening safe rendering.
  Mitigation: builder remains pure and renderer ownership stays in `interpretation_result_ui.js`; malicious text tests treat strings as data only.
- Risk: Browser plugin runtime instability.
  Mitigation: attempt Browser first for local smoke, then use the existing local Playwright fallback only if Browser invocation fails and record the reason.

## Assumptions and Defaults

- No live Gmail testing is in scope.
- The new export is internal to static browser modules.
- User has authorized the PR-first publish and merge flow for this next modernization step.
- Status: complete; move to `completed/` before commit.
