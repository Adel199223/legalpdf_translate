# Court Email Selector and Deterministic Suggestion Plan

## Summary
Extend the existing `court_email` Job Log feature with:
- selectable default court-email options
- editable combo-box UI
- deterministic pattern-based suggestion ranking
- save-time vocab persistence

## Scope
- Add `vocab_court_emails` to Job Log settings defaults/load/save.
- Keep `court_email` as the DB/UI field name.
- Use deterministic local logic only; no AI for email selection or generation.
- Keep the Job Log table column hidden by default.

## Implementation Notes
- Seed the default selector list with the user-supplied `tribunais.org.pt` addresses.
- Use exact extracted email first; otherwise suggest the best ranked option from curated defaults plus deterministic generated hints.
- Support known slug aliases:
  - `Reguengos de Monsaraz -> rmonsaraz`
  - `Foro Alentejo -> falentejo`
- Persist newly saved non-empty court emails back into `vocab_court_emails`.

## Validation
- Targeted tests for settings/vocab persistence, deterministic ranking, Qt dialog save flow, and seed preparation.
- Full `pytest` and `compileall`.
