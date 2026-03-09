# Profile Phone for Honorarios Gmail

## Goal and non-goals
- Goal: add an optional profile phone number and render it only in the honorarios Gmail draft body under the selected profile name.
- Goal: keep the selected honorarios export profile as the single identity source for both the DOCX and Gmail draft.
- Non-goal: change the honorarios DOCX layout or add phone/email into the document.
- Non-goal: make phone number a required profile field.

## Scope
- In scope: profile model/settings, profile manager UI, honorarios Gmail draft builders, and focused regression tests.
- Out of scope: unrelated Gmail flows, job log schema changes, and docs sync in this pass.

## Worktree provenance
- Worktree path: `/mnt/c/Users/FA507/.codex/legalpdf_translate`
- Branch name: `feat/profile-honorarios-profiles`
- Base branch: `main`
- Base SHA: `15071f3b53d428088281f844848fd7a1434bef92`
- Target integration branch: `main`
- Canonical build status: noncanonical feature branch allowed because `HEAD` contains the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- `UserProfile` gains additive optional field `phone_number`.
- GUI settings/profile normalization persists `phone_number` without making it required.
- Honorarios Gmail draft builders become profile-aware for the signature block.

## File-by-file implementation steps
- Update `src/legalpdf_translate/user_profile.py` to add `phone_number`, serialize/normalize it, and keep it optional.
- Update `src/legalpdf_translate/qt_gui/dialogs.py` profile manager UI to edit/save the phone number and pass the selected profile into Gmail draft creation.
- Update `src/legalpdf_translate/gmail_draft.py` to replace the fixed body constant with a builder that renders the selected profile name and optional phone line.
- Update focused tests in `tests/test_gmail_draft.py`, `tests/test_user_settings_schema.py`, and honorarios/Qt integration tests to cover blank/default phone behavior and selected secondary-profile Gmail signatures.

## Tests and acceptance criteria
- `tests/test_user_settings_schema.py` covers round-trip persistence and normalization with missing `phone_number`.
- `tests/test_gmail_draft.py` covers phone included/omitted in both honorarios draft flows.
- Targeted honorarios/Qt tests confirm the selected profile feeds the Gmail draft path without changing DOCX content.

## Rollout and fallback
- Existing users pick up a blank `phone_number` automatically through additive normalization.
- If a profile has no phone number, Gmail draft creation still succeeds and omits the phone line.

## Risks and mitigations
- Risk: drift between the selected export profile and Gmail signature identity.
  - Mitigation: pass the same selected `UserProfile` through the Gmail draft builder path instead of recomputing identity separately.
- Risk: breaking exact-body Gmail tests.
  - Mitigation: update tests to assert the intended signature output explicitly for both present and blank phone cases.

## Assumptions/defaults
- The phone line is rendered as the raw phone number on its own line below the sender name.
- This applies only to honorarios Gmail drafts and batch replies, not to the DOCX itself.

## Executed validations and outcomes
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_user_settings_schema.py tests/test_gmail_draft.py` -> passed (`35 passed`)
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_honorarios_docx.py tests/test_qt_app_state.py -k "honorarios or profile_manager or offer_gmail_batch_reply_draft or finalize_completed_gmail_batch"` -> passed (`36 passed, 117 deselected`)
- `./.venv311/Scripts/python.exe -m compileall src tests` -> passed
- `./.venv311/Scripts/python.exe -m pytest -q tests/test_user_settings_schema.py tests/test_gmail_draft.py tests/test_honorarios_docx.py tests/test_qt_app_state.py` -> passed (`188 passed`)
