# Translation Source Card Presentation

## Goal And Non-Goals

Extract New Job translation source-card presentation shaping from `translation.js` into a pure static presentation module while preserving the existing safe DOM renderer, field IDs, routes, payloads, Gmail-prepared launch behavior, browser PDF staging, and submitted values.

This does not change upload/staging behavior, translation start rules, Gmail/native-host behavior, backend APIs, or live Gmail flows.

## Scope

In scope:
- Add `src/legalpdf_translate/shadow_web/static/translation_source_presentation.js`.
- Export `buildTranslationSourceCardPresentation(...)`.
- Update `translation.js` so `renderTranslationSourceCard()` gathers coordinator state and calls the builder before `renderTranslationSourceCardInto(...)`.
- Keep `translation_ui.js` as the safe DOM writer and leave its renderer contract unchanged.
- Add focused ESM/static tests for the builder and coordinator contract.
- Run targeted, focused, full validation, and shadow Browser smoke.

Out of scope:
- Translation source upload rules.
- Translation action button enablement logic.
- Gmail prepare/restore/preview flows.
- Live Gmail/OAuth/native-host testing.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_translation_source_presentation`
- Branch name: `codex/translation-source-presentation`
- Base branch: `main`
- Base SHA: `85857433e6ba90fa4e43514718f826189aca6988`
- Target integration branch: `main`
- Runtime mode for browser validation: noncanonical shadow mode only.

## Interfaces And Contracts

Affected browser modules:
- `src/legalpdf_translate/shadow_web/static/translation.js`
- `src/legalpdf_translate/shadow_web/static/translation_ui.js`
- `src/legalpdf_translate/shadow_web/static/translation_source_presentation.js`
- `tests/test_shadow_web_api.py`

Contracts preserved:
- Existing source card DOM IDs remain unchanged.
- Existing `renderTranslationSourceCardInto(...)` presentation shape remains unchanged.
- Dynamic text remains inserted through the existing safe renderer.
- Gmail-prepared attachments still populate the New Job source card and Start Translate readiness without route or payload changes.

## Implementation Steps

1. Add failing tests expecting `translation_source_presentation.js` and `buildTranslationSourceCardPresentation(...)`.
2. Update the source-card renderer contract test so `translation.js` must call the builder and no longer shape copy/status/chip text inline.
3. Add static asset graph coverage for the new module export.
4. Implement the pure builder from the current inline source-card presentation logic.
5. Update `translation.js` to import the builder, gather only source/coordinator state, and pass the returned object into `renderTranslationSourceCardInto(...)`.
6. Run targeted, focused, and full validation.
7. Run Browser shadow smoke on port `8888`.
8. Move this ExecPlan to `completed/` before commit.

## Tests And Acceptance Criteria

Targeted red/green tests:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_translation_source_presentation_module_builds_source_card_state tests/test_shadow_web_api.py::test_translation_ui_module_centralizes_source_card_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`

Focused suite:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`

Full validation:
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow preview on port `8888`.
- Open `http://127.0.0.1:8888/?mode=shadow&workspace=translation-source-smoke#new-job`.
- Verify page identity, nonblank content, no framework overlay, console health, source card/default state, and safe Gmail-prepared handoff surface using shadow/demo-only state where applicable.

## Rollout And Fallback

Publish via ready PR after validation. Stop before merge if GitHub auth fails, PR creation fails, CI is red, merge conflicts appear, or required checks remain unexpectedly pending.

Fallback is reverting this narrow PR; behavior should be unchanged because source-card presentation shaping only moves modules.

## Risks And Mitigations

- Risk: New Job source card copy drifts. Mitigation: ESM tests cover empty, manual-ready, uploading replacement, manual error, current job, Gmail-prepared, non-Gmail prepared, malicious text, and fallback target cases.
- Risk: Gmail-prepared launch readiness regresses. Mitigation: coordinator contract tests preserve current prepared launch inputs and builder arguments.
- Risk: unsafe rendering regression. Mitigation: renderer remains text-safe; tests assert no `innerHTML` writes.

## Assumptions

- No live Gmail testing is in scope.
- No docs sync is needed for this internal frontend module split.
- The PR should be ready and merged after green checks under the user's standing authorization.

## Completion Notes

- Added `translation_source_presentation.js` with `buildTranslationSourceCardPresentation(...)`.
- Updated `translation.js` so `renderTranslationSourceCard()` gathers coordinator state and delegates source-card shaping to the pure builder.
- Kept `translation_ui.js` unchanged as the safe DOM writer.
- Confirmed targeted red before implementation on the missing module/export/static asset.
- Targeted tests passed: `3 passed`.
- Focused browser/Gmail suite passed: `195 passed`.
- Full validation passed. The known `dart run` AOT launcher issue appeared for agent-docs and workspace-hygiene checks; direct-Dart fallback succeeded both times.
- Shadow Browser/Playwright smoke on port `8888` verified New Job identity, nonblank source-card content, no framework overlay, clean console on reload, route interaction Recent Work -> New Job, source-card `empty` state, and no live Gmail/OAuth/native-host flow.
- In-app Browser DOM/console checks worked, but Browser screenshot and click CDP calls timed out; Playwright fallback supplied the interaction and screenshot evidence. Visual evidence saved at `C:\Users\FA507\AppData\Local\Temp\legalpdf_translation_source_presentation_smoke.png`.
