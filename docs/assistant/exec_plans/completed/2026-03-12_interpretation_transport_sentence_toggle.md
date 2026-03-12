# ExecPlan: Interpretation Transport Sentence Toggle

## Goal and non-goals
- Goal: add a persisted interpretation-only honorários toggle that omits the transport/distance clause when requested, while keeping inclusion as the default.
- Goal: keep the choice canonical on the Job Log row and reusable across manual/save/edit/historical interpretation honorários flows.
- Non-goal: change translation honorários generation or Gmail attachment behavior.
- Non-goal: remove or rewrite stored KM/profile distance data when the clause is omitted.

## Scope (in/out)
- In scope:
  - interpretation honorários draft model and paragraph builder
  - Job Log schema/read/write wiring for the new persisted flag
  - interpretation save/edit/export dialog controls and persistence handoff
  - focused regression coverage across Job Log, export dialogs, and app window interpretation flows
- Out of scope:
  - docs sync unless requested after implementation
  - visible Job Log table columns for the new flag
  - translation honorários content or UI

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `codex/honorarios-pdf-stage1`
- Base branch: `main`
- Base SHA: `6d738b20e6080e63f2b9457a9ad95d9b67e41e4f`
- Target integration branch: `main`
- Canonical build status: dirty worktree with prior approved honorários rollout changes; this pass must stay focused on interpretation transport-clause control

## Interfaces/types/contracts affected
- `HonorariosDraft`: new interpretation-oriented `include_transport_sentence_in_honorarios` boolean, default `True`.
- `build_interpretation_honorarios_draft(...)`: new boolean input, default `True`.
- `JobLogSeed` and normalized Job Log payloads: new `include_transport_sentence_in_honorarios` field stored as boolean/int.
- SQLite `job_runs`: new `include_transport_sentence_in_honorarios INTEGER DEFAULT 1` column.

## File-by-file implementation steps
1. Update `src/legalpdf_translate/honorarios_docx.py` to carry the new flag and compose interpretation body text with an optional transport clause.
2. Update `src/legalpdf_translate/joblog_db.py`, `src/legalpdf_translate/qt_gui/dialogs.py`, and `src/legalpdf_translate/qt_gui/app_window.py` so the flag persists through Job Log save/edit/export and save-result-backed interpretation export flows.
3. Update `tests/test_honorarios_docx.py`, `tests/test_qt_app_state.py`, and `tests/test_db_migration_joblog_v2.py` to lock defaulting, omission behavior, UI state, and persistence.

## Tests and acceptance criteria
- `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_honorarios_docx.py tests/test_qt_app_state.py`
- `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
- `.\\.venv311\\Scripts\\python.exe -m pytest -q`
- Acceptance:
  - interpretation honorários include the transport clause by default
  - unchecking the new checkbox omits the full transport clause and does not require/prompt for KM
  - accepted exports persist the new flag back to the Job Log-backed interpretation context
  - translation behavior remains unchanged

## Rollout and fallback
- Rollout: schema migration plus interpretation-only UI/document updates in the same pass.
- Fallback: revert the new flag wiring and paragraph branch if persistence or UI state regresses.

## Risks and mitigations
- Risk: the new DB column defaults to `NULL` for helper/test inserts that do not pass the field.
- Mitigation: coalesce reads to `1` and make insert helpers default the new field to included when omitted.
- Risk: disabled distance controls could accidentally clear stored KM values.
- Mitigation: disable without mutating the text field and keep payload persistence unchanged unless the user edits it.
- Risk: save-result-driven interpretation exports from the main window could diverge from Job Log state.
- Mitigation: persist accepted export checkbox changes back to the saved row where a row id exists.

## Assumptions/defaults
- The checkbox removes the full `bem como o pagamento das despesas de transporte... km em cada sentido` clause.
- New and legacy interpretation rows default to including the transport clause.
- The new field remains hidden from the Job Log visible-column picker/table.

## Completion evidence
- Added `include_transport_sentence_in_honorarios` to interpretation honorários drafts, Job Log seeds/payloads, and SQLite schema migration/read paths.
- Updated interpretation save/edit/export dialogs so the new checkbox defaults on, disables KM handling when off, and persists the accepted export choice back to Job Log-backed interpretation flows.
- Updated interpretation paragraph generation to omit the full transport clause cleanly when the checkbox is off while leaving translation output unchanged.
- Added regression coverage in `tests/test_db_migration_joblog_v2.py`, `tests/test_honorarios_docx.py`, and `tests/test_qt_app_state.py`.
- Validation completed:
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q tests/test_db_migration_joblog_v2.py tests/test_honorarios_docx.py tests/test_qt_app_state.py`
  - `.\\.venv311\\Scripts\\python.exe -m compileall src tests`
  - `.\\.venv311\\Scripts\\python.exe -m pytest -q`
  - artifact-level smoke check generated interpretation DOCX output with and without the transport clause and confirmed the expected body text
