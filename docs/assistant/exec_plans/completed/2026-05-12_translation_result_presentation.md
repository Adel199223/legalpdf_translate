# Translation Result Presentation

Status: Completed 2026-05-12

## Goal and Non-Goals

Move translation result-card state shaping out of `translation.js` into a pure browser presentation module. Keep the existing safe DOM renderer, translation routes, payloads, selectors, Gmail/native-host behavior, submitted values, and recovery semantics unchanged.

This does not change backend APIs, live Gmail/OAuth/native-host behavior, translation execution, PDF/DOCX generation, numeric mismatch warnings, or result-card DOM structure.

## Scope

In scope:
- Create `src/legalpdf_translate/shadow_web/static/translation_result_presentation.js`.
- Export pure helpers for translation result-card presentation, including the existing recovery-state derivation used by the card.
- Update `translation.js` so `renderTranslationResultCard(...)` gathers coordinator state, calls the builder, and passes the shaped card to `renderTranslationResultCardInto(...)`.
- Preserve `deriveTranslationRecoveryState(...)` as an import/re-export compatible interface for existing tests and callers.
- Add ESM probe, ownership, safe-rendering, and static asset coverage.

Out of scope:
- Live Gmail testing.
- Route, selector, backend payload, submitted value, extension, or native-host contract changes.
- Refactoring translation job polling, diagnostics slots, numeric mismatch warnings, source-card presentation, or completion drawer presentation.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_translation_result_presentation`
- Branch name: `codex/translation-result-presentation`
- Base branch: `main`
- Base SHA: `4cc0da6d0c1317aed8fb07313ade91cb34bec655`
- Target integration branch: `main`
- Browser smoke mode: `shadow` with isolated workspace data only.

## Interfaces and Contracts Affected

- Internal browser static module interface: new `translation_result_presentation.js`.
- Internal coordinator/renderer contract: `renderTranslationResultCard(...)` will call a builder and continue passing card objects to `renderTranslationResultCardInto(...)`.
- Existing exported `deriveTranslationRecoveryState(...)` remains available from `translation.js`.
- No public API, selector, payload, route, Gmail/native-host, or extension contract changes.

## File-by-File Implementation Steps

1. `tests/test_translation_result_presentation.py`
   - Add ESM probe coverage for empty, prepared Gmail launch, source-ready, analyze completed, rebuild completed, translate completed with raw technical status fallback, auth failure, recovery failure/cancelled/advisor, malicious text, and null-safe defaults.
2. `tests/test_shadow_web_api.py`
   - Add ownership coverage proving the new module exports the builder/recovery helper, is pure, avoids DOM/rendering, and `translation.js` imports/calls it.
   - Update translation result-card safe-rendering contract to expect shaped-card rendering in the coordinator.
   - Extend the versioned static asset graph to serve `translation_result_presentation.js`.
3. `src/legalpdf_translate/shadow_web/static/translation_result_presentation.js`
   - Implement pure result-card builders preserving current copy, labels, tones, summary lines, auth failure guidance, recovery guidance, and raw technical text fallback.
4. `src/legalpdf_translate/shadow_web/static/translation.js`
   - Import the builder/recovery helper.
   - Replace inline result-card shaping in `renderTranslationResultCard(...)` with a builder call.
   - Re-export `deriveTranslationRecoveryState(...)` for existing tests and callers.

## Tests and Acceptance Criteria

Baseline:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_result_card_ui_module_centralizes_translation_result_card_renderer tests/test_translation_recovery_state.py`

RED target before implementation:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_result_presentation.py::test_translation_result_presentation_builds_translation_result_cards tests/test_shadow_web_api.py::test_translation_result_presentation_module_owns_result_card_state`

Post-implementation:
- RED target passes.
- Static asset graph test passes.
- Focused browser/Gmail/translation suite:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow browser smoke on port `8888` verifies page identity, nonblank content, no framework overlay, console health, screenshot evidence, Translation tab interaction, and safe inert rendering of malicious result-card text.

## Validation Log

- Baseline passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_result_card_ui_module_centralizes_translation_result_card_renderer tests/test_translation_recovery_state.py`
  -> `2 passed`.
- Confirmed RED before implementation:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_result_presentation.py::test_translation_result_presentation_builds_translation_result_cards tests/test_shadow_web_api.py::test_translation_result_presentation_module_owns_result_card_state`
  failed because `translation_result_presentation.js` did not exist and `translation.js` had not imported/called it yet.
- Post-implementation RED target passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_translation_result_presentation.py::test_translation_result_presentation_builds_translation_result_cards tests/test_shadow_web_api.py::test_translation_result_presentation_module_owns_result_card_state`
  -> `2 passed`.
- Adjacent/static/recovery tests passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_result_card_ui_module_centralizes_translation_result_card_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_translation_result_presentation.py tests/test_translation_recovery_state.py`
  -> `4 passed`.
- Focused browser/Gmail/translation suite passed:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_translation_recovery_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  -> `228 passed in 184.90s`.
- Full validation passed:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`.
  The wrapper reported the known `dart run ...` AOT snapshot issue and direct-Dart fallback success for docs validation and workspace hygiene.
- Shadow smoke launched from this worktree on port `8888` with workspace `translation-result-presentation-smoke`.
  Browser plugin connection was attempted first and failed with `No active Codex browser pane available`; local Playwright fallback verified page identity, nonblank content, no framework overlay, clean console, screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\legalpdf_translation_result_presentation_smoke.png`, Translation tab interaction, and safe inert rendering for malicious translation result-card text.

## Rollout and Fallback

Publish through a ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, merge conflicts appear, or required checks remain unexpectedly pending.

Fallback is to leave the branch/worktree intact and report the blocker; do not direct-push to `main`.

## Risks and Mitigations

- Risk: changing translation result-card copy or recovery guidance.
  Mitigation: ESM probes assert existing card shapes for each status path.
- Risk: weakening safe rendering.
  Mitigation: renderer stays in `result_card_ui.js`; malicious text remains text-only in probes and browser smoke.
- Risk: moving recovery helper breaks existing imports.
  Mitigation: re-export `deriveTranslationRecoveryState(...)` from `translation.js` and keep focused recovery tests.
- Risk: Browser plugin runtime instability.
  Mitigation: attempt Browser first for local smoke, then use local Playwright fallback only if Browser invocation fails and record the reason.
