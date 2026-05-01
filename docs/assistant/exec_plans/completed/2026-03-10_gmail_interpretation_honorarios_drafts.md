# Gmail Interpretation Honorarios Drafts

## Goal and non-goals
- Goal: extend Gmail intake so a notice email can drive an interpretation-only flow that downloads the original notice attachment, extracts interpretation metadata without translation, saves or edits the interpretation Job Log entry, generates the interpretation honorarios DOCX, and creates a Gmail reply draft in the original thread with the honorarios DOCX only.
- Goal: make interpretation honorarios use the service date as the document closing date when the service date is a valid ISO date.
- Non-goal: add historical re-threading for old Job Log rows.
- Non-goal: attach translated DOCX files in interpretation Gmail drafts.
- Non-goal: change the existing translation Gmail batch workflow beyond the new explicit mode split.

## Scope
- In scope: Gmail intake review UI, Gmail interpretation download/session flow, interpretation Gmail draft builder/body text, interpretation honorarios date semantics, tests, and touched-scope docs.
- Out of scope: Gmail provider changes, database schema changes for Gmail thread/message persistence, and non-Gmail interpretation workflows beyond the shared date fix.

## Worktree provenance
- Worktree path: `c:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/gmail-interpretation-honorarios`
- Base branch: `main`
- Base SHA: `2fb140b0584479ee737638674fbc21f588f4d842`
- Target integration branch: `main`
- Canonical build status: canonical-approved base floor satisfied via `docs/assistant/runtime/CANONICAL_BUILD.json` (`approved_base_head_floor=4e9d20e`)

## Interfaces/types/contracts affected
- Gmail intake review result will carry workflow kind in addition to selected attachments.
- Gmail draft layer gains an interpretation-specific reply-draft builder that attaches only the generated honorarios DOCX.
- Gmail intake app flow gains a dedicated interpretation session/finalization path instead of overloading translation batch session semantics.
- Interpretation honorarios drafts will derive `date_pt` from `service_date` when it parses as ISO.
- Product contract update: interpretation honorarios can produce a Gmail reply draft only when started from Gmail intake; manual/local interpretation export remains available.

## File-by-file implementation steps
- `src/legalpdf_translate/honorarios_docx.py`
  - make interpretation draft date derive from `service_date` when valid.
  - add interpretation-specific Gmail body helpers if the draft text layer stays here; otherwise keep the document change only.
- `src/legalpdf_translate/gmail_draft.py`
  - add interpretation subject/body/attachment builder using `reply_to_message_id`.
  - keep translation validation isolated so interpretation paths never require translated DOCX artifacts.
- `src/legalpdf_translate/gmail_batch.py`
  - add interpretation intake result/session structures for one selected notice attachment and staged original attachment reuse.
  - reuse exact-message fetch and attachment download mechanics without translation batch-only assumptions.
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - extend the Gmail intake review dialog with explicit workflow mode selection.
  - translation mode keeps target language and current review behavior.
  - interpretation mode hides translation-only controls and enforces one selected attachment.
- `src/legalpdf_translate/qt_gui/app_window.py`
  - branch Gmail intake finalization into translation batch vs interpretation notice flow.
  - for interpretation: download attachment, build interpretation seed from PDF/image, open save-to-joblog, open honorarios export, and create the Gmail reply draft without re-attaching the source notice.
  - keep translation batch functions and finalization unchanged except for the new mode dispatch.
- `tests/test_honorarios_docx.py`
  - cover interpretation closing date derived from service date and interpretation Gmail body/draft builder behavior.
- `tests/test_gmail_draft.py`
  - cover interpretation Gmail draft builder attachment set, body text, and reply-to behavior.
- `tests/test_gmail_batch.py`
  - cover interpretation intake/session payload or attachment staging behavior if logic is added there.
- `tests/test_qt_app_state.py`
  - cover Gmail review mode switching, interpretation single-attachment validation, interpretation Gmail finalization path, and translation regression.
- Docs
  - update `APP_KNOWLEDGE.md`, `docs/assistant/APP_KNOWLEDGE.md`, and relevant user guides to replace the old local-only interpretation Gmail wording with the new Gmail-intake interpretation workflow.

## Tests and acceptance criteria
- `tests/test_honorarios_docx.py`
- `tests/test_gmail_draft.py`
- `tests/test_gmail_batch.py`
- `tests/test_qt_app_state.py`
- `dart run tooling/validate_agent_docs.dart`
- Acceptance:
  - translation Gmail batch still behaves exactly as before.
  - interpretation Gmail intake requires one selected notice attachment and never requests a target language.
  - interpretation Gmail draft replies in-thread with the honorarios DOCX only.
  - interpretation honorarios closing date matches `service_date`.

## Rollout and fallback
- Rollout stays on this feature branch until validated.
- If Gmail interpretation draft creation fails after DOCX generation, the local honorarios DOCX should still remain saved and the user should get a clear Gmail failure message, matching current Gmail draft failure handling.

## Risks and mitigations
- Risk: translation Gmail review regressions while adding the mode split.
  - Mitigation: keep translation mode as the default path and cover it with existing plus new regression tests.
- Risk: interpretation seed extraction differs between PDF and image notice attachments.
  - Mitigation: reuse the existing notification PDF and photo/screenshot extraction helpers instead of duplicating parsing logic.
- Risk: Gmail interpretation path still mentions or re-attaches the notice even though the final draft should send only the honorarios DOCX.
  - Mitigation: keep the notice staged only for local extraction and remove it entirely from the interpretation reply-draft builder and body text.

## Assumptions/defaults
- Interpretation Gmail drafts are always reply-in-thread.
- Interpretation Gmail intake handles exactly one selected notice attachment per flow.
- Historical Job Log rows do not gain Gmail thread/message persistence in this pass.
- Manual/local interpretation honorarios generation remains available alongside the new Gmail-intake interpretation reply flow.

## Completion evidence
- Integrated on publish branch `codex/gmail-intake-publish`.
- Combined validation on the final publish branch:
  - `.\.venv311\Scripts\python.exe -m pytest tests\test_gmail_batch.py tests\test_gmail_draft.py tests\test_honorarios_docx.py tests\test_qt_app_state.py tests\test_user_settings_schema.py tests\test_gmail_focus_host.py tests\test_gmail_intake.py tests\test_launch_qt_build.py -q` -> `277 passed`
  - `dart run tooling/validate_agent_docs.dart` -> `PASS`
