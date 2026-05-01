# Profile-Driven Honorarios Identity

## 1) Title
Implement profile-managed honorarios identity, multi-profile selection, and sidebar profile management.

## 2) Goal and non-goals
- Goal:
  - replace fixed honorarios issuer constants with persisted user profiles
  - turn the sidebar `Profile` entry into a real profile manager
  - let honorarios export default to the primary profile with per-export secondary override
  - keep current honorarios wording/layout materially unchanged apart from substituted identity values
- Non-goals:
  - no CLI profile support
  - no Job Log schema migration
  - no persistent per-row or per-session profile override
  - no email line added to the honorarios DOCX in this pass

## 3) Scope (in/out)
- In:
  - GUI settings/profile persistence
  - sidebar profile management UI
  - honorarios document model/generation
  - honorarios export dialog integration
  - current-run, Job Log, and Gmail batch honorarios entrypoints
  - regression tests and settings migration tests
- Out:
  - generalized document-template engine work
  - redesign of the honorarios letter layout
  - coupling profile email to Gmail account settings behavior

## 4) Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/profile-honorarios-profiles`
- Base branch: `main`
- Base SHA: `15071f3b53d428088281f844848fd7a1434bef92`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch on canonical worktree path; approved-base floor satisfied from `main`

## 5) Interfaces/types/contracts affected
- `settings.json`
  - additive profile store:
    - `profiles`
    - `primary_profile_id`
- Honorarios internals
  - additive internal issuer-profile model for document generation
  - `HonorariosDraft` carries or resolves selected profile identity instead of module constants
- Qt UI
  - sidebar `Profile` opens a real profile manager dialog
  - `QtHonorariosExportDialog` gains profile selection and `Edit Profiles...`

## 6) File-by-file implementation steps
- `src/legalpdf_translate/user_settings.py`
  - add profile defaults, normalization, schema bump, migration seeding from legacy constants and existing Gmail account email
  - expose helpers to load/save normalized profile state through GUI settings
- `src/legalpdf_translate/honorarios_docx.py`
  - replace fixed-name/address/bank/tax constants with profile-backed identity values
  - keep current paragraph order/text structure stable
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - add a profile manager dialog
  - extend honorarios export dialog with profile selection/editing and selected-profile validation
- `src/legalpdf_translate/qt_gui/app_window.py`
  - route sidebar `Profile` to the new manager and refresh defaults after profile changes
  - ensure all honorarios entrypoints pass current profile state into the export dialog
- `tests/test_user_settings_schema.py`
  - cover profile seeding, normalization, and primary promotion behavior
- `tests/test_honorarios_docx.py`
  - cover profile-backed paragraph generation and honorarios dialog profile selection behavior
- `tests/test_qt_app_state.py`
  - cover sidebar profile entry opening the real manager and refresh behavior where needed

## 7) Tests and acceptance criteria
- `pytest` targets:
  - `tests/test_user_settings_schema.py`
  - `tests/test_honorarios_docx.py`
  - `tests/test_qt_app_state.py`
- Acceptance:
  - no fixed personal identity constants remain in honorarios generation
  - first app load seeds one usable primary profile from legacy honorarios defaults
  - profile manager can create/edit/set-primary/delete with last-profile protection
  - honorarios export defaults to primary profile on every open
  - secondary profile selection affects only that export
  - Gmail draft attachment flow and honorarios filename collision behavior stay intact

## 8) Rollout and fallback
- Implement on this feature branch only.
- If profile data is incomplete, block honorarios generation with a targeted validation message instead of generating a partial document.
- Preserve legacy seeded values so existing single-user installs continue to work immediately after upgrade.

## 9) Risks and mitigations
- Risk: settings migration breaks existing users.
  - Mitigation: additive schema change with deterministic default seeding and focused migration tests.
- Risk: honorarios/Gmail tests rely on fixed marker text.
  - Mitigation: preserve the core honorarios wording/signature markers and only substitute issuer values.
- Risk: UI complexity around profile editing from honorarios flow.
  - Mitigation: keep override ephemeral and rehydrate dialog state from persisted profiles after `Edit Profiles...`.

## 10) Assumptions/defaults
- Required honorarios identity fields are `first_name`, `last_name`, `postal_address`, `iban`, `iva_text`, and `irs_text`.
- `document_name_override` is optional and overrides the combined first/last name when present.
- Profile email is stored now for completeness/future use but does not print in the current honorarios DOCX.
- The primary profile is always the default export identity unless the user explicitly chooses another profile for that one export.

## 11) Execution log
- 2026-03-09:
  - Added shared `user_profile.py` modeling/normalization for persisted honorarios identity profiles.
  - Bumped GUI settings schema to `6` and migrated default settings to seed a primary profile from legacy honorarios constants, optionally seeding profile email from existing `gmail_account_email`.
  - Replaced fixed honorarios issuer constants with profile-backed values in `honorarios_docx.py` while preserving the current letter structure and marker text.
  - Implemented `QtProfileManagerDialog` and routed the sidebar `Profile` nav to a live profile manager.
  - Extended `QtHonorariosExportDialog` with primary-by-default profile selection, per-export secondary override, and in-flow `Edit Profiles...`.
  - Wired current-run, Job Log, and Gmail batch honorarios entrypoints to use the primary profile by default.
  - Validation results:
    - `./.venv311/Scripts/python.exe -m pytest -q tests/test_user_settings_schema.py` -> `18 passed`
    - `./.venv311/Scripts/python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_qt_app_state.py -k "profile_dialog or honorarios or settings_dialog_shows_build_identity_summary"` -> `32 passed, 121 deselected`
    - `./.venv311/Scripts/python.exe -m compileall src tests` -> passed
    - `./.venv311/Scripts/python.exe -m pytest -q tests/test_user_settings_schema.py tests/test_honorarios_docx.py tests/test_gmail_draft.py tests/test_qt_app_state.py` -> `185 passed`
  - Generated and rendered a temporary sample honorarios DOCX/PDF successfully during manual verification, then kept only repo-tracked changes in the worktree.
