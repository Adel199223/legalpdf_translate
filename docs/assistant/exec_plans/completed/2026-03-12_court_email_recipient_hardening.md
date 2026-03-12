# Court Email Recipient Hardening for Gmail Drafts

## Goal and non-goals
- Goal: prevent Gmail draft recipients from silently drifting away from the document's court email, especially when OCR/header extraction misses the address and saved court-email vocabulary contains conflicting domain variants.
- Non-goals: rewriting historical job-log rows, adding DB migrations, changing Gmail draft APIs, or broad metadata-autofill redesign beyond the court-email path.

## Scope (in/out)
- In:
  - court-email extraction fallback hardening for PDF metadata
  - shared court-email resolution metadata and ranking cleanup
  - `vocab_court_emails` normalization for same-local-part collisions
  - Save-to-Job-Log and Gmail draft blocking/warning behavior for inferred or ambiguous recipients
  - focused regression tests for the Beja `.org.pt` vs `.gov.pt` failure
- Out:
  - bulk repair of already-saved rows
  - Gmail bridge/native-host behavior
  - non-court email heuristics beyond this recipient-safety contract

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_court_email_recipient_hardening`
- branch name: `codex/court-email-recipient-hardening`
- base branch: `main`
- base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- target integration branch: `main`
- canonical build status or intended noncanonical override: noncanonical feature worktree based on the canonical `main` floor declared in `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Add one internal court-email resolution helper/type that carries:
  - selected email
  - source provenance
  - ambiguity/conflict state
  - ranked candidates
- Preserve current external Gmail draft interfaces and Job Log schema.
- Tighten the Gmail draft behavior contract so inferred/ambiguous recipients block automatic draft creation until the user corrects `Court Email`.

## File-by-file implementation steps
1. `src/legalpdf_translate/metadata_autofill.py`
   - add the shared resolution type/helper and domain-aware ranking for same-local-part collisions
   - harden PDF metadata extraction to retry email discovery from full-page OCR/text when header extraction is empty or email-less
   - keep exact document emails highest priority
2. `src/legalpdf_translate/user_settings.py`
   - normalize `vocab_court_emails` with same-local-part de-duplication and canonical `tribunais.org.pt` preference
3. `src/legalpdf_translate/qt_gui/app_window.py`
   - route seed preparation and Gmail batch / interpretation draft creation through the shared court-email resolution/preflight guard
4. `src/legalpdf_translate/qt_gui/dialogs.py`
   - surface lightweight court-email provenance in Save-to-Job-Log
   - block honorarios Gmail draft creation when recipient provenance is inferred or ambiguous
5. Tests
   - update focused metadata, Qt, and Gmail regression tests for extraction fallback, domain collision handling, and draft blocking

## Tests and acceptance criteria
- `tests/test_metadata_autofill_header.py`
  - exact document email wins
  - header-empty page falls back to full-page extraction for email discovery
  - same-local-part `.org.pt` and `.gov.pt` settings prefer `.org.pt`
- `tests/test_qt_app_state.py`
  - Save-to-Job-Log seed/provenance follows the shared resolver
  - inferred/ambiguous recipients block Gmail draft creation paths
- `tests/test_honorarios_docx.py`
  - honorarios Gmail draft is blocked with warning when recipient is inferred/ambiguous
- `tests/test_gmail_batch.py`
  - Gmail batch finalization blocks draft creation for inferred/ambiguous court-email recipients
- Acceptance:
  - the Beja notice scenario cannot produce a `.gov.pt` draft recipient when `.org.pt` is the document or canonical candidate

## Rollout and fallback
- Roll out as code-only behavior change on `main`.
- If full-page email fallback fails, the app must warn and stop draft creation rather than guessing silently.

## Risks and mitigations
- Risk: over-blocking drafts for legitimate manual emails.
  - Mitigation: manual user-entered `Court Email` remains allowed and is treated as confirmed/manual provenance.
- Risk: changing ranking alters existing convenience autofill.
  - Mitigation: exact document email precedence remains unchanged; only conflicting inferred collisions get stricter handling.
- Risk: settings normalization removes desired legacy variants.
  - Mitigation: preserve distinct local parts; only same-local-part conflicts are normalized by canonical preference.

## Assumptions/defaults
- `tribunais.org.pt` is the canonical tie-breaker only for same-local-part domain conflicts when no exact document email is available.
- Manual correction in the dialog is sufficient confirmation for draft creation; no extra persisted provenance schema is needed.
- Existing bad historical rows remain untouched unless a later cleanup task is requested.

## Execution notes
- Added `src/legalpdf_translate/court_email.py` as the shared internal resolver/provenance contract for ranking, normalization, ambiguity detection, and Gmail draft blocking warnings.
- Hardened `metadata_autofill.py` so priority-page extraction rechecks the same page with full-text fallback when header extraction has no usable email.
- Normalized `vocab_court_emails` on both load and save, with canonical `.org.pt` ordering ahead of same-local-part variants such as `.gov.pt`.
- Routed Save-to-Job-Log, Gmail batch reply drafts, interpretation reply drafts, and honorários Gmail drafts through the shared court-email safety behavior.
- Historical Job Log honorários drafts now only use the saved `court_email` value; they no longer silently re-infer a recipient when that field is blank.

## Validation
- Targeted regression suite passed:
  - `tests/test_metadata_autofill_header.py`
  - `tests/test_column_visibility_persistence.py`
  - `tests/test_qt_app_state.py`
  - `tests/test_honorarios_docx.py`
  - `tests/test_gmail_batch.py`
- Result: `243 passed`
- Reality check against the live Beja-style polluted settings state now resolves to `beja.ministeriopublico@tribunais.org.pt` but marks it `ambiguous=True`, so Gmail draft creation is blocked until the recipient is manually confirmed.

## Execution closeout
- Status: implementation complete on `codex/court-email-recipient-hardening`; Assistant Docs Sync and publish/merge remain pending after the implementation commit.
- Changed files:
  - `src/legalpdf_translate/court_email.py`
  - `src/legalpdf_translate/gmail_batch.py`
  - `src/legalpdf_translate/metadata_autofill.py`
  - `src/legalpdf_translate/qt_gui/app_window.py`
  - `src/legalpdf_translate/qt_gui/dialogs.py`
  - `src/legalpdf_translate/user_settings.py`
  - `tests/test_column_visibility_persistence.py`
  - `tests/test_honorarios_docx.py`
  - `tests/test_metadata_autofill_header.py`
  - `tests/test_qt_app_state.py`
- Outcome summary:
  - document-extracted court emails now outrank saved vocabulary suggestions through a shared resolver with provenance, ambiguity, and ranked candidate tracking
  - header-first PDF metadata extraction now falls back to the same page's full text when the header path yields no usable email
  - same-local-part `vocab_court_emails` collisions are normalized with canonical `tribunais.org.pt` preference ahead of alternate domains such as `.gov.pt`
  - Gmail draft creation paths now block and warn when the recipient is inferred or ambiguous instead of drafting to an unconfirmed address
  - Save-to-Job-Log surfaces the inferred/ambiguous court-email state before the Gmail-draft step
