# Page 1 Default Translation Start

## Goal and non-goals
- Goal: enforce page `1` as the default first page to translate across the main translation form, Gmail attachment review, Gmail attachment preview wording, and settings-backed UI behavior.
- Non-goals: remove the ability to manually start from page `2+`, change explicit per-run/per-attachment start-page selections, or change interpretation notice flows.

## Scope (in/out)
- In scope:
  - main-window translation start-page initialization
  - Gmail attachment review default start-page seeding
  - Gmail attachment preview wording and CTA copy
  - settings normalization so legacy non-`1` defaults no longer leak back into UI
  - touched user guides / knowledge docs
  - regression updates for the new page-`1` contract
- Out of scope:
  - translation run validation rules for explicit user-entered later pages
  - Gmail interpretation notice path
  - unrelated Gmail draft / honorarios behavior

## Worktree provenance
- worktree path: `c:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/gmail-interpretation-honorarios`
- base branch: `main`
- base SHA: `2fb140b0584479ee737638674fbc21f588f4d842`
- target integration branch: `main`
- canonical build status: approved-base floor present on top of `main`, with additional uncommitted Gmail interpretation work already in progress in this worktree

## Interfaces/types/contracts affected
- Translation UI contract:
  - default first page to translate is always `1`
  - page `2+` remains an explicit override only
- Settings compatibility contract:
  - legacy `default_start_page` may still exist in stored settings, but the app normalizes it to `1` and does not expose it as a configurable default
- Gmail review contract:
  - PDF attachment review rows seed to page `1`
  - image attachments remain fixed at page `1`

## File-by-file implementation steps
- `src/legalpdf_translate/qt_gui/app_window.py`
  - initialize blank/new translation start page to `1`
  - stop passing the main-form current start page into Gmail review as the review default
- `src/legalpdf_translate/qt_gui/dialogs.py`
  - seed Gmail review PDF rows to `1`
  - relabel the review and preview copy so page `1` is framed as the default
  - remove the editable settings control for a global default start page
- `src/legalpdf_translate/user_settings.py`
  - normalize any legacy `default_start_page` value to `1` during GUI settings load
- `tests/test_qt_app_state.py`
  - replace expectations that still lock non-`1` defaults
  - verify explicit overrides still work
- `APP_KNOWLEDGE.md`
  - align product knowledge with the new page-`1` default wording
- `docs/assistant/APP_KNOWLEDGE.md`
  - align assistant-facing runtime truth with the new page-`1` default wording
- `docs/assistant/features/APP_USER_GUIDE.md`
  - update guidance so page `1` is default and later pages are an explicit choice
- `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
  - update translation preview/review guidance accordingly
- `docs/assistant/DOCS_REFRESH_NOTES.md`
  - record the doc-sync evidence for this behavior change

## Tests and acceptance criteria
- Run:
  - `.\.venv311\Scripts\python.exe -m pytest tests\test_qt_app_state.py -q`
  - targeted settings/UI slice if needed
  - `dart run tooling/validate_agent_docs.dart`
- Acceptance:
  - main translation form starts at page `1`
  - Gmail review PDF rows start at page `1` regardless of prior main-form state
  - preview defaults to page `1` but later-page selection still works
  - settings no longer round-trip a configurable non-`1` start-page default back into the UI

## Rollout and fallback
- Rollout is immediate in the local app once restarted from this worktree.
- Fallback is limited to restoring the removed settings field and old initialization behavior if this breaks explicit user overrides, which the regression slice should catch.

## Risks and mitigations
- Risk: removing the settings field breaks dialog load/save expectations.
  - Mitigation: keep the stored key compatibility-safe and normalize it internally to `1`.
- Risk: Gmail review tests still assume old inherited defaults.
  - Mitigation: update those tests to assert explicit overrides still survive after manual changes.

## Assumptions/defaults
- Page `1` is the only acceptable automatic default.
- Persisted non-`1` defaults are legacy noise, not desired user intent.
- Explicit later-page choices in a given run remain fully supported.

## Completion evidence
- Integrated on publish branch `codex/gmail-intake-publish`.
- Combined validation on the final publish branch:
  - `.\.venv311\Scripts\python.exe -m pytest tests\test_gmail_batch.py tests\test_gmail_draft.py tests\test_honorarios_docx.py tests\test_qt_app_state.py tests\test_user_settings_schema.py tests\test_gmail_focus_host.py tests\test_gmail_intake.py tests\test_launch_qt_build.py -q` -> `277 passed`
  - `dart run tooling/validate_agent_docs.dart` -> `PASS`
