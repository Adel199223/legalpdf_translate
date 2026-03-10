# Interpretation Honorarios Wave 1

## 1. Title
Manual interpretation honorarios core.

## 2. Goal and non-goals
- Goal:
  - implement a manual interpretation honorarios workflow without waiting for notification/photo import
  - make Job Log, profile settings, and honorarios export kind-aware
  - provide a real `Job Log -> Add... -> Blank interpretation entry` path
- Non-goals:
  - no notification import yet
  - no photo/screenshot import yet
  - no remote/WebEx branch
  - no interpretation Gmail draft integration

## 3. Scope (in/out)
- In:
  - Job Log migration for interpretation fields
  - interpretation-aware payload normalization
  - profile travel origin and distance map support
  - interpretation honorarios draft/template generation
  - interpretation-aware export dialog and Job Log editor
  - blank interpretation add flow
- Out:
  - import automation waves
  - external integrations

## 4. Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/interpretation-honorarios`
- Base branch: `main`
- Base SHA: `abf608f16fac69e477849b9e8b3e040502856999`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on the canonical worktree path; approved-base floor satisfied from `main`

## 5. Interfaces/types/contracts affected
- `settings.json`
  - additive profile fields:
    - `travel_origin_label`
    - `travel_distances_by_city`
- Job Log DB:
  - additive columns:
    - `travel_km_outbound`
    - `travel_km_return`
    - `use_service_location_in_honorarios`
- Honorarios internals:
  - kind-aware draft contract with translation and interpretation branches
- Qt:
  - interpretation-specific fields/validation in Job Log editing and honorarios export
  - new blank interpretation entrypoint from Job Log

## 6. File-by-file implementation steps
- `src/legalpdf_translate/user_profile.py`
  - add travel origin and per-city distance map helpers
- `src/legalpdf_translate/user_settings.py`
  - migrate and persist new profile travel fields
- `src/legalpdf_translate/joblog_db.py`
  - add interpretation columns and expose them in list/insert/update paths
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - make job-log normalization job-type-aware
  - add interpretation controls to save/edit flow
  - add Job Log `Add...` flow for blank interpretation entries
  - make honorarios export dialog branch by kind
- `src/legalpdf_translate/honorarios_docx.py`
  - add interpretation draft/template generation while keeping translation branch unchanged
- `tests/`
  - migration tests
  - honorarios template tests
  - settings/profile tests
  - Qt flow tests

## 7. Tests and acceptance criteria
- `tests/test_user_settings_schema.py`
- `tests/test_db_migration_joblog_v2.py`
- `tests/test_honorarios_docx.py`
- `tests/test_qt_app_state.py`
- Acceptance:
  - blank interpretation entries can be created from Job Log
  - interpretation rows save without translation-only numeric requirements
  - interpretation export auto-fills ida/volta from the selected profile distance map when available
  - missing city distance prompts for one-way distance and persists it to the selected profile
  - translation honorarios behavior remains intact

## 8. Rollout and fallback
- Land Wave 1 as a standalone usable core.
- If distance prompting proves too coupled to export flow, fall back to editing km directly in the Job Log form while still persisting per-profile defaults.

## 9. Risks and mitigations
- Risk: UI clutter in the existing edit dialog.
  - Mitigation: show/de-emphasize fields based on `job_type`.
- Risk: filename collisions between translation and interpretation honorarios.
  - Mitigation: add a kind suffix for interpretation filenames.
- Risk: recipient wording guess is wrong in some judicial cases.
  - Mitigation: interpretation export allows manual recipient override.

## 10. Assumptions/defaults
- `use_service_location_in_honorarios` defaults to `false`.
- `service_city` remains blank by default until explicitly confirmed.
- Unknown one-way city distance is prompted once and then saved per profile.
- Travel destination falls back to `case_city` unless explicit service-location usage is enabled.

## 11. Current status
- Wave 1 implementation complete in the current feature branch worktree.
- Outcome:
  - manual blank interpretation entries are supported
  - interpretation honorários generation is kind-aware and profile-backed
  - Job Log storage and normalization support interpretation-specific travel/location fields
- Next stage:
  - Wave 2 notification-first import from local PDF
