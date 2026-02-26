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
- `dart run tooling/validate_agent_docs.dart`
