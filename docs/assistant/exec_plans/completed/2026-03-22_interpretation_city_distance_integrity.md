# Interpretation City and Distance Integrity

## Goal and non-goals
- Goal: stop browser/Gmail interpretation exports from generating honorários with invalid cities or `0 km`, and expose enough structured validation state for the browser to recover in a Qt-like way.
- Goal: add shared interpretation city-reference bootstrap data so browser review can move to guarded city selection in later stages.
- Non-goal: redesign the full browser interpretation UI in this stage.
- Non-goal: mutate existing saved live data or remove prior wrong artifacts in this stage.

## Scope
- In scope:
  - shared interpretation validation and city-reference helpers
  - browser API validation payload contract
  - browser bootstrap reference payload
  - targeted tests for shared service, browser API, and Gmail finalization propagation
- Out of scope:
  - browser city-picker UI
  - browser add-city modal flow
  - Qt widget/autofill parity cleanup
  - live artifact regeneration

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/gmail-review-parity-browser`
- Base branch: `feat/gmail-review-parity-browser`
- Base SHA: `e990ef3fca7aad1ed29d4f121bf05b405f37cf31`
- Target integration branch: `feat/gmail-review-parity-browser`
- Canonical build status: noncanonical feature branch carrying the accepted live browser/Gmail parity work-in-progress

## Interfaces, types, and contracts affected
- `interpretation_service` will expose:
  - structured `InterpretationValidationError`
  - browser bootstrap interpretation reference payload
- Browser 422 responses for interpretation export/save/Gmail finalization will include structured validation payloads when raised from interpretation validation.
- `save_interpretation_row` will stop silently growing `vocab_cities` from ordinary payload saves.

## File-by-file implementation steps
- `src/legalpdf_translate/interpretation_service.py`
  - add shared city-reference and validation helpers
  - add structured validation error type
  - validate/export/save interpretation city and distance integrity
  - include interpretation reference payload in shadow bootstrap
- `src/legalpdf_translate/joblog_flow.py`
  - add a narrow opt-out so browser save flow can skip silent city-vocabulary growth
- `src/legalpdf_translate/shadow_web/app.py`
  - return structured validation payloads for interpretation save/export and Gmail interpretation finalization
- `tests/test_shadow_runtime_service.py`
  - cover interpretation reference bootstrap, city-vocab non-growth, and export validation failures
- `tests/test_shadow_web_api.py`
  - cover structured browser validation payloads and bootstrap reference exposure
- `tests/test_gmail_browser_service.py`
  - cover Gmail interpretation finalization propagation of shared validation failures

## Tests and acceptance criteria
- Shared service tests must prove:
  - `0 km` is rejected when transport sentence is enabled
  - unknown city is rejected before export
  - known-distance cities from profile data appear in bootstrap reference data
  - browser save flow no longer auto-adds cities to `vocab_cities`
- Browser API tests must prove:
  - interpretation bootstrap exposes city reference data
  - interpretation export returns structured validation JSON
  - Gmail interpretation finalize returns structured validation JSON

## Stage status
- Stage 1 complete.
- Stage 2 complete.
- Implemented in Stage 1:
  - structured `InterpretationValidationError`
  - shared interpretation city/distance validation for browser save/export and Gmail interpretation finalization
  - browser bootstrap `interpretation_reference` payload with `available_cities`, `travel_origin_label`, and known profile distances
  - browser save flow no longer silently grows `vocab_cities`
  - structured 422 validation payloads on interpretation save/export and Gmail interpretation finalization routes
- Implemented in Stage 2:
  - guarded browser city selectors replacing the raw free-text city inputs
  - browser-side city/distance guard-state helper in `shadow_web/static/interpretation_review_state.js`
  - explicit browser `Add city...` flow via `POST /api/interpretation/cities/add`
  - bounded browser city/distance dialog for explicit add-city and missing-distance confirmation
  - profile-aware browser reference merging so profile distance-map cities appear even when the sparse city vocab list does not contain them yet
  - inline browser recovery UI that blocks save/export/finalize until imported cities are confirmed or added
  - Qt-style saved-distance hinting and on-demand missing-distance prompt before browser save/export/Gmail finalize
- Deferred to Stage 3:
  - Qt autofill/add-city parity cleanup
  - live Gmail/browser replay and corrected artifact regeneration

## Rollout and fallback
- Stage 1 is intentionally backend-first and may surface validation errors before the browser UI gains the full correction flow.
- Stage 2 added guarded city selectors and the add-city/distance prompt flow so those errors are now recoverable in-product.
- If validation breaks an unexpected known-good case, fall back by checking the new structured error payload rather than weakening the `0 km` guard.

## Risks and mitigations
- Risk: backend validation may block current browser review flows before Stage 2 UI exists.
  - Mitigation: keep error payload structured and human-readable so the next stage can bind directly to it.
- Risk: changing save-row settings merge could affect other job-log vocab behavior.
  - Mitigation: scope the no-auto-grow change to `vocab_cities` for browser interpretation save flow only.
- Risk: live Gmail/browser flows may still carry stale exported artifacts from before the fix.
  - Mitigation: defer regeneration to Stage 3 and do not overwrite prior exports automatically.

## Assumptions and defaults
- Qt remains the source of truth for distance resolution semantics.
- Unknown imported cities should block export/finalization instead of being guessed.
- Profile travel-distance cities are valid selectable cities even if `vocab_cities` is sparse.
- Existing wrong files remain untouched until the final live-regeneration stage.

## Validation outcomes
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_runtime_service.py` -> PASS (`23 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_browser_service.py` -> PASS (`5 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_runtime_service.py tests/test_shadow_web_api.py tests/test_gmail_browser_service.py` -> PASS (`45 passed`)
- `dart run tooling/validate_agent_docs.dart` -> FAIL on pre-existing repo issue:
  - `AD046: docs/assistant/SESSION_RESUME.md points to a branch that does not exist in this repo: codex/browser-qt-parity-shell`
- Stage 2 validation:
  - `node --check src/legalpdf_translate/shadow_web/static/interpretation_review_state.js` -> PASS
  - `node --check src/legalpdf_translate/shadow_web/static/app.js` -> PASS
  - `node --check src/legalpdf_translate/shadow_web/static/gmail.js` -> PASS
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py` -> PASS (`1 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_runtime_service.py tests/test_shadow_web_api.py` -> PASS (`44 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)
- Stage 3 validation:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py -k "interpretation_city_combos_include_profile_distance_cities or interpretation_header_autofill_does_not_promote_unknown_city or interpretation_honorarios_rejects_zero_distance or honorarios_export_dialog_interpretation_rejects_zero_distance or interpretation_service_city_switches_to_saved_distance or interpretation_header_autofill_reveals_distinct_service_location or interpretation_save_persists_manual_distance_for_service_city or save_to_joblog_dialog_interpretation_photo_autofill_prompts_and_saves_distance"` -> PASS (`8 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_shadow_web_route_state.py` -> PASS (`4 passed`)
  - `node --check src/legalpdf_translate/shadow_web/static/app.js` -> PASS after the summary-card sync polish
  - `dart run tooling/automation_preflight.dart` -> PASS (`automation_host_selected=local`, `playwright_available=true`, `automation_browser_source=system`)
  - Live browser verification via Playwright against `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`:
    - compact Gmail home showed `Resume Current Step`
    - interpretation review opened with imported provisional `Camões` blocked behind guarded city selection
    - selecting `Beja` auto-filled `travel_km_outbound=39` with hint `Saved by city: 39 km one way.`
    - `Finalize Gmail Reply` remained blocked until city correction, then became enabled
    - summary cards now refresh to the corrected city instead of keeping the stale provisional value
  - Live artifact regeneration:
    - new DOCX: `C:\Users\FA507\Downloads\Requerimento_Honorarios_Interpretacao_305_23.2GCBJA_20260322_02.docx`
    - new PDF: `C:\Users\FA507\Downloads\Requerimento_Honorarios_Interpretacao_305_23.2GCBJA_20260322_02.pdf`
    - new Gmail interpretation session: `C:\Users\FA507\Downloads\_gmail_interpretation_sessions\gmail_interpretation_bcacafe1ff36\gmail_interpretation_session.json`
  - Text verification on regenerated DOCX/PDF:
    - rejected phrases absent in both rendered artifacts: `Ministério Público de Camões`, `entre Marmelar e Camões`, `Camões, 22 de março de 2026`, `tendo percorrido 0 km em cada sentido`
    - corrected phrases present: `Ministério Público de Beja`, `Beja, 22 de março de 2026`, `tendo percorrido 39 km em cada sentido`
    - bare `Camões` still appears only inside the legitimate street address `Rua Luís de Camões`
