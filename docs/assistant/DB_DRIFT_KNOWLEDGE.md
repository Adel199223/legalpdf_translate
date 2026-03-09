# DB Drift Knowledge

## Purpose
Canonical persistence drift guidance for the SQLite job log store.

## Scope
- `src/legalpdf_translate/joblog_db.py`
- Job log schema versions and migrations.
- Backward-compatible migration checks.

## Drift Signals
- Runtime migration exceptions.
- Missing expected columns after deployment.
- Mixed schema versions across user machines.

## Current additive schema delta
Job-log v2 adds these columns to `job_runs` without removing older fields:
- `target_lang`
- `run_id`
- `total_tokens`
- `estimated_api_cost`
- `quality_risk_score`
- `output_docx_path`
- `partial_docx_path`

The current migration is additive and idempotent. It also backfills:
- `target_lang` from `lang` when missing.
- `estimated_api_cost` from `api_cost` when missing.

Save-to-Job-Log can prefill these values from the latest run summary, but the user can still edit them before saving the row.
Historical Gmail draft + honorarios flows reuse `output_docx_path` first, then `partial_docx_path`, before falling back to exact `run_id` recovery or a one-time manual picker.
Job-log word-count semantics now use translated output artifacts with this precedence:
1. final DOCX
2. partial DOCX
3. `pages/page_*.txt`
4. `0`

`expected_total` and `profit` in the Save-to-Job-Log flow are recalculated from that translated-output word count source.

## Safe Process
1. Inspect current schema version and expected migration chain.
2. Add additive migration first; avoid destructive edits in-place.
3. Back up DB before risky migration operations.
4. Run migration tests and targeted data integrity checks.
5. Document schema delta in relevant workflow docs.

## Rollback/Safety
- Keep migration changes reversible where possible.
- Do not drop old columns/tables until replacement path is verified.
- Require approval gate for destructive schema operations.

## Validation
- `python -m pytest -q tests/test_db_migration_joblog_v2.py`
- `python -m pytest -q tests/test_qt_app_state.py`
- `dart run tooling/validate_agent_docs.dart`
