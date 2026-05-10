# Gmail Confirmation Gate Presentation

## Goal and non-goals
- Move Gmail translation confirmation gate message/state shaping out of `gmail.js` into a pure session presentation helper.
- Preserve existing Gmail confirmation behavior, thrown messages, routes, payloads, selectors, submitted values, Gmail/native-host behavior, and safe rendering.
- Keep the slice narrow: no live Gmail, OAuth, native-host, backend API, renderer, or finalization workflow changes.

## Scope
- In scope:
  - Add a pure builder for the Gmail translation confirmation gate.
  - Update `confirmCurrentTranslation()` to gather coordinator state, call the builder, and keep the existing throw/fetch side effects.
  - Add contract and ESM probe coverage for Arabic review, failed/cancelled/recovery, rebuild/no-save-seed, missing job id, success, malicious text, and null-safe defaults.
  - Validate with targeted tests, focused browser/Gmail suite, full dev validation, and shadow-only Browser smoke.
- Out of scope:
  - Live Gmail testing, real drafts, OAuth, native-host registration, extension handoff, backend route or payload changes, and UI renderer changes.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_confirmation_gate_presentation`
- Branch name: `codex/gmail-confirmation-gate-presentation`
- Base branch: `main`
- Base SHA: `d46f60d9fc0f29105de2704b54214c355e82f88e`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow browser mode only for GUI smoke.

## Interfaces/types/contracts affected
- No public backend route, payload, selector, submitted value, Gmail/native-host, or extension contract changes are intended.
- `gmail_session_presentation.js` gains an internal static-browser export:
  - `buildGmailTranslationConfirmationGatePresentation({ translationUi, jobId })`
- Existing coordinator behavior remains:
  - blocked confirmation throws `Error(message)`
  - successful confirmation posts the same `job_id`, completion key, form values, and row id to `/api/gmail/batch/confirm-current`

## Implementation steps
- `tests/test_shadow_web_api.py`
  - Add the failing confirmation gate presentation contract and ESM probes.
  - Extend the versioned static asset test for the new export.
- `src/legalpdf_translate/shadow_web/static/gmail_session_presentation.js`
  - Add the pure confirmation gate builder.
  - Keep the builder data-only, with no DOM or renderer references.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Import the builder.
  - Replace inline confirmation gate message shaping in `confirmCurrentTranslation()` with a builder call.

## Tests and acceptance criteria
- RED:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_translation_confirmation_gate_state`
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_translation_confirmation_gate_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke:
  - Launch shadow preview on port `8888`.
  - Verify Gmail intake page identity, nonblank content, no framework overlay, console health, screenshot evidence, demo attachment load, and normal review/preview interaction.

## Rollout and fallback
- Publish through a ready GitHub PR after local validation and Browser smoke.
- Merge only after required checks are green.
- If validation fails, keep the branch open and fix before publishing or merging.
- Fallback is to revert the helper import/call and leave the existing inline confirmation gate unchanged.

## Risks and mitigations
- Risk: blocked confirmation messages change accidentally.
  - Mitigation: ESM probes assert exact current messages for each gate path.
- Risk: coordinator stops sending the correct job id.
  - Mitigation: builder returns the normalized job id and tests assert it is preserved.
- Risk: live Gmail impact.
  - Mitigation: smoke uses `mode=shadow` and demo attachments only.

## Assumptions/defaults
- Null or missing `translationUi` is treated as not confirmable unless a job id and durable save seed are explicitly present.
- No docs sync is needed for this internal presentation-only extraction unless later validation reveals user-facing docs drift.

## Closeout results
- RED confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_translation_confirmation_gate_state`
  - Result: failed for the intended missing `buildGmailTranslationConfirmationGatePresentation` export before implementation.
- Targeted GREEN:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_translation_confirmation_gate_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - Result: `2 passed`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `205 passed`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed.
  - Known Dart launcher issue observed for `dart run ...`: `Unable to find AOT snapshot for dartdev`.
  - Direct-Dart fallback succeeded for agent docs validation and workspace hygiene validation.
- Browser smoke:
  - Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_confirmation_gate_presentation`
  - Branch: `codex/gmail-confirmation-gate-presentation`
  - URL: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-confirmation-gate-smoke-fallback#gmail-intake`
  - Result: passed with local Playwright fallback after the Browser plugin refused to allocate an owned disposable in-app tab.
  - Verified page identity, nonblank hydrated Gmail intake content, no framework overlay, empty console warnings/errors, demo attachment load, Preview opening, preview status, and PDF canvas content for `demo-gmail-review.pdf`.
  - Screenshot evidence saved outside the repo:
    - `C:\Users\FA507\AppData\Local\Temp\gmail-confirmation-gate-smoke.png`
    - `C:\Users\FA507\AppData\Local\Temp\gmail-confirmation-gate-smoke-preview.png`
  - No live Gmail, OAuth, native-host, extension handoff, draft, or private mailbox flow was touched.
